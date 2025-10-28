"""
增量特征缓存
优化2：特征快取 + 增量计算
"""
import logging
import time
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class IncrementalFeatureCache:
    """增量特征缓存器"""
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.last_computed: Dict[str, int] = {}
    
    def get_or_compute_feature(self, symbol: str, feature_name: str, current_data, window_size: int):
        """
        增量计算特征
        
        Args:
            symbol: 交易对符号
            feature_name: 特征名称
            current_data: 当前数据
            window_size: 窗口大小
        
        Returns:
            计算后的特征值
        """
        cache_key = f"{symbol}_{feature_name}_{window_size}"
        
        if cache_key not in self.cache:
            # 首次计算
            self.cache[cache_key] = self._compute_feature(feature_name, current_data, window_size)
            self.last_computed[cache_key] = len(current_data)
            logger.debug(f"✨ 首次计算特征: {cache_key}")
            return self.cache[cache_key]
        
        # 增量更新
        new_data_points = len(current_data) - self.last_computed[cache_key]
        if new_data_points > 0:
            self.cache[cache_key] = self._incremental_update(
                feature_name, 
                self.cache[cache_key], 
                current_data[-new_data_points:],
                window_size
            )
            self.last_computed[cache_key] = len(current_data)
            logger.debug(f"🔄 增量更新特征: {cache_key} (+{new_data_points} 数据点)")
        
        return self.cache[cache_key]
    
    def _incremental_update(self, feature_name: str, old_value: float, new_data, window_size: int) -> float:
        """
        增量更新特征
        
        Args:
            feature_name: 特征名称
            old_value: 旧值
            new_data: 新数据
            window_size: 窗口大小
        
        Returns:
            更新后的特征值
        """
        if feature_name == "ema":
            # EMA 增量公式: new_ema = alpha * new_price + (1-alpha) * old_ema
            alpha = 2 / (window_size + 1)
            return alpha * new_data[-1] + (1 - alpha) * old_value
        
        elif feature_name == "atr":
            # ATR 增量计算
            tr = max(
                new_data[-1] - min(new_data[-2:-1] or [new_data[-1]]),
                max(new_data[-2:-1] or [new_data[-1]]) - new_data[-1],
                abs(new_data[-1] - (new_data[-2] if len(new_data) > 1 else new_data[-1]))
            )
            return (old_value * (window_size - 1) + tr) / window_size
        
        else:
            # 回退到完整计算
            logger.debug(f"⚠️ 特征 {feature_name} 不支持增量更新，使用完整计算")
            return self._compute_feature(feature_name, new_data, window_size)
    
    def _compute_feature(self, feature_name: str, data, window_size: int) -> float:
        """
        完整计算特征
        
        Args:
            feature_name: 特征名称
            data: 数据
            window_size: 窗口大小
        
        Returns:
            计算后的特征值
        """
        if len(data) == 0:
            return 0.0
        
        data_array = np.array(data)
        
        if feature_name == "ema":
            # 指数移动平均
            alpha = 2 / (window_size + 1)
            ema = data_array[0]
            for price in data_array[1:]:
                ema = alpha * price + (1 - alpha) * ema
            return ema
        
        elif feature_name == "sma":
            # 简单移动平均
            return np.mean(data_array[-window_size:])
        
        elif feature_name == "atr":
            # 平均真实范围
            if len(data_array) < 2:
                return 0.0
            
            high_low = np.abs(data_array[1:] - data_array[:-1])
            tr = np.mean(high_low[-window_size:])
            return tr
        
        elif feature_name == "rsi":
            # 相对强弱指数
            if len(data_array) < window_size + 1:
                return 50.0
            
            deltas = np.diff(data_array)
            gain = np.where(deltas > 0, deltas, 0)
            loss = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.mean(gain[-window_size:])
            avg_loss = np.mean(loss[-window_size:])
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        
        else:
            logger.warning(f"⚠️ 未知特征类型: {feature_name}")
            return 0.0
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        self.last_computed.clear()
        logger.info("🗑️ 特征缓存已清空")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        return {
            "cached_features": len(self.cache),
            "total_computations": sum(self.last_computed.values())
        }
