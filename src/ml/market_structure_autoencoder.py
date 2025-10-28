"""
市场结构自动编码器
使用无监督学习从价格序列中学习市场结构
"""

import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import Conv1D, Dense, GlobalMaxPooling1D
    TF_AVAILABLE = True
except ImportError:
    logger.warning("TensorFlow not available, MarketStructureAutoencoder will use fallback mode")
    TF_AVAILABLE = False


class MarketStructureAutoencoder:
    """市场结构自动编码器"""
    
    def __init__(self, structure_dim: int = 16):
        self.structure_dim = structure_dim
        self.encoder = None
        self.decoder = None
        
        if TF_AVAILABLE:
            self.encoder = self._build_encoder()
            self.decoder = self._build_decoder()
        else:
            logger.warning("使用简化版市场结构分析（TensorFlow未安装）")
    
    def _build_encoder(self):
        """编码器：压缩价格序列到市场结构向量"""
        if not TF_AVAILABLE:
            return None
        
        from tensorflow.keras.layers import Input
        from tensorflow.keras.models import Model
        
        inputs = Input(shape=(50, 1))
        x = Conv1D(64, 5, activation='relu')(inputs)
        x = Conv1D(32, 3, activation='relu')(x)
        x = GlobalMaxPooling1D()(x)
        outputs = Dense(self.structure_dim, activation='tanh')(x)
        
        model = Model(inputs=inputs, outputs=outputs)
        return model
    
    def _build_decoder(self):
        """解码器：从市场结构向量重建价格序列"""
        if not TF_AVAILABLE:
            return None
        
        from tensorflow.keras.layers import Input
        from tensorflow.keras.models import Model
        
        inputs = Input(shape=(self.structure_dim,))
        x = Dense(32, activation='relu')(inputs)
        outputs = Dense(50, activation='linear')(x)
        
        model = Model(inputs=inputs, outputs=outputs)
        return model
    
    def encode_structure(self, price_series: np.ndarray) -> np.ndarray:
        """
        将价格序列编码为市场结构向量
        
        Args:
            price_series: 价格序列 (shape: (n,))
            
        Returns:
            市场结构向量 (shape: (structure_dim,))
        """
        if len(price_series) < 50:
            price_series = np.pad(price_series, (0, 50 - len(price_series)), mode='edge')
        elif len(price_series) > 50:
            price_series = price_series[-50:]
        
        if TF_AVAILABLE and self.encoder is not None:
            normalized_prices = (price_series - np.mean(price_series)) / (np.std(price_series) + 1e-8)
            normalized_prices = normalized_prices.reshape(1, -1, 1)
            structure_vector = self.encoder.predict(normalized_prices, verbose=0)
            return structure_vector[0]
        else:
            return self._fallback_encode(price_series)
    
    def _fallback_encode(self, price_series: np.ndarray) -> np.ndarray:
        """
        简化版市场结构编码（当TensorFlow不可用时）
        使用统计特征作为市场结构表示
        """
        features = []
        
        normalized = (price_series - np.mean(price_series)) / (np.std(price_series) + 1e-8)
        
        features.append(np.mean(normalized))
        features.append(np.std(normalized))
        features.append(np.max(normalized))
        features.append(np.min(normalized))
        features.append(np.median(normalized))
        
        if len(normalized) > 1:
            features.append(normalized[-1] - normalized[0])
            features.append(np.corrcoef(np.arange(len(normalized)), normalized)[0, 1])
        else:
            features.extend([0, 0])
        
        features.extend([0] * (self.structure_dim - len(features)))
        
        return np.array(features[:self.structure_dim], dtype=np.float32)
    
    def train(self, price_data_batch: np.ndarray, epochs: int = 10):
        """
        训练自动编码器
        
        Args:
            price_data_batch: 价格数据批次 (shape: (batch_size, 50))
            epochs: 训练轮数
        """
        if not TF_AVAILABLE:
            logger.warning("TensorFlow未安装，跳过训练")
            return
            
        normalized_batch = []
        for price_series in price_data_batch:
            normalized = (price_series - np.mean(price_series)) / (np.std(price_series) + 1e-8)
            normalized_batch.append(normalized)
        
        X = np.array(normalized_batch).reshape(-1, 50, 1)
        
        full_model = Sequential([self.encoder, self.decoder])
        full_model.compile(optimizer='adam', loss='mse')
        full_model.fit(X, price_data_batch, epochs=epochs, verbose=0)
        
        logger.info(f"自动编码器训练完成 ({epochs} epochs)")
    
    def update_incremental(self, price_series: np.ndarray):
        """
        增量学习：基于新的价格序列更新模型
        
        Args:
            price_series: 新的价格序列
        """
        if not TF_AVAILABLE or len(price_series) < 50:
            return
        
        try:
            if len(price_series) > 50:
                price_series = price_series[-50:]
            
            normalized = (price_series - np.mean(price_series)) / (np.std(price_series) + 1e-8)
            X = normalized.reshape(1, 50, 1)
            
            full_model = Sequential([self.encoder, self.decoder])
            full_model.compile(optimizer='adam', loss='mse')
            full_model.fit(X, price_series.reshape(1, 50), epochs=1, verbose=0)
            
            logger.debug("增量更新：市场结构编码器")
            
        except Exception as e:
            logger.debug(f"增量学习失败: {e}")
