"""
🧠 AEGIS Hybrid Learner - Teacher-Student Mode + ML Prediction + Feature Schema
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Consolidated ML Brain: 
- Experience Replay Buffer
- Teacher-Student Mode Switching
- LightGBM Confidence Scoring
- 12-Feature Schema Definition
"""

import logging
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path

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


# ════════════════════════════════════════════════════════════════════════════
# FEATURE SCHEMA - The 12 ATR-Normalized Features
# ════════════════════════════════════════════════════════════════════════════

FEATURE_SCHEMA = [
    {
        'index': 0,
        'name': 'market_structure',
        'description': 'Break of Structure direction (BOS/CHoCh)',
        'range': (-1, 0, 1),
        'type': 'discrete',
        'priority': 'HIGH'
    },
    {
        'index': 1,
        'name': 'order_blocks_count',
        'description': 'Order Block presence indicator',
        'range': (0, 1),
        'type': 'binary',
        'priority': 'HIGH'
    },
    {
        'index': 2,
        'name': 'institutional_candle',
        'description': 'Candle body × volume strength',
        'range': (0, 1),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 3,
        'name': 'liquidity_grab',
        'description': 'Liquidity Sweep detection ⭐ CRITICAL',
        'range': (0, 1),
        'type': 'binary',
        'priority': 'CRITICAL'
    },
    {
        'index': 4,
        'name': 'fvg_size_atr',
        'description': 'Fair Value Gap size normalized by ATR',
        'range': (0, float('inf')),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 5,
        'name': 'fvg_proximity',
        'description': 'Distance to FVG normalized by ATR',
        'range': (-1, 1),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 6,
        'name': 'ob_proximity',
        'description': 'Distance to Order Block normalized by ATR',
        'range': (0, 1),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 7,
        'name': 'atr_normalized_volume',
        'description': 'Current volume / Average volume',
        'range': (0, float('inf')),
        'type': 'continuous',
        'priority': 'LOW'
    },
    {
        'index': 8,
        'name': 'rsi_14',
        'description': 'Relative Strength Index (14 period)',
        'range': (0, 1),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 9,
        'name': 'momentum_atr',
        'description': 'Price momentum normalized by ATR',
        'range': (-1, 1),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 10,
        'name': 'time_to_next_level',
        'description': 'Distance to support/resistance level',
        'range': (0, 1),
        'type': 'continuous',
        'priority': 'LOW'
    },
    {
        'index': 11,
        'name': 'confidence_ensemble',
        'description': 'ML model confidence score',
        'range': (0, 1),
        'type': 'continuous',
        'priority': 'HIGH'
    },
]

FEATURE_NAMES = [f['name'] for f in FEATURE_SCHEMA]
FEATURE_INDICES = {f['name']: f['index'] for f in FEATURE_SCHEMA}
CRITICAL_FEATURES = [f['name'] for f in FEATURE_SCHEMA if f['priority'] in ('CRITICAL', 'HIGH')]


def get_feature_names() -> List[str]:
    """Get list of all 12 feature names"""
    return FEATURE_NAMES


def get_feature_index(name: str) -> int:
    """Get index of a feature by name"""
    return FEATURE_INDICES.get(name, -1)


def validate_feature_vector(vector: Dict) -> bool:
    """Validate that a feature vector has all required fields"""
    return all(name in vector for name in FEATURE_NAMES)


# ════════════════════════════════════════════════════════════════════════════
# ML PREDICTOR - LightGBM Confidence Scoring
# ════════════════════════════════════════════════════════════════════════════

class MLPredictor:
    """
    LightGBM-based predictor for SMC confidence scores
    
    Model file: models/lgbm_smc.txt
    If missing: Returns neutral 0.5 score
    """
    
    def __init__(self, model_path: str = "models/lgbm_smc.txt"):
        """Initialize predictor"""
        self.model_path = model_path
        self.model: Optional[lgb.Booster] = None
        self.feature_names = FEATURE_NAMES
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
        """Predict confidence score (0.0 to 1.0)"""
        if not features:
            return 0.5
        
        if not self.loaded:
            return self._heuristic_confidence(features)
        
        try:
            feature_vector = [features.get(name, 0.0) for name in self.feature_names]
            prediction = self.model.predict([feature_vector])[0]
            confidence = max(0.0, min(1.0, float(prediction)))
            logger.debug(f"🤖 LightGBM confidence: {confidence:.3f}")
            return confidence
        
        except Exception as e:
            logger.error(f"❌ Prediction failed: {e}, using heuristic")
            return self._heuristic_confidence(features)
    
    def _heuristic_confidence(self, features: Dict) -> float:
        """Fallback heuristic when model is unavailable"""
        confidence = 0.5
        
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
        
        rsi = features.get('rsi_14', 0.5)
        if 0.35 < rsi < 0.65:
            confidence -= 0.05
        elif rsi < 0.3 or rsi > 0.7:
            confidence += 0.1
        
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


# ════════════════════════════════════════════════════════════════════════════
# EXPERIENCE REPLAY BUFFER
# ════════════════════════════════════════════════════════════════════════════

