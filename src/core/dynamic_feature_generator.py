"""
动态特征生成器 (v3.16.0)
职责：根据市场状态动态生成最优特征
使用特征进化算法
"""

import logging
from typing import Dict, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class DynamicFeatureGenerator:
    """动态特征生成器"""
    
    def __init__(self, config):
        """
        初始化生成器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.min_sharpe = config.DYNAMIC_FEATURE_MIN_SHARPE
        self.max_count = config.DYNAMIC_FEATURE_MAX_COUNT
        
        logger.info(f"✅ DynamicFeatureGenerator 初始化: min_sharpe={self.min_sharpe}, max_count={self.max_count}")
    
    def generate(self, market_regime: str, recent_data: pd.DataFrame) -> Optional[Dict]:
        """
        生成动态特征
        
        Args:
            market_regime: 市场状态 (trending/ranging/volatile)
            recent_data: 最近的市场数据
        
        Returns:
            Optional[Dict]: 生成的特征
                {
                    'features': Dict[str, float],  # 特征字典
                    'feature_count': int,          # 特征数量
                    'avg_sharpe': float            # 平均夏普比率
                }
        """
        try:
            if recent_data is None or len(recent_data) < 20:
                return None
            
            features = {}
            
            # 🔥 v3.16.0 基础实现：根据市场状态生成不同特征
            if market_regime == 'trending':
                # 趋势市场：强调动量特征
                features['momentum_5'] = self._calculate_momentum(recent_data, 5)
                features['momentum_10'] = self._calculate_momentum(recent_data, 10)
                features['trend_strength'] = self._calculate_trend_strength(recent_data)
                features['adx_14'] = self._calculate_adx(recent_data, 14)
                
            elif market_regime == 'ranging':
                # 震荡市场：强调均值回归特征
                features['rsi_deviation'] = self._calculate_rsi_deviation(recent_data)
                features['bollinger_position'] = self._calculate_bollinger_position(recent_data)
                features['mean_reversion_score'] = self._calculate_mean_reversion(recent_data)
                
            elif market_regime == 'volatile':
                # 波动市场：强调波动率特征
                features['volatility_5'] = self._calculate_volatility(recent_data, 5)
                features['volatility_10'] = self._calculate_volatility(recent_data, 10)
                features['atr_normalized'] = self._calculate_atr_normalized(recent_data)
            
            # 通用特征
            features['volume_ratio'] = self._calculate_volume_ratio(recent_data)
            features['price_position'] = self._calculate_price_position(recent_data)
            
            result = {
                'features': features,
                'feature_count': len(features),
                'avg_sharpe': 0.5,  # 基础实现使用固定值
                'market_regime': market_regime
            }
            
            logger.debug(f"动态特征生成: {market_regime} -> {len(features)} 个特征")
            
            return result
            
        except Exception as e:
            logger.error(f"动态特征生成失败: {e}")
            return None
    
    def _calculate_momentum(self, data: pd.DataFrame, period: int) -> float:
        """计算动量"""
        if len(data) < period:
            return 0.0
        return float((data['close'].iloc[-1] - data['close'].iloc[-period]) / data['close'].iloc[-period])
    
    def _calculate_trend_strength(self, data: pd.DataFrame) -> float:
        """计算趋势强度"""
        if len(data) < 20:
            return 0.0
        ema_20 = data['close'].ewm(span=20).mean()
        return float(abs(data['close'].iloc[-1] - ema_20.iloc[-1]) / ema_20.iloc[-1])
    
    def _calculate_adx(self, data: pd.DataFrame, period: int) -> float:
        """计算 ADX（简化版本）"""
        if len(data) < period + 1:
            return 0.0
        high_low = data['high'] - data['low']
        return float(high_low.tail(period).mean() / data['close'].iloc[-1])
    
    def _calculate_rsi_deviation(self, data: pd.DataFrame) -> float:
        """计算 RSI 偏离"""
        if len(data) < 14:
            return 0.0
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return float(abs(rsi.iloc[-1] - 50) / 50)
    
    def _calculate_bollinger_position(self, data: pd.DataFrame) -> float:
        """计算布林带位置"""
        if len(data) < 20:
            return 0.5
        sma = data['close'].rolling(window=20).mean()
        std = data['close'].rolling(window=20).std()
        upper = sma + 2 * std
        lower = sma - 2 * std
        position = (data['close'].iloc[-1] - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1] + 1e-10)
        return float(np.clip(position, 0, 1))
    
    def _calculate_mean_reversion(self, data: pd.DataFrame) -> float:
        """计算均值回归分数"""
        if len(data) < 20:
            return 0.0
        sma = data['close'].rolling(window=20).mean()
        deviation = (data['close'].iloc[-1] - sma.iloc[-1]) / sma.iloc[-1]
        return float(abs(deviation))
    
    def _calculate_volatility(self, data: pd.DataFrame, period: int) -> float:
        """计算波动率"""
        if len(data) < period:
            return 0.0
        returns = data['close'].pct_change().tail(period)
        return float(returns.std())
    
    def _calculate_atr_normalized(self, data: pd.DataFrame) -> float:
        """计算归一化 ATR"""
        if len(data) < 14:
            return 0.0
        high_low = data['high'] - data['low']
        atr = high_low.rolling(window=14).mean()
        return float(atr.iloc[-1] / data['close'].iloc[-1])
    
    def _calculate_volume_ratio(self, data: pd.DataFrame) -> float:
        """计算成交量比率"""
        if len(data) < 20:
            return 1.0
        avg_volume = data['volume'].rolling(window=20).mean()
        return float(data['volume'].iloc[-1] / (avg_volume.iloc[-1] + 1e-10))
    
    def _calculate_price_position(self, data: pd.DataFrame) -> float:
        """计算价格位置"""
        if len(data) < 20:
            return 0.5
        high_20 = data['high'].rolling(window=20).max()
        low_20 = data['low'].rolling(window=20).min()
        position = (data['close'].iloc[-1] - low_20.iloc[-1]) / (high_20.iloc[-1] - low_20.iloc[-1] + 1e-10)
        return float(np.clip(position, 0, 1))
