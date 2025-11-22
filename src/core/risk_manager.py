"""
🛡️ Risk Manager - Dynamic Position Sizing & Exit Logic
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Dynamic position sizing based on confidence + forced exit logic
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Manages position sizing based on confidence and forced exits
    
    Features:
    - Dynamic sizing based on confidence score
    - 2-hour maximum hold time
    - Stagnation exit (no profit after 30 min)
    """
    
    def __init__(self):
        """Initialize risk manager"""
        self.max_position_size_pct = 10.0  # Max 10% of account per position
        self.high_confidence_threshold = 0.85
        self.med_confidence_threshold = 0.70
        self.low_confidence_threshold = 0.60
        
        # Position sizing per confidence level
        self.size_mapping = {
            'high': 2.0,      # 2% equity at >0.85 confidence
            'med': 1.0,       # 1% equity at 0.70-0.85
            'low': 0.5,       # 0.5% equity at 0.60-0.70
            'very_low': 0.0   # No trade at <0.60
        }
        
        # Time exits
        self.max_hold_time = 2 * 3600  # 2 hours in seconds
        self.stagnation_time = 30 * 60  # 30 minutes
        self.stagnation_pnl_threshold = 0.001  # 0.1% PnL
    
    def calculate_size(self, confidence: float, balance: float) -> float:
        """
        Calculate position size based on confidence
        
        Args:
            confidence: Score from 0.0 to 1.0
            balance: Account balance in USDT
        
        Returns: Position size in USDT (0 if no trade)
        """
        # Determine confidence level
        if confidence > self.high_confidence_threshold:
            risk_pct = self.size_mapping['high']
        elif confidence > self.med_confidence_threshold:
            risk_pct = self.size_mapping['med']
        elif confidence > self.low_confidence_threshold:
            risk_pct = self.size_mapping['low']
        else:
            risk_pct = self.size_mapping['very_low']
        
        # Calculate position size
        position_size = balance * (risk_pct / 100.0)
        
        # Cap at max position size
        max_position = balance * (self.max_position_size_pct / 100.0)
        position_size = min(position_size, max_position)
        
        logger.info(
            f"📊 Position Sizing: Confidence={confidence:.2f}, "
            f"Risk%={risk_pct:.1f}%, Size={position_size:.2f} USDT"
        )
        
        return position_size
    
    def check_time_exit(self, position: Dict) -> Dict:
        """
        Check if position should be force-closed due to time
        
        Args:
            position: Position dict with 'entry_time', 'entry_price', 'current_price', 'quantity'
        
        Returns: {
            'should_exit': bool,
            'exit_reason': str,
            'force': bool (True if forced exit)
        }
        """
        result = {
            'should_exit': False,
            'exit_reason': '',
            'force': False
        }
        
        if not position:
            return result
        
        entry_time = position.get('entry_time')
        if not entry_time:
            return result
        
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)
        
        now = datetime.utcnow()
        hold_time_seconds = (now - entry_time).total_seconds()
        
        # Force close after 2 hours
        if hold_time_seconds > self.max_hold_time:
            result['should_exit'] = True
            result['exit_reason'] = f"Max hold time (2h) reached"
            result['force'] = True
            logger.warning(f"⏰ Force exit: Max hold time reached ({hold_time_seconds/3600:.1f}h)")
            return result
        
        # Stagnation exit: >30 min with <0.1% PnL
        if hold_time_seconds > self.stagnation_time:
            entry_price = float(position.get('entry_price', 0))
            current_price = float(position.get('current_price', 0))
            
            if entry_price > 0:
                pnl_pct = abs(current_price - entry_price) / entry_price
                
                if pnl_pct < self.stagnation_pnl_threshold:
                    result['should_exit'] = True
                    result['exit_reason'] = f"Stagnation (no profit after 30m)"
                    result['force'] = True
                    logger.info(
                        f"💤 Stagnation exit: Hold={hold_time_seconds/60:.0f}m, "
                        f"PnL%={pnl_pct*100:.2f}%"
                    )
                    return result
        
        return result
    
    def get_risk_metrics(self) -> Dict:
        """Get current risk configuration"""
        return {
            'max_hold_time_minutes': self.max_hold_time / 60,
            'stagnation_time_minutes': self.stagnation_time / 60,
            'stagnation_pnl_threshold': self.stagnation_pnl_threshold,
            'size_mapping': self.size_mapping,
            'confidence_thresholds': {
                'high': self.high_confidence_threshold,
                'med': self.med_confidence_threshold,
                'low': self.low_confidence_threshold
            }
        }


# Global singleton
_risk_manager: Optional[RiskManager] = None


def get_risk_manager() -> RiskManager:
    """Get or create global risk manager"""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager
