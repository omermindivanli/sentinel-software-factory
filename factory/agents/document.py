"""Documentation Agent (AutoWiki) - Handles automatic documentation updates."""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from langchain_core.tools import tool

from factory.agents.base import BaseAgent
from factory.orchestration.state import FactoryState, StageExecution, StageStatus
from factory.sandbox.manager import get_sandbox_manager

logger = structlog.get_logger(__name__)


# Documentation tools
@tool
async def update_wiki(
    sandbox_id: str,
    pages: List[Dict[str, Any]],
) -> str:
    """Update wiki/documentation pages."""
    sandbox_mgr = get_sandbox_manager()
    
    results = []
    for page in pages:
        path = page.get("path", "docs/README.md")
        content = page.get("content", "")
        
        # Ensure directory exists
        import os
        dir_path = os.path.dirname(path)
        if dir_path:
            await sandbox_mgr.run_in_worktree(sandbox_id, ["mkdir", "-p", dir_path])
        
        # Write file
        result = await sandbox_mgr.run_in_worktree(
            sandbox_id,
            ["tee", path],
            environment={"CONTENT": content},
        )
        results.append({"path": path, "success": result.returncode == 0})
    
    return json.dumps({"results": results})


@tool
async def generate_api_docs(
    sandbox_id: str,
    output_path: str = "docs/api.md",
) -> str:
    """Generate API documentation from code."""
    sandbox_mgr = get_sandbox_manager()
    
    # Try to detect and generate docs
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["bash", "-c", "if [ -f pyproject.toml ] && command -v pdoc &> /dev/null; then pdoc -o docs/api .; elif [ -f package.json ] && command -v typedoc &> /dev/null; then typedoc --out docs/api; else echo 'No doc generator found'; fi"],
        timeout=120,
    )
    
    return json.dumps({
        "success": result.returncode == 0,
        "output": result.stdout[-2000:],
    })


@tool
async def update_changelog(
    sandbox_id: str,
    version: str,
    changes: List[str],
) -> str:
    """Update CHANGELOG.md."""
    sandbox_mgr = get_sandbox_manager()
    
    # Read existing changelog
    read_result = await sandbox_mgr.run_in_worktree(sandbox_id, ["cat", "CHANGELOG.md"])
    existing = read_result.stdout if read_result.returncode == 0 else "# Changelog\n\n"
    
    # Prepend new version
    date = datetime.utcnow().strftime("%Y-%m-%d")
    new_entry = f"\n## [{version}] - {date}\n\n"
    for change in changes:
        new_entry += f"- {change}\n"
    
    new_content = existing.replace("# Changelog\n\n", f"# Changelog\n\n{new_entry}\n")
    
    write_result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["tee", "CHANGELOG.md"],
        environment={"CONTENT": new_content},
    )
    
    return json.dumps({"success": write_result.returncode == 0})


@tool
async def generate_adr(
    sandbox_id: str,
    title: str,
    context: str,
    decision: str,
    consequences: str,
) -> str:
    """Generate Architecture Decision Record (ADR)."""
    sandbox_mgr = get_sandbox_manager()
    
    # Ensure ADR directory exists
    await sandbox_mgr.run_in_worktree(sandbox_id, ["mkdir", "-p", "docs/adr"])
    
    # Generate ADR number
    import os
    list_result = await sandbox_mgr.run_in_worktree(sandbox_id, ["ls", "docs/adr"])
    adr_count = len(list_result.stdout.strip().split("\n")) if list_result.stdout.strip() else 0
    adr_num = adr_count + 1
    
    adr_content = f"""# {adr_num:04d}. {title}

**Status**: Accepted
**Date**: {datetime.utcnow().strftime('%Y-%m-%d')}

## Context
{context}

## Decision
{decision}

## Consequences
{consequences}
"""
    
    path = f"docs/adr/{adr_num:04d}-{title.lower().replace(' ', '-')}.md"
    
    write_result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["tee", path],
        environment={"CONTENT": adr_content},
    )
    
    return json.dumps({"success": write_result.returncode == 0, "path": path})


DOCUMENTER_SYSTEM_PROMPT = """You are the Documentation Agent (AutoWiki) for a software factory. Your job is to:

1. ANALYZE code changes for documentation impact
2. UPDATE relevant documentation (README, API docs, guides)
3. GENERATE API documentation from code
4. UPDATE CHANGELOG
5. CREATE Architecture Decision Records (ADRs)
6. ENSURE documentation stays in sync with code

Use the Think tool to determine what documentation needs updating. Consider:
- New public APIs need documentation
- Behavior changes need changelog entries
- Architecture decisions need ADRs
- Complex logic needs inline comments
- Setup/installation guides may need updates

Keep documentation accurate, concise, and discoverable."""


class DocumenterAgent(BaseAgent):
    """Agent for automatic documentation (AutoWiki)."""
    
    def __init__(self, **kwargs):
        tools = [
            update_wiki,
            generate_api_docs,
            update_changelog,
            generate_adr,
        ]
        
        super().__init__(
            name="documenter-agent",
            agent_type="documenter",
            system_prompt=DOCUMENTER_SYSTEM_PROMPT,
            tools=tools,
            **kwargs
        )
    
    async def execute(self, state: FactoryState) -> FactoryState:
        """Execute documentation updates."""
        logger.info("documentation_start", run_id=str(state.run_id))
        
        stage_exec = state.get_stage("document")
        if not stage_exec:
            stage_exec = StageExecution(stage_id="document", status=StageStatus.RUNNING)
            state.stages["document"] = stage_exec
        
        stage_exec.status = StageStatus.RUNNING
        stage_exec.started_at = datetime.utcnow()
        
        exec_stage = state.get_stage("execution")
        sandboxes = exec_stage.output_data.get("sandboxes", []) if exec_stage else []
        
        task_prompt = f"""Update documentation for {len(sandboxes)} sandboxes:

1. Analyze changes in each sandbox
2. Update relevant documentation
3. Generate API docs
4. Update CHANGELOG
5. Create ADRs for architecture decisions

Repository: {state.work_item.repository}"""
        
        context = {
            "sandboxes": sandboxes,
            "work_item": state.work_item.model_dump(),
            "release_info": state.shared_context.get("release", {}),
        }
        
        state = await self.run_react_loop(state, task_prompt, context)
        
        doc_result = {
            "pages_updated": 0,
            "api_docs_generated": False,
            "changelog_updated": False,
            "adrs_created": 0,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        for obs in self._execution.observations if self._execution else []:
            if obs["tool"] == "update_wiki":
                result = json.loads(obs["result"])
                doc_result["pages_updated"] = sum(1 for r in result.get("results", []) if r.get("success"))
            elif obs["tool"] == "generate_api_docs":
                result = json.loads(obs["result"])
                doc_result["api_docs_generated"] = result.get("success", False)
            elif obs["tool"] == "update_changelog":
                result = json.loads(obs["result"])
                doc_result["changelog_updated"] = result.get("success", False)
            elif obs["tool"] == "generate_adr":
                result = json.loads(obs["result"])
                if result.get("success"):
                    doc_result["adrs_created"] += 1
        
        stage_exec.output_data = doc_result
        stage_exec.status = StageStatus.COMPLETED
        stage_exec.completed_at = datetime.utcnow()
        
        logger.info("documentation_complete", run_id=str(state.run_id), **doc_result)
        
        return state


class DynamicDocumenterAgent(DocumenterAgent):
    pass