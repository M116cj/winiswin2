"""
🧠 Intelligence Layer - Complete SMC + ML Integration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Unified interface for SMC pattern detection + ML prediction
This module orchestrates the entire intelligence pipeline:
  1. SMCEngine detects patterns (FVG, OB, LS, BOS)
  2. FeatureEngineer converts patterns to numerical features
  3. MLPredictor generates confidence scores
"""

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class IntelligenceLayer:
    """
    Complete intelligence pipeline for trading signal generation
    
    Pipeline:
    - Input: OHLCV klines for a symbol
    - Step 1: Detect SMC patterns
    - Step 2: Engineer features
    - Step 3: Predict confidence score
    - Output: Signal with confidence (0.0-1.0)
    """
    
    def __init__(self):
        """Initialize intelligence layer"""
        from src.core.smc_engine import SMCEngine
        from src.ml.feature_engineer import get_feature_engineer
        from src.ml.predictor import get_predictor
        
        self.smc_engine = SMCEngine()
        self.feature_engineer = get_feature_engineer()
        self.predictor = get_predictor()
        
        logger.info("✅ IntelligenceLayer initialized")
    
    def analyze_klines(self, klines: List[Dict], min_buffer_size: int = 20) -> Dict:
        """
        Analyze klines and generate trading signal
        
        Args:
            klines: List of kline dicts with OHLCV
            min_buffer_size: Minimum candles needed for analysis
        
        Returns: {
            'signal': 'buy' | 'sell' | 'neutral',
            'confidence': 0.0-1.0,
            'patterns': {
                'fvg': {...},
                'order_block': {...},
                'liquidity_sweep': {...},
                'structure': {...}
            },
            'features': {all 12 features},
            'metadata': {...}
        }
        """
        if not klines or len(klines) < min_buffer_size:
            return self._empty_signal()
        
        try:
            # Step 1: Detect SMC patterns
            patterns = self._detect_patterns(klines)
            
            # Step 2: Engineer features
            features = self.feature_engineer.compute_features(klines, patterns)
            
            # Step 3: Predict confidence
            confidence = self.predictor.predict_confidence(features)
            
            # Step 4: Generate signal
            signal = self._generate_signal(patterns, confidence)
            
            return {
                'signal': signal,
                'confidence': confidence,
                'patterns': patterns,
                'features': features,
                'metadata': {
                    'candles_analyzed': len(klines),
                    'current_price': float(klines[-1]['close']),
                    'timestamp': klines[-1].get('time', 0)
                }
            }
        
        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}")
            return self._empty_signal()
    
    def _detect_patterns(self, klines: List[Dict]) -> Dict:
        """Detect all SMC patterns"""
        return {
            'fvg': self.smc_engine.detect_fvg(klines),
            'order_block': self.smc_engine.detect_order_block(klines),
            'liquidity_sweep': self.smc_engine.detect_liquidity_sweep(klines),
            'structure': self.smc_engine.detect_structure(klines),
        }
    
    def _generate_signal(self, patterns: Dict, confidence: float) -> str:
        """
        Generate trading signal based on patterns and confidence
        
        Rules:
        - Buy: Bullish patterns + high confidence
        - Sell: Bearish patterns + high confidence
        - Neutral: Low confidence or mixed signals
        """
        if confidence < 0.5:
            return 'neutral'
        
        # Count bullish and bearish signals
        bullish_count = 0
        bearish_count = 0
        
        # FVG
        if patterns['fvg'].get('fvg_type') == 'bullish':
            bullish_count += 1
        elif patterns['fvg'].get('fvg_type') == 'bearish':
            bearish_count += 1
        
        # Order Block
        if patterns['order_block'].get('ob_type') == 'bullish':
            bullish_count += 1
        elif patterns['order_block'].get('ob_type') == 'bearish':
            bearish_count += 1
        
        # Liquidity Sweep
        if patterns['liquidity_sweep'].get('ls_type') == 'bullish':
            bullish_count += 1
        elif patterns['liquidity_sweep'].get('ls_type') == 'bearish':
            bearish_count += 1
        
        # Break of Structure
        if patterns['structure'].get('bos_type') == 'bullish':
            bullish_count += 1
        elif patterns['structure'].get('bos_type') == 'bearish':
            bearish_count += 1
        
        # Determine signal
        if bullish_count > bearish_count:
            return 'buy'
        elif bearish_count > bullish_count:
            return 'sell'
        else:
            return 'neutral'
    
    def _empty_signal(self) -> Dict:
        """Return empty/neutral signal"""
        return {
            'signal': 'neutral',
            'confidence': 0.5,
            'patterns': {},
            'features': {name: 0.0 for name in self.feature_engineer.feature_names},
            'metadata': {
                'candles_analyzed': 0,
                'current_price': 0.0,
                'timestamp': 0
            }
        }
    
    def batch_analyze(self, symbol_klines: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """
        Analyze multiple symbols in parallel
        
        Args:
            symbol_klines: {symbol: [klines]}
        
        Returns:
            {symbol: analysis_result}
        """
        results = {}
        for symbol, klines in symbol_klines.items():
            try:
                results[symbol] = self.analyze_klines(klines)
            except Exception as e:
                logger.error(f"❌ {symbol} analysis failed: {e}")
                results[symbol] = self._empty_signal()
        
        return results


# Global singleton
_intelligence_layer: Optional[IntelligenceLayer] = None


def get_intelligence_layer() -> IntelligenceLayer:
    """Get or create global intelligence layer"""
    global _intelligence_layer
    if _intelligence_layer is None:
        _intelligence_layer = IntelligenceLayer()
    return _intelligence_layer
