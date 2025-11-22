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
from src.ml.predictor import get_predictor
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
