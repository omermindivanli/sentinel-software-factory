"""Dashboard API routes and WebSocket handlers."""

import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

from factory.orchestration.engine import get_engine, FactoryEngine
from factory.orchestration.state import FactoryState, WorkItem, StageStatus, AgentStatus
from factory.orchestration.checkpoints import create_checkpoint_store
from factory.config.settings import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.run_subscriptions: Dict[str, set] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info("ws_connected", client_id=client_id, total=len(self.active_connections))
    
    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        # Remove from all subscriptions
        for run_id in list(self.run_subscriptions.keys()):
            self.run_subscriptions[run_id].discard(client_id)
            if not self.run_subscriptions[run_id]:
                del self.run_subscriptions[run_id]
        logger.info("ws_disconnected", client_id=client_id, total=len(self.active_connections))
    
    def subscribe_to_run(self, client_id: str, run_id: str):
        if run_id not in self.run_subscriptions:
            self.run_subscriptions[run_id] = set()
        self.run_subscriptions[run_id].add(client_id)
    
    async def send_personal_message(self, message: dict, client_id: str):
        websocket = self.active_connections.get(client_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect(client_id)
    
    async def broadcast_to_run(self, message: dict, run_id: str):
        client_ids = self.run_subscriptions.get(run_id, set()).copy()
        for client_id in client_ids:
            await self.send_personal_message(message, client_id)
    
    async def broadcast(self, message: dict):
        for client_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, client_id)


manager = ConnectionManager()


# Request/Response models
class WorkItemRequest(BaseModel):
    title: str
    description: str
    source: str = "manual"
    source_id: str = ""
    repository: str
    branch: str = "main"
    priority: str = "medium"
    labels: List[str] = []


class RunResponse(BaseModel):
    run_id: str
    work_item: Dict[str, Any]
    status: str
    current_stage: Optional[str]
    stages: Dict[str, Any]
    metrics: Dict[str, Any]
    created_at: str
    updated_at: str


class StageMetricsResponse(BaseModel):
    stage_id: str
    name: str
    status: str
    throughput: int
    pass_rate: float
    avg_cycle_time: float
    queue_depth: int


# API Routes
@router.post("/runs", response_model=RunResponse)
async def create_run(request: WorkItemRequest):
    """Create a new factory run."""
    engine = get_engine()
    
    work_item = WorkItem(
        title=request.title,
        description=request.description,
        source=request.source,
        source_id=request.source_id or f"manual-{datetime.utcnow().timestamp()}",
        repository=request.repository,
        branch=request.branch,
        priority=request.priority,
        labels=request.labels,
    )
    
    state = await engine.run(work_item)
    
    return RunResponse(
        run_id=str(state.run_id),
        work_item=work_item.model_dump(),
        status=state.overall_status,
        current_stage=state.current_stage,
        stages={sid: se.model_dump() for sid, se in state.stages.items()},
        metrics={
            "total_tokens": state.total_tokens,
            "total_cost": state.total_cost,
        },
        created_at=state.started_at.isoformat(),
        updated_at=state.updated_at.isoformat(),
    )


