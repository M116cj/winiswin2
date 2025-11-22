"""
⚙️ Feature Engineer - SMC → Numerical Features (Polars)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Convert SMC patterns to numerical features using polars
Design: High-speed dataframe operations for batch processing
"""

import polars as pl
import numpy as np
from typing import Dict, List, Optional
import logging

from src.core.indicators import Indicators

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Converts SMC detection results + OHLCV into ML-ready features
    
    All distances are normalized by ATR (volatility-adjusted)
    """
    
    def __init__(self):
        """Initialize feature engineer"""
        self.feature_names = [
            'market_structure',  # BOS bullish=1, bearish=-1
            'order_blocks_count',  # Number of strong candles
            'institutional_candle',  # Is current candle strong (0-1)
            'liquidity_grab',  # LS detected (1) or not (0)
            'fvg_size_atr',  # Fair Value Gap size in ATR
            'fvg_proximity',  # Distance to FVG in ATR (-1 to 1)
            'ob_proximity',  # Distance to Order Block in ATR
            'atr_normalized_volume',  # Volume / ATR
            'rsi_14',  # Relative Strength Index
            'momentum_atr',  # Price momentum in ATR
            'time_to_next_level',  # Bars to significant level
            'confidence_ensemble',  # Ensemble score from features
        ]
    
    @staticmethod
    def compute_atr(ohlcv: List[Dict], period: int = 14) -> float:
        """Compute ATR from OHLCV (delegates to centralized Indicators)"""
        highs = np.array([float(k['high']) for k in ohlcv])
        lows = np.array([float(k['low']) for k in ohlcv])
        closes = np.array([float(k['close']) for k in ohlcv])
        return Indicators.calculate_atr(highs, lows, closes, period)
    
    @staticmethod
    def compute_rsi(closes: np.ndarray, period: int = 14) -> float:
        """Compute RSI (delegates to centralized Indicators)"""
        return Indicators.calculate_rsi(closes, period)
    
    @staticmethod
    def process_data(df: pl.DataFrame) -> pl.DataFrame:
        """
        Process Polars dataframe with OHLCV data
        
        Adds computed features:
        - atr: Average True Range
        - dist_to_fvg_atr: Distance to nearest FVG / ATR
        - is_sweep: Boolean liquidity sweep flag
        - trend_strength: ADX-like trend metric
        
        Args:
            df: Polars DataFrame with columns: symbol, open, high, low, close, volume, timestamp
        
        Returns: DataFrame with added features
        """
        if df.is_empty():
            return df
        
        # Group by symbol for multi-coin processing
        try:
            processed = df.with_columns([
                # Calculate ATR for each symbol group
                pl.col('high').rolling_max(14).over(['symbol']).alias('high_max'),
                pl.col('low').rolling_min(14).over(['symbol']).alias('low_min'),
            ]).with_columns([
                (pl.col('high') - pl.col('low')).alias('tr'),
            ]).with_columns([
                pl.col('tr').rolling_mean(14).over(['symbol']).alias('atr'),
            ]).drop(['high_max', 'low_min'])
            
            # Add FVG detection flag
            processed = processed.with_columns([
                (pl.col('low').shift(2).over(['symbol']) > pl.col('high')).alias('fvg_bullish'),
                (pl.col('high').shift(2).over(['symbol']) < pl.col('low')).alias('fvg_bearish'),
            ]).with_columns([
                ((pl.col('fvg_bullish') | pl.col('fvg_bearish')).cast(pl.Int32)).alias('is_fvg'),
            ])
            
            # Add liquidity sweep flag
            processed = processed.with_columns([
                pl.col('low').rolling_min(10).over(['symbol']).alias('swing_low'),
                pl.col('high').rolling_max(10).over(['symbol']).alias('swing_high'),
            ]).with_columns([
                ((pl.col('close') < pl.col('swing_low')) | (pl.col('close') > pl.col('swing_high'))).cast(pl.Int32).alias('is_sweep'),
            ]).drop(['swing_low', 'swing_high'])
            
            # Add trend strength (simple momentum)
            processed = processed.with_columns([
                (pl.col('close') - pl.col('close').shift(14).over(['symbol'])).alias('momentum'),
            ]).with_columns([
                (pl.col('momentum') / pl.col('atr')).alias('trend_strength'),
            ]).drop('momentum')
            
            # Fill NaN values with defaults
            processed = processed.fill_null(0.0)
            
            return processed
        
        except Exception as e:
            logger.error(f"❌ Data processing failed: {e}")
            return df
    
    def compute_features(self, ohlcv: List[Dict], smc_results: Dict, min_size: int = 5) -> Dict:
        """
        Convert SMC patterns + OHLCV into numerical features
        
        Args:
            ohlcv: List of kline dicts
            smc_results: Results from SMCEngine (FVG, OB, LS, BOS)
            min_size: Minimum buffer size (default 5, use 20 in production)
        
        Returns: Dict of features for ML model
        """
        if not ohlcv or len(ohlcv) < min_size:
            return {name: 0.0 for name in self.feature_names}
        
        # Extract raw data
        closes = np.array([float(k['close']) for k in ohlcv])
        highs = np.array([float(k['high']) for k in ohlcv])
        lows = np.array([float(k['low']) for k in ohlcv])
        volumes = np.array([float(k.get('volume', 0)) for k in ohlcv])
        
        atr = self.compute_atr(ohlcv)
        
        # Feature 1: Market Structure (BOS)
        bos_result = smc_results.get('structure', {})
        market_structure = 1.0 if bos_result.get('bos_type') == 'bullish' else \
                          -1.0 if bos_result.get('bos_type') == 'bearish' else 0.0
        
        # Feature 2: Order Blocks Count
        ob_result = smc_results.get('order_block', {})
        ob_strength = ob_result.get('ob_strength_atr', 0)
        order_blocks_count = 1.0 if ob_strength > 1.5 else 0.0
        
        # Feature 3: Institutional Candle (strong last candle)
        last_candle_body = abs(closes[-1] - float(ohlcv[-1]['open']))
        institutional_candle = min(1.0, last_candle_body / atr)
        
        # Feature 4: Liquidity Grab
        ls_result = smc_results.get('liquidity_sweep', {})
        liquidity_grab = 1.0 if ls_result.get('ls_type') else 0.0
        
        # Feature 5: FVG Size in ATR
        fvg_result = smc_results.get('fvg', {})
        fvg_size_atr = fvg_result.get('fvg_size_atr', 0)
        
        # Feature 6: FVG Proximity (normalized distance to FVG)
        fvg_proximity = 0.0
        if fvg_result.get('fvg_type'):
            if fvg_result['fvg_type'] == 'bullish':
                dist = (closes[-1] - fvg_result['fvg_end']) / atr
            else:
                dist = (fvg_result['fvg_start'] - closes[-1]) / atr
            fvg_proximity = max(-1.0, min(1.0, dist))
        
        # Feature 7: OB Proximity
        ob_proximity = 0.0
        if ob_result.get('ob_type'):
            dist = abs(closes[-1] - ob_result.get('ob_price', closes[-1])) / atr
            ob_proximity = min(1.0, dist)
        
        # Feature 8: ATR Normalized Volume
        avg_volume = np.mean(volumes[-14:]) if len(volumes) >= 14 else np.mean(volumes)
        atr_normalized_volume = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        
        # Feature 9: RSI
        rsi_14 = self.compute_rsi(closes, period=14)
        
        # Feature 10: Momentum (price change in ATR)
        momentum = (closes[-1] - closes[-5]) / atr if len(closes) >= 5 else 0.0
        momentum_atr = max(-2.0, min(2.0, momentum))
        
        # Feature 11: Time to Next Level (bars to previous swing)
        swing_high = np.max(highs[-20:]) if len(highs) >= 20 else np.max(highs)
        swing_low = np.min(lows[-20:]) if len(lows) >= 20 else np.min(lows)
        
        time_to_next = 5.0  # Default
        if closes[-1] > swing_high or closes[-1] < swing_low:
            time_to_next = 1.0
        elif abs(closes[-1] - swing_high) / atr < 1.0:
            time_to_next = 2.0
        elif abs(closes[-1] - swing_low) / atr < 1.0:
            time_to_next = 2.0
        
        # Feature 12: Confidence Ensemble
        confidence = 0.5  # Neutral baseline
        if market_structure != 0:
            confidence += 0.1 * market_structure  # Direction alignment
        if liquidity_grab > 0:
            confidence += 0.15  # LS is strong signal
        if fvg_size_atr > 1.0:
            confidence += 0.1  # Significant FVG
        if ob_strength > 1.5:
            confidence += 0.1  # Strong OB
        if abs(momentum_atr) > 1.0:
            confidence += 0.05  # Trending
        
        confidence = max(0.0, min(1.0, confidence))
        
        return {
            'market_structure': market_structure,
            'order_blocks_count': order_blocks_count,
            'institutional_candle': institutional_candle,
            'liquidity_grab': liquidity_grab,
            'fvg_size_atr': fvg_size_atr,
            'fvg_proximity': fvg_proximity,
            'ob_proximity': ob_proximity,
            'atr_normalized_volume': atr_normalized_volume,
            'rsi_14': rsi_14 / 100.0,  # Normalize to 0-1
            'momentum_atr': momentum_atr / 2.0,  # Normalize to -1 to 1
            'time_to_next_level': time_to_next / 5.0,  # Normalize
            'confidence_ensemble': confidence,
        }
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature names"""
        return self.feature_names


# Global singleton
_feature_engineer: Optional[FeatureEngineer] = None


def get_feature_engineer() -> FeatureEngineer:
    """Get or create global feature engineer"""
    global _feature_engineer
    if _feature_engineer is None:
        _feature_engineer = FeatureEngineer()
    return _feature_engineer
