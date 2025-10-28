"""
自我学习交易员（核心策略）
完全自主的信号生成，无需预定义规则
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, Dict, Any

from src.ml.market_structure_autoencoder import MarketStructureAutoencoder
from src.ml.feature_discovery_network import FeatureDiscoveryNetwork
from src.ml.liquidity_prediction_model import LiquidityPredictionModel
from src.core.data_models import TradingSignal

logger = logging.getLogger(__name__)


class SelfLearningTrader:
    """自我学习交易员策略"""
    
    def __init__(self, config):
        self.config = config
        
        self.structure_model = MarketStructureAutoencoder()
        self.feature_model = FeatureDiscoveryNetwork()
        self.liquidity_model = LiquidityPredictionModel()
        
        self.min_confidence = config.MIN_CONFIDENCE
        
        logger.info("✅ 自我学习交易员初始化完成")
    
    def analyze(self, symbol: str, multi_tf_data: Dict[str, pd.DataFrame]) -> Optional[TradingSignal]:
        """
        完全自主的信号生成
        
        Args:
            symbol: 交易对符号
            multi_tf_data: 多时间框架数据
            
        Returns:
            交易信号或None
        """
        try:
            if '5m' not in multi_tf_data or len(multi_tf_data['5m']) < 50:
                return None
            
            market_structure = self.structure_model.encode_structure(
                multi_tf_data['5m']['close'].values
            )
            
            dynamic_features = self.feature_model.discover_features(
                market_structure,
                multi_tf_data['5m'].tail(50)
            )
            
            liquidity_prediction = self.liquidity_model.predict_liquidity(
                symbol,
                multi_tf_data['5m'].tail(20)
            )
            
            signal = self._generate_signal_from_learned_patterns(
                symbol,
                market_structure,
                dynamic_features,
                liquidity_prediction,
                multi_tf_data['5m']
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"自我学习分析失败 {symbol}: {e}")
            return None
    
    def _generate_signal_from_learned_patterns(
        self,
        symbol: str,
        market_structure: np.ndarray,
        dynamic_features: np.ndarray,
        liquidity_prediction: Dict[str, Any],
        df_5m: pd.DataFrame
    ) -> Optional[TradingSignal]:
        """从学习到的模式生成交易信号"""
        
        structure_signal = np.mean(market_structure[:8])
        feature_signal = np.mean(dynamic_features[:16])
        
        combined_signal = (structure_signal + feature_signal) / 2
        
        if abs(combined_signal) < 0.1:
            return None
        
        direction = 1 if combined_signal > 0 else -1
        confidence = min(abs(combined_signal), 1.0)
        
        if confidence < self.min_confidence:
            return None
        
        current_price = float(df_5m['close'].iloc[-1])
        
        atr = self._calculate_atr(df_5m)
        
        if direction == 1:
            entry_price = current_price
            stop_loss = current_price - (atr * 1.5)
            take_profit = current_price + (atr * 3.0)
        else:
            entry_price = current_price
            stop_loss = current_price + (atr * 1.5)
            take_profit = current_price - (atr * 3.0)
        
        leverage = self._calculate_leverage(confidence)
        
        signal = TradingSignal(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            leverage=leverage,
            reasoning=f"自我学习信号 (结构:{structure_signal:.3f}, 特征:{feature_signal:.3f})",
            timeframe='5m',
            strategy_name='self_learning'
        )
        
        return signal
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算ATR"""
        if len(df) < period:
            high = df['high'].values if 'high' in df.columns else df['close'].values
            low = df['low'].values if 'low' in df.columns else df['close'].values
            return float(np.mean(high - low))
        
        high = df['high'].tail(period).values
        low = df['low'].tail(period).values
        close = df['close'].tail(period + 1).values
        
        tr = np.maximum(high - low, np.abs(high - close[:-1]))
        tr = np.maximum(tr, np.abs(low - close[:-1]))
        
        return float(np.mean(tr))
    
    def _calculate_leverage(self, confidence: float) -> int:
        """基于信心度计算杠杆"""
        base_leverage = self.config.BASE_LEVERAGE
        max_leverage = self.config.MAX_LEVERAGE
        
        leverage = int(base_leverage + (max_leverage - base_leverage) * confidence)
        return min(max(leverage, base_leverage), max_leverage)
