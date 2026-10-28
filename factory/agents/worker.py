"""Worker Agent Pool - Executes implementation tasks in parallel."""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4
import structlog

from langchain_core.tools import tool

from factory.agents.base import BaseAgent
from factory.orchestration.state import FactoryState, StageExecution, StageStatus, AgentExecution, AgentStatus
from factory.sandbox.manager import get_sandbox_manager, SandboxManager

logger = structlog.get_logger(__name__)


# Tool definitions for workers
@tool
async def read_file(
    sandbox_id: str,
    file_path: str,
) -> str:
    """Read a file from the sandbox."""
    sandbox_mgr = get_sandbox_manager()
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["cat", file_path],
    )
    if result.returncode == 0:
        return result.stdout
    else:
        return f"Error: {result.stderr}"


@tool
async def write_file(
    sandbox_id: str,
    file_path: str,
    content: str,
) -> str:
    """Write a file to the sandbox."""
    sandbox_mgr = get_sandbox_manager()
    # Create directory if needed
    import os
    dir_path = os.path.dirname(file_path)
    if dir_path:
        await sandbox_mgr.run_in_worktree(sandbox_id, ["mkdir", "-p", dir_path])
    
    # Write file using tee
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["tee", file_path],
        environment={"CONTENT": content},
    )
    if result.returncode == 0:
        return f"File written: {file_path}"
    else:
        return f"Error: {result.stderr}"


@tool
async def edit_file(
    sandbox_id: str,
    file_path: str,
    old_string: str,
    new_string: str,
) -> str:
    """Edit a file in the sandbox (patch)."""
    sandbox_mgr = get_sandbox_manager()
    # Read current content
    read_result = await sandbox_mgr.run_in_worktree(sandbox_id, ["cat", file_path])
    if read_result.returncode != 0:
        return f"Error reading file: {read_result.stderr}"
    
    content = read_result.stdout
    if old_string not in content:
        return f"Error: old_string not found in file"
    
    new_content = content.replace(old_string, new_string, 1)
    write_result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["tee", file_path],
        environment={"CONTENT": new_content},
    )
    if write_result.returncode == 0:
        return f"File edited: {file_path}"
    else:
        return f"Error: {write_result.stderr}"


@tool
async def list_files(
    sandbox_id: str,
    directory: str = ".",
    pattern: str = "**/*",
) -> str:
    """List files in sandbox."""
    sandbox_mgr = get_sandbox_manager()
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["find", directory, "-type", "f", "-name", pattern.replace("**/", "")],
    )
    if result.returncode == 0:
        return result.stdout
    else:
        return f"Error: {result.stderr}"


@tool
async def run_command(
    sandbox_id: str,
    command: List[str],
    workdir: str = "/workspace",
    timeout: int = 120,
) -> str:
    """Run a command in the sandbox."""
    sandbox_mgr = get_sandbox_manager()
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        command,
        workdir=workdir,
        timeout=timeout,
    )
    return json.dumps({
        "returncode": result.returncode,
        "stdout": result.stdout[-5000:],  # Truncate
        "stderr": result.stderr[-5000:],
    })


@tool
async def run_tests(
    sandbox_id: str,
    test_command: str = "pytest",
    test_path: str = ".",
    timeout: int = 300,
) -> str:
    """Run tests in the sandbox."""
    sandbox_mgr = get_sandbox_manager()
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        test_command.split() + [test_path],
        timeout=timeout,
    )
    return json.dumps({
        "returncode": result.returncode,
        "stdout": result.stdout[-10000:],
        "stderr": result.stderr[-10000:],
    })


@tool
async def search_code(
    sandbox_id: str,
    query: str,
    file_pattern: str = "*.py",
) -> str:
    """Search code in sandbox using grep."""
    sandbox_mgr = get_sandbox_manager()
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["grep", "-r", "-n", query, "--include", file_pattern, "."],
    )
    if result.returncode in [0, 1]:  # 1 = no matches
        return result.stdout
    else:
        return f"Error: {result.stderr}"


@tool
async def get_git_diff(
    sandbox_id: str,
) -> str:
    """Get git diff of changes in sandbox."""
    sandbox_mgr = get_sandbox_manager()
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["git", "diff"],
    )
    return result.stdout


@tool
async def commit_changes(
    sandbox_id: str,
    message: str,
) -> str:
    """Commit changes in sandbox."""
    sandbox_mgr = get_sandbox_manager()
    success = await sandbox_mgr.commit_changes(sandbox_id, message)
    return json.dumps({"success": success})


