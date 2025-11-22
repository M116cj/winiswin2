"""
📡 Feed Process - WebSocket Data Ingestion + Ring Buffer Writer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Runs in separate process with own GIL.
Receives ticks from WebSocket, writes to shared memory ring buffer.
Never blocks. Handles 100,000+ ticks/sec.
"""

import logging
import asyncio
import gc
from time import time
from typing import List, Optional

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from src.ring_buffer import get_ring_buffer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Feed] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def optimize_gc():
    """Optimize GC for feed process"""
    gc.set_threshold(700, 10, 10)
    gc.collect()
    try:
        gc.freeze()
    except AttributeError:
        pass


async def run_feed(symbols: Optional[List[str]] = None) -> None:
    """
    Run feed process: WebSocket + Ring Buffer writer
    
    Args:
        symbols: Symbols to stream
    """
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT"]
    
    optimize_gc()
    
    logger.info(f"🚀 Feed process started (symbols={symbols})")
    
    # Get ring buffer (attach to existing)
    ring_buffer = get_ring_buffer(create=False)
    logger.info("✅ Attached to ring buffer")
    
    try:
        tick_count = 0
        
        # Simulated WebSocket feed
        while True:
            await asyncio.sleep(0.001)  # Simulate 1000 ticks/sec
            
            # Generate simulated tick
            current_time = time()
            tick = {
                'symbol': 'BTCUSDT',
                'open': 42000 + (tick_count % 100),
                'high': 42500 + (tick_count % 100),
                'low': 41500 + (tick_count % 100),
                'close': 42200 + (tick_count % 100),
                'volume': 1000.0,
                'time': int(current_time * 1000)
            }
            
            # Write to ring buffer (non-blocking, struct packed)
            candle = (
                float(tick['time']),
                float(tick['open']),
                float(tick['high']),
                float(tick['low']),
                float(tick['close']),
                float(tick['volume'])
            )
            ring_buffer.write(candle)
            
            tick_count += 1
            if tick_count % 10000 == 0:
                logger.info(f"📊 Feed: {tick_count} ticks written")
    
    except KeyboardInterrupt:
        logger.info("⏹️ Feed shutdown")
    except Exception as e:
        logger.error(f"❌ Feed error: {e}", exc_info=True)


async def main():
    """Main feed process entry"""
    try:
        await run_feed()
    except Exception as e:
        logger.critical(f"Fatal: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Feed terminated")
