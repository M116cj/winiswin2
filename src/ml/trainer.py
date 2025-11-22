"""
🤖 ML Model Trainer - Offline Training Module
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Train LightGBM models for SMC pattern prediction (offline)
Labeling: 2:1 Reward/Risk - Target = 1 if price +1 ATR before -0.5 ATR
This module is used during development/backtesting, not in production trading
"""

import logging
from typing import Tuple, List, Dict, Any, Optional
import polars as pl
import numpy as np

logger = logging.getLogger(__name__)


class MLTrainer:
    """
    Offline model trainer using LightGBM
    
    Training Flow:
    1. Load historical OHLCV + SMC patterns from database
    2. Engineer features using FeatureEngineer
    3. Create labels using 2:1 reward/risk ratio
    4. Train LightGBM classifier
    5. Save model to models/lgbm_smc.txt
    """
    
    def __init__(self):
        """Initialize trainer"""
        self.model = None
        self.feature_names = [
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
        logger.info("✅ MLTrainer initialized (offline training mode)")
    
    def load_training_data(self, limit: int = 10000) -> Tuple[pl.DataFrame, pl.Series]:
        """
        Load training data from database
        
        Args:
            limit: Max number of candles to load
        
        Returns:
            (features_df, labels_series)
        """
        logger.info(f"📊 Loading training data (limit={limit})...")
        
        # Placeholder: In production, load from PostgreSQL
        # Example: SELECT * FROM klines WHERE symbol IN (...) ORDER BY timestamp DESC LIMIT ?
        
        return pl.DataFrame(), pl.Series("label", [])
    
    @staticmethod
    def create_labels(
        closes: np.ndarray,
        atr: float,
        lookback: int = 20
    ) -> np.ndarray:
        """
        Create labels using 2:1 Reward/Risk ratio
        
        Label = 1 if:
            - Price moves +1 ATR before -0.5 ATR (within lookback bars)
        Label = 0 otherwise
        
        Args:
            closes: Array of close prices
            atr: Average True Range value
            lookback: Number of future bars to check
        
        Returns:
            Array of labels (0 or 1)
        """
        labels = np.zeros(len(closes))
        
        for i in range(len(closes) - lookback):
            current_price = closes[i]
            future_prices = closes[i+1:i+lookback+1]
            
            # Target price: +1 ATR (profit)
            profit_target = current_price + atr
            # Stop loss: -0.5 ATR
            stop_loss = current_price - 0.5 * atr
            
            # Check if price hits profit before stop loss
            for future_price in future_prices:
                if future_price >= profit_target:
                    labels[i] = 1  # Profitable signal
                    break
                elif future_price <= stop_loss:
                    labels[i] = 0  # Hit stop loss
                    break
        
        return labels
    
    def generate_features(
        self,
        df: pl.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate features and labels for training
        
        Args:
            df: Polars DataFrame with OHLCV + SMC patterns
        
        Returns:
            (features_array, labels_array)
        """
        try:
            from src.ml.feature_engineer import FeatureEngineer
            from src.core.smc_engine import SMCEngine
            
            feature_engineer = FeatureEngineer()
            
            # Extract arrays
            closes = np.array(df['close'].to_list(), dtype=float)
            highs = np.array(df['high'].to_list(), dtype=float)
            lows = np.array(df['low'].to_list(), dtype=float)
            
            # Calculate ATR
            atr = SMCEngine.calculate_atr(highs, lows, closes)
            
            # Create labels
            labels = self.create_labels(closes, atr)
            
            # Generate features (convert dict list to numpy)
            features_list = []
            for i, row in enumerate(df.to_dicts()):
                # Simulate SMC results (minimal for demo)
                smc_results = {
                    'fvg': {'fvg_type': None, 'fvg_size_atr': 0},
                    'order_block': {'ob_type': None, 'ob_strength_atr': 0},
                    'liquidity_sweep': {'ls_type': None},
                    'structure': {'bos_type': None},
                }
                
                # Create feature dict from row
                ohlcv_dict = {
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row.get('volume', 0),
                }
                
                # Build OHLCV list for feature engineer
                ohlcv = [ohlcv_dict] if i == 0 else [ohlcv_dict]
                
                # Compute features
                features_dict = feature_engineer.compute_features(
                    ohlcv,
                    smc_results,
                    min_size=1
                )
                
                # Convert to array in correct order
                features_array = np.array([
                    features_dict.get(name, 0.0) for name in self.feature_names
                ])
                features_list.append(features_array)
            
            if not features_list:
                return np.array([]), np.array([])
            
            features = np.array(features_list)
            return features, labels
        
        except Exception as e:
            logger.error(f"❌ Feature generation failed: {e}")
            return np.array([]), np.array([])
    
    def train(self, X: np.ndarray, y: np.ndarray) -> bool:
        """
        Train LightGBM model
        
        Args:
            X: Feature array (N, 12)
            y: Target array (N,)
        
        Returns:
            Success flag
        """
        try:
            if len(X) == 0 or len(y) == 0:
                logger.warning("⚠️ Empty training data")
                return False
            
            logger.info(f"🚀 Training LightGBM model (samples={len(X)})...")
            
            # Import lightgbm if available
            try:
                import lightgbm as lgb
                
                # Train
                self.model = lgb.LGBMClassifier(
                    n_estimators=100,
                    learning_rate=0.1,
                    num_leaves=31,
                    max_depth=5,
                    random_state=42,
                    verbose=-1,
                    feature_name=self.feature_names
                )
                self.model.fit(X, y)
                
                logger.info("✅ Model training complete")
                logger.info(f"   Features: {len(self.feature_names)}")
                logger.info(f"   Samples: {len(X)}")
                
                return True
            
            except ImportError:
                logger.warning("⚠️ LightGBM not available - using heuristic fallback")
                return False
        
        except Exception as e:
            logger.error(f"❌ Training failed: {e}")
            return False
    
    def save_model(self, filepath: str = "models/lgbm_smc.txt") -> bool:
        """
        Save trained model to file
        
        Args:
            filepath: Output path
        
        Returns:
            Success flag
        """
        if not self.model:
            logger.error("❌ No model to save")
            return False
        
        try:
            self.model.booster_.save_model(filepath)
            logger.info(f"✅ Model saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save model: {e}")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """Get trainer info"""
        return {
            'type': 'LightGBM Classifier',
            'purpose': 'SMC Pattern Prediction (2:1 Reward/Risk)',
            'model_loaded': self.model is not None,
            'mode': 'Offline Training',
            'feature_count': len(self.feature_names)
        }


# Global singleton
_trainer: Optional[MLTrainer] = None


def get_trainer() -> MLTrainer:
    """Get or create global trainer"""
    global _trainer
    if _trainer is None:
        _trainer = MLTrainer()
    return _trainer
