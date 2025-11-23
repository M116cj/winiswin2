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
    level=logging.WARNING,
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


def run_orchestrator():
    """Run orchestrator process (Process 3) - Cache reconciliation, monitoring & maintenance"""
    import asyncio
    from src import reconciliation
    from src.core import system_monitor
    from src import maintenance
    
    logger.info(f"🔄 Orchestrator Process started (PID={os.getpid()})")
    
    try:
        # Run orchestrator with system monitoring and auto-maintenance
        async def orchestrator_main():
            # Start all tasks in parallel
            reconciliation_task = asyncio.create_task(reconciliation.background_reconciliation_task())
            monitor_task = asyncio.create_task(system_monitor.background_monitor_task())
            maintenance_task = asyncio.create_task(maintenance.background_maintenance_task())
            
            # Wait for all (they run indefinitely)
            await asyncio.gather(reconciliation_task, monitor_task, maintenance_task)
        
        asyncio.run(orchestrator_main())
    except KeyboardInterrupt:
        logger.info("Orchestrator process terminated")
    except Exception as e:
        logger.critical(f"Orchestrator process fatal error: {e}", exc_info=True)


def main():
    """
    Main orchestrator: Launch Feed + Brain processes
    
    Architecture:
    1. Create shared memory ring buffer
    2. Launch Feed process (WebSocket + Write)
    3. Launch Brain process (Read + Analysis + Trade)
    4. Keep both running with monitoring
    """
    logger.critical("🚀 A.E.G.I.S. v8.0 - Dual-Process Quantum Engine")
    logger.critical("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.critical("🔇 Log Level: WARNING (Noise silenced)")
    logger.critical("💓 System Monitor: Enabled (15-min heartbeat)")
    logger.critical("🧹 Auto-Maintenance: Enabled (log rotation, cache pruning, health checks)")
    
    # Create ring buffer (in main process)
    logger.critical("🔄 Creating shared memory ring buffer...")
    try:
        from src.ring_buffer import TOTAL_BUFFER_SIZE
        ring_buffer = get_ring_buffer(create=True)
        logger.critical(f"✅ Ring buffer ready: {TOTAL_BUFFER_SIZE} bytes")
    except Exception as e:
        logger.error(f"❌ Failed to create ring buffer: {e}", exc_info=True)
        sys.exit(1)
    
    # Create processes
    logger.critical("🚀 Launching Feed + Brain + Orchestrator processes...")
    
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
    
    orchestrator_process = multiprocessing.Process(
        target=run_orchestrator,
        name="Orchestrator-Process",
        daemon=False
    )
    
    try:
        # Start all processes
        feed_process.start()
        logger.critical(f"📡 Feed process started (PID={feed_process.pid})")
        
        brain_process.start()
        logger.critical(f"🧠 Brain process started (PID={brain_process.pid})")
        
        orchestrator_process.start()
        logger.critical(f"🔄 Orchestrator process started (PID={orchestrator_process.pid})")
        logger.critical(f"   └─ Includes: Cache reconciliation (15 min) + System monitor (heartbeat)")
        logger.critical(f"   └─ Maintenance: Log rotation (24h) + Cache pruning (1h) + Health checks (6h) + Shard rotation (12h)")
        
        logger.critical("✅ All processes running")
        logger.critical("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.critical("🔄 Entering Process Monitor Loop (keep-alive)")
        
        # ⚓ PRODUCTION KEEP-ALIVE LOOP
        # This ensures the main process stays running and monitors child processes
        import time
        try:
            while True:
                # Check every 5 seconds (non-blocking)
                time.sleep(5)
                
                # Monitor process health
                feed_alive = feed_process.is_alive()
                brain_alive = brain_process.is_alive()
                orch_alive = orchestrator_process.is_alive()
                
                # If any critical process died, log and exit (container restart)
                if not feed_alive:
                    logger.critical("🔴 CRITICAL: Feed process died! Container will restart.")
                    sys.exit(1)
                
                if not brain_alive:
                    logger.critical("🔴 CRITICAL: Brain process died! Container will restart.")
                    sys.exit(1)
                
                if not orch_alive:
                    logger.critical("🔴 CRITICAL: Orchestrator process died! Container will restart.")
                    sys.exit(1)
                
                # All processes alive - continue monitoring
                logger.debug(f"✅ All processes running (Feed={feed_alive}, Brain={brain_alive}, Orch={orch_alive})")
        
        except KeyboardInterrupt:
            logger.critical("🔄 Graceful shutdown requested...")
            raise  # Re-raise to trigger cleanup below
    
    except KeyboardInterrupt:
        logger.critical("⏹️ Shutdown requested")
        
        # Terminate all processes
        feed_process.terminate()
        brain_process.terminate()
        orchestrator_process.terminate()
        
        # Wait for graceful shutdown
        feed_process.join(timeout=5)
        brain_process.join(timeout=5)
        orchestrator_process.join(timeout=5)
        
        # Force kill if needed
        if feed_process.is_alive():
            feed_process.kill()
        if brain_process.is_alive():
            brain_process.kill()
        if orchestrator_process.is_alive():
            orchestrator_process.kill()
        
        logger.critical("🛑 All processes terminated")
    
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}", exc_info=True)
        feed_process.terminate()
        brain_process.terminate()
        orchestrator_process.terminate()
        sys.exit(1)


if __name__ == "__main__":
    # Required for Windows/macOS multiprocessing
    multiprocessing.set_start_method('spawn', force=True)
    
    try:
        main()
    except Exception as e:
        logger.critical(f"Fatal: {e}", exc_info=True)
        sys.exit(1)
