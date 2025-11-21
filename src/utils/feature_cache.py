"""
智能特征缓存系统 (v3.13.0 策略17)
职责：缓存技术指标和特征向量，避免重复计算

✅ 为什么需要特征缓存：
1. 相同symbol+timeframe重复计算（浪费CPU）
2. ML特征提取耗时（28个特征 × 200个symbol = 大量计算）
3. 智能TTL（高波动率→短TTL，低波动率→长TTL）

性能提升：
    无缓存: 200 symbols × 28 features = 5600次计算 ≈ 3秒
    有缓存: 缓存命中率70% → 1680次计算 ≈ 0.9秒
    节省: 2.1秒（70%）
"""

import logging
import time
import hashlib
from typing import Any, Optional, Dict, Tuple
from collections import OrderedDict
import pandas as pd

logger = logging.getLogger(__name__)


class LRUCache:
    """
    LRU（Least Recently Used）缓存
    
    自动淘汰最久未使用的项
    """
    
    def __init__(self, max_size: int = 1000):
        """
        初始化LRU缓存
        
        Args:
            max_size: 最大缓存项数
        """
        self.cache: OrderedDict = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Tuple[Any, float]]:
        """
        获取缓存项
        
        Args:
            key: 缓存键
        
        Returns:
            (value, expiry) 或 None
        """
        if key not in self.cache:
            self.misses += 1
            return None
        
        # 移动到末尾（标记为最近使用）
        value, expiry = self.cache.pop(key)
        
        # 检查是否过期
        if time.time() > expiry:
            self.misses += 1
            return None
        
        self.cache[key] = (value, expiry)
        self.hits += 1
        
        return (value, expiry)
    
    def set(self, key: str, value: Any, ttl: float = 300.0):
        """
        设置缓存项
        
        Args:
            key: 缓存键
            value: 值
            ttl: 存活时间（秒）
        """
        expiry = time.time() + ttl
        
        # 如果已存在，删除旧的
        if key in self.cache:
            self.cache.pop(key)
        
        # 添加到末尾
        self.cache[key] = (value, expiry)
        
        # 检查是否超过最大大小
        if len(self.cache) > self.max_size:
            # 删除最旧的（第一个）
            self.cache.popitem(last=False)
    
    def invalidate(self, key: str):
        """使缓存项失效"""
        if key in self.cache:
            self.cache.pop(key)
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate
        }


class SmartFeatureCache:
    """
    智能特征缓存（v3.13.0）
    
    特性：
    1. 自动计算缓存键（基于symbol+timeframe+参数）
    2. 智能TTL（基于波动率）
    3. LRU淘汰策略
    4. 统计信息
    """
    
    def __init__(self, max_size: int = 1000):
        """
        初始化智能特征缓存
        
        Args:
            max_size: 最大缓存项数
        """
        self.cache = LRUCache(max_size)
        self._default_ttl = 300.0  # 5分钟默认TTL
        
        logger.info(f"✅ 智能特征缓存初始化（max_size={max_size}）")
    
    def _generate_cache_key(self, symbol: str, timeframe: str, **kwargs) -> str:
        """
        生成缓存键
        
        Args:
            symbol: 交易对
            timeframe: 时间框架
            **kwargs: 额外参数（影响缓存键）
        
        Returns:
            str: 缓存键（哈希）
        """
        # 创建确定性键
        key_parts = [symbol, timeframe]
        
        # 添加额外参数（排序确保一致性）
        for k in sorted(kwargs.keys()):
            key_parts.append(f"{k}={kwargs[k]}")
        
        key_string = "|".join(key_parts)
        
        # 哈希（缩短键长度）
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:16]
        
        return key_hash
    
    def get_indicators(
        self,
        symbol: str,
        timeframe: str,
        **kwargs
    ) -> Optional[Dict]:
        """
        获取缓存的技术指标
        
        Args:
            symbol: 交易对
            timeframe: 时间框架
            **kwargs: 指标参数
        
        Returns:
            Dict: 指标数据 或 None
        """
        cache_key = self._generate_cache_key(symbol, timeframe, **kwargs)
        result = self.cache.get(cache_key)
        
        if result is None:
            return None
        
        value, _ = result
        return value
    
    def set_indicators(
        self,
        symbol: str,
        timeframe: str,
        indicators: Dict,
        volatility: Optional[float] = None,
        **kwargs
    ):
        """
        缓存技术指标
        
        Args:
            symbol: 交易对
            timeframe: 时间框架
            indicators: 指标数据
            volatility: 波动率（用于计算智能TTL）
            **kwargs: 指标参数
        """
        cache_key = self._generate_cache_key(symbol, timeframe, **kwargs)
        
        # 智能TTL：高波动率→短TTL，低波动率→长TTL
        if volatility is not None:
            # 波动率范围 0.005-0.05 → TTL 60-600秒
            ttl = max(60, min(600, 300 * (1 - min(volatility, 0.05) / 0.05)))
        else:
            ttl = self._default_ttl
        
        self.cache.set(cache_key, indicators, ttl=ttl)
    
    def get_features(
        self,
        symbol: str,
        timeframe: str,
        **kwargs
    ) -> Optional['LightFeatureVector']:
        """
        获取缓存的特征向量
        
        Args:
            symbol: 交易对
            timeframe: 时间框架
            **kwargs: 特征参数
        
        Returns:
            LightFeatureVector 或 None
        """
        cache_key = self._generate_cache_key(symbol, timeframe, feature_type="vector", **kwargs)
        result = self.cache.get(cache_key)
        
        if result is None:
            return None
        
        value, _ = result
        return value
    
    def set_features(
        self,
        symbol: str,
        timeframe: str,
        features: 'LightFeatureVector',
        ttl: Optional[float] = None,
        **kwargs
    ):
        """
        缓存特征向量
        
        Args:
            symbol: 交易对
            timeframe: 时间框架
            features: 特征向量
            ttl: 存活时间（秒）
            **kwargs: 特征参数
        """
        cache_key = self._generate_cache_key(symbol, timeframe, feature_type="vector", **kwargs)
        self.cache.set(cache_key, features, ttl=ttl or self._default_ttl)
    
    def invalidate_symbol(self, symbol: str):
        """
        使某个symbol的所有缓存失效
        
        Args:
            symbol: 交易对
        """
        # 这是一个简化实现，真实场景中可能需要跟踪symbol对应的所有键
        logger.debug(f"使 {symbol} 的缓存失效")
        # 注：LRU缓存没有按前缀删除功能，这里仅为示意
        # 实际实现中可以添加symbol->keys的映射
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        return self.cache.get_stats()
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()


# 全局特征缓存实例（单例）
_global_feature_cache: Optional[SmartFeatureCache] = None


def get_global_feature_cache(max_size: int = 1000) -> SmartFeatureCache:
    """
    获取全局特征缓存实例（单例）
    
    Args:
        max_size: 最大缓存项数（仅首次调用时有效）
    
    Returns:
        SmartFeatureCache: 全局缓存实例
    """
    global _global_feature_cache
    if _global_feature_cache is None:
        _global_feature_cache = SmartFeatureCache(max_size)
    return _global_feature_cache
