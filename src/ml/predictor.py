"""
ML 預測服務
職責：實時預測、信心度校準、預測結果集成
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
import logging

from src.ml.model_trainer import XGBoostTrainer
from src.ml.data_processor import MLDataProcessor

logger = logging.getLogger(__name__)


class MLPredictor:
    """ML 預測服務"""
    
    def __init__(self):
        """初始化預測器"""
        self.trainer = XGBoostTrainer()
        self.data_processor = MLDataProcessor()
        self.model = None
        self.is_ready = False
    
    def initialize(self) -> bool:
        """
        初始化預測器（加載模型）
        
        Returns:
            bool: 是否成功初始化
        """
        try:
            # 嘗試加載已有模型
            self.model = self.trainer.load_model()
            
            if self.model is None:
                logger.info("未找到已訓練模型，嘗試自動訓練...")
                
                # 如果有足夠數據，自動訓練
                success = self.trainer.auto_train_if_needed(min_samples=100)
                
                if success:
                    self.model = self.trainer.model
            
            if self.model is not None:
                self.is_ready = True
                logger.info("✅ ML 預測器已就緒")
                return True
            else:
                logger.warning("⚠️  ML 模型未就緒，將使用傳統策略")
                return False
                
        except Exception as e:
            logger.error(f"初始化 ML 預測器失敗: {e}")
            return False
    
    def predict(self, signal: Dict) -> Optional[Dict]:
        """
        預測信號的成功概率
        
        Args:
            signal: 交易信號
        
        Returns:
            Optional[Dict]: 預測結果
        """
        if not self.is_ready or self.model is None:
            return None
        
        try:
            # 準備特徵
            features = self._prepare_signal_features(signal)
            
            if features is None:
                return None
            
            # 預測
            proba = self.model.predict_proba([features])[0]
            prediction = self.model.predict([features])[0]
            
            result = {
                'predicted_class': int(prediction),
                'win_probability': float(proba[1]),
                'loss_probability': float(proba[0]),
                'ml_confidence': float(proba[1]) if prediction == 1 else float(proba[0])
            }
            
            logger.debug(f"ML 預測: {signal['symbol']} - 勝率 {result['win_probability']:.2%}")
            
            return result
            
        except Exception as e:
            logger.error(f"ML 預測失敗: {e}")
            return None
    
    def _prepare_signal_features(self, signal: Dict) -> Optional[list]:
        """
        從信號準備特徵向量
        
        Args:
            signal: 交易信號
        
        Returns:
            Optional[list]: 特徵向量
        """
        try:
            indicators = signal.get('indicators', {})
            timeframes = signal.get('timeframes', {})
            
            # 編碼趨勢
            trend_encoding = {'bullish': 1, 'bearish': -1, 'neutral': 0}
            market_structure_encoding = {'bullish': 1, 'bearish': -1, 'neutral': 0}
            direction_encoding = {'LONG': 1, 'SHORT': -1}
            
            features = [
                signal.get('confidence', 0),
                0,  # leverage - 將在風險管理器中確定
                0,  # position_value - 將在交易服務中確定
                0,  # hold_duration_hours - 未知
                abs(signal.get('take_profit', 0) - signal.get('entry_price', 0)) / 
                    abs(signal.get('entry_price', 0) - signal.get('stop_loss', 0)) 
                    if signal.get('entry_price', 0) != signal.get('stop_loss', 0) else 2.0,
                signal.get('order_blocks', 0),
                signal.get('liquidity_zones', 0),
                indicators.get('rsi', 0),
                indicators.get('macd', 0),
                indicators.get('macd_signal', 0),
                indicators.get('macd_histogram', 0),
                indicators.get('atr', 0),
                indicators.get('bb_width_pct', 0),
                indicators.get('volume_sma_ratio', 0),
                indicators.get('price_vs_ema50', 0),
                indicators.get('price_vs_ema200', 0),
                trend_encoding.get(timeframes.get('1h', 'neutral'), 0),
                trend_encoding.get(timeframes.get('15m', 'neutral'), 0),
                trend_encoding.get(timeframes.get('5m', 'neutral'), 0),
                market_structure_encoding.get(signal.get('market_structure', 'neutral'), 0),
                direction_encoding.get(signal.get('direction', 'LONG'), 1)
            ]
            
            return features
            
        except Exception as e:
            logger.error(f"準備特徵失敗: {e}")
            return None
    
    def calibrate_confidence(
        self,
        traditional_confidence: float,
        ml_prediction: Optional[Dict]
    ) -> float:
        """
        校準信心度（結合傳統策略和 ML 預測）
        
        Args:
            traditional_confidence: 傳統策略信心度
            ml_prediction: ML 預測結果
        
        Returns:
            float: 校準後的信心度
        """
        if ml_prediction is None or not self.is_ready:
            return traditional_confidence
        
        try:
            ml_confidence = ml_prediction.get('ml_confidence', 0.5)
            
            # 加權平均
            # 傳統策略權重: 60%
            # ML 預測權重: 40%
            calibrated = traditional_confidence * 0.6 + ml_confidence * 0.4
            
            return min(1.0, max(0.0, calibrated))
            
        except Exception as e:
            logger.error(f"校準信心度失敗: {e}")
            return traditional_confidence
