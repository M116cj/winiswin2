"""
🚀 Main - Quantum Event-Driven Trading Engine (High-Performance + Dispatcher)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Orchestration with uvloop, GC optimization, priority dispatcher, and resilience.
Flow: Data (ticks) → Dispatcher → Analysis (threaded) → Trade → State
"""

import asyncio
import logging
import gc
import sys

# High-performance event loop
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    logging.warning("⚠️ uvloop not installed, using default event loop")

from src import data, trade
from src.dispatch import init_dispatcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def optimize_gc():
    """
    Optimize garbage collection for low-latency trading
    
    Strategy:
    1. Increase thresholds to reduce GC frequency
    2. Freeze initial objects to reduce scan overhead
    """
    # Tune GC thresholds for less frequent collections
    # (gen0_threshold, gen1_threshold, gen2_threshold)
    gc.set_threshold(700, 10, 10)
    
    # Collect everything first
    gc.collect()
    
    # Freeze built-in objects to avoid re-scanning them
    try:
        gc.freeze()
        logger.info("✅ GC optimized: thresholds=(700,10,10), startup objects frozen")
    except AttributeError:
        logger.warning("⚠️ gc.freeze() not available (Python < 3.13)")


async def main():
    """
    Start quantum event-driven trading engine with priority dispatcher
    
    Flow:
    1. Optimize GC
    2. Initialize dispatcher (priority queue + thread pool)
    3. Initialize modules (they auto-subscribe to EventBus)
    4. Start data feed (heartbeat)
    5. Keep alive with auto-reconnect
    """
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        try:
            logger.info("🚀 Starting Quantum Event-Driven Engine (uvloop + Dispatcher + GC optimized)")
            
            # Optimize garbage collection
            optimize_gc()
            
            # Initialize priority dispatcher
            logger.info("⚡ Initializing TaskDispatcher...")
            dispatcher = await init_dispatcher()
            logger.info("✅ TaskDispatcher ready")
            
            # Initialize modules in order
            await trade.init()
            await data.init()
            
            logger.info("✅ All modules initialized")
            
            # Start data feed (the heartbeat that triggers everything)
            logger.info("📡 Starting data feed...")
            await data.start()
            
            # Keep running
            while True:
                await asyncio.sleep(1)
        
        except KeyboardInterrupt:
            logger.info("⏹️ Shutdown requested")
            break
        
        except Exception as e:
            retry_count += 1
            logger.error(f"❌ Error (retry {retry_count}/{max_retries}): {e}", exc_info=True)
            
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                logger.info(f"⏳ Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.critical(f"❌ Max retries ({max_retries}) exceeded. Shutting down.")
                break
        
        finally:
            try:
                await data.stop()
            except Exception as e:
                logger.error(f"Error stopping data: {e}")
            
            logger.info("🛑 Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Terminated by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
