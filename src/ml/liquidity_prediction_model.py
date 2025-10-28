"""
流动性预测模型
预测流动性聚集点（订单簇集）
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    TF_AVAILABLE = True
except ImportError:
    logger.warning("TensorFlow not available, LiquidityPredictionModel will use fallback mode")
    TF_AVAILABLE = False


class LiquidityPredictionModel:
    """流动性预测模型"""
    
    def __init__(self, sequence_length: int = 20):
        self.sequence_length = sequence_length
        self.model = None
        
        if TF_AVAILABLE:
            self.model = self._build_model()
        else:
            logger.warning("使用简化版流动性预测（TensorFlow未安装）")
    
    def _build_model(self):
        """构建LSTM流动性预测模型"""
        if not TF_AVAILABLE:
            return None
            
        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=(self.sequence_length, 5)),
            Dropout(0.2),
            LSTM(32, return_sequences=False),
            Dropout(0.2),
            Dense(16, activation='relu'),
            Dense(2, activation='linear')
        ])
        return model
    
    def predict_liquidity(self, symbol: str, recent_data: pd.DataFrame) -> Dict[str, Any]:
        """
        预测流动性聚集点
        
        Args:
            symbol: 交易对符号
            recent_data: 最近的K线数据
            
        Returns:
            流动性预测结果
        """
        if len(recent_data) < self.sequence_length:
            return self._get_default_prediction()
        
        if TF_AVAILABLE and self.model is not None:
            features = self._prepare_features(recent_data)
            prediction = self.model.predict(features.reshape(1, -1, 5), verbose=0)
            
            return {
                'buy_liquidity_price': float(prediction[0][0]),
                'sell_liquidity_price': float(prediction[0][1]),
                'confidence': 0.5
            }
        else:
            return self._fallback_predict(recent_data)
    
    def _prepare_features(self, data: pd.DataFrame) -> np.ndarray:
        """准备LSTM输入特征"""
        features = []
        
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col in data.columns:
                features.append(data[col].values[-self.sequence_length:])
            else:
                features.append(np.zeros(self.sequence_length))
        
        return np.array(features).T
    
    def _fallback_predict(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        简化版流动性预测（当TensorFlow不可用时）
        基于价格波动和成交量分析
        """
        if 'close' not in data.columns:
            return self._get_default_prediction()
        
        close = data['close'].values
        high = data['high'].values if 'high' in data.columns else close
        low = data['low'].values if 'low' in data.columns else close
        volume = data['volume'].values if 'volume' in data.columns else np.ones_like(close)
        
        recent_close = close[-1]
        atr = np.mean(high[-10:] - low[-10:]) if len(close) > 10 else (np.max(close) - np.min(close))
        
        volume_profile = np.zeros_like(close)
        for i in range(len(close)):
            volume_profile[i] = volume[i] * (high[i] - low[i])
        
        high_volume_idx = np.argmax(volume_profile)
        liquidity_level = close[high_volume_idx]
        
        return {
            'buy_liquidity_price': liquidity_level - atr,
            'sell_liquidity_price': liquidity_level + atr,
            'confidence': 0.5
        }
    
    def _get_default_prediction(self) -> Dict[str, Any]:
        """获取默认预测"""
        return {
            'buy_liquidity_price': 0,
            'sell_liquidity_price': 0,
            'confidence': 0.0
        }
    
    def train(self, price_sequences: np.ndarray, liquidity_targets: np.ndarray, epochs: int = 10):
        """
        训练流动性预测模型
        
        Args:
            price_sequences: 价格序列批次
            liquidity_targets: 流动性目标批次
            epochs: 训练轮数
        """
        if not TF_AVAILABLE:
            logger.warning("TensorFlow未安装，跳过训练")
            return
            
        self.model.compile(optimizer='adam', loss='mse')
        self.model.fit(price_sequences, liquidity_targets, epochs=epochs, verbose=0)
        
        logger.info(f"流动性预测模型训练完成 ({epochs} epochs)")
    
    def update_incremental(self, symbol: str, recent_data: pd.DataFrame, actual_liquidity: Optional[Dict] = None):
        """
        增量学习：基于实际流动性位置更新模型
        
        Args:
            symbol: 交易对符号
            recent_data: 最近的K线数据
            actual_liquidity: 实际观察到的流动性位置 (可选)
        """
        if not TF_AVAILABLE or self.model is None or len(recent_data) < self.sequence_length:
            return
        
        try:
            features = self._prepare_features(recent_data)
            
            if actual_liquidity:
                target = np.array([[
                    actual_liquidity.get('buy_liquidity_price', 0),
                    actual_liquidity.get('sell_liquidity_price', 0)
                ]], dtype=np.float32)
            else:
                prediction = self._fallback_predict(recent_data)
                target = np.array([[
                    prediction['buy_liquidity_price'],
                    prediction['sell_liquidity_price']
                ]], dtype=np.float32)
            
            self.model.compile(optimizer='adam', loss='mse')
            self.model.fit(
                features.reshape(1, -1, 5),
                target,
                epochs=1,
                verbose=0
            )
            
            logger.debug(f"增量更新：流动性预测模型 {symbol}")
            
        except Exception as e:
            logger.debug(f"增量学习失败: {e}")
