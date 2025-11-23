"""
🚀 Main - Dual-Process Quantum Engine (Ring Buffer + Zero GIL Contention)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Kernel-level optimization: Launches three independent processes
- Process 1 (Feed): Reads WebSocket, writes to ring buffer
- Process 2 (Brain): Polls ring buffer, runs SMC/ML/Trade
- Process 3 (Orchestrator): Cache reconciliation, monitoring, maintenance

No GIL contention. Microsecond latency. Scalable to 300+ symbols.
"""

import logging
import os
import sys
import multiprocessing
import time
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
        # Initialize system on startup (database + ring buffer)
        # This ensures one-time initialization in supervisord mode
        logger.critical("🔄 Orchestrator: Initializing system on startup...")
        initialize_system()
        logger.critical("✅ Orchestrator: System initialization complete")
        
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


def initialize_system():
    """
    Initialize database schema and shared memory ring buffer
    Called once at startup (by supervisord or orchestrator)
    """
    # Initialize database schema (auto-migration on startup)
    logger.critical("🗄️ Initializing database schema...")
    try:
        import asyncio
        from src.database import UnifiedDatabaseManager
        
        schema_result = asyncio.run(UnifiedDatabaseManager.init_schema())
        if schema_result:
            logger.critical("✅ Database schema initialized successfully")
        else:
            logger.warning("⚠️ Database schema initialization failed - system may not persist data")
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}", exc_info=True)
    
    # Create ring buffer (in main process)
    logger.critical("🔄 Creating shared memory ring buffer...")
    try:
        from src.ring_buffer import TOTAL_BUFFER_SIZE
        ring_buffer = get_ring_buffer(create=True)
        logger.critical(f"✅ Ring buffer ready: {TOTAL_BUFFER_SIZE} bytes")
    except Exception as e:
        logger.error(f"❌ Failed to create ring buffer: {e}", exc_info=True)
        sys.exit(1)


def main_supervisord():
    """
    Supervisord mode: Initialize system once, then just monitor
    This is called when running under supervisord
    """
    logger.critical("🚀 A.E.G.I.S. v8.0 - Supervisord Mode")
    logger.critical("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    initialize_system()
    
    logger.critical("✅ System initialized successfully")
    logger.critical("🔄 Supervisord will manage individual processes")
    logger.critical("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Exit gracefully - supervisord manages the processes
    sys.exit(0)


def main():
    """
    Main orchestrator: Launch Feed + Brain + Orchestrator processes
    
    Architecture:
    1. Initialize database schema
    2. Create shared memory ring buffer
    3. Launch Feed process (WebSocket + Write)
    4. Launch Brain process (Read + Analysis + Trade)
    5. Launch Orchestrator process (Reconciliation + Monitoring + Maintenance)
    6. Monitor all processes and handle restarts
    """
    logger.critical("🚀 A.E.G.I.S. v8.0 - Dual-Process Quantum Engine")
    logger.critical("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.critical("🔇 Log Level: WARNING (Noise silenced)")
    logger.critical("💓 System Monitor: Enabled (15-min heartbeat)")
    logger.critical("🧹 Auto-Maintenance: Enabled (log rotation, cache pruning, health checks)")
    
    initialize_system()
    
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
    
    # Check for command-line arguments (supervisord mode)
    if len(sys.argv) > 1:
        component = sys.argv[1].lower()
        
        if component == "feed":
            logger.critical("🚀 Starting FEED process (standalone)")
            try:
                run_feed_process()
            except Exception as e:
                logger.critical(f"Feed process fatal error: {e}", exc_info=True)
                sys.exit(1)
        
        elif component == "brain":
            logger.critical("🚀 Starting BRAIN process (standalone)")
            try:
                run_brain_process()
            except Exception as e:
                logger.critical(f"Brain process fatal error: {e}", exc_info=True)
                sys.exit(1)
        
        elif component == "orchestrator":
            logger.critical("🚀 Starting ORCHESTRATOR process (standalone)")
            try:
                run_orchestrator()
            except Exception as e:
                logger.critical(f"Orchestrator process fatal error: {e}", exc_info=True)
                sys.exit(1)
        
        elif component == "init":
            logger.critical("🚀 Initializing system (database + ring buffer)")
            try:
                initialize_system()
                logger.critical("✅ System initialization complete")
            except Exception as e:
                logger.critical(f"Initialization fatal error: {e}", exc_info=True)
                sys.exit(1)
        
        else:
            print(f"Usage: python -m src.main [feed|brain|orchestrator|init]")
            print(f"Invalid component: {component}")
            sys.exit(1)
    
    else:
        # No arguments - run full orchestrator mode (for local development)
        try:
            main()
        except Exception as e:
            logger.critical(f"Fatal: {e}", exc_info=True)
            sys.exit(1)
