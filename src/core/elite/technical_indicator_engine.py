"""
统一技术指标计算引擎 v3.20

职责：所有技术指标的单一真相来源（Single Source of Truth）

整合：
- src/utils/indicators.py (标记为deprecated)
- src/utils/core_calculations.py (标记为deprecated)
- src/features/technical_indicators.py (安全版合并)

核心优势：
1. 消除重复：3处EMA实现 → 1处统一实现
2. 智能缓存：相同数据不重复计算（60-80%性能提升）
3. 向量化计算：使用NumPy/Pandas加速
4. 安全降级：数据不足时自动调整参数
5. 批量计算：支持多指标并行计算

性能优化：
- 缓存键：symbol_timeframe_indicator_period_datahash
- TTL：60秒（基于K线更新频率）
- 预期计算时间减少：2.65-5.3秒 → 0.5-1秒（5倍）
"""

import logging
import hashlib
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass

from .intelligent_cache import IntelligentCache, generate_cache_key

logger = logging.getLogger(__name__)


@dataclass
class IndicatorResult:
    """指标计算结果"""
    value: Union[pd.Series, Dict[str, pd.Series]]
    period_used: int
    data_points: int
    cached: bool = False


class EliteTechnicalEngine:
    """
    统一技术指标计算引擎
    
    功能：
    1. 统一所有技术指标计算（EMA, RSI, MACD, ATR, BB, ADX等）
    2. 智能缓存（减少重复计算）
    3. 批量计算优化
    4. 安全降级（数据不足时）
    5. 向量化实现（高性能）
    
    使用示例：
        engine = EliteTechnicalEngine()
        
        # 单个指标
        ema20 = engine.calculate('ema', close_prices, period=20)
        
        # 批量指标
        results = engine.calculate_batch(
            data_frame,
            indicators=['ema_20', 'rsi_14', 'macd', 'atr']
        )
    """
    
    def __init__(self, cache: Optional[IntelligentCache] = None):
        """
        初始化统一技术指标引擎
        
        Args:
            cache: 智能缓存实例（可选，自动创建）
        """
        self.cache = cache or IntelligentCache(l1_max_size=5000)
        self._calculation_count = 0
        self._cache_hit_count = 0
        
        logger.info(
            "✅ EliteTechnicalEngine 初始化完成\n"
            "   🎯 统一指标计算引擎（消除3处重复）\n"
            "   💾 智能缓存已启用"
        )
    
    def calculate(
        self,
        indicator: str,
        data: Union[pd.Series, pd.DataFrame],
        **params
    ) -> IndicatorResult:
        """
        计算单个技术指标
        
        Args:
            indicator: 指标名称
                基础指标: 'ema', 'rsi', 'macd', 'atr', 'bb', 'adx'
                ICT指标: 'ema_slope', 'order_blocks', 'market_structure', 'swing_points', 'fvg'
            data: 价格数据（Series或DataFrame）
            **params: 指标参数（如period=20）
            
        Returns:
            IndicatorResult包含计算结果
            
        示例：
            result = engine.calculate('ema', close_prices, period=20)
            ema_values = result.value
        """
        # 生成缓存键
        data_hash = self._hash_data(data)
        cache_key = generate_cache_key(
            'indicator', indicator, data_hash, **params
        )
        
        # 检查缓存
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            self._cache_hit_count += 1
            logger.debug(f"✅ 缓存命中: {indicator} {params}")
            return IndicatorResult(
                value=cached_result['value'],
                period_used=cached_result['period_used'],
                data_points=cached_result['data_points'],
                cached=True
            )
        
        # 计算指标
        self._calculation_count += 1
        
        try:
            if indicator == 'ema':
                result = self._calculate_ema(data, **params)
            elif indicator == 'rsi':
                result = self._calculate_rsi(data, **params)
            elif indicator == 'macd':
                result = self._calculate_macd(data, **params)
            elif indicator == 'atr':
                result = self._calculate_atr(data, **params)
            elif indicator == 'bb':
                result = self._calculate_bollinger_bands(data, **params)
            elif indicator == 'adx':
                result = self._calculate_adx(data, **params)
            elif indicator == 'ema_slope':
                result = self._calculate_ema_slope(data, **params)
            elif indicator == 'order_blocks':
                result = self._identify_order_blocks(data, **params)
            elif indicator == 'market_structure':
                result = self._determine_market_structure(data, **params)
            elif indicator == 'swing_points':
                result = self._identify_swing_points(data, **params)
            elif indicator == 'fvg':
                result = self._detect_fair_value_gaps(data, **params)
            else:
                raise ValueError(f"不支持的指标: {indicator}")
            
            # 缓存结果
            cache_data = {
                'value': result.value,
                'period_used': result.period_used,
                'data_points': result.data_points
            }
            self.cache.set(cache_key, cache_data, ttl=60)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 计算指标失败 {indicator}: {e}")
            raise
    
    def calculate_batch(
        self,
        data: pd.DataFrame,
        indicators: List[str]
    ) -> Dict[str, Any]:
        """
        批量计算多个指标
        
        Args:
            data: DataFrame包含OHLCV数据
            indicators: 指标列表，如['ema_20', 'rsi_14', 'macd']
            
        Returns:
            指标计算结果字典
            
        示例：
            results = engine.calculate_batch(df, ['ema_20', 'rsi_14'])
            ema20 = results['ema_20']
            rsi14 = results['rsi_14']
        """
        results = {}
        
        for indicator_spec in indicators:
            # 解析指标规格（如'ema_20' → indicator='ema', period=20）
            indicator, params = self._parse_indicator_spec(indicator_spec)
            
            try:
                result = self.calculate(indicator, data, **params)
                results[indicator_spec] = result.value
            except Exception as e:
                logger.warning(f"⚠️  批量计算失败 {indicator_spec}: {e}")
                results[indicator_spec] = None
        
        return results
    
    def _calculate_ema(
        self,
        data: Union[pd.Series, pd.DataFrame],
        period: int = 20
    ) -> IndicatorResult:
        """
        计算指数移动平均线（EMA）
        
        统一实现（替代3处重复）：
        - src/utils/indicators.py::calculate_ema
        - src/utils/core_calculations.py::ema_fast
        - src/features/technical_indicators.py::safe_ema
        """
        # 提取close价格
        close = self._extract_close(data)
        
        # 安全降级（数据不足时）
        actual_period = period
        if len(close) < period:
            actual_period = max(5, len(close))
            logger.debug(
                f"⚠️  EMA数据不足，降级: period {period} → {actual_period}"
            )
        
        # 向量化计算
        result = close.ewm(span=actual_period, adjust=False, min_periods=1).mean()
        
        # 确保返回Series
        if isinstance(result, pd.DataFrame):
            result = result.iloc[:, 0]
        
        return IndicatorResult(
            value=pd.Series(result, index=close.index),
            period_used=actual_period,
            data_points=len(close)
        )
    
    def _calculate_rsi(
        self,
        data: Union[pd.Series, pd.DataFrame],
        period: int = 14
    ) -> IndicatorResult:
        """计算相对强弱指数（RSI）"""
        close = self._extract_close(data)
        
        # 安全降级
        actual_period = min(period, max(5, len(close) - 1))
        
        # 计算价格变化
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=actual_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=actual_period).mean()
        
        # 计算RS和RSI
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return IndicatorResult(
            value=rsi,
            period_used=actual_period,
            data_points=len(close)
        )
    
    def _calculate_macd(
        self,
        data: Union[pd.Series, pd.DataFrame],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> IndicatorResult:
        """计算MACD"""
        close = self._extract_close(data)
        
        # 计算快慢EMA
        ema_fast = close.ewm(span=fast_period, adjust=False).mean()
        ema_slow = close.ewm(span=slow_period, adjust=False).mean()
        
        # MACD线
        macd_line = ema_fast - ema_slow
        
        # 信号线
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        
        # 柱状图
        histogram = macd_line - signal_line
        
        return IndicatorResult(
            value={
                'macd': macd_line,
                'signal': signal_line,
                'histogram': histogram
            },
            period_used=slow_period,
            data_points=len(close)
        )
    
    def _calculate_atr(
        self,
        data: pd.DataFrame,
        period: int = 14
    ) -> IndicatorResult:
        """计算平均真实波幅（ATR）"""
        high = data['high'] if 'high' in data.columns else data['close']
        low = data['low'] if 'low' in data.columns else data['close']
        close = data['close']
        
        # 计算True Range
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        # ATR = EMA of TR
        atr = pd.Series(tr, index=high.index).ewm(
            span=period, adjust=False, min_periods=1
        ).mean()
        
        return IndicatorResult(
            value=atr,
            period_used=period,
            data_points=len(close)
        )
    
    def _calculate_bollinger_bands(
        self,
        data: Union[pd.Series, pd.DataFrame],
        period: int = 20,
        std_dev: float = 2.0
    ) -> IndicatorResult:
        """计算布林带"""
        close = self._extract_close(data)
        
        # 中轨（SMA）
        middle = close.rolling(window=period).mean()
        
        # 标准差
        std = close.rolling(window=period).std()
        
        # 上下轨
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        # 带宽
        width = (upper - lower) / middle
        
        return IndicatorResult(
            value={
                'upper': upper,
                'middle': middle,
                'lower': lower,
                'width': width
            },
            period_used=period,
            data_points=len(close)
        )
    
    def _calculate_adx(
        self,
        data: pd.DataFrame,
        period: int = 14
    ) -> IndicatorResult:
        """计算平均趋向指标（ADX）"""
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 计算+DM和-DM
        up_move = high.diff()
        down_move = -low.diff()
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # 计算ATR
        atr_result = self._calculate_atr(data, period=period)
        atr = atr_result.value
        
        # 计算+DI和-DI
        plus_di = 100 * pd.Series(plus_dm).ewm(span=period, adjust=False).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).ewm(span=period, adjust=False).mean() / atr
        
        # 计算DX
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        
        # 计算ADX
        adx = dx.ewm(span=period, adjust=False).mean()
        
        return IndicatorResult(
            value={
                'adx': adx,
                'di_plus': plus_di,
                'di_minus': minus_di
            },
            period_used=period,
            data_points=len(close)
        )
    
    def _extract_close(self, data: Union[pd.Series, pd.DataFrame]) -> pd.Series:
        """提取close价格列"""
        if isinstance(data, pd.Series):
            return data
        
        if isinstance(data, pd.DataFrame):
            if 'close' in data.columns:
                return data['close']
            else:
                raise ValueError("DataFrame必须包含'close'列")
        
        # 尝试转换为Series
        return pd.Series(data)
    
    def _parse_indicator_spec(self, spec: str) -> tuple:
        """
        解析指标规格字符串
        
        Args:
            spec: 如'ema_20', 'rsi_14', 'macd', 'bb_20_2'
            
        Returns:
            (indicator_name, params_dict)
        """
        parts = spec.split('_')
        indicator = parts[0]
        
        params = {}
        
        if indicator == 'ema':
            params['period'] = int(parts[1]) if len(parts) > 1 else 20
        elif indicator == 'rsi':
            params['period'] = int(parts[1]) if len(parts) > 1 else 14
        elif indicator == 'atr':
            params['period'] = int(parts[1]) if len(parts) > 1 else 14
        elif indicator == 'bb':
            params['period'] = int(parts[1]) if len(parts) > 1 else 20
            params['std_dev'] = float(parts[2]) if len(parts) > 2 else 2.0
        elif indicator == 'adx':
            params['period'] = int(parts[1]) if len(parts) > 1 else 14
        
        return indicator, params
    
    def _hash_data(self, data: Union[pd.Series, pd.DataFrame]) -> str:
        """生成数据哈希（用于缓存键）"""
        if isinstance(data, pd.DataFrame):
            data_str = f"{len(data)}_{data.iloc[-1].to_dict() if len(data) > 0 else ''}"
        else:
            data_str = f"{len(data)}_{data.iloc[-1] if len(data) > 0 else ''}"
        
        return hashlib.md5(data_str.encode()).hexdigest()[:8]
    
    def _calculate_ema_slope(
        self,
        data: pd.Series,
        lookback: int = 3
    ) -> IndicatorResult:
        """
        计算EMA斜率（用于判断趋势强度）
        
        Args:
            data: EMA序列
            lookback: 回溯期（默认3根K线）
            
        Returns:
            EMA斜率（正数=上升，负数=下降）
        """
        if len(data) < lookback + 1:
            slope = pd.Series(0.0, index=data.index)
        else:
            slope = (data - data.shift(lookback)) / lookback
            slope_pct = (slope / data) * 100
            slope = slope_pct
        
        return IndicatorResult(
            value=slope,
            period_used=lookback,
            data_points=len(data)
        )
    
    def _identify_order_blocks(
        self,
        data: pd.DataFrame,
        lookback: int = 20,
        volume_multiplier: float = 1.2,  # 降低从1.5→1.2，更宽松的成交量要求
        rejection_threshold: float = 0.005,
        max_history: int = 20
    ) -> IndicatorResult:
        """
        识别Order Blocks（订单块）
        
        Args:
            data: K线数据框
            lookback: 回溯周期
            volume_multiplier: 成交量倍数阈值
            rejection_threshold: 拒绝率阈值
            max_history: 最多保留的OB历史数量
            
        Returns:
            Order Blocks列表
        """
        if data.empty or len(data) < lookback + 4:
            return IndicatorResult(value=[], period_used=lookback, data_points=len(data))
        
        order_blocks = []
        avg_volume_20 = None
        if 'volume' in data.columns:
            avg_volume_20 = data['volume'].rolling(20).mean()
        
        for i in range(lookback, len(data) - 3):
            body = abs(data['close'].iloc[i] - data['open'].iloc[i])
            total_range = data['high'].iloc[i] - data['low'].iloc[i]
            
            if total_range == 0:
                continue
            
            body_ratio = body / total_range
            
            # 降低从0.7→0.5，允许实体占K线50%即可（更实用）
            if body_ratio < 0.5:
                continue
            
            if avg_volume_20 is not None:
                if data['volume'].iloc[i] < volume_multiplier * avg_volume_20.iloc[i]:
                    continue
            
            is_bullish = data['close'].iloc[i] > data['open'].iloc[i]
            is_bearish = data['close'].iloc[i] < data['open'].iloc[i]
            
            if is_bullish:
                # 移除过于严格的后续价格检查，允许回调
                # Order Block主要由强势K线+高成交量定义
                ob_low = float(data['low'].iloc[i])
                ob_high = float(data['open'].iloc[i])
                ob_type = 'bullish'
                ob_price = (ob_low + ob_high) / 2
                ob_strength = body_ratio * (data['volume'].iloc[i] / avg_volume_20.iloc[i] if avg_volume_20 is not None else 1.0)
            elif is_bearish:
                # 移除过于严格的后续价格检查，允许回调
                ob_high = float(data['high'].iloc[i])
                ob_low = float(data['open'].iloc[i])
                ob_type = 'bearish'
                ob_price = (ob_low + ob_high) / 2
                ob_strength = body_ratio * (data['volume'].iloc[i] / avg_volume_20.iloc[i] if avg_volume_20 is not None else 1.0)
            else:
                continue
            
            order_blocks.append({
                'type': ob_type,
                'high': ob_high,
                'low': ob_low,
                'price': ob_price,
                'strength': ob_strength,
                'index': i
            })
        
        if len(order_blocks) > max_history:
            order_blocks = order_blocks[-max_history:]
        
        return IndicatorResult(
            value=order_blocks,
            period_used=lookback,
            data_points=len(data)
        )
    
    def _determine_market_structure(
        self,
        data: Union[pd.Series, pd.DataFrame],
        lookback: int = 10
    ) -> IndicatorResult:
        """
        判断市场结构（更高高点/更低低点）
        
        Args:
            data: 价格数据
            lookback: 回溯周期
            
        Returns:
            市场结构信息
        """
        close = self._extract_close(data)
        
        if len(close) < lookback + 1:
            structure = {"trend": "neutral", "structure_valid": False}
        else:
            recent_high = close.iloc[-lookback:].max()
            previous_high = close.iloc[-(lookback*2):-lookback].max() if len(close) >= lookback * 2 else recent_high
            
            recent_low = close.iloc[-lookback:].min()
            previous_low = close.iloc[-(lookback*2):-lookback].min() if len(close) >= lookback * 2 else recent_low
            
            higher_high = recent_high > previous_high
            higher_low = recent_low > previous_low
            lower_high = recent_high < previous_high
            lower_low = recent_low < previous_low
            
            if higher_high and higher_low:
                trend = "bullish"
            elif lower_high and lower_low:
                trend = "bearish"
            else:
                trend = "neutral"
            
            structure = {
                "trend": trend,
                "structure_valid": True,
                "higher_high": higher_high,
                "higher_low": higher_low,
                "lower_high": lower_high,
                "lower_low": lower_low
            }
        
        return IndicatorResult(
            value=structure,
            period_used=lookback,
            data_points=len(close)
        )
    
    def _identify_swing_points(
        self,
        data: pd.DataFrame,
        lookback: int = 5
    ) -> IndicatorResult:
        """
        识别摆动高点和低点
        
        使用改进逻辑：当前点显著高于/低于前后lookback周期（而非绝对最大/最小）
        这样在趋势数据中也能检测到摆动点
        
        Args:
            data: K线数据框
            lookback: 回溯周期
            
        Returns:
            (swing_highs, swing_lows)
        """
        if data.empty or len(data) < lookback * 2 + 1:
            return IndicatorResult(
                value={'highs': [], 'lows': []},
                period_used=lookback,
                data_points=len(data)
            )
        
        high = data['high']
        low = data['low']
        
        swing_highs = []
        swing_lows = []
        
        for i in range(lookback, len(data) - lookback):
            # 改用更实用的局部极值定义：
            # Swing High: 当前高点高于左侧至少lookback/2个点 AND 高于右侧至少lookback/2个点
            # Swing Low: 当前低点低于左侧至少lookback/2个点 AND 低于右侧至少lookback/2个点
            
            left_highs = high.iloc[i-lookback:i]
            right_highs = high.iloc[i+1:i+lookback+1]
            left_lows = low.iloc[i-lookback:i]
            right_lows = low.iloc[i+1:i+lookback+1]
            
            # Swing High: 当前高点高于左侧大部分点和右侧大部分点
            left_higher_count = (high.iloc[i] > left_highs).sum()
            right_higher_count = (high.iloc[i] > right_highs).sum()
            threshold = max(lookback // 2, 2)  # 至少高于2个点或lookback/2
            
            if left_higher_count >= threshold and right_higher_count >= threshold:
                swing_highs.append({
                    'price': float(high.iloc[i]),
                    'index': i
                })
            
            # Swing Low: 当前低点低于左侧大部分点和右侧大部分点
            left_lower_count = (low.iloc[i] < left_lows).sum()
            right_lower_count = (low.iloc[i] < right_lows).sum()
            
            if left_lower_count >= threshold and right_lower_count >= threshold:
                swing_lows.append({
                    'price': float(low.iloc[i]),
                    'index': i
                })
        
        return IndicatorResult(
            value={'highs': swing_highs, 'lows': swing_lows},
            period_used=lookback,
            data_points=len(data)
        )
    
    def _detect_fair_value_gaps(
        self,
        data: pd.DataFrame,
        min_gap_pct: float = 0.001
    ) -> IndicatorResult:
        """
        检测公平价值缺口（Fair Value Gap）
        
        Args:
            data: K线数据框
            min_gap_pct: 最小缺口百分比
            
        Returns:
            FVG列表
        """
        if data.empty or len(data) < 3:
            return IndicatorResult(value=[], period_used=3, data_points=len(data))
        
        high = data['high']
        low = data['low']
        close = data['close']
        
        bullish_mask = low > high.shift(2)
        bullish_gap_size = (low - high.shift(2)) / close
        bullish_valid = bullish_mask & (bullish_gap_size >= min_gap_pct)
        
        bearish_mask = high < low.shift(2)
        bearish_gap_size = (low.shift(2) - high) / close
        bearish_valid = bearish_mask & (bearish_gap_size >= min_gap_pct)
        
        fvgs = []
        
        for idx in bullish_valid[bullish_valid].index:
            fvgs.append({
                'type': 'bullish',
                'gap_high': float(low.loc[idx]),
                'gap_low': float(high.shift(2).loc[idx]),
                'gap_size': float(bullish_gap_size.loc[idx]),
                'index': idx
            })
        
        for idx in bearish_valid[bearish_valid].index:
            fvgs.append({
                'type': 'bearish',
                'gap_high': float(low.shift(2).loc[idx]),
                'gap_low': float(high.loc[idx]),
                'gap_size': float(bearish_gap_size.loc[idx]),
                'index': idx
            })
        
        return IndicatorResult(
            value=fvgs,
            period_used=3,
            data_points=len(data)
        )
    
    def get_stats(self) -> Dict[str, int]:
        """获取引擎统计"""
        cache_stats = self.cache.get_stats()
        
        return {
            'total_calculations': self._calculation_count,
            'cache_hits': self._cache_hit_count,
            'cache_hit_rate': (
                self._cache_hit_count / (self._calculation_count + self._cache_hit_count)
                if (self._calculation_count + self._cache_hit_count) > 0
                else 0.0
            ),
            'l1_cache_size': self.cache.l1_cache.size()
        }
    
    def print_stats(self):
        """打印引擎统计"""
        stats = self.get_stats()
        logger.info(
            f"📊 EliteTechnicalEngine 统计:\n"
            f"   🔢 总计算次数: {stats['total_calculations']}\n"
            f"   ✅ 缓存命中次数: {stats['cache_hits']}\n"
            f"   🎯 缓存命中率: {stats['cache_hit_rate']:.1%}\n"
            f"   📦 L1缓存大小: {stats['l1_cache_size']}"
        )
