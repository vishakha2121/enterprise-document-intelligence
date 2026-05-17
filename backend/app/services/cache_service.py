"""
Cache Service
Redis caching for improved performance
"""

import json
import logging
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Service for Redis cache operations"""
    
    def __init__(self, redis_client: redis.Redis):
        self.client = redis_client
        self.default_ttl = settings.REDIS_CACHE_TTL
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except RedisError as e:
            logger.error(f"Redis GET error: {str(e)}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache with TTL"""
        try:
            serialized = json.dumps(value, default=str)
            ttl_seconds = ttl or self.default_ttl
            await self.client.setex(key, ttl_seconds, serialized)
            return True
        except RedisError as e:
            logger.error(f"Redis SET error: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            await self.client.delete(key)
            return True
        except RedisError as e:
            logger.error(f"Redis DELETE error: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return await self.client.exists(key) > 0
        except RedisError as e:
            logger.error(f"Redis EXISTS error: {str(e)}")
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on existing key"""
        try:
            return await self.client.expire(key, ttl)
        except RedisError as e:
            logger.error(f"Redis EXPIRE error: {str(e)}")
            return False
    
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter"""
        try:
            return await self.client.incrby(key, amount)
        except RedisError as e:
            logger.error(f"Redis INCR error: {str(e)}")
            return None
    
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Set hash field"""
        try:
            serialized = json.dumps(value, default=str)
            await self.client.hset(key, field, serialized)
            return True
        except RedisError as e:
            logger.error(f"Redis HSET error: {str(e)}")
            return False
    
    async def hget(self, key: str, field: str) -> Optional[Any]:
        """Get hash field"""
        try:
            value = await self.client.hget(key, field)
            if value:
                return json.loads(value)
            return None
        except RedisError as e:
            logger.error(f"Redis HGET error: {str(e)}")
            return None
    
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all hash fields"""
        try:
            result = await self.client.hgetall(key)
            return {
                k.decode(): json.loads(v)
                for k, v in result.items()
            }
        except RedisError as e:
            logger.error(f"Redis HGETALL error: {str(e)}")
            return {}
    
    async def lpush(self, key: str, value: Any) -> bool:
        """Push to list (left)"""
        try:
            serialized = json.dumps(value, default=str)
            await self.client.lpush(key, serialized)
            return True
        except RedisError as e:
            logger.error(f"Redis LPUSH error: {str(e)}")
            return False
    
    async def rpop(self, key: str) -> Optional[Any]:
        """Pop from list (right)"""
        try:
            value = await self.client.rpop(key)
            if value:
                return json.loads(value)
            return None
        except RedisError as e:
            logger.error(f"Redis RPOP error: {str(e)}")
            return None
    
    async def lrange(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """Get range from list"""
        try:
            values = await self.client.lrange(key, start, end)
            return [json.loads(v) for v in values]
        except RedisError as e:
            logger.error(f"Redis LRANGE error: {str(e)}")
            return []
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern"""
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await self.client.delete(*keys)
            return 0
        except RedisError as e:
            logger.error(f"Redis DELETE_PATTERN error: {str(e)}")
            return 0
    
    async def clear_all(self) -> bool:
        """Clear all cache (use with caution)"""
        try:
            await self.client.flushdb()
            logger.warning("Cache completely cleared")
            return True
        except RedisError as e:
            logger.error(f"Redis FLUSHDB error: {str(e)}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            info = await self.client.info("stats")
            return {
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": info.get("keyspace_hits", 0) / (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1)) * 100,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": await self.client.info("memory").get("used_memory_human", "0"),
                "uptime_days": await self.client.info("server").get("uptime_in_days", 0)
            }
        except RedisError as e:
            logger.error(f"Redis GET_STATS error: {str(e)}")
            return {}
    
    async def ping(self) -> bool:
        """Test Redis connection"""
        try:
            return await self.client.ping()
        except RedisError as e:
            logger.error(f"Redis PING error: {str(e)}")
            return False
    
    # Convenience methods for common patterns
    async def cache_document_extraction(self, document_id: int, extraction_data: Any) -> bool:
        """Cache document extraction result"""
        key = f"extraction:{document_id}"
        return await self.set(key, extraction_data, ttl=86400)  # 24 hours
    
    async def get_cached_extraction(self, document_id: int) -> Optional[Any]:
        """Get cached extraction result"""
        key = f"extraction:{document_id}"
        return await self.get(key)
    
    async def cache_classification(self, document_id: int, classification: Any) -> bool:
        """Cache document classification"""
        key = f"classification:{document_id}"
        return await self.set(key, classification, ttl=86400)
    
    async def get_cached_classification(self, document_id: int) -> Optional[Any]:
        """Get cached classification"""
        key = f"classification:{document_id}"
        return await self.get(key)
    
    async def rate_limit_check(self, client_id: str, limit: int = 100, period: int = 60) -> bool:
        """
        Rate limit check
        Returns True if under limit, False if over
        """
        key = f"rate_limit:{client_id}"
        current = await self.get(key)
        
        if current is None:
            await self.set(key, 1, ttl=period)
            return True
        
        if isinstance(current, (int, float)):
            if current >= limit:
                return False
            await self.incr(key)
            return True
        
        return True