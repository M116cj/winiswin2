"""
🤖 ML Predictor - LightGBM Confidence Scoring
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Load LightGBM model and predict confidence scores
Design: Stateless inference engine
"""

from typing import Dict, List, Optional
from pathlib import Path
import logging

# Try to import LightGBM, fall back to heuristic if not available
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except (ImportError, OSError) as e:
    logging.warning(f"⚠️ LightGBM not available: {e}")
    logging.warning("⚠️ Using heuristic confidence scoring (50-60% accuracy)")
    lgb = None
    LIGHTGBM_AVAILABLE = False

logger = logging.getLogger(__name__)


class MLPredictor:
    """
    LightGBM-based predictor for SMC confidence scores
    
    Model file: models/lgbm_smc.txt
    If missing: Returns neutral 0.5 score
    """
    
    def __init__(self, model_path: str = "models/lgbm_smc.txt"):
        """
        Initialize predictor
        
        Args:
            model_path: Path to LightGBM model file
        """
        self.model_path = model_path
        self.model: Optional[lgb.Booster] = None
        self.feature_names: List[str] = [
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
        ]
        self.loaded = False
        self._load_model()
    
    def _load_model(self):
        """Load LightGBM model from disk"""
        if not LIGHTGBM_AVAILABLE or lgb is None:
            logger.warning("⚠️ LightGBM not available, using heuristic")
            self.loaded = False
            return
        
        try:
            model_file = Path(self.model_path)
            
            if not model_file.exists():
                logger.warning(
                    f"⚠️ Model file not found: {self.model_path}\n"
                    f"   Will use default neutral confidence (0.5)\n"
                    f"   To use LightGBM: Place model at {self.model_path}"
                )
                self.loaded = False
                return
            
            self.model = lgb.Booster(model_file=str(model_file))
            self.loaded = True
            logger.info(f"✅ LightGBM model loaded: {self.model_path}")
        
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            self.loaded = False
    
    def predict_confidence(self, features: Dict) -> float:
        """
        Predict confidence score (0.0 to 1.0)
        
        Args:
            features: Dictionary of features from FeatureEngineer
        
        Returns: Confidence score (probability of profitable trade)
        """
        if not features:
            return 0.5
        
        # If model not loaded, use heuristic
        if not self.loaded:
            return self._heuristic_confidence(features)
        
        try:
            # Prepare feature vector in correct order
            feature_vector = [
                features.get(name, 0.0) for name in self.feature_names
            ]
            
            # LightGBM prediction (returns probability)
            prediction = self.model.predict([feature_vector])[0]
            
            # Clamp to [0, 1]
            confidence = max(0.0, min(1.0, float(prediction)))
            
            logger.debug(f"🤖 LightGBM confidence: {confidence:.3f}")
            
            return confidence
        
        except Exception as e:
            logger.error(f"❌ Prediction failed: {e}, using heuristic")
            return self._heuristic_confidence(features)
    
    def _heuristic_confidence(self, features: Dict) -> float:
        """
        Fallback heuristic when model is unavailable
        
        Combines multiple features for confidence estimate
        """
        confidence = 0.5  # Neutral baseline
        
        # SMC geometry signals
        market_structure = features.get('market_structure', 0)
        if market_structure != 0:
            confidence += 0.1 * market_structure
        
        liquidity_grab = features.get('liquidity_grab', 0)
        if liquidity_grab > 0:
            confidence += 0.15
        
        fvg_size = features.get('fvg_size_atr', 0)
        if fvg_size > 1.0:
            confidence += 0.1
        
        ob_proximity = features.get('ob_proximity', 0)
        if ob_proximity < 0.5:
            confidence += 0.1
        
        momentum = features.get('momentum_atr', 0)
        if abs(momentum) > 0.3:
            confidence += 0.05
        
        # Technical indicators
        rsi = features.get('rsi_14', 0.5)
        if 0.35 < rsi < 0.65:  # Neutral zone
            confidence -= 0.05
        elif rsi < 0.3 or rsi > 0.7:  # Extreme
            confidence += 0.1
        
        # Clamp and return
        confidence = max(0.0, min(1.0, confidence))
        
        logger.debug(f"📊 Heuristic confidence: {confidence:.3f}")
        
        return confidence
    
    def get_model_info(self) -> Dict:
        """Get model information"""
        return {
            'model_path': self.model_path,
            'loaded': self.loaded,
            'feature_count': len(self.feature_names),
            'feature_names': self.feature_names
        }


# Global singleton
_predictor: Optional[MLPredictor] = None


def get_predictor(model_path: str = "models/lgbm_smc.txt") -> MLPredictor:
    """Get or create global predictor"""
    global _predictor
    if _predictor is None:
        _predictor = MLPredictor(model_path)
    return _predictor
