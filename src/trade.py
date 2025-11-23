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

import json  # Always available
import redis.asyncio as redis_async

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

from src.bus import bus, Topic
from src.config import Config

logger = logging.getLogger(__name__)

# Redis client (initialized in each process)
_redis_client: Optional[redis_async.Redis] = None


async def _get_redis() -> Optional[redis_async.Redis]:
    """Get or initialize Redis client"""
    global _redis_client
    if _redis_client is None:
        try:
            from src.config import get_redis_url
            redis_url = get_redis_url()
            if redis_url:
                _redis_client = await redis_async.from_url(redis_url, decode_responses=False)
                logger.debug("✅ Redis client initialized for trade module")
        except Exception as e:
            logger.debug(f"⚠️ Redis not available: {e}")
            return None
    return _redis_client


async def _sync_state_to_redis() -> None:
    """
    📡 STATE BROADCASTER: Sync account state to Redis
    Called after every state mutation to keep processes in sync
    """
    try:
        redis = await _get_redis()
        if not redis:
            return
        
        state_payload = {
            "balance": _account_state['balance'],
            "pnl": sum(_account_state['positions'].values()) if _account_state['positions'] else 0.0,
            "trade_count": len(_account_state['trades']),
            "positions": _account_state['positions'].copy(),
            "last_update": time.time()
        }
        
        # Use orjson for fast serialization (or fallback to json)
        if HAS_ORJSON:
            encoded = orjson.dumps(state_payload)
        else:
            encoded = json.dumps(state_payload).encode('utf-8')
        
        # Set with 60-second TTL (refreshed on each update)
        await redis.setex("system:account_state", 60, encoded)
        logger.debug(f"✅ State synced to Redis: Balance=${_account_state['balance']:.2f}, Positions={len(_account_state['positions'])}")
    
    except Exception as e:
        logger.debug(f"⚠️ Failed to sync state to Redis: {e}")

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

# FIX 2: Failed Order Cooldown - Prevent infinite retry loops
# Maps symbol -> timestamp of last failed order
_failed_order_cooldown: Dict[str, float] = {}


