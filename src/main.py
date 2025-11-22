"""
🚀 Main - Quantum Event-Driven Orchestration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pure orchestration. Components auto-subscribe on init. Start feed, keep alive.
Everything talks through EventBus. ZERO direct coupling.
"""

import asyncio
import logging

from src.bus import bus
from src.components import feed, brain, gatekeeper, hand, memory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """
    Start quantum event-driven engine
    
    Flow:
    1. Initialize components (they auto-subscribe to EventBus)
    2. Start feed (heartbeat)
    3. Keep alive
    """
    try:
        logger.info("🚀 Starting Quantum Event-Driven Engine")
        
        # Initialize components in order (they subscribe to EventBus)
        await memory.init()
        await hand.init()
        await gatekeeper.init()
        await brain.init()
        
        logger.info("✅ All components initialized")
        
        # Start feed (the heartbeat that triggers everything)
        await feed.start()
        
        # Keep running
        while True:
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("⏹️ Shutdown requested")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
    finally:
        await feed.stop()
        logger.info("🛑 Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
