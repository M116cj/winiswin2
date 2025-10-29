"""
🔥 v3.18+ 統一信號評估引擎 (Unified Signal Evaluation Engine)

核心設計哲學:
- 無狀態純函數：即時計算，不存儲中間狀態
- 統一評估上下文：開倉和監控使用相同的特徵構建邏輯
- 共享XGBoost模型：單例模式，避免重複加載

架構位置:
UnifiedScheduler → EvaluationEngine (單例)
                     ↓
    ┌────────────────┴────────────────┐
    ↓                                 ↓
SelfLearningTrader              PositionMonitor24x7
(開倉時評估)                    (監控時即時評估)
"""

import logging
import time
import numpy as np
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MarketContext:
    """
    市場上下文快照（用於即時評估）
    
    Attributes:
        trend_direction: 當前趨勢方向 ("BULLISH"/"BEARISH"/"NEUTRAL")
        liquidity_score: 流動性分數 (0-1)
        volatility: 波動率 (ATR/價格)
        rsi: RSI指標
        macd: MACD值
        volume_ratio: 當前成交量/平均成交量
    """
    trend_direction: str
    liquidity_score: float
    volatility: float
    rsi: Optional[float] = None
    macd: Optional[float] = None
    volume_ratio: Optional[float] = 1.0


