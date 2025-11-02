"""
共享指标计算管道（v3.18.8+）
职责：统一技术指标计算，避免重复代码，提供缓存机制

⚠️⚠️⚠️ DEPRECATED v3.20.0 ⚠️⚠️⚠️

本模块已被 src.core.elite.EliteTechnicalEngine 替代。

请使用新的统一引擎：
    from src.core.elite import EliteTechnicalEngine
    
    engine = EliteTechnicalEngine()
    result = engine.calculate('ema', data, period=20)
    
优势：
- ✅ 智能缓存：L1内存缓存（5000条目）
- ✅ 统一接口：所有指标统一调用方式
- ✅ 批量计算：支持多指标并行计算
- ✅ 安全降级：数据不足时自动调整

本文件将在 v3.21.0 移除。
"""

import warnings
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging
import hashlib
import time
from functools import lru_cache

logger = logging.getLogger(__name__)

# 发出弃用警告
warnings.warn(
    "src.utils.indicator_pipeline.IndicatorPipeline 已弃用，请使用 src.core.elite.EliteTechnicalEngine",
    DeprecationWarning,
    stacklevel=2
)


class IndicatorPipeline:
    """
    技术指标计算管道
    
    特性：
    - 统一的指标计算接口
    - 基于DataFrame哈希的智能缓存
    - 避免重复计算，提升性能
    """
    
    def __init__(self, cache_size: int = 256, cache_ttl: int = 60):
        """
        初始化指标管道
        
        Args:
            cache_size: LRU缓存大小
            cache_ttl: 缓存过期时间（秒）
        """
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[float, any]] = {}  # key: (timestamp, value)
        self._cache_size = cache_size
        logger.info(f"✅ IndicatorPipeline initialized (cache_size={cache_size}, ttl={cache_ttl}s)")
    
    def _get_cache_key(self, symbol: str, timeframe: str, df_hash: str, indicator: str) -> str:
        """生成缓存键"""
        return f"{symbol}_{timeframe}_{indicator}_{df_hash}"
    
    def _get_df_hash(self, df: pd.DataFrame) -> str:
        """
        生成DataFrame唯一哈希（基于最后N行数据）
        
        Args:
            df: K线数据
            
        Returns:
            哈希字符串
        """
        if df.empty:
            return "empty"
        
        # 使用最后50行的close价格和timestamp生成哈希
        last_rows = df.tail(50)
        data_str = f"{last_rows['close'].values.tobytes()}{last_rows.index[-1]}"
        return hashlib.md5(data_str.encode()).hexdigest()[:16]
    
    def _check_cache(self, cache_key: str) -> Optional[any]:
        """检查缓存是否有效"""
        if cache_key in self._cache:
            timestamp, value = self._cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return value
            else:
                del self._cache[cache_key]
        return None
    
    def _set_cache(self, cache_key: str, value: any):
        """设置缓存"""
        # 简单的LRU：当缓存满时清理旧条目
        if len(self._cache) >= self._cache_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]
        
        self._cache[cache_key] = (time.time(), value)
    
    def calculate_ema(
        self,
        df: pd.DataFrame,
        period: int,
        symbol: str = "",
        timeframe: str = "",
        use_cache: bool = True
    ) -> pd.Series:
        """
        计算EMA（指数移动平均线）
        
        Args:
            df: K线数据（必须有close列）
            period: EMA周期
            symbol: 交易对（用于缓存）
            timeframe: 时间框架（用于缓存）
            use_cache: 是否使用缓存
            
        Returns:
            EMA序列
        """
        if use_cache and symbol and timeframe:
            df_hash = self._get_df_hash(df)
            cache_key = self._get_cache_key(symbol, timeframe, df_hash, f"ema{period}")
            cached = self._check_cache(cache_key)
            if cached is not None:
                return cached
        
        ema = df['close'].ewm(span=period, adjust=False).mean()
        
        if use_cache and symbol and timeframe:
            self._set_cache(cache_key, ema)
        
        return ema
    
    def calculate_macd(
        self,
        df: pd.DataFrame,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        symbol: str = "",
        timeframe: str = "",
        use_cache: bool = True
    ) -> Dict[str, pd.Series]:
        """
        计算MACD指标
        
        Args:
            df: K线数据
            fast_period: 快线周期
            slow_period: 慢线周期
            signal_period: 信号线周期
            symbol: 交易对
            timeframe: 时间框架
            use_cache: 是否使用缓存
            
        Returns:
            Dict包含 macd, signal, histogram
        """
        if use_cache and symbol and timeframe:
            df_hash = self._get_df_hash(df)
            cache_key = self._get_cache_key(symbol, timeframe, df_hash, f"macd_{fast_period}_{slow_period}_{signal_period}")
            cached = self._check_cache(cache_key)
            if cached is not None:
                return cached
        
        ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
        
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=signal_period, adjust=False).mean()
        histogram = macd - signal
        
        result = {
            'macd': macd,
            'signal': signal,
            'histogram': histogram
        }
        
        if use_cache and symbol and timeframe:
            self._set_cache(cache_key, result)
        
        return result
    
    def calculate_rsi(
        self,
        df: pd.DataFrame,
        period: int = 14,
        symbol: str = "",
        timeframe: str = "",
        use_cache: bool = True
    ) -> pd.Series:
        """
        计算RSI（相对强弱指标）
        
        Args:
            df: K线数据
            period: RSI周期
            symbol: 交易对
            timeframe: 时间框架
            use_cache: 是否使用缓存
            
        Returns:
            RSI序列
        """
        if use_cache and symbol and timeframe:
            df_hash = self._get_df_hash(df)
            cache_key = self._get_cache_key(symbol, timeframe, df_hash, f"rsi{period}")
            cached = self._check_cache(cache_key)
            if cached is not None:
                return cached
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        if use_cache and symbol and timeframe:
            self._set_cache(cache_key, rsi)
        
        return rsi
    
    def calculate_adx(
        self,
        df: pd.DataFrame,
        period: int = 14,
        symbol: str = "",
        timeframe: str = "",
        use_cache: bool = True
    ) -> pd.Series:
        """
        计算ADX（平均趋向指标）
        
        Args:
            df: K线数据（需要high, low, close）
            period: ADX周期
            symbol: 交易对
            timeframe: 时间框架
            use_cache: 是否使用缓存
            
        Returns:
            ADX序列
        """
        if use_cache and symbol and timeframe:
            df_hash = self._get_df_hash(df)
            cache_key = self._get_cache_key(symbol, timeframe, df_hash, f"adx{period}")
            cached = self._check_cache(cache_key)
            if cached is not None:
                return cached
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        # 正确的ADX计算：
        # +DM = current_high - previous_high (when positive)
        # -DM = previous_low - current_low (when positive)
        plus_dm = high.diff()  # current_high - prev_high
        minus_dm = -low.diff()  # prev_low - current_low = -(current_low - prev_low)
        
        # 保留正值，负值设为0
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean()
        
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        if use_cache and symbol and timeframe:
            self._set_cache(cache_key, adx)
        
        return adx
    
    def calculate_atr(
        self,
        df: pd.DataFrame,
        period: int = 14,
        symbol: str = "",
        timeframe: str = "",
        use_cache: bool = True
    ) -> pd.Series:
        """
        计算ATR（平均真实波幅）
        
        Args:
            df: K线数据
            period: ATR周期
            symbol: 交易对
            timeframe: 时间框架
            use_cache: 是否使用缓存
            
        Returns:
            ATR序列
        """
        if use_cache and symbol and timeframe:
            df_hash = self._get_df_hash(df)
            cache_key = self._get_cache_key(symbol, timeframe, df_hash, f"atr{period}")
            cached = self._check_cache(cache_key)
            if cached is not None:
                return cached
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean()
        
        if use_cache and symbol and timeframe:
            self._set_cache(cache_key, atr)
        
        return atr
    
    def calculate_bollinger_bands(
        self,
        df: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0,
        symbol: str = "",
        timeframe: str = "",
        use_cache: bool = True
    ) -> Dict[str, pd.Series]:
        """
        计算布林带
        
        Args:
            df: K线数据
            period: 移动平均周期
            std_dev: 标准差倍数
            symbol: 交易对
            timeframe: 时间框架
            use_cache: 是否使用缓存
            
        Returns:
            Dict包含 upper, middle, lower, width_pct
        """
        if use_cache and symbol and timeframe:
            df_hash = self._get_df_hash(df)
            cache_key = self._get_cache_key(symbol, timeframe, df_hash, f"bb_{period}_{std_dev}")
            cached = self._check_cache(cache_key)
            if cached is not None:
                return cached
        
        middle = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        width_pct = ((upper - lower) / middle) * 100
        
        result = {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'width_pct': width_pct
        }
        
        if use_cache and symbol and timeframe:
            self._set_cache(cache_key, result)
        
        return result
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        return {
            'size': len(self._cache),
            'max_size': self._cache_size,
            'usage_pct': (len(self._cache) / self._cache_size) * 100 if self._cache_size > 0 else 0
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("✅ IndicatorPipeline cache cleared")


# 全局单例
_indicator_pipeline: Optional[IndicatorPipeline] = None


def get_indicator_pipeline(cache_size: int = 256, cache_ttl: int = 60) -> IndicatorPipeline:
    """
    获取全局指标管道单例
    
    Args:
        cache_size: 缓存大小
        cache_ttl: 缓存TTL（秒）
        
    Returns:
        IndicatorPipeline实例
    """
    global _indicator_pipeline
    if _indicator_pipeline is None:
        _indicator_pipeline = IndicatorPipeline(cache_size=cache_size, cache_ttl=cache_ttl)
    return _indicator_pipeline
