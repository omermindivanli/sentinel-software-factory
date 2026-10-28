"""Memory bus for shared context across agents."""

import json
import asyncio
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID
import structlog

from factory.config.settings import settings

logger = structlog.get_logger(__name__)


class MemoryBus:
    """
    Central memory bus for sharing context across agents.
    Provides pub/sub, key-value storage, and context propagation.
    """
    
    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._kv_store: Dict[str, Any] = {}
        self._ttl: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to channel. Returns number of subscribers notified."""
        async with self._lock:
            queues = self._subscribers.get(channel, set()).copy()
        
        count = 0
        for queue in queues:
            try:
                await queue.put(message)
                count += 1
            except Exception:
                pass
        
        if count > 0:
            logger.debug("published", channel=channel, subscribers=count)
        
        return count
    
    async def subscribe(self, channel: str) -> asyncio.Queue:
        """Subscribe to channel. Returns queue for receiving messages."""
        queue = asyncio.Queue()
        async with self._lock:
            if channel not in self._subscribers:
                self._subscribers[channel] = set()
            self._subscribers[channel].add(queue)
        return queue
    
    async def unsubscribe(self, channel: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from channel."""
        async with self._lock:
            if channel in self._subscribers:
                self._subscribers[channel].discard(queue)
                if not self._subscribers[channel]:
                    del self._subscribers[channel]
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set key-value with optional TTL."""
        async with self._lock:
            self._kv_store[key] = value
            if ttl_seconds:
                self._ttl[key] = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            elif key in self._ttl:
                del self._ttl[key]
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value by key."""
        async with self._lock:
            # Check TTL
            if key in self._ttl:
                if datetime.utcnow() > self._ttl[key]:
                    del self._kv_store[key]
                    del self._ttl[key]
                    return default
            return self._kv_store.get(key, default)
    
    async def delete(self, key: str) -> bool:
        """Delete key."""
        async with self._lock:
            if key in self._kv_store:
                del self._kv_store[key]
                if key in self._ttl:
                    del self._ttl[key]
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists and not expired."""
        async with self._lock:
            if key in self._ttl:
                if datetime.utcnow() > self._ttl[key]:
                    del self._kv_store[key]
                    del self._ttl[key]
                    return False
            return key in self._kv_store
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern."""
        import fnmatch
        async with self._lock:
            # Clean expired
            now = datetime.utcnow()
            expired = [k for k, v in self._ttl.items() if now > v]
            for k in expired:
                del self._kv_store[k]
                del self._ttl[k]
            
            return [k for k in self._kv_store.keys() if fnmatch.fnmatch(k, pattern)]
    
    async def clear_expired(self) -> int:
        """Clear all expired keys."""
        async with self._lock:
            now = datetime.utcnow()
            expired = [k for k, v in self._ttl.items() if now > v]
            for k in expired:
                del self._kv_store[k]
                del self._ttl[k]
            return len(expired)


