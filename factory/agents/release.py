"""Release Agent - Handles deployment, canary gates, and rollback."""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from langchain_core.tools import tool

from factory.agents.base import BaseAgent
from factory.orchestration.state import FactoryState, StageExecution, StageStatus, GateResult
from factory.sandbox.manager import get_sandbox_manager

logger = structlog.get_logger(__name__)


# Release tools
@tool
async def create_release_notes(
    changes_summary: str,
    work_items: List[Dict[str, Any]],
    version: str,
) -> str:
    """Generate release notes."""
    notes = f"""# Release {version}

## Changes
{changes_summary}

## Work Items
"""
    for item in work_items:
        notes += f"- {item.get('title', 'Unknown')} ({item.get('id', 'N/A')})\n"
    
    return notes


@tool
async def tag_release(
    sandbox_id: str,
    version: str,
    message: str,
) -> str:
    """Create a git tag for release."""
    sandbox_mgr = get_sandbox_manager()
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["git", "tag", "-a", version, "-m", message],
    )
    if result.returncode == 0:
        # Push tag
        push_result = await sandbox_mgr.run_in_worktree(
            sandbox_id,
            ["git", "push", "origin", version],
        )
        return json.dumps({"success": push_result.returncode == 0})
    return json.dumps({"success": False, "error": result.stderr})


@tool
async def deploy_to_environment(
    environment: str,
    version: str,
    config: Dict[str, Any],
) -> str:
    """Deploy to target environment."""
    # This would integrate with actual deployment systems
    # For now, simulate deployment
    return json.dumps({
        "environment": environment,
        "version": version,
        "status": "deployed",
        "url": f"https://{environment}.example.com",
        "deployed_at": datetime.utcnow().isoformat(),
    })


@tool
async def run_smoke_tests(
    environment: str,
    version: str,
) -> str:
    """Run smoke tests against deployed environment."""
    # Placeholder - would run actual smoke tests
    return json.dumps({
        "passed": True,
        "tests": ["health_check", "api_ping", "db_connection"],
        "duration_ms": 1500,
    })


@tool
async def rollback_deployment(
    environment: str,
    previous_version: str,
) -> str:
    """Rollback to previous version."""
    return json.dumps({
        "environment": environment,
        "rolled_back_to": previous_version,
        "status": "rollback_complete",
        "rolled_back_at": datetime.utcnow().isoformat(),
    })


RELEASE_SYSTEM_PROMPT = """You are the Release Agent for a software factory. Your job is to:

1. PREPARE release artifacts from validated changes
2. GENERATE release notes
3. CREATE git tags
4. DEPLOY to environments (staging, production)
5. RUN smoke tests
6. MONITOR deployment health
7. ROLLBACK if issues detected

Use the Think tool for deployment decisions. Consider:
- Deployment strategy (blue/green, canary, rolling)
- Rollback plan
- Health checks
- Traffic shifting
- Database migrations

Be careful and deliberate. Production deployments require human approval for high-risk repos."""


class ReleaseAgent(BaseAgent):
    """Agent for release management."""
    
    def __init__(self, **kwargs):
        tools = [
            create_release_notes,
            tag_release,
            deploy_to_environment,
            run_smoke_tests,
            rollback_deployment,
        ]
        
        super().__init__(
            name="release-agent",
            agent_type="release",
            system_prompt=RELEASE_SYSTEM_PROMPT,
            tools=tools,
            **kwargs
        )
    
    async def execute(self, state: FactoryState) -> FactoryState:
        """Execute release process."""
        logger.info("release_start", run_id=str(state.run_id))
        
        stage_exec = state.get_stage("release")
        if not stage_exec:
            stage_exec = StageExecution(stage_id="release", status=StageStatus.RUNNING)
            state.stages["release"] = stage_exec
        
        stage_exec.status = StageStatus.RUNNING
        stage_exec.started_at = datetime.utcnow()
        
        # Get work item and validation results
        work_item = state.work_item
        validation_results = []
        
        for gate in state.gate_results:
            if gate.gate_id in ["code_review", "tests", "security"]:
                validation_results.append({
                    "gate": gate.gate_id,
                    "passed": gate.passed,
                    "score": gate.score,
                })
        
        # Determine version
        version = f"v{datetime.utcnow().strftime('%Y%m%d')}-{str(work_item.id)[:8]}"
        
        task_prompt = f"""Prepare release for work item {work_item.title}:

Validation Results: {json.dumps(validation_results)}
Version: {version}
Repository: {work_item.repository}

Steps:
1. Generate release notes
2. Create git tag
3. Deploy to staging
4. Run smoke tests
5. If staging passes, deploy to production (with approval for high-risk)

Use Think tool for deployment strategy decisions."""
        
        context = {
            "version": version,
            "validation_results": validation_results,
            "work_item": work_item.model_dump(),
        }
        
        state = await self.run_react_loop(state, task_prompt, context)
        
        # Parse results
        deployment = {"status": "pending", "environments": {}}
        
        for obs in self._execution.observations if self._execution else []:
            if obs["tool"] == "create_release_notes":
                deployment["release_notes"] = obs["result"]
            elif obs["tool"] == "tag_release":
                deployment["tagged"] = json.loads(obs["result"]).get("success", False)
            elif obs["tool"] == "deploy_to_environment":
                result = json.loads(obs["result"])
                deployment["environments"][result["environment"]] = result
            elif obs["tool"] == "run_smoke_tests":
                result = json.loads(obs["result"])
                deployment["smoke_tests"] = result
            elif obs["tool"] == "rollback_deployment":
                deployment["rollback"] = json.loads(obs["result"])
        
        stage_exec.output_data = deployment
        stage_exec.status = StageStatus.COMPLETED
        stage_exec.completed_at = datetime.utcnow()
        
        logger.info("release_complete", run_id=str(state.run_id), version=version)
        
        return state


class DynamicReleaseAgent(ReleaseAgent):
    pass