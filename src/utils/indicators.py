"""
技術指標
職責：EMA、MACD、RSI、Bollinger Bands、ATR 計算
"""

import pandas as pd
import numpy as np
from typing import Optional


class TechnicalIndicators:
    """
    技術指標計算類
    
    封裝所有技術指標計算方法，便於在position_monitor中使用
    """
    
    def calculate_rsi(self, data, period=14):
        """計算RSI指標"""
        if isinstance(data, (list, np.ndarray)):
            data = pd.Series(data)
        return calculate_rsi(data, period)
    
    def calculate_macd(self, data, fast_period=12, slow_period=26, signal_period=9):
        """計算MACD指標"""
        if isinstance(data, (list, np.ndarray)):
            data = pd.Series(data)
        return calculate_macd(data, fast_period, slow_period, signal_period)
    
    def calculate_bollinger_bands(self, data, period=20, std_dev=2):
        """計算布林帶"""
        if isinstance(data, (list, np.ndarray)):
            data = pd.Series(data)
        return calculate_bollinger_bands(data, period, std_dev)

def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """
    計算指數移動平均線 (EMA)
    
    Args:
        data: 價格數據
        period: 周期
    
    Returns:
        EMA 值
    """
    result = data.ewm(span=period, adjust=False).mean()
    # 確保返回Series，不是DataFrame
    if isinstance(result, pd.DataFrame):
        return result.iloc[:, 0]
    return pd.Series(result)

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
    
    # 確保返回Series類型
    return pd.Series(macd_line), pd.Series(signal_line), pd.Series(histogram)

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
    
    # 確保返回Series類型
    return pd.Series(rsi)

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

def calculate_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """
    計算成交量簡單移動平均
    
    Args:
        volume: 成交量數據
        period: 周期
    
    Returns:
        成交量 SMA
    """
    result = volume.rolling(window=period).mean()
    return pd.Series(result)

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
    swing_highs_raw = high.rolling(window=lookback, center=True).max()
    swing_highs = pd.Series(swing_highs_raw)
    swing_lows_raw = low.rolling(window=lookback, center=True).min()
    swing_lows = pd.Series(swing_lows_raw)
    
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


def identify_order_blocks(df: pd.DataFrame, lookback: int = 20) -> list:
    """
    識別 Order Blocks（严格版本）
    
    定义：
    - 看涨 OB：下跌末期出现实体 ≥ 70% 全长的阳K，区间 = [Low, Open]
    - 看跌 OB：上涨末期出现实体 ≥ 70% 全长的阴K，区间 = [High, Open]
    - 需要后续 3 根 K 线确认方向延续
    
    Args:
        df: K線數據框
        lookback: 回溯周期
    
    Returns:
        Order Blocks 列表
    """
    if df.empty or len(df) < lookback + 4:
        return []
    
    order_blocks = []
    
    for i in range(lookback, len(df) - 4):
        candle_high = df['high'].iloc[i]
        candle_low = df['low'].iloc[i]
        candle_open = df['open'].iloc[i]
        candle_close = df['close'].iloc[i]
        
        full_length = candle_high - candle_low
        body_length = abs(candle_close - candle_open)
        
        if full_length == 0:
            continue
        
        body_pct = body_length / full_length
        
        if body_pct < 0.70:
            continue
        
        is_bullish_candle = candle_close > candle_open
        is_bearish_candle = candle_close < candle_open
        
        next_3_candles = df.iloc[i+1:i+4]
        
        if len(next_3_candles) < 3:
            continue
        
        next_3_closes = next_3_candles['close']
        
        if is_bullish_candle:
            confirmed = (next_3_closes > candle_close).sum() >= 2
            
            if confirmed:
                order_blocks.append({
                    'type': 'bullish',
                    'price': float((candle_low + candle_open) / 2),
                    'zone_low': float(candle_low),
                    'zone_high': float(candle_open),
                    'timestamp': df.index[i] if hasattr(df.index[i], 'isoformat') else i,
                    'body_pct': float(body_pct),
                    'confirmed': True
                })
        
        elif is_bearish_candle:
            confirmed = (next_3_closes < candle_close).sum() >= 2
            
            if confirmed:
                order_blocks.append({
                    'type': 'bearish',
                    'price': float((candle_high + candle_open) / 2),
                    'zone_low': float(candle_open),
                    'zone_high': float(candle_high),
                    'timestamp': df.index[i] if hasattr(df.index[i], 'isoformat') else i,
                    'body_pct': float(body_pct),
                    'confirmed': True
                })
    
    return order_blocks[-5:]


