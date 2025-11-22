"""
🧠 AEGIS Hybrid Learner - Teacher-Student Mode with Experience Replay
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Integrated online learning with automatic mode switching
Design: 
  - Teacher Phase (<50 trades): Rule-based SMC logic, max 3x leverage
  - Student Phase (>=50 trades): LightGBM model, dynamic leverage
  - Experience Replay: Redis buffer of last 5000 trade results
"""

import logging
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class ExperienceReplayBuffer:
    """
    Stores trade experience (features + outcomes) for replay and model training
    
    Uses Redis List to maintain last 5000 experiences
    """
    
    def __init__(self, redis_client=None, max_size: int = 5000):
        """
        Args:
            redis_client: Redis connection (from UnifiedDatabaseManager)
            max_size: Maximum buffer size before forgetting
        """
        self.redis = redis_client
        self.max_size = max_size
        self.buffer_key = "experience_replay_buffer"
        self.experience_count = 0
        
        logger.info(f"✅ ExperienceReplayBuffer initialized (max size: {max_size})")
    
    async def add_experience(self, features: Dict, outcome: float, symbol: str):
        """
        Add trade experience to buffer
        
        Args:
            features: 12-feature vector dict
            outcome: Trade result (profit/loss ratio)
            symbol: Trading pair
        
        Implements: Automatic forgetting when buffer > max_size
        """
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
            # Push to Redis List (left side - newest first)
            await self.redis.lpush(
                self.buffer_key,
                json.dumps(experience)
            )
            self.experience_count += 1
            
            # Implement forgetting: pop oldest if > max_size
            buffer_size = await self.redis.llen(self.buffer_key)
            if buffer_size > self.max_size:
                await self.redis.rpop(self.buffer_key)  # Remove oldest (right side)
                logger.debug(f"🗑️ Forgot oldest experience (buffer size: {buffer_size})")
            
            logger.debug(f"✅ Stored experience #{self.experience_count} ({symbol})")
        
        except Exception as e:
            logger.error(f"❌ Failed to store experience: {e}")
    
    async def get_batch(self, batch_size: int = 128) -> List[Tuple[Dict, float]]:
        """
        Get batch of experiences for model training
        
        Returns: [(features_dict, outcome), ...]
        """
        if not self.redis:
            return []
        
        try:
            # Get batch from left side (most recent)
            experiences = await self.redis.lrange(
                self.buffer_key,
                0,
                batch_size - 1
            )
            
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


class HybridLearner:
    """
    AEGIS Central Brain - Automatic Teacher-Student mode switching
    
    Phase Logic:
    - TEACHER (<50 trades):  Use SMC rule logic, max 3x leverage
    - STUDENT (>=50 trades): Use LightGBM model, dynamic leverage
    """
    
    def __init__(self, db_manager=None, redis_client=None):
        """
        Args:
            db_manager: UnifiedDatabaseManager for trade count queries
            redis_client: Redis connection for experience replay
        """
        self.db = db_manager
        self.redis = redis_client
        self.replay_buffer = ExperienceReplayBuffer(redis_client)
        
        # Phase tracking
        self.current_phase = "TEACHER"
        self.total_trades = 0
        self.teacher_phase_threshold = 50
        
        logger.info("✅ HybridLearner initialized (Teacher-Student mode)")
    
    async def update_phase(self):
        """Update current phase based on trade count"""
        try:
            if self.db:
                # Query total trades from database
                total_trades = await self._get_total_trades()
                self.total_trades = total_trades
                
                # Determine phase
                if total_trades < self.teacher_phase_threshold:
                    self.current_phase = "TEACHER"
                else:
                    self.current_phase = "STUDENT"
                
                logger.info(f"📊 Phase update: {self.current_phase} ({total_trades} trades)")
        
        except Exception as e:
            logger.error(f"❌ Failed to update phase: {e}")
    
    async def _get_total_trades(self) -> int:
        """Query total completed trades from database"""
        # Implementation depends on your DB schema
        # This is a placeholder
        try:
            if not self.db:
                return self.total_trades
            # Assuming DB has a way to count trades
            query = "SELECT COUNT(*) as count FROM trades WHERE status = 'CLOSED'"
            result = await self.db.execute_query(query)
            return result[0]['count'] if result else 0
        except Exception:
            return self.total_trades
    
    def get_max_leverage(self) -> float:
        """
        Get max leverage based on current phase
        
        Returns: 
            - TEACHER phase: 3.0x (capped)
            - STUDENT phase: Dynamic based on confidence (up to model's limit)
        """
        if self.current_phase == "TEACHER":
            return 3.0  # Hard cap for teacher phase
        else:
            return 10.0  # Student phase can use higher leverage
    
    def apply_teacher_logic(self, features: Dict) -> Optional[str]:
        """
        Teacher phase: Rule-based SMC logic
        
        Returns: 'BUY' | 'SELL' | None
        """
        # CRITICAL: liquidity_grab is priority HIGH signal
        if features.get('liquidity_grab', 0) > 0.5:
            # Strong LS detected - likely reversal
            if features.get('market_structure', 0) > 0:
                return 'BUY'
            elif features.get('market_structure', 0) < 0:
                return 'SELL'
        
        # Order block confluence
        if features.get('order_blocks_count', 0) > 0.5:
            if features.get('fvg_proximity', 0) < 0:  # Price in FVG
                return 'BUY'
        
        # Momentum-based signal
        if features.get('momentum_atr', 0) > 1.0:
            return 'BUY'
        elif features.get('momentum_atr', 0) < -1.0:
            return 'SELL'
        
        return None
    
    async def record_trade_outcome(
        self,
        features: Dict,
        outcome: float,
        symbol: str
    ):
        """
        Record completed trade for experience replay buffer
        
        Args:
            features: Trade entry features
            outcome: P/L ratio or normalized outcome
            symbol: Trading pair
        """
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


# Global singleton
_hybrid_learner: Optional[HybridLearner] = None


def get_hybrid_learner(
    db_manager=None,
    redis_client=None
) -> HybridLearner:
    """Get or create global hybrid learner"""
    global _hybrid_learner
    if _hybrid_learner is None:
        _hybrid_learner = HybridLearner(db_manager, redis_client)
    return _hybrid_learner
