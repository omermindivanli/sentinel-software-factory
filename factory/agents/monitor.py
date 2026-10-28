"""Monitor Agent - Handles incident response, telemetry, and agent effectiveness."""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from langchain_core.tools import tool

from factory.agents.base import BaseAgent
from factory.orchestration.state import FactoryState, StageExecution, StageStatus

logger = structlog.get_logger(__name__)


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


@tool
async def trigger_auto_remediation(
    incident_id: str,
    action: str,
    params: Dict[str, Any],
) -> str:
    """Trigger automated remediation for an incident."""
    # Placeholder - would execute remediation
    return json.dumps({
        "incident_id": incident_id,
        "action": action,
        "status": "triggered",
        "params": params,
    })


@tool
async def record_agent_effectiveness(
    agent_type: str,
    task_type: str,
    success: bool,
    duration_ms: float,
    tokens_used: int,
    cost: float,
) -> str:
    """Record agent effectiveness metrics for continuous improvement."""
    return json.dumps({
        "recorded": True,
        "agent_type": agent_type,
        "task_type": task_type,
        "success": success,
        "duration_ms": duration_ms,
        "tokens_used": tokens_used,
        "cost": cost,
    })


MONITOR_SYSTEM_PROMPT = """You are the Monitor Agent for a software factory. Your job is to:

1. MONITOR deployed services for incidents
2. CORRELATE incidents with recent changes
3. ANALYZE deployment health
4. CREATE incident reports with root cause
5. TRIGGER auto-remediation where safe
6. RECORD agent effectiveness for continuous improvement
7. FEED learnings back to the factory

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
            trigger_auto_remediation,
            record_agent_effectiveness,
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
5. Record agent effectiveness metrics"""
        
        context = {
            "release_info": release_info,
            "work_item": state.work_item.model_dump(),
        }
        
        state = await self.run_react_loop(state, task_prompt, context)
        
        monitor_result = {
            "incidents_found": 0,
            "incidents_correlated": 0,
            "health_checks": {},
            "remediations_triggered": 0,
            "effectiveness_records": 0,
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
            elif obs["tool"] == "trigger_auto_remediation":
                monitor_result["remediations_triggered"] += 1
            elif obs["tool"] == "record_agent_effectiveness":
                monitor_result["effectiveness_records"] += 1
        
        stage_exec.output_data = monitor_result
        stage_exec.status = StageStatus.COMPLETED
        stage_exec.completed_at = datetime.utcnow()
        
        logger.info("monitor_complete", run_id=str(state.run_id), **monitor_result)
        
        return state


class DynamicMonitorAgent(MonitorAgent):
    pass