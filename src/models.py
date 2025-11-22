"""
🔄 Object Pool - Memory Efficiency for High-Frequency Trading
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pre-allocate objects to reduce garbage collection pressure.
Objects are acquired/released from pool instead of created/destroyed.
"""

import logging
from typing import Dict, Any, Optional
from collections import deque

logger = logging.getLogger(__name__)


class Candle:
    """Market candle data (OHLCV)"""
    
    __slots__ = ['symbol', 'open', 'high', 'low', 'close', 'volume', 'time']
    
    def __init__(self, symbol: str = '', open: float = 0.0, high: float = 0.0,
                 low: float = 0.0, close: float = 0.0, volume: float = 0.0,
                 time: int = 0):
        self.symbol = symbol
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.time = time
    
    def reset(self) -> None:
        """Reset to empty state"""
        self.symbol = ''
        self.open = 0.0
        self.high = 0.0
        self.low = 0.0
        self.close = 0.0
        self.volume = 0.0
        self.time = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'time': self.time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Candle':
        """Create from dictionary"""
        return cls(
            symbol=data.get('symbol', ''),
            open=float(data.get('open', 0.0)),
            high=float(data.get('high', 0.0)),
            low=float(data.get('low', 0.0)),
            close=float(data.get('close', 0.0)),
            volume=float(data.get('volume', 0.0)),
            time=int(data.get('time', 0))
        )


class Signal:
    """Trading signal"""
    
    __slots__ = ['symbol', 'confidence', 'patterns', 'position_size', 'side']
    
    def __init__(self, symbol: str = '', confidence: float = 0.0,
                 patterns: Optional[Dict[str, Any]] = None, position_size: float = 0.0,
                 side: str = ''):
        self.symbol = symbol
        self.confidence = confidence
        self.patterns = patterns or {}
        self.position_size = position_size
        self.side = side
    
    def reset(self) -> None:
        """Reset to empty state"""
        self.symbol = ''
        self.confidence = 0.0
        self.patterns = {}
        self.position_size = 0.0
        self.side = ''
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'confidence': self.confidence,
            'patterns': self.patterns,
            'position_size': self.position_size,
            'side': self.side
        }


class ObjectPool:
    """Generic object pool for pre-allocated objects"""
    
    def __init__(self, object_class: type, size: int = 10000):
        """
        Initialize object pool
        
        Args:
            object_class: Class to instantiate objects from
            size: Number of pre-allocated objects
        """
        self.object_class = object_class
        self.pool: deque = deque(maxlen=size)
        self.size = size
        self.acquired = 0
        self.released = 0
        
        # Pre-allocate objects
        for _ in range(size):
            self.pool.append(object_class())
        
        logger.info(f"🔄 ObjectPool initialized: {object_class.__name__} x{size}")
    
    def acquire(self) -> Any:
        """Get object from pool"""
        if self.pool:
            self.acquired += 1
            return self.pool.popleft()
        else:
            # Fallback: create new if pool exhausted
            logger.warning(f"⚠️ {self.object_class.__name__} pool exhausted, creating new")
            return self.object_class()
    
    def release(self, obj: Any) -> None:
        """Return object to pool"""
        if hasattr(obj, 'reset'):
            obj.reset()
        self.released += 1
        self.pool.append(obj)
    
    def stats(self) -> Dict[str, int]:
        """Get pool statistics"""
        return {
            'available': len(self.pool),
            'capacity': self.size,
            'acquired': self.acquired,
            'released': self.released
        }


# Global pools
_candle_pool: ObjectPool = ObjectPool(Candle, size=10000)
_signal_pool: ObjectPool = ObjectPool(Signal, size=10000)


def get_candle_pool() -> ObjectPool:
    """Get global candle pool"""
    return _candle_pool


def get_signal_pool() -> ObjectPool:
    """Get global signal pool"""
    return _signal_pool


def acquire_candle() -> Candle:
    """Acquire candle from pool"""
    return _candle_pool.acquire()


def release_candle(candle: Candle) -> None:
    """Release candle back to pool"""
    _candle_pool.release(candle)


def acquire_signal() -> Signal:
    """Acquire signal from pool"""
    return _signal_pool.acquire()


def release_signal(signal: Signal) -> None:
    """Release signal back to pool"""
    _signal_pool.release(signal)


def pool_stats() -> Dict[str, Dict[str, int]]:
    """Get statistics for all pools"""
    return {
        'candle': _candle_pool.stats(),
        'signal': _signal_pool.stats()
    }
