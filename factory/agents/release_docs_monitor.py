"""Release, Document, and Monitor Agents."""

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
    """Deploy to target environment (placeholder)."""
    # This would integrate with actual deployment systems
    return json.dumps({
        "environment": environment,
        "version": version,
        "status": "deployed",
        "url": f"https://{environment}.example.com",
    })


@tool
async def run_smoke_tests(
    environment: str,
    version: str,
) -> str:
    """Run smoke tests against deployed environment."""
    # Placeholder
    return json.dumps({
        "passed": True,
        "tests": ["health_check", "api_ping", "db_connection"],
    })


RELEASE_SYSTEM_PROMPT = """You are the Release Agent for a software factory. Your job is to:

1. PREPARE release artifacts from validated changes
2. GENERATE release notes
3. CREATE git tags
4. DEPLOY to environments (staging, production)
5. RUN smoke tests
6. MONITOR deployment health

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
        
        # Determine version (simplified)
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
        
        stage_exec.output_data = deployment
        stage_exec.status = StageStatus.COMPLETED
        stage_exec.completed_at = datetime.utcnow()
        
        logger.info("release_complete", run_id=str(state.run_id), version=version)
        
        return state


# Documentation tools
@tool
async def update_wiki(
    sandbox_id: str,
    pages: List[Dict[str, Any]],
) -> str:
    """Update wiki/documentation."""
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


DOCUMENTER_SYSTEM_PROMPT = """You are the Documentation Agent (AutoWiki) for a software factory. Your job is to:

1. ANALYZE code changes for documentation impact
2. UPDATE relevant documentation (README, API docs, guides)
3. GENERATE API documentation from code
4. UPDATE CHANGELOG
5. ENSURE documentation stays in sync with code

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
            get_sandbox_changes,
            get_full_diff,
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
        
        stage_exec.output_data = doc_result
        stage_exec.status = StageStatus.COMPLETED
        stage_exec.completed_at = datetime.utcnow()
        
        logger.info("documentation_complete", run_id=str(state.run_id), **doc_result)
        
        return state


# Monitor tools
@tool
async def check_incidents(
    repository: str,
    since: str,
) -> str:
    """Check for incidents related to repository."""
    # Placeholder - would integrate with PagerDuty, Datadog, etc.
    return json.dumps({
        "incidents": [],
        "repository": repository,
        "since": since,
    })


@tool
async def analyze_deployment_health(
    environment: str,
    version: str,
) -> str:
    """Analyze health of deployment."""
    # Placeholder
    return json.dumps({
        "healthy": True,
        "metrics": {
            "error_rate": 0.001,
            "latency_p95": 150,
            "throughput": 1000,
        },
    })


@tool
async def correlate_incident_with_changes(
    incident: Dict[str, Any],
    recent_changes: List[Dict[str, Any]],
) -> str:
    """Correlate incident with recent changes."""
    # Placeholder - would use LLM to analyze
    return json.dumps({
        "correlated": False,
        "suspected_changes": [],
        "confidence": 0.0,
    })


@tool
async def create_incident_report(
    incident: Dict[str, Any],
    root_cause: str,
    resolution: str,
    prevention: List[str],
) -> str:
    """Create incident report."""
    report = f"""# Incident Report

**Incident**: {incident.get('title', 'Unknown')}
**Severity**: {incident.get('severity', 'Unknown')}
**Started**: {incident.get('started_at', 'Unknown')}
**Resolved**: {datetime.utcnow().isoformat()}

## Root Cause
{root_cause}

## Resolution
{resolution}

## Prevention
"""
    for item in prevention:
        report += f"- {item}\n"
    
    return report


MONITOR_SYSTEM_PROMPT = """You are the Monitor Agent for a software factory. Your job is to:

1. MONITOR deployed services for incidents
2. CORRELATE incidents with recent changes
3. ANALYZE deployment health
4. CREATE incident reports with root cause
5. TRIGGER auto-remediation where safe
6. FEED learnings back to the factory

Use the Think tool for incident analysis. Consider:
- Is this a regression from a recent deploy?
- What changed in the related code?
- Can we automatically rollback?
- What prevention measures can we add?

Focus on MTTR (Mean Time To Recovery) and learning from each incident."""


class MonitorAgent(BaseAgent):
    """Agent for monitoring and incident response."""
    
    def __init__(self, **kwargs):
        tools = [
            check_incidents,
            analyze_deployment_health,
            correlate_incident_with_changes,
            create_incident_report,
        ]
        
        super().__init__(
            name="monitor-agent",
            agent_type="monitor",
            system_prompt=MONITOR_SYSTEM_PROMPT,
            tools=tools,
            **kwargs
        )
    
    async def execute(self, state: FactoryState) -> FactoryState:
        """Execute monitoring and incident response."""
        logger.info("monitor_start", run_id=str(state.run_id))
        
        stage_exec = state.get_stage("monitor")
        if not stage_exec:
            stage_exec = StageExecution(stage_id="monitor", status=StageStatus.RUNNING)
            state.stages["monitor"] = stage_exec
        
        stage_exec.status = StageStatus.RUNNING
        stage_exec.started_at = datetime.utcnow()
        
        # Get release info
        release_info = state.shared_context.get("release", {})
        environments = release_info.get("environments", {})
        
        task_prompt = f"""Monitor deployments for work item {state.work_item.title}:

Environments: {list(environments.keys())}
Repository: {state.work_item.repository}

Steps:
1. Check for incidents since deployment
2. Analyze deployment health
3. Correlate any incidents with changes
4. Create incident reports if needed
5. Update factory learnings"""
        
        context = {
            "release_info": release_info,
            "work_item": state.work_item.model_dump(),
        }
        
        state = await self.run_react_loop(state, task_prompt, context)
        
        monitor_result = {
            "incidents_found": 0,
            "incidents_correlated": 0,
            "health_checks": {},
            "monitored_at": datetime.utcnow().isoformat(),
        }
        
        for obs in self._execution.observations if self._execution else []:
            if obs["tool"] == "check_incidents":
                result = json.loads(obs["result"])
                monitor_result["incidents_found"] = len(result.get("incidents", []))
            elif obs["tool"] == "analyze_deployment_health":
                result = json.loads(obs["result"])
                env = obs.get("args", {}).get("environment", "unknown")
                monitor_result["health_checks"][env] = result
            elif obs["tool"] == "correlate_incident_with_changes":
                result = json.loads(obs["result"])
                if result.get("correlated"):
                    monitor_result["incidents_correlated"] += 1
        
        stage_exec.output_data = monitor_result
        stage_exec.status = StageStatus.COMPLETED
        stage_exec.completed_at = datetime.utcnow()
        
        logger.info("monitor_complete", run_id=str(state.run_id), **monitor_result)
        
        return state


class DynamicReleaseAgent(ReleaseAgent):
    pass


class DynamicDocumenterAgent(DocumenterAgent):
    pass


class DynamicMonitorAgent(MonitorAgent):
    pass