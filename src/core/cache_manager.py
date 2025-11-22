"""Simple cache manager stub"""
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Simple in-memory cache"""
    def __init__(self):
        self._cache = {}
    
    def set(self, key: str, value, ttl: int = 3600):
        """Set cache value"""
        self._cache[key] = {'value': value, 'ttl': ttl}
    
    def get(self, key: str):
        """Get cache value"""
        if key in self._cache:
            return self._cache[key]['value']
        return None
    
    def delete(self, key: str):
        """Delete cache key"""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self):
        """Clear all cache"""
        self._cache.clear()
