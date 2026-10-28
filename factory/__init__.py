"""
Software Factory - Local-first SDLC automation with multi-agent orchestration.

A production-grade software factory that automates the full software development
lifecycle using coordinated multi-agent AI loops.
"""

__version__ = "0.1.0"
__author__ = "Software Factory Team"

from factory.config.settings import settings
from factory.orchestration.engine import get_engine, initialize_engine
from factory.memory.tiered import get_tiered_memory, initialize_tiered_memory
from factory.tools.mcp_client import get_mcp_client, initialize_mcp_client
from factory.agents import create_agent, get_agent_factory

__all__ = [
    "settings",
    "get_engine",
    "initialize_engine",
    "get_tiered_memory",
    "initialize_tiered_memory",
    "get_mcp_client",
    "initialize_mcp_client",
    "create_agent",
    "get_agent_factory",
]


async def initialize_factory() -> None:
    """Initialize all factory subsystems."""
    await initialize_tiered_memory()
    await initialize_mcp_client()
    await initialize_engine()
    
    # Register stage handlers
    engine = get_engine()
    engine.register_stage_handler("triage", create_agent("triage").execute)
    engine.register_stage_handler("planning", create_agent("architect").execute)
    engine.register_stage_handler("execution", create_agent("worker_pool").execute)
    engine.register_stage_handler("validation", create_agent("reviewer").execute)
    engine.register_stage_handler("release", create_agent("release").execute)
    engine.register_stage_handler("document", create_agent("documenter").execute)
    engine.register_stage_handler("monitor", create_agent("monitor").execute)


def create_factory_run(
    title: str,
    description: str,
    repository: str,
    branch: str = "main",
    priority: str = "medium",
) -> str:
    """Create a new factory run (sync wrapper)."""
    import asyncio
    from factory.orchestration.state import WorkItem, TaskPriority
    from factory.orchestration.engine import get_engine
    
    engine = get_engine()
    work_item = WorkItem(
        title=title,
        description=description,
        source="api",
        source_id=f"api-{title[:20]}",
        repository=repository,
        branch=branch,
        priority=TaskPriority(priority.lower()),
    )
    
    return asyncio.run(engine.run(work_item))