WORKER_SYSTEM_PROMPT = """You are a Worker Agent in a software factory. Your job is to:

1. IMPLEMENT assigned tasks in an isolated sandbox
2. WRITE clean, tested, production-ready code
3. FOLLOW the technical specification exactly
4. RUN tests and verify your implementation
5. COMMIT changes with clear messages

You have access to a full development environment with:
- File operations (read, write, edit, list)
- Command execution (build, test, lint, type-check)
- Git operations (diff, commit, push)
- Code search and navigation

Guidelines:
- Write one thing at a time, test it, then move on
- Follow existing code patterns and conventions
- Use the Think tool for complex implementation decisions
- Run tests frequently to catch issues early
- Keep changes focused and minimal
- Document any deviations from the spec

If you encounter blockers, use Think tool to analyze, then report clearly."""


class WorkerAgent(BaseAgent):
    """Individual worker agent for executing tasks."""
    
    def __init__(self, task: Dict[str, Any], sandbox_id: str, **kwargs):
        self.task = task
        self.sandbox_id = sandbox_id
        
        tools = [
            read_file,
            write_file,
            edit_file,
            list_files,
            run_command,
            run_tests,
            search_code,
            get_git_diff,
            commit_changes,
        ]
        
        # Customize system prompt with task info
        task_prompt = f"""{WORKER_SYSTEM_PROMPT}

Your assigned task:
- ID: {task.get('id')}
- Title: {task.get('title')}
- Description: {task.get('description')}
- Type: {task.get('type')}
- Dependencies: {task.get('dependencies', [])}
- Estimated hours: {task.get('estimated_hours', 4)}
- Skills required: {task.get('skills_required', [])}

Sandbox ID: {sandbox_id}"""
        
        super().__init__(
            name=f"worker-{task.get('id', 'unknown')}",
            agent_type="worker",
            system_prompt=task_prompt,
            tools=tools,
            **kwargs
        )
    
    async def execute(self, state: FactoryState) -> FactoryState:
        """Execute the assigned task."""
        logger.info("worker_start", task_id=self.task.get('id'), sandbox=self.sandbox_id)
        
        task_prompt = f"""Implement the following task:

Task: {self.task.get('title')}
Description: {self.task.get('description')}
Type: {self.task.get('type')}

Requirements:
1. Read relevant existing code to understand patterns
2. Implement the changes
3. Write tests for your implementation
4. Run tests to verify
5. Run linting/type-checking
6. Commit changes with descriptive message

Use the Think tool for design decisions during implementation.
If you're unsure about something, think through it before acting."""
        
        context = {
            "task": self.task,
            "sandbox_id": self.sandbox_id,
            "spec": state.shared_context.get("planning", {}).get("spec", {}),
        }
        
        state = await self.run_react_loop(state, task_prompt, context)
        
        # Collect outputs
        outputs = {
            "task_id": self.task.get('id'),
            "files_changed": [],
            "tests_run": False,
            "tests_passed": False,
            "lint_passed": False,
            "commit_message": "",
        }
        
        for obs in self._execution.observations if self._execution else []:
            if obs["tool"] in ["write_file", "edit_file"]:
                outputs["files_changed"].append(obs.get("args", {}).get("file_path", "unknown"))
            elif obs["tool"] == "run_tests":
                result = json.loads(obs["result"])
                outputs["tests_run"] = True
                outputs["tests_passed"] = result.get("returncode") == 0
            elif obs["tool"] == "run_command":
                # Check for lint/type-check
                cmd = obs.get("args", {}).get("command", [])
                if any(c in str(cmd) for c in ["lint", "mypy", "ruff", "black", "eslint", "prettier"]):
                    result = json.loads(obs["result"])
                    outputs["lint_passed"] = result.get("returncode") == 0
            elif obs["tool"] == "commit_changes":
                outputs["commit_message"] = self.task.get('title', 'Implementation')
        
        # Store in shared context for aggregation
        key = f"worker_output:{self.task.get('id')}"
        state.shared_context[key] = outputs
        
        logger.info("worker_complete", 
                   task_id=self.task.get('id'),
                   files_changed=len(outputs["files_changed"]),
                   tests_passed=outputs["tests_passed"])
        
        return state