class ContextPropagator:
    """
    Propagates context between stages and agents.
    Implements the "shared context" pattern from Agentic Design Patterns.
    """
    
    def __init__(self, memory_bus: MemoryBus):
        self.bus = memory_bus
        self._context_versions: Dict[str, int] = {}
    
    async def save_context(
        self, 
        run_id: str, 
        stage_id: str, 
        context: Dict[str, Any],
        version: Optional[int] = None
    ) -> int:
        """Save context for a stage."""
        key = f"context:{run_id}:{stage_id}"
        new_version = version or self._context_versions.get(key, 0) + 1
        self._context_versions[key] = new_version
        
        await self.bus.set(
            key, 
            {
                "version": new_version,
                "stage_id": stage_id,
                "context": context,
                "timestamp": datetime.utcnow().isoformat(),
            },
            ttl_seconds=86400  # 24 hours
        )
        
        # Also publish for real-time updates
        await self.bus.publish(f"context:{run_id}", {
            "stage_id": stage_id,
            "version": new_version,
            "keys": list(context.keys()),
        })
        
        return new_version
    
    async def load_context(
        self, 
        run_id: str, 
        stage_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load context for a stage."""
        key = f"context:{run_id}:{stage_id}"
        data = await self.bus.get(key)
        if data:
            return data.get("context")
        return None
    
    async def load_previous_context(
        self, 
        run_id: str, 
        current_stage: str,
        stage_order: List[str]
    ) -> Dict[str, Any]:
        """Load and merge context from all previous stages."""
        merged = {}
        
        try:
            idx = stage_order.index(current_stage)
            previous_stages = stage_order[:idx]
        except ValueError:
            previous_stages = stage_order
        
        for stage in previous_stages:
            context = await self.load_context(run_id, stage)
            if context:
                merged.update(context)
        
        return merged
    
    async def propagate_output(
        self, 
        run_id: str, 
        from_stage: str, 
        to_stage: str,
        output_keys: Optional[List[str]] = None
    ) -> None:
        """Propagate specific output keys from one stage to another."""
        context = await self.load_context(run_id, from_stage)
        if not context:
            return
        
        if output_keys:
            propagated = {k: v for k, v in context.items() if k in output_keys}
        else:
            propagated = context
        
        # Merge into target stage context
        target_context = await self.load_context(run_id, to_stage) or {}
        target_context.update(propagated)
        await self.save_context(run_id, to_stage, target_context)


class ArtifactStore:
    """Store for build artifacts, test results, logs."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_run_dir(self, run_id: str) -> Path:
        path = self.base_path / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    async def save_artifact(
        self, 
        run_id: str, 
        name: str, 
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save binary artifact."""
        run_dir = self._get_run_dir(run_id)
        file_path = run_dir / name
        
        def _write():
            file_path.write_bytes(content)
        
        await asyncio.get_event_loop().run_in_executor(None, _write)
        
        # Save metadata
        if metadata:
            meta_path = run_dir / f"{name}.meta.json"
            
            def _write_meta():
                meta_path.write_text(json.dumps(metadata, indent=2))
            
            await asyncio.get_event_loop().run_in_executor(None, _write_meta)
        
        return str(file_path)
    
    async def save_text_artifact(
        self, 
        run_id: str, 
        name: str, 
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save text artifact."""
        return await self.save_artifact(run_id, name, content.encode(), metadata)
    
    async def load_artifact(self, run_id: str, name: str) -> Optional[bytes]:
        """Load binary artifact."""
        run_dir = self._get_run_dir(run_id)
        file_path = run_dir / name
        
        if not file_path.exists():
            return None
        
        def _read():
            return file_path.read_bytes()
        
        return await asyncio.get_event_loop().run_in_executor(None, _read)
    
    async def load_text_artifact(self, run_id: str, name: str) -> Optional[str]:
        """Load text artifact."""
        data = await self.load_artifact(run_id, name)
        return data.decode() if data else None
    
    async def list_artifacts(self, run_id: str) -> List[Dict[str, Any]]:
        """List artifacts for a run."""
        run_dir = self._get_run_dir(run_id)
        
        def _list():
            artifacts = []
            for path in run_dir.iterdir():
                if path.name.endswith(".meta.json"):
                    continue
                meta_path = run_dir / f"{path.name}.meta.json"
                metadata = {}
                if meta_path.exists():
                    metadata = json.loads(meta_path.read_text())
                artifacts.append({
                    "name": path.name,
                    "size": path.stat().st_size,
                    "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    "metadata": metadata,
                })
            return artifacts
        
        return await asyncio.get_event_loop().run_in_executor(None, _list)


# Global instances
memory_bus = MemoryBus()
context_propagator = ContextPropagator(memory_bus)
artifact_store = ArtifactStore(settings.data_dir / "artifacts")


def get_memory_bus() -> MemoryBus:
    return memory_bus


def get_context_propagator() -> ContextPropagator:
    return context_propagator


def get_artifact_store() -> ArtifactStore:
    return artifact_store