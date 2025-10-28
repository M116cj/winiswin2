"""
規則驅動信號生成器（v3.17+ SelfLearningTrader 架構）
職責：整合 ICT 策略邏輯，生成標準化交易信號
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

from src.utils.indicators import (
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_adx,
    identify_order_blocks,
    determine_market_structure
)
from src.config import Config

logger = logging.getLogger(__name__)


class RuleBasedSignalGenerator:
    """
    規則驅動信號生成器（v3.17+）
    
    職責：
    1. 整合 ICT/SMC 策略邏輯
    2. 生成標準化信號格式（供 SelfLearningTrader 使用）
    3. 計算基礎信心度（不含槓桿決策）
    """
    
    def __init__(self, config=None):
        """初始化信號生成器"""
        self.config = config or Config
        logger.info("✅ RuleBasedSignalGenerator 初始化完成")
    
    def generate_signal(
        self,
        symbol: str,
        multi_tf_data: Dict[str, pd.DataFrame]
    ) -> Optional[Dict]:
        """
        生成交易信號
        
        Args:
            symbol: 交易對
            multi_tf_data: 多時間框架數據
        
        Returns:
            標準化信號字典，包含：
            - symbol: 交易對
            - direction: 'LONG' 或 'SHORT'
            - entry_price: 入場價格
            - stop_loss: 止損價格
            - take_profit: 止盈價格
            - confidence: 基礎信心度（0-1）
            - win_probability: 預估勝率（0-1）
            - rr_ratio: 風報比
            - indicators: 所有技術指標
            - reasoning: 信號原因
        """
        try:
            # 驗證數據
            if not self._validate_data(multi_tf_data):
                return None
            
            h1_data = multi_tf_data.get('1h')
            m15_data = multi_tf_data.get('15m')
            m5_data = multi_tf_data.get('5m')
            
            # 計算所有指標
            indicators = self._calculate_all_indicators(h1_data, m15_data, m5_data)
            
            # 確定趨勢
            h1_trend = self._determine_trend(h1_data)
            m15_trend = self._determine_trend(m15_data)
            m5_trend = self._determine_trend(m5_data)
            
            # 市場結構
            market_structure = determine_market_structure(m15_data)
            
            # Order Blocks
            order_blocks = identify_order_blocks(
                m15_data,
                lookback=self.config.OB_LOOKBACK
            )
            
            # 流動性區域
            liquidity_zones = self._identify_liquidity_zones(m15_data)
            
            current_price = float(m5_data['close'].iloc[-1])
            
            # 確定信號方向
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
            
            # 計算基礎信心度（五維 ICT 評分）
            confidence_score, sub_scores = self._calculate_confidence(
                h1_trend=h1_trend,
                m15_trend=m15_trend,
                m5_trend=m5_trend,
                market_structure=market_structure,
                order_blocks=order_blocks,
                liquidity_zones=liquidity_zones,
                current_price=current_price,
                h1_data=h1_data,
                m15_data=m15_data,
                m5_data=m5_data,
                direction=signal_direction,
                indicators=indicators
            )
            
            # 計算 SL/TP
            atr = indicators['atr']
            stop_loss, take_profit = self._calculate_sl_tp(
                current_price,
                signal_direction,
                atr,
                order_blocks
            )
            
            # 計算風報比
            risk = abs(current_price - stop_loss)
            reward = abs(take_profit - current_price)
            rr_ratio = reward / risk if risk > 0 else 1.5
            
            # 預估勝率（基於歷史統計 + 信心度）
            win_probability = self._estimate_win_probability(
                confidence_score,
                rr_ratio,
                signal_direction,
                market_structure
            )
            
            # 構建標準化信號
            signal = {
                'symbol': symbol,
                'direction': signal_direction,
                'entry_price': current_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': confidence_score / 100.0,  # 轉換為 0-1
                'win_probability': win_probability,
                'rr_ratio': rr_ratio,
                'indicators': indicators,
                'sub_scores': sub_scores,
                'reasoning': self._generate_reasoning(
                    signal_direction,
                    sub_scores,
                    market_structure,
                    h1_trend,
                    m15_trend,
                    m5_trend
                ),
                'timestamp': pd.Timestamp.now()
            }
            
            logger.info(
                f"✅ {symbol} 信號生成: {signal_direction} | "
                f"信心度={confidence_score:.1f}% | "
                f"勝率={win_probability*100:.1f}% | "
                f"R:R={rr_ratio:.2f}"
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ {symbol} 信號生成失敗: {e}", exc_info=True)
            return None
    
    def _validate_data(self, multi_tf_data: Dict[str, pd.DataFrame]) -> bool:
        """驗證數據完整性"""
        required_tfs = ['1h', '15m', '5m']
        for tf in required_tfs:
            if tf not in multi_tf_data:
                return False
            df = multi_tf_data[tf]
            if df is None or len(df) < 50:
                return False
        return True
    
    def _calculate_all_indicators(self, h1_data, m15_data, m5_data) -> Dict:
        """計算所有技術指標"""
        indicators = {}
        
        # ATR（用於 SL/TP）
        indicators['atr'] = calculate_atr(m5_data, period=14).iloc[-1]
        
        # RSI
        indicators['rsi'] = calculate_rsi(m5_data, period=14).iloc[-1]
        
        # MACD
        macd_data = calculate_macd(m5_data)
        indicators['macd'] = macd_data['macd'].iloc[-1]
        indicators['macd_signal'] = macd_data['signal'].iloc[-1]
        indicators['macd_hist'] = macd_data['histogram'].iloc[-1]
        
        # 布林帶
        bb_data = calculate_bollinger_bands(m5_data)
        indicators['bb_upper'] = bb_data['upper'].iloc[-1]
        indicators['bb_middle'] = bb_data['middle'].iloc[-1]
        indicators['bb_lower'] = bb_data['lower'].iloc[-1]
        indicators['bb_width'] = bb_data['width'].iloc[-1]
        
        # ADX（趨勢強度）
        adx_data = calculate_adx(m5_data)
        indicators['adx'] = adx_data['adx'].iloc[-1]
        indicators['di_plus'] = adx_data['di_plus'].iloc[-1]
        indicators['di_minus'] = adx_data['di_minus'].iloc[-1]
        
        return indicators
    
    def _determine_trend(self, df: pd.DataFrame) -> str:
        """確定趨勢方向"""
        ema_20 = calculate_ema(df, period=20)
        ema_50 = calculate_ema(df, period=50)
        ema_100 = calculate_ema(df, period=100)
        
        current_price = float(df['close'].iloc[-1])
        ema_20_val = float(ema_20.iloc[-1])
        ema_50_val = float(ema_50.iloc[-1])
        ema_100_val = float(ema_100.iloc[-1])
        
        if current_price > ema_20_val > ema_50_val > ema_100_val:
            return 'bullish'
        elif current_price < ema_20_val < ema_50_val < ema_100_val:
            return 'bearish'
        else:
            return 'neutral'
    
    def _identify_liquidity_zones(self, df: pd.DataFrame) -> list:
        """識別流動性區域"""
        highs = df['high'].values
        lows = df['low'].values
        
        zones = []
        window = 20
        
        for i in range(len(df) - window, len(df)):
            if i < window:
                continue
            
            # 識別高點聚集
            recent_highs = highs[i-window:i]
            max_high = np.max(recent_highs)
            high_cluster = np.sum(np.abs(recent_highs - max_high) / max_high < 0.002)
            
            if high_cluster >= 3:
                zones.append({
                    'type': 'resistance',
                    'price': max_high,
                    'strength': high_cluster
                })
            
            # 識別低點聚集
            recent_lows = lows[i-window:i]
            min_low = np.min(recent_lows)
            low_cluster = np.sum(np.abs(recent_lows - min_low) / min_low < 0.002)
            
            if low_cluster >= 3:
                zones.append({
                    'type': 'support',
                    'price': min_low,
                    'strength': low_cluster
                })
        
        return zones
    
    def _determine_signal_direction(
        self,
        h1_trend: str,
        m15_trend: str,
        m5_trend: str,
        market_structure: str,
        order_blocks: list,
        liquidity_zones: list,
        current_price: float
    ) -> Optional[str]:
        """確定信號方向"""
        # 多頭條件
        long_conditions = (
            h1_trend == 'bullish' and
            m15_trend == 'bullish' and
            market_structure == 'bullish'
        )
        
        # 空頭條件
        short_conditions = (
            h1_trend == 'bearish' and
            m15_trend == 'bearish' and
            market_structure == 'bearish'
        )
        
        if long_conditions:
            return 'LONG'
        elif short_conditions:
            return 'SHORT'
        else:
            return None
    
    def _calculate_confidence(
        self,
        h1_trend: str,
        m15_trend: str,
        m5_trend: str,
        market_structure: str,
        order_blocks: list,
        liquidity_zones: list,
        current_price: float,
        h1_data: pd.DataFrame,
        m15_data: pd.DataFrame,
        m5_data: pd.DataFrame,
        direction: str,
        indicators: Dict
    ) -> tuple:
        """
        計算五維 ICT 信心度評分
        
        Returns:
            (總分, 子分數字典)
        """
        sub_scores = {}
        
        # 1️⃣ 趨勢對齊 (40%)
        trend_score = 0.0
        if direction == 'LONG':
            if h1_trend == 'bullish':
                trend_score += 15
            if m15_trend == 'bullish':
                trend_score += 15
            if m5_trend == 'bullish':
                trend_score += 10
        elif direction == 'SHORT':
            if h1_trend == 'bearish':
                trend_score += 15
            if m15_trend == 'bearish':
                trend_score += 15
            if m5_trend == 'bearish':
                trend_score += 10
        
        sub_scores['trend_alignment'] = trend_score
        
        # 2️⃣ 市場結構 (20%)
        structure_score = 0.0
        if (direction == 'LONG' and market_structure == 'bullish') or \
           (direction == 'SHORT' and market_structure == 'bearish'):
            structure_score = 20.0
        
        sub_scores['market_structure'] = structure_score
        
        # 3️⃣ Order Block 質量 (20%)
        ob_score = 0.0
        if order_blocks:
            relevant_obs = [
                ob for ob in order_blocks
                if (direction == 'LONG' and ob['type'] == 'bullish') or
                   (direction == 'SHORT' and ob['type'] == 'bearish')
            ]
            if relevant_obs:
                # 取最近的 OB
                nearest_ob = min(relevant_obs, key=lambda x: abs(x['zone'][0] - current_price))
                ob_distance = abs(nearest_ob['zone'][0] - current_price) / current_price
                
                # 距離越近分數越高
                if ob_distance < 0.005:  # <0.5%
                    ob_score = 20.0
                elif ob_distance < 0.01:  # <1%
                    ob_score = 15.0
                elif ob_distance < 0.02:  # <2%
                    ob_score = 10.0
                else:
                    ob_score = 5.0
        
        sub_scores['order_block'] = ob_score
        
        # 4️⃣ 動量指標 (10%)
        momentum_score = 0.0
        rsi = indicators['rsi']
        macd_hist = indicators['macd_hist']
        
        if direction == 'LONG':
            if 50 <= rsi <= 70:
                momentum_score += 5.0
            if macd_hist > 0:
                momentum_score += 5.0
        elif direction == 'SHORT':
            if 30 <= rsi <= 50:
                momentum_score += 5.0
            if macd_hist < 0:
                momentum_score += 5.0
        
        sub_scores['momentum'] = momentum_score
        
        # 5️⃣ 波動率 (10%)
        volatility_score = 0.0
        bb_width = indicators['bb_width']
        
        # 計算波動率分位數
        bb_width_series = calculate_bollinger_bands(m5_data)['width']
        bb_percentile = (bb_width_series <= bb_width).sum() / len(bb_width_series)
        
        # 中等波動率最佳
        if 0.3 <= bb_percentile <= 0.7:
            volatility_score = 10.0
        elif 0.2 <= bb_percentile <= 0.8:
            volatility_score = 7.0
        else:
            volatility_score = 4.0
        
        sub_scores['volatility'] = volatility_score
        
        # 總分
        total_score = sum(sub_scores.values())
        
        return total_score, sub_scores
    
    def _calculate_sl_tp(
        self,
        entry_price: float,
        direction: str,
        atr: float,
        order_blocks: list
    ) -> tuple:
        """計算基礎 SL/TP（不含槓桿調整）"""
        # 基礎止損：2 ATR
        base_sl_distance = atr * 2.0
        
        if direction == 'LONG':
            stop_loss = entry_price - base_sl_distance
            take_profit = entry_price + (base_sl_distance * 1.5)
        else:  # SHORT
            stop_loss = entry_price + base_sl_distance
            take_profit = entry_price - (base_sl_distance * 1.5)
        
        return stop_loss, take_profit
    
    def _estimate_win_probability(
        self,
        confidence_score: float,
        rr_ratio: float,
        direction: str,
        market_structure: str
    ) -> float:
        """
        預估勝率（基於歷史統計）
        
        邏輯：
        - 信心度 90+ → 勝率 65-70%
        - 信心度 70-90 → 勝率 60-65%
        - 信心度 50-70 → 勝率 55-60%
        - R:R 越高，勝率應略低（風險補償）
        """
        # 基礎勝率（基於信心度）
        if confidence_score >= 90:
            base_win_rate = 0.675
        elif confidence_score >= 70:
            base_win_rate = 0.625
        elif confidence_score >= 50:
            base_win_rate = 0.575
        else:
            base_win_rate = 0.55
        
        # R:R 調整
        rr_adjustment = -0.02 * (rr_ratio - 1.5)  # R:R 每高 1.0，勝率降 2%
        
        # 市場結構調整
        structure_bonus = 0.02 if (
            (direction == 'LONG' and market_structure == 'bullish') or
            (direction == 'SHORT' and market_structure == 'bearish')
        ) else 0.0
        
        win_probability = base_win_rate + rr_adjustment + structure_bonus
        
        # 限制範圍
        return max(0.50, min(0.75, win_probability))
    
    def _generate_reasoning(
        self,
        direction: str,
        sub_scores: Dict,
        market_structure: str,
        h1_trend: str,
        m15_trend: str,
        m5_trend: str
    ) -> str:
        """生成信號推理說明"""
        reasons = []
        
        # 趨勢對齊
        if sub_scores['trend_alignment'] >= 35:
            reasons.append(f"三時間框架趨勢強勁對齊({h1_trend}/{m15_trend}/{m5_trend})")
        
        # 市場結構
        if sub_scores['market_structure'] >= 15:
            reasons.append(f"市場結構支持{direction}({market_structure})")
        
        # OB 質量
        if sub_scores['order_block'] >= 15:
            reasons.append("Order Block 距離理想")
        
        # 動量
        if sub_scores['momentum'] >= 8:
            reasons.append("動量指標確認")
        
        # 波動率
        if sub_scores['volatility'] >= 8:
            reasons.append("波動率適中")
        
        return " | ".join(reasons)
