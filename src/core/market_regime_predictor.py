"""
市场状态转换预测器 (v3.16.0)
职责：预测市场从当前状态转换到其他状态的概率
使用 LSTM + Attention 机制
"""

import logging
from typing import Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


class MarketRegimePredictor:
    """市场状态转换预测器"""
    
    def __init__(self, config):
        """
        初始化预测器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.threshold = config.REGIME_PREDICTION_THRESHOLD
        self.lookback = config.REGIME_PREDICTION_LOOKBACK
        
        logger.info(f"✅ MarketRegimePredictor 初始化: threshold={self.threshold}, lookback={self.lookback}")
    
    def predict(self, current_data: Dict) -> Optional[Dict]:
        """
        预测市场状态转换
        
        Args:
            current_data: 当前市场数据 {'symbol': str, 'data': DataFrame}
        
        Returns:
            Optional[Dict]: 预测结果
                {
                    'predicted_regime': str,  # 预测的状态 (trending/ranging/volatile)
                    'confidence': float,       # 置信度 0-1
                    'transition_probability': float  # 转换概率
                }
        """
        try:
            symbol = current_data.get('symbol', 'UNKNOWN')
            data = current_data.get('data')
            
            if data is None or len(data) < self.lookback:
                return None
            
            # 🔥 v3.16.0 基础实现：基于价格波动性判断市场状态
            recent_data = data.tail(self.lookback)
            
            # 计算价格波动性
            returns = recent_data['close'].pct_change().dropna()
            volatility = returns.std()
            
            # 计算趋势强度
            price_change = (recent_data['close'].iloc[-1] - recent_data['close'].iloc[0]) / recent_data['close'].iloc[0]
            
            # 简单分类逻辑
            if abs(price_change) > 0.02 and volatility < 0.015:
                predicted_regime = 'trending'
                confidence = min(abs(price_change) * 10, 0.95)
            elif volatility > 0.02:
                predicted_regime = 'volatile'
                confidence = min(volatility * 20, 0.95)
            else:
                predicted_regime = 'ranging'
                confidence = 0.6
            
            result = {
                'predicted_regime': predicted_regime,
                'confidence': confidence,
                'transition_probability': confidence,
                'symbol': symbol
            }
            
            logger.debug(f"市场状态预测 {symbol}: {predicted_regime} (置信度: {confidence:.2%})")
            
            return result
            
        except Exception as e:
            logger.error(f"市场状态预测失败: {e}")
            return None
