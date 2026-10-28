"""Vector store for episodic memory using ChromaDB."""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
import structlog

import chromadb
from chromadb.config import Settings as ChromaSettings

from factory.config.settings import settings

logger = structlog.get_logger(__name__)


class VectorStore:
    """ChromaDB-backed vector store for episodic memory."""
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        collection_prefix: str = "factory",
    ):
        self.host = host or settings.memory.chroma_host
        self.port = port or settings.memory.chroma_port
        self.collection_prefix = collection_prefix
        self._client: Optional[chromadb.HttpClient] = None
        self._collections: Dict[str, Any] = {}
    
    async def initialize(self) -> None:
        """Initialize ChromaDB client."""
        self._client = chromadb.HttpClient(
            host=self.host,
            port=self.port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        
        # Test connection
        await asyncio.get_event_loop().run_in_executor(None, self._client.heartbeat)
        logger.info("chroma_connected", host=self.host, port=self.port)
    
    def _get_collection(self, name: str):
        """Get or create collection."""
        full_name = f"{self.collection_prefix}_{name}"
        if full_name not in self._collections:
            self._collections[full_name] = self._client.get_or_create_collection(
                name=full_name,
                metadata={"created_at": datetime.utcnow().isoformat()},
            )
        return self._collections[full_name]
    
    async def add(
        self,
        collection: str,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Add documents to collection."""
        if not self._client:
            await self.initialize()
        
        coll = self._get_collection(collection)
        
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        
        # Add timestamps
        for meta in metadatas:
            meta["timestamp"] = meta.get("timestamp", datetime.utcnow().isoformat())
            meta["collection"] = collection
        
        def _add():
            coll.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
        
        await asyncio.get_event_loop().run_in_executor(None, _add)
        return ids
    
    async def query(
        self,
        collection: str,
        query_texts: List[str],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Query collection for similar documents."""
        if not self._client:
            await self.initialize()
        
        coll = self._get_collection(collection)
        
        def _query():
            return coll.query(
                query_texts=query_texts,
                n_results=n_results,
                where=where,
                where_document=where_document,
            )
        
        return await asyncio.get_event_loop().run_in_executor(None, _query)
    
    async def get(
        self,
        collection: str,
        ids: List[str],
    ) -> Dict[str, Any]:
        """Get documents by IDs."""
        if not self._client:
            await self.initialize()
        
        coll = self._get_collection(collection)
        
        def _get():
            return coll.get(ids=ids)
        
        return await asyncio.get_event_loop().run_in_executor(None, _get)
    
    async def delete(
        self,
        collection: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Delete documents."""
        if not self._client:
            await self.initialize()
        
        coll = self._get_collection(collection)
        
        def _delete():
            coll.delete(ids=ids, where=where)
        
        await asyncio.get_event_loop().run_in_executor(None, _delete)
    
    async def count(self, collection: str) -> int:
        """Count documents in collection."""
        if not self._client:
            await self.initialize()
        
        coll = self._get_collection(collection)
        
        def _count():
            return coll.count()
        
        return await asyncio.get_event_loop().run_in_executor(None, _count)
    
    async def list_collections(self) -> List[str]:
        """List all collections."""
        if not self._client:
            await self.initialize()
        
        def _list():
            return [c.name for c in self._client.list_collections()]
        
        return await asyncio.get_event_loop().run_in_executor(None, _list)
    
    async def cleanup_old(self, collection: str, days: int = 30) -> int:
        """Remove documents older than specified days."""
        if not self._client:
            await self.initialize()
        
        coll = self._get_collection(collection)
        cutoff = datetime.utcnow().timestamp() - (days * 86400)
        
        def _cleanup():
            # Get all documents
            all_docs = coll.get()
            to_delete = []
            
            for i, meta in enumerate(all_docs.get("metadatas", [])):
                if meta and "timestamp" in meta:
                    try:
                        ts = datetime.fromisoformat(meta["timestamp"]).timestamp()
                        if ts < cutoff:
                            to_delete.append(all_docs["ids"][i])
                    except Exception:
                        pass
            
            if to_delete:
                coll.delete(ids=to_delete)
            return len(to_delete)
        
        return await asyncio.get_event_loop().run_in_executor(None, _cleanup)


# Global vector store
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


async def initialize_vector_store() -> VectorStore:
    """Initialize global vector store."""
    store = get_vector_store()
    await store.initialize()
    return store