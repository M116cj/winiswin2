"""
🚀 Main - Quantum Event-Driven Trading Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Orchestration: Initialize all modules and start the trading loop.
Flow: Data (ticks) → Brain (signals) → Trade (execution) → State (updates)
"""

import asyncio
import logging

from src import data, trade

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """
    Start quantum event-driven trading engine
    
    Flow:
    1. Initialize modules (they auto-subscribe to EventBus)
    2. Start data feed (heartbeat)
    3. Keep alive
    """
    try:
        logger.info("🚀 Starting Quantum Event-Driven Engine")
        
        # Initialize modules in order
        await trade.init()
        await data.init()
        
        logger.info("✅ All modules initialized")
        
        # Start data feed (the heartbeat that triggers everything)
        await data.start()
        
        # Keep running
        while True:
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("⏹️ Shutdown requested")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
    finally:
        await data.stop()
        logger.info("🛑 Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
