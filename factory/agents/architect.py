"""Architect/Planning Agent - Creates technical specifications and task breakdowns."""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from langchain_core.tools import tool

from factory.agents.base import BaseAgent
from factory.orchestration.state import FactoryState, StageExecution, StageStatus

logger = structlog.get_logger(__name__)


# Tool definitions
@tool
async def analyze_requirements(
    work_item_title: str,
    work_item_description: str,
    triage_classification: Dict[str, Any],
    repository_context: Dict[str, Any],
) -> str:
    """Analyze requirements and extract key technical considerations."""
    # This would use LLM reasoning in practice
    analysis = {
        "functional_requirements": [],
        "non_functional_requirements": [],
        "technical_constraints": [],
        "dependencies": [],
        "risks": [],
        "assumptions": [],
    }
    
    # Simple extraction based on keywords
    text = f"{work_item_title} {work_item_description}".lower()
    
    if "api" in text or "endpoint" in text:
        analysis["functional_requirements"].append("REST API endpoint implementation")
    if "database" in text or "db" in text or "model" in text:
        analysis["functional_requirements"].append("Database schema changes")
    if "ui" in text or "frontend" in text or "component" in text:
        analysis["functional_requirements"].append("Frontend component development")
    if "test" in text:
        analysis["functional_requirements"].append("Test coverage")
    if "doc" in text:
        analysis["functional_requirements"].append("Documentation updates")
    
    # Non-functional
    if "performance" in text or "fast" in text or "latency" in text:
        analysis["non_functional_requirements"].append("Response time < 200ms")
    if "security" in text or "auth" in text:
        analysis["non_functional_requirements"].append("Authentication/authorization")
    if "scale" in text or "concurrent" in text:
        analysis["non_functional_requirements"].append("Horizontal scalability")
    
    return json.dumps(analysis)


@tool
async def create_technical_spec(
    analysis: Dict[str, Any],
    architecture_context: Dict[str, Any],
) -> str:
    """Create detailed technical specification."""
    spec = {
        "overview": "",
        "architecture": {
            "components": [],
            "interfaces": [],
            "data_flow": [],
        },
        "implementation_plan": {
            "steps": [],
            "estimated_effort": "medium",
            "parallelizable": [],
        },
        "testing_strategy": {
            "unit_tests": [],
            "integration_tests": [],
            "e2e_tests": [],
        },
        "deployment": {
            "migrations": [],
            "config_changes": [],
            "rollback_plan": "",
        },
        "monitoring": {
            "metrics": [],
            "alerts": [],
        },
    }
    
    # Populate from analysis
    spec["overview"] = f"Implementation of {analysis.get('functional_requirements', ['feature'])[0]}"
    
    # Add components based on requirements
    for req in analysis.get("functional_requirements", []):
        if "API" in req or "api" in req:
            spec["architecture"]["components"].append({
                "name": "API Layer",
                "type": "service",
                "responsibility": "Handle HTTP requests",
            })
        if "Database" in req or "database" in req:
            spec["architecture"]["components"].append({
                "name": "Data Layer",
                "type": "repository",
                "responsibility": "Data persistence",
            })
        if "Frontend" in req or "frontend" in req:
            spec["architecture"]["components"].append({
                "name": "UI Components",
                "type": "component",
                "responsibility": "User interface",
            })
    
    # Create implementation steps
    steps = []
    for i, req in enumerate(analysis.get("functional_requirements", []), 1):
        steps.append({
            "id": f"step_{i}",
            "description": req,
            "dependencies": [],
            "estimated_hours": 4,
        })
    
    spec["implementation_plan"]["steps"] = steps
    spec["implementation_plan"]["parallelizable"] = [
        s["id"] for s in steps if "test" not in s["description"].lower()
    ]
    
    return json.dumps(spec, indent=2)


@tool
async def break_down_tasks(
    spec: Dict[str, Any],
    team_capacity: Dict[str, Any],
) -> str:
    """Break down spec into executable tasks for workers."""
    tasks = []
    
    for step in spec.get("implementation_plan", {}).get("steps", []):
        task = {
            "id": step["id"],
            "title": step["description"],
            "description": f"Implement: {step['description']}",
            "type": "implementation",
            "dependencies": step.get("dependencies", []),
            "estimated_hours": step.get("estimated_hours", 4),
            "skills_required": ["backend"],  # Would be inferred
            "parallelizable": step["id"] in spec.get("implementation_plan", {}).get("parallelizable", []),
        }
        tasks.append(task)
    
    # Add testing tasks
    for test_type in ["unit_tests", "integration_tests", "e2e_tests"]:
        for test in spec.get("testing_strategy", {}).get(test_type, []):
            tasks.append({
                "id": f"test_{len(tasks)}",
                "title": f"{test_type}: {test}",
                "description": f"Write {test_type} for {test}",
                "type": "test",
                "dependencies": [t["id"] for t in tasks if t["type"] == "implementation"],
                "estimated_hours": 2,
                "skills_required": ["testing"],
                "parallelizable": True,
            })
    
    # Add documentation task
    tasks.append({
        "id": f"doc_{len(tasks)}",
        "title": "Update documentation",
        "description": "Update relevant documentation for changes",
        "type": "documentation",
        "dependencies": [t["id"] for t in tasks if t["type"] == "implementation"],
        "estimated_hours": 1,
        "skills_required": ["documentation"],
        "parallelizable": True,
    })
    
    return json.dumps({"tasks": tasks}, indent=2)


