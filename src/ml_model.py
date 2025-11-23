"""
🤖 ML Model - Signal Quality Prediction + Confidence Scoring
Learns from historical trades to improve signal filtering
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    import joblib
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("⚠️ scikit-learn not available, ML model disabled")


class MLModel:
    """
    Machine Learning model for signal quality prediction
    
    Learns to:
    1. Predict win probability from signal features
    2. Adjust confidence scores based on historical patterns
    3. Filter low-quality signals early
    """
    
    def __init__(self, model_type: str = "random_forest"):
        """
        Initialize ML model
        
        Args:
            model_type: "random_forest" or "gradient_boosting"
        """
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = [
            'confidence',
            'fvg_detected',
            'liquidity_score',
            'position_size_pct',
            'rsi',
            'atr',
            'macd',
            'bb_width'
        ]
        
        if HAS_SKLEARN:
            self._init_model()
            logger.info(f"✅ ML Model initialized: {model_type}")
        else:
            logger.warning("⚠️ ML Model disabled (scikit-learn not available)")
    
    def _init_model(self):
        """Initialize the sklearn model"""
        if not HAS_SKLEARN:
            return
        
        if self.model_type == "random_forest":
            self.model = RandomForestClassifier(
                n_estimators=50,        # 50 trees (balance speed/accuracy)
                max_depth=8,            # Shallow trees for speed
                random_state=42,
                n_jobs=-1               # Use all cores
            )
        elif self.model_type == "gradient_boosting":
            self.model = GradientBoostingClassifier(
                n_estimators=30,        # Fewer boosting iterations
                learning_rate=0.1,
                max_depth=4,            # Very shallow
                random_state=42
            )
    
    def _extract_features(self, signal_data: Dict) -> Optional[List[float]]:
        """
        Extract features from signal for ML prediction
        
        Args:
            signal_data: {confidence, patterns, position_size, rsi, atr, macd, bb_width}
        
        Returns:
            Feature vector
        """
        try:
            features = [
                signal_data.get('confidence', 0.5),
                float(signal_data.get('patterns', {}).get('fvg', 0)),
                signal_data.get('patterns', {}).get('liquidity', 0.5),
                signal_data.get('position_size', 100) / 10000,  # Normalize to %
                signal_data.get('rsi', 50) / 100,  # Normalize 0-100 to 0-1
                signal_data.get('atr', 0) / 1000,  # Rough normalize
                signal_data.get('macd', 0) / 100,  # Normalize
                signal_data.get('bb_width', 0) / 1000  # Normalize
            ]
            return features
        except Exception as e:
            logger.debug(f"Error extracting features: {e}")
            return None
    
    async def train(self, training_data: List[Dict]) -> bool:
        """
        Train ML model on historical trades
        
        Args:
            training_data: List of complete trades {confidence, patterns, outcome}
        
        Returns:
            True if training successful
        """
        if not HAS_SKLEARN or not self.model:
            logger.warning("⚠️ Training skipped: scikit-learn not available")
            return False
        
        try:
            if len(training_data) < 10:
                logger.warning(f"⚠️ Insufficient data for training: {len(training_data)} samples")
                return False
            
            # Extract features and labels
            X = []
            y = []
            
            for trade in training_data:
                features = self._extract_features(trade)
                outcome = trade.get('outcome', {})
                
                if features and outcome:
                    X.append(features)
                    y.append(1 if outcome.get('win', False) else 0)
            
            if len(X) < 10:
                logger.warning(f"⚠️ Not enough valid samples: {len(X)}")
                return False
            
            # Convert to numpy arrays
            X_array = np.array(X)
            y_array = np.array(y)
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X_array)
            
            # Train model
            self.model.fit(X_scaled, y_array)
            self.is_trained = True
            
            # Calculate accuracy
            accuracy = self.model.score(X_scaled, y_array)
            
            logger.critical(f"🤖 ML Model trained: {len(X)} samples, {accuracy:.1%} accuracy")
            return True
        
        except Exception as e:
            logger.error(f"❌ Training failed: {e}", exc_info=True)
            return False
    
    def predict_win_probability(self, signal_data: Dict) -> float:
        """
        Predict probability that a signal will be profitable
        
        Args:
            signal_data: Signal features
        
        Returns:
            Win probability (0.0 to 1.0)
        """
        if not HAS_SKLEARN or not self.is_trained or not self.model:
            # Return signal's own confidence if model not trained
            return signal_data.get('confidence', 0.5)
        
        try:
            features = self._extract_features(signal_data)
            if not features:
                return signal_data.get('confidence', 0.5)
            
            # Scale features using same scaler
            X = np.array([features])
            X_scaled = self.scaler.transform(X)
            
            # Get probability
            probabilities = self.model.predict_proba(X_scaled)[0]
            win_prob = probabilities[1]  # Probability of class 1 (win)
            
            return float(win_prob)
        
        except Exception as e:
            logger.debug(f"Prediction error: {e}")
            return signal_data.get('confidence', 0.5)
    
    async def adjust_confidence(self, signal_data: Dict) -> Dict:
        """
        Adjust signal confidence based on ML prediction
        
        Args:
            signal_data: Original signal
        
        Returns:
            Signal with adjusted confidence
        """
        original_confidence = signal_data.get('confidence', 0.5)
        
        # Get ML prediction
        win_prob = self.predict_win_probability(signal_data)
        
        # Blend original confidence with ML prediction (70% original, 30% ML)
        adjusted_confidence = (original_confidence * 0.7) + (win_prob * 0.3)
        
        signal_data['original_confidence'] = original_confidence
        signal_data['ml_confidence'] = win_prob
        signal_data['confidence'] = adjusted_confidence
        
        logger.debug(f"🤖 Confidence adjusted: {original_confidence:.2f} → {adjusted_confidence:.2f}")
        
        return signal_data
    
    def save(self, filepath: str) -> bool:
        """Save trained model to disk"""
        if not HAS_SKLEARN or not self.is_trained:
            return False
        
        try:
            joblib.dump(self.model, f"{filepath}.model")
            joblib.dump(self.scaler, f"{filepath}.scaler")
            logger.info(f"💾 Model saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving model: {e}")
            return False
    
    def load(self, filepath: str) -> bool:
        """Load trained model from disk"""
        if not HAS_SKLEARN:
            return False
        
        try:
            self.model = joblib.load(f"{filepath}.model")
            self.scaler = joblib.load(f"{filepath}.scaler")
            self.is_trained = True
            logger.info(f"📖 Model loaded from {filepath}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Could not load model: {e}")
            return False


# Global instance
_model: Optional[MLModel] = None


def get_ml_model() -> MLModel:
    """Get or create global ML model"""
    global _model
    if _model is None:
        _model = MLModel()
    return _model
