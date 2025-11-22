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
from src.config import Config

logger = logging.getLogger(__name__)

# Binance API configuration
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
BINANCE_BASE_URL = "https://fapi.binance.com"  # Futures API
LIVE_TRADING_ENABLED = BINANCE_API_KEY and BINANCE_API_SECRET

# In-memory account state (in production: use Redis/DB)
_account_state = {
    'balance': 10000.0,
    'positions': {},  # {symbol: {quantity, entry_price, entry_confidence, entry_time, side}}
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


async def _get_position_pnl(position_data: Dict) -> float:
    """
    Calculate PnL for a position
    
    In production: fetch current price from Binance
    For now: use mock calculation
    
    Returns: PnL in USD (positive = profit)
    """
    entry_price = position_data.get('entry_price', 0)
    quantity = position_data.get('quantity', 0)
    side = position_data.get('side', 'BUY')
    
    if entry_price <= 0 or quantity <= 0:
        return 0.0
    
    # Mock current price (in production: fetch from API)
    current_price = entry_price * 1.02  # Assume 2% gain
    
    if side == 'BUY':
        pnl = (current_price - entry_price) * quantity
    else:  # SELL
        pnl = (entry_price - current_price) * quantity
    
    return pnl


async def _close_position(symbol: str, quantity: float) -> bool:
    """
    Close an existing position
    
    Args:
        symbol: Trading pair
        quantity: Position size
    
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"🚪 Closing position: {symbol} {quantity:.0f}")
    
    # Create SELL order
    order = {
        'symbol': symbol,
        'side': 'SELL',
        'quantity': quantity,
        'type': 'MARKET',
        'confidence': 0.0  # Forced close (not a signal trade)
    }
    
    # Execute close order
    if LIVE_TRADING_ENABLED:
        filled_order = await _execute_order_live(order)
        if filled_order is None:
            logger.error(f"❌ Failed to close {symbol}")
            return False
    else:
        filled_order = await _execute_order_simulated(order)
    
    # Remove from positions
    async with _state_lock:
        if symbol in _account_state['positions']:
            del _account_state['positions'][symbol]
            logger.info(f"✅ Position closed: {symbol}")
            return True
    
    return False


async def _check_risk(signal: Dict) -> None:
    """
    Validate risk parameters + Elite Rotation Logic
    
    Logic:
    1. Get account balance
    2. Check if slots available (MAX_OPEN_POSITIONS = 3)
    3. If slots full: Check for rotation opportunity
       - Find weakest position (lowest confidence)
       - If New_Confidence > Weakest_Confidence AND Weakest_Position.PnL > 0:
         - Close weakest position
         - Open new position (Upgrade quality)
       - Else: Reject signal
    4. If slots available: Open new position
    """
    if not signal:
        return
    
    symbol = signal.get('symbol', '')
    confidence = signal.get('confidence', 0)
    position_size = signal.get('position_size', 0)
    
    # Get current state (thread-safe)
    async with _state_lock:
        balance = _account_state['balance']
        current_positions = list(_account_state['positions'].items())
    
    max_risk = balance * 0.02  # 2% risk per trade
    
    # Risk validation
    if position_size > max_risk:
        logger.warning(f"🛡️ Risk check failed: {symbol} (risk={position_size:.0f} > max={max_risk:.0f})")
        return
    
    if confidence <= 0.55:
        logger.warning(f"🛡️ Confidence too low: {symbol} ({confidence:.2f} <= 0.55)")
        return
    
    # Check slot availability
    num_positions = len(current_positions)
    max_positions = Config.MAX_OPEN_POSITIONS
    
    # CASE 1: Slots available
    if num_positions < max_positions:
        order = {
            'symbol': symbol,
            'side': 'BUY',
            'quantity': position_size,
            'type': 'MARKET',
            'confidence': confidence
        }
        
        logger.info(f"✅ Order approved (Slot {num_positions + 1}/{max_positions}): {symbol} {order['side']} {position_size:.0f}")
        await bus.publish(Topic.ORDER_REQUEST, order)
        return
    
    # CASE 2: Slots full - Check for rotation
    logger.info(f"⚠️ Positions full ({num_positions}/{max_positions}). Checking rotation opportunity...")
    
    # Find weakest position (lowest confidence)
    weakest_pos = None
    weakest_key = None
    weakest_confidence = float('inf')
    
    for pos_symbol, pos_data in current_positions:
        pos_confidence = pos_data.get('entry_confidence', 0.5)
        if pos_confidence < weakest_confidence:
            weakest_confidence = pos_confidence
            weakest_pos = pos_data
            weakest_key = pos_symbol
    
    if weakest_pos is None:
        logger.warning(f"❌ No positions to compare (rotation check failed)")
        return
    
    # Compare confidences
    if confidence <= weakest_confidence:
        logger.info(f"❌ Signal Rejected: New confidence {confidence:.2f} not higher than weakest ({weakest_key} {weakest_confidence:.2f})")
        return
    
    # Check if weakest position is profitable
    pnl = await _get_position_pnl(weakest_pos)
    
    if pnl <= 0:
        logger.info(f"❌ Rotation Rejected: Weakest position {weakest_key} is losing money (PnL: ${pnl:.2f}). Holding position.")
        return
    
    # ROTATION APPROVED: Close weakest, open new
    if weakest_key is None:
        logger.error("❌ Rotation failed: Invalid weakest key")
        return
    
    weakest_quantity = weakest_pos.get('quantity', 0)
    logger.info(f"♻️ ROTATION: Swapping {weakest_key} (Conf: {weakest_confidence:.2f}, PnL: +${pnl:.2f}) for {symbol} (Conf: {confidence:.2f})")
    
    # Close weakest position
    if await _close_position(weakest_key, weakest_quantity):
        # Open new position
        order = {
            'symbol': symbol,
            'side': 'BUY',
            'quantity': position_size,
            'type': 'MARKET',
            'confidence': confidence
        }
        
        logger.info(f"✅ New position approved: {symbol} {order['side']} {position_size:.0f}")
        await bus.publish(Topic.ORDER_REQUEST, order)
    else:
        logger.error(f"❌ Rotation failed: Could not close {weakest_key}")


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
    2. Record position with metadata (entry_confidence, entry_price, entry_time)
    3. Track trade
    """
    if not filled_order:
        return
    
    async with _state_lock:
        symbol = filled_order.get('symbol', '')
        quantity = filled_order.get('quantity', 0)
        price = filled_order.get('price', 0)
        side = filled_order.get('side', 'BUY')
        confidence = filled_order.get('confidence', 0.5)
        
        # Check if this is a SELL (closing position)
        if side == 'SELL' and symbol in _account_state['positions']:
            del _account_state['positions'][symbol]
            logger.info(f"💾 Position closed: {symbol}")
        else:
            # Store position with enhanced metadata
            _account_state['positions'][symbol] = {
                'quantity': quantity,
                'entry_price': price,
                'entry_confidence': confidence,
                'entry_time': int(time.time() * 1000),
                'side': side
            }
            logger.info(f"💾 Position opened: {symbol} {quantity:.0f} @ ${price:.2f} (Conf: {confidence:.2f})")
        
        # Track trade
        _account_state['trades'].append(filled_order)
        
        # Simple balance update (in production: calculate properly)
        _account_state['balance'] -= quantity * price * 0.001  # Assume 0.1% commission
        
        logger.info(f"💾 State updated: {symbol} | Balance: ${_account_state['balance']:.0f} | Positions: {len(_account_state['positions'])}")


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
