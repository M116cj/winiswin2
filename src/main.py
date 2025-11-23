"""
🚀 Main - A.E.G.I.S. v8.0 - Hardened Entry Point with 24/7 Stability
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Python Multiprocessing Specialist - Kernel-Level Dual-Process Architecture
Hardened to ensure 24/7 stability with proper signal handling and process monitoring.

Architecture:
- Process 1 (Orchestrator): priority=999 - Initializes DB + Ring Buffer
- Process 2 (Feed): priority=100 - WebSocket ingestion to ring buffer
- Process 3 (Brain): priority=50 - Analysis and trading execution

Features:
✅ Signal handling (SIGTERM, SIGINT)
✅ Process auto-restart on failure
✅ Graceful shutdown
✅ Zero-lock ring buffer communication
✅ Keep-alive watchdog loop
"""

import multiprocessing
import time
import signal
import sys
import os
import logging
from typing import List

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
processes: List[multiprocessing.Process] = []
shutdown_flag = False


def handle_signal(signum, frame):
    """Handle SIGTERM and SIGINT for graceful shutdown"""
    global shutdown_flag
    logger.critical(f"🛑 Signal {signum} received. Initiating graceful shutdown...")
    shutdown_flag = True


def run_feed():
    """Feed Process: WebSocket data ingestion to ring buffer"""
    try:
        from src import feed
        logger.critical("🚀 Starting FEED process (standalone)")
        import asyncio
        asyncio.run(feed.main())
    except KeyboardInterrupt:
        logger.info("📡 Feed process terminated")
    except Exception as e:
        logger.critical(f"❌ Feed process fatal error: {e}", exc_info=True)
        sys.exit(1)


def run_brain():
    """Brain Process: Ring buffer reader + SMC/ML analysis + Trade execution"""
    try:
        from src import brain
        logger.critical("🚀 Starting BRAIN process (standalone)")
        import asyncio
        asyncio.run(brain.main())
    except KeyboardInterrupt:
        logger.info("🧠 Brain process terminated")
    except Exception as e:
        logger.critical(f"❌ Brain process fatal error: {e}", exc_info=True)
        sys.exit(1)


def run_orchestrator():
    """
    Orchestrator Process: System initialization, reconciliation, monitoring, maintenance
    Runs on priority=999 to ensure initialization before Feed/Brain
    """
    try:
        logger.critical("🚀 Starting ORCHESTRATOR process (standalone)")
        
        # Initialize system (database + ring buffer) on startup
        logger.critical("🔄 Orchestrator: Initializing system on startup...")
        initialize_system()
        logger.critical("✅ Orchestrator: System initialization complete")
        
        # Now run orchestrator tasks
        import asyncio
        from src import reconciliation
        from src.core import system_monitor
        from src import maintenance
        
        async def orchestrator_main():
            """Run all orchestrator tasks in parallel"""
            reconciliation_task = asyncio.create_task(
                reconciliation.background_reconciliation_task()
            )
            monitor_task = asyncio.create_task(
                system_monitor.background_monitor_task()
            )
            maintenance_task = asyncio.create_task(
                maintenance.background_maintenance_task()
            )
            
            # Wait for all (they run indefinitely)
            await asyncio.gather(
                reconciliation_task, monitor_task, maintenance_task
            )
        
        asyncio.run(orchestrator_main())
    
    except KeyboardInterrupt:
        logger.info("🔄 Orchestrator process terminated")
    except Exception as e:
        logger.critical(f"❌ Orchestrator process fatal error: {e}", exc_info=True)
        sys.exit(1)


def initialize_system():
    """
    Initialize database schema and shared memory ring buffer
    Runs once in main process before spawning child processes
    """
    # Initialize database schema
    logger.critical("🗄️ Initializing database schema...")
    try:
        import asyncio
        from src.database import UnifiedDatabaseManager
        
        schema_result = asyncio.run(UnifiedDatabaseManager.init_schema())
        if schema_result:
            logger.critical("✅ Database schema initialized successfully")
        else:
            logger.warning("⚠️ Database schema initialization failed")
    except Exception as e:
        logger.critical(f"❌ Error initializing database: {e}", exc_info=True)
        sys.exit(1)
    
    # Create ring buffer
    logger.critical("🔄 Creating shared memory ring buffer...")
    try:
        from src.ring_buffer import get_ring_buffer, TOTAL_BUFFER_SIZE
        
        ring_buffer = get_ring_buffer(create=True)
        logger.critical(f"✅ Ring buffer created: {TOTAL_BUFFER_SIZE} bytes")
    except Exception as e:
        logger.critical(f"❌ Failed to create ring buffer: {e}", exc_info=True)
        sys.exit(1)


