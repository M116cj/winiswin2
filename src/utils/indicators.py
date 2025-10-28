"""
技術指標
職責：EMA、MACD、RSI、Bollinger Bands、ATR 計算
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Tuple


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

def calculate_ema(data, period: int) -> pd.Series:
    """
    計算指數移動平均線 (EMA)
    
    Args:
        data: 價格數據（Series 或 DataFrame，如果是 DataFrame 會自動提取 'close' 列）
        period: 周期
    
    Returns:
        EMA 值
    """
    # 自動提取 close 列（如果是 DataFrame）
    if isinstance(data, pd.DataFrame):
        if 'close' in data.columns:
            data = data['close']
        else:
            raise ValueError("DataFrame must contain 'close' column")
    
    # 確保是 Series
    if not isinstance(data, pd.Series):
        data = pd.Series(data)
    
    result = data.ewm(span=period, adjust=False).mean()
    # 確保返回Series，不是DataFrame
    if isinstance(result, pd.DataFrame):
        return result.iloc[:, 0]
    return pd.Series(result)

def calculate_macd(
    data,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
):
    """
    計算 MACD 指標
    
    Args:
        data: 價格數據（Series 或 DataFrame，如果是 DataFrame 會自動提取 'close' 列）
        fast_period: 快線周期
        slow_period: 慢線周期
        signal_period: 信號線周期
    
    Returns:
        Dict 包含 'macd', 'signal', 'histogram'
    """
    # 自動提取 close 列（如果是 DataFrame）
    if isinstance(data, pd.DataFrame):
        if 'close' in data.columns:
            data = data['close']
        else:
            raise ValueError("DataFrame must contain 'close' column")
    
    # 確保是 Series
    if not isinstance(data, pd.Series):
        data = pd.Series(data)
    
    ema_fast = calculate_ema(data, fast_period)
    ema_slow = calculate_ema(data, slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    
    # 返回字典格式以保持一致性
    return {
        'macd': pd.Series(macd_line),
        'signal': pd.Series(signal_line),
        'histogram': pd.Series(histogram)
    }

def calculate_rsi(data, period: int = 14) -> pd.Series:
    """
    計算相對強弱指標 (RSI)
    
    Args:
        data: 價格數據（Series 或 DataFrame，如果是 DataFrame 會自動提取 'close' 列）
        period: 周期
    
    Returns:
        RSI 值
    """
    # 自動提取 close 列（如果是 DataFrame）
    if isinstance(data, pd.DataFrame):
        if 'close' in data.columns:
            data = data['close']
        else:
            raise ValueError("DataFrame must contain 'close' column")
    
    # 確保是 Series 且是數值類型
    if not isinstance(data, pd.Series):
        data = pd.Series(data)
    
    # 計算 RSI
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # 確保返回Series類型
    return pd.Series(rsi)

def calculate_bollinger_bands(
    data,
    period: int = 20,
    std_dev: float = 2.0
):
    """
    計算布林帶
    
    Args:
        data: 價格數據（Series 或 DataFrame，如果是 DataFrame 會自動提取 'close' 列）
        period: 周期
        std_dev: 標準差倍數
    
    Returns:
        Dict 包含 'upper', 'middle', 'lower', 'width'
    """
    # 自動提取 close 列（如果是 DataFrame）
    if isinstance(data, pd.DataFrame):
        if 'close' in data.columns:
            data = data['close']
        else:
            raise ValueError("DataFrame must contain 'close' column")
    
    # 確保是 Series
    if not isinstance(data, pd.Series):
        data = pd.Series(data)
    
    middle_band = data.rolling(window=period).mean()
    std = data.rolling(window=period).std()
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    width = (upper_band - lower_band) / middle_band
    
    # 返回字典格式
    return {
        'upper': upper_band,
        'middle': middle_band,
        'lower': lower_band,
        'width': width
    }

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


def identify_order_blocks(
    df: pd.DataFrame, 
    lookback: int = 20,
    volume_multiplier: float = 1.5,
    rejection_threshold: float = 0.005,
    max_history: int = 20
) -> list:
    """
    識別 Order Blocks（v3.11.0质量筛选增强版）
    
    定义：
    - 看涨 OB：下跌末期出现实体 ≥ 70% 全长的阳K，区间 = [Low, Open]
    - 看跌 OB：上涨末期出现实体 ≥ 70% 全长的阴K，区间 = [High, Open]
    - 需要后续 3 根 K 线确认方向延续
    
    v3.11.0新增质量筛选：
    - 成交量验证：OB K线成交量必须 >= volume_multiplier × 20根均量
    - 拒绝率验证：OB区间高度 / K线全长 >= rejection_threshold
    - 测试次数追踪：记录每个OB被价格触及的次数
    - 历史保留：保留max_history个OB（而非仅5个）
    
    Args:
        df: K線數據框
        lookback: 回溯周期
        volume_multiplier: 成交量倍数阈值
        rejection_threshold: 拒绝率阈值（相对于K线全长，如0.005=0.5%）
        max_history: 最多保留的OB历史数量
    
    Returns:
        Order Blocks 列表（包含质量分数）
    """
    if df.empty or len(df) < lookback + 4:
        return []
    
    order_blocks = []
    
    # 计算20根K线平均成交量（用于质量筛选）
    avg_volume_20 = None
    if 'volume' in df.columns:
        avg_volume_20 = df['volume'].rolling(20).mean()
    
    for i in range(lookback, len(df) - 4):
        candle_high = df['high'].iloc[i]
        candle_low = df['low'].iloc[i]
        candle_open = df['open'].iloc[i]
        candle_close = df['close'].iloc[i]
        candle_volume = df['volume'].iloc[i] if 'volume' in df.columns else 0
        
        full_length = candle_high - candle_low
        body_length = abs(candle_close - candle_open)
        
        if full_length == 0:
            continue
        
        body_pct = body_length / full_length
        
        # 基础验证：实体占比 >= 70%
        if body_pct < 0.70:
            continue
        
        # 🔍 v3.11.0：质量筛选 - 成交量验证
        if 'volume' in df.columns and avg_volume_20 is not None and avg_volume_20.iloc[i] > 0:
            volume_ratio = candle_volume / avg_volume_20.iloc[i]
            if volume_ratio < volume_multiplier:
                continue  # 成交量不足，跳过
        else:
            volume_ratio = 1.0  # 无成交量数据时默认通过
        
        # 🔍 v3.11.0：质量筛选 - 拒绝率验证（相对于K线全长）
        zone_height = abs(candle_open - (candle_low if candle_close > candle_open else candle_high))
        rejection_pct = zone_height / full_length if full_length > 0 else 0
        
        if rejection_pct < rejection_threshold:
            continue  # OB区间太小，跳过
        
        is_bullish_candle = candle_close > candle_open
        is_bearish_candle = candle_close < candle_open
        
        next_3_candles = df.iloc[i+1:i+4]
        
        if len(next_3_candles) < 3:
            continue
        
        next_3_closes = next_3_candles['close']
        
        if is_bullish_candle:
            confirmed = (next_3_closes > candle_close).sum() >= 2
            
            if confirmed:
                # 🎯 v3.11.0：计算质量分数（0-1）
                # 成交量30% + 实体占比30% + 拒绝率40%
                quality_score = (
                    min(volume_ratio / 3.0, 1.0) * 0.3 +  # 成交量分（最高3倍=1.0）
                    body_pct * 0.3 +                       # 实体占比分
                    min(rejection_pct / 0.05, 1.0) * 0.4   # 拒绝率分（5%=1.0）
                )
                
                order_blocks.append({
                    'type': 'bullish',
                    'price': float((candle_low + candle_open) / 2),
                    'zone_low': float(candle_low),
                    'zone_high': float(candle_open),
                    'timestamp': df.index[i] if hasattr(df.index[i], 'isoformat') else i,
                    'body_pct': float(body_pct),
                    'confirmed': True,
                    # v3.11.0新增字段
                    'volume_ratio': float(volume_ratio),
                    'rejection_pct': float(rejection_pct),
                    'quality_score': float(quality_score),
                    'test_count': 0,  # 初始测试次数为0
                    'created_at': df.index[i] if hasattr(df.index[i], 'isoformat') else i
                })
        
        elif is_bearish_candle:
            confirmed = (next_3_closes < candle_close).sum() >= 2
            
            if confirmed:
                # 🎯 v3.11.0：计算质量分数（0-1）
                quality_score = (
                    min(volume_ratio / 3.0, 1.0) * 0.3 +
                    body_pct * 0.3 +
                    min(rejection_pct / 0.05, 1.0) * 0.4
                )
                
                order_blocks.append({
                    'type': 'bearish',
                    'price': float((candle_high + candle_open) / 2),
                    'zone_low': float(candle_open),
                    'zone_high': float(candle_high),
                    'timestamp': df.index[i] if hasattr(df.index[i], 'isoformat') else i,
                    'body_pct': float(body_pct),
                    'confirmed': True,
                    # v3.11.0新增字段
                    'volume_ratio': float(volume_ratio),
                    'rejection_pct': float(rejection_pct),
                    'quality_score': float(quality_score),
                    'test_count': 0,
                    'created_at': df.index[i] if hasattr(df.index[i], 'isoformat') else i
                })
    
    # v3.11.0修复：保留max_history个OB（而非仅5个），用于衰减追踪
    return order_blocks[-max_history:] if order_blocks else []


def calculate_ob_decay_factor(
    ob: Dict,
    current_time,
    time_decay_hours: int = 48,
    decay_rate: float = 0.1,
    max_test_count: int = 3
) -> float:
    """
    计算Order Block的动态衰减系数（v3.11.0）
    
    衰减因素：
    1. 时间衰减：OB创建后每24小时衰减decay_rate
    2. 测试次数衰减：每被测试一次衰减20%
    
    Args:
        ob: Order Block字典
        current_time: 当前时间戳
        time_decay_hours: 开始衰减的小时数
        decay_rate: 每24小时的衰减率
        max_test_count: 最大测试次数（超过后失效）
    
    Returns:
        float: 衰减系数 (0-1)，0表示完全失效
    """
    import pandas as pd
    from datetime import datetime, timedelta
    
    # 测试次数衰减
    test_count = ob.get('test_count', 0)
    if test_count >= max_test_count:
        return 0.0  # 完全失效
    
    test_decay = 1.0 - (test_count * 0.2)  # 每次测试衰减20%
    
    # 时间衰减
    created_at = ob.get('created_at', current_time)
    
    try:
        if isinstance(created_at, (int, float)):
            # 假设是索引，转换为时间差
            time_diff_hours = 0
        elif isinstance(created_at, str):
            created_dt = pd.to_datetime(created_at)
            current_dt = pd.to_datetime(current_time)
            time_diff_hours = (current_dt - created_dt).total_seconds() / 3600
        else:
            # pd.Timestamp
            time_diff_hours = (current_time - created_at).total_seconds() / 3600
    except:
        time_diff_hours = 0
    
    if time_diff_hours < time_decay_hours:
        time_decay = 1.0  # 未开始衰减
    else:
        # 每24小时衰减decay_rate
        periods_elapsed = (time_diff_hours - time_decay_hours) / 24
        time_decay = max(0, 1.0 - (periods_elapsed * decay_rate))
    
    # 综合衰减系数
    total_decay = test_decay * time_decay
    
    return max(0.0, min(1.0, total_decay))


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


def detect_bos_choch(
    df: pd.DataFrame,
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    current_trend: str = 'neutral'
) -> Dict:
    """
    检测BOS (Break of Structure) 和 CHOCH (Change of Character) v3.11.0
    
    定义：
    - BOS: 突破同方向的swing点（趋势延续）
      * 上升趋势BOS：价格突破前一个swing high
      * 下降趋势BOS：价格跌破前一个swing low
    
    - CHOCH: 突破反方向的swing点（趋势转换）
      * 上升趋势CHOCH：价格跌破前一个swing low
      * 下降趋势CHOCH：价格突破前一个swing high
    
    Args:
        df: K线数据框
        swing_highs: Swing High列表
        swing_lows: Swing Low列表
        current_trend: 当前趋势 ('bullish', 'bearish', 'neutral')
    
    Returns:
        Dict: 包含BOS/CHOCH事件信息
    """
    if df.empty or len(df) < 10:
        return {'bos': None, 'choch': None, 'structure_type': 'unknown'}
    
    current_price = df['close'].iloc[-1]
    current_high = df['high'].iloc[-1]
    current_low = df['low'].iloc[-1]
    
    bos_event = None
    choch_event = None
    structure_type = 'unknown'
    
    # 获取最近的swing点
    recent_swing_high = swing_highs[-1] if swing_highs else None
    recent_swing_low = swing_lows[-1] if swing_lows else None
    
    # 检测BOS/CHOCH
    if current_trend == 'bullish':
        # 上升趋势：检测BOS (突破swing high) 或 CHOCH (跌破swing low)
        if recent_swing_high and current_high > recent_swing_high['price']:
            bos_event = {
                'type': 'BOS',
                'direction': 'bullish',
                'price': recent_swing_high['price'],
                'confirmed': True,
                'strength': (current_high - recent_swing_high['price']) / recent_swing_high['price']
            }
            structure_type = 'trend_continuation'
        
        elif recent_swing_low and current_low < recent_swing_low['price']:
            choch_event = {
                'type': 'CHOCH',
                'direction': 'bearish',  # 从bullish转向bearish
                'price': recent_swing_low['price'],
                'confirmed': True,
                'strength': (recent_swing_low['price'] - current_low) / recent_swing_low['price']
            }
            structure_type = 'trend_reversal'
    
    elif current_trend == 'bearish':
        # 下降趋势：检测BOS (跌破swing low) 或 CHOCH (突破swing high)
        if recent_swing_low and current_low < recent_swing_low['price']:
            bos_event = {
                'type': 'BOS',
                'direction': 'bearish',
                'price': recent_swing_low['price'],
                'confirmed': True,
                'strength': (recent_swing_low['price'] - current_low) / recent_swing_low['price']
            }
            structure_type = 'trend_continuation'
        
        elif recent_swing_high and current_high > recent_swing_high['price']:
            choch_event = {
                'type': 'CHOCH',
                'direction': 'bullish',  # 从bearish转向bullish
                'price': recent_swing_high['price'],
                'confirmed': True,
                'strength': (current_high - recent_swing_high['price']) / recent_swing_high['price']
            }
            structure_type = 'trend_reversal'
    
    else:
        # 中性趋势：检测首次结构突破
        if recent_swing_high and current_high > recent_swing_high['price']:
            bos_event = {
                'type': 'BOS',
                'direction': 'bullish',
                'price': recent_swing_high['price'],
                'confirmed': True,
                'strength': (current_high - recent_swing_high['price']) / recent_swing_high['price']
            }
            structure_type = 'breakout'
        
        elif recent_swing_low and current_low < recent_swing_low['price']:
            bos_event = {
                'type': 'BOS',
                'direction': 'bearish',
                'price': recent_swing_low['price'],
                'confirmed': True,
                'strength': (recent_swing_low['price'] - current_low) / recent_swing_low['price']
            }
            structure_type = 'breakout'
    
    return {
        'bos': bos_event,
        'choch': choch_event,
        'structure_type': structure_type,
        'has_structure_break': bos_event is not None or choch_event is not None
    }


def classify_market_regime(
    df: pd.DataFrame,
    adx_threshold: float = 25.0,
    bb_width_low: float = 0.02,
    bb_width_high: float = 0.05
) -> Dict:
    """
    市场状态分类器（v3.11.0）
    
    识别四种市场状态：
    1. TRENDING（趋势市）: ADX > 25 + 布林带宽度适中
    2. RANGING（震荡市）: ADX < 20 + 价格在布林带内频繁震荡
    3. BREAKOUT（突破市）: 价格突破布林带 + ADX上升
    4. DRIFT（漂移市）: ADX低 + 价格沿布林带边缘缓慢移动
    
    Args:
        df: K线数据框
        adx_threshold: ADX趋势阈值
        bb_width_low: 布林带宽度下限（震荡判断）
        bb_width_high: 布林带宽度上限（高波动判断）
    
    Returns:
        Dict: 市场状态信息
    """
    if df.empty or len(df) < 50:
        return {
            'regime': 'unknown',
            'confidence': 0.0,
            'adx': 0,
            'bb_width': 0,
            'price_position': 'middle'
        }
    
    # 计算ADX
    adx_series = calculate_adx(df, period=14)
    adx = adx_series.iloc[-1] if not adx_series.empty else 0
    
    # 计算布林带
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df, period=20)
    current_price = df['close'].iloc[-1]
    
    # 布林带宽度（标准化）
    bb_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_middle.iloc[-1]
    
    # 价格相对布林带位置
    if current_price > bb_upper.iloc[-1]:
        price_position = 'above_upper'
    elif current_price < bb_lower.iloc[-1]:
        price_position = 'below_lower'
    elif current_price > bb_middle.iloc[-1]:
        price_position = 'upper_half'
    else:
        price_position = 'lower_half'
    
    # ADX变化率（判断趋势强度是否上升）
    adx_change = 0
    if len(adx_series) >= 5:
        adx_change = (adx - adx_series.iloc[-5]) / adx_series.iloc[-5] if adx_series.iloc[-5] > 0 else 0
    
    # 分类逻辑
    regime = 'unknown'
    confidence = 0.0
    
    # 1. 突破市：价格突破布林带 + ADX上升
    if price_position in ['above_upper', 'below_lower'] and adx > 20:
        regime = 'breakout'
        confidence = min(1.0, (adx / 40) + (abs(adx_change) * 2))
    
    # 2. 趋势市：ADX强 + 布林带宽度适中
    elif adx >= adx_threshold and bb_width_low < bb_width < bb_width_high:
        regime = 'trending'
        confidence = min(1.0, adx / 40)
    
    # 3. 震荡市：ADX弱 + 布林带窄
    elif adx < 20 and bb_width < bb_width_low:
        regime = 'ranging'
        confidence = min(1.0, (20 - adx) / 20)
    
    # 4. 漂移市：ADX弱 + 价格沿布林带边缘移动
    elif adx < 20 and price_position in ['upper_half', 'lower_half']:
        regime = 'drift'
        confidence = 0.6  # 中等置信度
    
    # 5. 高波动震荡：ADX弱但布林带很宽
    elif adx < 20 and bb_width >= bb_width_high:
        regime = 'choppy'
        confidence = 0.7
    
    # 6. 默认：趋势衰减中
    else:
        regime = 'transitioning'
        confidence = 0.4
    
    return {
        'regime': regime,
        'confidence': float(confidence),
        'adx': float(adx),
        'adx_change': float(adx_change),
        'bb_width': float(bb_width),
        'price_position': price_position,
        'should_trade': regime in ['trending', 'breakout'],  # 只在趋势和突破时交易
        'risk_level': 'high' if regime in ['choppy', 'ranging'] else 'normal'
    }


def detect_reversal_risk(
    df: pd.DataFrame,
    liquidity_sweep_threshold: float = 0.01,
    rsi_extreme_bull: float = 75,
    rsi_extreme_bear: float = 25,
    macd_convergence_ratio: float = 0.3
) -> Dict:
    """
    反转预警滤网（v3.11.0 - 四层防反转架构 Layer 1）
    
    检测三种高反转风险情况：
    1. 流动性扫荡（Liquidity Sweep）：价格突破后快速回撤
    2. RSI极端 + 价格背离
    3. MACD动量急剧衰减
    
    Args:
        df: K线数据框
        liquidity_sweep_threshold: 流动性扫荡阈值（1%）
        rsi_extreme_bull: RSI看跌极端值
        rsi_extreme_bear: RSI看涨极端值
        macd_convergence_ratio: MACD收敛比例
    
    Returns:
        Dict: 反转风险信息
    """
    if df.empty or len(df) < 20:
        return {
            'high_risk': False,
            'risk_type': 'none',
            'risk_score': 0.0,
            'should_skip': False
        }
    
    current_price = df['close'].iloc[-1]
    risk_factors = []
    risk_score = 0.0
    
    # 1. 检测流动性扫荡（Bull Trap / Bear Trap）
    recent_high = df['high'].iloc[-20:].max()
    recent_low = df['low'].iloc[-20:].min()
    
    # Bull Trap：价格突破高点后快速回撤
    if (current_price > recent_high * (1 + liquidity_sweep_threshold) and
        current_price < recent_high * 0.995):
        risk_factors.append('bull_trap')
        risk_score += 0.4
    
    # Bear Trap：价格跌破低点后快速反弹
    if (current_price < recent_low * (1 - liquidity_sweep_threshold) and
        current_price > recent_low * 1.005):
        risk_factors.append('bear_trap')
        risk_score += 0.4
    
    # 2. RSI极端 + 价格背离检测
    rsi = calculate_rsi(df['close'], period=14)
    current_rsi = rsi.iloc[-1] if not rsi.empty else 50
    
    # 检测看跌背离（价格创新高，RSI未创新高）
    if current_rsi > rsi_extreme_bull:
        price_high_recent = df['high'].iloc[-5:].max()
        price_high_prev = df['high'].iloc[-15:-5].max()
        rsi_high_recent = rsi.iloc[-5:].max()
        rsi_high_prev = rsi.iloc[-15:-5].max()
        
        if price_high_recent > price_high_prev and rsi_high_recent < rsi_high_prev:
            risk_factors.append('bearish_divergence')
            risk_score += 0.3
    
    # 检测看涨背离（价格创新低，RSI未创新低）
    if current_rsi < rsi_extreme_bear:
        price_low_recent = df['low'].iloc[-5:].min()
        price_low_prev = df['low'].iloc[-15:-5].min()
        rsi_low_recent = rsi.iloc[-5:].min()
        rsi_low_prev = rsi.iloc[-15:-5].min()
        
        if price_low_recent < price_low_prev and rsi_low_recent > rsi_low_prev:
            risk_factors.append('bullish_divergence')
            risk_score += 0.3
    
    # 3. MACD动量急剧衰减
    macd_line, signal_line, macd_hist = calculate_macd(df['close'])
    
    if not macd_hist.empty and len(macd_hist) >= 5:
        current_hist = abs(macd_hist.iloc[-1])
        prev_hist = abs(macd_hist.iloc[-3])
        
        # MACD柱状图收敛超过70%
        if prev_hist > 0 and current_hist < prev_hist * macd_convergence_ratio:
            risk_factors.append('macd_convergence')
            risk_score += 0.2
    
    # 综合判断
    high_risk = risk_score >= 0.4  # 风险分数>=0.4视为高风险
    risk_type = ','.join(risk_factors) if risk_factors else 'none'
    should_skip = high_risk  # 高风险时跳过交易
    
    return {
        'high_risk': high_risk,
        'risk_type': risk_type,
        'risk_score': float(risk_score),
        'should_skip': should_skip,
        'risk_factors': risk_factors
    }


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


def calculate_adx(df: pd.DataFrame, period: int = 14):
    """
    計算平均方向指數 (ADX) + DMI
    
    用於判斷趨勢強度（v3.10.0新增）
    
    Args:
        df: K線數據框（必須包含 high, low, close）
        period: 周期（默認14）
    
    Returns:
        Dict 包含 'adx', 'di_plus', 'di_minus'
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
    
    # 返回字典格式
    return {
        'adx': pd.Series(adx),
        'di_plus': pd.Series(plus_di),
        'di_minus': pd.Series(minus_di)
    }


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
