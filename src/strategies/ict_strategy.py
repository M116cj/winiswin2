"""
ICT/SMC 策略引擎
職責：Order Blocks、Liquidity Zones、Market Structure 分析、信心度評分
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

from src.utils.indicators import (
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_atr,
    calculate_bollinger_bands,
    identify_order_blocks,
    identify_swing_points,
    determine_market_structure
)
from src.config import Config

logger = logging.getLogger(__name__)


class ICTStrategy:
    """ICT/SMC 策略引擎"""
    
    def __init__(self):
        """初始化策略引擎"""
        self.config = Config
    
    def analyze(
        self,
        symbol: str,
        multi_tf_data: Dict[str, pd.DataFrame]
    ) -> Optional[Dict]:
        """
        分析交易信號
        
        Args:
            symbol: 交易對
            multi_tf_data: 多時間框架數據
        
        Returns:
            Optional[Dict]: 交易信號（如果有）
        """
        try:
            if not self._validate_data(multi_tf_data):
                return None
            
            h1_data = multi_tf_data.get('1h')
            m15_data = multi_tf_data.get('15m')
            m5_data = multi_tf_data.get('5m')
            m1_data = multi_tf_data.get('1m')
            
            h1_trend = self._determine_trend(h1_data)
            m15_trend = self._determine_trend(m15_data)
            m5_trend = self._determine_trend(m5_data)
            
            if h1_trend == "neutral" or m15_trend == "neutral":
                return None
            
            market_structure = determine_market_structure(m15_data)
            
            order_blocks = identify_order_blocks(
                m15_data,
                lookback=self.config.OB_LOOKBACK
            )
            
            liquidity_zones = self._identify_liquidity_zones(m15_data)
            
            current_price = float(m5_data['close'].iloc[-1])
            
            signal_direction = self._determine_signal_direction(
                h1_trend,
                m15_trend,
                m5_trend,
                market_structure,
                order_blocks,
                liquidity_zones,
                current_price
            )
            
            if not signal_direction:
                return None
            
            confidence_score = self._calculate_confidence(
                h1_trend=h1_trend,
                m15_trend=m15_trend,
                m5_trend=m5_trend,
                market_structure=market_structure,
                order_blocks=order_blocks,
                liquidity_zones=liquidity_zones,
                current_price=current_price,
                m15_data=m15_data,
                m5_data=m5_data
            )
            
            if confidence_score < self.config.MIN_CONFIDENCE:
                return None
            
            entry_price, stop_loss, take_profit = self._calculate_levels(
                signal_direction,
                current_price,
                m5_data,
                order_blocks,
                liquidity_zones
            )
            
            signal = {
                'symbol': symbol,
                'direction': signal_direction,
                'confidence': confidence_score,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': datetime.now(),
                'timeframes': {
                    '1h': h1_trend,
                    '15m': m15_trend,
                    '5m': m5_trend
                },
                'market_structure': market_structure,
                'order_blocks': len(order_blocks),
                'liquidity_zones': len(liquidity_zones)
            }
            
            logger.info(f"✅ 生成交易信號: {symbol} {signal_direction} 信心度 {confidence_score:.2%}")
            
            return signal
            
        except Exception as e:
            logger.error(f"分析 {symbol} 失敗: {e}")
            return None
    
    def _validate_data(self, multi_tf_data: Dict[str, pd.DataFrame]) -> bool:
        """驗證數據完整性"""
        required_timeframes = ['1h', '15m', '5m', '1m']
        
        for tf in required_timeframes:
            if tf not in multi_tf_data:
                return False
            
            df = multi_tf_data[tf]
            if df.empty or len(df) < 50:
                return False
        
        return True
    
    def _determine_trend(self, df: pd.DataFrame) -> str:
        """
        判斷趨勢方向
        
        Args:
            df: K線數據
        
        Returns:
            str: 趨勢方向 ('bullish', 'bearish', 'neutral')
        """
        if df.empty or len(df) < self.config.EMA_SLOW:
            return "neutral"
        
        ema_fast = calculate_ema(df['close'], self.config.EMA_FAST)
        ema_slow = calculate_ema(df['close'], self.config.EMA_SLOW)
        
        if ema_fast.iloc[-1] > ema_slow.iloc[-1] * 1.005:
            return "bullish"
        elif ema_fast.iloc[-1] < ema_slow.iloc[-1] * 0.995:
            return "bearish"
        else:
            return "neutral"
    
    def _identify_liquidity_zones(self, df: pd.DataFrame) -> List[Dict]:
        """
        識別流動性區域
        
        Args:
            df: K線數據
        
        Returns:
            List[Dict]: 流動性區域列表
        """
        if df.empty or len(df) < self.config.LZ_LOOKBACK:
            return []
        
        highs, lows = identify_swing_points(df, lookback=5)
        
        liquidity_zones = []
        
        recent_highs = df['high'].tail(self.config.LZ_LOOKBACK)
        high_clusters = self._find_price_clusters(recent_highs)
        
        for cluster in high_clusters:
            liquidity_zones.append({
                'type': 'resistance',
                'price': cluster['price'],
                'strength': cluster['strength']
            })
        
        recent_lows = df['low'].tail(self.config.LZ_LOOKBACK)
        low_clusters = self._find_price_clusters(recent_lows)
        
        for cluster in low_clusters:
            liquidity_zones.append({
                'type': 'support',
                'price': cluster['price'],
                'strength': cluster['strength']
            })
        
        return liquidity_zones
    
    def _find_price_clusters(self, prices: pd.Series) -> List[Dict]:
        """尋找價格聚集區"""
        if len(prices) < 3:
            return []
        
        price_array = prices.values
        clusters = []
        tolerance = 0.002
        
        for i in range(len(price_array)):
            nearby = np.abs(price_array - price_array[i]) / price_array[i] < tolerance
            count = np.sum(nearby)
            
            if count >= 3:
                clusters.append({
                    'price': float(np.mean(price_array[nearby])),
                    'strength': float(count / len(price_array))
                })
        
        unique_clusters = []
        for cluster in clusters:
            is_unique = True
            for existing in unique_clusters:
                if abs(cluster['price'] - existing['price']) / cluster['price'] < tolerance:
                    is_unique = False
                    if cluster['strength'] > existing['strength']:
                        existing['price'] = cluster['price']
                        existing['strength'] = cluster['strength']
                    break
            
            if is_unique:
                unique_clusters.append(cluster)
        
        return sorted(unique_clusters, key=lambda x: x['strength'], reverse=True)[:3]
    
    def _determine_signal_direction(
        self,
        h1_trend: str,
        m15_trend: str,
        m5_trend: str,
        market_structure: str,
        order_blocks: List[Dict],
        liquidity_zones: List[Dict],
        current_price: float
    ) -> Optional[str]:
        """判斷信號方向"""
        if h1_trend == m15_trend == m5_trend == "bullish":
            if market_structure in ["bullish", "neutral"]:
                return "LONG"
        
        elif h1_trend == m15_trend == m5_trend == "bearish":
            if market_structure in ["bearish", "neutral"]:
                return "SHORT"
        
        return None
    
    def _calculate_confidence(
        self,
        h1_trend: str,
        m15_trend: str,
        m5_trend: str,
        market_structure: str,
        order_blocks: List[Dict],
        liquidity_zones: List[Dict],
        current_price: float,
        m15_data: pd.DataFrame,
        m5_data: pd.DataFrame
    ) -> float:
        """
        計算信心度評分
        
        Returns:
            float: 信心度分數 (0-1)
        """
        weights = self.config.CONFIDENCE_WEIGHTS
        scores = {}
        
        trend_score = 0.0
        if h1_trend == m15_trend:
            trend_score += 0.5
        if m15_trend == m5_trend:
            trend_score += 0.5
        scores['trend_alignment'] = trend_score
        
        structure_score = 0.0
        if market_structure == "bullish" and h1_trend == "bullish":
            structure_score = 1.0
        elif market_structure == "bearish" and h1_trend == "bearish":
            structure_score = 1.0
        elif market_structure == "neutral":
            structure_score = 0.5
        scores['market_structure'] = structure_score
        
        position_score = 0.0
        if order_blocks:
            nearest_ob = min(
                order_blocks,
                key=lambda x: abs(x['price'] - current_price)
            )
            distance_pct = abs(nearest_ob['price'] - current_price) / current_price
            position_score = max(0, 1 - distance_pct * 10)
        scores['price_position'] = position_score
        
        rsi = calculate_rsi(m5_data['close'])
        macd_line, signal_line, _ = calculate_macd(m5_data['close'])
        
        momentum_score = 0.0
        if not rsi.empty and not macd_line.empty:
            rsi_val = rsi.iloc[-1]
            macd_val = macd_line.iloc[-1]
            signal_val = signal_line.iloc[-1]
            
            if h1_trend == "bullish":
                if 40 < rsi_val < 70 and macd_val > signal_val:
                    momentum_score = 1.0
                elif rsi_val < 70:
                    momentum_score = 0.5
            elif h1_trend == "bearish":
                if 30 < rsi_val < 60 and macd_val < signal_val:
                    momentum_score = 1.0
                elif rsi_val > 30:
                    momentum_score = 0.5
        
        scores['momentum'] = momentum_score
        
        atr = calculate_atr(m15_data)
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(m15_data['close'])
        
        volatility_score = 0.0
        if not atr.empty and not bb_upper.empty:
            atr_val = atr.iloc[-1]
            bb_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_middle.iloc[-1]
            
            if 0.02 < bb_width < 0.10:
                volatility_score = 1.0
            elif bb_width < 0.15:
                volatility_score = 0.5
        
        scores['volatility'] = volatility_score
        
        confidence = sum(
            scores[key] * weights[key]
            for key in weights.keys()
        )
        
        return min(1.0, max(0.0, confidence))
    
    def _calculate_levels(
        self,
        direction: str,
        current_price: float,
        m5_data: pd.DataFrame,
        order_blocks: List[Dict],
        liquidity_zones: List[Dict]
    ) -> Tuple[float, float, float]:
        """
        計算入場、止損、止盈價格
        
        Returns:
            Tuple[float, float, float]: (入場價, 止損價, 止盈價)
        """
        atr = calculate_atr(m5_data)
        atr_value = atr.iloc[-1] if not atr.empty else current_price * 0.01
        
        entry_price = current_price
        
        stop_distance = atr_value * self.config.ATR_MULTIPLIER
        take_profit_distance = stop_distance * self.config.RISK_REWARD_RATIO
        
        if direction == "LONG":
            stop_loss = entry_price - stop_distance
            take_profit = entry_price + take_profit_distance
        else:
            stop_loss = entry_price + stop_distance
            take_profit = entry_price - take_profit_distance
        
        return entry_price, stop_loss, take_profit
