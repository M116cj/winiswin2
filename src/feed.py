"""
📡 Feed Process - WebSocket Data Ingestion & Ring Buffer Writing
Minimal version for process communication

🛡️ STRICT FIREWALL: Comprehensive data validation to prevent poison pills
"""

import logging
import asyncio
import math
import time as time_module

logger = logging.getLogger(__name__)

# Rate limiter for poison pill warnings (avoid spam)
_last_poison_warning = 0.0
_poison_warning_cooldown = 60.0  # Warn max once per minute


def _is_valid_price(price: float, context: str = "Price") -> bool:
    """Check if price is valid (positive, finite, not NaN)"""
    if price is None:
        return False
    try:
        price_f = float(price)
        # Check: must be positive
        if price_f <= 0:
            return False
        # Check: must be finite (not inf, not nan)
        if not math.isfinite(price_f):
            return False
        return True
    except (ValueError, TypeError):
        return False


def _is_valid_volume(volume: float) -> bool:
    """Check if volume is valid (non-negative, finite, not NaN)"""
    if volume is None:
        return False
    try:
        vol_f = float(volume)
        # Check: must be non-negative
        if vol_f < 0:
            return False
        # Check: must be finite
        if not math.isfinite(vol_f):
            return False
        return True
    except (ValueError, TypeError):
        return False


def _is_valid_timestamp(timestamp: float, max_age_days: int = 365) -> bool:
    """
    Check if timestamp is valid (reasonable bounds)
    
    Valid range: Last N days to next day (allow some clock skew)
    """
    if timestamp is None:
        return False
    try:
        ts_f = float(timestamp)
        current_time = time_module.time() * 1000  # Convert to milliseconds
        
        # Check: not too old (older than max_age_days)
        if ts_f < (current_time - max_age_days * 86400 * 1000):
            return False
        
        # Check: not in future (allow 1 hour skew for clock drift)
        if ts_f > (current_time + 3600 * 1000):
            return False
        
        return True
    except (ValueError, TypeError):
        return False


def _is_valid_candle_logic(open_p: float, high: float, low: float, close: float) -> bool:
    """
    Check if candle respects basic physics:
    - high >= low (required)
    - high >= open (usually)
    - high >= close (usually)
    - low <= open (usually)
    - low <= close (usually)
    """
    try:
        o, h, l, c = float(open_p), float(high), float(low), float(close)
        
        # CRITICAL: High must be >= Low
        if h < l:
            return False
        
        # CRITICAL: High must be >= both open and close
        if h < o or h < c:
            return False
        
        # CRITICAL: Low must be <= both open and close
        if l > o or l > c:
            return False
        
        return True
    except (ValueError, TypeError):
        return False


def _is_valid_tick(candle_dict: dict) -> bool:
    """
    🛡️ STRICT FIREWALL: Comprehensive validation before ring buffer
    
    Returns True only if candle is safe to process.
    """
    try:
        # Check structure: must have required keys
        required_keys = {'t', 'o', 'h', 'l', 'c', 'v'}  # timestamp, open, high, low, close, volume
        # Allow both 't' and 'T', 'o' and 'open', etc.
        available_keys = set(candle_dict.keys())
        
        # Map common variations
        key_map = {
            't': ['t', 'T', 'time', 'timestamp'],
            'o': ['o', 'O', 'open', 'open_price'],
            'h': ['h', 'H', 'high'],
            'l': ['l', 'L', 'low'],
            'c': ['c', 'C', 'close'],
            'v': ['v', 'V', 'volume'],
        }
        
        # Extract values with flexible key names
        values = {}
        for standard_key, variations in key_map.items():
            found = False
            for var_key in variations:
                if var_key in candle_dict:
                    values[standard_key] = candle_dict[var_key]
                    found = True
                    break
            if not found:
                # Missing required key
                return False
        
        # Extract values
        timestamp = values.get('t')
        open_p = values.get('o')
        high = values.get('h')
        low = values.get('l')
        close = values.get('c')
        volume = values.get('v')
        
        # 1. Validate timestamp
        if not _is_valid_timestamp(timestamp):
            return False
        
        # 2. Validate all prices (open, high, low, close)
        if not all(_is_valid_price(p) for p in [open_p, high, low, close]):
            return False
        
        # 3. Validate volume
        if not _is_valid_volume(volume):
            return False
        
        # 4. Validate candle logic (high >= low, etc.)
        if not _is_valid_candle_logic(open_p, high, low, close):
            return False
        
        # All checks passed!
        return True
    
    except Exception as e:
        logger.error(f"⚠️ Validation error: {e}")
        return False


