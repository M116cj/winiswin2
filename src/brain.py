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
from src.timeframe_analyzer import get_timeframe_analyzer
import numpy as np
import uuid

# ML & Experience Buffer
from src.ml_model import get_ml_model
from src.experience_buffer import get_experience_buffer

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
    """Legacy function - replaced by timeframe analyzer"""
    return {'strength': 0.5}


async def process_candle(candle: tuple, symbol: str = "BTC/USDT") -> None:
    """
    Process multi-timeframe signal (1D → 1H → 15m → 5m/1m)
    Only generates signals when all timeframes align
    """
    # Get real multi-timeframe data from buffer
    from src.timeframe_buffer import get_timeframe_buffer
    
    buffer = get_timeframe_buffer()
    
    # Add this candle to the buffer (it will be aggregated to all timeframes)
    buffer.add_tick(symbol, candle)
    
    # Check if we have enough data for analysis
    if not buffer.has_sufficient_data(symbol, min_candles_per_tf=3):
        return
    
    # Get complete multi-timeframe candles
    candles_by_tf = buffer.get_candles_by_tf(symbol)
    
    # Use timeframe analyzer for proper multi-timeframe validation
    analyzer = get_timeframe_analyzer()
    signal_data = analyzer.validate_setup(symbol, candles_by_tf)
    
    if signal_data is None:
        # Setup failed - not a valid signal
        return
    
    # ✅ Multi-timeframe validation passed
    # Extract current market price from latest candle (close price)
    current_price = candle[4] if len(candle) > 4 else 1.0
    
    # Create complete signal object
    signal = {
        'signal_id': str(uuid.uuid4()),
        'symbol': symbol,
        'confidence': signal_data['confidence'],
        'direction': signal_data['direction'],
        'strength': signal_data['strength'],
        'timeframe_analysis': signal_data['timeframe_analysis'],
        'position_size': 100.0,
        'entry_price': current_price,  # 🎯 Real market price for virtual trading
        'timestamp': candle[0] / 1000.0
    }
    
    # 🤖 ML model enhancement (optional)
    ml_model = get_ml_model()
    if ml_model.is_trained:
        signal = await ml_model.adjust_confidence(signal)
    
    # 💾 Record in experience buffer
    experience_buffer = get_experience_buffer()
    await experience_buffer.record_signal(signal['signal_id'], signal)
    
    logger.critical(
        f"🎯 {symbol} {signal['direction']} Signal | "
        f"Confidence: {signal['confidence']:.2%} | "
        f"1D:{signal['timeframe_analysis']['1d']['confidence']:.0%} "
        f"1H:{signal['timeframe_analysis']['1h']['confidence']:.0%} "
        f"15m:{signal['timeframe_analysis']['15m']['confidence']:.0%}"
    )
    
    # Publish to EventBus
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
        _symbols = [
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "SOL/USDT",
            "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "MATIC/USDT",
            "FTT/USDT", "TRX/USDT", "ARB/USDT", "OP/USDT", "LTC/USDT",
            "BCH/USDT", "ETC/USDT", "XLM/USDT", "ATOM/USDT", "UNI/USDT"
        ]
    
    logger.info(f"✅ Will analyze {len(_symbols)} symbols")
    logger.info(f"📊 Symbols: {_symbols[:10]}...")
    
    # Initialize modules
    await trade.init()
    logger.info("✅ Trade module initialized")
    
    # Initialize ML model
    ml_model = get_ml_model()
    logger.info("✅ ML model initialized")
    
    # Initialize experience buffer
    experience_buffer = get_experience_buffer()
    logger.info("✅ Experience buffer initialized")
    
    # Get ring buffer (attach to existing)
    ring_buffer = get_ring_buffer(create=False)
    if ring_buffer is None:
        logger.error("❌ Failed to attach to ring buffer")
        return
    logger.info("✅ Attached to ring buffer")
    
    try:
        candle_count = 0
        latencies = []
        symbol_index = 0
        
        while True:
            # Poll for pending candles (non-blocking)
            if ring_buffer is None:
                await asyncio.sleep(0.001)
                continue
            
            pending = ring_buffer.pending_count()
            
            if pending > 0:
                # Read generator
                for candle in ring_buffer.read_new():
                    if candle is None:
                        break
                    
                    try:
                        # Measure latency
                        write_time = candle[0] / 1000.0  # Convert ms to seconds
                        read_time = time()
                        latency_us = (read_time - write_time) * 1_000_000
                        
                        latencies.append(latency_us)
                        
                        # Track which symbol this candle belongs to (round-robin)
                        current_symbol = _symbols[symbol_index % len(_symbols)]
                        symbol_index += 1
                        
                        # Process candle (no need to pass candles_by_tf - it's fetched from buffer)
                        await process_candle(candle, current_symbol)
                        
                        candle_count += 1
                        
                        if candle_count % 1000 == 0:
                            avg_latency = np.mean(latencies[-1000:])
                            logger.info(f"📊 Brain: {candle_count} candles | {len(_symbols)} symbols | Latency: {avg_latency:.1f}µs")
                    except Exception as e:
                        logger.error(f"Error processing candle: {e}", exc_info=True)
                        continue
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
    """Entry point for supervisord"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🧠 Brain process stopped")
    except Exception as e:
        logger.critical(f"Fatal error in Brain: {e}", exc_info=True)
