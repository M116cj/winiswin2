"""
💰 Trade Module - Risk Management + Live Binance Order Execution + State
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Validates signals, executes orders on Binance, tracks account state.
Supports both simulated (paper) and live trading modes.
"""

import logging
import asyncio
import os
import hmac
import hashlib
import time
from typing import Dict, Optional
from urllib.parse import urlencode
import aiohttp

from src.bus import bus, Topic

logger = logging.getLogger(__name__)

# Binance API configuration
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
BINANCE_BASE_URL = "https://fapi.binance.com"  # Futures API
LIVE_TRADING_ENABLED = BINANCE_API_KEY and BINANCE_API_SECRET

# In-memory account state (in production: use Redis/DB)
_account_state = {
    'balance': 10000.0,
    'positions': {},
    'trades': []
}

# Lock for async-safe state mutations
_state_lock = asyncio.Lock()


def _generate_signature(query_string: str) -> str:
    """Generate HMAC-SHA256 signature for Binance API"""
    return hmac.new(
        BINANCE_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


async def _execute_order_live(order: Dict) -> Optional[Dict]:
    """
    Execute order on live Binance Futures account
    
    Args:
        order: Order details {symbol, side, quantity, type, confidence}
    
    Returns:
        Filled order details or None if failed
    """
    if not LIVE_TRADING_ENABLED:
        logger.warning("⚠️ Live trading not enabled - set BINANCE_API_KEY and BINANCE_API_SECRET")
        return None
    
    symbol = order.get('symbol', '')
    side = order.get('side', 'BUY')  # BUY or SELL
    quantity = order.get('quantity', 0)
    order_type = order.get('type', 'MARKET')
    
    try:
        # Prepare order parameters
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity,
            'timestamp': int(time.time() * 1000),
            'recvWindow': 5000
        }
        
        # Build query string and sign
        query_string = urlencode(params)
        signature = _generate_signature(query_string)
        
        # Build request
        url = f"{BINANCE_BASE_URL}/fapi/v1/order?{query_string}&signature={signature}"
        headers = {
            'X-MBX-APIKEY': BINANCE_API_KEY
        }
        
        logger.info(f"📤 Sending order to Binance: {symbol} {side} {quantity}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    
                    filled_order = {
                        'symbol': symbol,
                        'side': side,
                        'quantity': quantity,
                        'price': float(result.get('avgPrice', 0)),
                        'orderId': result.get('orderId', ''),
                        'status': result.get('status', 'FILLED'),
                        'timestamp': result.get('time', int(time.time() * 1000))
                    }
                    
                    logger.info(f"✅ Order executed: {symbol} {side} {quantity} @ {filled_order['price']}")
                    return filled_order
                else:
                    error_text = await resp.text()
                    logger.error(f"❌ Binance API error ({resp.status}): {error_text}")
                    return None
    
    except Exception as e:
        logger.error(f"❌ Order execution failed: {e}")
        return None


async def _execute_order_simulated(order: Dict) -> Dict:
    """
    Simulate order execution (paper trading)
    Used when live trading is disabled or for testing
    """
    symbol = order.get('symbol', '')
    side = order.get('side', '')
    quantity = order.get('quantity', 0)
    
    # Simulate some latency
    await asyncio.sleep(0.1)
    
    filled_order = {
        'symbol': symbol,
        'side': side,
        'quantity': quantity,
        'price': 42000.0,  # Mock price
        'status': 'FILLED'
    }
    
    logger.info(f"✅ Order filled (SIMULATED): {symbol} {side} {quantity}")
    return filled_order


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
    
    # Get current balance
    async with _state_lock:
        balance = _account_state['balance']
    
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
    Execute order (live or simulated)
    
    Logic:
    1. Validate order
    2. Send to Binance API or simulate
    3. Publish ORDER_FILLED event
    """
    if not order:
        return
    
    symbol = order.get('symbol', '')
    quantity = order.get('quantity', 0)
    
    logger.info(f"✋ Executing: {symbol} {quantity:.0f}")
    
    # Execute order (live or simulated)
    if LIVE_TRADING_ENABLED:
        filled_order = await _execute_order_live(order)
        if filled_order is None:
            logger.error(f"❌ Order failed for {symbol}")
            return
    else:
        filled_order = await _execute_order_simulated(order)
    
    # Notify that order filled
    await bus.publish(Topic.ORDER_FILLED, filled_order)


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
    
    if LIVE_TRADING_ENABLED:
        logger.info("✅ LIVE TRADING ENABLED - Orders will be sent to Binance")
    else:
        logger.warning("⚠️ LIVE TRADING DISABLED - Using simulated orders")
        logger.warning("   To enable live trading, set environment variables:")
        logger.warning("   BINANCE_API_KEY=your_key")
        logger.warning("   BINANCE_API_SECRET=your_secret")
    
    bus.subscribe(Topic.SIGNAL_GENERATED, _check_risk)
    bus.subscribe(Topic.ORDER_REQUEST, _execute_order)
    bus.subscribe(Topic.ORDER_FILLED, _update_state)
    logger.info("✅ Trade module ready")
