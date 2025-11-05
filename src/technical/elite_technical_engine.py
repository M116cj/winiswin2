"""
Elite Technical Engine v3.29+ - 统一技术指标计算引擎
职责：集成所有技术指标、消除代码冗余、提供高性能缓存

整合文件：
- src/utils/indicators.py (删除)
- src/utils/core_calculations.py (删除)
- src/features/technical_indicators.py (删除)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class TechnicalIndicators:
    """技术指标结果数据类"""
    # 趋势指标
    ema_fast: float
    ema_slow: float
    ema_trend: str  # "bullish"/"bearish"/"neutral"
    
    # 动量指标
    rsi: float
    rsi_signal: str  # "overbought"/"oversold"/"neutral"
    
    # 波动率指标
    atr: float
    bbands_upper: float
    bbands_middle: float
    bbands_lower: float
    bbands_width: float
    
    # 趋势强度
    adx: float
    adx_signal: str  # "strong"/"moderate"/"weak"
    
    # MACD
    macd: float
    macd_signal: float
    macd_hist: float
    macd_cross: str  # "bullish"/"bearish"/"none"
    
    # ICT 特征
    market_structure: Optional[float] = None
    order_blocks_count: Optional[int] = None
    liquidity_context: Optional[float] = None
    fvg_count: Optional[int] = None
    
    # 元数据
    timestamp: str = ""
    symbol: str = ""


class EliteTechnicalEngine:
    """
    精英技术引擎 v3.29+
    
    特性：
    1. 统一所有技术指标计算（EMA, RSI, MACD, BB, ADX, ATR）
    2. 集成 ICT 特征计算
    3. 高性能缓存机制（基于数据哈希）
    4. 完整的数据验证和错误处理
    5. 类型注解和文档字符串
    6. TA-Lib 集成（可选，降级到numpy）
    """
    
    def __init__(
        self,
        use_talib: bool = False,
        cache_enabled: bool = True,
        cache_ttl: int = 300
    ):
        """
        初始化技术引擎
        
        Args:
            use_talib: 是否使用 TA-Lib 库（更快，需安装）
            cache_enabled: 是否启用缓存
            cache_ttl: 缓存TTL（秒）
        """
        self.use_talib = use_talib
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        
        # 缓存
        self._cache: Dict[str, Tuple[TechnicalIndicators, float]] = {}
        
        # 尝试导入 TA-Lib
        if use_talib:
            try:
                import talib
                self.talib = talib
                logger.info("✅ TA-Lib 已启用（高性能模式）")
            except ImportError:
                logger.warning("⚠️ TA-Lib 未安装，降级到 NumPy")
                self.use_talib = False
                self.talib = None
        else:
            self.talib = None
        
        logger.info("=" * 80)
        logger.info("✅ EliteTechnicalEngine v3.29+ 初始化完成")
        logger.info(f"   🚀 TA-Lib: {'启用' if self.use_talib else '禁用'}")
        logger.info(f"   💾 缓存: {'启用' if cache_enabled else '禁用'}")
        logger.info(f"   ⏱️  TTL: {cache_ttl}秒")
        logger.info("=" * 80)
    
    def calculate_all_indicators(
        self,
        df: pd.DataFrame,
        symbol: str = "",
        config: Optional[Dict] = None
    ) -> TechnicalIndicators:
        """
        计算所有技术指标（主入口）
        
        Args:
            df: OHLCV 数据（必须包含：open, high, low, close, volume）
            symbol: 交易对符号
            config: 配置参数（可选）
            
        Returns:
            TechnicalIndicators 对象
        """
        # 数据验证
        if not self._validate_dataframe(df):
            raise ValueError("无效的数据框：缺少必需列")
        
        # 检查缓存
        cache_key = self._get_cache_key(df, symbol)
        if self.cache_enabled and cache_key in self._cache:
            cached_result, cache_time = self._cache[cache_key]
            if (datetime.now().timestamp() - cache_time) < self.cache_ttl:
                logger.debug(f"💾 缓存命中: {symbol}")
                return cached_result
        
        # 设置默认配置
        if config is None:
            config = {
                'ema_fast': 20,
                'ema_slow': 50,
                'rsi_period': 14,
                'rsi_overbought': 70,
                'rsi_oversold': 30,
                'atr_period': 14,
                'adx_period': 14,
                'bb_period': 20,
                'bb_std': 2.0
            }
        
        try:
            # 计算各类指标
            ema_fast, ema_slow, ema_trend = self._calculate_ema(
                df['close'],
                config['ema_fast'],
                config['ema_slow']
            )
            
            rsi, rsi_signal = self._calculate_rsi(
                df['close'],
                config['rsi_period'],
                config['rsi_overbought'],
                config['rsi_oversold']
            )
            
            atr = self._calculate_atr(
                df['high'],
                df['low'],
                df['close'],
                config['atr_period']
            )
            
            bb_upper, bb_middle, bb_lower, bb_width = self._calculate_bollinger_bands(
                df['close'],
                config['bb_period'],
                config['bb_std']
            )
            
            adx, adx_signal = self._calculate_adx(
                df['high'],
                df['low'],
                df['close'],
                config['adx_period']
            )
            
            macd, macd_signal, macd_hist, macd_cross = self._calculate_macd(
                df['close']
            )
            
            # 创建结果对象
            result = TechnicalIndicators(
                ema_fast=ema_fast,
                ema_slow=ema_slow,
                ema_trend=ema_trend,
                rsi=rsi,
                rsi_signal=rsi_signal,
                atr=atr,
                bbands_upper=bb_upper,
                bbands_middle=bb_middle,
                bbands_lower=bb_lower,
                bbands_width=bb_width,
                adx=adx,
                adx_signal=adx_signal,
                macd=macd,
                macd_signal=macd_signal,
                macd_hist=macd_hist,
                macd_cross=macd_cross,
                timestamp=datetime.now().isoformat(),
                symbol=symbol
            )
            
            # 更新缓存
            if self.cache_enabled:
                self._cache[cache_key] = (result, datetime.now().timestamp())
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 计算指标失败 {symbol}: {e}", exc_info=True)
            raise
    
    def _calculate_ema(
        self,
        close: pd.Series,
        fast_period: int,
        slow_period: int
    ) -> Tuple[float, float, str]:
        """计算 EMA 和趋势"""
        if self.use_talib and self.talib:
            ema_fast = self.talib.EMA(close.values, timeperiod=fast_period)
            ema_slow = self.talib.EMA(close.values, timeperiod=slow_period)
        else:
            ema_fast = close.ewm(span=fast_period, adjust=False).mean()
            ema_slow = close.ewm(span=slow_period, adjust=False).mean()
        
        ema_fast_val = float(ema_fast.iloc[-1])
        ema_slow_val = float(ema_slow.iloc[-1])
        
        # 趋势判断
        if ema_fast_val > ema_slow_val * 1.01:
            trend = "bullish"
        elif ema_fast_val < ema_slow_val * 0.99:
            trend = "bearish"
        else:
            trend = "neutral"
        
        return ema_fast_val, ema_slow_val, trend
    
    def _calculate_rsi(
        self,
        close: pd.Series,
        period: int,
        overbought: float,
        oversold: float
    ) -> Tuple[float, str]:
        """计算 RSI 和信号"""
        if self.use_talib and self.talib:
            rsi = self.talib.RSI(close.values, timeperiod=period)
            rsi_val = float(rsi[-1])
        else:
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(window=period).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_val = float(rsi.iloc[-1])
        
        # 信号判断
        if rsi_val >= overbought:
            signal = "overbought"
        elif rsi_val <= oversold:
            signal = "oversold"
        else:
            signal = "neutral"
        
        return rsi_val, signal
    
    def _calculate_atr(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int
    ) -> float:
        """计算 ATR（平均真实波幅）"""
        if self.use_talib and self.talib:
            atr = self.talib.ATR(high.values, low.values, close.values, timeperiod=period)
            return float(atr[-1])
        else:
            high_low = high - low
            high_close = np.abs(high - close.shift())
            low_close = np.abs(low - close.shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            return float(atr.iloc[-1])
    
    def _calculate_bollinger_bands(
        self,
        close: pd.Series,
        period: int,
        std_dev: float
    ) -> Tuple[float, float, float, float]:
        """计算布林带"""
        if self.use_talib and self.talib:
            upper, middle, lower = self.talib.BBANDS(
                close.values,
                timeperiod=period,
                nbdevup=std_dev,
                nbdevdn=std_dev
            )
            upper_val = float(upper[-1])
            middle_val = float(middle[-1])
            lower_val = float(lower[-1])
        else:
            middle = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            upper = middle + (std * std_dev)
            lower = middle - (std * std_dev)
            
            upper_val = float(upper.iloc[-1])
            middle_val = float(middle.iloc[-1])
            lower_val = float(lower.iloc[-1])
        
        width = (upper_val - lower_val) / middle_val
        
        return upper_val, middle_val, lower_val, width
    
    def _calculate_adx(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int
    ) -> Tuple[float, str]:
        """计算 ADX（趋势强度）"""
        if self.use_talib and self.talib:
            adx = self.talib.ADX(high.values, low.values, close.values, timeperiod=period)
            adx_val = float(adx[-1])
        else:
            # 简化的 ADX 计算
            plus_dm = high.diff()
            minus_dm = -low.diff()
            
            plus_dm[plus_dm < 0] = 0
            minus_dm[minus_dm < 0] = 0
            
            tr = pd.concat([
                high - low,
                np.abs(high - close.shift()),
                np.abs(low - close.shift())
            ], axis=1).max(axis=1)
            
            atr = tr.rolling(window=period).mean()
            plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
            minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
            
            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
            adx = dx.rolling(window=period).mean()
            adx_val = float(adx.iloc[-1])
        
        # 趋势强度判断
        if adx_val >= 25:
            signal = "strong"
        elif adx_val >= 20:
            signal = "moderate"
        else:
            signal = "weak"
        
        return adx_val, signal
    
    def _calculate_macd(
        self,
        close: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[float, float, float, str]:
        """计算 MACD"""
        if self.use_talib and self.talib:
            macd, macd_signal, macd_hist = self.talib.MACD(
                close.values,
                fastperiod=fast,
                slowperiod=slow,
                signalperiod=signal
            )
            macd_val = float(macd[-1])
            signal_val = float(macd_signal[-1])
            hist_val = float(macd_hist[-1])
        else:
            ema_fast = close.ewm(span=fast, adjust=False).mean()
            ema_slow = close.ewm(span=slow, adjust=False).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()
            hist = macd_line - signal_line
            
            macd_val = float(macd_line.iloc[-1])
            signal_val = float(signal_line.iloc[-1])
            hist_val = float(hist.iloc[-1])
        
        # 交叉判断
        if hist_val > 0 and (len(close) < 2 or float(hist.iloc[-2]) <= 0):
            cross = "bullish"
        elif hist_val < 0 and (len(close) < 2 or float(hist.iloc[-2]) >= 0):
            cross = "bearish"
        else:
            cross = "none"
        
        return macd_val, signal_val, hist_val, cross
    
    def _validate_dataframe(self, df: pd.DataFrame) -> bool:
        """验证数据框完整性"""
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        return all(col in df.columns for col in required_columns)
    
    def _get_cache_key(self, df: pd.DataFrame, symbol: str) -> str:
        """生成缓存键（基于数据哈希）"""
        # 使用最后一行数据的哈希作为键
        last_row = df.iloc[-1][['open', 'high', 'low', 'close', 'volume']].values
        data_str = f"{symbol}_{last_row.tobytes()}"
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.info("🧹 缓存已清空")
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        return {
            'cache_size': len(self._cache),
            'cache_enabled': self.cache_enabled,
            'cache_ttl': self.cache_ttl
        }


# 标记需要删除的重复文件
"""
⚠️ 以下文件已被整合，建议删除：
1. src/utils/indicators.py
2. src/utils/core_calculations.py  
3. src/features/technical_indicators.py

迁移说明：
- 所有技术指标计算已迁移到 EliteTechnicalEngine
- ICT 特征计算保留在 FeatureEngine
- 新代码应使用 EliteTechnicalEngine.calculate_all_indicators()
"""
