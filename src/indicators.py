"""
📊 Indicators - Pure Stateless Functions (Numba JIT Compiled)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Centralized indicator calculations with Numba JIT compilation.
No state, no coupling, blazing fast.
"""

from typing import Tuple
import numpy as np

try:
    from numba import jit, njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    # Dummy decorator if Numba not available
    def jit(*args, **kwargs):  # type: ignore
        def decorator(func):  # type: ignore
            return func
        return decorator
    def njit(*args, **kwargs):  # type: ignore
        def decorator(func):  # type: ignore
            return func
        return decorator


# JIT-compiled fast math functions
@njit(cache=True)
def _calculate_tr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> np.ndarray:
    """Calculate True Range (JIT compiled)"""
    n = len(closes)
    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
    
    return tr


@njit(cache=True)
def _calculate_rsi_fast(prices: np.ndarray, period: int) -> float:
    """Calculate RSI (JIT compiled)"""
    if len(prices) < period + 1:
        return 50.0
    
    deltas = np.diff(prices)
    gains = np.zeros(len(deltas))
    losses = np.zeros(len(deltas))
    
    for i in range(len(deltas)):
        if deltas[i] > 0:
            gains[i] = deltas[i]
        else:
            losses[i] = -deltas[i]
    
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return float(100.0)
    
    rs = avg_gain / avg_loss
    result: float = 100.0 - (100.0 / (1.0 + rs))
    return result


class Indicators:
    """Pure stateless indicator calculations (Numba accelerated)"""
    
    @staticmethod
    def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Calculate Average True Range (Numba JIT compiled)"""
        if len(closes) < period:
            return 0.0
        
        tr = _calculate_tr(highs, lows, closes)
        return float(np.mean(tr[-period:]))
    
    @staticmethod
    def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
        """Calculate Relative Strength Index (Numba JIT compiled)"""
        if len(prices) < period + 1:
            return 50.0
        
        return float(_calculate_rsi_fast(prices, period))
    
    @staticmethod
    def calculate_momentum(prices: np.ndarray, period: int = 12) -> float:
        """Calculate momentum (pure Python, very fast)"""
        if len(prices) < period + 1:
            return 0.0
        
        return float(prices[-1] - prices[-period - 1])
    
    @staticmethod
    @njit(cache=True)
    def calculate_bollinger_bands(prices: np.ndarray, period: int = 20, num_std: float = 2.0) -> tuple:
        """Calculate Bollinger Bands (JIT compiled)"""
        if len(prices) < period:
            return (0.0, 0.0, 0.0)
        
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper = sma + (num_std * std)
        lower = sma - (num_std * std)
        
        return (upper, sma, lower)


# Print Numba status at import
if HAS_NUMBA:
    import logging
    logger = logging.getLogger(__name__)
    logger.debug("✅ Numba JIT compilation enabled for indicators")
