"""
🚀 SelfLearningTrader - SMC-Quant Sharded Engine v5.1

Production Entry Point (Pure Orchestration)
"""

import asyncio
import logging

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from src.core.cluster_manager import ClusterManager
from src.core.websocket.shard_feed import ShardFeed
from src.core.account_state_cache import AccountStateCache

logger = logging.getLogger(__name__)


class SelfLearningTradingSystem:
    """Main orchestration system - delegates all work"""
    
    async def run(self):
        """Start trading engine"""
        logger.info("🚀 Starting SMC-Quant Engine...")
        
        cache = AccountStateCache()
        manager = ClusterManager(None, on_signal_callback=self._on_signal)
        await manager.start()
        
        pairs = manager.pairs or ["BTCUSDT", "ETHUSDT"]
        feed = ShardFeed(pairs, 0, manager.on_kline_close)
        await feed.start()
        
        try:
            logger.info("✅ Engine running...")
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            logger.info("⏹️ Stopping...")
        finally:
            await feed.stop()
            await manager.stop()
    
    @staticmethod
    def _on_signal(signal):
        logger.info(f"📊 Signal: {signal.get('symbol')} @ {signal.get('confidence'):.1%}")


async def main():
    """Entry point"""
    system = SelfLearningTradingSystem()
    await system.run()


if __name__ == "__main__":
    asyncio.run(main())
