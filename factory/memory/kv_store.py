"""KV store for working/procedural memory using Redis."""

import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import structlog

import redis.asyncio as redis

from factory.config.settings import settings

logger = structlog.get_logger(__name__)


class KVStore:
    """Redis-backed key-value store for working memory and caching."""
    
    def __init__(self, url: Optional[str] = None):
        self.url = url or settings.memory.redis_url
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
    
    async def initialize(self) -> None:
        """Initialize Redis connection."""
        self._client = redis.from_url(
            self.url,
            encoding="utf-8",
            decode_responses=True,
        )
        
        # Test connection
        await self._client.ping()
        logger.info("redis_connected", url=self.url)
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        nx: bool = False,
    ) -> bool:
        """Set key-value with optional TTL."""
        if not self._client:
            await self.initialize()
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        elif not isinstance(value, str):
            value = str(value)
        
        return await self._client.set(key, value, ex=ttl, nx=nx)
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value by key."""
        if not self._client:
            await self.initialize()
        
        value = await self._client.get(key)
        if value is None:
            return default
        
        # Try to parse JSON
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    
    async def delete(self, key: str) -> int:
        """Delete key."""
        if not self._client:
            await self.initialize()
        return await self._client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._client:
            await self.initialize()
        return await self._client.exists(key) > 0
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL on existing key."""
        if not self._client:
            await self.initialize()
        return await self._client.expire(key, ttl)
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern."""
        if not self._client:
            await self.initialize()
        return await self._client.keys(pattern)
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment numeric value."""
        if not self._client:
            await self.initialize()
        return await self._client.incrby(key, amount)
    
    async def hset(self, name: str, mapping: Dict[str, Any]) -> int:
        """Set hash fields."""
        if not self._client:
            await self.initialize()
        
        # Serialize values
        serialized = {}
        for k, v in mapping.items():
            if isinstance(v, (dict, list)):
                serialized[k] = json.dumps(v)
            else:
                serialized[k] = str(v)
        
        return await self._client.hset(name, mapping=serialized)
    
    async def hget(self, name: str, key: str) -> Any:
        """Get hash field."""
        if not self._client:
            await self.initialize()
        
        value = await self._client.hget(name, key)
        if value is None:
            return None
        
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    
    async def hgetall(self, name: str) -> Dict[str, Any]:
        """Get all hash fields."""
        if not self._client:
            await self.initialize()
        
        data = await self._client.hgetall(name)
        result = {}
        for k, v in data.items():
            try:
                result[k] = json.loads(v)
            except json.JSONDecodeError:
                result[k] = v
        return result
    
    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields."""
        if not self._client:
            await self.initialize()
        return await self._client.hdel(name, *keys)
    
    # Pub/Sub for real-time updates
    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to channel."""
        if not self._client:
            await self.initialize()
        
        if isinstance(message, (dict, list)):
            message = json.dumps(message)
        elif not isinstance(message, str):
            message = str(message)
        
        return await self._client.publish(channel, message)
    
    async def subscribe(self, channel: str):
        """Subscribe to channel."""
        if not self._client:
            await self.initialize()
        
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        return pubsub
    
    async def close(self) -> None:
        """Close connection."""
        if self._client:
            await self._client.close()
        if self._pubsub:
            await self._pubsub.close()


# Global KV store
_kv_store: Optional[KVStore] = None


def get_kv_store() -> KVStore:
    global _kv_store
    if _kv_store is None:
        _kv_store = KVStore()
    return _kv_store


async def initialize_kv_store() -> KVStore:
    """Initialize global KV store."""
    store = get_kv_store()
    await store.initialize()
    return store