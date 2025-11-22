"""
🧬 AEGIS Core Models - High-Performance Data Structures
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Zero-copy, memory-efficient candle and feature models
Design: __slots__ for memory efficiency + orjson for JSON serialization
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class Candle:
    """
    High-performance OHLCV candle with __slots__ optimization
    
    Memory savings: ~60% compared to regular Python objects
    """
    __slots__ = ('ts', 'o', 'h', 'l', 'c', 'v', 'symbol', 'interval')
    
    def __init__(
        self,
        ts: int,
        o: float,
        h: float,
        l: float,
        c: float,
        v: float,
        symbol: str = "",
        interval: str = "1m"
    ):
        """
        Initialize candle
        
        Args:
            ts: Timestamp (milliseconds)
            o: Open price
            h: High price
            l: Low price
            c: Close price
            v: Volume
            symbol: Trading pair symbol
            interval: Candle interval (1m, 5m, etc.)
        """
        self.ts = ts
        self.o = o
        self.h = h
        self.l = l
        self.c = c
        self.v = v
        self.symbol = symbol
        self.interval = interval
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'timestamp': self.ts,
            'open': self.o,
            'high': self.h,
            'low': self.l,
            'close': self.c,
            'volume': self.v,
            'symbol': self.symbol,
            'interval': self.interval
        }
    
    @classmethod
    def from_kline(cls, kline: Dict) -> 'Candle':
        """Create from WebSocket kline format"""
        return cls(
            ts=kline.get('timestamp', 0),
            o=float(kline.get('open', 0)),
            h=float(kline.get('high', 0)),
            l=float(kline.get('low', 0)),
            c=float(kline.get('close', 0)),
            v=float(kline.get('volume', 0)),
            symbol=kline.get('symbol', ''),
            interval=kline.get('interval', '1m')
        )
    
    def __repr__(self) -> str:
        return f"Candle({self.symbol} {self.c} @ {self.ts})"


class FeatureVector:
    """
    High-performance feature vector with __slots__
    
    Stores the 12 ATR-normalized ML features
    """
    __slots__ = (
        'market_structure',
        'order_blocks_count',
        'institutional_candle',
        'liquidity_grab',
        'fvg_size_atr',
        'fvg_proximity',
        'ob_proximity',
        'atr_normalized_volume',
        'rsi_14',
        'momentum_atr',
        'time_to_next_level',
        'confidence_ensemble',
        'timestamp',
        'symbol'
    )
    
    def __init__(
        self,
        market_structure: float = 0.0,
        order_blocks_count: float = 0.0,
        institutional_candle: float = 0.0,
        liquidity_grab: float = 0.0,
        fvg_size_atr: float = 0.0,
        fvg_proximity: float = 0.0,
        ob_proximity: float = 0.0,
        atr_normalized_volume: float = 0.0,
        rsi_14: float = 0.0,
        momentum_atr: float = 0.0,
        time_to_next_level: float = 0.0,
        confidence_ensemble: float = 0.0,
        timestamp: int = 0,
        symbol: str = ""
    ):
        """Initialize 12-feature vector"""
        self.market_structure = market_structure
        self.order_blocks_count = order_blocks_count
        self.institutional_candle = institutional_candle
        self.liquidity_grab = liquidity_grab
        self.fvg_size_atr = fvg_size_atr
        self.fvg_proximity = fvg_proximity
        self.ob_proximity = ob_proximity
        self.atr_normalized_volume = atr_normalized_volume
        self.rsi_14 = rsi_14
        self.momentum_atr = momentum_atr
        self.time_to_next_level = time_to_next_level
        self.confidence_ensemble = confidence_ensemble
        self.timestamp = timestamp
        self.symbol = symbol
    
    def to_list(self) -> List[float]:
        """Convert to list for ML model input"""
        return [
            self.market_structure,
            self.order_blocks_count,
            self.institutional_candle,
            self.liquidity_grab,
            self.fvg_size_atr,
            self.fvg_proximity,
            self.ob_proximity,
            self.atr_normalized_volume,
            self.rsi_14,
            self.momentum_atr,
            self.time_to_next_level,
            self.confidence_ensemble
        ]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'market_structure': self.market_structure,
            'order_blocks_count': self.order_blocks_count,
            'institutional_candle': self.institutional_candle,
            'liquidity_grab': self.liquidity_grab,
            'fvg_size_atr': self.fvg_size_atr,
            'fvg_proximity': self.fvg_proximity,
            'ob_proximity': self.ob_proximity,
            'atr_normalized_volume': self.atr_normalized_volume,
            'rsi_14': self.rsi_14,
            'momentum_atr': self.momentum_atr,
            'time_to_next_level': self.time_to_next_level,
            'confidence_ensemble': self.confidence_ensemble,
            'timestamp': self.timestamp,
            'symbol': self.symbol
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FeatureVector':
        """Create from dictionary"""
        return cls(**data)
    
    def __repr__(self) -> str:
        return f"Features({self.symbol} conf={self.confidence_ensemble:.2f})"


class TradeExperience:
    """
    Single trade experience for Experience Replay buffer
    
    Structure: (features, outcome)
    """
    __slots__ = ('features', 'outcome', 'timestamp', 'symbol')
    
    def __init__(
        self,
        features: FeatureVector,
        outcome: float,
        timestamp: int = 0,
        symbol: str = ""
    ):
        """
        Args:
            features: Input feature vector
            outcome: Trade result (profit/loss ratio or binary outcome)
            timestamp: When trade occurred
            symbol: Trading pair
        """
        self.features = features
        self.outcome = outcome
        self.timestamp = timestamp
        self.symbol = symbol
    
    def to_dict(self) -> Dict:
        """Serialize for Redis storage"""
        return {
            'features': self.features.to_dict(),
            'outcome': self.outcome,
            'timestamp': self.timestamp,
            'symbol': self.symbol
        }
    
    def __repr__(self) -> str:
        return f"TradeExperience({self.symbol} outcome={self.outcome:.4f})"
