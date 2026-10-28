"""Triage Agent - Classifies and routes inbound work."""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from factory.agents.base import BaseAgent, ThinkTool
from factory.orchestration.state import FactoryState, WorkItem, StageExecution, StageStatus

logger = structlog.get_logger(__name__)


# Tool definitions
@tool
async def classify_work_item(
    title: str,
    description: str,
    source: str,
    labels: List[str] = [],
) -> str:
    """Classify a work item into category and priority."""
    # This would use an LLM in practice, simplified here
    categories = {
        "bug": ["bug", "error", "crash", "fail", "broken", "issue"],
        "feature": ["feature", "enhancement", "add", "implement", "new"],
        "refactor": ["refactor", "cleanup", "improve", "optimize", "tech debt"],
        "docs": ["doc", "documentation", "readme", "comment", "guide"],
        "security": ["security", "vulnerability", "exploit", "cve", "audit"],
        "performance": ["performance", "slow", "latency", "optimize", "speed"],
        "test": ["test", "testing", "coverage", "unit test", "integration"],
        "infra": ["infra", "devops", "deploy", "ci", "cd", "kubernetes", "docker"],
    }
    
    text = f"{title} {description}".lower()
    scores = {}
    for cat, keywords in categories.items():
        scores[cat] = sum(1 for kw in keywords if kw in text)
    
    category = max(scores, key=scores.get) if scores else "other"
    
    # Priority based on keywords
    priority_keywords = {
        "critical": ["critical", "urgent", "production down", "data loss", "security breach"],
        "high": ["high", "important", "blocker", "regression"],
        "low": ["low", "minor", "cosmetic", "nice to have"],
    }
    
    priority = "medium"
    for p, kws in priority_keywords.items():
        if any(kw in text for kw in kws):
            priority = p
            break
    
    return json.dumps({
        "category": category,
        "priority": priority,
        "confidence": max(scores.values()) / len(text.split()) if text else 0.5,
    })


@tool
async def check_duplicates(
    title: str,
    description: str,
    repository: str,
    existing_items: List[Dict[str, Any]],
) -> str:
    """Check for duplicate work items."""
    # Simple similarity check
    duplicates = []
    text = f"{title} {description}".lower()
    
    for item in existing_items:
        item_text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        # Simple word overlap
        words = set(text.split())
        item_words = set(item_text.split())
        if words and item_words:
            overlap = len(words & item_words) / len(words | item_words)
            if overlap > 0.7:
                duplicates.append({
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "similarity": overlap,
                })
    
    return json.dumps({"duplicates": duplicates})


@tool
async def route_work_item(
    category: str,
    priority: str,
    repository: str,
) -> str:
    """Determine routing for work item."""
    # Routing rules based on category and priority
    routing = {
        "next_stage": "planning",
        "assignee": None,
        "labels": [],
        "sla_hours": 24,
    }
    
    if category == "security" and priority in ["critical", "high"]:
        routing["next_stage"] = "planning"
        routing["sla_hours"] = 4
        routing["labels"].append("security-urgent")
    elif category == "bug" and priority == "critical":
        routing["sla_hours"] = 2
        routing["labels"].append("hotfix")
    elif category == "docs":
        routing["next_stage"] = "execution"  # Skip planning for docs
        routing["sla_hours"] = 48
    elif category == "infra":
        routing["sla_hours"] = 12
    
    return json.dumps(routing)


TRIAGE_SYSTEM_PROMPT = """You are the Triage Agent for a software factory. Your job is to:

1. CLASSIFY incoming work items (bugs, features, refactors, docs, security, performance, tests, infra)
2. PRIORITIZE them (critical, high, medium, low)
3. DEDUPLICATE against existing work
4. ROUTE to the appropriate next stage

Use the Think tool to reason through ambiguous cases. Consider:
- Business impact vs technical complexity
- Security implications
- Dependencies on other work
- Team capacity and expertise

Be thorough but efficient. Every work item must be classified, prioritized, and routed."""


class TriageAgent(BaseAgent):
    """Agent for triaging inbound work items."""
    
    def __init__(self, **kwargs):
        tools = [
            classify_work_item,
            check_duplicates,
            route_work_item,
        ]
        
        super().__init__(
            name="triage-agent",
            agent_type="triage",
            system_prompt=TRIAGE_SYSTEM_PROMPT,
            tools=tools,
            **kwargs
        )
    
    async def execute(self, state: FactoryState) -> FactoryState:
        """Execute triage on the work item."""
        logger.info("triage_start", run_id=str(state.run_id))
        
        work_item = state.work_item
        stage_exec = state.get_stage("triage")
        
        if not stage_exec:
            stage_exec = StageExecution(stage_id="triage", status=StageStatus.RUNNING)
            state.stages["triage"] = stage_exec
        
        stage_exec.status = StageStatus.RUNNING
        stage_exec.started_at = datetime.utcnow()
        
        # Prepare context for triage
        context = {
            "title": work_item.title,
            "description": work_item.description,
            "source": work_item.source,
            "source_id": work_item.source_id,
            "repository": work_item.repository,
            "labels": work_item.labels,
            "existing_items": state.shared_context.get("existing_work_items", []),
        }
        
        # Run ReAct loop for triage
        task_prompt = f"""Triage the following work item:

Title: {work_item.title}
Description: {work_item.description}
Source: {work_item.source} ({work_item.source_id})
Repository: {work_item.repository}
Labels: {work_item.labels}

Steps:
1. Classify the work item (category, priority)
2. Check for duplicates
3. Determine routing
4. Output structured result

Use Think tool for reasoning on ambiguous cases."""
        
        state = await self.run_react_loop(state, task_prompt, context)
        
        # Parse results from tool calls
        classification = {}
        duplicates = []
        routing = {}
        
        for obs in self._execution.observations if self._execution else []:
            if obs["tool"] == "classify_work_item":
                classification = json.loads(obs["result"])
            elif obs["tool"] == "check_duplicates":
                duplicates = json.loads(obs["result"]).get("duplicates", [])
            elif obs["tool"] == "route_work_item":
                routing = json.loads(obs["result"])
        
        # Store output
        stage_exec.output_data = {
            "classification": classification,
            "duplicates": duplicates,
            "routing": routing,
            "triaged_at": datetime.utcnow().isoformat(),
        }
        
        # Update work item
        work_item.labels.extend([
            classification.get("category", "unknown"),
            f"priority:{classification.get('priority', 'medium')}",
        ])
        work_item.priority = classification.get("priority", "medium")
        
        # Add routing info to shared context
        state.shared_context["triage"] = stage_exec.output_data
        
        stage_exec.status = StageStatus.COMPLETED
        stage_exec.completed_at = datetime.utcnow()
        
        logger.info("triage_complete", 
                   run_id=str(state.run_id),
                   category=classification.get("category"),
                   priority=classification.get("priority"))
        
        return state


# Dynamic agent for factory registration
class DynamicTriageAgent(TriageAgent):
    """Dynamically created triage agent."""
    pass