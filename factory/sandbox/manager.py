"""Sandbox management for isolated code execution."""

import asyncio
import shutil
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID, uuid4
import structlog
import docker

from factory.config.settings import settings, SandboxConfig
from factory.orchestration.state import SandboxExecution, SandboxStatus

logger = structlog.get_logger(__name__)


class WorktreeManager:
    """Manages Git worktrees for isolated development."""
    
    def __init__(self, base_path: Path, repo_path: Path):
        self.base_path = base_path
        self.repo_path = repo_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._active_worktrees: Dict[str, Path] = {}
    
    async def create_worktree(
        self, 
        branch_name: str, 
        base_branch: str = "main"
    ) -> Path:
        """Create a new worktree for a branch."""
        worktree_path = self.base_path / branch_name
        
        # Ensure repo is clean and up to date
        await self._run_git(["fetch", "origin"], cwd=self.repo_path)
        
        # Check if branch exists locally or remotely
        result = await self._run_git(
            ["rev-parse", "--verify", f"origin/{branch_name}"], 
            cwd=self.repo_path,
            check=False
        )
        
        if result.returncode == 0:
            # Branch exists on remote, create tracking branch
            await self._run_git(
                ["checkout", "-b", branch_name, f"origin/{branch_name}"],
                cwd=self.repo_path
            )
        else:
            # Create new branch from base
            await self._run_git(
                ["checkout", "-b", branch_name, f"origin/{base_branch}"],
                cwd=self.repo_path
            )
        
        # Create worktree
        await self._run_git(
            ["worktree", "add", str(worktree_path), branch_name],
            cwd=self.repo_path
        )
        
        self._active_worktrees[branch_name] = worktree_path
        logger.info("worktree_created", branch=branch_name, path=str(worktree_path))
        
        return worktree_path
    
    async def remove_worktree(self, branch_name: str, force: bool = False) -> bool:
        """Remove a worktree."""
        worktree_path = self._active_worktrees.get(branch_name)
        
        if worktree_path and worktree_path.exists():
            await self._run_git(
                ["worktree", "remove", str(worktree_path)] + (["--force"] if force else []),
                cwd=self.repo_path
            )
            del self._active_worktrees[branch_name]
            logger.info("worktree_removed", branch=branch_name)
            return True
        
        # Try to remove anyway
        await self._run_git(
            ["worktree", "remove", str(self.base_path / branch_name)] + (["--force"] if force else []),
            cwd=self.repo_path,
            check=False
        )
        return False
    
    async def list_worktrees(self) -> List[Dict[str, Any]]:
        """List all worktrees."""
        result = await self._run_git(["worktree", "list", "--porcelain"], cwd=self.repo_path)
        
        worktrees = []
        current = {}
        for line in result.stdout.strip().split("\n"):
            if line.startswith("worktree "):
                if current:
                    worktrees.append(current)
                current = {"path": line[9:]}
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]
            elif line == "bare":
                current["bare"] = True
            elif line == "detached":
                current["detached"] = True
        
        if current:
            worktrees.append(current)
        
        return worktrees
    
    async def _run_git(
        self, 
        args: List[str], 
        cwd: Path, 
        check: bool = True
    ) -> subprocess.CompletedProcess:
        """Run git command asynchronously."""
        cmd = ["git"] + args
        
        def _run():
            return subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=check
            )
        
        return await asyncio.get_event_loop().run_in_executor(None, _run)


