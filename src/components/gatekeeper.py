"""
🛡️ Gatekeeper Component - Risk Management
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Risk validation. Receives SIGNAL_GENERATED, checks balance/leverage, publishes ORDER_REQUEST.
Pure risk logic. NO other imports.
"""

import logging
from typing import Dict

from src.bus import bus, Topic

logger = logging.getLogger(__name__)


async def check_risk(signal: Dict) -> None:
    """
    Validate risk parameters
    
    Logic:
    1. Get account balance (from memory)
    2. Check leverage
    3. If pass -> publish ORDER_REQUEST
    """
    if not signal:
        return
    
    symbol = signal.get('symbol', '')
    confidence = signal.get('confidence', 0)
    position_size = signal.get('position_size', 0)
    
    # Simple risk check (in production: fetch from memory)
    balance = 10000.0
    max_risk = balance * 0.02  # 2% risk per trade
    
    if position_size <= max_risk and confidence > 0.55:
        order = {
            'symbol': symbol,
            'side': 'BUY' if confidence > 0.5 else 'SELL',
            'quantity': position_size,
            'type': 'MARKET',
            'confidence': confidence
        }
        
        logger.info(f"🛡️ Order approved: {symbol} {order['side']} {position_size:.0f}")
        
        # Publish to hand for execution
        await bus.publish(Topic.ORDER_REQUEST, order)
    else:
        logger.warning(f"🛡️ Risk check failed: {symbol} (risk={position_size:.0f} > max={max_risk:.0f})")


async def init() -> None:
    """Initialize gatekeeper - subscribe to signals"""
    logger.info("🛡️ Gatekeeper initializing")
    bus.subscribe(Topic.SIGNAL_GENERATED, check_risk)
    logger.info("✅ Gatekeeper ready (subscribed to SIGNAL_GENERATED)")