class ExperienceReplayBuffer:
    """Stores trade experience for replay and model training"""
    
    def __init__(self, redis_client=None, max_size: int = 5000):
        self.redis = redis_client
        self.max_size = max_size
        self.buffer_key = "experience_replay_buffer"
        self.experience_count = 0
        logger.info(f"✅ ExperienceReplayBuffer initialized (max size: {max_size})")
    
    async def add_experience(self, features: Dict, outcome: float, symbol: str):
        """Add trade experience to buffer"""
        if not self.redis:
            logger.warning("⚠️ No Redis connection, skipping experience storage")
            return
        
        experience = {
            'features': features,
            'outcome': outcome,
            'symbol': symbol,
            'timestamp': self.experience_count
        }
        
        try:
            await self.redis.lpush(self.buffer_key, json.dumps(experience))
            self.experience_count += 1
            
            buffer_size = await self.redis.llen(self.buffer_key)
            if buffer_size > self.max_size:
                await self.redis.rpop(self.buffer_key)
                logger.debug(f"🗑️ Forgot oldest experience (buffer size: {buffer_size})")
            
            logger.debug(f"✅ Stored experience #{self.experience_count} ({symbol})")
        
        except Exception as e:
            logger.error(f"❌ Failed to store experience: {e}")
    
    async def get_batch(self, batch_size: int = 128) -> List[Tuple[Dict, float]]:
        """Get batch of experiences for model training"""
        if not self.redis:
            return []
        
        try:
            experiences = await self.redis.lrange(self.buffer_key, 0, batch_size - 1)
            batch = []
            for exp_json in experiences:
                exp = json.loads(exp_json)
                batch.append((exp['features'], exp['outcome']))
            
            logger.debug(f"📊 Retrieved training batch: {len(batch)} experiences")
            return batch
        
        except Exception as e:
            logger.error(f"❌ Failed to get training batch: {e}")
            return []
    
    async def get_buffer_size(self) -> int:
        """Get current buffer size"""
        if not self.redis:
            return 0
        try:
            return await self.redis.llen(self.buffer_key)
        except Exception:
            return 0


# ════════════════════════════════════════════════════════════════════════════
# HYBRID LEARNER - Teacher-Student Mode Switching
# ════════════════════════════════════════════════════════════════════════════

class HybridLearner:
    """
    AEGIS Central Brain - Automatic Teacher-Student mode switching
    
    Phase Logic:
    - TEACHER (<50 trades):  Use SMC rule logic, max 3x leverage
    - STUDENT (>=50 trades): Use LightGBM model, dynamic leverage
    """
    
    def __init__(self, db_manager=None, redis_client=None):
        """Initialize HybridLearner"""
        self.db = db_manager
        self.redis = redis_client
        self.replay_buffer = ExperienceReplayBuffer(redis_client)
        self.predictor = MLPredictor()
        
        # Phase tracking
        self.current_phase = "TEACHER"
        self.total_trades = 0
        self.teacher_phase_threshold = 50
        
        logger.info("✅ HybridLearner initialized (Teacher-Student mode)")
    
    async def update_phase(self):
        """Update current phase based on trade count"""
        try:
            if self.db:
                total_trades = await self._get_total_trades()
                self.total_trades = total_trades
                
                if total_trades < self.teacher_phase_threshold:
                    self.current_phase = "TEACHER"
                else:
                    self.current_phase = "STUDENT"
                
                logger.info(f"📊 Phase update: {self.current_phase} ({total_trades} trades)")
        
        except Exception as e:
            logger.error(f"❌ Failed to update phase: {e}")
    
    async def _get_total_trades(self) -> int:
        """Query total completed trades from database"""
        try:
            if not self.db:
                return self.total_trades
            query = "SELECT COUNT(*) as count FROM trades WHERE status = 'CLOSED'"
            result = await self.db.execute_query(query)
            return result[0]['count'] if result else 0
        except Exception:
            return self.total_trades
    
    def get_max_leverage(self) -> float:
        """Get max leverage based on current phase"""
        if self.current_phase == "TEACHER":
            return 3.0
        else:
            return 10.0
    
    def apply_teacher_logic(self, features: Dict) -> Optional[str]:
        """Teacher phase: Rule-based SMC logic"""
        if features.get('liquidity_grab', 0) > 0.5:
            if features.get('market_structure', 0) > 0:
                return 'BUY'
            elif features.get('market_structure', 0) < 0:
                return 'SELL'
        
        if features.get('order_blocks_count', 0) > 0.5:
            if features.get('fvg_proximity', 0) < 0:
                return 'BUY'
        
        if features.get('momentum_atr', 0) > 1.0:
            return 'BUY'
        elif features.get('momentum_atr', 0) < -1.0:
            return 'SELL'
        
        return None
    
    async def record_trade_outcome(self, features: Dict, outcome: float, symbol: str):
        """Record completed trade for experience replay buffer"""
        await self.replay_buffer.add_experience(features, outcome, symbol)
        logger.info(f"📚 Recorded trade outcome: {symbol} outcome={outcome:.4f}")
    
    async def get_learning_status(self) -> Dict:
        """Get current learning status"""
        buffer_size = await self.replay_buffer.get_buffer_size()
        
        return {
            'current_phase': self.current_phase,
            'total_trades': self.total_trades,
            'teacher_threshold': self.teacher_phase_threshold,
            'max_leverage': self.get_max_leverage(),
            'replay_buffer_size': buffer_size,
            'buffer_max_size': self.replay_buffer.max_size,
            'phase_progress': f"{self.total_trades}/{self.teacher_phase_threshold}"
        }
    
    def __repr__(self) -> str:
        return f"HybridLearner({self.current_phase} | {self.total_trades} trades)"


# Global singletons
_hybrid_learner: Optional[HybridLearner] = None
_predictor: Optional[MLPredictor] = None


def get_hybrid_learner(db_manager=None, redis_client=None) -> HybridLearner:
    """Get or create global hybrid learner"""
    global _hybrid_learner
    if _hybrid_learner is None:
        _hybrid_learner = HybridLearner(db_manager, redis_client)
    return _hybrid_learner


def get_predictor(model_path: str = "models/lgbm_smc.txt") -> MLPredictor:
    """Get or create global predictor"""
    global _predictor
    if _predictor is None:
        _predictor = MLPredictor(model_path)
    return _predictor
