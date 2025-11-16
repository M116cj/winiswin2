"""
Pragmatic Resource Pool for SelfLearningTrader v4.6.0 Phase 1A4
实用主义资源池：只池化昂贵对象，接受copy开销

Author: SelfLearningTrader Team
Version: 4.6.0
"""

import numpy as np
import threading
from typing import Dict, List, Any, Callable, Optional
import logging

from src.utils.resource_pool import ObjectPool

logger = logging.getLogger(__name__)


class PragmaticResourcePool:
    """
    实用主义资源池：针对性优化昂贵分配
    
    策略：
    - 只池化大型、昂贵的对象（numpy数组、大容器）
    - 接受最终结果需要copy的现实
    - 目标：减少中间计算的分配开销
    
    性能目标：15-20% GC压力减少
    """
    
    def __init__(
        self,
        array_pool_size: int = 20,
        feature_buffer_pool_size: int = 50,
        kline_buffer_pool_size: int = 30,
        enable_pooling: bool = True
    ):
        """
        初始化实用主义资源池
        
        Args:
            array_pool_size: numpy数组池大小
            feature_buffer_pool_size: 特征缓冲区池大小
            kline_buffer_pool_size: K线缓冲区池大小
            enable_pooling: 是否启用池化
        """
        self.enable_pooling = enable_pooling
        
        if not enable_pooling:
            logger.info("⚠️ PragmaticResourcePool已禁用")
            self.array_pool = None
            self.feature_buffer_pool = None
            self.kline_buffer_pool = None
            return
        
        # 池1：大型numpy数组（用于技术指标计算）
        self.array_pool = ObjectPool(
            factory=lambda: np.zeros(1000, dtype=np.float64),
            reset_func=lambda arr: arr.fill(0),
            max_size=array_pool_size,
            pool_name="NumpyArrayPool"
        )
        
        # 池2：特征计算缓冲区（dict）
        self.feature_buffer_pool = ObjectPool(
            factory=lambda: {},
            reset_func=lambda d: d.clear(),
            max_size=feature_buffer_pool_size,
            pool_name="FeatureBufferPool"
        )
        
        # 池3：K线数据处理缓冲区（list）
        self.kline_buffer_pool = ObjectPool(
            factory=lambda: [],
            reset_func=lambda lst: lst.clear(),
            max_size=kline_buffer_pool_size,
            pool_name="KlineBufferPool"
        )
        
        logger.info(
            f"✅ PragmaticResourcePool已初始化 (v4.6.0 Phase 1A4)\n"
            f"   NumpyArray池: {array_pool_size}个槽位\n"
            f"   FeatureBuffer池: {feature_buffer_pool_size}个槽位\n"
            f"   KlineBuffer池: {kline_buffer_pool_size}个槽位"
        )
    
    def compute_moving_average_optimized(
        self,
        price_data: np.ndarray,
        window: int = 20
    ) -> np.ndarray:
        """
        优化的移动平均计算（使用池化数组）
        
        Args:
            price_data: 价格数据数组
            window: 窗口大小
            
        Returns:
            移动平均数组
        """
        if not self.enable_pooling or self.array_pool is None:
            # 降级为标准计算
            return self._compute_ma_standard(price_data, window)
        
        # 从池中获取缓冲数组
        buffer = self.array_pool.acquire()
        
        try:
            data_len = len(price_data)
            
            # 使用池化数组进行中间计算
            if data_len <= len(buffer):
                # 计算累积和
                buffer[:data_len] = price_data
                cumsum = np.cumsum(buffer[:data_len])
                cumsum[window:] = cumsum[window:] - cumsum[:-window]
                
                # 结果需要copy（但中间计算已优化）
                result = cumsum[window - 1:] / window
                return result.copy()
            else:
                # 数据太大，降级为标准计算
                return self._compute_ma_standard(price_data, window)
                
        finally:
            self.array_pool.release(buffer)
    
    def _compute_ma_standard(self, price_data: np.ndarray, window: int) -> np.ndarray:
        """标准移动平均计算（无池化）"""
        cumsum = np.cumsum(price_data)
        cumsum[window:] = cumsum[window:] - cumsum[:-window]
        return cumsum[window - 1:] / window
    
    def compute_volatility_optimized(
        self,
        price_data: np.ndarray,
        window: int = 20
    ) -> float:
        """
        优化的波动率计算（使用池化数组）
        
        Args:
            price_data: 价格数据数组
            window: 窗口大小
            
        Returns:
            波动率值
        """
        if not self.enable_pooling or self.array_pool is None:
            return np.std(price_data[-window:]) if len(price_data) >= window else 0.0
        
        buffer = self.array_pool.acquire()
        
        try:
            data_len = min(len(price_data), window)
            buffer[:data_len] = price_data[-data_len:]
            
            # 使用池化数组计算标准差
            std_value = np.std(buffer[:data_len])
            return float(std_value)
            
        finally:
            self.array_pool.release(buffer)
    
    def build_features_optimized(
        self,
        market_data: Dict,
        feature_extractors: List[Callable]
    ) -> Dict:
        """
        优化的特征构建（使用池化字典）
        
        Args:
            market_data: 市场数据
            feature_extractors: 特征提取器列表
            
        Returns:
            特征字典（copy）
        """
        if not self.enable_pooling or self.feature_buffer_pool is None:
            # 降级为标准构建
            return self._build_features_standard(market_data, feature_extractors)
        
        # 从池中获取特征缓冲区
        feature_buffer = self.feature_buffer_pool.acquire()
        
        try:
            # 使用池化字典进行特征构建
            for extractor in feature_extractors:
                feature_buffer.update(extractor(market_data))
            
            # 返回copy（线程安全）
            return feature_buffer.copy()
            
        finally:
            self.feature_buffer_pool.release(feature_buffer)
    
    def _build_features_standard(
        self,
        market_data: Dict,
        feature_extractors: List[Callable]
    ) -> Dict:
        """标准特征构建（无池化）"""
        features = {}
        for extractor in feature_extractors:
            features.update(extractor(market_data))
        return features
    
    def process_klines_optimized(
        self,
        klines: List[Dict],
        processor: Callable
    ) -> List:
        """
        优化的K线数据处理（使用池化列表）
        
        Args:
            klines: K线数据列表
            processor: 处理函数
            
        Returns:
            处理结果列表（copy）
        """
        if not self.enable_pooling or self.kline_buffer_pool is None:
            return processor(klines)
        
        # 从池中获取K线缓冲区
        kline_buffer = self.kline_buffer_pool.acquire()
        
        try:
            # 使用池化列表进行处理
            result = processor(klines)
            
            # 如果结果是列表，copy后返回
            if isinstance(result, list):
                return result.copy()
            return result
            
        finally:
            self.kline_buffer_pool.release(kline_buffer)
    
    def get_pool_stats(self) -> Dict:
        """
        获取所有池的统计信息
        
        Returns:
            统计字典
        """
        if not self.enable_pooling:
            return {'enabled': False}
        
        stats = {'enabled': True, 'pools': {}}
        
        if self.array_pool:
            stats['pools']['array'] = self.array_pool.get_stats()
        if self.feature_buffer_pool:
            stats['pools']['feature_buffer'] = self.feature_buffer_pool.get_stats()
        if self.kline_buffer_pool:
            stats['pools']['kline_buffer'] = self.kline_buffer_pool.get_stats()
        
        return stats
    
    def log_stats(self) -> None:
        """记录池统计信息"""
        if not self.enable_pooling:
            logger.info("PragmaticResourcePool未启用")
            return
        
        stats = self.get_pool_stats()
        
        logger.info("📊 PragmaticResourcePool统计:")
        for pool_name, pool_stats in stats.get('pools', {}).items():
            logger.info(
                f"   {pool_name}: "
                f"获取={pool_stats['acquired']}, "
                f"复用={pool_stats['reused']}, "
                f"复用率={pool_stats['reuse_rate']*100:.1f}%"
            )