def identify_swing_points(df: pd.DataFrame, lookback: int = 5) -> tuple:
    """
    識別擺動點
    
    Args:
        df: K線數據框
        lookback: 回溯周期
    
    Returns:
        tuple[擺動高點列表, 擺動低點列表]
    """
    if df.empty or len(df) < lookback * 2 + 1:
        return [], []
    
    highs = []
    lows = []
    
    for i in range(lookback, len(df) - lookback):
        window_high = df['high'].iloc[i-lookback:i+lookback+1]
        window_low = df['low'].iloc[i-lookback:i+lookback+1]
        
        if df['high'].iloc[i] == window_high.max():
            highs.append({
                'price': float(df['high'].iloc[i]),
                'index': i
            })
        
        if df['low'].iloc[i] == window_low.min():
            lows.append({
                'price': float(df['low'].iloc[i]),
                'index': i
            })
    
    return highs, lows


def determine_market_structure(df: pd.DataFrame) -> str:
    """
    判斷市場結構
    
    Args:
        df: K線數據框
    
    Returns:
        str: 市場結構 ('bullish', 'bearish', 'neutral')
    """
    if df.empty or len(df) < 20:
        return "neutral"
    
    structure = calculate_market_structure(df['close'], lookback=10)
    return structure.get('trend', 'neutral')


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    計算平均真實波幅 (ATR) - DataFrame 版本
    
    Args:
        df: K線數據框
        period: 周期
    
    Returns:
        ATR 值
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    # 確保返回Series類型
    return pd.Series(atr)


def calculate_adx(df: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    計算平均方向指數 (ADX) + DMI
    
    用於判斷趨勢強度（v3.10.0新增）
    
    Args:
        df: K線數據框（必須包含 high, low, close）
        period: 周期（默認14）
    
    Returns:
        tuple[ADX, +DI, -DI]
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # 計算方向移動（Directional Movement）
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    # +DM 和 -DM
    plus_dm = pd.Series(0.0, index=df.index)
    minus_dm = pd.Series(0.0, index=df.index)
    
    plus_dm[up_move > down_move] = up_move[up_move > down_move]
    plus_dm[plus_dm < 0] = 0
    
    minus_dm[down_move > up_move] = down_move[down_move > up_move]
    minus_dm[minus_dm < 0] = 0
    
    # 計算TR（True Range）
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 平滑DM和TR（Wilder's smoothing）
    atr = tr.ewm(alpha=1/period, min_periods=period).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)
    
    # 計算DX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
    
    # 計算ADX（DX的平滑）
    adx = dx.ewm(alpha=1/period, min_periods=period).mean()
    
    return pd.Series(adx), pd.Series(plus_di), pd.Series(minus_di)


def calculate_ema_slope(ema: pd.Series, lookback: int = 3) -> pd.Series:
    """
    計算EMA斜率（用於判斷趨勢強度）
    
    Args:
        ema: EMA序列
        lookback: 回溯期（默認3根K線）
    
    Returns:
        EMA斜率（正數=上升，負數=下降）
    """
    if len(ema) < lookback + 1:
        return pd.Series(0.0, index=ema.index)
    
    # 計算斜率：(當前值 - N根前值) / N
    slope = (ema - ema.shift(lookback)) / lookback
    
    # 標準化為百分比變化
    slope_pct = (slope / ema) * 100
    
    return pd.Series(slope_pct)
