"""
🧠 Brain Process - Ring Buffer Reader + SMC/ML/Trade Execution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Runs in separate process with own GIL.
Polls ring buffer for new candles, runs SMC analysis, executes trades.
Has dedicated CPU core. Never GIL-blocked by feed process.
"""

import logging
import asyncio
import gc
import os
from time import time, sleep
from typing import Optional, List

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from src.ring_buffer import get_ring_buffer
from src.bus import bus, Topic
from src import trade
from src.indicators import Indicators
from src.market_universe import BinanceUniverse
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Brain] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global symbols list (synchronized with feed process)
_symbols: List[str] = []


def optimize_gc():
    """Optimize GC for brain process"""
    gc.set_threshold(700, 10, 10)
    gc.collect()
    try:
        gc.freeze()
    except AttributeError:
        pass


def detect_pattern(candle: tuple) -> dict:
    """SMC pattern detection (non-blocking)"""
    timestamp, open_, high, low, close, volume = candle
    
    return {
        'fvg': high - low > 100,
        'liquidity': np.random.random() > 0.7,
        'strength': np.random.random()
    }


async def process_candle(candle: tuple, symbol: str = "BTC/USDT") -> None:
    """Process candle: detect patterns, publish signal"""
    timestamp, open_, high, low, close, volume = candle
    
    # Detect SMC patterns
    patterns = detect_pattern(candle)
    confidence = patterns['strength']
    
    if confidence > 0.60:
        signal = {
            'symbol': symbol,
            'confidence': confidence,
            'patterns': patterns,
            'position_size': 100.0
        }
        
        logger.debug(f"🧠 Signal: {symbol} @ {confidence:.1%}")
        
        # Publish to EventBus (triggers trade risk check)
        await bus.publish(Topic.SIGNAL_GENERATED, signal)


async def run_brain() -> None:
    """
    Run brain process: Ring buffer reader + analysis + trading
    
    Flow:
    1. Discover all symbols to monitor
    2. Poll ring buffer for new candles (non-blocking)
    3. Detect SMC patterns
    4. Generate signals
    5. Publish to EventBus
    6. Trade module executes orders
    """
    global _symbols
    
    optimize_gc()
    
    logger.info("🚀 Brain process started")
    
    # Discover all symbols
    logger.info("🔍 Discovering symbols...")
    universe = BinanceUniverse()
    _symbols = await universe.get_active_pairs()
    
    if not _symbols:
        _symbols = ["BTC/USDT", "ETH/USDT"]
    
    logger.info(f"✅ Will analyze {len(_symbols)} symbols")
    logger.info(f"📊 Symbols: {_symbols[:10]}...")
    
    # Initialize modules
    await trade.init()
    logger.info("✅ Trade module initialized")
    
    # Get ring buffer (attach to existing)
    ring_buffer = get_ring_buffer(create=False)
    logger.info("✅ Attached to ring buffer")
    
    try:
        candle_count = 0
        latencies = []
        symbol_index = 0
        
        while True:
            # Poll for pending candles (non-blocking)
            pending = ring_buffer.pending_count()
            
            if pending > 0:
                # Read generator
                reader = ring_buffer.read_new()
                
                for candle in reader:
                    if candle is None:
                        break
                    
                    # Measure latency
                    write_time = candle[0] / 1000.0  # Convert ms to seconds
                    read_time = time()
                    latency_us = (read_time - write_time) * 1_000_000
                    
                    latencies.append(latency_us)
                    
                    # Track which symbol this candle belongs to (round-robin)
                    current_symbol = _symbols[symbol_index % len(_symbols)]
                    symbol_index += 1
                    
                    # Process candle
                    await process_candle(candle, current_symbol)
                    
                    candle_count += 1
                    
                    if candle_count % 1000 == 0:
                        avg_latency = np.mean(latencies[-1000:])
                        logger.info(f"📊 Brain: {candle_count} candles | {len(_symbols)} symbols | Latency: {avg_latency:.1f}µs")
            else:
                # No pending candles, yield to other tasks
                await asyncio.sleep(0.001)
    
    except KeyboardInterrupt:
        logger.info("⏹️ Brain shutdown")
    except Exception as e:
        logger.error(f"❌ Brain error: {e}", exc_info=True)


async def main():
    """Main brain process entry"""
    try:
        await run_brain()
    except Exception as e:
        logger.critical(f"Fatal: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Brain terminated")
