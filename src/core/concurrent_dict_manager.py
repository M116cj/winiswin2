"""
🔒 v3.23+ ConcurrentDictManager - 线程安全字典管理器

职责：
1. 提供线程安全的字典操作（get/set/delete/update/clear）
2. 支持同步和异步两种模式
3. 自动过期清理（TTL支持）
4. 统计信息收集
5. 集成ExceptionHandler异常处理

使用场景：
- KlineFeed.kline_cache - K线数据缓存
- PriceFeed.price_cache - 价格数据缓存
- AccountFeed.position_cache - 持仓数据缓存
- AdvancedWebSocketManager.data_buffers - WebSocket数据缓冲区
- 任何需要并发访问的字典

设计原则：
- 双模式锁：threading.RLock（同步）+ asyncio.Lock（异步）
- 最小锁粒度：只在关键区域持有锁
- 统一接口：同步和异步方法一致
- 性能优化：读写分离，减少锁竞争
"""

import logging
import asyncio
import threading
import time
from typing import Dict, Any, Optional, List, TypeVar, Generic, Callable
from dataclasses import dataclass
from datetime import datetime

from src.core.exception_handler import ExceptionHandler

logger = logging.getLogger(__name__)

K = TypeVar('K')  # Key type
V = TypeVar('V')  # Value type


@dataclass
class CacheEntry(Generic[V]):
    """缓存条目"""
    value: V
    timestamp: float
    expiry: Optional[float] = None  # None表示永不过期