def _generate_signature(query_string: str) -> str:
    """
    Generate HMAC-SHA256 signature for Binance API
    
    Critical steps:
    1. Query string must be properly formed before signing
    2. Secret key MUST be encoded as bytes (UTF-8)
    3. Query string MUST be encoded as bytes (UTF-8)
    4. Use hexdigest() to get hex string output
    """
    # Get secret from environment or module variable
    secret = os.getenv('BINANCE_API_SECRET', '') or BINANCE_API_SECRET
    
    if not secret:
        logger.error("❌ BINANCE_API_SECRET not set - cannot sign requests")
        return ""
    
    # FIX 3: Debugging - Log masked API key for verification
    key_preview = f"{secret[:3]}***{secret[-3:]}" if len(secret) >= 6 else "***"
    logger.debug(f"🔐 Signing request with API key: {key_preview} (length: {len(secret)})")
    
    signature = hmac.new(
        secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    logger.debug(f"✅ Signature generated: {signature[:16]}...")
    return signature


def _build_signed_request(params: Dict) -> str:
    """
    Build properly signed query string for Binance API
    
    Process:
    1. Ensure timestamp exists
    2. Clean parameters (remove None values, convert to strings)
    3. Build query string
    4. Generate signature
    5. Append signature
    
    Returns:
        Complete signed query string ready for API request
    """
    # Step 1: Ensure timestamp
    if 'timestamp' not in params:
        params['timestamp'] = int(time.time() * 1000)
    
    # Step 2: Clean parameters (remove None/empty values)
    clean_params = {}
    for k, v in params.items():
        if v is not None and v != '':
            # Convert numbers to strings for urlencode
            if isinstance(v, (int, float)):
                clean_params[k] = str(v)
            else:
                clean_params[k] = v
    
    # Step 3: Build query string (parameters are now strings)
    query_string = urlencode(clean_params)
    
    logger.debug(f"Query string before signing: {query_string}")
    
    # Step 4: Generate signature
    signature = _generate_signature(query_string)
    
    if not signature:
        logger.error("❌ Signature generation failed")
        return ""
    
    # Step 5: Append signature
    signed_request = f"{query_string}&signature={signature}"
    logger.debug(f"Signed request built (signature: {signature[:16]}...)")
    
    return signed_request


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
        # Validate quantity is numeric
        if not isinstance(quantity, (int, float)) or quantity <= 0:
            logger.error(f"❌ Invalid quantity: {quantity} (must be numeric and > 0)")
            return None
        
        # Convert quantity to string (Binance API expects string)
        quantity_str = str(float(quantity))
        
        # Prepare order parameters (all as base types, will be converted to strings)
        params = {
            'symbol': symbol,  # e.g., "BTCUSDT"
            'side': side,      # "BUY" or "SELL"
            'type': order_type,  # "MARKET" or "LIMIT"
            'quantity': float(quantity),  # Keep as float for now, will stringify in _build_signed_request
            'timestamp': int(time.time() * 1000),
            'recvWindow': 5000
        }
        
        # Build properly signed request
        signed_query = _build_signed_request(params)
        if not signed_query:
            logger.error("❌ Failed to build signed request")
            return None
        
        # Build complete URL
        url = f"{BINANCE_BASE_URL}/fapi/v1/order?{signed_query}"
        headers = {
            'X-MBX-APIKEY': BINANCE_API_KEY,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        logger.debug(f"📤 Sending order to Binance: {symbol} {side} {quantity_str} units")
        logger.debug(f"URL: {url[:100]}...")  # Log partial URL for debug
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                response_text = await resp.text()
                
                if resp.status == 200:
                    result = await resp.json()
                    
                    # Extract price from response
                    avg_price = float(result.get('avgPrice', 0))
                    
                    # Validate response contains required fields
                    if not result.get('orderId'):
                        logger.error(f"❌ Invalid response: missing orderId")
                        return None
                    
                    filled_order = {
                        'symbol': symbol,  # BTCUSDT
                        'side': side,  # BUY/SELL
                        'quantity': float(quantity_str),  # Quantity in base asset (BTC, ETH, etc)
                        'price': avg_price,  # Price in quote asset (USDT)
                        'cost': avg_price * float(quantity_str),  # Total cost in quote asset
                        'orderId': result.get('orderId', ''),
                        'status': result.get('status', 'FILLED'),
                        'timestamp': result.get('time', int(time.time() * 1000)),
                        'commission': float(result.get('commission', 0))
                    }
                    
                    logger.debug(
                        f"✅ Order executed: {symbol} {side} {quantity_str} @ ${avg_price:.2f} USDT "
                        f"(Total: ${filled_order['cost']:.2f})"
                    )
                    return filled_order
                else:
                    logger.error(f"❌ Binance API error ({resp.status}): {response_text}")
                    
                    # Try to parse error message
                    try:
                        error_json = await resp.json()
                        error_msg = error_json.get('msg', 'Unknown error')
                        error_code = error_json.get('code', 'Unknown')
                        logger.error(f"   Error Code: {error_code}")
                        logger.error(f"   Error Message: {error_msg}")
                    except Exception as e:
                        logger.error(f"Failed to parse error response: {e}", exc_info=True)
                    
                    # FIX 2: Record cooldown for this symbol to prevent infinite retry loops
                    _failed_order_cooldown[symbol] = time.time()
                    logger.debug(f"❄️ COOLDOWN ACTIVATED: {symbol} - Skipping new signals for 60 seconds")
                    
                    return None
    
    except Exception as e:
        logger.error(f"❌ Order execution failed: {e}", exc_info=True)
        
        # FIX 2: Record cooldown for exception cases too
        _failed_order_cooldown[symbol] = time.time()
        logger.debug(f"❄️ COOLDOWN ACTIVATED: {symbol} - Exception during order execution")
        
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
    
    logger.debug(f"✅ Order filled (SIMULATED): {symbol} {side} {quantity}")
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
    try:
        logger.debug(f"🚪 Closing position: {symbol} {quantity:.0f}")
        
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
                logger.debug(f"✅ Position closed: {symbol}")
                return True
        
        return False
    except Exception as e:
        logger.error(f"❌ Error in _close_position({symbol}): {e}", exc_info=True)
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
    try:
        if not signal:
            return
        
        symbol = signal.get('symbol', '')
        confidence = signal.get('confidence', 0)
        position_size = signal.get('position_size', 0)
        
        # FIX 2: Check if this symbol is in cooldown (failed order recently)
        current_time = time.time()
        COOLDOWN_DURATION = 60  # 60 seconds cooldown after failed order
        
        if symbol in _failed_order_cooldown:
            time_since_failure = current_time - _failed_order_cooldown[symbol]
            if time_since_failure < COOLDOWN_DURATION:
                remaining = COOLDOWN_DURATION - time_since_failure
                logger.debug(f"⏸️ COOLDOWN: {symbol} - Failed order 🔄 in progress, skipping signal (remaining: {remaining:.0f}s)")
                return  # Ignore this signal
            else:
                # Cooldown expired, remove from dict
                del _failed_order_cooldown[symbol]
                logger.debug(f"✅ Cooldown expired: {symbol} - Ready for new signals")
        
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
            
            logger.debug(f"✅ Order approved (Slot {num_positions + 1}/{max_positions}): {symbol} {order['side']} {position_size:.0f}")
            await bus.publish(Topic.ORDER_REQUEST, order)
            return
        
        # CASE 2: Slots full - Check for rotation
        logger.debug(f"⚠️ Positions full ({num_positions}/{max_positions}). Checking rotation opportunity...")
        
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
            logger.debug(f"❌ Signal Rejected: New confidence {confidence:.2f} not higher than weakest ({weakest_key} {weakest_confidence:.2f})")
            return
        
        # Check if weakest position is profitable
        pnl = await _get_position_pnl(weakest_pos)
        
        if pnl <= 0:
            logger.debug(f"❌ Rotation Rejected: Weakest position {weakest_key} is losing money (PnL: ${pnl:.2f}). Holding position.")
            return
        
        # ROTATION APPROVED: Close weakest, open new
        if weakest_key is None:
            logger.error("❌ Rotation failed: Invalid weakest key")
            return
        
        weakest_quantity = weakest_pos.get('quantity', 0)
        logger.debug(f"♻️ ROTATION: Swapping {weakest_key} (Conf: {weakest_confidence:.2f}, PnL: +${pnl:.2f}) for {symbol} (Conf: {confidence:.2f})")
        
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
            
            logger.debug(f"✅ New position approved: {symbol} {order['side']} {position_size:.0f}")
            await bus.publish(Topic.ORDER_REQUEST, order)
        else:
            logger.error(f"❌ Rotation failed: Could not close {weakest_key}")
    except Exception as e:
        logger.error(f"❌ Error in _check_risk(): {e}", exc_info=True)


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
    
    logger.debug(f"✋ Executing: {symbol} {quantity:.0f}")
    
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
    4. 📡 Sync to Redis (for cross-process visibility)
    """
    try:
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
                logger.debug(f"💾 Position closed: {symbol}")
            else:
                # Store position with enhanced metadata
                _account_state['positions'][symbol] = {
                    'quantity': quantity,
                    'entry_price': price,
                    'entry_confidence': confidence,
                    'entry_time': int(time.time() * 1000),
                    'side': side
                }
                logger.debug(f"💾 Position opened: {symbol} {quantity:.0f} @ ${price:.2f} (Conf: {confidence:.2f})")
            
            # Track trade
            _account_state['trades'].append(filled_order)
            
            # Simple balance update (in production: calculate properly)
            _account_state['balance'] -= quantity * price * 0.001  # Assume 0.1% commission
            
            logger.debug(f"💾 State updated: {symbol} | Balance: ${_account_state['balance']:.0f} | Positions: {len(_account_state['positions'])}")
        
        # 📡 STEP 1: STATE BROADCASTER - Sync to Redis (fire-and-forget)
        asyncio.create_task(_sync_state_to_redis())
    
    except Exception as e:
        logger.error(f"❌ Error in _update_state(): {e}", exc_info=True)


async def get_balance() -> float:
    """Get current balance (thread-safe)"""
    try:
        async with _state_lock:
            return _account_state['balance']
    except Exception as e:
        logger.error(f"❌ Error in get_balance(): {e}", exc_info=True)
        return 0.0


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
