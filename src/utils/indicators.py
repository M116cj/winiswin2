"""
技術指標
職責：EMA、MACD、RSI、Bollinger Bands、ATR 計算
"""

import pandas as pd
import numpy as np
from typing import Optional

def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """
    計算指數移動平均線 (EMA)
    
    Args:
        data: 價格數據
        period: 周期
    
    Returns:
        EMA 值
    """
    return data.ewm(span=period, adjust=False).mean()

def calculate_macd(
    data: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    計算 MACD 指標
    
    Args:
        data: 價格數據
        fast_period: 快線周期
        slow_period: 慢線周期
        signal_period: 信號線周期
    
    Returns:
        tuple[MACD線, 信號線, 柱狀圖]
    """
    ema_fast = calculate_ema(data, fast_period)
    ema_slow = calculate_ema(data, slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """
    計算相對強弱指標 (RSI)
    
    Args:
        data: 價格數據
        period: 周期
    
    Returns:
        RSI 值
    """
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_bollinger_bands(
    data: pd.Series,
    period: int = 20,
    std_dev: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    計算布林帶
    
    Args:
        data: 價格數據
        period: 周期
        std_dev: 標準差倍數
    
    Returns:
        tuple[上軌, 中軌, 下軌]
    """
    middle_band = data.rolling(window=period).mean()
    std = data.rolling(window=period).std()
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    return upper_band, middle_band, lower_band

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    計算平均真實波幅 (ATR)
    
    Args:
        high: 最高價
        low: 最低價
        close: 收盤價
        period: 周期
    
    Returns:
        ATR 值
    """
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr

def calculate_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """
    計算成交量簡單移動平均
    
    Args:
        volume: 成交量數據
        period: 周期
    
    Returns:
        成交量 SMA
    """
    return volume.rolling(window=period).mean()

def detect_price_rejection(
    open_price: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    threshold: float = 0.03
) -> pd.Series:
    """
    檢測價格拒絕（用於 Order Blocks）
    
    Args:
        open_price: 開盤價
        high: 最高價
        low: 最低價
        close: 收盤價
        threshold: 拒絕閾值（百分比）
    
    Returns:
        是否為價格拒絕（布林值序列）
    """
    body = abs(close - open_price)
    total_range = high - low
    
    # 避免除零
    rejection_ratio = body / total_range.replace(0, np.nan)
    
    # 拒絕定義：實體小於總範圍的指定百分比
    return rejection_ratio < threshold

def find_swing_highs_lows(
    high: pd.Series,
    low: pd.Series,
    lookback: int = 20
) -> tuple[pd.Series, pd.Series]:
    """
    識別擺動高點和低點（用於 Liquidity Zones）
    
    Args:
        high: 最高價
        low: 最低價
        lookback: 回溯周期
    
    Returns:
        tuple[擺動高點, 擺動低點]
    """
    swing_highs = high.rolling(window=lookback, center=True).max()
    swing_lows = low.rolling(window=lookback, center=True).min()
    
    return swing_highs, swing_lows

def calculate_market_structure(close: pd.Series, lookback: int = 10) -> dict:
    """
    分析市場結構（更高高點/更低低點）
    
    Args:
        close: 收盤價
        lookback: 回溯周期
    
    Returns:
        市場結構信息
    """
    if len(close) < lookback + 1:
        return {"trend": "neutral", "structure_valid": False}
    
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
    
    return {
        "trend": trend,
        "structure_valid": True,
        "higher_high": higher_high,
        "higher_low": higher_low,
        "lower_high": lower_high,
        "lower_low": lower_low
    }
