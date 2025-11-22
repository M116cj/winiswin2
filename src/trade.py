"""
💰 Trade Module - Risk Management + Order Execution + State
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Merged: Gatekeeper (risk) + Hand (execution) + Memory (state)
Validates signals, executes orders, tracks account state.
"""

import logging
import asyncio
from typing import Dict

from src.bus import bus, Topic

logger = logging.getLogger(__name__)

# In-memory account state (in production: use Redis/DB)
_account_state = {
    'balance': 10000.0,
    'positions': {},
    'trades': []
}

# Lock for async-safe state mutations
_state_lock = asyncio.Lock()


async def _check_risk(signal: Dict) -> None:
    """
    Validate risk parameters
    
    Logic:
    1. Get account balance
    2. Check leverage
    3. If pass -> publish ORDER_REQUEST
    """
    if not signal:
        return
    
    symbol = signal.get('symbol', '')
    confidence = signal.get('confidence', 0)
    position_size = signal.get('position_size', 0)
    
    # Simple risk check
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
        
        # Publish to execution
        await bus.publish(Topic.ORDER_REQUEST, order)
    else:
        logger.warning(f"🛡️ Risk check failed: {symbol} (risk={position_size:.0f} > max={max_risk:.0f})")


async def _execute_order(order: Dict) -> None:
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


async def _update_state(filled_order: Dict) -> None:
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
    """Initialize trade module - connect risk → execution → state"""
    logger.info("💰 Trade module initializing")
    bus.subscribe(Topic.SIGNAL_GENERATED, _check_risk)
    bus.subscribe(Topic.ORDER_REQUEST, _execute_order)
    bus.subscribe(Topic.ORDER_FILLED, _update_state)
    logger.info("✅ Trade module ready")
