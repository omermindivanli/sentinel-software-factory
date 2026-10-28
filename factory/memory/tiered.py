"""Tiered memory facade combining all memory stores."""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import structlog

from factory.memory.vector_store import get_vector_store, VectorStore
from factory.memory.graph_store import get_graph_store, GraphStore
from factory.memory.kv_store import get_kv_store, KVStore

logger = structlog.get_logger(__name__)


class MemoryTier(str, Enum):
    """Memory tier enumeration."""
    WORKING = "working"      # In-context, session-scoped
    EPISODIC = "episodic"    # Vector store, conversation history
    SEMANTIC = "semantic"    # Graph store, knowledge/patterns
    PROCEDURAL = "procedural"  # Prompt templates, skills


class TieredMemory:
    """
    Unified interface for all memory tiers.
    
    Implements the 4-tier memory architecture from Agentic Design Patterns:
    - Working: Active task context (Redis, TTL: 1hr)
    - Episodic: Conversation history, decisions (ChromaDB, TTL: 30 days)
    - Semantic: Architecture decisions, patterns (Neo4j, permanent)
    - Procedural: Skills, workflows, templates (Versioned, permanent)
    """
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        graph_store: Optional[GraphStore] = None,
        kv_store: Optional[KVStore] = None,
    ):
        self.vector = vector_store or get_vector_store()
        self.graph = graph_store or get_graph_store()
        self.kv = kv_store or get_kv_store()
    
    async def initialize(self) -> None:
        """Initialize all memory stores."""
        await asyncio.gather(
            self.vector.initialize(),
            self.graph.initialize(),
            self.kv.initialize(),
            return_exceptions=True,
        )
        logger.info("tiered_memory_initialized")
    
    # ==================== Working Memory (Redis, short TTL) ====================
    
    async def set_working(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,  # 1 hour default
    ) -> bool:
        """Set working memory (session-scoped)."""
        return await self.kv.set(f"working:{key}", value, ttl=ttl)
    
    async def get_working(self, key: str, default: Any = None) -> Any:
        """Get working memory."""
        return await self.kv.get(f"working:{key}", default)
    
    async def delete_working(self, key: str) -> int:
        """Delete working memory."""
        return await self.kv.delete(f"working:{key}")
    
    # ==================== Episodic Memory (Vector store, 30 days) ====================
    
    async def add_episode(
        self,
        collection: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Add an episodic memory (conversation, decision, event)."""
        episode_id = f"ep_{datetime.utcnow().timestamp()}"
        metadata["episode_id"] = episode_id
        metadata["tier"] = "episodic"
        
        await self.vector.add(
            collection=collection,
            documents=[content],
            metadatas=[metadata],
            ids=[episode_id],
        )
        return episode_id
    
    async def recall_episodes(
        self,
        collection: str,
        query: str,
        limit: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Recall relevant episodes."""
        results = await self.vector.query(
            collection=collection,
            query_texts=[query],
            n_results=limit,
            where=filter_metadata,
        )
        
        episodes = []
        for i, doc in enumerate(results.get("documents", [[]])[0]):
            episodes.append({
                "id": results["ids"][0][i] if results.get("ids") else None,
                "content": doc,
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        
        return episodes
    
    async def get_recent_episodes(
        self,
        collection: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get most recent episodes."""
        # Query with empty string to get all, then sort by timestamp
        results = await self.vector.query(
            collection=collection,
            query_texts=[""],
            n_results=limit * 2,  # Get more to sort
        )
        
        episodes = []
        for i, doc in enumerate(results.get("documents", [[]])[0]):
            episodes.append({
                "id": results["ids"][0][i] if results.get("ids") else None,
                "content": doc,
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
            })
        
        # Sort by timestamp descending
        episodes.sort(
            key=lambda e: e["metadata"].get("timestamp", ""),
            reverse=True
        )
        
        return episodes[:limit]
    
    # ==================== Semantic Memory (Graph store, permanent) ====================
    
    async def record_decision(
        self,
        decision_id: str,
        title: str,
        description: str,
        context: str,
        status: str = "proposed",
        related: Optional[List[str]] = None,
    ) -> None:
        """Record an architecture decision (ADR)."""
        await self.graph.add_decision(
            decision_id=decision_id,
            title=title,
            description=description,
            context=context,
            status=status,
            related_decisions=related,
        )
        
        # Also store in episodic for retrieval
        await self.add_episode(
            collection="decisions",
            content=f"{title}\n\n{description}\n\nContext: {context}",
            metadata={
                "decision_id": decision_id,
                "title": title,
                "status": status,
                "type": "architecture_decision",
            },
        )
    
    async def record_pattern(
        self,
        pattern_id: str,
        name: str,
        description: str,
        category: str,
        code_example: str = "",
    ) -> None:
        """Record a reusable pattern."""
        await self.graph.add_pattern(
            pattern_id=pattern_id,
            name=name,
            description=description,
            category=category,
            code_example=code_example,
        )
    
    async def record_component(
        self,
        component_id: str,
        name: str,
        type: str,
        repository: str,
        description: str = "",
        dependencies: Optional[List[str]] = None,
    ) -> None:
        """Record a system component."""
        await self.graph.add_component(
            component_id=component_id,
            name=name,
            type=type,
            repository=repository,
            description=description,
            dependencies=dependencies,
        )
    
    async def query_knowledge(
        self,
        query: str,
        limit: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Query semantic knowledge (decisions + patterns)."""
        decisions = await self.graph.query_decisions(query, limit)
        patterns = await self.graph.query_patterns(limit=limit)
        
        return {
            "decisions": decisions,
            "patterns": patterns,
        }
    
    async def get_architecture_graph(
        self,
        repository: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get component dependency graph."""
        return await self.graph.get_component_graph(repository)
    
    # ==================== Procedural Memory (Versioned templates) ====================
    
    async def save_procedure(
        self,
        name: str,
        version: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save a procedure/template/skill."""
        key = f"procedural:{name}:{version}"
        meta = metadata or {}
        meta.update({
            "name": name,
            "version": version,
            "saved_at": datetime.utcnow().isoformat(),
        })
        
        await self.kv.hset(key, {
            "content": content,
            "metadata": meta,
        })
        
        # Also track versions
        await self.kv.hset(f"procedural:{name}:versions", {
            version: datetime.utcnow().isoformat(),
        })
        
        return key
    
    async def load_procedure(
        self,
        name: str,
        version: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Load a procedure by name and version."""
        if version:
            key = f"procedural:{name}:{version}"
        else:
            # Get latest version
            versions = await self.kv.hgetall(f"procedural:{name}:versions")
            if not versions:
                return None
            version = max(versions.keys())
            key = f"procedural:{name}:{version}"
        
        data = await self.kv.hgetall(key)
        if not data:
            return None
        
        return {
            "name": name,
            "version": version,
            "content": data.get("content"),
            "metadata": data.get("metadata", {}),
        }
    
    async def list_procedures(self) -> List[Dict[str, Any]]:
        """List all procedures."""
        keys = await self.kv.keys("procedural:*:versions")
        procedures = []
        
        for key in keys:
            name = key.replace("procedural:", "").replace(":versions", "")
            versions = await self.kv.hgetall(key)
            for ver, ts in versions.items():
                procedures.append({
                    "name": name,
                    "version": ver,
                    "saved_at": ts,
                })
        
        return procedures
    
    # ==================== Unified Interface ====================
    
    async def store(
        self,
        tier: MemoryTier,
        key: str,
        value: Any,
        **kwargs,
    ) -> Any:
        """Unified store interface."""
        if tier == MemoryTier.WORKING:
            return await self.set_working(key, value, kwargs.get("ttl", 3600))
        elif tier == MemoryTier.EPISODIC:
            return await self.add_episode(
                kwargs.get("collection", "default"),
                str(value),
                kwargs.get("metadata", {}),
            )
        elif tier == MemoryTier.SEMANTIC:
            if kwargs.get("type") == "decision":
                return await self.record_decision(
                    kwargs.get("id", key),
                    kwargs.get("title", key),
                    str(value),
                    kwargs.get("context", ""),
                    kwargs.get("status", "proposed"),
                    kwargs.get("related"),
                )
            elif kwargs.get("type") == "pattern":
                return await self.record_pattern(
                    kwargs.get("id", key),
                    kwargs.get("name", key),
                    str(value),
                    kwargs.get("category", "general"),
                    kwargs.get("code_example", ""),
                )
        elif tier == MemoryTier.PROCEDURAL:
            return await self.save_procedure(
                name=key,
                version=kwargs.get("version", "1.0"),
                content=str(value),
                metadata=kwargs.get("metadata"),
            )
    
    async def retrieve(
        self,
        tier: MemoryTier,
        key: str,
        **kwargs,
    ) -> Any:
        """Unified retrieve interface."""
        if tier == MemoryTier.WORKING:
            return await self.get_working(key, kwargs.get("default"))
        elif tier == MemoryTier.EPISODIC:
            return await self.recall_episodes(
                kwargs.get("collection", "default"),
                key,
                kwargs.get("limit", 10),
                kwargs.get("filter"),
            )
        elif tier == MemoryTier.SEMANTIC:
            return await self.query_knowledge(key, kwargs.get("limit", 10))
        elif tier == MemoryTier.PROCEDURAL:
            return await self.load_procedure(key, kwargs.get("version"))
    
    async def cleanup_expired(self) -> Dict[str, int]:
        """Clean up expired entries across tiers."""
        results = {}
        
        # Clean episodic (older than 30 days)
        collections = await self.vector.list_collections()
        total_cleaned = 0
        for coll in collections:
            if coll.startswith("factory_"):
                cleaned = await self.vector.cleanup_old(coll, days=30)
                total_cleaned += cleaned
        results["episodic_cleaned"] = total_cleaned
        
        # Working memory auto-expires via TTL
        
        return results


# Global tiered memory
_tiered_memory: Optional[TieredMemory] = None


def get_tiered_memory() -> TieredMemory:
    global _tiered_memory
    if _tiered_memory is None:
        _tiered_memory = TieredMemory()
    return _tiered_memory


async def initialize_tiered_memory() -> TieredMemory:
    """Initialize global tiered memory."""
    memory = get_tiered_memory()
    await memory.initialize()
    return memory