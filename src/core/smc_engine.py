"""
🧬 SMC Engine - Smart Money Concepts Geometry Detection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Detect SMC patterns (FVG, Order Blocks, Liquidity Sweeps, Structure)
Design: Stateless, lightweight, efficient for M1 candlesticks
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SMCEngine:
    """
    Stateless SMC geometry detection engine
    
    Methods detect:
    - Fair Value Gaps (FVG)
    - Order Blocks (OB)
    - Liquidity Sweeps (LS)
    - Break of Structure (BOS)
    - ATR-normalized distances
    """
    
    @staticmethod
    def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """
        Calculate Average True Range
        
        Args:
            highs: Array of high prices
            lows: Array of low prices
            closes: Array of close prices
            period: ATR period (default 14)
        
        Returns: ATR value
        """
        if len(highs) < period:
            return closes[-1] * 0.01  # Default to 1% if not enough data
        
        # Calculate True Range
        tr = np.zeros(len(highs))
        tr[0] = highs[0] - lows[0]
        
        for i in range(1, len(highs)):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
        
        # ATR is EMA of TR
        atr = np.mean(tr[-period:])
        return max(atr, 0.001)  # Avoid zero division
    
    @staticmethod
    def detect_fvg(kline_window: List[Dict]) -> Dict:
        """
        Detect Fair Value Gaps (FVG)
        
        FVG = Gap between consecutive candles (bullish or bearish)
        Bullish FVG: Previous candle low > Current candle high
        Bearish FVG: Previous candle high < Current candle low
        
        Args:
            kline_window: List of kline dicts with OHLCV
        
        Returns: {
            'fvg_type': 'bullish' | 'bearish' | None,
            'fvg_start': price,
            'fvg_end': price,
            'fvg_size_atr': normalized_size
        }
        """
        result = {
            'fvg_type': None,
            'fvg_start': 0,
            'fvg_end': 0,
            'fvg_size_atr': 0
        }
        
        if len(kline_window) < 2:
            return result
        
        closes = np.array([float(k['close']) for k in kline_window])
        atr = SMCEngine.calculate_atr(
            np.array([float(k['high']) for k in kline_window]),
            np.array([float(k['low']) for k in kline_window]),
            closes
        )
        
        prev_candle = kline_window[-2]
        curr_candle = kline_window[-1]
        
        prev_low = float(prev_candle['low'])
        prev_high = float(prev_candle['high'])
        curr_low = float(curr_candle['low'])
        curr_high = float(curr_candle['high'])
        
        # Bullish FVG: prev_low > curr_high
        if prev_low > curr_high:
            result['fvg_type'] = 'bullish'
            result['fvg_start'] = curr_high
            result['fvg_end'] = prev_low
            result['fvg_size_atr'] = (result['fvg_end'] - result['fvg_start']) / atr
        
        # Bearish FVG: prev_high < curr_low
        elif prev_high < curr_low:
            result['fvg_type'] = 'bearish'
            result['fvg_start'] = prev_high
            result['fvg_end'] = curr_low
            result['fvg_size_atr'] = (result['fvg_end'] - result['fvg_start']) / atr
        
        return result
    
    @staticmethod
    def detect_order_block(kline_window: List[Dict], lookback: int = 5) -> Dict:
        """
        Detect Order Blocks (Strong candles during structure)
        
        OB = Strong impulsive candle (large body, closing beyond midpoint)
        
        Args:
            kline_window: List of klines
            lookback: Number of candles to check
        
        Returns: {
            'ob_type': 'bullish' | 'bearish' | None,
            'ob_price': price,
            'ob_strength_atr': normalized_size
        }
        """
        result = {
            'ob_type': None,
            'ob_price': 0,
            'ob_strength_atr': 0
        }
        
        if len(kline_window) < lookback:
            return result
        
        recent = kline_window[-lookback:]
        closes = np.array([float(k['close']) for k in recent])
        opens = np.array([float(k['open']) for k in recent])
        highs = np.array([float(k['high']) for k in recent])
        lows = np.array([float(k['low']) for k in recent])
        
        atr = SMCEngine.calculate_atr(highs, lows, closes)
        
        # Check last candle for strength
        last_candle = recent[-1]
        body_size = abs(float(last_candle['close']) - float(last_candle['open']))
        body_range_ratio = body_size / atr
        
        # Strong bullish OB
        if float(last_candle['close']) > float(last_candle['open']) and body_range_ratio > 1.5:
            result['ob_type'] = 'bullish'
            result['ob_price'] = float(last_candle['low'])
            result['ob_strength_atr'] = body_range_ratio
        
        # Strong bearish OB
        elif float(last_candle['close']) < float(last_candle['open']) and body_range_ratio > 1.5:
            result['ob_type'] = 'bearish'
            result['ob_price'] = float(last_candle['high'])
            result['ob_strength_atr'] = body_range_ratio
        
        return result
    
    @staticmethod
    def detect_liquidity_sweep(kline_window: List[Dict], lookback: int = 10) -> Dict:
        """
        Detect Liquidity Sweeps (Recent High/Low break)
        
        LS = Price breaks recent swing high/low
        
        Args:
            kline_window: List of klines
            lookback: Number of candles to check for swing
        
        Returns: {
            'ls_type': 'bullish' | 'bearish' | None,
            'ls_level': price,
            'distance_atr': distance in ATR units
        }
        """
        result = {
            'ls_type': None,
            'ls_level': 0,
            'distance_atr': 0
        }
        
        if len(kline_window) < lookback + 1:
            return result
        
        recent = kline_window[-lookback:]
        all_closes = np.array([float(k['close']) for k in kline_window])
        atr = SMCEngine.calculate_atr(
            np.array([float(k['high']) for k in kline_window]),
            np.array([float(k['low']) for k in kline_window]),
            all_closes
        )
        
        recent_highs = np.array([float(k['high']) for k in recent])
        recent_lows = np.array([float(k['low']) for k in recent])
        
        swing_high = np.max(recent_highs)
        swing_low = np.min(recent_lows)
        
        current_close = all_closes[-1]
        
        # Bullish LS: Break of recent swing low
        if current_close < swing_low:
            result['ls_type'] = 'bullish'
            result['ls_level'] = swing_low
            result['distance_atr'] = (swing_low - current_close) / atr
        
        # Bearish LS: Break of recent swing high
        elif current_close > swing_high:
            result['ls_type'] = 'bearish'
            result['ls_level'] = swing_high
            result['distance_atr'] = (current_close - swing_high) / atr
        
        return result
    
    @staticmethod
    def detect_structure(kline_window: List[Dict]) -> Dict:
        """
        Detect Break of Structure (BOS)
        
        BOS = Price action breaks above/below previous highs/lows
        
        Args:
            kline_window: List of klines
        
        Returns: {
            'bos_type': 'bullish' | 'bearish' | None,
            'bos_level': price
        }
        """
        result = {
            'bos_type': None,
            'bos_level': 0
        }
        
        if len(kline_window) < 5:
            return result
        
        closes = np.array([float(k['close']) for k in kline_window])
        highs = np.array([float(k['high']) for k in kline_window])
        lows = np.array([float(k['low']) for k in kline_window])
        
        # Get last 5 candles structure
        recent = kline_window[-5:]
        recent_highs = [float(k['high']) for k in recent]
        recent_lows = [float(k['low']) for k in recent]
        
        # Previous structure
        prev_high = max(recent_highs[:-1]) if len(recent_highs) > 1 else recent_highs[0]
        prev_low = min(recent_lows[:-1]) if len(recent_lows) > 1 else recent_lows[0]
        
        current_high = float(recent[-1]['high'])
        current_low = float(recent[-1]['low'])
        
        # Bullish BOS: Break of previous high
        if current_high > prev_high:
            result['bos_type'] = 'bullish'
            result['bos_level'] = prev_high
        
        # Bearish BOS: Break of previous low
        elif current_low < prev_low:
            result['bos_type'] = 'bearish'
            result['bos_level'] = prev_low
        
        return result
