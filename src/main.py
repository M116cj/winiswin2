"""
🚀 SelfLearningTrader - SMC-Quant Sharded Engine v5.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Main Entry Point for Production Deployment

Architecture: Sharded SMC-Quant Engine
- Zero-polling (WebSocket + local cache only)
- 300+ pair concurrent monitoring
- ML-driven confidence filtering
- Dynamic risk management
"""

import asyncio
import logging
import sys
from typing import Optional, Dict, Any, Callable

# 🔥 Performance: Enable uvloop for 2-4x faster event loop
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    _UVLOOP_ENABLED = True
except ImportError:
    _UVLOOP_ENABLED = False

# ════════════════════════════════════════════════════════════════════════════
# CORE IMPORTS - SMC-Quant Sharded Architecture
# ════════════════════════════════════════════════════════════════════════════

from src.core.unified_config import UnifiedConfig
from src.core.cluster_manager import ClusterManager
from src.core.websocket.shard_feed import ShardFeed
from src.core.account_state_cache import AccountStateCache
from src.strategies.ict_scalper import ICTScalper
from src.utils.smart_logger import SmartLogger
from src.ml.hybrid_learner import HybridLearner

# Setup logging
logger = logging.getLogger(__name__)
smart_logger = SmartLogger(
    name="SelfLearningTrader",
    rate_limit_window=3.0,
    enable_aggregation=True
)


class SelfLearningTradingSystem:
    """
    Production-grade SMC-Quant Sharded Engine
    
    Components:
    ├─ ClusterManager (300+ pair orchestration)
    ├─ ShardFeed (zero-polling WebSocket data)
    ├─ AccountStateCache (in-memory account state)
    ├─ ICTScalper (M1 scalping strategy)
    ├─ HybridLearner (Teacher-Student mode)
    └─ DriftDetector (Monitoring & stability)
    """
    
    def __init__(self):
        """Initialize trading system"""
        self.running = False
        self.config = UnifiedConfig
        
        # Core components
        self.cluster_manager: Optional[ClusterManager] = None
        self.shard_feed: Optional[ShardFeed] = None
        self.account_cache: Optional[AccountStateCache] = None
        self.strategy: Optional[ICTScalper] = None
        self.learner: Optional[HybridLearner] = None
        
        logger.info("✅ SelfLearningTradingSystem initialized")
    
    async def initialize(self):
        """Initialize all components"""
        try:
            logger.info("🚀 Initializing SMC-Quant Sharded Engine...")
            
            if _UVLOOP_ENABLED:
                logger.info("⚡ uvloop enabled (2-4x WebSocket performance)")
            
            # 1. Initialize account state cache (singleton, no initialize() needed)
            logger.info("💾 Initializing account state cache...")
            self.account_cache = AccountStateCache()
            logger.info("✅ Account cache initialized")
            
            # 2. Initialize cluster manager
            logger.info("🌐 Starting cluster manager (300+ pairs)...")
            self.cluster_manager = ClusterManager(
                None,  # BinanceClient optional
                on_signal_callback=self.on_signal
            )
            await self.cluster_manager.start()
            logger.info("✅ Cluster manager started")
            
            # 3. Start sharded market coverage
            logger.info("🌐 Starting sharded market coverage (300+ pairs)...")
            
            # Get all trading pairs from cluster manager universe
            pairs = self.cluster_manager.pairs if self.cluster_manager.pairs else []
            
            if not pairs:
                logger.warning("⚠️ No pairs discovered, using defaults")
                pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
            
            # Initialize shard feed with all pairs
            self.shard_feed = ShardFeed(
                all_symbols=pairs,
                shard_id=0,
                on_kline_callback=self.cluster_manager.on_kline_close
            )
            await self.shard_feed.start()
            logger.info(f"✅ ShardFeed started ({len(pairs)} pairs)")
            
            # 4. Initialize strategy
            logger.info("⚙️ Initializing ICT scalper strategy...")
            self.strategy = ICTScalper()
            logger.info("✅ Strategy initialized")
            
            # 5. Initialize hybrid learner
            logger.info("🧠 Initializing Hybrid Learner (Teacher-Student)...")
            self.learner = HybridLearner()
            await self.learner.update_phase()
            logger.info("✅ Hybrid learner initialized")
            
            self.running = True
            logger.info("✅ SMC-Quant Engine fully initialized")
        
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            sys.exit(1)
    
    async def on_signal(self, signal: Dict[str, Any]):
        """Handle trading signal from cluster manager"""
        try:
            if not self.strategy or not self.learner:
                return
            
            # Apply strategy logic
            symbol = signal.get('symbol', '')
            confidence = signal.get('confidence', 0)
            
            # Get max leverage from current learning phase
            max_leverage = self.learner.get_max_leverage()
            
            logger.info(f"📊 Signal: {symbol} confidence={confidence:.2%} leverage_max={max_leverage:.1f}x")
        
        except Exception as e:
            logger.error(f"❌ Signal handler error: {e}")
    
    async def run(self):
        """Main trading loop"""
        await self.initialize()
        
        try:
            logger.info("🎯 Trading system running...")
            while self.running:
                await asyncio.sleep(1)
        
        except KeyboardInterrupt:
            logger.info("⏹️ Keyboard interrupt received")
        except Exception as e:
            logger.error(f"❌ Runtime error: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down...")
        self.running = False
        
        if self.shard_feed:
            await self.shard_feed.stop()
        
        if self.cluster_manager:
            await self.cluster_manager.stop()
        
        logger.info("✅ Shutdown complete")


async def main():
    """Entry point"""
    system = SelfLearningTradingSystem()
    await system.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