class ContainerManager:
    """Manages Docker containers for isolated execution."""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.client = docker.from_env()
        self._active_containers: Dict[str, docker.models.containers.Container] = {}
    
    async def create_container(
        self,
        name: str,
        image: Optional[str] = None,
        working_dir: str = "/workspace",
        environment: Optional[Dict[str, str]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        cpu_limit: Optional[float] = None,
        memory_limit: Optional[str] = None,
        network: Optional[str] = None,
    ) -> docker.models.containers.Container:
        """Create and start a container."""
        image = image or self.config.container_base_image
        cpu_limit = cpu_limit or self.config.default_cpu_limit
        memory_limit = memory_limit or self.config.default_memory_limit
        
        # Prepare container config
        container_config = {
            "image": image,
            "name": name,
            "working_dir": working_dir,
            "detach": True,
            "stdin_open": True,
            "tty": True,
            "remove": False,  # We'll clean up manually
            "cpus": cpu_limit,
            "mem_limit": memory_limit,
            "environment": environment or {},
        }
        
        if volumes:
            container_config["volumes"] = volumes
        
        if network:
            container_config["network"] = network
        
        # Add docker socket for nested docker if needed
        if self.config.network_enabled:
            container_config["volumes"] = container_config.get("volumes", {})
            container_config["volumes"]["/var/run/docker.sock"] = {
                "bind": "/var/run/docker.sock",
                "mode": "rw"
            }
        
        def _create():
            return self.client.containers.run(**container_config)
        
        container = await asyncio.get_event_loop().run_in_executor(None, _create)
        self._active_containers[name] = container
        
        logger.info("container_created", name=name, image=image)
        return container
    
    async def exec_in_container(
        self,
        name: str,
        command: List[str],
        workdir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> subprocess.CompletedProcess:
        """Execute command in container."""
        container = self._active_containers.get(name)
        
        if not container:
            # Try to get by name
            try:
                container = self.client.containers.get(name)
                self._active_containers[name] = container
            except docker.errors.NotFound:
                raise ValueError(f"Container not found: {name}")
        
        # Reload to get latest state
        def _reload():
            container.reload()
        
        await asyncio.get_event_loop().run_in_executor(None, _reload)
        
        if container.status != "running":
            def _start():
                container.start()
            await asyncio.get_event_loop().run_in_executor(None, _start)
        
        # Execute command
        def _exec():
            exec_result = container.exec_run(
                cmd=command,
                workdir=workdir,
                environment=environment,
                demux=True,
                tty=False,
            )
            return exec_result
        
        try:
            exec_result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, _exec),
                timeout=timeout
            )
            
            stdout = exec_result.output[0].decode() if exec_result.output[0] else ""
            stderr = exec_result.output[1].decode() if exec_result.output[1] else ""
            
            return subprocess.CompletedProcess(
                args=command,
                returncode=exec_result.exit_code,
                stdout=stdout,
                stderr=stderr,
            )
        except asyncio.TimeoutError:
            # Kill the container
            def _kill():
                container.kill()
            await asyncio.get_event_loop().run_in_executor(None, _kill)
            raise TimeoutError(f"Command timed out after {timeout}s")
    
    async def copy_to_container(
        self,
        name: str,
        src_path: Path,
        dest_path: str,
    ) -> None:
        """Copy files to container."""
        container = self._active_containers.get(name)
        if not container:
            container = self.client.containers.get(name)
        
        # Use tar to copy
        import tarfile
        import io
        
        def _copy():
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w') as tar:
                tar.add(src_path, arcname=Path(dest_path).name)
            stream.seek(0)
            container.put_archive(os.path.dirname(dest_path), stream.read())
        
        await asyncio.get_event_loop().run_in_executor(None, _copy)
    
    async def copy_from_container(
        self,
        name: str,
        src_path: str,
        dest_path: Path,
    ) -> None:
        """Copy files from container."""
        container = self._active_containers.get(name)
        if not container:
            container = self.client.containers.get(name)
        
        def _copy():
            bits, stat = container.get_archive(src_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            import tarfile
            import io
            
            stream = io.BytesIO()
            for chunk in bits:
                stream.write(chunk)
            stream.seek(0)
            
            with tarfile.open(fileobj=stream, mode='r') as tar:
                tar.extractall(dest_path.parent)
        
        await asyncio.get_event_loop().run_in_executor(None, _copy)
    
    async def remove_container(self, name: str, force: bool = True) -> bool:
        """Remove container."""
        container = self._active_containers.get(name)
        if not container:
            try:
                container = self.client.containers.get(name)
            except docker.errors.NotFound:
                return False
        
        def _remove():
            container.remove(force=force, v=True)
        
        await asyncio.get_event_loop().run_in_executor(None, _remove)
        
        if name in self._active_containers:
            del self._active_containers[name]
        
        logger.info("container_removed", name=name)
        return True
    
    async def get_container_logs(self, name: str, tail: int = 100) -> str:
        """Get container logs."""
        container = self._active_containers.get(name)
        if not container:
            try:
                container = self.client.containers.get(name)
            except docker.errors.NotFound:
                return ""
        
        def _logs():
            return container.logs(tail=tail).decode()
        
        return await asyncio.get_event_loop().run_in_executor(None, _logs)
    
    async def cleanup_all(self) -> None:
        """Clean up all managed containers."""
        for name in list(self._active_containers.keys()):
            await self.remove_container(name, force=True)


class SandboxManager:
    """High-level sandbox management combining worktrees and containers."""
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or settings.sandbox
        self.container_manager = ContainerManager(self.config)
        self._worktree_managers: Dict[str, WorktreeManager] = {}
        self._sandboxes: Dict[str, SandboxExecution] = {}
    
    def _get_worktree_manager(self, repo_path: Path) -> WorktreeManager:
        """Get or create worktree manager for a repository."""
        repo_key = str(repo_path.resolve())
        if repo_key not in self._worktree_managers:
            worktree_base = self.config.worktree_base / repo_path.name
            self._worktree_managers[repo_key] = WorktreeManager(worktree_base, repo_path)
        return self._worktree_managers[repo_key]
    
    async def create_sandbox(
        self,
        sandbox_id: str,
        repository: str,
        repo_path: Path,
        branch: str,
        base_branch: str = "main",
        resources: Optional[Dict[str, Any]] = None,
    ) -> SandboxExecution:
        """Create a new sandbox with worktree and container."""
        sandbox = SandboxExecution(
            id=uuid4(),
            repository=repository,
            branch=branch,
            base_branch=base_branch,
            resources=resources or {},
            status=SandboxStatus.CREATING,
        )
        
        self._sandboxes[sandbox_id] = sandbox
        
        try:
            # Create worktree
            wt_manager = self._get_worktree_manager(repo_path)
            worktree_path = await wt_manager.create_worktree(branch, base_branch)
            sandbox.worktree_path = str(worktree_path)
            
            # Create container
            container_name = f"factory-{sandbox_id[:8]}"
            volumes = {
                str(worktree_path): {
                    "bind": "/workspace",
                    "mode": "rw"
                }
            }
            
            container = await self.container_manager.create_container(
                name=container_name,
                working_dir="/workspace",
                volumes=volumes,
                cpu_limit=resources.get("cpu_limit") if resources else None,
                memory_limit=resources.get("memory_limit") if resources else None,
            )
            sandbox.container_id = container.id
            
            sandbox.status = SandboxStatus.READY
            sandbox.started_at = datetime.utcnow()
            
            logger.info("sandbox_created", sandbox_id=sandbox_id, worktree=str(worktree_path))
            
        except Exception as e:
            logger.error("sandbox_create_failed", sandbox_id=sandbox_id, error=str(e))
            sandbox.status = SandboxStatus.FAILED
            raise
        
        return sandbox
    
    async def execute_in_sandbox(
        self,
        sandbox_id: str,
        command: List[str],
        workdir: str = "/workspace",
        environment: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> subprocess.CompletedProcess:
        """Execute command in sandbox container."""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox or not sandbox.container_id:
            raise ValueError(f"Sandbox not found: {sandbox_id}")
        
        sandbox.status = SandboxStatus.RUNNING
        
        container_name = f"factory-{sandbox_id[:8]}"
        result = await self.container_manager.exec_in_container(
            container_name,
            command,
            workdir=workdir,
            environment=environment,
            timeout=timeout,
        )
        
        return result
    
    async def run_in_worktree(
        self,
        sandbox_id: str,
        command: List[str],
        workdir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> subprocess.CompletedProcess:
        """Run command directly in worktree (no container)."""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox or not sandbox.worktree_path:
            raise ValueError(f"Sandbox not found: {sandbox_id}")
        
        workdir = workdir or sandbox.worktree_path
        
        def _run():
            return subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                env={**os.environ, **(environment or {})},
                timeout=timeout,
            )
        
        return await asyncio.get_event_loop().run_in_executor(None, _run)
    
    async def get_sandbox_logs(self, sandbox_id: str, tail: int = 100) -> str:
        """Get sandbox container logs."""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox or not sandbox.container_id:
            return ""
        
        container_name = f"factory-{sandbox_id[:8]}"
        return await self.container_manager.get_container_logs(container_name, tail)
    
    async def copy_to_sandbox(
        self,
        sandbox_id: str,
        src_path: Path,
        dest_path: str,
    ) -> None:
        """Copy files to sandbox."""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox or not sandbox.container_id:
            raise ValueError(f"Sandbox not found: {sandbox_id}")
        
        container_name = f"factory-{sandbox_id[:8]}"
        await self.container_manager.copy_to_container(container_name, src_path, dest_path)
    
    async def copy_from_sandbox(
        self,
        sandbox_id: str,
        src_path: str,
        dest_path: Path,
    ) -> None:
        """Copy files from sandbox."""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox or not sandbox.container_id:
            raise ValueError(f"Sandbox not found: {sandbox_id}")
        
        container_name = f"factory-{sandbox_id[:8]}"
        await self.container_manager.copy_from_container(container_name, src_path, dest_path)
    
    async def commit_changes(
        self,
        sandbox_id: str,
        message: str,
        author: Optional[str] = None,
    ) -> bool:
        """Commit changes in sandbox worktree."""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox or not sandbox.worktree_path:
            raise ValueError(f"Sandbox not found: {sandbox_id}")
        
        worktree_path = Path(sandbox.worktree_path)
        
        def _commit():
            # Stage all changes
            subprocess.run(["git", "add", "-A"], cwd=worktree_path, check=True)
            
            # Commit
            cmd = ["git", "commit", "-m", message]
            if author:
                cmd.extend(["--author", author])
            result = subprocess.run(cmd, cwd=worktree_path, capture_output=True, text=True)
            
            return result.returncode == 0
        
        return await asyncio.get_event_loop().run_in_executor(None, _commit)
    
    async def push_branch(
        self,
        sandbox_id: str,
        remote: str = "origin",
        force: bool = False,
    ) -> bool:
        """Push sandbox branch to remote."""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox or not sandbox.worktree_path:
            raise ValueError(f"Sandbox not found: {sandbox_id}")
        
        worktree_path = Path(sandbox.worktree_path)
        
        def _push():
            cmd = ["git", "push", remote, sandbox.branch]
            if force:
                cmd.append("--force-with-lease")
            result = subprocess.run(cmd, cwd=worktree_path, capture_output=True, text=True)
            return result.returncode == 0
        
        return await asyncio.get_event_loop().run_in_executor(None, _push)
    
    async def create_pr(
        self,
        sandbox_id: str,
        title: str,
        body: str,
        base_branch: str = "main",
        draft: bool = False,
    ) -> Dict[str, Any]:
        """Create a pull request (requires gh CLI)."""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox or not sandbox.worktree_path:
            raise ValueError(f"Sandbox not found: {sandbox_id}")
        
        worktree_path = Path(sandbox.worktree_path)
        
        def _create_pr():
            cmd = [
                "gh", "pr", "create",
                "--title", title,
                "--body", body,
                "--base", base_branch,
                "--head", sandbox.branch,
            ]
            if draft:
                cmd.append("--draft")
            
            result = subprocess.run(cmd, cwd=worktree_path, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Parse PR URL from output
                import re
                match = re.search(r'(https://github.com/[^\s]+/pull/\d+)', result.stdout)
                return {"success": True, "url": match.group(1) if match else result.stdout.strip()}
            else:
                return {"success": False, "error": result.stderr}
        
        return await asyncio.get_event_loop().run_in_executor(None, _create_pr)
    
    async def cleanup_sandbox(self, sandbox_id: str) -> bool:
        """Clean up sandbox resources."""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            return False
        
        sandbox.status = SandboxStatus.CLEANING_UP
        
        # Remove container
        if sandbox.container_id:
            container_name = f"factory-{sandbox_id[:8]}"
            await self.container_manager.remove_container(container_name)
        
        # Remove worktree
        if sandbox.worktree_path:
            repo_path = Path(sandbox.worktree_path).parent.parent  # Go up to repo root
            wt_manager = self._get_worktree_manager(repo_path)
            await wt_manager.remove_worktree(sandbox.branch, force=True)
        
        sandbox.status = SandboxStatus.COMPLETED
        sandbox.completed_at = datetime.utcnow()
        
        del self._sandboxes[sandbox_id]
        
        logger.info("sandbox_cleaned_up", sandbox_id=sandbox_id)
        return True
    
    async def cleanup_all(self) -> None:
        """Clean up all sandboxes."""
        for sandbox_id in list(self._sandboxes.keys()):
            await self.cleanup_sandbox(sandbox_id)
        
        await self.container_manager.cleanup_all()
    
    def get_sandbox(self, sandbox_id: str) -> Optional[SandboxExecution]:
        """Get sandbox by ID."""
        return self._sandboxes.get(sandbox_id)
    
    def list_sandboxes(self) -> List[SandboxExecution]:
        """List all active sandboxes."""
        return list(self._sandboxes.values())


# Global sandbox manager
_sandbox_manager: Optional[SandboxManager] = None


def get_sandbox_manager() -> SandboxManager:
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
    return _sandbox_manager