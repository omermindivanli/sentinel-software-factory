"""Main orchestration engine using LangGraph."""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Awaitable
from uuid import UUID
import structlog

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from factory.config.settings import settings
from factory.orchestration.state import (
    FactoryState, 
    WorkItem, 
    StageExecution, 
    StageStatus,
    AgentExecution,
    AgentStatus,
    GateResult,
    HumanCheckpoint,
    SandboxExecution,
    SandboxStatus,
)
from factory.orchestration.checkpoints import create_checkpoint_store
from factory.orchestration.router import get_router, ModelRouter
from factory.orchestration.memory_bus import (
    get_memory_bus, 
    get_context_propagator, 
    get_artifact_store,
    MemoryBus,
    ContextPropagator,
    ArtifactStore,
)

logger = structlog.get_logger(__name__)


# Type aliases
StageHandler = Callable[[FactoryState], Awaitable[FactoryState]]
GateHandler = Callable[[FactoryState], Awaitable[GateResult]]


class FactoryEngine:
    """
    Main orchestration engine for the software factory.
    Uses LangGraph for stateful, checkpointed execution.
    """
    
    def __init__(
        self,
        router: Optional[ModelRouter] = None,
        memory_bus: Optional[MemoryBus] = None,
        context_propagator: Optional[ContextPropagator] = None,
        artifact_store: Optional[ArtifactStore] = None,
    ):
        self.router = router or get_router()
        self.memory_bus = memory_bus or get_memory_bus()
        self.context_propagator = context_propagator or get_context_propagator()
        self.artifact_store = artifact_store or get_artifact_store()
        self.checkpoint_store = create_checkpoint_store(settings)
        
        # Stage handlers (registered dynamically)
        self._stage_handlers: Dict[str, StageHandler] = {}
        self._gate_handlers: Dict[str, GateHandler] = {}
        
        # Human checkpoint callbacks
        self._checkpoint_callbacks: List[Callable[[HumanCheckpoint], Awaitable[bool]]] = []
        
        # Build the graph
        self._graph = self._build_graph()
        self._app = self._graph.compile(
            checkpointer=SqliteSaver.from_conn_string("sqlite:///.factory/checkpoints.sqlite")
        )
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        workflow = StateGraph(FactoryState)
        
        # Add nodes for each stage
        for stage_id in ["triage", "planning", "execution", "validation", "release", "document", "monitor"]:
            workflow.add_node(stage_id, self._create_stage_node(stage_id))
        
        # Add gate nodes
        workflow.add_node("gate_pre_execution", self._create_gate_node("pre_execution"))
        workflow.add_node("gate_code_quality", self._create_gate_node("code_quality"))
        workflow.add_node("gate_tests", self._create_gate_node("tests"))
        workflow.add_node("gate_security", self._create_gate_node("security"))
        workflow.add_node("gate_review", self._create_gate_node("review"))
        workflow.add_node("gate_human_approval", self._create_gate_node("human_approval"))
        workflow.add_node("gate_performance", self._create_gate_node("performance"))
        workflow.add_node("gate_documentation", self._create_gate_node("documentation"))
        
        # Add checkpoint node
        workflow.add_node("human_checkpoint", self._checkpoint_node)
        
        # Set entry point
        workflow.set_entry_point("triage")
        
        # Add edges (sequential by default, conditional for gates)
        workflow.add_edge("triage", "gate_pre_execution")
        workflow.add_conditional_edges(
            "gate_pre_execution",
            self._gate_router("pre_execution"),
            {"pass": "planning", "fail": END}
        )
        
        workflow.add_edge("planning", "gate_pre_execution")
        workflow.add_conditional_edges(
            "gate_pre_execution",
            self._gate_router("pre_execution"),
            {"pass": "execution", "fail": END, "human": "human_checkpoint"}
        )
        
        workflow.add_edge("execution", "gate_code_quality")
        workflow.add_conditional_edges(
            "gate_code_quality",
            self._gate_router("code_quality"),
            {"pass": "gate_tests", "fail": "execution", "human": "human_checkpoint"}
        )
        
        workflow.add_edge("gate_tests", "gate_security")
        workflow.add_conditional_edges(
            "gate_security",
            self._gate_router("security"),
            {"pass": "gate_review", "fail": "execution", "human": "human_checkpoint"}
        )
        
        workflow.add_edge("gate_review", "gate_human_approval")
        workflow.add_conditional_edges(
            "gate_human_approval",
            self._gate_router("human_approval"),
            {"pass": "release", "fail": "execution", "human": "human_checkpoint"}
        )
        
        workflow.add_edge("release", "gate_performance")
        workflow.add_conditional_edges(
            "gate_performance",
            self._gate_router("performance"),
            {"pass": "gate_documentation", "fail": "execution", "warn": "document"}
        )
        
        workflow.add_edge("gate_documentation", "document")
        workflow.add_conditional_edges(
            "document",
            lambda s: "monitor" if s.overall_status == "running" else END,
            {"monitor": "monitor", END: END}
        )
        
        workflow.add_edge("monitor", END)
        
        # Human checkpoint loops back
        workflow.add_edge("human_checkpoint", "gate_pre_execution")
        
        return workflow
    
    def _create_stage_node(self, stage_id: str) -> StageHandler:
        """Create a stage execution node."""
        async def stage_node(state: FactoryState) -> FactoryState:
            logger.info("stage_start", stage=stage_id, run_id=str(state.run_id))
            
            # Initialize stage execution
            stage_exec = StageExecution(
                stage_id=stage_id,
                status=StageStatus.RUNNING,
                started_at=datetime.utcnow(),
            )
            state.stages[stage_id] = stage_exec
            state.current_stage = stage_id
            state.overall_status = "running"
            state.updated_at = datetime.utcnow()
            
            # Load previous context
            prev_context = await self.context_propagator.load_previous_context(
                str(state.run_id), stage_id, state.stage_order
            )
            state.shared_context.update(prev_context)
            
            # Get handler
            handler = self._stage_handlers.get(stage_id)
            if not handler:
                logger.warning("no_handler_for_stage", stage=stage_id)
                stage_exec.status = StageStatus.SKIPPED
                stage_exec.completed_at = datetime.utcnow()
                return state
            
            # Execute handler
            try:
                state = await handler(state)
                stage_exec.status = StageStatus.COMPLETED
                stage_exec.completed_at = datetime.utcnow()
                logger.info("stage_complete", stage=stage_id, run_id=str(state.run_id))
            except Exception as e:
                logger.error("stage_error", stage=stage_id, error=str(e))
                stage_exec.status = StageStatus.FAILED
                stage_exec.error = str(e)
                stage_exec.completed_at = datetime.utcnow()
                state.overall_status = "failed"
                state.error = str(e)
            
            # Save context for next stages
            if stage_exec.output_data:
                await self.context_propagator.save_context(
                    str(state.run_id), stage_id, stage_exec.output_data
                )
            
            # Save checkpoint
            await self.checkpoint_store.save(state)
            
            return state
        
        return stage_node
    
    def _create_gate_node(self, gate_id: str) -> StageHandler:
        """Create a validation gate node."""
        async def gate_node(state: FactoryState) -> FactoryState:
            logger.info("gate_start", gate=gate_id, run_id=str(state.run_id))
            
            handler = self._gate_handlers.get(gate_id)
            if not handler:
                logger.warning("no_handler_for_gate", gate=gate_id)
                # Default pass
                result = GateResult(
                    gate_id=gate_id,
                    name=gate_id,
                    passed=True,
                    details={"reason": "no_handler"}
                )
            else:
                result = await handler(state)
            
            state.add_gate_result(result)
            
            # Store gate result in current stage
            current = state.get_current_stage()
            if current:
                current.metrics[f"gate_{gate_id}"] = {
                    "passed": result.passed,
                    "score": result.score,
                    "details": result.details,
                }
            
            await self.checkpoint_store.save(state)
            
            return state
        
        return gate_node
    
    def _gate_router(self, gate_id: str) -> Callable[[FactoryState], str]:
        """Create a conditional edge router for a gate."""
        def router(state: FactoryState) -> str:
            # Find the gate result
            for result in reversed(state.gate_results):
                if result.gate_id == gate_id:
                    if result.passed:
                        return "pass"
                    # Check if human approval is required
                    current = state.get_current_stage()
                    if current and self._requires_human_approval(state, gate_id):
                        return "human"
                    return "fail"
            return "fail"
        return router
    
    def _requires_human_approval(self, state: FactoryState, gate_id: str) -> bool:
        """Check if human approval is required for this gate/stage."""
        # Check governance config
        tier = settings.governance.get_tier_for_repo(state.work_item.repository)
        
        if gate_id == "human_approval" and tier.human_approval:
            return True
        
        # Check stage config
        for stage_config in settings.stages:
            if stage_config.id == state.current_stage:
                return stage_config.human_gate
        
        return False
    
    async def _checkpoint_node(self, state: FactoryState) -> FactoryState:
        """Handle human checkpoint."""
        logger.info("human_checkpoint", run_id=str(state.run_id))
        
        current = state.get_current_stage()
        if not current:
            return state
        
        # Create checkpoint
        checkpoint = HumanCheckpoint(
            stage_id=current.stage_id,
            title=f"Approval required for {current.stage_id}",
            description=f"Stage {current.stage_id} requires human approval before proceeding.",
            required_approvers=1,
        )
        state.add_checkpoint(checkpoint)
        current.status = StageStatus.WAITING_HUMAN
        state.overall_status = "paused"
        
        # Notify via memory bus
        await self.memory_bus.publish("checkpoints", {
            "run_id": str(state.run_id),
            "checkpoint_id": str(checkpoint.id),
            "stage_id": current.stage_id,
        })
        
        # Save and wait
        await self.checkpoint_store.save(state)
        
        # Wait for approval (in real implementation, this would be async with callback)
        # For now, we'll simulate approval
        await self._wait_for_approval(state, checkpoint)
        
        return state
    
    async def _wait_for_approval(
        self, 
        state: FactoryState, 
        checkpoint: HumanCheckpoint
    ) -> None:
        """Wait for human approval."""
        # Subscribe to checkpoint resolution
        queue = await self.memory_bus.subscribe(f"checkpoint:{checkpoint.id}")
        
        try:
            # Wait for approval message (with timeout)
            msg = await asyncio.wait_for(queue.get(), timeout=3600)  # 1 hour timeout
            
            if msg.get("approved"):
                checkpoint.status = "approved"
                checkpoint.approvers.append(msg.get("approver", "unknown"))
                checkpoint.resolved_at = datetime.utcnow()
                
                current = state.get_current_stage()
                if current:
                    current.status = StageStatus.RUNNING
                state.overall_status = "running"
            else:
                checkpoint.status = "rejected"
                checkpoint.resolved_at = datetime.utcnow()
                state.overall_status = "cancelled"
                state.error = "Human rejected checkpoint"
        except asyncio.TimeoutError:
            checkpoint.status = "rejected"
            checkpoint.resolved_at = datetime.utcnow()
            state.overall_status = "cancelled"
            state.error = "Checkpoint timed out"
        finally:
            await self.memory_bus.unsubscribe(f"checkpoint:{checkpoint.id}", queue)
            await self.checkpoint_store.save(state)
    
    def register_stage_handler(self, stage_id: str, handler: StageHandler) -> None:
        """Register a handler for a stage."""
        self._stage_handlers[stage_id] = handler
        logger.info("registered_stage_handler", stage=stage_id)
    
    def register_gate_handler(self, gate_id: str, handler: GateHandler) -> None:
        """Register a handler for a gate."""
        self._gate_handlers[gate_id] = handler
        logger.info("registered_gate_handler", gate=gate_id)
    
    def register_checkpoint_callback(
        self, 
        callback: Callable[[HumanCheckpoint], Awaitable[bool]]
    ) -> None:
        """Register callback for human checkpoint resolution."""
        self._checkpoint_callbacks.append(callback)
    
    async def run(
        self, 
        work_item: WorkItem,
        initial_context: Optional[Dict[str, Any]] = None,
        resume_from: Optional[str] = None,
    ) -> FactoryState:
        """
        Run the factory for a work item.
        
        Args:
            work_item: The work to process
            initial_context: Optional initial context
            resume_from: Optional run_id to resume from checkpoint
            
        Returns:
            Final factory state
        """
        # Load or create state
        if resume_from:
            state = await self.checkpoint_store.load(resume_from)
            if not state:
                raise ValueError(f"Checkpoint not found: {resume_from}")
        else:
            state = FactoryState(
                run_id=uuid.uuid4(),
                work_item=work_item,
                shared_context=initial_context or {},
            )
        
        logger.info("factory_run_start", run_id=str(state.run_id), work_item=work_item.title)
        
        # Execute graph
        config = {"configurable": {"thread_id": str(state.run_id)}}
        
        try:
            async for chunk in self._app.astream(state, config):
                # Log progress
                for node_name, node_state in chunk.items():
                    if node_name != "__checkpoint__":
                        logger.debug("node_complete", node=node_name, run_id=str(state.run_id))
            
            # Get final state
            final_state = self._app.get_state(config)
            state = final_state.values
            
            state.overall_status = "completed"
            state.completed_at = datetime.utcnow()
            
        except Exception as e:
            logger.error("factory_run_error", run_id=str(state.run_id), error=str(e))
            state.overall_status = "failed"
            state.error = str(e)
            state.completed_at = datetime.utcnow()
        
        # Save final checkpoint
        await self.checkpoint_store.save(state)
        
        logger.info("factory_run_complete", run_id=str(state.run_id), status=state.overall_status)
        
        return state
    
    async def get_state(self, run_id: str) -> Optional[FactoryState]:
        """Get current state of a run."""
        return await self.checkpoint_store.load(run_id)
    
    async def approve_checkpoint(self, checkpoint_id: str, approver: str) -> bool:
        """Approve a human checkpoint."""
        await self.memory_bus.publish(f"checkpoint:{checkpoint_id}", {
            "approved": True,
            "approver": approver,
        })
        return True
    
    async def reject_checkpoint(self, checkpoint_id: str, approver: str) -> bool:
        """Reject a human checkpoint."""
        await self.memory_bus.publish(f"checkpoint:{checkpoint_id}", {
            "approved": False,
            "approver": approver,
        })
        return True
    
    async def list_runs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List recent runs."""
        return await self.checkpoint_store.list_runs(limit, offset)
    
    async def get_run_history(self, run_id: str) -> List[FactoryState]:
        """Get checkpoint history for a run."""
        return await self.checkpoint_store.get_history(run_id)


# Global engine instance
_engine: Optional[FactoryEngine] = None


def get_engine() -> FactoryEngine:
    """Get global engine instance."""
    global _engine
    if _engine is None:
        _engine = FactoryEngine()
    return _engine


async def initialize_engine() -> FactoryEngine:
    """Initialize the factory engine."""
    global _engine
    _engine = FactoryEngine()
    return _engine