def _log_poison_pill(candle_dict: dict, reason: str) -> None:
    """Rate-limited logging for dropped poison pills"""
    global _last_poison_warning
    
    current_time = time_module.time()
    if current_time - _last_poison_warning >= _poison_warning_cooldown:
        logger.warning(f"🛡️ Dropped Poison Pill: {reason} - Sample: {candle_dict}")
        _last_poison_warning = current_time


def _sanitize_candle(timestamp, open_price, high, low, close, volume):
    """
    🛡️ STRICT DATA SANITIZATION: Ensure all candle data is clean AND valid
    
    Protects against:
    - None values ✅
    - String values ✅
    - Zero/negative prices ✅
    - Infinity/NaN values ✅
    - Logical impossibilities (high < low) ✅
    - Out-of-range timestamps ✅
    - Invalid volumes ✅
    - Mixed types ✅
    
    Returns: tuple(timestamp, open, high, low, close, volume) or None
    """
    try:
        # Create candle dict for validation
        candle_dict = {
            't': timestamp,
            'o': open_price,
            'h': high,
            'l': low,
            'c': close,
            'v': volume
        }
        
        # STRICT FIREWALL: Validate everything
        if not _is_valid_tick(candle_dict):
            _log_poison_pill(
                candle_dict,
                f"Failed validation: ts={timestamp}, o={open_price}, h={high}, l={low}, c={close}, v={volume}"
            )
            return None
        
        # Convert all values to float (now guaranteed to be valid)
        safe_candle = (
            float(timestamp),
            float(open_price),
            float(high),
            float(low),
            float(close),
            float(volume)
        )
        
        return safe_candle
    
    except (ValueError, TypeError) as e:
        logger.error(
            f"❌ Data sanitization failed: "
            f"ts={timestamp}, o={open_price}, h={high}, l={low}, c={close}, v={volume}. "
            f"Error: {e}"
        )
        return None


