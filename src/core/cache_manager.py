"""
緩存管理器
職責：統一緩存策略、差異化 TTL、內存優化
"""

import time
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """統一緩存管理器"""
    
    def __init__(self):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        獲取緩存值
        
        Args:
            key: 緩存鍵
        
        Returns:
            緩存值或 None
        """
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                self._hits += 1
                return value
            else:
                del self._cache[key]
        
        self._misses += 1
        return None
    
    def set(self, key: str, value: Any, ttl: int):
        """
        設置緩存值
        
        Args:
            key: 緩存鍵
            value: 緩存值
            ttl: 存活時間（秒）
        """
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)
    
    def delete(self, key: str):
        """刪除緩存項"""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self):
        """清空所有緩存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("緩存已清空")
    
    def cleanup_expired(self):
        """清理過期緩存"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, expiry) in self._cache.items()
            if current_time >= expiry
        ]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"清理了 {len(expired_keys)} 個過期緩存項")
    
    def get_stats(self) -> dict:
        """獲取緩存統計"""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "total_items": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests
        }
