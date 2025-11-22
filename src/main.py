"""
🚀 Main - Dual-Process Quantum Engine (Ring Buffer + Zero GIL Contention)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Kernel-level optimization: Launches two independent processes
- Process 1 (Feed): Reads WebSocket, writes to ring buffer
- Process 2 (Brain): Polls ring buffer, runs SMC/ML/Trade

No GIL contention. Microsecond latency. Scalable to 300+ symbols.
"""

import logging
import os
import sys
import multiprocessing
from typing import Optional

from src.ring_buffer import get_ring_buffer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_feed_process():
    """Run feed process (Process 1)"""
    from src import feed
    
    logger.info(f"📡 Feed Process started (PID={os.getpid()})")
    
    try:
        import asyncio
        asyncio.run(feed.main())
    except KeyboardInterrupt:
        logger.info("Feed process terminated")
    except Exception as e:
        logger.critical(f"Feed process fatal error: {e}", exc_info=True)


def run_brain_process():
    """Run brain process (Process 2)"""
    from src import brain
    
    logger.info(f"🧠 Brain Process started (PID={os.getpid()})")
    
    try:
        import asyncio
        asyncio.run(brain.main())
    except KeyboardInterrupt:
        logger.info("Brain process terminated")
    except Exception as e:
        logger.critical(f"Brain process fatal error: {e}", exc_info=True)


def main():
    """
    Main orchestrator: Launch Feed + Brain processes
    
    Architecture:
    1. Create shared memory ring buffer
    2. Launch Feed process (WebSocket + Write)
    3. Launch Brain process (Read + Analysis + Trade)
    4. Keep both running with monitoring
    """
    logger.info("🚀 A.E.G.I.S. v8.0 - Dual-Process Quantum Engine")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Create ring buffer (in main process)
    logger.info("🔄 Creating shared memory ring buffer...")
    try:
        from src.ring_buffer import TOTAL_BUFFER_SIZE
        ring_buffer = get_ring_buffer(create=True)
        logger.info(f"✅ Ring buffer ready: {TOTAL_BUFFER_SIZE} bytes")
    except Exception as e:
        logger.error(f"❌ Failed to create ring buffer: {e}", exc_info=True)
        sys.exit(1)
    
    # Create processes
    logger.info("🚀 Launching Feed + Brain processes...")
    
    feed_process = multiprocessing.Process(
        target=run_feed_process,
        name="Feed-Process",
        daemon=False
    )
    
    brain_process = multiprocessing.Process(
        target=run_brain_process,
        name="Brain-Process",
        daemon=False
    )
    
    try:
        # Start both processes
        feed_process.start()
        logger.info(f"📡 Feed process started (PID={feed_process.pid})")
        
        brain_process.start()
        logger.info(f"🧠 Brain process started (PID={brain_process.pid})")
        
        logger.info("✅ All processes running")
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Monitor processes
        while feed_process.is_alive() and brain_process.is_alive():
            pass
        
        if not feed_process.is_alive():
            logger.warning("⚠️ Feed process died")
        if not brain_process.is_alive():
            logger.warning("⚠️ Brain process died")
    
    except KeyboardInterrupt:
        logger.info("⏹️ Shutdown requested")
        
        # Terminate both processes
        feed_process.terminate()
        brain_process.terminate()
        
        # Wait for graceful shutdown
        feed_process.join(timeout=5)
        brain_process.join(timeout=5)
        
        # Force kill if needed
        if feed_process.is_alive():
            feed_process.kill()
        if brain_process.is_alive():
            brain_process.kill()
        
        logger.info("🛑 All processes terminated")
    
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}", exc_info=True)
        feed_process.terminate()
        brain_process.terminate()
        sys.exit(1)


if __name__ == "__main__":
    # Required for Windows/macOS multiprocessing
    multiprocessing.set_start_method('spawn', force=True)
    
    try:
        main()
    except Exception as e:
        logger.critical(f"Fatal: {e}", exc_info=True)
        sys.exit(1)