@tool
async def estimate_effort(
    tasks: List[Dict[str, Any]],
    velocity: Dict[str, float],
) -> str:
    """Estimate total effort and timeline."""
    total_hours = sum(t.get("estimated_hours", 0) for t in tasks)
    
    # Group by skill
    by_skill = {}
    for task in tasks:
        for skill in task.get("skills_required", ["general"]):
            by_skill.setdefault(skill, 0)
            by_skill[skill] += task.get("estimated_hours", 0)
    
    # Calculate timeline with parallelization
    parallel_tasks = [t for t in tasks if t.get("parallelizable", False)]
    sequential_tasks = [t for t in tasks if not t.get("parallelizable", False)]
    
    parallel_hours = sum(t.get("estimated_hours", 0) for t in parallel_tasks)
    sequential_hours = sum(t.get("estimated_hours", 0) for t in sequential_tasks)
    
    # Assume 2 parallel workers
    effective_parallel = parallel_hours / 2
    total_timeline_hours = sequential_hours + effective_parallel
    total_days = total_timeline_hours / 6  # 6 productive hours/day
    
    return json.dumps({
        "total_hours": total_hours,
        "by_skill": by_skill,
        "parallel_hours": parallel_hours,
        "sequential_hours": sequential_hours,
        "estimated_days": round(total_days, 1),
        "estimated_weeks": round(total_days / 5, 1),
    }, indent=2)


ARCHITECT_SYSTEM_PROMPT = """You are the Architect Agent for a software factory. Your job is to:

1. ANALYZE requirements from triage output
2. CREATE a detailed technical specification
3. BREAK DOWN the spec into executable tasks for worker agents
4. ESTIMATE effort and timeline

Use the Think tool for complex architectural decisions. Consider:
- Existing architecture and patterns in the codebase
- Scalability, maintainability, security
- Team capacity and skill distribution
- Technical debt and migration paths
- Testing strategy (unit, integration, e2e)
- Deployment and rollback considerations
- Monitoring and observability

Output must be detailed enough for worker agents to execute independently.
Include clear interfaces, data flows, and acceptance criteria for each task."""


class ArchitectAgent(BaseAgent):
    """Agent for planning and architectural design."""
    
    def __init__(self, **kwargs):
        tools = [
            analyze_requirements,
            create_technical_spec,
            break_down_tasks,
            estimate_effort,
        ]
        
        super().__init__(
            name="architect-agent",
            agent_type="architect",
            system_prompt=ARCHITECT_SYSTEM_PROMPT,
            tools=tools,
            **kwargs
        )
    
    async def execute(self, state: FactoryState) -> FactoryState:
        """Execute planning phase."""
        logger.info("planning_start", run_id=str(state.run_id))
        
        stage_exec = state.get_stage("planning")
        if not stage_exec:
            stage_exec = StageExecution(stage_id="planning", status=StageStatus.RUNNING)
            state.stages["planning"] = stage_exec
        
        stage_exec.status = StageStatus.RUNNING
        stage_exec.started_at = datetime.utcnow()
        
        # Get triage output
        triage_data = state.shared_context.get("triage", {})
        
        context = {
            "work_item": state.work_item.model_dump(),
            "triage": triage_data,
            "repository_context": state.shared_context.get("repository_context", {}),
            "architecture_context": state.shared_context.get("architecture_context", {}),
            "team_capacity": state.shared_context.get("team_capacity", {}),
        }
        
        task_prompt = f"""Create a technical specification and implementation plan for:

Work Item: {state.work_item.title}
Description: {state.work_item.description}
Classification: {triage_data.get('classification', {})}
Repository: {state.work_item.repository}

Steps:
1. Analyze requirements
2. Create technical specification
3. Break down into tasks
4. Estimate effort

Use Think tool for architectural decisions. Consider existing patterns, scalability, security, and team capacity."""
        
        state = await self.run_react_loop(state, task_prompt, context)
        
        # Parse results
        analysis = {}
        spec = {}
        tasks = {}
        estimate = {}
        
        for obs in self._execution.observations if self._execution else []:
            if obs["tool"] == "analyze_requirements":
                analysis = json.loads(obs["result"])
            elif obs["tool"] == "create_technical_spec":
                spec = json.loads(obs["result"])
            elif obs["tool"] == "break_down_tasks":
                tasks = json.loads(obs["result"])
            elif obs["tool"] == "estimate_effort":
                estimate = json.loads(obs["result"])
        
        # Store output
        stage_exec.output_data = {
            "analysis": analysis,
            "spec": spec,
            "tasks": tasks.get("tasks", []),
            "estimate": estimate,
            "planned_at": datetime.utcnow().isoformat(),
        }
        
        # Add to shared context
        state.shared_context["planning"] = stage_exec.output_data
        state.shared_context["tasks"] = tasks.get("tasks", [])
        
        stage_exec.status = StageStatus.COMPLETED
        stage_exec.completed_at = datetime.utcnow()
        
        logger.info("planning_complete", 
                   run_id=str(state.run_id),
                   task_count=len(tasks.get("tasks", [])),
                   estimated_days=estimate.get("estimated_days"))
        
        return state


class DynamicArchitectAgent(ArchitectAgent):
    pass