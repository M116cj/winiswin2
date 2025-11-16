"""
Hybrid ML Processor for SelfLearningTrader v4.6.0 Phase 1A3
批量ML推理的实用主义实现：在流式架构中通过缓冲实现小批量处理

Author: SelfLearningTrader Team
Version: 4.6.0
"""

import time
import threading
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from collections import deque
import logging

logger = logging.getLogger(__name__)


class HybridMLProcessor:
    """
    混合ML处理器：在不改变流式架构的前提下实现批量推理优化
    
    核心策略：
    - 缓冲进来的预测请求
    - 达到batch_size或超时时触发批量处理
    - 将批量结果缓存，后续请求直接从缓存获取
    - 兼容现有的单个预测API
    
    性能目标：15-25% 推理速度提升
    """
    
    def __init__(
        self,
        model,
        batch_size: int = 10,
        max_buffer_time: float = 0.1,
        enable_batching: bool = True
    ):
        """
        初始化混合ML处理器
        
        Args:
            model: ML模型包装器（MLModelWrapper实例）
            batch_size: 触发批量处理的最小请求数
            max_buffer_time: 缓冲区最大等待时间（秒）
            enable_batching: 是否启用批量处理（可配置关闭）
        """
        self.model = model
        self.batch_size = batch_size
        self.max_buffer_time = max_buffer_time
        self.enable_batching = enable_batching
        
        # 特征缓冲区：[(symbol, features)]
        self.feature_buffer: List[Tuple[str, Dict]] = []
        
        # 预测缓存：symbol -> prediction
        self.prediction_cache: Dict[str, Any] = {}
        
        # 上次批量处理时间
        self.last_batch_time = time.time()
        
        # 线程锁（thread-safe）
        self._lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            'total_predictions': 0,
            'batch_predictions': 0,
            'single_predictions': 0,
            'cache_hits': 0,
            'batches_processed': 0
        }
        
        logger.info(
            f"✅ HybridMLProcessor已初始化 (v4.6.0 Phase 1A3)\n"
            f"   批量大小: {batch_size}\n"
            f"   缓冲超时: {max_buffer_time}s\n"
            f"   批量处理: {'启用' if enable_batching else '禁用'}"
        )
    
    def predict(self, symbol: str, features: Dict) -> Any:
        """
        主接口：兼容现有的单个预测API（简化设计）
        
        工作流程：
        1. 检查缓存（从之前的批量处理）
        2. 先加入缓冲区
        3. 如果缓冲区满或超时：批量处理所有请求
        4. 如果不满：保留在缓冲区，当前请求单个预测
        
        设计理念：
        - 批量处理：当缓冲区满时处理所有缓冲的请求
        - 单个预测：缓冲区未满时的当前请求
        - 缓冲请求会在下次批量时处理（延迟批量）
        
        Args:
            symbol: 交易对符号
            features: 特征字典
            
        Returns:
            预测结果
        """
        self.stats['total_predictions'] += 1
        
        # 如果批量处理被禁用，直接单个预测
        if not self.enable_batching:
            return self._predict_single(features)
        
        with self._lock:
            # 步骤1：检查缓存（从之前的批量处理）
            if symbol in self.prediction_cache:
                self.stats['cache_hits'] += 1
                prediction = self.prediction_cache.pop(symbol)
                logger.debug(f"🎯 缓存命中: {symbol}")
                return prediction
            
            # 步骤2：加入缓冲区（为将来的批量准备）
            buffer_entry = (symbol, features)
            self.feature_buffer.append(buffer_entry)
            
            # 步骤3：检查是否应触发批量处理
            should_process_batch = (
                len(self.feature_buffer) >= self.batch_size or
                (time.time() - self.last_batch_time) >= self.max_buffer_time
            )
            
            # 记录当前buffer位置（用于后续移除）
            current_buffer_len = len(self.feature_buffer)
        
        # 步骤4：决策分支
        if should_process_batch:
            # 路径A：触发批量处理（处理所有缓冲的请求）
            self._process_batch()
            
            # 从缓存获取结果
            with self._lock:
                if symbol in self.prediction_cache:
                    return self.prediction_cache.pop(symbol)
            
            # 降级（批量失败的情况）
            logger.warning(f"批量处理后未找到{symbol}的缓存，降级为单个预测")
            return self._predict_single(features)
        else:
            # 路径B：缓冲区未满，当前请求单个预测
            # 保留在缓冲区供后续批量处理
            return self._predict_single(features)
    
    def _process_batch(self) -> None:
        """
        处理缓冲区中的批量请求（同步方法）
        """
        with self._lock:
            if not self.feature_buffer:
                return
            
            # 复制缓冲区数据并清空
            symbols = [item[0] for item in self.feature_buffer]
            features_batch = [item[1] for item in self.feature_buffer]
            buffer_copy = self.feature_buffer.copy()
            self.feature_buffer.clear()
            self.last_batch_time = time.time()
        
        batch_size = len(symbols)
        logger.debug(f"🚀 批量处理: {batch_size}个预测请求")
        
        try:
            # 使用模型的批量预测方法
            if hasattr(self.model, 'predict_batch'):
                predictions = self.model.predict_batch(features_batch)
            else:
                # 降级：逐个预测
                logger.warning("模型不支持batch_predict，降级为逐个预测")
                predictions = [self.model.predict(feat) for feat in features_batch]
            
            # 将结果缓存
            with self._lock:
                for symbol, prediction in zip(symbols, predictions):
                    self.prediction_cache[symbol] = prediction
                
                self.stats['batch_predictions'] += batch_size
                self.stats['batches_processed'] += 1
            
            logger.debug(
                f"✅ 批量处理完成: {batch_size}个预测, "
                f"批量效率: {self.get_batch_efficiency():.1f}%"
            )
            
        except Exception as e:
            logger.error(f"❌ 批量处理失败，预测将降级为单个模式: {e}")
            # 失败时不缓存，调用者会自动降级到_predict_single
    
    def _predict_single(self, features: Dict) -> Any:
        """
        单个预测（降级模式）
        
        Args:
            features: 特征字典
            
        Returns:
            预测结果
        """
        self.stats['single_predictions'] += 1
        return self.model.predict(features)
    
    def flush(self) -> None:
        """
        强制处理缓冲区中的所有待处理请求并清空缓存
        
        应在每次市场扫描周期结束时调用，用于：
        1. 处理剩余的缓冲请求（批量优化）
        2. 清空预测缓存（防止下一周期使用过期特征）
        """
        with self._lock:
            buffer_size = len(self.feature_buffer)
        
        if buffer_size > 0:
            logger.debug(f"🔄 flush: 处理缓冲区中的{buffer_size}个待处理请求")
            self._process_batch()
        
        # 清空缓存（防止下一周期使用过期特征）
        with self._lock:
            cache_size = len(self.prediction_cache)
            if cache_size > 0:
                logger.debug(f"🧹 flush: 清空{cache_size}个缓存预测")
                self.prediction_cache.clear()
    
    def get_batch_efficiency(self) -> float:
        """
        计算批量处理效率（批量预测占比）
        
        Returns:
            批量预测占总预测的百分比
        """
        total = self.stats['total_predictions']
        if total == 0:
            return 0.0
        return (self.stats['batch_predictions'] / total) * 100
    
    def get_stats(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            统计字典
        """
        stats = self.stats.copy()
        batch_eff = self.get_batch_efficiency()
        cache_rate = (
            (self.stats['cache_hits'] / self.stats['total_predictions'] * 100)
            if self.stats['total_predictions'] > 0 else 0.0
        )
        # 添加额外字段（非int字段）
        result = dict(stats)
        result['batch_efficiency'] = batch_eff
        result['cache_hit_rate'] = cache_rate
        return result
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            'total_predictions': 0,
            'batch_predictions': 0,
            'single_predictions': 0,
            'cache_hits': 0,
            'batches_processed': 0
        }
        logger.info("📊 统计信息已重置")
    
    def log_stats(self) -> None:
        """记录当前统计信息"""
        stats = self.get_stats()
        logger.info(
            f"📊 HybridMLProcessor统计:\n"
            f"   总预测数: {stats['total_predictions']}\n"
            f"   批量预测: {stats['batch_predictions']} ({stats['batch_efficiency']:.1f}%)\n"
            f"   单个预测: {stats['single_predictions']}\n"
            f"   缓存命中: {stats['cache_hits']} ({stats['cache_hit_rate']:.1f}%)\n"
            f"   批次数: {stats['batches_processed']}"
        )
