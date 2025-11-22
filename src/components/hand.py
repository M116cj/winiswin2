"""
✋ Hand Component - Order Execution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Order execution. Receives ORDER_REQUEST, sends to Binance, publishes ORDER_FILLED.
Pure execution logic. NO business logic imports.
"""

import logging
from typing import Dict

from src.bus import bus, Topic

logger = logging.getLogger(__name__)


async def execute_order(order: Dict) -> None:
    """
    Execute order on Binance
    
    Logic:
    1. Validate order
    2. Send HTTP request to Binance
    3. Publish ORDER_FILLED event
    """
    if not order:
        return
    
    symbol = order.get('symbol', '')
    side = order.get('side', '')
    quantity = order.get('quantity', 0)
    
    logger.info(f"✋ Executing: {symbol} {side} {quantity:.0f}")
    
    # In production: make HTTP request to Binance API
    # For now: simulate
    
    filled_order = {
        'symbol': symbol,
        'side': side,
        'quantity': quantity,
        'price': 42000.0,
        'status': 'FILLED'
    }
    
    # Notify memory that order filled
    await bus.publish(Topic.ORDER_FILLED, filled_order)
    
    logger.info(f"✅ Order filled: {symbol}")


async def init() -> None:
    """Initialize hand - subscribe to order requests"""
    logger.info("✋ Hand initializing")
    bus.subscribe(Topic.ORDER_REQUEST, execute_order)
    logger.info("✅ Hand ready (subscribed to ORDER_REQUEST)")
