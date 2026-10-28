"""Base agent class with Think tool and standard patterns."""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime
from uuid import UUID, uuid4
import structlog

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import BaseTool, tool

from factory.config.settings import settings, ModelConfig
from factory.orchestration.state import (
    FactoryState, 
    AgentExecution, 
    AgentStatus,
    WorkItem,
)
from factory.orchestration.router import get_router, ModelRouter
from factory.orchestration.memory_bus import get_memory_bus, get_context_propagator
from factory.orchestration.engine import get_engine

logger = structlog.get_logger(__name__)


class ThinkTool:
    """Think tool for structured reasoning during agent execution."""
    
    name = "think"
    description = "Use this tool to stop and think about the current situation. It does not perform any action but allows you to reason through complex decisions, verify assumptions, check policies, or plan next steps."
    
    def __init__(self):
        self.thoughts: List[Dict[str, Any]] = []
    
    async def invoke(self, thought: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Record a thought and return confirmation."""
        entry = {
            "thought": thought,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.thoughts.append(entry)
        return f"Thought recorded: {thought[:100]}..."
    
    def get_thoughts(self) -> List[Dict[str, Any]]:
        return self.thoughts
    
    def clear(self) -> None:
        self.thoughts = []


class BaseAgent(ABC):
    """
    Base agent class implementing the ReAct loop with Think tool.
    
    Patterns from Agentic Design Patterns:
    - Prompt Chaining (sequential decomposition)
    - Reflection (self-critique)
    - Tool Use (structured tool calling)
    - Planning (goal decomposition)
    - Human-in-the-Loop (checkpoints)
    """
    
    def __init__(
        self,
        name: str,
        agent_type: str,
        system_prompt: str,
        tools: Optional[List[BaseTool]] = None,
        model_config: Optional[ModelConfig] = None,
        router: Optional[ModelRouter] = None,
        max_iterations: int = 20,
        think_tool_enabled: bool = True,
    ):
        self.name = name
        self.agent_type = agent_type
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model_config = model_config
        self.router = router or get_router()
        self.max_iterations = max_iterations
        self.think_tool_enabled = think_tool_enabled
        
        # Think tool
        self.think_tool = ThinkTool() if think_tool_enabled else None
        if self.think_tool:
            self.tools.append(self._create_think_tool())
        
        # LLM client (initialized lazily)
        self._llm: Optional[ChatAnthropic] = None
        
        # Execution tracking
        self._execution: Optional[AgentExecution] = None
    
    def _create_think_tool(self) -> BaseTool:
        """Create the think tool for LangChain."""
        @tool
        async def think(thought: str) -> str:
            """Use this tool to think through complex reasoning, verify assumptions, 
            check policies, or plan next steps. This tool does not perform any action
            but provides a dedicated space for structured thinking."""
            return await self.think_tool.invoke(thought)
        
        return think
    
    def _get_llm(self, model: Optional[ModelConfig] = None) -> ChatAnthropic:
        """Get or create LLM client."""
        model = model or self.model_config
        if not model:
            # Use router to get default model for this agent type
            capability_map = {
                "triage": "classification",
                "planning": "planning",
                "architect": "architecture",
                "worker": "code_generation",
                "reviewer": "code_review",
                "qa": "test_generation",
                "security": "code_review",
                "release": "planning",
                "documenter": "documentation",
                "monitor": "simple_tasks",
            }
            capability = capability_map.get(self.agent_type, "code_generation")
            model = self.router.get_model(capability)
        
        if self._llm is None or self._llm.model_name != model.id:
            self._llm = ChatAnthropic(
                model=model.id,
                max_tokens=model.max_tokens,
                temperature=model.temperature,
                api_key=model.get_api_key(),
            )
            # Bind tools
            if self.tools:
                self._llm = self._llm.bind_tools(self.tools)
        
        return model
    
    @abstractmethod
    async def execute(self, state: FactoryState) -> FactoryState:
        """Execute the agent's main logic. Must be implemented by subclasses."""
        pass
    
    async def run_react_loop(
        self,
        state: FactoryState,
        task_prompt: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> FactoryState:
        """
        Run the ReAct (Reason + Act) loop with Think tool.
        
        This implements the core agent loop from Agentic Design Patterns:
        1. Gather context
        2. Think (reason about next action)
        3. Act (call tools)
        4. Check results
        5. Repeat until condition met
        """
        # Initialize execution tracking
        self._execution = AgentExecution(
            id=uuid4(),
            agent_type=self.agent_type,
            agent_name=self.name,
            status=AgentStatus.THINKING,
        )
        state.add_agent_execution(self._execution)
        
        # Build messages
        messages = [SystemMessage(content=self.system_prompt)]
        
        # Add context
        context = {
            "work_item": state.work_item.model_dump(),
            "shared_context": state.shared_context,
            "current_stage": state.current_stage,
            "stage_outputs": {
                sid: se.output_data for sid, se in state.stages.items()
            },
        }
        if additional_context:
            context.update(additional_context)
        
        messages.append(HumanMessage(content=f"Task: {task_prompt}\n\nContext: {json.dumps(context, default=str)}"))
        
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            
            # Get LLM with current model
            model = self._get_llm()
            
            try:
                # Invoke LLM
                self._execution.status = AgentStatus.THINKING
                response = await model.ainvoke(messages)
                
                # Track tokens
                if hasattr(response, 'usage_metadata'):
                    tokens = response.usage_metadata.get('total_tokens', 0)
                    self._execution.tokens_used += tokens
                
                messages.append(response)
                
                # Check for tool calls
                tool_calls = getattr(response, 'tool_calls', [])
                
                if not tool_calls:
                    # No tool calls, agent is done
                    self._execution.status = AgentStatus.COMPLETED
                    self._execution.completed_at = datetime.utcnow()
                    break
                
                # Execute tool calls
                for tool_call in tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    tool_call_id = tool_call['id']
                    
                    self._execution.status = AgentStatus.ACTING
                    self._execution.current_action = tool_name
                    self._execution.tool_calls.append({
                        "name": tool_name,
                        "args": tool_args,
                        "id": tool_call_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    
                    # Find and execute tool
                    tool = next((t for t in self.tools if t.name == tool_name), None)
                    if tool:
                        try:
                            result = await tool.ainvoke(tool_args)
                            self._execution.observations.append({
                                "tool": tool_name,
                                "result": str(result)[:5000],  # Truncate
                                "timestamp": datetime.utcnow().isoformat(),
                            })
                            
                            # Add tool result to messages
                            messages.append(ToolMessage(
                                content=str(result),
                                tool_call_id=tool_call_id,
                            ))
                        except Exception as e:
                            logger.error("tool_error", tool=tool_name, error=str(e))
                            messages.append(ToolMessage(
                                content=f"Error: {str(e)}",
                                tool_call_id=tool_call_id,
                            ))
                    else:
                        logger.warning("tool_not_found", tool=tool_name)
                        messages.append(ToolMessage(
                            content=f"Error: Tool '{tool_name}' not found",
                            tool_call_id=tool_call_id,
                        ))
                
                # Update cost estimate
                model_config = self._get_llm()
                if model_config and hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    input_tokens = usage.get('input_tokens', 0)
                    output_tokens = usage.get('output_tokens', 0)
                    cost = (input_tokens / 1000 * model_config.cost_per_1k_input + 
                           output_tokens / 1000 * model_config.cost_per_1k_output)
                    self._execution.cost += cost
                    state.update_metrics(input_tokens + output_tokens, cost)
                
            except Exception as e:
                logger.error("agent_iteration_error", agent=self.name, error=str(e))
                self._execution.status = AgentStatus.ERROR
                self._execution.error = str(e)
                break
        
        if iteration >= self.max_iterations:
            logger.warning("max_iterations_reached", agent=self.name, iterations=iteration)
            self._execution.status = AgentStatus.ERROR
            self._execution.error = "Max iterations reached"
        
        return state
    
    async def reflect(
        self, 
        state: FactoryState, 
        reflection_prompt: str
    ) -> Dict[str, Any]:
        """Perform reflection/self-critique (Reflection pattern)."""
        model = self._get_llm()
        
        messages = [
            SystemMessage(content="You are performing self-reflection on your previous work. Be critical and specific."),
            HumanMessage(content=reflection_prompt),
        ]
        
        response = await model.ainvoke(messages)
        
        return {
            "reflection": response.content,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def plan(
        self, 
        state: FactoryState, 
        goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Generate a plan for achieving a goal (Planning pattern)."""
        model = self._get_llm()
        
        planning_prompt = f"""Create a detailed plan to achieve the following goal:

Goal: {goal}

Context: {json.dumps(context or {}, default=str)}

Current stage outputs: {json.dumps({sid: se.output_data for sid, se in state.stages.items()}, default=str)}

Provide a step-by-step plan with:
1. Clear steps with descriptions
2. Dependencies between steps
3. Expected outputs for each step
4. Potential risks and mitigations

Format as JSON array of steps."""
        
        messages = [
            SystemMessage(content="You are an expert planner. Create detailed, actionable plans."),
            HumanMessage(content=planning_prompt),
        ]
        
        response = await model.ainvoke(messages)
        
        try:
            plan = json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback: parse as text
            plan = [{"step": i, "description": line} 
                   for i, line in enumerate(response.content.split('\n')) if line.strip()]
        
        return plan


class AgentFactory:
    """Factory for creating agents with proper configuration."""
    
    def __init__(self, router: Optional[ModelRouter] = None):
        self.router = router or get_router()
        self._agents: Dict[str, BaseAgent] = {}
    
    def create_agent(
        self,
        agent_type: str,
        name: str,
        system_prompt: str,
        tools: Optional[List[BaseTool]] = None,
        **kwargs
    ) -> BaseAgent:
        """Create an agent of the specified type."""
        # Get model config for this agent type
        capability_map = {
            "triage": "classification",
            "planning": "planning",
            "architect": "architecture",
            "worker": "code_generation",
            "reviewer": "code_review",
            "qa": "test_generation",
            "security": "code_review",
            "release": "planning",
            "documenter": "documentation",
            "monitor": "simple_tasks",
        }
        capability = capability_map.get(agent_type, "code_generation")
        model_config = self.router.get_model(capability)
        
        # Create appropriate agent class
        agent_class = self._get_agent_class(agent_type)
        agent = agent_class(
            name=name,
            agent_type=agent_type,
            system_prompt=system_prompt,
            tools=tools,
            model_config=model_config,
            router=self.router,
            **kwargs
        )
        
        self._agents[name] = agent
        return agent
    
    def _get_agent_class(self, agent_type: str) -> type:
        """Get agent class for type."""
        # This will be overridden by specific agent modules
        from factory.agents.base import DynamicAgent
        return DynamicAgent
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)


# Global agent factory
_agent_factory: Optional[AgentFactory] = None


def get_agent_factory() -> AgentFactory:
    global _agent_factory
    if _agent_factory is None:
        _agent_factory = AgentFactory()
    return _agent_factory