async def main():
    """
    Feed process main loop
    - Connect to Binance Futures WebSocket
    - Read 1m klines for multiple symbols
    - Sanitize data
    - Write to ring buffer
    """
    import json
    import websockets
    
    logger.info("📡 Feed Process started")
    
    try:
        from src.ring_buffer import get_ring_buffer
        
        # Attach to ring buffer created by main process
        ring_buffer = get_ring_buffer(create=False)
        if ring_buffer is None:
            logger.error("❌ Failed to attach to ring buffer")
            return
        
        logger.info("✅ Feed attached to ring buffer")
        logger.critical(f"🔍 Ring Buffer Diagnostic: pending={ring_buffer.pending_count()}, ready for writes")
        
        # Top 20 symbols for trading
        symbols = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
            "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "MATICUSDT",
            "FTTUSDT", "TRXUSDT", "ARBUSDT", "OPUSDT", "LTCUSDT",
            "BCHUSDT", "ETCUSDT", "XLMUSDT", "ATOMUSDT", "UNIUSDT"
        ]
        
        # Build WebSocket subscription
        streams = [f"{symbol.lower()}@kline_1m" for symbol in symbols]
        stream_str = "/".join(streams)
        ws_url = f"wss://fstream.binance.com/stream?streams={stream_str}"
        
        logger.info(f"🔗 Connecting to Binance Futures WebSocket... ({len(symbols)} symbols)")
        
        reconnect_count = 0
        max_reconnect_attempts = 999  # Essentially unlimited - keep reconnecting
        
        while reconnect_count < max_reconnect_attempts:
            try:
                # Binance WebSocket 配置優化：
                # - ping_interval: 20s (更頻繁的心跳保持連接活躍)
                # - ping_timeout: 30s (給予充足時間等待 pong)
                # - close_timeout: 10s (快速關閉）
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=30, close_timeout=10) as websocket:
                    logger.critical(f"✅ Connected to Binance WebSocket (attempt {reconnect_count + 1})")
                    reconnect_count = 0  # Reset on successful connection
                    candle_count = 0
                    
                    while True:
                        try:
                            # 增加超時時間為 45s，允許短暫的網絡波動
                            message = await asyncio.wait_for(websocket.recv(), timeout=45)
                            data = json.loads(message)
                            
                            # Extract kline data
                            if 'data' in data and 'k' in data['data']:
                                kline = data['data']['k']
                                
                                # Only process closed candles or latest data
                                timestamp = kline.get('t')  # Time
                                open_price = kline.get('o')  # Open
                                high = kline.get('h')  # High
                                low = kline.get('l')  # Low
                                close = kline.get('c')  # Close
                                volume = kline.get('v')  # Volume
                                
                                # Sanitize and validate
                                safe_candle = _sanitize_candle(
                                    timestamp,
                                    open_price,
                                    high,
                                    low,
                                    close,
                                    volume
                                )
                                
                                if safe_candle:
                                    # 🔍 Diagnostic: Log Ring Buffer write
                                    write_cursor_before = ring_buffer._get_cursors()[0]
                                    ring_buffer.write_candle(safe_candle)
                                    write_cursor_after = ring_buffer._get_cursors()[0]
                                    candle_count += 1
                                    
                                    # Log every 10 writes (more frequent for diagnostics)
                                    if candle_count % 10 == 0:
                                        pending = ring_buffer.pending_count()
                                        logger.critical(f"🔍 Feed Ring Buffer: Written {candle_count}, Pending={pending}, Cursor: {write_cursor_before}→{write_cursor_after}")
                                    
                                    # 💾 Persist market data to PostgreSQL & Redis
                                    try:
                                        # Extract OHLCV data
                                        ts, o, h, l, c, v = safe_candle
                                        symbol = kline.get('s', '')
                                        
                                        # Store to PostgreSQL market_data table (async non-blocking)
                                        if symbol:
                                            try:
                                                from src.database.unified_db import UnifiedDatabaseManager
                                                conn = await UnifiedDatabaseManager.get_connection()
                                                if conn:
                                                    await conn.execute("""
                                                        INSERT INTO market_data (symbol, timestamp, open_price, high_price, low_price, close_price, volume, timeframe)
                                                        VALUES ($1, $2, $3, $4, $5, $6, $7, '1m')
                                                    """, symbol, int(ts), float(o), float(h), float(l), float(c), float(v))
                                                    await conn.close()
                                            except Exception as e:
                                                logger.debug(f"Market data persistence: {e}")
                                        
                                        # Store to Redis cache (fast access)
                                        try:
                                            import redis.asyncio as redis_async
                                            from src.config import get_redis_url
                                            redis_url = get_redis_url()
                                            if redis_url:
                                                redis_client = await redis_async.from_url(redis_url, decode_responses=True)
                                                # Store latest OHLCV for each symbol
                                                market_data = json.dumps({
                                                    'symbol': symbol,
                                                    'timestamp': ts,
                                                    'o': o, 'h': h, 'l': l, 'c': c, 'v': v
                                                })
                                                await redis_client.set(f"market:{symbol}", market_data, ex=3600)  # 1hr TTL
                                                await redis_client.close()
                                        except Exception as e:
                                            logger.debug(f"Redis market data: {e}")
                                    except Exception as e:
                                        logger.debug(f"Market data collection: {e}")
                                    
                                    if candle_count % 100 == 0:
                                        logger.info(f"📊 Feed: {candle_count} candles written to ring buffer")
                        
                        except asyncio.TimeoutError:
                            # 這是正常的 - Binance 可能暫時沒有新資料
                            logger.debug("⏱️ WebSocket receive timeout - waiting for next message...")
                            continue
                        except json.JSONDecodeError:
                            logger.debug("Invalid JSON received - skipping...")
                            continue
                        except websockets.exceptions.ConnectionClosedError as e:
                            # WebSocket 被正常關閉（通常是 keepalive ping timeout）
                            logger.warning(f"⚠️  WebSocket connection closed: {e}")
                            break  # 跳出內層 while，觸發重連
                        except Exception as e:
                            # 只記錄真正的錯誤，不要把 ConnectionClosedError 當成普通錯誤
                            logger.debug(f"Message processing: {e}")
                            continue
            
            except websockets.exceptions.WebSocketException as e:
                reconnect_count += 1
                # 指數退避，但 cap 在 30s（保持快速重連）
                wait_time = min(2 ** reconnect_count, 30)
                logger.info(f"🔄 WebSocket disconnected ({reconnect_count} attempts): {type(e).__name__}")
                logger.info(f"   Reconnecting in {wait_time}s...")
                await asyncio.sleep(wait_time)
            
            except Exception as e:
                reconnect_count += 1
                wait_time = min(2 ** reconnect_count, 30)
                logger.warning(f"🔄 Connection error: {type(e).__name__}: {e}")
                logger.info(f"   Reconnecting in {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        # 由於 max_reconnect_attempts 是 999，這本質上不會被觸發
        logger.critical(f"Feed process exceeded max reconnection attempts - stopping")
        return
    
    except KeyboardInterrupt:
        logger.info("📡 Feed process terminated")
    except Exception as e:
        logger.critical(f"Feed process error: {e}", exc_info=True)


if __name__ == "__main__":
    """Entry point for supervisord"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("📡 Feed process stopped")
    except Exception as e:
        logger.critical(f"Fatal error in Feed: {e}", exc_info=True)
