"""
ML 預測服務
職責：實時預測、信心度校準、預測結果集成
"""

import os
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any
import logging
from datetime import datetime, timedelta

from src.ml.model_trainer import XGBoostTrainer
from src.ml.data_processor import MLDataProcessor

logger = logging.getLogger(__name__)


class MLPredictor:
    """ML 預測服務"""
    
    def __init__(self):
        """初始化預測器"""
        self.trainer = XGBoostTrainer()
        self.data_processor = MLDataProcessor()
        self.model: Optional[Any] = None  # XGBoost模型
        self.is_ready = False
        self.last_training_samples = 0  # 上次訓練時的樣本數
        self.last_training_time: Optional[datetime] = None  # 上次訓練時間
        self.retrain_threshold = 50  # 累積50筆新交易後重訓練
        self.last_model_accuracy = 0.0  # 上次模型準確率
    
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
                # 記錄初始訓練時的樣本數和時間
                self.last_training_samples = self._load_last_training_samples()
                self.last_training_time = self._load_last_training_time()
                self.last_model_accuracy = self._load_last_model_accuracy()
                logger.info(
                    f"✅ ML 預測器已就緒 "
                    f"(訓練樣本: {self.last_training_samples}, "
                    f"準確率: {self.last_model_accuracy:.2%})"
                )
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
        從信號準備特徵向量（v3.3.7優化版 - 28個特徵）
        
        Args:
            signal: 交易信號
        
        Returns:
            Optional[list]: 特徵向量（28個）
        """
        try:
            indicators = signal.get('indicators', {})
            timeframes = signal.get('timeframes', {})
            
            # 編碼趨勢
            trend_encoding = {'bullish': 1, 'bearish': -1, 'neutral': 0}
            market_structure_encoding = {'bullish': 1, 'bearish': -1, 'neutral': 0}
            direction_encoding = {'LONG': 1, 'SHORT': -1}
            
            # 計算風險回報比
            entry_price = signal.get('entry_price', 0)
            stop_loss = signal.get('stop_loss', 0)
            take_profit = signal.get('take_profit', 0)
            
            risk_reward_ratio = (
                abs(take_profit - entry_price) / abs(entry_price - stop_loss)
                if entry_price != stop_loss else 2.0
            )
            
            # 基礎特徵（21個）
            basic_features = [
                signal.get('confidence', 0),  # confidence_score
                0,  # leverage - 將在風險管理器中確定
                0,  # position_value - 將在交易服務中確定
                0,  # hold_duration_hours - 未知
                risk_reward_ratio,  # risk_reward_ratio
                signal.get('order_blocks', 0),  # order_blocks_count
                signal.get('liquidity_zones', 0),  # liquidity_zones_count
                indicators.get('rsi', 0),  # rsi_entry
                indicators.get('macd', 0),  # macd_entry
                indicators.get('macd_signal', 0),  # macd_signal_entry
                indicators.get('macd_histogram', 0),  # macd_histogram_entry
                indicators.get('atr', 0),  # atr_entry
                indicators.get('bb_width_pct', 0),  # bb_width_pct
                indicators.get('volume_sma_ratio', 0),  # volume_sma_ratio
                indicators.get('price_vs_ema50', 0),  # price_vs_ema50
                indicators.get('price_vs_ema200', 0),  # price_vs_ema200
                trend_encoding.get(timeframes.get('1h', 'neutral'), 0),  # trend_1h_encoded
                trend_encoding.get(timeframes.get('15m', 'neutral'), 0),  # trend_15m_encoded
                trend_encoding.get(timeframes.get('5m', 'neutral'), 0),  # trend_5m_encoded
                market_structure_encoding.get(signal.get('market_structure', 'neutral'), 0),  # market_structure_encoded
                direction_encoding.get(signal.get('direction', 'LONG'), 1)  # direction_encoded
            ]
            
            # ✨ 增強特徵（7個 - 修復版）
            timestamp = signal.get('timestamp', datetime.now())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            hour_of_day = timestamp.hour
            day_of_week = timestamp.weekday()
            is_weekend = 1 if day_of_week in [5, 6] else 0
            
            # 止損止盈距離百分比
            stop_distance_pct = abs(stop_loss - entry_price) / entry_price if entry_price > 0 else 0
            tp_distance_pct = abs(take_profit - entry_price) / entry_price if entry_price > 0 else 0
            
            # 交互特徵
            confidence = signal.get('confidence', 0)
            rsi = indicators.get('rsi', 0)
            atr = indicators.get('atr', 0)
            bb_width = indicators.get('bb_width_pct', 0)
            trend_15m = trend_encoding.get(timeframes.get('15m', 'neutral'), 0)
            
            enhanced_features = [
                hour_of_day,  # hour_of_day
                day_of_week,  # day_of_week
                is_weekend,  # is_weekend
                stop_distance_pct,  # stop_distance_pct
                tp_distance_pct,  # tp_distance_pct
                confidence * 0,  # confidence_x_leverage (leverage未知，用0替代)
                rsi * trend_15m,  # rsi_x_trend
                atr * bb_width  # atr_x_bb_width
            ]
            
            # 組合成28個特徵
            features = basic_features + enhanced_features
            
            return features
            
        except Exception as e:
            logger.error(f"準備特徵失敗: {e}", exc_info=True)
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
    
    def check_and_retrain_if_needed(self) -> bool:
        """
        智能檢查是否需要重訓練（多觸發條件）
        
        觸發條件：
        1. 數量觸發：累積>=50筆新交易
        2. 時間觸發：距離上次訓練>=24小時
        3. 性能觸發：檢測到準確率下降（未來實現）
        
        Returns:
            bool: 是否成功重訓練
        """
        try:
            # 加載當前數據
            df = self.data_processor.load_training_data()
            current_samples = len(df)
            
            # 計算新增樣本數
            new_samples = current_samples - self.last_training_samples
            
            # ⚠️ 防禦：如果檢測到數據減少（例如數據清理），重置計數器
            if new_samples < 0:
                logger.warning(
                    f"檢測到數據減少: {current_samples} < {self.last_training_samples}，"
                    f"重置計數器"
                )
                self.last_training_samples = current_samples
                self.last_training_time = datetime.now()
                return False
            
            # 檢查各種觸發條件
            should_retrain = False
            trigger_reason = []
            
            # 1. 數量觸發
            if new_samples >= self.retrain_threshold:
                should_retrain = True
                trigger_reason.append(f"新增{new_samples}筆數據")
            
            # 2. 時間觸發（24小時）
            if self.last_training_time:
                time_since_training = datetime.now() - self.last_training_time
                if time_since_training > timedelta(hours=24) and new_samples >= 10:
                    should_retrain = True
                    trigger_reason.append(f"距離上次訓練{time_since_training.total_seconds()/3600:.1f}小時")
            
            if not should_retrain:
                logger.debug(
                    f"暫不重訓練: 新增{new_samples}/{self.retrain_threshold}筆 "
                    f"(總樣本: {current_samples})"
                )
                return False
            
            # 觸發重訓練
            logger.info(
                f"🔄 觸發重訓練 ({', '.join(trigger_reason)}), "
                f"總樣本: {current_samples}"
            )
            
            model, metrics = self.trainer.train()
            
            if model is not None:
                self.trainer.save_model(model, metrics)
                self.model = model
                self.last_training_samples = current_samples
                self.last_training_time = datetime.now()
                self.last_model_accuracy = metrics.get('accuracy', 0)
                
                logger.info(
                    f"✅ 模型重訓練完成！"
                    f"準確率: {metrics.get('accuracy', 0):.2%}, "
                    f"AUC: {metrics.get('roc_auc', 0):.3f}"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"重訓練檢查失敗: {e}")
            return False
    
    def _load_last_training_samples(self) -> int:
        """從metrics文件加載上次訓練的樣本數"""
        try:
            import json
            metrics_path = 'data/models/model_metrics.json'
            
            if os.path.exists(metrics_path):
                with open(metrics_path, 'r', encoding='utf-8') as f:
                    metrics = json.load(f)
                    samples = metrics.get('training_samples', 0)
                    if samples > 0:
                        return samples
            
            # 如果沒有metrics，使用當前數據量
            df = self.data_processor.load_training_data()
            return len(df)
            
        except Exception as e:
            logger.warning(f"加載訓練樣本數失敗: {e}")
            df = self.data_processor.load_training_data()
            return len(df)
    
    def _load_last_training_time(self) -> Optional[datetime]:
        """從metrics文件加載上次訓練時間"""
        try:
            import json
            metrics_path = 'data/models/model_metrics.json'
            
            if os.path.exists(metrics_path):
                with open(metrics_path, 'r', encoding='utf-8') as f:
                    metrics = json.load(f)
                    trained_at = metrics.get('trained_at')
                    if trained_at:
                        return datetime.fromisoformat(trained_at)
            
            return None
            
        except Exception as e:
            logger.warning(f"加載訓練時間失敗: {e}")
            return None
    
    def _load_last_model_accuracy(self) -> float:
        """從metrics文件加載上次模型準確率"""
        try:
            import json
            metrics_path = 'data/models/model_metrics.json'
            
            if os.path.exists(metrics_path):
                with open(metrics_path, 'r', encoding='utf-8') as f:
                    metrics = json.load(f)
                    return metrics.get('accuracy', 0.0)
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"加載模型準確率失敗: {e}")
            return 0.0
