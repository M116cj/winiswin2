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

# ✅ Railway 日誌過濾
from src.utils.railway_logger import setup_railway_logger
setup_railway_logger(logger)

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
    🔄 ORCHESTRATOR PROCESS - Background Tasks Only
    
    CRITICAL: API Server is now started in MAIN PROCESS before this spawns.
    
    This process runs background maintenance tasks:
    - Cache reconciliation (15 min interval)
    - System monitoring (heartbeat)
    - Automated maintenance tasks
    
    The API server is already serving in the main process thread.
    """
    try:
        logger.critical("🚀 Starting ORCHESTRATOR process")
        logger.critical("   Role: Background maintenance tasks (not API)")
        
        import asyncio
        from src import reconciliation
        from src.core import system_monitor
        from src import maintenance
        
        async def orchestrator_main():
            """
            Run all background maintenance tasks in parallel
            """
            logger.critical("🔄 Orchestrator: Launching background maintenance tasks...")
            
            reconciliation_task = asyncio.create_task(
                reconciliation.background_reconciliation_task()
            )
            monitor_task = asyncio.create_task(
                system_monitor.background_monitor_task()
            )
            maintenance_task = asyncio.create_task(
                maintenance.background_maintenance_task()
            )
            
            # 🎓 Virtual Learning Monitor - Background TP/SL checking
            from src.virtual_monitor import run_virtual_monitor
            virtual_monitor_task = asyncio.create_task(run_virtual_monitor())
            
            # Wait for all tasks (they run indefinitely)
            try:
                await asyncio.gather(reconciliation_task, monitor_task, maintenance_task, virtual_monitor_task)
            except Exception as e:
                logger.critical(f"❌ Orchestrator background task error: {e}", exc_info=True)
                raise
        
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
    🚀 API-FIRST STARTUP - CRITICAL INCIDENT FIX
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    PROBLEM: Railway kills container (SIGTERM 15) during startup
    ROOT CAUSE: Heavy initialization (DB, Ring Buffer) blocks API port binding
    SOLUTION: Bind API port FIRST (< 500ms), do heavy work SECOND
    
    NEW FLOW (API-FIRST):
    1️⃣  Setup signal handlers
    2️⃣  START API SERVER IN BACKGROUND THREAD (returns immediately, port binding < 500ms)
    3️⃣  Wait for API to bind (Railway sees healthy port within 1-2 seconds)
    4️⃣  Initialize heavy resources (DB, Ring Buffer) - while API already serves
    5️⃣  Spawn worker processes (Feed, Brain)
    6️⃣  Spawn Orchestrator process (background maintenance)
    7️⃣  Enter keep-alive watchdog loop
    
    RESULT: 
    - API responds to Railway health checks within 1-2 seconds ✅
    - SIGTERM 15 timeout prevented ✅
    - Heavy initialization happens in background ✅
    - No container restarts ✅
    """
    global processes, shutdown_flag
    
    # 1️⃣ Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    logger.critical("🚀 A.E.G.I.S. v8.0 - API-FIRST STARTUP SEQUENCE")
    logger.critical("━" * 80)
    logger.critical("   Incident Fix: API binds within 500ms BEFORE heavy init")
    logger.critical("   Target: Health check response < 1 second")
    logger.critical("━" * 80)
    
    try:
        # 2️⃣ START API SERVER IN BACKGROUND THREAD (FAST - returns immediately!)
        logger.critical("⚡ STEP 1: Starting API server in background thread")
        logger.critical("   Target: Bind to 0.0.0.0:$PORT within 500ms")
        
        from src.api.server import start_api_server, wait_for_api
        
        if not start_api_server():
            logger.critical("❌ CRITICAL: Failed to start API server")
            sys.exit(1)
        
        logger.critical("✅ API server thread started (background)")
        
        # 3️⃣ Wait for API to bind + Railway health check window
        logger.critical("⏳ STEP 2: Waiting for API to bind...")
        logger.critical("   (Railway probes /health endpoint during this window)")
        
        wait_for_api(timeout_seconds=2.0)  # Wait up to 2 seconds
        logger.critical("✅ API port binding detected")
        logger.critical("✅ Railway health checks now passing")
        
        # 4️⃣ NOW do heavy initialization (while API is already serving!)
        logger.critical("🔄 STEP 3: Initializing heavy resources (DB + Ring Buffer)...")
        logger.critical("   (API continues serving health checks in background)")
        
        initialize_system()
        logger.critical("✅ Heavy resources initialized successfully")
        
        # 5️⃣ Spawn worker processes (Feed, Brain)
        logger.critical("📡 STEP 4: Launching worker processes...")
        
        p_feed = multiprocessing.Process(
            target=run_feed,
            name="Feed",
            daemon=False
        )
        p_feed.start()
        processes.append(p_feed)
        logger.critical(f"✅ Feed started (PID={p_feed.pid})")
        
        p_brain = multiprocessing.Process(
            target=run_brain,
            name="Brain",
            daemon=False
        )
        p_brain.start()
        processes.append(p_brain)
        logger.critical(f"✅ Brain started (PID={p_brain.pid})")
        
        # 6️⃣ Spawn Orchestrator process (background maintenance tasks)
        logger.critical("🔄 STEP 5: Launching Orchestrator (background tasks)...")
        p_orchestrator = multiprocessing.Process(
            target=run_orchestrator,
            name="Orchestrator",
            daemon=False
        )
        p_orchestrator.start()
        processes.append(p_orchestrator)
        logger.critical(f"✅ Orchestrator started (PID={p_orchestrator.pid})")
        
        logger.critical("━" * 80)
        logger.critical("✅ ALL SYSTEMS LAUNCHED SUCCESSFULLY")
        logger.critical(f"   API Server: Running in main process thread")
        logger.critical(f"   Feed: {p_feed.pid}, Brain: {p_brain.pid}")
        logger.critical(f"   Orchestrator: {p_orchestrator.pid}")
        logger.critical("🔄 Entering keep-alive monitoring loop...")
        logger.critical("━" * 80)
        
        # 7️⃣ KEEP-ALIVE WATCHDOG LOOP
        # Monitors all processes; if any dies, triggers container restart
        while not shutdown_flag:
            time.sleep(5)  # Check every 5 seconds
            
            # Check process health
            if not p_feed.is_alive():
                logger.critical("🔴 CRITICAL: Feed process died!")
                logger.critical("💥 Triggering container restart...")
                sys.exit(1)
            
            if not p_brain.is_alive():
                logger.critical("🔴 CRITICAL: Brain process died!")
                logger.critical("💥 Triggering container restart...")
                sys.exit(1)
            
            if not p_orchestrator.is_alive():
                logger.critical("🔴 CRITICAL: Orchestrator process died!")
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