class WorkerPoolAgent(BaseAgent):
    """Manages a pool of worker agents for parallel execution."""
    
    def __init__(self, sandbox_manager: Optional[SandboxManager] = None, **kwargs):
        self.sandbox_manager = sandbox_manager or get_sandbox_manager()
        self.max_parallelism = 5
        
        tools = []  # Pool agent doesn't need tools directly
        
        super().__init__(
            name="worker-pool",
            agent_type="worker_pool",
            system_prompt="You coordinate a pool of worker agents for parallel task execution.",
            tools=tools,
            **kwargs
        )
    
    async def execute(self, state: FactoryState) -> FactoryState:
        """Execute all tasks in parallel using worker agents."""
        logger.info("worker_pool_start", run_id=str(state.run_id))
        
        stage_exec = state.get_stage("execution")
        if not stage_exec:
            stage_exec = StageExecution(stage_id="execution", status=StageStatus.RUNNING)
            state.stages["execution"] = stage_exec
        
        stage_exec.status = StageStatus.RUNNING
        stage_exec.started_at = datetime.utcnow()
        
        # Get tasks from planning
        tasks = state.shared_context.get("tasks", [])
        if not tasks:
            # Fallback: create a generic implementation task
            tasks = [{
                "id": "impl_1",
                "title": "Implement feature",
                "description": state.work_item.description,
                "type": "implementation",
                "dependencies": [],
                "estimated_hours": 8,
                "skills_required": ["fullstack"],
                "parallelizable": False,
            }]
        
        # Filter to implementation tasks for this stage
        impl_tasks = [t for t in tasks if t.get("type") in ["implementation", "refactor"]]
        
        # Get repository path
        repo_path = state.shared_context.get("repo_path")
        if not repo_path:
            # Try to find repo
            import os
            repo_path = os.getcwd()
        
        # Create sandboxes for each task
        sandboxes = []
        for task in impl_tasks[:self.max_parallelism]:
            sandbox_id = f"exec-{state.run_id}-{task['id']}"
            sandbox = await self.sandbox_manager.create_sandbox(
                sandbox_id=sandbox_id,
                repository=state.work_item.repository,
                repo_path=Path(repo_path),
                branch=f"factory/{state.work_item.id}/{task['id']}",
                base_branch=state.work_item.branch,
            )
            sandboxes.append((task, sandbox))
            stage_exec.output_data.setdefault("sandboxes", []).append({
                "task_id": task["id"],
                "sandbox_id": sandbox_id,
                "worktree": sandbox.worktree_path,
            })
        
        # Execute workers in parallel
        worker_tasks = []
        for task, sandbox in sandboxes:
            worker = WorkerAgent(task=task, sandbox_id=sandbox.id)
            worker_tasks.append(worker.execute(state))
        
        # Wait for all workers
        results = await asyncio.gather(*worker_tasks, return_exceptions=True)
        
        # Aggregate results
        aggregated = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_files_changed": 0,
            "all_tests_passed": True,
            "all_lint_passed": True,
            "sandboxes": [],
        }
        
        for i, (task, sandbox) in enumerate(sandboxes):
            key = f"worker_output:{task['id']}"
            output = state.shared_context.get(key, {})
            
            aggregated["sandboxes"].append({
                "task_id": task["id"],
                "sandbox_id": sandbox.id,
                "output": output,
            })
            
            if isinstance(results[i], Exception):
                aggregated["tasks_failed"] += 1
                logger.error("worker_failed", task_id=task['id'], error=str(results[i]))
            else:
                aggregated["tasks_completed"] += 1
                aggregated["total_files_changed"] += len(output.get("files_changed", []))
                if not output.get("tests_passed", False):
                    aggregated["all_tests_passed"] = False
                if not output.get("lint_passed", False):
                    aggregated["all_lint_passed"] = False
        
        stage_exec.output_data = aggregated
        stage_exec.metrics = {
            "tasks_completed": aggregated["tasks_completed"],
            "tasks_failed": aggregated["tasks_failed"],
            "files_changed": aggregated["total_files_changed"],
        }
        
        if aggregated["tasks_failed"] > 0:
            stage_exec.status = StageStatus.FAILED
        else:
            stage_exec.status = StageStatus.COMPLETED
        
        stage_exec.completed_at = datetime.utcnow()
        
        logger.info("worker_pool_complete", 
                   run_id=str(state.run_id),
                   **aggregated)
        
        return state


class DynamicWorkerAgent(WorkerAgent):
    pass


class DynamicWorkerPoolAgent(WorkerPoolAgent):
    pass