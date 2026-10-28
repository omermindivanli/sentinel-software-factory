"""Factory agents package."""

from factory.agents.base import BaseAgent, ThinkTool, AgentFactory, get_agent_factory
from factory.agents.triage import TriageAgent, DynamicTriageAgent
from factory.agents.architect import ArchitectAgent, DynamicArchitectAgent
from factory.agents.worker import WorkerAgent, WorkerPoolAgent, DynamicWorkerAgent, DynamicWorkerPoolAgent
from factory.agents.validation import (
    CodeReviewAgent, QAAgent, SecurityAgent,
    DynamicCodeReviewAgent, DynamicQAAgent, DynamicSecurityAgent
)
from factory.agents.release import ReleaseAgent, DynamicReleaseAgent
from factory.agents.document import DocumenterAgent, DynamicDocumenterAgent
from factory.agents.monitor import MonitorAgent, DynamicMonitorAgent

__all__ = [
    # Base
    "BaseAgent",
    "ThinkTool",
    "AgentFactory",
    "get_agent_factory",
    # Triage
    "TriageAgent",
    "DynamicTriageAgent",
    # Planning
    "ArchitectAgent",
    "DynamicArchitectAgent",
    # Execution
    "WorkerAgent",
    "WorkerPoolAgent",
    "DynamicWorkerAgent",
    "DynamicWorkerPoolAgent",
    # Validation
    "CodeReviewAgent",
    "QAAgent",
    "SecurityAgent",
    "DynamicCodeReviewAgent",
    "DynamicQAAgent",
    "DynamicSecurityAgent",
    # Release/Docs/Monitor
    "ReleaseAgent",
    "DocumenterAgent",
    "MonitorAgent",
    "DynamicReleaseAgent",
    "DynamicDocumenterAgent",
    "DynamicMonitorAgent",
]

# Agent registry for dynamic creation
AGENT_REGISTRY = {
    "triage": DynamicTriageAgent,
    "architect": DynamicArchitectAgent,
    "worker_pool": DynamicWorkerPoolAgent,
    "reviewer": DynamicCodeReviewAgent,
    "qa": DynamicQAAgent,
    "security": DynamicSecurityAgent,
    "release": DynamicReleaseAgent,
    "documenter": DynamicDocumenterAgent,
    "monitor": DynamicMonitorAgent,
}


def create_agent(agent_type: str, **kwargs) -> BaseAgent:
    """Create an agent by type."""
    agent_class = AGENT_REGISTRY.get(agent_type)
    if not agent_class:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return agent_class(**kwargs)


def get_registered_agents() -> Dict[str, type]:
    """Get all registered agent types."""
    return AGENT_REGISTRY.copy()