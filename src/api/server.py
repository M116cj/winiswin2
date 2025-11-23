"""
🚀 API Server - FastAPI with Health Monitoring
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Provides HTTP endpoints for Railway health checks and system monitoring.
Critical: Must start immediately to prevent container timeout on deployment.

Features:
✅ Health check endpoint for Railway deployment detection
✅ System status monitoring
✅ Minimal overhead - pure FastAPI with uvicorn
"""

import os
import time
import logging
from fastapi import FastAPI
import uvicorn

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="A.E.G.I.S. v8.0", version="8.0.0")

# Server startup timestamp
_server_start_time = time.time()


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


async def start_api_server():
    """
    🚀 Start FastAPI server with uvicorn
    
    Critical deployment fix:
    - Binds to 0.0.0.0 to accept Railway health checks
    - Uses $PORT environment variable (Railway standard)
    - Runs asynchronously to not block other tasks
    
    Usage in orchestrator:
        uvicorn_config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=int(os.getenv("PORT", 8080)),
            log_level="info"
        )
        server = uvicorn.Server(uvicorn_config)
        await server.serve()
    """
    port = int(os.getenv("PORT", 8080))
    logger.critical(f"🚀 API Server binding to 0.0.0.0:{port}")
    
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        log_level="warning"
    )
    server = uvicorn.Server(config)
    
    # Return server instance for graceful shutdown support
    return server


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting API server on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
