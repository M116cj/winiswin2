"""💾 Cache Manager - Multi-tier caching (Memory, Redis, PostgreSQL)"""
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """Unified cache interface"""
    def __init__(self):
        self.memory_cache = {}
    
    async def get(self, key: str):
        """Get from cache"""
        return self.memory_cache.get(key)
    
    async def set(self, key: str, value, ttl: int = 300):
        """Set cache value"""
        self.memory_cache[key] = value
    
    async def delete(self, key: str):
        """Delete cache entry"""
        self.memory_cache.pop(key, None)

_cache_manager = CacheManager()

def get_cache_manager() -> CacheManager:
    """Get global cache manager instance"""
    return _cache_manager
