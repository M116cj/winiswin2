"""
RedisManager v1.0 - High-Performance Async Redis Caching Layer
職責：為高頻查詢提供毫秒級緩存（Trade Counts、Daily Stats）

🔥 Performance Benefits:
- PostgreSQL查詢: 30-60ms (with indices)
- Redis查詢: 1-3ms (30-60x faster)
- Ideal for: Trade counts, daily stats, win rates
"""

import asyncio
import os
from typing import Optional, Any
from src.utils.logger_factory import get_logger

logger = get_logger(__name__)

# Lazy import redis (only if REDIS_URL is set)
try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    aioredis = None


class RedisManager:
    """
    異步Redis管理器（v1.0）
    
    特性：
    - ✅ 完全異步（非阻塞）
    - ✅ 自動連接重試
    - ✅ TTL支持（防止數據陳舊）
    - ✅ JSON序列化（使用orjson）
    - ✅ 優雅降級（Redis不可用時不崩潰）
    
    使用示例：
    ```python
    redis_mgr = RedisManager()
    await redis_mgr.connect()
    
    # 設置緩存（5秒TTL）
    await redis_mgr.set("trade_count", 150, ttl=5)
    
    # 獲取緩存
    count = await redis_mgr.get("trade_count")
    
    # 清理
    await redis_mgr.close()
    ```
    """
    
    def __init__(self):
        """初始化Redis管理器"""
        self.redis_url = os.environ.get('REDIS_URL')
        self.redis_client: Optional[aioredis.Redis] = None
        self.enabled = False
        self._connected = False
        
        # 統計信息
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'errors': 0
        }
        
        if not _REDIS_AVAILABLE:
            logger.info("ℹ️  Redis未安裝（可選功能）- 使用純PostgreSQL模式")
        elif not self.redis_url:
            logger.info("ℹ️  REDIS_URL未設置（可選功能）- Redis緩存禁用")
        else:
            self.enabled = True
            logger.info(f"✅ Redis緩存已啟用: {self.redis_url[:30]}...")
    
    async def connect(self):
        """建立Redis連接（自動重試）"""
        if not self.enabled or self._connected:
            return
        
        try:
            # 🔥 CRITICAL FIX: from_url returns Redis instance (not awaitable)
            self.redis_client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=3.0,  # 3秒超時
                socket_connect_timeout=3.0,
                retry_on_timeout=True,
                max_connections=10  # 連接池
            )
            
            # 測試連接（async operation)
            await self.redis_client.ping()
            self._connected = True
            
            logger.info("✅ Redis連接成功")
            
        except Exception as e:
            logger.error(f"❌ Redis連接失敗: {e}")
            logger.warning("⚠️  降級到純PostgreSQL模式（無緩存）")
            self.enabled = False
            self.redis_client = None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = 300
    ) -> bool:
        """
        設置緩存值（帶TTL）
        
        Args:
            key: 緩存鍵
            value: 緩存值（自動JSON序列化）
            ttl: 過期時間（秒），預設5分鐘
            
        Returns:
            是否成功
        """
        if not self.enabled or not self._connected:
            return False
        
        try:
            # 🔥 使用orjson進行高性能序列化
            try:
                import orjson
                serialized = orjson.dumps(value).decode('utf-8')
            except ImportError:
                # Fallback to standard json
                import json
                serialized = json.dumps(value)
            
            # 設置值（帶TTL）
            await self.redis_client.setex(
                name=key,
                time=ttl,
                value=serialized
            )
            
            self.stats['sets'] += 1
            logger.debug(f"✅ Redis SET: {key} (TTL={ttl}s)")
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.warning(f"⚠️  Redis SET失敗: {key} - {e}")
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """
        獲取緩存值（自動JSON反序列化）
        
        Args:
            key: 緩存鍵
            
        Returns:
            緩存值（如果存在），否則None
        """
        if not self.enabled or not self._connected:
            return None
        
        try:
            value = await self.redis_client.get(key)
            
            if value is None:
                self.stats['misses'] += 1
                logger.debug(f"❌ Redis MISS: {key}")
                return None
            
            # 🔥 使用orjson進行高性能反序列化
            try:
                import orjson
                deserialized = orjson.loads(value)
            except ImportError:
                # Fallback to standard json
                import json
                deserialized = json.loads(value)
            
            self.stats['hits'] += 1
            logger.debug(f"✅ Redis HIT: {key}")
            return deserialized
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.warning(f"⚠️  Redis GET失敗: {key} - {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """
        刪除緩存鍵
        
        Args:
            key: 緩存鍵
            
        Returns:
            是否成功
        """
        if not self.enabled or not self._connected:
            return False
        
        try:
            await self.redis_client.delete(key)
            logger.debug(f"🗑️  Redis DELETE: {key}")
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.warning(f"⚠️  Redis DELETE失敗: {key} - {e}")
            return False
    
    async def close(self):
        """關閉Redis連接"""
        if self.redis_client and self._connected:
            try:
                await self.redis_client.close()
                await self.redis_client.connection_pool.disconnect()
                self._connected = False
                
                # 報告統計信息
                hit_rate = (
                    self.stats['hits'] / (self.stats['hits'] + self.stats['misses']) * 100
                    if (self.stats['hits'] + self.stats['misses']) > 0
                    else 0
                )
                
                logger.info("✅ Redis連接已關閉")
                logger.info(f"   📊 統計: Hits={self.stats['hits']}, "
                          f"Misses={self.stats['misses']}, "
                          f"Hit Rate={hit_rate:.1f}%, "
                          f"Sets={self.stats['sets']}, "
                          f"Errors={self.stats['errors']}")
                
            except Exception as e:
                logger.warning(f"⚠️  Redis關閉失敗: {e}")
    
    def get_stats(self) -> dict:
        """獲取緩存統計信息"""
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            **self.stats,
            'hit_rate': hit_rate,
            'total_requests': total,
            'enabled': self.enabled,
            'connected': self._connected
        }
    
    async def __aenter__(self):
        """異步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器出口"""
        await self.close()