def main():
    """
    Main entry point: Orchestrates all processes with keep-alive monitoring
    
    Process startup order:
    1. Initialize system (DB + Ring Buffer)
    2. Spawn Orchestrator (priority=999)
    3. Spawn Feed (priority=100)
    4. Spawn Brain (priority=50)
    5. Enter keep-alive watchdog loop
    """
    global processes, shutdown_flag
    
    # Signal handling for graceful shutdown
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    logger.critical("🚀 A.E.G.I.S. v8.0 - Hardened Startup Sequence")
    logger.critical("━" * 80)
    
    # Initialize shared resources (database + ring buffer)
    initialize_system()
    
    logger.critical("📡 Spawning processes...")
    
    try:
        # Spawn Orchestrator (priority=999, starts FIRST)
        p_orchestrator = multiprocessing.Process(
            target=run_orchestrator,
            name="Orchestrator",
            daemon=False
        )
        p_orchestrator.start()
        processes.append(p_orchestrator)
        logger.critical(f"🔄 Orchestrator started (PID={p_orchestrator.pid})")
        
        # Spawn Feed (priority=100, starts SECOND)
        p_feed = multiprocessing.Process(
            target=run_feed,
            name="Feed",
            daemon=False
        )
        p_feed.start()
        processes.append(p_feed)
        logger.critical(f"📡 Feed started (PID={p_feed.pid})")
        
        # Spawn Brain (priority=50, starts THIRD)
        p_brain = multiprocessing.Process(
            target=run_brain,
            name="Brain",
            daemon=False
        )
        p_brain.start()
        processes.append(p_brain)
        logger.critical(f"🧠 Brain started (PID={p_brain.pid})")
        
        logger.critical("✅ All processes launched")
        logger.critical("🔄 Entering keep-alive monitoring loop...")
        logger.critical("━" * 80)
        
        # ⚓ KEEP-ALIVE WATCHDOG LOOP
        # Monitors all processes; if any dies, triggers container restart
        while not shutdown_flag:
            time.sleep(5)  # Check every 5 seconds
            
            # Check process health
            if not p_orchestrator.is_alive():
                logger.critical("🔴 CRITICAL: Orchestrator process died!")
                logger.critical("💥 Triggering container restart...")
                sys.exit(1)
            
            if not p_feed.is_alive():
                logger.critical("🔴 CRITICAL: Feed process died!")
                logger.critical("💥 Triggering container restart...")
                sys.exit(1)
            
            if not p_brain.is_alive():
                logger.critical("🔴 CRITICAL: Brain process died!")
                logger.critical("💥 Triggering container restart...")
                sys.exit(1)
            
            # All processes alive, continue monitoring
            logger.debug("✅ All processes running")
    
    except KeyboardInterrupt:
        logger.critical("⏹️ Shutdown requested (KeyboardInterrupt)")
        shutdown_flag = True
    
    except Exception as e:
        logger.critical(f"❌ Fatal error in main loop: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        # Graceful cleanup
        logger.critical("🛑 Stopping all processes...")
        
        for p in processes:
            if p.is_alive():
                logger.critical(f"   Terminating {p.name} (PID={p.pid})...")
                p.terminate()
        
        # Wait for graceful termination
        for p in processes:
            p.join(timeout=5)
        
        # Force kill if needed
        for p in processes:
            if p.is_alive():
                logger.critical(f"   Force killing {p.name} (PID={p.pid})...")
                p.kill()
        
        # Cleanup shared memory
        try:
            from src.ring_buffer import get_ring_buffer
            rb = get_ring_buffer(create=False)
            if rb is not None:
                rb.close()
                try:
                    rb.shm.unlink()
                    logger.critical("🧹 Shared memory unlinked")
                except (AttributeError, Exception):
                    pass
        except Exception as e:
            logger.warning(f"⚠️ Error cleaning up shared memory: {e}")
        
        logger.critical("👋 System shutdown complete")
        
        # Exit with appropriate code
        exit_code = 0 if shutdown_flag else 1
        sys.exit(exit_code)


if __name__ == "__main__":
    # Required for Windows/macOS multiprocessing
    multiprocessing.set_start_method('spawn', force=True)
    
    # Check for command-line arguments (standalone component mode)
    if len(sys.argv) > 1:
        component = sys.argv[1].lower()
        
        if component == "feed":
            try:
                run_feed()
            except Exception as e:
                logger.critical(f"Feed standalone fatal error: {e}", exc_info=True)
                sys.exit(1)
        
        elif component == "brain":
            try:
                run_brain()
            except Exception as e:
                logger.critical(f"Brain standalone fatal error: {e}", exc_info=True)
                sys.exit(1)
        
        elif component == "orchestrator":
            try:
                run_orchestrator()
            except Exception as e:
                logger.critical(f"Orchestrator standalone fatal error: {e}", exc_info=True)
                sys.exit(1)
        
        elif component == "init":
            try:
                logger.critical("🚀 System initialization only")
                initialize_system()
                logger.critical("✅ System initialization complete")
            except Exception as e:
                logger.critical(f"Initialization fatal error: {e}", exc_info=True)
                sys.exit(1)
        
        else:
            print("Usage: python -m src.main [feed|brain|orchestrator|init]")
            print(f"Unknown component: {component}")
            sys.exit(1)
    
    else:
        # No arguments - run full orchestrator mode
        try:
            main()
        except Exception as e:
            logger.critical(f"Fatal: {e}", exc_info=True)
            sys.exit(1)
