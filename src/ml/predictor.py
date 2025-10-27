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
    """
    ML 預測服務
    
    v3.9.1: 使用独立的binary分类模型用于实时预测
    - predictor_trainer: binary分类模型（快速预测，有predict_proba）
    - research_trainer: risk_adjusted回归模型（后台研究用）
    """
    
    def __init__(self):
        """初始化預測器"""
        # 🎯 v3.9.1: 使用独立的binary分类模型用于实时预测
        from src.ml.model_trainer import XGBoostTrainer as BaseTrainer
        from src.ml.target_optimizer import TargetOptimizer
        
        # 创建定制化的binary分类训练器（用于实时预测）
        self.trainer = BaseTrainer()
        # 重置为binary目标
        self.trainer.target_optimizer = TargetOptimizer(target_type='binary')
        
        # 🔒 v3.9.1: 使用独立的模型文件路径（避免与risk_adjusted模型冲突）
        self.trainer.model_path = "data/models/xgboost_predictor_binary.pkl"
        self.trainer.metrics_path = "data/models/predictor_metrics.json"
        
        self.data_processor = MLDataProcessor()
        self.model: Optional[Any] = None  # XGBoost分类模型
        self.is_ready = False
        self.last_training_samples = 0  # 上次訓練時的樣本數
        self.last_training_time: Optional[datetime] = None  # 上次訓練時間
        self.retrain_threshold = 50  # 累積50筆新交易後重訓練
        self.last_model_accuracy = 0.0  # 上次模型準確率
    
    def initialize(self) -> bool:
        """
        初始化預測器（加載模型）
        
        v3.9.1: 添加模型类型检测，确保加载的是binary分类模型
        
        Returns:
            bool: 是否成功初始化
        """
        try:
            # 嘗試加載已有模型
            self.model = self.trainer.load_model()
            
            # 🔍 v3.9.1: 验证模型类型（必须支持predict_proba）
            if self.model is not None:
                if not hasattr(self.model, 'predict_proba'):
                    logger.warning(
                        "⚠️  加载的模型不支持predict_proba（可能是回归模型），"
                        "将重新训练binary分类模型..."
                    )
                    self.model = None
            
            if self.model is None:
                logger.info("未找到已訓練的binary分类模型，嘗試自動訓練...")
                
                # 如果有足夠數據，自動訓練binary分类模型
                success = self.trainer.auto_train_if_needed(min_samples=100)
                
                if success:
                    self.model = self.trainer.model
                    
                    # 再次验证
                    if self.model and not hasattr(self.model, 'predict_proba'):
                        logger.error("❌ 训练的模型不是分类模型，初始化失败")
                        self.model = None
                        return False
            
            if self.model is not None:
                self.is_ready = True
                # 記錄初始訓練時的樣本數和時間
                self.last_training_samples = self._load_last_training_samples()
                self.last_training_time = self._load_last_training_time()
                self.last_model_accuracy = self._load_last_model_accuracy()
                logger.info(
                    f"✅ ML 預測器已就緒（binary分类模型）"
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
        從信號準備特徵向量（v3.9.1優化版 - 29個特徵）
        
        Args:
            signal: 交易信號
        
        Returns:
            Optional[list]: 特徵向量（29個）
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
            
            # ✨ 增強特徵（8個 - v3.9.1修復版）
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
            
            # v3.9.1修复：使用默认杠杆估计值而非0
            default_leverage = 10  # 中等杠杆（3-20范围内的中值）
            
            enhanced_features = [
                hour_of_day,  # hour_of_day
                day_of_week,  # day_of_week
                is_weekend,  # is_weekend
                stop_distance_pct,  # stop_distance_pct
                tp_distance_pct,  # tp_distance_pct
                confidence * default_leverage,  # confidence_x_leverage（使用估计值）
                rsi * trend_15m,  # rsi_x_trend
                atr * bb_width  # atr_x_bb_width
            ]
            
            # 組合成29個特徵（21基礎 + 8增強）
            features = basic_features + enhanced_features
            
            return features
            
        except Exception as e:
            logger.error(f"準備特徵失敗: {e}", exc_info=True)
            return None
    
    async def predict_rebound(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        current_price: float,
        pnl_pct: float,
        indicators: Optional[Dict] = None
    ) -> Dict:
        """
        預測市場反彈概率（用於平倉決策）
        
        🎯 v3.9.2.5新增：ML輔助持倉監控
        
        分析當前虧損倉位是否有可能反彈，幫助決定：
        - 立即平倉（反彈概率低）
        - 等待觀察（反彈概率高）
        - 調整策略（反彈概率中等）
        
        Args:
            symbol: 交易對
            direction: 方向（LONG/SHORT）
            entry_price: 入場價格
            current_price: 當前價格
            pnl_pct: 當前盈虧百分比
            indicators: 當前技術指標（可選）
        
        Returns:
            Dict: {
                'rebound_probability': float,  # 反彈概率 0-1
                'should_wait': bool,  # 是否應該等待
                'recommended_action': str,  # 建議操作
                'confidence': float,  # 預測信心度
                'reason': str  # 判斷原因
            }
        """
        try:
            # 默認返回值（保守策略：建議平倉）
            default_result = {
                'rebound_probability': 0.0,
                'should_wait': False,
                'recommended_action': 'close_immediately',
                'confidence': 0.5,
                'reason': 'ML模型未就緒或數據不足'
            }
            
            # 如果indicators未提供，嘗試獲取實時數據
            if indicators is None:
                logger.debug(f"未提供技術指標，使用基礎分析預測反彈 {symbol}")
                indicators = {}
            
            # === 1. 基於技術指標的反彈分析 ===
            rebound_signals = []
            rebound_score = 0.0
            
            # RSI超賣/超買信號
            rsi = indicators.get('rsi', 50)
            if direction == "LONG":
                if rsi < 30:  # 超賣，可能反彈
                    rebound_signals.append("RSI超賣(<30)")
                    rebound_score += 0.3
                elif rsi < 40:
                    rebound_signals.append("RSI偏低(<40)")
                    rebound_score += 0.15
            else:  # SHORT
                if rsi > 70:  # 超買，可能反彈
                    rebound_signals.append("RSI超買(>70)")
                    rebound_score += 0.3
                elif rsi > 60:
                    rebound_signals.append("RSI偏高(>60)")
                    rebound_score += 0.15
            
            # MACD趨勢反轉信號
            macd = indicators.get('macd', 0)
            macd_signal = indicators.get('macd_signal', 0)
            macd_histogram = indicators.get('macd_histogram', 0)
            
            if direction == "LONG":
                # LONG: 尋找向上反轉信號
                if macd > macd_signal and macd_histogram > 0:
                    rebound_signals.append("MACD金叉")
                    rebound_score += 0.25
                elif macd_histogram > 0:  # histogram轉正
                    rebound_signals.append("MACD柱轉正")
                    rebound_score += 0.1
            else:  # SHORT
                # SHORT: 尋找向下反轉信號
                if macd < macd_signal and macd_histogram < 0:
                    rebound_signals.append("MACD死叉")
                    rebound_score += 0.25
                elif macd_histogram < 0:  # histogram轉負
                    rebound_signals.append("MACD柱轉負")
                    rebound_score += 0.1
            
            # 布林帶位置
            bb_width = indicators.get('bb_width_pct', 0)
            price_vs_bb = indicators.get('price_vs_bb', 0)  # 相對布林帶位置
            
            if direction == "LONG":
                if price_vs_bb < 0.2:  # 接近下軌
                    rebound_signals.append("價格接近布林下軌")
                    rebound_score += 0.2
            else:  # SHORT
                if price_vs_bb > 0.8:  # 接近上軌
                    rebound_signals.append("價格接近布林上軌")
                    rebound_score += 0.2
            
            # === 2. 基於虧損程度的風險評估 ===
            # 虧損越嚴重，反彈要求越高
            risk_factor = 1.0
            if pnl_pct < -40:  # 超過-40%，非常危險
                risk_factor = 0.5  # 降低反彈判斷的權重
                rebound_signals.append("⚠️虧損嚴重(< -40%)")
            elif pnl_pct < -30:
                risk_factor = 0.7
                rebound_signals.append("⚠️虧損較大(< -30%)")
            elif pnl_pct < -20:
                risk_factor = 0.85
            
            # 應用風險因子
            adjusted_rebound_score = rebound_score * risk_factor
            
            # === 3. ML模型預測（如果可用）===
            ml_boost = 0.0
            if self.is_ready and self.model is not None:
                try:
                    # 構造一個假設的反向信號來預測反彈
                    reverse_direction = "SHORT" if direction == "LONG" else "LONG"
                    hypothetical_signal = {
                        'symbol': symbol,
                        'direction': reverse_direction,
                        'entry_price': current_price,
                        'stop_loss': entry_price if direction == "LONG" else current_price * 1.02,
                        'take_profit': current_price * 1.02 if direction == "LONG" else entry_price,
                        'confidence': 0.5,
                        'indicators': indicators,
                        'timeframes': {},
                        'timestamp': datetime.now()
                    }
                    
                    ml_pred = self.predict(hypothetical_signal)
                    if ml_pred:
                        ml_rebound_prob = ml_pred.get('win_probability', 0)
                        if ml_rebound_prob > 0.55:  # ML認為反向交易有>55%勝率
                            ml_boost = 0.15
                            rebound_signals.append(f"ML反向信號勝率{ml_rebound_prob:.1%}")
                        elif ml_rebound_prob > 0.50:
                            ml_boost = 0.08
                except Exception as e:
                    logger.debug(f"ML反彈預測失敗: {e}")
            
            # === 4. 綜合判斷 ===
            final_rebound_prob = min(1.0, adjusted_rebound_score + ml_boost)
            
            # 決策閾值
            WAIT_THRESHOLD = 0.50  # 反彈概率>50%才建議等待
            ADJUST_THRESHOLD = 0.35  # 反彈概率35-50%建議調整策略
            
            if final_rebound_prob >= WAIT_THRESHOLD:
                recommended_action = 'wait_and_monitor'
                should_wait = True
                reason = f"反彈概率高({final_rebound_prob:.1%})，建議等待: {', '.join(rebound_signals)}"
            elif final_rebound_prob >= ADJUST_THRESHOLD:
                recommended_action = 'adjust_strategy'
                should_wait = True
                reason = f"反彈概率中等({final_rebound_prob:.1%})，建議收緊止損: {', '.join(rebound_signals)}"
            else:
                recommended_action = 'close_immediately'
                should_wait = False
                reason = f"反彈概率低({final_rebound_prob:.1%})，建議立即平倉"
            
            result = {
                'rebound_probability': final_rebound_prob,
                'should_wait': should_wait,
                'recommended_action': recommended_action,
                'confidence': 0.7 if self.is_ready else 0.5,
                'reason': reason,
                'signals': rebound_signals
            }
            
            logger.info(
                f"🔮 反彈預測 {symbol} {direction}: "
                f"概率={final_rebound_prob:.1%} | "
                f"建議={recommended_action} | "
                f"信號: {', '.join(rebound_signals[:3])}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"預測反彈失敗: {e}", exc_info=True)
            return default_result
    
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
