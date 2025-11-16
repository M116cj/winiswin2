"""
🚀 v4.6.0: 资源池化系统
职责：复用常用对象，减少GC压力和创建开销

性能目标：
- 减少对象创建开销 50%+
- 减少GC压力 30%+
- 适用场景：高频创建的小对象
"""

import logging
from typing import Any, Callable, Generic, TypeVar, Optional, List
from collections import deque
from threading import Lock
import time

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ObjectPool(Generic[T]):
    """
    通用对象池
    
    功能：
    1. 对象复用（减少GC压力）
    2. 自动扩容（需求大时）
    3. 定期清理（避免内存泄漏）
    """
    
    def __init__(
        self,
        factory: Callable[[], T],
        reset_func: Optional[Callable[[T], None]] = None,
        max_size: int = 100,
        initial_size: int = 10,
        pool_name: str = "GenericPool"
    ):
        """
        初始化对象池
        
        Args:
            factory: 对象工厂函数（如何创建新对象）
            reset_func: 对象重置函数（归还前如何清理）
            max_size: 池最大容量
            initial_size: 初始预创建对象数
            pool_name: 池名称（用于日志）
        """
        self.factory = factory
        self.reset_func = reset_func
        self.max_size = max_size
        self.pool_name = pool_name
        
        # 线程安全的双端队列
        self._available: deque = deque(maxlen=max_size)
        self._lock = Lock()
        
        # 统计信息
        self.stats = {
            'created': 0,
            'acquired': 0,
            'released': 0,
            'reused': 0,
            'discarded': 0
        }
        
        # 预创建对象
        for _ in range(initial_size):
            try:
                obj = self.factory()
                self._available.append(obj)
                self.stats['created'] += 1
            except Exception as e:
                logger.error(f"❌ {pool_name}预创建对象失败: {e}")
        
        logger.info(f"✅ 对象池已创建: {pool_name} (初始: {initial_size}, 最大: {max_size})")
    
    def acquire(self) -> T:
        """
        获取对象（从池中取出或创建新对象）
        
        Returns:
            可用对象
        """
        with self._lock:
            if self._available:
                obj = self._available.pop()
                self.stats['acquired'] += 1
                self.stats['reused'] += 1
                return obj
            else:
                obj = self.factory()
                self.stats['created'] += 1
                self.stats['acquired'] += 1
                return obj
    
    def release(self, obj: T) -> None:
        """
        归还对象到池中
        
        Args:
            obj: 要归还的对象
        """
        if obj is None:
            return
        
        with self._lock:
            # 重置对象状态
            if self.reset_func:
                try:
                    self.reset_func(obj)
                except Exception as e:
                    logger.warning(f"⚠️ {self.pool_name}对象重置失败: {e}")
                    self.stats['discarded'] += 1
                    return
            
            # 检查池容量
            if len(self._available) < self.max_size:
                self._available.append(obj)
                self.stats['released'] += 1
            else:
                self.stats['discarded'] += 1
    
    def get_stats(self) -> dict:
        """获取池统计信息"""
        with self._lock:
            return {
                **self.stats,
                'available': len(self._available),
                'reuse_rate': self.stats['reused'] / max(1, self.stats['acquired'])
            }
    
    def clear(self) -> None:
        """清空池（释放所有对象）"""
        with self._lock:
            self._available.clear()
            logger.info(f"🧹 {self.pool_name}已清空")


class FeatureDictPool:
    """
    特征字典池（用于ML特征）
    
    复用12个ICT/SMC特征的字典，避免频繁创建
    """
    
    def __init__(self, max_size: int = 50):
        from src.ml.feature_schema import CANONICAL_FEATURE_NAMES, FEATURE_DEFAULTS
        
        def create_feature_dict():
            return {name: FEATURE_DEFAULTS.get(name, 0.0) for name in CANONICAL_FEATURE_NAMES}
        
        def reset_feature_dict(d: dict):
            for key in d:
                d[key] = FEATURE_DEFAULTS.get(key, 0.0)
        
        self.pool = ObjectPool(
            factory=create_feature_dict,
            reset_func=reset_feature_dict,
            max_size=max_size,
            initial_size=10,
            pool_name="FeatureDictPool"
        )
    
    def acquire(self) -> dict:
        """获取特征字典"""
        return self.pool.acquire()
    
    def release(self, feature_dict: dict) -> None:
        """归还特征字典"""
        self.pool.release(feature_dict)
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.pool.get_stats()


class ListPool:
    """
    列表池（用于批量操作）
    
    复用列表对象，避免频繁创建
    """
    
    def __init__(self, max_size: int = 100):
        def create_list():
            return []
        
        def reset_list(lst: list):
            lst.clear()
        
        self.pool = ObjectPool(
            factory=create_list,
            reset_func=reset_list,
            max_size=max_size,
            initial_size=20,
            pool_name="ListPool"
        )
    
    def acquire(self) -> list:
        """获取列表"""
        return self.pool.acquire()
    
    def release(self, lst: list) -> None:
        """归还列表"""
        self.pool.release(lst)
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.pool.get_stats()


class GlobalResourcePools:
    """
    全局资源池管理器
    
    集中管理所有资源池
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if GlobalResourcePools._initialized:
            return
        
        # 创建各类资源池
        self.feature_dict_pool = FeatureDictPool(max_size=50)
        self.list_pool = ListPool(max_size=100)
        
        GlobalResourcePools._initialized = True
        logger.info("=" * 60)
        logger.info("✅ 全局资源池已初始化 (v4.6.0)")
        logger.info("   📦 FeatureDictPool: 50个槽位")
        logger.info("   📦 ListPool: 100个槽位")
        logger.info("=" * 60)
    
    def get_all_stats(self) -> dict:
        """获取所有池的统计信息"""
        return {
            'feature_dict_pool': self.feature_dict_pool.get_stats(),
            'list_pool': self.list_pool.get_stats()
        }
    
    def log_stats(self) -> None:
        """记录所有池的统计信息"""
        stats = self.get_all_stats()
        logger.info("📊 资源池统计:")
        for pool_name, pool_stats in stats.items():
            reuse_rate = pool_stats.get('reuse_rate', 0) * 100
            logger.info(
                f"   {pool_name}: "
                f"复用率={reuse_rate:.1f}%, "
                f"可用={pool_stats.get('available', 0)}, "
                f"已创建={pool_stats.get('created', 0)}"
            )


# 全局单例
_global_pools = None


def get_global_pools() -> GlobalResourcePools:
    """获取全局资源池管理器（单例）"""
    global _global_pools
    if _global_pools is None:
        _global_pools = GlobalResourcePools()
    return _global_pools
