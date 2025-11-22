"""
🌐 FastAPI Dashboard Backend (Optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REST API for monitoring and controlling the A.E.G.I.S. trading system.
"""

import logging

logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI(title="A.E.G.I.S. Trading System")
    
    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "system": "A.E.G.I.S. v5.0"
        }
    
    @app.get("/status")
    async def status():
        """System status endpoint"""
        return {
            "trading": "online",
            "symbols_monitored": 300,
            "architecture": "SMC-Quant"
        }
    
    HAS_FASTAPI = True
    
except ImportError:
    logger.warning("⚠️ FastAPI not installed, dashboard disabled")
    app = None
    HAS_FASTAPI = False


if __name__ == "__main__" and HAS_FASTAPI:
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
