"""
💾 Memory Component - State Management
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

State tracking. Listens to ORDER_FILLED, updates account state.
Pure state management. NO execution logic.
"""

import logging
import asyncio
from typing import Dict

from src.bus import bus, Topic

logger = logging.getLogger(__name__)

# In-memory state (in production: use Redis/DB)
_account_state = {
    'balance': 10000.0,
    'positions': {},
    'trades': []
}

# Lock for async-safe state mutations
_state_lock = asyncio.Lock()


async def update_state(filled_order: Dict) -> None:
    """
    Update account state when order fills (thread-safe)
    
    Logic:
    1. Update balance
    2. Record position
    3. Track trade
    """
    if not filled_order:
        return
    
    async with _state_lock:
        symbol = filled_order.get('symbol', '')
        quantity = filled_order.get('quantity', 0)
        price = filled_order.get('price', 0)
        
        # Update state
        _account_state['positions'][symbol] = quantity
        _account_state['trades'].append(filled_order)
        
        # Simple balance update (in production: calculate properly)
        _account_state['balance'] -= quantity * price * 0.001  # Assume 0.1% commission
        
        logger.info(f"💾 State updated: {symbol} | Balance: {_account_state['balance']:.0f}")


async def get_balance() -> float:
    """Get current balance (thread-safe)"""
    async with _state_lock:
        return _account_state['balance']


async def init() -> None:
    """Initialize memory - subscribe to filled orders"""
    logger.info("💾 Memory initializing")
    bus.subscribe(Topic.ORDER_FILLED, update_state)
    logger.info("✅ Memory ready (subscribed to ORDER_FILLED)")
