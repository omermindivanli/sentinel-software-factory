"""Core state schema for the software factory orchestration."""

from typing import Any, Dict, List, Optional, Literal, Annotated
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import operator


class StageStatus(str, Enum):
    """Status of a stage execution."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentStatus(str, Enum):
    """Status of an agent."""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"


class SandboxStatus(str, Enum):
    """Status of a sandbox."""
    CREATING = "creating"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CLEANING_UP = "cleaning_up"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkItem(BaseModel):
    """A unit of work in the factory."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    source: str  # github, linear, slack, manual
    source_id: str  # Issue number, PR ID, etc.
    repository: str
    branch: str = "main"
    priority: TaskPriority = TaskPriority.MEDIUM
    labels: List[str] = Field(default_factory=list)
    assignee: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StageExecution(BaseModel):
    """Execution state for a single stage."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    stage_id: str
    status: StageStatus = StageStatus.PENDING
    agent_id: Optional[str] = None
    sandbox_id: Optional[str] = None
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class SandboxExecution(BaseModel):
    """Sandbox execution state."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: UUID = Field(default_factory=uuid4)
    worktree_path: Optional[str] = None
    container_id: Optional[str] = None
    status: SandboxStatus = SandboxStatus.CREATING
    repository: str
    branch: str
    base_branch: str = "main"
    resources: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list)
    logs: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AgentExecution(BaseModel):
    """Individual agent execution state."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: UUID = Field(default_factory=uuid4)
    agent_type: str
    agent_name: str
    status: AgentStatus = AgentStatus.IDLE
    current_thought: Optional[str] = None
    current_action: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    tokens_used: int = 0
    cost: float = 0.0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class GateResult(BaseModel):
    """Result of a validation gate."""
    
    gate_id: str
    name: str
    passed: bool
    score: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list)
    executed_at: datetime = Field(default_factory=datetime.utcnow)


class HumanCheckpoint(BaseModel):
    """Human approval checkpoint."""
    
    id: UUID = Field(default_factory=uuid4)
    stage_id: str
    title: str
    description: str
    required_approvers: int = 1
    approvers: List[str] = Field(default_factory=list)
    status: Literal["pending", "approved", "rejected"] = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    comments: List[Dict[str, Any]] = Field(default_factory=list)


class FactoryState(BaseModel):
    """Complete factory state for orchestration."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Run identification
    run_id: UUID = Field(default_factory=uuid4)
    work_item: WorkItem
    
    # Stage executions (ordered by SDLC)
    stages: Dict[str, StageExecution] = Field(default_factory=dict)
    current_stage: Optional[str] = None
    stage_order: List[str] = Field(default_factory=lambda: [
        "triage", "planning", "execution", "validation", "release", "document", "monitor"
    ])
    
    # Sandbox management
    sandboxes: Dict[str, SandboxExecution] = Field(default_factory=dict)
    active_sandboxes: List[str] = Field(default_factory=list)
    
    # Agent executions
    agents: Dict[str, AgentExecution] = Field(default_factory=dict)
    
    # Validation gates
    gate_results: List[GateResult] = Field(default_factory=list)
    
    # Human checkpoints
    checkpoints: List[HumanCheckpoint] = Field(default_factory=list)
    
    # Shared memory/context
    shared_context: Dict[str, Any] = Field(default_factory=dict)
    memory_refs: List[str] = Field(default_factory=list)
    
    # Metrics aggregation
    total_tokens: int = 0
    total_cost: float = 0.0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Status
    overall_status: Literal["running", "paused", "completed", "failed", "cancelled"] = "running"
    error: Optional[str] = None
    
    def get_stage(self, stage_id: str) -> Optional[StageExecution]:
        """Get stage execution by ID."""
        return self.stages.get(stage_id)
    
    def get_current_stage(self) -> Optional[StageExecution]:
        """Get current stage execution."""
        if self.current_stage:
            return self.stages.get(self.current_stage)
        return None
    
    def advance_stage(self) -> bool:
        """Advance to next stage. Returns True if there is a next stage."""
        if not self.current_stage:
            self.current_stage = self.stage_order[0] if self.stage_order else None
            return self.current_stage is not None
        
        try:
            idx = self.stage_order.index(self.current_stage)
            if idx + 1 < len(self.stage_order):
                self.current_stage = self.stage_order[idx + 1]
                return True
        except ValueError:
            pass
        return False
    
    def add_agent_execution(self, agent: AgentExecution) -> None:
        """Add agent execution to state."""
        self.agents[str(agent.id)] = agent
    
    def add_gate_result(self, result: GateResult) -> None:
        """Add gate result."""
        self.gate_results.append(result)
    
    def add_checkpoint(self, checkpoint: HumanCheckpoint) -> None:
        """Add human checkpoint."""
        self.checkpoints.append(checkpoint)
    
    def update_metrics(self, tokens: int, cost: float) -> None:
        """Update aggregate metrics."""
        self.total_tokens += tokens
        self.total_cost += cost
        self.updated_at = datetime.utcnow()


# LangGraph state annotation for reducer
def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dicts (right takes precedence)."""
    return {**left, **right}


def merge_lists(left: List[Any], right: List[Any]) -> List[Any]:
    """Concatenate lists."""
    return left + right


# Annotated state for LangGraph reducers
class AnnotatedFactoryState(FactoryState):
    """Factory state with LangGraph reducers."""
    
    shared_context: Annotated[Dict[str, Any], merge_dicts] = Field(default_factory=dict)
    gate_results: Annotated[List[GateResult], merge_lists] = Field(default_factory=list)
    checkpoints: Annotated[List[HumanCheckpoint], merge_lists] = Field(default_factory=list)
    agents: Annotated[Dict[str, AgentExecution], merge_dicts] = Field(default_factory=dict)
    sandboxes: Annotated[Dict[str, SandboxExecution], merge_dicts] = Field(default_factory=dict)