class EvaluationEngine:
    """
    🔥 v3.18+ 統一信號評估引擎
    
    核心功能:
    1. calculate_current_confidence() - 即時計算信心度
    2. calculate_current_win_probability() - 即時計算勝率
    3. calculate_reward_ratio() - 計算報酬率
    
    使用場景:
    - SelfLearningTrader: 開倉時評估信號質量
    - PositionMonitor: 監控時即時重新評估
    
    特性:
    - 無狀態: 每次調用基於實時數據計算
    - 可測試: 純函數，易於單元測試
    - 高效: 共享XGBoost模型，避免重複加載
    """
    
    def __init__(self, model: Optional[Any] = None):
        """
        初始化評估引擎
        
        Args:
            model: XGBoost模型實例（可選，如果為None則使用規則引擎）
        """
        self.model = model
        self.use_ml_model = model is not None
        
        if self.use_ml_model:
            logger.info("✅ EvaluationEngine 使用 ML 模型評估")
        else:
            logger.info("⚠️ EvaluationEngine 使用規則引擎評估（無ML模型）")
    
    def calculate_current_confidence(
        self,
        original_signal: Dict[str, Any],
        current_price: float,
        market_context: MarketContext
    ) -> float:
        """
        🔥 即時計算當前信心度（無狀態）
        
        信心度定義：
        - ML模型：max(predict_proba) - 模型最有信心的預測概率
        - 規則引擎：基於分數加權的信心度
        
        Args:
            original_signal: 開倉時的原始信號（包含entry, stop_loss, scores等）
            current_price: 當前市場價格
            market_context: 當前市場狀態
        
        Returns:
            float: 信心度 (0-1)，越高表示模型越有信心
        """
        if self.use_ml_model:
            return self._ml_calculate_confidence(
                original_signal, current_price, market_context
            )
        else:
            return self._rule_based_confidence(
                original_signal, current_price, market_context
            )
    
    def calculate_current_win_probability(
        self,
        original_signal: Dict[str, Any],
        current_price: float,
        market_context: MarketContext
    ) -> float:
        """
        🔥 即時計算當前勝率（無狀態）
        
        勝率定義：
        - ML模型：predict_proba[1] - 預測為LONG的概率
        - 規則引擎：基於趨勢對齊和分數的勝率估算
        
        Args:
            original_signal: 開倉時的原始信號
            current_price: 當前市場價格
            market_context: 當前市場狀態
        
        Returns:
            float: 勝率 (0-1)，越高表示勝算越大
        """
        if self.use_ml_model:
            return self._ml_calculate_win_probability(
                original_signal, current_price, market_context
            )
        else:
            return self._rule_based_win_probability(
                original_signal, current_price, market_context
            )
    
    def calculate_reward_ratio(
        self,
        original_signal: Dict[str, Any],
        current_price: float
    ) -> float:
        """
        計算報酬率 (Risk/Reward Ratio)
        
        公式：
        報酬率 = (take_profit - entry) / (entry - stop_loss)
        
        Args:
            original_signal: 開倉時的原始信號
            current_price: 當前價格（可用於動態調整）
        
        Returns:
            float: 報酬率，通常 >1.5 視為良好
        """
        entry = original_signal.get('entry_price', current_price)
        stop_loss = original_signal.get('stop_loss', entry * 0.99)
        take_profit = original_signal.get('take_profit', entry * 1.02)
        direction = original_signal.get('direction', 'LONG')
        
        if direction == 'LONG':
            risk = entry - stop_loss
            reward = take_profit - entry
        else:  # SHORT
            risk = stop_loss - entry
            reward = entry - take_profit
        
        if risk <= 0:
            logger.warning(f"⚠️ 風險距離異常: risk={risk}, 使用默認報酬率1.0")
            return 1.0
        
        reward_ratio = reward / risk
        return max(0.0, reward_ratio)  # 確保非負
    
    # ========== ML模型評估方法 ==========
    
    def _ml_calculate_confidence(
        self,
        signal: Dict[str, Any],
        current_price: float,
        market_context: MarketContext
    ) -> float:
        """
        使用ML模型計算信心度
        
        Returns:
            信心度 = max(predict_proba)
        """
        try:
            features = self._build_realtime_features(signal, current_price, market_context)
            proba = self.model.predict_proba([features])[0]
            confidence = float(max(proba))
            return min(max(confidence, 0.0), 1.0)  # 限制在[0,1]
            
        except Exception as e:
            logger.error(f"❌ ML信心度計算失敗: {e}，降級為規則引擎")
            return self._rule_based_confidence(signal, current_price, market_context)
    
    def _ml_calculate_win_probability(
        self,
        signal: Dict[str, Any],
        current_price: float,
        market_context: MarketContext
    ) -> float:
        """
        使用ML模型計算勝率
        
        Returns:
            勝率 = predict_proba[1] (LONG類別概率)
        """
        try:
            features = self._build_realtime_features(signal, current_price, market_context)
            proba = self.model.predict_proba([features])[0]
            win_prob = float(proba[1]) if len(proba) > 1 else float(max(proba))
            return min(max(win_prob, 0.0), 1.0)  # 限制在[0,1]
            
        except Exception as e:
            logger.error(f"❌ ML勝率計算失敗: {e}，降級為規則引擎")
            return self._rule_based_win_probability(signal, current_price, market_context)
    
    def _build_realtime_features(
        self,
        signal: Dict[str, Any],
        current_price: float,
        market_context: MarketContext
    ) -> np.ndarray:
        """
        動態構建特徵向量（與開倉時一致的特徵工程）
        
        特徵組成:
        1. 原始信號特徵（開倉時計算）
        2. 實時市場特徵（當前狀態）
        3. 持倉動態特徵（價格偏離、持倉時長等）
        
        Returns:
            np.ndarray: 特徵向量
        """
        entry_price = signal.get('entry_price', current_price)
        entry_timestamp = signal.get('timestamp', time.time())
        direction = signal.get('direction', 'LONG')
        
        # 1. 原始信號特徵（開倉時的分數）
        base_features = np.array([
            signal.get('confidence', 0.5),
            signal.get('trend_alignment_score', 0.5),
            signal.get('market_structure_score', 0.5),
            signal.get('price_position_score', 0.5),
            signal.get('momentum_score', 0.5),
            signal.get('volatility_score', 0.5),
        ])
        
        # 2. 實時市場特徵
        realtime_features = np.array([
            (current_price - entry_price) / entry_price,  # 價格偏離%
            1.0 if market_context.trend_direction == direction else 0.0,  # 趨勢對齊
            market_context.liquidity_score,
            market_context.volatility,
            market_context.rsi / 100.0 if market_context.rsi else 0.5,
            (market_context.macd + 10) / 20 if market_context.macd else 0.5,  # 歸一化
            market_context.volume_ratio,
        ])
        
        # 3. 持倉動態特徵
        hold_time_hours = (time.time() - entry_timestamp) / 3600.0
        dynamic_features = np.array([
            hold_time_hours,
            min(hold_time_hours / 24.0, 1.0),  # 持倉時長歸一化（以天為單位）
        ])
        
        # 合併所有特徵
        all_features = np.concatenate([base_features, realtime_features, dynamic_features])
        
        return all_features
    
    # ========== 規則引擎評估方法（ML模型不可用時的降級方案）==========
    
    def _rule_based_confidence(
        self,
        signal: Dict[str, Any],
        current_price: float,
        market_context: MarketContext
    ) -> float:
        """
        規則引擎: 基於分數加權計算信心度
        
        權重分配:
        - 原始信號分數: 60%
        - 趨勢對齊: 20%
        - 流動性: 10%
        - 價格偏離懲罰: 10%
        """
        # 1. 原始信號平均分數
        scores = signal.get('scores', {})
        avg_score = np.mean([
            scores.get('trend_alignment', 0.5),
            scores.get('market_structure', 0.5),
            scores.get('price_position', 0.5),
            scores.get('momentum', 0.5),
            scores.get('volatility', 0.5),
        ])
        
        # 2. 趨勢對齊獎勵
        direction = signal.get('direction', 'LONG')
        trend_bonus = 0.15 if market_context.trend_direction == direction else -0.10
        
        # 3. 流動性獎勵
        liquidity_bonus = market_context.liquidity_score * 0.10
        
        # 4. 價格偏離懲罰
        entry_price = signal.get('entry_price', current_price)
        price_deviation = abs(current_price - entry_price) / entry_price
        deviation_penalty = min(price_deviation * 0.5, 0.15)  # 最多扣15%
        
        # 計算最終信心度
        confidence = avg_score * 0.60 + trend_bonus + liquidity_bonus - deviation_penalty
        
        return min(max(confidence, 0.0), 1.0)  # 限制在[0,1]
    
    def _rule_based_win_probability(
        self,
        signal: Dict[str, Any],
        current_price: float,
        market_context: MarketContext
    ) -> float:
        """
        規則引擎: 基於趨勢對齊和分數估算勝率
        
        勝率計算:
        - 基礎勝率: 50%
        - 趨勢對齊: +20%
        - 高分信號: +15%
        - RSI超買/超賣: ±10%
        """
        direction = signal.get('direction', 'LONG')
        
        # 1. 基礎勝率
        base_win_prob = 0.50
        
        # 2. 趨勢對齊獎勵
        if market_context.trend_direction == direction:
            trend_bonus = 0.20
        elif market_context.trend_direction == 'NEUTRAL':
            trend_bonus = 0.0
        else:  # 逆勢
            trend_bonus = -0.15
        
        # 3. 信號質量獎勵
        scores = signal.get('scores', {})
        avg_score = np.mean([
            scores.get('trend_alignment', 0.5),
            scores.get('market_structure', 0.5),
            scores.get('momentum', 0.5),
        ])
        quality_bonus = (avg_score - 0.5) * 0.30  # 高於0.5獎勵，低於0.5懲罰
        
        # 4. RSI超買/超賣調整
        rsi_adjustment = 0.0
        if market_context.rsi is not None:
            if direction == 'LONG' and market_context.rsi < 30:
                rsi_adjustment = 0.10  # 超賣，做多勝率提升
            elif direction == 'SHORT' and market_context.rsi > 70:
                rsi_adjustment = 0.10  # 超買，做空勝率提升
            elif direction == 'LONG' and market_context.rsi > 70:
                rsi_adjustment = -0.10  # 超買做多，勝率降低
            elif direction == 'SHORT' and market_context.rsi < 30:
                rsi_adjustment = -0.10  # 超賣做空，勝率降低
        
        # 計算最終勝率
        win_prob = base_win_prob + trend_bonus + quality_bonus + rsi_adjustment
        
        return min(max(win_prob, 0.0), 1.0)  # 限制在[0,1]
    
    # ========== 輔助方法 ==========
    
    def get_engine_info(self) -> Dict[str, Any]:
        """
        獲取評估引擎信息（用於調試）
        
        Returns:
            包含模型類型、狀態等信息的字典
        """
        return {
            "engine_type": "ML_MODEL" if self.use_ml_model else "RULE_ENGINE",
            "model_loaded": self.model is not None,
            "model_type": type(self.model).__name__ if self.model else None,
        }