@router.get("/runs")
async def list_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
):
    """List factory runs."""
    engine = get_engine()
    runs = await engine.list_runs(limit, offset)
    return {"runs": runs, "limit": limit, "offset": offset}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get run details."""
    engine = get_engine()
    state = await engine.get_state(run_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return RunResponse(
        run_id=str(state.run_id),
        work_item=state.work_item.model_dump(),
        status=state.overall_status,
        current_stage=state.current_stage,
        stages={sid: se.model_dump() for sid, se in state.stages.items()},
        metrics={
            "total_tokens": state.total_tokens,
            "total_cost": state.total_cost,
        },
        created_at=state.started_at.isoformat(),
        updated_at=state.updated_at.isoformat(),
    )


@router.get("/runs/{run_id}/history")
async def get_run_history(run_id: str):
    """Get checkpoint history for a run."""
    engine = get_engine()
    history = await engine.get_run_history(run_id)
    return {"history": [h.model_dump() for h in history]}


@router.post("/runs/{run_id}/checkpoint/{checkpoint_id}/approve")
async def approve_checkpoint(run_id: str, checkpoint_id: str, approver: str = "api-user"):
    """Approve a human checkpoint."""
    engine = get_engine()
    await engine.approve_checkpoint(checkpoint_id, approver)
    return {"success": True, "checkpoint_id": checkpoint_id, "status": "approved"}


@router.post("/runs/{run_id}/checkpoint/{checkpoint_id}/reject")
async def reject_checkpoint(run_id: str, checkpoint_id: str, approver: str = "api-user"):
    """Reject a human checkpoint."""
    engine = get_engine()
    await engine.reject_checkpoint(checkpoint_id, approver)
    return {"success": True, "checkpoint_id": checkpoint_id, "status": "rejected"}


@router.get("/metrics/overview")
async def get_overview_metrics(
    time_range: str = Query("24h", pattern="^(1h|24h|7d|30d)$"),
):
    """Get factory overview metrics."""
    engine = get_engine()
    runs = await engine.list_runs(200)
    
    # Calculate metrics from recent runs
    now = datetime.utcnow()
    if time_range == "1h":
        cutoff = now - timedelta(hours=1)
    elif time_range == "24h":
        cutoff = now - timedelta(days=1)
    elif time_range == "7d":
        cutoff = now - timedelta(days=7)
    else:
        cutoff = now - timedelta(days=30)
    
    # Filter runs (simplified)
    total_runs = len(runs)
    completed = sum(1 for r in runs if r.get("updated_at", "") > cutoff.isoformat())
    
    return {
        "time_range": time_range,
        "total_runs": total_runs,
        "completed_runs": completed,
        "success_rate": completed / total_runs if total_runs > 0 else 0,
        "stages": {
            "triage": {"throughput": 0, "backlog": 0},
            "planning": {"throughput": 0, "avg_time": 0},
            "execution": {"throughput": 0, "success_rate": 0},
            "validation": {"pass_rate": 0, "volume": 0},
            "release": {"deployments": 0, "cycle_time": 0},
            "document": {"updated": 0, "coverage": 0},
            "monitor": {"incidents": 0, "mttr": 0},
        },
    }


@router.get("/metrics/stage/{stage_id}")
async def get_stage_metrics(stage_id: str, time_range: str = "24h"):
    """Get metrics for a specific stage."""
    # Placeholder - would query Prometheus/metrics store
    return {
        "stage_id": stage_id,
        "time_range": time_range,
        "throughput": 0,
        "pass_rate": 0.0,
        "avg_cycle_time": 0.0,
        "queue_depth": 0,
        "health": "unknown",
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
    }


@router.get("/config")
async def get_config():
    """Get current configuration (sanitized)."""
    return {
        "stages": [s.model_dump() for s in settings.stages],
        "models": [
            {
                "id": m.id,
                "provider": m.provider,
                "capabilities": m.capabilities,
            }
            for m in settings.router.models
        ],
    }


# WebSocket endpoint
@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket for real-time updates."""
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Handle subscription messages
            if data.get("type") == "subscribe":
                run_id = data.get("run_id")
                if run_id:
                    manager.subscribe_to_run(client_id, run_id)
                    await manager.send_personal_message({
                        "type": "subscribed",
                        "run_id": run_id,
                    }, client_id)
            
            elif data.get("type") == "unsubscribe":
                run_id = data.get("run_id")
                if run_id and run_id in manager.run_subscriptions:
                    manager.run_subscriptions[run_id].discard(client_id)
            
            elif data.get("type") == "ping":
                await manager.send_personal_message({"type": "pong"}, client_id)
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error("ws_error", client_id=client_id, error=str(e))
        manager.disconnect(client_id)


# Background task to push updates
async def push_run_update(run_id: str, update: Dict[str, Any]):
    """Push update to subscribed clients."""
    await manager.broadcast_to_run({
        "type": "run_update",
        "run_id": run_id,
        "data": update,
        "timestamp": datetime.utcnow().isoformat(),
    }, run_id)


async def push_agent_thought(run_id: str, agent_name: str, thought: str, action: Optional[str] = None):
    """Push agent thought/action to subscribed clients."""
    await manager.broadcast_to_run({
        "type": "agent_thought",
        "run_id": run_id,
        "agent": agent_name,
        "thought": thought,
        "action": action,
        "timestamp": datetime.utcnow().isoformat(),
    }, run_id)


async def push_stage_transition(run_id: str, from_stage: Optional[str], to_stage: str):
    """Push stage transition."""
    await manager.broadcast_to_run({
        "type": "stage_transition",
        "run_id": run_id,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "timestamp": datetime.utcnow().isoformat(),
    }, run_id)