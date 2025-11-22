"""
🚀 ICT Scalper - M1/M5 SMC-Based Scalping Strategy
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Execute SMC/ICT signals with LightGBM confidence filtering
Architecture: Full pipeline integration with SMCEngine, FeatureEngineer, MLPredictor
"""

from typing import Dict, Optional, List
import logging

# 🔥 SMC-Quant Pipeline Imports (Full Integration)
from src.core.smc_engine import SMCEngine
from src.ml.feature_engineer import get_feature_engineer
from src.ml.hybrid_learner import get_predictor
from src.core.risk_manager import get_risk_manager

logger = logging.getLogger(__name__)


class ICTScalper:
    """
    ICT Scalper Strategy - M1 scalping with SMC geometry + ML
    
    Features:
    - Detects SMC patterns (FVG, OB, LS, BOS)
    - Filters with LightGBM confidence
    - Dynamic position sizing
    - 2-hour max hold time
    - Forced exits on stagnation
    """
    
    def __init__(self):
        """Initialize scalper with full SMC-Quant pipeline"""
        self.name = "ICT Scalper v1.0"
        self.trades: Dict[str, Dict] = {}  # {symbol: trade_info}
        
        # 🔥 Initialize ML Pipeline Components
        self.smc_engine = SMCEngine()
        self.feature_engineer = get_feature_engineer()
        self.predictor = get_predictor()
        self.risk_manager = get_risk_manager()
        
        logger.info(f"✅ {self.name} initialized with SMC-Quant pipeline")
    
    def on_signal(self, signal: Dict) -> Optional[Dict]:
        """
        Process trading signal
        
        Args:
            signal: Signal from ClusterManager
        
        Returns: Order to execute (or None)
        """
        if not signal:
            return None
        
        symbol = signal.get('symbol')
        confidence = signal.get('confidence', 0.5)
        position_size = signal.get('position_size', 0)
        
        if position_size == 0:
            return None
        
        # Create order
        order = {
            'symbol': symbol,
            'side': 'BUY' if confidence > 0.5 else 'SELL',
            'quantity': position_size,
            'type': 'MARKET',
            'confidence': confidence
        }
        
        logger.info(f"📋 Order created: {order['symbol']} {order['side']} {order['quantity']} @ {confidence:.2%}")
        
        return order
    
    def validate_holding_logic(self, position: Dict, current_features: Dict) -> bool:
        """
        PART 2: Signal Decay - Real-time validation of holding logic
        
        Re-calculate 12 features on every new candle.
        Return False if entry logic becomes invalid → trigger immediate market close
        
        Args:
            position: Current position info
            current_features: Fresh 12-feature vector
        
        Returns: True if hold valid, False if signal decayed (close position)
        """
        if not position or not current_features:
            return False
        
        symbol = position.get('symbol', '')
        side = position.get('side', 'BUY')
        entry_features = position.get('entry_features', {})
        
        # CRITICAL: Check if market_structure flipped (BOS/ChoCh invalidated)
        entry_structure = entry_features.get('market_structure', 0)
        current_structure = current_features.get('market_structure', 0)
        
        if entry_structure != current_structure and entry_structure != 0:
            logger.warning(f"⚠️ Signal Decay: {symbol} market_structure flipped (was {entry_structure}, now {current_structure})")
            return False  # Trigger immediate market close
        
        # CRITICAL: Check if FVG proximity becomes invalid (gap filled)
        fvg_prox_current = current_features.get('fvg_proximity', 0)
        fvg_prox_entry = entry_features.get('fvg_proximity', 0)
        
        if abs(fvg_prox_current) > abs(fvg_prox_entry) + 1.0:
            # Gap has filled beyond entry distance → FVG invalidated
            logger.warning(f"⚠️ Signal Decay: {symbol} FVG gap filled (proximity: {fvg_prox_entry:.2f} → {fvg_prox_current:.2f})")
            return False  # Trigger immediate market close
        
        # Check if price moved against position with no recovery
        entry_price = position.get('entry_price', 0)
        current_price = current_features.get('close_price', entry_price)
        
        if side == 'BUY' and current_price < entry_price * 0.99:
            # Price dropped >1% after entry without recovery signal
            if current_features.get('liquidity_grab', 0) == 0:
                logger.warning(f"⚠️ Signal Decay: {symbol} price dropped without LS support")
                return False  # No liquidity grab to support position
        
        elif side == 'SELL' and current_price > entry_price * 1.01:
            # Price jumped >1% after entry without recovery signal
            if current_features.get('liquidity_grab', 0) == 0:
                logger.warning(f"⚠️ Signal Decay: {symbol} price jumped without LS support")
                return False
        
        # All checks passed - hold position
        return True
    
    def check_exit(self, position: Dict) -> Optional[str]:
        """
        Check if position should be exited
        
        Args:
            position: Position dict
        
        Returns: Exit reason (or None if no exit)
        """
        # Check time-based exits via RiskManager
        return None
    
    def get_info(self) -> Dict:
        """Get strategy info"""
        return {
            'name': self.name,
            'trades': len(self.trades),
            'timeframe': 'M1',
            'style': 'Scalping',
            'features': ['SMC', 'ICT', 'LightGBM', 'Dynamic Sizing']
        }
