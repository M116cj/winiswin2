"""
📊 Centralized Indicators Module - Single Source of Truth
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Eliminate duplicate indicator calculations
- ATR (Average True Range)
- RSI (Relative Strength Index)
- All other technical indicators

Used by both SMCEngine and FeatureEngineer to avoid redundant computation.
"""

import numpy as np
from typing import List, Dict


class Indicators:
    """Centralized indicator calculations - single source of truth"""
    
    @staticmethod
    def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """
        Calculate Average True Range (ATR)
        
        Used by both SMC detection and ML feature engineering
        """
        if len(highs) < period:
            return closes[-1] * 0.01 if len(closes) > 0 else 0.01
        
        tr = np.zeros(len(highs))
        tr[0] = highs[0] - lows[0]
        
        for i in range(1, len(highs)):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
        
        atr = float(np.mean(tr[-period:]))
        return max(atr, 0.001)  # Avoid zero division
    
    @staticmethod
    def calculate_rsi(closes: np.ndarray, period: int = 14) -> float:
        """
        Calculate Relative Strength Index (RSI)
        
        Used by both SMC analysis and ML features
        """
        if len(closes) < period + 1:
            return 50.0
        
        deltas = np.diff(closes[-period-1:])
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        rs = up / down if down != 0 else 1.0
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return float(rsi)
    
    @staticmethod
    def calculate_momentum(closes: np.ndarray, period: int = 5) -> float:
        """
        Calculate Momentum (Rate of Change)
        
        Period: Usually 5-14 periods
        """
        if len(closes) < period:
            return 0.0
        
        return float((closes[-1] - closes[-period]) / closes[-period] * 100) if closes[-period] != 0 else 0.0
