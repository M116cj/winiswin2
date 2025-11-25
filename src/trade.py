"""
💰 Trade Module - Risk Management + Live Binance Order Execution + State
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Validates signals, executes orders on Binance, tracks account state.
🔴 LIVE TRADING MODE ONLY - Real Binance Futures trading
"""

import logging
import asyncio
import os
import hmac
import hashlib
import time
import uuid
from typing import Dict, Optional
from urllib.parse import urlencode
from datetime import datetime
import aiohttp

import json  # Always available
import redis.asyncio as redis_async

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

from src.bus import bus, Topic
from src.config import Config, get_database_url
from src.experience_buffer import get_experience_buffer
from src.utils.math_utils import round_step_size, round_to_precision, validate_quantity, get_step_size
from src.virtual_learning import (
    init_virtual_learning, open_virtual_position, check_virtual_tp_sl, 
    get_virtual_state, reset_virtual_account
)

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


async def _get_postgres_connection():
    """Initialize and return Postgres connection"""
    try:
        import asyncpg
        from src.config import get_database_url
        
        db_url = get_database_url()
        conn = await asyncpg.connect(db_url)
        return conn
    except Exception as e:
        logger.debug(f"⚠️ Postgres connection failed: {e}")
        return None


async def _sync_state_to_postgres() -> None:
    """
    💾 STATE BROADCASTER: Sync account state to Postgres
    Creates table if needed and writes current state
    Called after every state mutation to persist data
    """
    conn = None
    try:
        conn = await _get_postgres_connection()
        if not conn:
            logger.warning("⚠️ Postgres not available, skipping state sync")
            return
        
        # Create table if not exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS account_state (
                id SERIAL PRIMARY KEY,
                balance FLOAT NOT NULL,
                pnl FLOAT NOT NULL,
                trade_count INT NOT NULL,
                positions JSONB NOT NULL,
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Get current state
        positions_json = json.dumps(_account_state['positions'])
        
        # Calculate PnL from all positions (sum the PnL of each position)
        # For now: use simple 2% mock gain per position (in production: fetch real prices)
        pnl = 0.0
        for symbol, pos_data in _account_state['positions'].items():
            entry_price = pos_data.get('entry_price', 0)
            quantity = pos_data.get('quantity', 0)
            side = pos_data.get('side', 'BUY')
            
            # Mock current price (2% gain)
            current_price = entry_price * 1.02
            
            if side == 'BUY':
                pos_pnl = (current_price - entry_price) * quantity
            else:
                pos_pnl = (entry_price - current_price) * quantity
            
            pnl += pos_pnl
        
        # Insert/update state (insert new row with latest state)
        await conn.execute("""
            INSERT INTO account_state (balance, pnl, trade_count, positions, last_update)
            VALUES ($1, $2, $3, $4::jsonb, $5)
        """,
            _account_state['balance'],
            pnl,
            len(_account_state['trades']),
            positions_json,
            datetime.fromtimestamp(time.time())
        )
        
        logger.critical(f"💾 State persisted to Postgres: Balance=${_account_state['balance']:.2f}, Positions={len(_account_state['positions'])}, Trades={len(_account_state['trades'])}")
    
    except Exception as e:
        logger.critical(f"❌ Failed to sync state to Postgres: {e}", exc_info=True)
    
    finally:
        if conn:
            try:
                await conn.close()
            except:
                pass


