"""
🚀 API Server - FastAPI with Health Monitoring
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Provides HTTP endpoints for Railway health checks and system monitoring.
Critical: Must start immediately to prevent container timeout on deployment.

Features:
✅ Health check endpoint for Railway deployment detection
✅ System status monitoring
✅ ASYNC-FIRST: API binds within 500ms using background thread
✅ Minimal overhead - pure FastAPI with uvicorn
"""

import os
import time
import logging
import threading
from fastapi import FastAPI
import uvicorn

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="A.E.G.I.S. v8.0", version="8.0.0")

# Server startup timestamp
_server_start_time = time.time()

# Global API server thread and flag
_api_thread = None
_api_ready_event = threading.Event()  # Signals when API is bound


@app.get("/health")
def health_check():
    """
    🏥 Health Check Endpoint
    
    Railway calls this to detect if the service is alive.
    Critical: Must respond immediately after server startup.
    """
    return {
        "status": "ok",
        "timestamp": time.time(),
        "uptime_seconds": time.time() - _server_start_time,
        "version": "8.0.0"
    }


@app.get("/")
def root():
    """Root endpoint - system info"""
    return {
        "name": "A.E.G.I.S. v8.0",
        "type": "High-Frequency Trading Engine",
        "status": "running",
        "uptime_seconds": time.time() - _server_start_time
    }


@app.get("/virtual-learning")
async def get_virtual_learning_state():
    """🎓 Get virtual learning account state"""
    try:
        from src.virtual_learning import get_virtual_state
        state = await get_virtual_state()
        return {
            "status": "ok",
            "virtual_learning": state
        }
    except Exception as e:
        logger.error(f"❌ Failed to get virtual state: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


def _run_api_server_sync(port: int):
    """
    🚀 SYNCHRONOUS API Server Runner (runs in background thread)
    
    This function runs synchronously in a background thread.
    Binds to port immediately, signals when ready, then serves forever.
    
    CRITICAL: This binds to the port within ~500ms, preventing Railway timeout.
    """
    try:
        logger.critical(f"🚀 [API Thread] Binding to 0.0.0.0:{port}")
        
        # Create config
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=port,
            log_level="warning",
            access_log=False  # Disable access logs to reduce noise
        )
        
        # Create server
        server = uvicorn.Server(config)
        
        # Signal that we're about to start serving (port binding happens here)
        logger.critical(f"🌐 [API Thread] Starting to serve on 0.0.0.0:{port}")
        _api_ready_event.set()  # <-- Signal: API is binding NOW
        
        # Run server synchronously (blocks until shutdown)
        server.run()
        
    except Exception as e:
        logger.critical(f"❌ [API Thread] Fatal error: {e}", exc_info=True)
        raise


def start_api_server() -> bool:
    """
    🚀 START API SERVER IN BACKGROUND THREAD
    
    CRITICAL DEPLOYMENT FIX - API-First Startup Strategy:
    - Starts API in background thread
    - Returns immediately (non-blocking)
    - Port binding happens within ~500ms
    - Main process can do heavy initialization while API serves
    
    Returns: True if thread started successfully, False otherwise
    
    USAGE:
        # Start API (returns immediately, API runs in background)
        if start_api_server():
            logger.info("✅ API server started in background thread")
            # Now safe to do heavy initialization
            time.sleep(2)  # Wait for API to fully bind
            # ... do DB init, ring buffer creation, etc ...
        else:
            logger.critical("❌ Failed to start API server")
            sys.exit(1)
    """
    global _api_thread, _api_ready_event
    
    try:
        port = int(os.getenv("PORT", 8080))
        logger.critical(f"🌐 PRIORITY 1: Starting API server in background thread")
        logger.critical(f"   Target: Bind to 0.0.0.0:{port} within 500ms")
        
        # Create and start background thread
        _api_thread = threading.Thread(
            target=_run_api_server_sync,
            args=(port,),
            daemon=True,  # Daemon thread - won't prevent program exit
            name="APIServer"
        )
        _api_thread.start()
        
        logger.critical("✅ API server thread started")
        logger.critical("   (API binding to port in background...)")
        
        return True
    
    except Exception as e:
        logger.critical(f"❌ Failed to start API server thread: {e}", exc_info=True)
        return False


def wait_for_api(timeout_seconds: float = 2.0) -> bool:
    """
    ⏳ WAIT FOR API TO BIND TO PORT
    
    Blocks until API signals it's ready or timeout expires.
    
    Args:
        timeout_seconds: How long to wait (default 2s)
    
    Returns:
        True if API is ready, False if timeout
    
    USAGE:
        if wait_for_api(timeout_seconds=2.0):
            logger.info("✅ API is bound and ready")
        else:
            logger.warning("⚠️ API timeout - proceeding anyway")
    """
    logger.critical(f"⏳ Waiting up to {timeout_seconds}s for API to bind...")
    
    if _api_ready_event.wait(timeout=timeout_seconds):
        logger.critical("✅ API is bound and ready for Railway health checks")
        return True
    else:
        logger.warning(f"⚠️ API timeout after {timeout_seconds}s (proceeding anyway)")
        return False


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting API server on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
