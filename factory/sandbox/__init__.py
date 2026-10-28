"""Factory sandbox package."""

from factory.config.settings import settings
from factory.sandbox.manager import (
    SandboxManager,
    WorktreeManager,
    ContainerManager,
)
from factory.sandbox.manager_podman import (
    SandboxManager as PodmanSandboxManager,
    WorktreeManager as PodmanWorktreeManager,
    PodmanContainerManager,
)
from factory.sandbox.manager import SandboxExecution, SandboxStatus


def get_sandbox_manager():
    """Get the appropriate sandbox manager based on container_runtime setting."""
    if settings.sandbox.container_runtime == "podman":
        return PodmanSandboxManager()
    return SandboxManager()


# Backward compatibility exports
__all__ = [
    # Main entry point
    "get_sandbox_manager",
    # Docker-based (original)
    "SandboxManager",
    "WorktreeManager",
    "ContainerManager",
    # Podman-based
    "PodmanSandboxManager",
    "PodmanWorktreeManager",
    "PodmanContainerManager",
    # Shared
    "SandboxExecution",
    "SandboxStatus",
]