"""
ICT/SMC 策略引擎
職責：Order Blocks、Liquidity Zones、Market Structure 分析、信心度評分
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from src.utils.logger_factory import get_logger
from src.core.elite import EliteTechnicalEngine
from src.config import Config

logger = get_logger(__name__)


class ICTStrategy:
    """ICT/SMC 策略引擎"""
    
    def __init__(self):
        """初始化策略引擎"""
        self.config = Config
        self.tech_engine = EliteTechnicalEngine()
        logger.info("✅ v3.20: ICTStrategy 使用 EliteTechnicalEngine 统一技术指标计算")
    
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
            
            h1_trend = self._determine_trend(h1_data)
            m15_trend = self._determine_trend(m15_data)
            m5_trend = self._determine_trend(m5_data)
            logger.debug(f"{symbol}: 趨勢檢測 - 1h:{h1_trend}, 15m:{m15_trend}, 5m:{m5_trend}")
            
            # ✅ v3.20.2: 使用 EliteTechnicalEngine 的 ICT 函数
            market_structure_result = self.tech_engine.calculate('market_structure', m15_data, lookback=10)
            market_structure = market_structure_result.value.get('trend', 'neutral')
            
            order_blocks_result = self.tech_engine.calculate('order_blocks', m15_data, lookback=self.config.OB_LOOKBACK)
            order_blocks = order_blocks_result.value
            
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
                logger.debug(
                    f"{symbol}: 拒絕 - 趨勢不對齊 "
                    f"(1h:{h1_trend}, 15m:{m15_trend}, 5m:{m5_trend}, structure:{market_structure})"
                )
                return None
            
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
                direction=signal_direction
            )
            
            if confidence_score < self.config.MIN_CONFIDENCE:
                logger.debug(
                    f"{symbol}: 拒絕 - 信心度不足 "
                    f"({confidence_score:.1%} < {self.config.MIN_CONFIDENCE:.1%})"
                )
                return None
            
            entry_price, stop_loss, take_profit = self._calculate_levels(
                signal_direction,
                current_price,
                m5_data,
                order_blocks,
                liquidity_zones
            )
            
            indicators_data = self._collect_indicators(m15_data, m5_data)
            
            signal = {
                'symbol': symbol,
                'direction': signal_direction,
                'confidence': confidence_score,
                'scores': sub_scores,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': datetime.now(),
                'trends': {
                    'h1': h1_trend,
                    'm15': m15_trend,
                    'm5': m5_trend
                },
                'timeframes': {
                    '1h': h1_trend,
                    '15m': m15_trend,
                    '5m': m5_trend
                },
                'market_structure': market_structure,
                'order_blocks': order_blocks,
                'liquidity_zones': liquidity_zones,
                'current_price': current_price,
                'indicators': indicators_data
            }
            
            # v3.9.2.3: 简化日志输出
            logger.debug(
                f"✅ {symbol} {signal_direction} | 信心度: {confidence_score:.1%} | "
                f"趨勢: {h1_trend}/{m15_trend}/{m5_trend}"
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"分析 {symbol} 失敗: {e}")
            return None
    
    def _validate_data(self, multi_tf_data: Dict[str, pd.DataFrame]) -> bool:
        """驗證數據完整性"""
        required_timeframes = ['1h', '15m', '5m']
        
        for tf in required_timeframes:
            if tf not in multi_tf_data:
                return False
            
            df = multi_tf_data[tf]
            if df.empty or len(df) < 50:
                return False
        
        return True
    
    def _determine_trend(self, df: pd.DataFrame) -> str:
        """
        判斷趨勢方向 - v3.10.0 增強版（ADX過濾 + EMA斜率）
        
        Args:
            df: K線數據
        
        Returns:
            str: 趨勢方向 ('bullish', 'bearish', 'neutral')
        """
        if df.empty or len(df) < self.config.EMA_SLOW:
            return "neutral"
        
        # ✅ v3.20: 使用 EliteTechnicalEngine
        ema_fast_result = self.tech_engine.calculate('ema', df, period=self.config.EMA_FAST)
        ema_slow_result = self.tech_engine.calculate('ema', df, period=self.config.EMA_SLOW)
        ema_fast = ema_fast_result.value
        ema_slow = ema_slow_result.value
        
        if ema_fast.empty or ema_slow.empty:
            return "neutral"
        
        fast_val = float(ema_fast.iloc[-1])
        slow_val = float(ema_slow.iloc[-1])
        try:
            # ✅ v3.20: 使用 EliteTechnicalEngine（键名：di_plus/di_minus）
            adx_result = self.tech_engine.calculate('adx', df, period=self.config.ADX_PERIOD)
            adx_dict = adx_result.value
            adx = adx_dict['adx']
            plus_di = adx_dict['di_plus']
            minus_di = adx_dict['di_minus']
            if not adx.empty:
                adx_val = float(adx.iloc[-1])
                
                # ADX < 20：無趨勢（震盪市），拒絕信號
                if adx_val < self.config.ADX_TREND_THRESHOLD:
                    logger.debug(f"ADX過濾：{adx_val:.1f} < {self.config.ADX_TREND_THRESHOLD} （震盪市）")
                    return "neutral"
        except Exception as e:
            logger.debug(f"ADX計算失敗（降級使用EMA）: {e}")
        # ✅ v3.20.2: 使用 EliteTechnicalEngine 的 ema_slope
        try:
            ema_fast_slope_result = self.tech_engine.calculate('ema_slope', ema_fast, lookback=3)
            ema_fast_slope = ema_fast_slope_result.value
            if not ema_fast_slope.empty:
                slope_val = float(ema_fast_slope.iloc[-1])
                slope_threshold = self.config.EMA_SLOPE_THRESHOLD
                
                # 快線 > 慢線 但斜率平坦 → 趨勢可能衰竭
                if fast_val > slow_val:
                    if slope_val < slope_threshold:
                        logger.debug(f"EMA斜率過低：{slope_val:.3f}% （趨勢衰竭）")
                        return "neutral"
                    return "bullish"
                elif fast_val < slow_val:
                    if slope_val > -slope_threshold:
                        logger.debug(f"EMA斜率過低：{slope_val:.3f}% （趨勢衰竭）")
                        return "neutral"
                    return "bearish"
        except Exception as e:
            logger.debug(f"EMA斜率計算失敗（降級使用簡單EMA）: {e}")
        
        # 降級邏輯：僅使用EMA交叉
        if fast_val > slow_val:
            return "bullish"
        elif fast_val < slow_val:
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
        
        # ✅ v3.20.2: 使用 EliteTechnicalEngine 的 swing_points
        swing_points_result = self.tech_engine.calculate('swing_points', df, lookback=5)
        highs = swing_points_result.value['highs']
        lows = swing_points_result.value['lows']
        
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
        """
        判斷信號方向
        
        策略：1h 和 15m 趨勢一致即可（5m 用於找入場點，不要求完全一致）
        """
        # 統一轉換為小寫進行比較
        h1_trend_lower = h1_trend.lower()
        m15_trend_lower = m15_trend.lower()
        m5_trend_lower = m5_trend.lower()
        market_structure_lower = market_structure.lower()
        
        # 优先级1: 三个时間框架完全一致（最高置信度）
        if h1_trend_lower == m15_trend_lower == m5_trend_lower == "bullish":
            if market_structure_lower in ["bullish", "neutral"]:
                return "LONG"
        elif h1_trend_lower == m15_trend_lower == m5_trend_lower == "bearish":
            if market_structure_lower in ["bearish", "neutral"]:
                return "SHORT"
        
        # 优先级2: 1h 和 15m 一致（5m 可以不同，用于精準入場）
        if h1_trend_lower == m15_trend_lower == "bullish":
            if market_structure_lower in ["bullish", "neutral"]:
                return "LONG"
        elif h1_trend_lower == m15_trend_lower == "bearish":
            if market_structure_lower in ["bearish", "neutral"]:
                return "SHORT"
        
        # 优先级3: 1h 有明确趨勢，15m 是 neutral（等待 15m 確認）
        if h1_trend_lower == "bullish" and m15_trend_lower == "neutral":
            if m5_trend_lower == "bullish" and market_structure_lower == "bullish":
                return "LONG"
        elif h1_trend_lower == "bearish" and m15_trend_lower == "neutral":
            if m5_trend_lower == "bearish" and market_structure_lower == "bearish":
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
        h1_data: pd.DataFrame,
        m15_data: pd.DataFrame,
        m5_data: pd.DataFrame,
        direction: Optional[str] = None
    ) -> Tuple[float, Dict]:
        """
        計算信心度評分（新框架版本）
        
        五大子指標：
        1. 趨勢對齊 40% - 基於 EMA
        2. 市場結構 20% - 基於分形高低點
        3. 價格位置 20% - 距離 OB 的 ATR 距離
        4. 動量指標 10% - RSI + MACD 同向確認
        5. 波動率適宜度 10% - 布林帶寬分位數
        
        Returns:
            Tuple[float, Dict]: (信心度分數 0-1, 各子指標得分)
        """
        weights = self.config.CONFIDENCE_WEIGHTS
        scores = {}
        
        # ✅ 修复：根据趋势方向动态判断趋势对齐（移除LONG偏向）
        trend_alignment_count = 0
        h1_lower = h1_trend.lower()
        
        # ✅ v3.20: 使用 EliteTechnicalEngine
        ema20_5m = self.tech_engine.calculate('ema', m5_data, period=20).value
        if not ema20_5m.empty:
            current_price = m5_data['close'].iloc[-1]
            ema_val = ema20_5m.iloc[-1]
            # LONG: 价格 > EMA，SHORT: 价格 < EMA
            if (h1_lower == "bullish" and current_price > ema_val) or \
               (h1_lower == "bearish" and current_price < ema_val):
                trend_alignment_count += 1
        
        ema50_15m = self.tech_engine.calculate('ema', m15_data, period=50).value
        if not ema50_15m.empty:
            current_price = m15_data['close'].iloc[-1]
            ema_val = ema50_15m.iloc[-1]
            # LONG: 价格 > EMA，SHORT: 价格 < EMA
            if (h1_lower == "bullish" and current_price > ema_val) or \
               (h1_lower == "bearish" and current_price < ema_val):
                trend_alignment_count += 1
        
        ema100_1h = self.tech_engine.calculate('ema', h1_data, period=100).value
        if not ema100_1h.empty:
            current_price = h1_data['close'].iloc[-1]
            ema_val = ema100_1h.iloc[-1]
            # LONG: 价格 > EMA，SHORT: 价格 < EMA
            if (h1_lower == "bullish" and current_price > ema_val) or \
               (h1_lower == "bearish" and current_price < ema_val):
                trend_alignment_count += 1
        
        trend_score = trend_alignment_count / 3.0
        scores['trend_alignment'] = trend_score
        
        # 統一轉換為小寫
        ms_lower = market_structure.lower()
        h1_lower = h1_trend.lower()
        
        structure_score = 0.0
        if ms_lower == "bullish" and h1_lower == "bullish":
            structure_score = 1.0
        elif ms_lower == "bearish" and h1_lower == "bearish":
            structure_score = 1.0
        elif ms_lower == "neutral" or (ms_lower != h1_lower and h1_lower != "neutral"):
            structure_score = 0.5
        scores['market_structure'] = structure_score
        
        position_score = 0.0
        if order_blocks and direction:
            # ✅ v3.20: 使用 EliteTechnicalEngine
            atr = self.tech_engine.calculate('atr', m15_data).value
            atr_value = atr.iloc[-1] if not atr.empty else current_price * 0.01
            
            relevant_obs = [ob for ob in order_blocks if ob['type'] == direction.lower()]
            
            if relevant_obs:
                nearest_ob = min(relevant_obs, key=lambda x: abs(x['price'] - current_price))
                
                if direction == "LONG":
                    distance_atr = (current_price - nearest_ob['zone_low']) / atr_value
                    
                    if current_price > nearest_ob['zone_high']:
                        position_score = 0.3
                    elif distance_atr <= 0.5:
                        position_score = 1.0
                    elif distance_atr <= 1.0:
                        position_score = 0.8
                    elif distance_atr <= 1.5:
                        position_score = 0.6
                    elif distance_atr <= 2.0:
                        position_score = 0.4
                    else:
                        position_score = 0.2
                
                elif direction == "SHORT":
                    distance_atr = (nearest_ob['zone_high'] - current_price) / atr_value
                    
                    if current_price < nearest_ob['zone_low']:
                        position_score = 0.3
                    elif distance_atr <= 0.5:
                        position_score = 1.0
                    elif distance_atr <= 1.0:
                        position_score = 0.8
                    elif distance_atr <= 1.5:
                        position_score = 0.6
                    elif distance_atr <= 2.0:
                        position_score = 0.4
                    else:
                        position_score = 0.2
        
        scores['price_position'] = position_score
        
        # ✅ v3.20: 使用 EliteTechnicalEngine
        rsi = self.tech_engine.calculate('rsi', m5_data).value
        macd_result = self.tech_engine.calculate('macd', m5_data).value
        
        momentum_score = 0.0
        if not rsi.empty and not macd_result['macd'].empty:
            macd_data = macd_result  # 兼容原代码
            rsi_val = rsi.iloc[-1]
            macd_val = macd_data['macd'].iloc[-1]
            signal_val = macd_data['signal'].iloc[-1]
            
            # ✅ 修复：RSI范围对称于50中线
            rsi_bullish = 50 < rsi_val < 70  # 看涨：RSI在50-70之间
            rsi_bearish = 30 < rsi_val < 50  # 看跌：RSI在30-50之间
            macd_bullish = macd_val > signal_val
            macd_bearish = macd_val < signal_val
            
            if h1_trend.lower() == "bullish":
                if rsi_bullish and macd_bullish:
                    momentum_score = 1.0
                elif rsi_bullish or macd_bullish:
                    momentum_score = 0.6
            elif h1_trend.lower() == "bearish":
                if rsi_bearish and macd_bearish:
                    momentum_score = 1.0
                elif rsi_bearish or macd_bearish:
                    momentum_score = 0.6
        
        scores['momentum'] = momentum_score
        
        # ✅ v3.20: 使用 EliteTechnicalEngine
        bb_result = self.tech_engine.calculate('bb', m15_data)
        bb_data = bb_result.value
        bb_upper = bb_data['upper']
        bb_middle = bb_data['middle']
        bb_lower = bb_data['lower']
        
        volatility_score = 0.0
        if not bb_upper.empty and len(m15_data) >= 168:
            bb_widths = []
            for i in range(max(0, len(m15_data) - 168), len(m15_data)):
                if i >= 20:
                    width = (bb_upper.iloc[i] - bb_lower.iloc[i]) / bb_middle.iloc[i]
                    bb_widths.append(width)
            
            if bb_widths:
                current_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_middle.iloc[-1]
                percentile_25 = np.percentile(bb_widths, 25)
                percentile_75 = np.percentile(bb_widths, 75)
                
                if percentile_25 <= current_width <= percentile_75:
                    volatility_score = 1.0
                elif current_width < percentile_25:
                    volatility_score = 0.6
                else:
                    volatility_score = 0.4
        
        scores['volatility'] = volatility_score
        
        confidence = sum(
            scores[key] * weights[key]
            for key in weights.keys()
        )
        
        return min(1.0, max(0.0, confidence)), scores
    
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
    
    def _collect_indicators(self, m15_data: pd.DataFrame, m5_data: pd.DataFrame) -> Dict:
        """
        收集所有技術指標數據用於 ML 訓練
        
        Args:
            m15_data: 15分鐘數據
            m5_data: 5分鐘數據
        
        Returns:
            Dict: 技術指標數據
        """
        indicators = {}
        
        try:
            # ✅ v3.20: 使用 EliteTechnicalEngine
            rsi = self.tech_engine.calculate('rsi', m5_data).value
            if not rsi.empty:
                indicators['rsi'] = float(rsi.iloc[-1])
            
            macd_result = self.tech_engine.calculate('macd', m5_data).value
            if not macd_result['macd'].empty:
                indicators['macd'] = float(macd_result['macd'].iloc[-1])
                indicators['macd_signal'] = float(macd_result['signal'].iloc[-1])
                indicators['macd_histogram'] = float(macd_result['histogram'].iloc[-1])
            
            atr = self.tech_engine.calculate('atr', m15_data).value
            if not atr.empty:
                indicators['atr'] = float(atr.iloc[-1])
            
            bb_result = self.tech_engine.calculate('bb', m15_data).value
            if not bb_result['upper'].empty:
                indicators['bb_upper'] = float(bb_result['upper'].iloc[-1])
                indicators['bb_middle'] = float(bb_result['middle'].iloc[-1])
                indicators['bb_lower'] = float(bb_result['lower'].iloc[-1])
                bb_width = (bb_result['upper'].iloc[-1] - bb_result['lower'].iloc[-1]) / bb_result['middle'].iloc[-1]
                indicators['bb_width_pct'] = float(bb_width)
            
            if len(m15_data) >= 20 and 'volume' in m15_data.columns:
                volume_sma = m15_data['volume'].rolling(window=20).mean()
                if not volume_sma.empty and volume_sma.iloc[-1] > 0:
                    indicators['volume_sma_ratio'] = float(m15_data['volume'].iloc[-1] / volume_sma.iloc[-1])
            
            ema50 = self.tech_engine.calculate('ema', m15_data, period=50).value
            if not ema50.empty:
                price = float(m15_data['close'].iloc[-1])
                indicators['price_vs_ema50'] = (price - float(ema50.iloc[-1])) / float(ema50.iloc[-1])
            
            ema200 = self.tech_engine.calculate('ema', m15_data, period=200).value
            if not ema200.empty:
                price = float(m15_data['close'].iloc[-1])
                indicators['price_vs_ema200'] = (price - float(ema200.iloc[-1])) / float(ema200.iloc[-1])
                
        except Exception as e:
            logger.error(f"收集指標數據失敗: {e}")
        
        return indicators