class ConcurrentDictManager(Generic[K, V]):
    """
    线程安全字典管理器
    
    核心功能：
    1. 线程安全的字典操作（get/set/delete/update）
    2. 同步和异步双模式支持
    3. 自动过期清理（TTL）
    4. 读写统计
    5. 批量操作支持
    
    使用示例：
    ```python
    # 创建管理器
    cache = ConcurrentDictManager[str, Dict]()
    
    # 同步操作
    cache.set("BTCUSDT", {"price": 67000}, ttl=60)
    price_data = cache.get("BTCUSDT")
    
    # 异步操作
    await cache.set_async("ETHUSDT", {"price": 3500}, ttl=60)
    price_data = await cache.get_async("ETHUSDT")
    
    # 批量操作
    cache.update_many({"BTCUSDT": {...}, "ETHUSDT": {...}})
    ```
    """
    
    def __init__(
        self,
        name: str = "ConcurrentDict",
        enable_auto_cleanup: bool = True,
        cleanup_interval: int = 60,
        max_size: Optional[int] = None
    ):
        """
        初始化并发字典管理器
        
        Args:
            name: 管理器名称（用于日志）
            enable_auto_cleanup: 是否启用自动清理过期条目
            cleanup_interval: 自动清理间隔（秒）
            max_size: 最大条目数（None表示无限制）
        """
        self.name = name
        self.enable_auto_cleanup = enable_auto_cleanup
        self.cleanup_interval = cleanup_interval
        self.max_size = max_size
        
        # 核心数据结构
        self._data: Dict[K, CacheEntry[V]] = {}
        
        # 双模式锁
        self._sync_lock = threading.RLock()
        self._async_lock = asyncio.Lock()
        
        # 统计信息
        self.stats = {
            'total_reads': 0,
            'total_writes': 0,
            'total_deletes': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'expirations': 0,
            'evictions': 0,  # LRU驱逐
            'start_time': datetime.now()
        }
        
        # 自动清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.debug(
            f"✅ {self.name} 初始化完成 | "
            f"自动清理: {enable_auto_cleanup} | "
            f"最大条目: {max_size or '无限制'}"
        )
    
    # ==================== 同步方法 ====================
    
    @ExceptionHandler.log_exceptions
    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """
        线程安全获取值
        
        Args:
            key: 键
            default: 默认值
        
        Returns:
            值或默认值
        """
        with self._sync_lock:
            self.stats['total_reads'] += 1
            
            if key not in self._data:
                self.stats['cache_misses'] += 1
                return default
            
            entry = self._data[key]
            
            # 检查是否过期
            if entry.expiry and time.time() > entry.expiry:
                del self._data[key]
                self.stats['expirations'] += 1
                self.stats['cache_misses'] += 1
                return default
            
            # 🔥 v3.23+ 真正的LRU：更新访问时间
            entry.timestamp = time.time()
            
            self.stats['cache_hits'] += 1
            return entry.value
    
    @ExceptionHandler.log_exceptions
    def set(self, key: K, value: V, ttl: Optional[int] = None):
        """
        线程安全设置值
        
        Args:
            key: 键
            value: 值
            ttl: 存活时间（秒），None表示永不过期
        """
        with self._sync_lock:
            self.stats['total_writes'] += 1
            
            # 检查容量限制
            if self.max_size and len(self._data) >= self.max_size and key not in self._data:
                self._evict_oldest()
            
            now = time.time()
            expiry = (now + ttl) if ttl else None
            
            self._data[key] = CacheEntry(
                value=value,
                timestamp=now,
                expiry=expiry
            )
    
    @ExceptionHandler.log_exceptions
    def delete(self, key: K) -> bool:
        """
        线程安全删除键
        
        Args:
            key: 键
        
        Returns:
            是否成功删除
        """
        with self._sync_lock:
            self.stats['total_deletes'] += 1
            
            if key in self._data:
                del self._data[key]
                return True
            return False
    
    @ExceptionHandler.log_exceptions
    def update_many(self, items: Dict[K, V], ttl: Optional[int] = None):
        """
        批量更新多个键值对
        
        Args:
            items: 键值对字典
            ttl: 存活时间（秒）
        """
        with self._sync_lock:
            for key, value in items.items():
                self.set(key, value, ttl=ttl)
    
    @ExceptionHandler.log_exceptions
    def get_many(self, keys: List[K]) -> Dict[K, V]:
        """
        批量获取多个键的值
        
        Args:
            keys: 键列表
        
        Returns:
            存在的键值对
        """
        with self._sync_lock:
            result = {}
            for key in keys:
                value = self.get(key)
                if value is not None:
                    result[key] = value
            return result
    
    @ExceptionHandler.log_exceptions
    def clear(self):
        """清空所有数据"""
        with self._sync_lock:
            self._data.clear()
            logger.info(f"🗑️ {self.name} 已清空所有数据")
    
    @ExceptionHandler.log_exceptions
    def contains(self, key: K) -> bool:
        """
        检查键是否存在（且未过期）
        
        Args:
            key: 键
        
        Returns:
            是否存在
        """
        with self._sync_lock:
            if key not in self._data:
                return False
            
            entry = self._data[key]
            if entry.expiry and time.time() > entry.expiry:
                del self._data[key]
                self.stats['expirations'] += 1
                return False
            
            return True
    
    def size(self) -> int:
        """获取当前条目数"""
        with self._sync_lock:
            return len(self._data)
    
    def keys(self) -> List[K]:
        """获取所有键"""
        with self._sync_lock:
            return list(self._data.keys())
    
    def values(self) -> List[V]:
        """获取所有值"""
        with self._sync_lock:
            return [entry.value for entry in self._data.values()]
    
    def items(self) -> List[tuple[K, V]]:
        """获取所有键值对"""
        with self._sync_lock:
            return [(key, entry.value) for key, entry in self._data.items()]
    
    def __len__(self) -> int:
        """支持len()操作"""
        return self.size()
    
    def __contains__(self, key: K) -> bool:
        """支持in操作"""
        return self.contains(key)
    
    def __getitem__(self, key: K) -> V:
        """支持[]读取操作"""
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value
    
    def __setitem__(self, key: K, value: V):
        """支持[]赋值操作"""
        self.set(key, value)
    
    def __delitem__(self, key: K):
        """支持del操作"""
        if not self.delete(key):
            raise KeyError(key)
    
    # ==================== 异步方法 ====================
    
    @ExceptionHandler.log_exceptions
    async def get_async(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """
        异步获取值
        
        Args:
            key: 键
            default: 默认值
        
        Returns:
            值或默认值
        """
        async with self._async_lock:
            # 使用同步方法（已经在async锁保护下）
            return self.get(key, default)
    
    @ExceptionHandler.log_exceptions
    async def set_async(self, key: K, value: V, ttl: Optional[int] = None):
        """
        异步设置值
        
        Args:
            key: 键
            value: 值
            ttl: 存活时间（秒）
        """
        async with self._async_lock:
            self.set(key, value, ttl=ttl)
    
    @ExceptionHandler.log_exceptions
    async def delete_async(self, key: K) -> bool:
        """
        异步删除键
        
        Args:
            key: 键
        
        Returns:
            是否成功删除
        """
        async with self._async_lock:
            return self.delete(key)
    
    @ExceptionHandler.log_exceptions
    async def update_many_async(self, items: Dict[K, V], ttl: Optional[int] = None):
        """
        异步批量更新
        
        Args:
            items: 键值对字典
            ttl: 存活时间（秒）
        """
        async with self._async_lock:
            self.update_many(items, ttl=ttl)
    
    # ==================== 内部方法 ====================
    
    def _evict_oldest(self):
        """LRU驱逐最旧的条目"""
        if not self._data:
            return
        
        # 找到最旧的条目
        oldest_key = min(
            self._data.keys(),
            key=lambda k: self._data[k].timestamp
        )
        
        del self._data[oldest_key]
        self.stats['evictions'] += 1
        
        logger.debug(
            f"🔄 {self.name} LRU驱逐: {oldest_key} "
            f"(当前大小: {len(self._data)}/{self.max_size})"
        )
    
    @ExceptionHandler.log_exceptions
    def cleanup_expired(self) -> int:
        """
        清理过期条目
        
        Returns:
            清理的条目数
        """
        with self._sync_lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._data.items()
                if entry.expiry and now > entry.expiry
            ]
            
            for key in expired_keys:
                del self._data[key]
            
            if expired_keys:
                self.stats['expirations'] += len(expired_keys)
                logger.debug(
                    f"🗑️ {self.name} 清理了 {len(expired_keys)} 个过期条目"
                )
            
            return len(expired_keys)
    
    async def start_auto_cleanup(self):
        """启动自动清理任务"""
        if not self.enable_auto_cleanup:
            return
        
        if self._cleanup_task and not self._cleanup_task.done():
            logger.warning(f"⚠️ {self.name} 自动清理任务已在运行")
            return
        
        self._cleanup_task = asyncio.create_task(self._auto_cleanup_loop())
        logger.info(
            f"✅ {self.name} 自动清理任务已启动 "
            f"(间隔: {self.cleanup_interval}秒)"
        )
    
    async def stop_auto_cleanup(self):
        """停止自动清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info(f"✅ {self.name} 自动清理任务已停止")
    
    async def _auto_cleanup_loop(self):
        """自动清理循环"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ {self.name} 自动清理失败: {e}")
    
    # ==================== 统计方法 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计字典
        """
        with self._sync_lock:
            total_operations = (
                self.stats['total_reads'] +
                self.stats['total_writes'] +
                self.stats['total_deletes']
            )
            
            hit_rate = (
                self.stats['cache_hits'] / self.stats['total_reads'] * 100
                if self.stats['total_reads'] > 0 else 0
            )
            
            uptime_seconds = (datetime.now() - self.stats['start_time']).total_seconds()
            
            return {
                'name': self.name,
                'size': len(self._data),
                'max_size': self.max_size,
                'total_operations': total_operations,
                'reads': self.stats['total_reads'],
                'writes': self.stats['total_writes'],
                'deletes': self.stats['total_deletes'],
                'cache_hits': self.stats['cache_hits'],
                'cache_misses': self.stats['cache_misses'],
                'hit_rate': f"{hit_rate:.2f}%",
                'expirations': self.stats['expirations'],
                'evictions': self.stats['evictions'],
                'uptime_seconds': uptime_seconds
            }
    
    def reset_stats(self):
        """重置统计信息"""
        with self._sync_lock:
            self.stats = {
                'total_reads': 0,
                'total_writes': 0,
                'total_deletes': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'expirations': 0,
                'evictions': 0,
                'start_time': datetime.now()
            }
            logger.info(f"📊 {self.name} 统计已重置")
