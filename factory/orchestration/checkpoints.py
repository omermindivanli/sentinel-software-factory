"""Checkpointing system for LangGraph state persistence."""

import json
import sqlite3
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
import structlog

from factory.orchestration.state import FactoryState

logger = structlog.get_logger(__name__)


class CheckpointStore:
    """SQLite-based checkpoint store for factory state."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    run_id TEXT PRIMARY KEY,
                    work_item_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS checkpoint_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stage_id TEXT,
                    state_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES checkpoints (run_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_history_run_id 
                ON checkpoint_history (run_id);
                
                CREATE INDEX IF NOT EXISTS idx_history_created 
                ON checkpoint_history (created_at);
            """)
    
    @asynccontextmanager
    async def _get_conn_async(self):
        """Get async database connection."""
        # For async, we use a thread pool since sqlite3 is sync
        loop = asyncio.get_event_loop()
        conn = await loop.run_in_executor(None, self._get_sync_conn)
        try:
            yield conn
        finally:
            await loop.run_in_executor(None, conn.close)
    
    def _get_sync_conn(self) -> sqlite3.Connection:
        """Get synchronous connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get connection (sync context manager)."""
        if self._conn is None:
            self._conn = self._get_sync_conn()
        return self._conn
    
    async def save(self, state: FactoryState) -> None:
        """Save checkpoint."""
        state_json = state.model_dump_json()
        
        def _save():
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO checkpoints (run_id, work_item_id, state_json, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    str(state.run_id),
                    str(state.work_item.id),
                    state_json,
                    datetime.utcnow().isoformat()
                ))
                conn.commit()
        
        await asyncio.get_event_loop().run_in_executor(None, _save)
        
        # Also save to history
        await self.save_history(state)
        
        logger.debug("checkpoint_saved", run_id=str(state.run_id))
    
    async def save_history(self, state: FactoryState) -> None:
        """Save state to history."""
        state_json = state.model_dump_json()
        
        def _save_history():
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO checkpoint_history (run_id, stage_id, state_json)
                    VALUES (?, ?, ?)
                """, (
                    str(state.run_id),
                    state.current_stage,
                    state_json
                ))
                conn.commit()
        
        await asyncio.get_event_loop().run_in_executor(None, _save_history)
    
    async def load(self, run_id: str) -> Optional[FactoryState]:
        """Load checkpoint by run ID."""
        def _load():
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT state_json FROM checkpoints WHERE run_id = ?",
                    (run_id,)
                ).fetchone()
                return row["state_json"] if row else None
        
        state_json = await asyncio.get_event_loop().run_in_executor(None, _load)
        
        if state_json:
            return FactoryState.model_validate_json(state_json)
        return None
    
    async def load_latest_for_work_item(self, work_item_id: str) -> Optional[FactoryState]:
        """Load latest checkpoint for a work item."""
        def _load():
            with self._get_conn() as conn:
                row = conn.execute("""
                    SELECT state_json FROM checkpoints 
                    WHERE work_item_id = ? 
                    ORDER BY updated_at DESC 
                    LIMIT 1
                """, (work_item_id,)).fetchone()
                return row["state_json"] if row else None
        
        state_json = await asyncio.get_event_loop().run_in_executor(None, _load)
        
        if state_json:
            return FactoryState.model_validate_json(state_json)
        return None
    
    async def get_history(self, run_id: str, limit: int = 100) -> List[FactoryState]:
        """Get checkpoint history for a run."""
        def _get_history():
            with self._get_conn() as conn:
                rows = conn.execute("""
                    SELECT state_json FROM checkpoint_history 
                    WHERE run_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (run_id, limit)).fetchall()
                return [row["state_json"] for row in rows]
        
        state_jsons = await asyncio.get_event_loop().run_in_executor(None, _get_history)
        return [FactoryState.model_validate_json(s) for s in state_jsons]
    
    async def list_runs(
        self, 
        limit: int = 50, 
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List recent runs."""
        def _list():
            with self._get_conn() as conn:
                query = "SELECT run_id, work_item_id, created_at, updated_at FROM checkpoints"
                params = []
                if status:
                    query += " WHERE json_extract(state_json, '$.overall_status') = ?"
                    params.append(status)
                query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                rows = conn.execute(query, params).fetchall()
                return [dict(row) for row in rows]
        
        return await asyncio.get_event_loop().run_in_executor(None, _list)
    
    async def delete(self, run_id: str) -> bool:
        """Delete checkpoint."""
        def _delete():
            with self._get_conn() as conn:
                cursor = conn.execute("DELETE FROM checkpoints WHERE run_id = ?", (run_id,))
                conn.commit()
                return cursor.rowcount > 0
        
        return await asyncio.get_event_loop().run_in_executor(None, _delete)
    
    async def cleanup_old(self, days: int = 30) -> int:
        """Clean up checkpoints older than specified days."""
        def _cleanup():
            with self._get_conn() as conn:
                cursor = conn.execute("""
                    DELETE FROM checkpoints 
                    WHERE updated_at < datetime('now', ?)
                """, (f'-{days} days',))
                conn.commit()
                return cursor.rowcount
        
        return await asyncio.get_event_loop().run_in_executor(None, _cleanup)
    
    def close(self) -> None:
        """Close connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


class FileCheckpointStore:
    """File-based checkpoint store (simpler, for development)."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, run_id: str) -> Path:
        return self.base_path / f"{run_id}.json"
    
    def _get_history_dir(self, run_id: str) -> Path:
        path = self.base_path / "history" / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    async def save(self, state: FactoryState) -> None:
        """Save checkpoint to file."""
        path = self._get_path(str(state.run_id))
        
        def _write():
            path.write_text(state.model_dump_json(indent=2))
        
        await asyncio.get_event_loop().run_in_executor(None, _write)
        
        # Save to history
        history_dir = self._get_history_dir(str(state.run_id))
        history_file = history_dir / f"{state.current_stage or 'init'}_{datetime.utcnow().isoformat()}.json"
        
        def _write_history():
            history_file.write_text(state.model_dump_json(indent=2))
        
        await asyncio.get_event_loop().run_in_executor(None, _write_history)
    
    async def load(self, run_id: str) -> Optional[FactoryState]:
        """Load checkpoint from file."""
        path = self._get_path(run_id)
        
        if not path.exists():
            return None
        
        def _read():
            return path.read_text()
        
        content = await asyncio.get_event_loop().run_in_executor(None, _read)
        return FactoryState.model_validate_json(content)
    
    async def load_latest_for_work_item(self, work_item_id: str) -> Optional[FactoryState]:
        """Load latest checkpoint for work item."""
        # Search all checkpoint files
        for path in self.base_path.glob("*.json"):
            try:
                content = path.read_text()
                state = FactoryState.model_validate_json(content)
                if str(state.work_item.id) == work_item_id:
                    return state
            except Exception:
                continue
        return None
    
    async def list_runs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List recent runs."""
        files = sorted(
            self.base_path.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[offset:offset + limit]
        
        runs = []
        for path in files:
            try:
                content = path.read_text()
                state = FactoryState.model_validate_json(content)
                runs.append({
                    "run_id": str(state.run_id),
                    "work_item_id": str(state.work_item.id),
                    "created_at": state.started_at.isoformat(),
                    "updated_at": state.updated_at.isoformat(),
                })
            except Exception:
                continue
        return runs


def create_checkpoint_store(settings) -> CheckpointStore:
    """Factory function to create checkpoint store based on settings."""
    db_path = settings.data_dir / "checkpoints.db"
    return CheckpointStore(db_path)