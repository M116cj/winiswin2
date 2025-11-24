"""
📊 統一數據格式定義
所有系統層使用這個文件中定義的格式，確保 PostgreSQL、Redis、WebSocket 數據一致
"""

from typing import Dict, List, TypedDict, Optional
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
# 常量定義
# ═══════════════════════════════════════════════════════════════════════════════

# Candle 元組索引 (timestamp_ms, open, high, low, close, volume)
CANDLE_IDX_TIMESTAMP = 0
CANDLE_IDX_OPEN = 1
CANDLE_IDX_HIGH = 2
CANDLE_IDX_LOW = 3
CANDLE_IDX_CLOSE = 4
CANDLE_IDX_VOLUME = 5

# 時間框架（秒）
TIMEFRAME_1M = 60
TIMEFRAME_5M = 300
TIMEFRAME_15M = 900
TIMEFRAME_1H = 3600
TIMEFRAME_1D = 86400

# 交易方向
DIRECTION_BUY = "BUY"
DIRECTION_SELL = "SELL"

# 訂單狀態
ORDER_STATUS_FILLED = "FILLED"
ORDER_STATUS_REJECTED = "REJECTED"
ORDER_STATUS_CANCELLED = "CANCELLED"

# ═══════════════════════════════════════════════════════════════════════════════
# 類型定義 (TypedDict)
# ═══════════════════════════════════════════════════════════════════════════════


class CandleData(TypedDict):
    """
    標準化的 K 線數據
    
    所有系統層統一使用此格式
    timestamp 統一為毫秒 (BIGINT)
    """
    timestamp: int  # 毫秒時間戳
    open: float
    high: float
    low: float
    close: float
    volume: float


class SignalFeatures(TypedDict, total=False):
    """
    信號特徵完整集合
    
    用於存儲到 signals.patterns 和 ML 訓練
    """
    # 基礎特徵
    confidence: float  # 0.0 to 1.0
    direction: str  # BUY/SELL
    strength: float  # 0.0 to 1.0

    # 技術指標
    fvg: float  # 0.0 to 1.0
    liquidity: float  # 0.0 to 1.0
    rsi: float  # 0 to 100
    atr: float  # 絕對值
    macd: float  # 相對值
    bb_width: float  # 相對值

    # 倉位信息
    position_size: float  # 數量
    position_size_pct: float  # 百分比

    # 多時間框架分析
    timeframe_analysis: Dict  # {1d, 1h, 15m: {...confidence, strength...}}


class SignalRecord(TypedDict):
    """
    完整信號記錄格式
    
    Brain 生成 -> Trade 存儲 -> Experience Buffer 記錄
    """
    signal_id: str  # UUID
    symbol: str
    timestamp: int  # 毫秒時間戳
    confidence: float
    features: SignalFeatures
    entry_price: float


class TradeOutcome(TypedDict, total=False):
    """
    交易結果記錄
    
    用於 experience_buffer
    """
    entry_price: float
    exit_price: float
    quantity: float
    side: str  # BUY/SELL
    pnl: float
    pnl_percent: float
    status: str  # FILLED/REJECTED
    close_reason: str  # TP_HIT/SL_HIT/MANUAL
    win: bool


class ExperienceRecord(TypedDict, total=False):
    """
    完整的經驗記錄
    
    信號 + 交易結果，用於 ML 訓練
    """
    signal_id: str
    symbol: str
    timestamp: int  # 毫秒
    features: SignalFeatures
    outcome: TradeOutcome


class MLTrainingData(TypedDict):
    """
    ML 訓練數據統一格式
    
    feature_vector: [confidence, fvg, liquidity, position_size_pct, rsi, atr, macd, bb_width]
    label: 0 (loss) or 1 (win)
    """
    features: List[float]  # 8 個特徵
    label: int  # 0 or 1
    metadata: Dict  # symbol, timestamp, pnl, source (virtual/real)


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函數
# ═══════════════════════════════════════════════════════════════════════════════


def candle_from_tuple(candle_tuple: tuple) -> CandleData:
    """
    將 Binance K 線元組轉換為標準格式
    
    輸入: (timestamp_ms, open, high, low, close, volume)
    """
    ts, o, h, l, c, v = candle_tuple
    return CandleData(
        timestamp=int(ts),
        open=float(o),
        high=float(h),
        low=float(l),
        close=float(c),
        volume=float(v),
    )


def candle_to_tuple(candle: CandleData) -> tuple:
    """
    將標準格式轉換回元組（用於 ring buffer）
    """
    return (
        candle["timestamp"],
        candle["open"],
        candle["high"],
        candle["low"],
        candle["close"],
        candle["volume"],
    )


def extract_ml_features(signal_data: Dict) -> List[float]:
    """
    從信號數據提取 ML 特徵向量
    
    統一的特徵提取方法，所有地方使用此函數
    
    輸出: [confidence, fvg, liquidity, position_size_pct, rsi, atr, macd, bb_width]
    """
    confidence = float(signal_data.get("confidence", 0.5))

    # 從 patterns 或 features 提取
    features_dict = signal_data.get("features", signal_data.get("patterns", {}))
    fvg = float(features_dict.get("fvg", 0.5))
    liquidity = float(features_dict.get("liquidity", 0.5))

    # 倉位大小百分比化 (假設倉位在 0-10000 範圍)
    position_size = float(signal_data.get("position_size", 100.0))
    position_size_pct = (position_size / 10000.0) if position_size else 0.0

    # 技術指標 (缺失使用默認值)
    rsi = float(features_dict.get("rsi", 50.0))  # 中立值
    atr = float(features_dict.get("atr", 0.0))
    macd = float(features_dict.get("macd", 0.0))
    bb_width = float(features_dict.get("bb_width", 0.0))

    # 返回標準化特徵向量
    return [confidence, fvg, liquidity, position_size_pct, rsi, atr, macd, bb_width]


def create_signal_record(
    signal_id: str,
    symbol: str,
    timestamp_ms: int,
    confidence: float,
    direction: str,
    strength: float,
    entry_price: float,
    features: Optional[SignalFeatures] = None,
) -> SignalRecord:
    """
    創建完整的信號記錄
    
    統一的信號創建方法
    """
    if features is None:
        features = SignalFeatures(
            confidence=confidence,
            direction=direction,
            strength=strength,
            fvg=0.5,
            liquidity=0.5,
            rsi=50,
            atr=0,
            macd=0,
            bb_width=0,
            position_size=100.0,
            position_size_pct=0.01,
            timeframe_analysis={},
        )

    return SignalRecord(
        signal_id=signal_id,
        symbol=symbol,
        timestamp=timestamp_ms,
        confidence=confidence,
        features=features,
        entry_price=entry_price,
    )
