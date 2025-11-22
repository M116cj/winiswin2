"""
📊 Indicators - Pure Stateless Functions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Centralized indicator calculations. No state, no coupling.
"""

import numpy as np


class Indicators:
    """Pure stateless indicator calculations"""
    
    @staticmethod
    def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(closes) < period:
            return 0.0
        
        tr = np.maximum(
            highs - lows,
            np.maximum(
                np.abs(highs - np.roll(closes, 1)),
                np.abs(lows - np.roll(closes, 1))
            )
        )
        return float(np.mean(tr[-period:]))
    
    @staticmethod
    def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return float(100.0 - (100.0 / (1.0 + rs)))
    
    @staticmethod
    def calculate_momentum(prices: np.ndarray, period: int = 12) -> float:
        """Calculate momentum"""
        if len(prices) < period + 1:
            return 0.0
        
        return float(prices[-1] - prices[-period - 1])
