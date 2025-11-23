"""
📡 Feed Process - WebSocket Data Ingestion & Ring Buffer Writing
Minimal version for process communication
"""

import logging
import asyncio

logger = logging.getLogger(__name__)


def _sanitize_candle(timestamp, open_price, high, low, close, volume):
    """
    ✅ DATA SANITIZATION: Ensure all candle data is clean float before writing to ring buffer
    
    Protects against:
    - None values
    - String values
    - Mixed types
    - Invalid data from Binance API errors
    """
    try:
        # Convert all values to float, use 0 for None values
        safe_candle = (
            float(timestamp),
            float(open_price),
            float(high),
            float(low),
            float(close),
            float(volume or 0)
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
    - Connect to WebSocket
    - Read ticks/candles
    - Sanitize data
    - Write to ring buffer
    """
    logger.info("📡 Feed Process started")
    
    try:
        from src.ring_buffer import get_ring_buffer
        
        # Attach to ring buffer created by main process
        ring_buffer = get_ring_buffer(create=False)
        if ring_buffer is None:
            logger.error("❌ Failed to attach to ring buffer")
            return
        
        logger.info("✅ Feed attached to ring buffer")
        
        # Placeholder: In production, connect to Binance WebSocket
        # Example of how to write sanitized data:
        # while True:
        #     candle_data = await websocket.recv()  # Get data from Binance
        #     safe_candle = _sanitize_candle(
        #         candle_data['t'],
        #         candle_data['o'],
        #         candle_data['h'],
        #         candle_data['l'],
        #         candle_data['c'],
        #         candle_data['v']
        #     )
        #     if safe_candle:
        #         ring_buffer.write_candle(safe_candle)
        
        while True:
            await asyncio.sleep(10)
            # logger.debug("Fetching data from WebSocket...")
    
    except KeyboardInterrupt:
        logger.info("📡 Feed process terminated")
    except Exception as e:
        logger.critical(f"Feed process error: {e}", exc_info=True)
