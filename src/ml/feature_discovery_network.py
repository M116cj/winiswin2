"""
特征发现网络
自动发现对当前市场状态最有效的特征
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

try:
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import Dense, Dropout
    TF_AVAILABLE = True
except ImportError:
    logger.warning("TensorFlow not available, FeatureDiscoveryNetwork will use fallback mode")
    TF_AVAILABLE = False


class FeatureDiscoveryNetwork:
    """特征发现网络"""
    
    def __init__(self, input_dim: int = 16, output_dim: int = 32):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.model = None
        
        if TF_AVAILABLE:
            self.model = self._build_model()
        else:
            logger.warning("使用简化版特征发现（TensorFlow未安装）")
    
    def _build_model(self):
        """构建特征发现模型"""
        if not TF_AVAILABLE:
            return None
            
        model = Sequential([
            Dense(64, activation='relu', input_shape=(self.input_dim,)),
            Dropout(0.3),
            Dense(128, activation='relu'),
            Dropout(0.3),
            Dense(self.output_dim, activation='tanh')
        ])
        return model
    
    def discover_features(self, market_structure: np.ndarray, recent_data: pd.DataFrame) -> np.ndarray:
        """
        发现当前市场状态下最有效的特征
        
        Args:
            market_structure: 市场结构向量
            recent_data: 最近的K线数据
            
        Returns:
            动态特征向量
        """
        if TF_AVAILABLE and self.model is not None:
            features = self.model.predict(market_structure.reshape(1, -1), verbose=0)
            return features[0]
        else:
            return self._fallback_discover(market_structure, recent_data)
    
    def _fallback_discover(self, market_structure: np.ndarray, recent_data: pd.DataFrame) -> np.ndarray:
        """
        简化版特征发现（当TensorFlow不可用时）
        基于技术指标生成特征
        """
        features = []
        
        features.extend(market_structure[:self.input_dim].tolist())
        
        if recent_data is not None and len(recent_data) > 0:
            if 'close' in recent_data.columns:
                close = recent_data['close'].values
                features.append(np.mean(close))
                features.append(np.std(close))
                
                if len(close) > 1:
                    returns = np.diff(close) / close[:-1]
                    features.append(np.mean(returns))
                    features.append(np.std(returns))
                else:
                    features.extend([0, 0])
            
            if 'volume' in recent_data.columns:
                volume = recent_data['volume'].values
                features.append(np.mean(volume))
                features.append(np.std(volume))
        
        while len(features) < self.output_dim:
            features.append(0)
        
        return np.array(features[:self.output_dim], dtype=np.float32)
    
    def train(self, market_structures: np.ndarray, target_features: np.ndarray, epochs: int = 10):
        """
        训练特征发现网络
        
        Args:
            market_structures: 市场结构向量批次
            target_features: 目标特征向量批次
            epochs: 训练轮数
        """
        if not TF_AVAILABLE:
            logger.warning("TensorFlow未安装，跳过训练")
            return
            
        self.model.compile(optimizer='adam', loss='mse')
        self.model.fit(market_structures, target_features, epochs=epochs, verbose=0)
        
        logger.info(f"特征发现网络训练完成 ({epochs} epochs)")