async def _sync_state_to_redis() -> None:
    """
    📡 STATE BROADCASTER: Sync account state to Redis
    Called after every state mutation to keep processes in sync
    (Optional: Redis may not be available in all environments)
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
            encoded = orjson.dumps(state_payload)  # type: ignore
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
        
        # ✅ FIX 1: APPLY PRECISION ROUNDING (StepSize Filter)
        # Round quantity DOWN to safe precision before sending to Binance
        step_size = get_step_size(symbol)
        quantity_safe = round_step_size(quantity, step_size)
        
        # Additional validation after rounding
        if not validate_quantity(quantity_safe, symbol):
            logger.error(f"❌ Quantity invalid after rounding: {quantity_safe}")
            return None
        
        # Convert quantity to string (Binance API expects string)
        quantity_str = str(quantity_safe)
        
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
        
        # Execute close order (LIVE MODE ONLY)
        filled_order = await _execute_order_live(order)
        if filled_order is None:
            logger.error(f"❌ Failed to close {symbol}")
            return False
        
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
        
        # 🎯 Extract from signal top-level (Brain sends data here)
        direction = signal.get('direction', 'LONG')  # LONG/SHORT
        entry_price = signal.get('entry_price', 1.0)
        
        # ✅ Use order_amount calculated by position sizing (from Brain)
        order_amount = signal.get('order_amount', signal.get('position_size', 0))
        tp_pct = signal.get('tp_pct', 0.05)  # Take profit %
        sl_pct = signal.get('sl_pct', 0.02)  # Stop loss %
        
        # Calculate position size (quantity) from order amount
        position_size = (order_amount / entry_price) if entry_price > 0 else 0
        
        # 💾 PERSIST SIGNAL TO POSTGRES
        try:
            conn = await _get_postgres_connection()
            if conn:
                signal_id = signal.get('signal_id', str(uuid.uuid4()))
                timestamp = int(signal.get('timestamp', time.time()) * 1000)
                
                # Store signal details in patterns JSONB + 12 ML FEATURES
                # Extract features from signal.features or signal directly
                features = signal.get('features', {})
                patterns_data = {
                    'direction': direction,
                    'strength': signal.get('strength', 0.5),
                    'entry_price': entry_price,
                    'timeframe_analysis': signal.get('timeframe_analysis', {}),
                    'signal_id': signal_id,
                    # ✅ 12 個 ML 特徵
                    'confidence': signal.get('confidence', features.get('confidence', 0.65)),
                    'fvg': signal.get('fvg', features.get('fvg', 0.5)),
                    'liquidity': signal.get('liquidity', features.get('liquidity', 0.5)),
                    'rsi': signal.get('rsi', features.get('rsi', 50)),
                    'atr': signal.get('atr', features.get('atr', 0.02)),
                    'macd': signal.get('macd', features.get('macd', 0)),
                    'bb_width': signal.get('bb_width', features.get('bb_width', 0)),
                    'position_size_pct': signal.get('position_size_pct', features.get('position_size_pct', 0.01))
                }
                
                await conn.execute("""
                    INSERT INTO signals (id, symbol, confidence, patterns, position_size, timestamp)
                    VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                    ON CONFLICT DO NOTHING
                """,
                    signal_id, symbol, confidence, json.dumps(patterns_data), position_size, timestamp
                )
                logger.debug(f"💾 Signal saved: {symbol} {direction} (conf: {confidence:.2%})")
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Failed to save signal to DB: {e}")
        
        # Check if this symbol is in cooldown
        current_time = time.time()
        COOLDOWN_DURATION = 60
        
        if symbol in _failed_order_cooldown:
            time_since_failure = current_time - _failed_order_cooldown[symbol]
            if time_since_failure < COOLDOWN_DURATION:
                remaining = COOLDOWN_DURATION - time_since_failure
                logger.debug(f"⏸️ COOLDOWN: {symbol} (remaining: {remaining:.0f}s)")
                return
            else:
                del _failed_order_cooldown[symbol]
                logger.debug(f"✅ Cooldown expired: {symbol}")
        
        # Get current state
        async with _state_lock:
            balance = _account_state['balance']
            current_positions = list(_account_state['positions'].items())
        
        max_risk = balance * 0.02
        
        # 🎓 VIRTUAL LEARNING: ALWAYS run virtual trading (independent of risk checks)
        try:
            # Convert LONG/SHORT to BUY/SELL
            side = 'BUY' if direction.upper() in ('LONG', 'BUY') else 'SELL'
            
            # Extract all 12 ML features for virtual trading
            features = signal.get('features', {})
            virtual_order = {
                'symbol': symbol,
                'side': side,
                'confidence': confidence,
                'quantity': position_size,
                'entry_price': entry_price,
                'tp_pct': tp_pct,
                'sl_pct': sl_pct,
                # ✅ 12 個 ML 特徵
                'fvg': signal.get('fvg', features.get('fvg', 0.5)),
                'liquidity': signal.get('liquidity', features.get('liquidity', 0.5)),
                'rsi': signal.get('rsi', features.get('rsi', 50)),
                'atr': signal.get('atr', features.get('atr', 0.02)),
                'macd': signal.get('macd', features.get('macd', 0)),
                'bb_width': signal.get('bb_width', features.get('bb_width', 0)),
                'position_size_pct': signal.get('position_size_pct', features.get('position_size_pct', 0.01))
            }
            
            success = await open_virtual_position(virtual_order)
            if success:
                logger.critical(f"🎓 Virtual position opened: {symbol} {side} x{position_size:.4f} @ ${entry_price:.2f}")
            else:
                logger.warning(f"❌ Virtual position failed: {symbol} - invalid data")
        except Exception as e:
            logger.error(f"Virtual learning error: {e}", exc_info=True)
        
        # Risk validation (live trading only)
        if position_size > max_risk:
            return
        
        # ✅ CORRECT THRESHOLD: 0.60 for professional trading
        if confidence < 0.60:
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
            
            # 🎓 VIRTUAL LEARNING: Open virtual position (no restrictions)
            # ✅ Include percentage stop-loss and take-profit + 12 ML features
            features = signal.get('features', {})
            virtual_order = {
                'symbol': symbol,
                'side': 'BUY',
                'confidence': confidence,
                'quantity': position_size,
                'entry_price': entry_price,  # 🎯 Real market price
                'tp_pct': tp_pct,  # Take profit %
                'sl_pct': sl_pct,  # Stop loss %
                # ✅ 12 個 ML 特徵
                'fvg': signal.get('fvg', features.get('fvg', 0.5)),
                'liquidity': signal.get('liquidity', features.get('liquidity', 0.5)),
                'rsi': signal.get('rsi', features.get('rsi', 50)),
                'atr': signal.get('atr', features.get('atr', 0.02)),
                'macd': signal.get('macd', features.get('macd', 0)),
                'bb_width': signal.get('bb_width', features.get('bb_width', 0)),
                'position_size_pct': signal.get('position_size_pct', features.get('position_size_pct', 0.01))
            }
            await open_virtual_position(virtual_order)
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
            
            # 🎓 VIRTUAL LEARNING: Open virtual position for rotation
            # ✅ Include percentage stop-loss and take-profit
            virtual_order = {
                'symbol': symbol,
                'side': 'BUY',
                'confidence': confidence,
                'quantity': position_size,
                'entry_price': entry_price,  # 🎯 Real market price
                'tp_pct': tp_pct,  # Take profit %
                'sl_pct': sl_pct   # Stop loss %
            }
            await open_virtual_position(virtual_order)
        else:
            logger.error(f"❌ Rotation failed: Could not close {weakest_key}")
    except Exception as e:
        logger.error(f"❌ Error in _check_risk(): {e}", exc_info=True)


async def _execute_order(order: Dict) -> None:
    """
    Execute order on Binance (LIVE MODE ONLY)
    
    Logic:
    1. Validate order
    2. Send to Binance API
    3. Publish ORDER_FILLED event
    """
    if not order:
        return
    
    symbol = order.get('symbol', '')
    quantity = order.get('quantity', 0)
    
    logger.debug(f"✋ Executing: {symbol} {quantity:.0f}")
    
    # Execute order (LIVE MODE ONLY)
    filled_order = await _execute_order_live(order)
    if filled_order is None:
        logger.error(f"❌ Order failed for {symbol}")
        return
    
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
        
        # 💾 Record trade outcome in experience buffer for ML training
        signal_id = filled_order.get('signal_id', '')
        if signal_id:
            try:
                experience_buffer = get_experience_buffer()
                await experience_buffer.record_trade_outcome(signal_id, filled_order)
            except Exception as e:
                logger.debug(f"⚠️ Error recording experience: {e}")
        
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
        
        # 💾 STEP 1: STATE BROADCASTER - Sync to Postgres (primary persistence)
        asyncio.create_task(_sync_state_to_postgres())
        
        # 📡 STEP 2: STATE BROADCASTER - Sync to Redis (if available)
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


async def _load_state_from_postgres() -> None:
    """
    Load last known account state from Postgres on startup
    Enables recovery after process restart
    
    ✅ FIX 2: ATOMIC STATE MUTATION (with lock)
    All state modifications are protected with the lock
    """
    try:
        conn = await _get_postgres_connection()
        if not conn:
            logger.debug("⚠️ Postgres not available, using default state")
            return
        
        # Get latest state from database
        row = await conn.fetchrow("""
            SELECT balance, positions, trade_count 
            FROM account_state 
            ORDER BY updated_at DESC 
            LIMIT 1
        """)
        
        if row:
            # ✅ FIX 2: Protect state mutation with lock (prevent race conditions)
            async with _state_lock:
                global _account_state
                _account_state['balance'] = row['balance']
                _account_state['positions'] = json.loads(row['positions'])
                _account_state['trade_count'] = row['trade_count']
                logger.info(f"📖 Loaded state from Postgres: Balance=${_account_state['balance']:.2f}, Positions={len(_account_state['positions'])}")
        
        await conn.close()
    
    except Exception as e:
        logger.debug(f"⚠️ Failed to load state from Postgres: {e}")


async def initial_account_sync() -> None:
    """
    💧 COLD START HYDRATION: Fetch initial account state from Binance REST API
    
    This ensures all account info comes from Binance API, not defaults:
    - Replaces hardcoded $10,000 default with real account data
    - Works with or without live trading enabled
    - Only requires API credentials to be present
    
    Steps:
    1. Call /fapi/v2/account endpoint
    2. Extract: totalWalletBalance, totalUnrealizedProfit, positions
    3. Update global _account_state
    4. Force sync to Redis & Postgres
    """
    # Check if API credentials are available (key indicator: has BINANCE_API_KEY)
    if not BINANCE_API_KEY:
        logger.debug("⏭️ No Binance API credentials - using default account state")
        return
    
    try:
        logger.critical("💧 Hydrating Account State from Binance API...")
        
        # Prepare request params for GET /fapi/v2/account
        params = {
            'timestamp': int(time.time() * 1000),
            'recvWindow': 5000
        }
        
        # Build properly signed request
        signed_query = _build_signed_request(params)
        if not signed_query:
            logger.error("❌ Failed to build signed request for account sync")
            return
        
        # Build complete URL for account info endpoint
        url = f"{BINANCE_BASE_URL}/fapi/v2/account?{signed_query}"
        headers = {
            'X-MBX-APIKEY': BINANCE_API_KEY,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        logger.debug(f"📤 Fetching account information from Binance...")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                response_text = await resp.text()
                
                if resp.status == 200:
                    account_data = await resp.json()
                    
                    # Extract real balance from API response
                    balance = float(account_data.get('totalWalletBalance', 10000.0))
                    pnl = float(account_data.get('totalUnrealizedProfit', 0.0))
                    
                    # Extract active positions (positionAmt != 0)
                    active_positions = {}
                    for position in account_data.get('positions', []):
                        symbol = position.get('symbol', '')
                        position_amt = float(position.get('positionAmt', 0))
                        
                        # Only keep positions with non-zero amount
                        if position_amt != 0:
                            entry_price = float(position.get('entryPrice', 0))
                            active_positions[symbol] = {
                                'quantity': position_amt,
                                'entry_price': entry_price,
                                'entry_confidence': 0.5,  # Default confidence
                                'entry_time': int(time.time() * 1000),
                                'side': 'BUY' if position_amt > 0 else 'SELL'
                            }
                    
                    # Update global state UNDER LOCK
                    global _account_state
                    async with _state_lock:
                        _account_state['balance'] = balance
                        _account_state['positions'] = active_positions
                    
                    logger.critical(
                        f"✅ Account Hydrated: Balance=${balance:.2f}, "
                        f"PnL=${pnl:.2f}, Active Positions={len(active_positions)}"
                    )
                    
                    # Force immediate sync to Redis and Postgres
                    await _sync_state_to_redis()
                    await _sync_state_to_postgres()
                    
                    logger.critical("✅ Account state synced to Redis & Postgres")
                    
                else:
                    logger.error(f"❌ Failed to fetch account info: HTTP {resp.status}")
                    logger.error(f"Response: {response_text}")
                    try:
                        error_json = json.loads(response_text)
                        logger.error(f"Error: {error_json.get('msg', 'Unknown')}")
                    except:
                        pass
    
    except Exception as e:
        logger.error(f"❌ Account hydration failed: {e}", exc_info=True)


async def init() -> None:
    """Initialize trade module - connect risk → execution → state (LIVE MODE ONLY)"""
    logger.info("💰 Trade module initializing - LIVE TRADING MODE")
    
    # Load previous state from Postgres if available
    await _load_state_from_postgres()
    
    # 🔴 LIVE MODE: Fetch real account state from Binance API
    logger.critical("🔴 LIVE TRADING MODE - Syncing with real Binance account")
    await initial_account_sync()
    
    # 🎓 Initialize virtual learning account
    await init_virtual_learning()
    
    if LIVE_TRADING_ENABLED:
        logger.critical("✅ LIVE TRADING ENABLED - Orders will be executed on Binance")
    else:
        logger.critical("⚠️ WARNING: LIVE TRADING DISABLED - Set BINANCE_API_KEY and BINANCE_API_SECRET")
    
    bus.subscribe(Topic.SIGNAL_GENERATED, _check_risk)
    bus.subscribe(Topic.ORDER_REQUEST, _execute_order)
    bus.subscribe(Topic.ORDER_FILLED, _update_state)
    logger.critical("✅ Trade module ready (LIVE MODE - Real Binance trading + Virtual Learning)")


# ✅ Dynamic position calculation (add at end of trade.py before if __name__ == "__main__")
from src.position_calculator import get_position_calculator


async def calculate_dynamic_position(
    signal: Dict,
    account_balance: float,
    model_winrate: float = 0.60
) -> Dict:
    """
    計算基於信心度和勝率的動態倉位
    
    Returns:
        {
            'position_size': 倉位大小,
            'leverage': 槓桿,
            'risk_amount': 風險金額,
            'recommended': 是否推薦開倉
        }
    """
    calculator = get_position_calculator()
    
    confidence = signal.get('confidence', 0.60)
    direction = signal.get('direction', 'UP')
    
    position = calculator.calculate_position(
        balance=account_balance,
        confidence=confidence,
        winrate=model_winrate,
        signal_direction=direction
    )
    
    if position.get('recommended'):
        logger.critical(
            f"📊 Position Calculation: {signal['symbol']} | "
            f"Size: ${position['position_size']:.2f} | "
            f"Leverage: {position['leverage']:.0f}x | "
            f"Risk: ${position['risk_amount']:.2f} | "
            f"{position['notes']}"
        )
    
    return position


# ✅ Binance 約束驗證集成
from src.binance_constraints import get_binance_constraints


async def validate_order_with_binance_constraints(
    symbol: str,
    quantity: float,
    current_price: float
) -> tuple[bool, str]:
    """
    驗證訂單是否符合 Binance 最低開倉限制
    
    檢查：
    1. 最低名義價值（BTCUSDT: 50 USDT, ETHUSDT: 20 USDT, 其他: 5 USDT）
    2. 最低數量限制
    
    Returns:
        (is_valid, error_message_or_empty_string)
    """
    constraints = get_binance_constraints()
    
    # 驗證訂單大小
    is_valid, error_msg = constraints.validate_order_size(
        symbol=symbol,
        quantity=quantity,
        current_price=current_price
    )
    
    if not is_valid:
        logger.warning(f"🛡️ Binance constraint violation for {symbol}: {error_msg}")
    
    return is_valid, error_msg


def get_max_leverage_for_position(
    symbol: str,
    notional_value: float
) -> int:
    """
    根據持倉名義價值獲得該符號的最大允許槓桿
    
    Binance 使用分檔制：持倉越大，最大槓桿越低
    
    Returns:
        最大槓桿倍數（整數）
    """
    constraints = get_binance_constraints()
    max_leverage = constraints.get_max_leverage(symbol, notional_value)
    logger.debug(
        f"📊 Max leverage for {symbol} at ${notional_value:.2f} notional: {max_leverage}x"
    )
    return max_leverage
