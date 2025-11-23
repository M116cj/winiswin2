"""
💓 System Monitor - 15-Minute Heartbeat
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 3: 15-Minute Heartbeat
Periodically logs system health summary:
- PnL (Profit/Loss)
- ML Data Count
- Current Confidence Score
- Position Count

Logs bypass WARNING filter using logger.critical()
"""

import logging
import asyncio
import time
from typing import Optional, Dict, Any

import json  # Always available
import redis.asyncio as redis_async

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

logger = logging.getLogger(__name__)

# Redis client (initialized in this process)
_redis_client: Optional[redis_async.Redis] = None


async def _get_redis() -> Optional[redis_async.Redis]:
    """Get or initialize Redis client"""
    global _redis_client
    if _redis_client is None:
        try:
            from src.config import get_redis_url
            redis_url = get_redis_url()
            if redis_url:
                _redis_client = await redis_async.from_url(redis_url, decode_responses=False)
                logger.debug("✅ Redis client initialized for system monitor")
        except Exception as e:
            logger.debug(f"⚠️ Redis not available: {e}")
            return None
    return _redis_client

# Heartbeat interval in seconds (15 minutes = 900 seconds)
HEARTBEAT_INTERVAL = 900  # 15 minutes


class SystemMonitor:
    """
    Monitor system health and log heartbeat every 15 minutes
    
    Gathers:
    - Account balance / PnL
    - Number of open positions
    - ML data count
    - Current confidence score
    """
    
    def __init__(self, interval_seconds: int = HEARTBEAT_INTERVAL):
        """
        Initialize system monitor
        
        Args:
            interval_seconds: Heartbeat interval (default 900 = 15 min)
        """
        self.interval = interval_seconds
        self.last_heartbeat = time.time()
    
    async def get_account_state(self) -> Dict[str, Any]:
        """
        🔭 STATE RECEIVER: Get current account state from Postgres
        (Reads from shared state written by Trade/Brain process)
        
        Returns:
            Dict with PnL, position_count, balance, trades
        """
        try:
            # 💾 STEP 1: Try to read from Postgres (primary persistence layer)
            try:
                import asyncpg
                from src.config import get_database_url
                
                db_url = get_database_url()
                conn = await asyncpg.connect(db_url)
                
                # Get latest account state
                row = await conn.fetchrow("""
                    SELECT balance, pnl, trade_count, positions 
                    FROM account_state 
                    ORDER BY updated_at DESC 
                    LIMIT 1
                """)
                
                if row:
                    logger.debug(f"✅ Account state read from Postgres: Balance=${row['balance']:.2f}, Positions={len(json.loads(row['positions']))}")
                    
                    positions = json.loads(row['positions']) if row['positions'] else {}
                    await conn.close()
                    
                    return {
                        'pnl': row['pnl'],
                        'position_count': len(positions),
                        'balance': row['balance'],
                        'trades': row['trade_count']
                    }
                
                await conn.close()
            except Exception as pg_error:
                # Handle UndefinedTable error gracefully
                error_msg = str(pg_error)
                if "does not exist" in error_msg or "relation" in error_msg:
                    logger.warning("⚠️ account_state table does not exist - schema will be initialized on next startup")
                else:
                    logger.debug(f"⚠️ Postgres read failed: {pg_error}")
            
            # 📡 STEP 2: Fallback to Redis (if Postgres unavailable)
            redis = await _get_redis()
            
            if redis:
                raw_data = await redis.get("system:account_state")
                if raw_data:
                    # Deserialize from Redis
                    if HAS_ORJSON:
                        state = orjson.loads(raw_data)  # type: ignore
                    else:
                        state = json.loads(raw_data.decode('utf-8') if isinstance(raw_data, bytes) else raw_data)
                    
                    logger.debug(f"✅ Account state read from Redis: Balance=${state['balance']:.2f}, Positions={len(state['positions'])}")
                    
                    return {
                        'pnl': state.get('pnl', 0),
                        'position_count': len(state.get('positions', {})),
                        'balance': state.get('balance', 0),
                        'trades': state.get('trade_count', 0)
                    }
            
            # STEP 3: Fallback to local memory (if both Postgres and Redis unavailable)
            logger.debug("⚠️ Postgres and Redis unavailable, falling back to local memory")
            from src import trade
            state = trade._account_state
            pnl = state.get('balance', 0) - 10000.0
            positions = state.get('positions', {})
            
            return {
                'pnl': pnl,
                'position_count': len(positions),
                'balance': state.get('balance', 0),
                'trades': len(state.get('trades', []))
            }
        except Exception as e:
            logger.debug(f"Could not get account state: {e}")
            return {'pnl': 0, 'position_count': 0, 'balance': 10000.0, 'trades': 0}
    
    async def get_ml_data_count(self) -> int:
        """
        Get count of ML training data records
        
        In production: Query ExperienceBuffer from Redis/DB
        For now: Return 0 (placeholder)
        
        Returns:
            Number of ML data rows
        """
        try:
            # TODO: Connect to Redis/DB to get actual count
            # For now, return placeholder
            return 0
        except Exception as e:
            logger.debug(f"Could not get ML data count: {e}")
            return 0
    
    async def get_confidence_score(self) -> float:
        """
        Get latest confidence score from Brain process
        
        In production: Query confidence_ensemble from shared state
        For now: Return 0 (placeholder)
        
        Returns:
            Current confidence score (0.0 - 1.0)
        """
        try:
            # TODO: Get from shared state or Redis
            # For now, return placeholder
            return 0.0
        except Exception as e:
            logger.debug(f"Could not get confidence score: {e}")
            return 0.0
    
    async def log_heartbeat(self) -> None:
        """
        Log system health summary (bypasses WARNING filter)
        
        Format:
        📊 [SYSTEM REPORT] PnL: $X.XX | Positions: N | Balance: $Y.YY | 
           ML Data: Z rows | Score: C.CC
        """
        try:
            # Gather all metrics
            account = await self.get_account_state()
            ml_count = await self.get_ml_data_count()
            score = await self.get_confidence_score()
            
            # Format heartbeat message
            heartbeat_msg = (
                f"📊 [SYSTEM REPORT] "
                f"PnL: ${account['pnl']:,.2f} | "
                f"Positions: {account['position_count']} | "
                f"Balance: ${account['balance']:,.2f} | "
                f"Trades: {account['trades']} | "
                f"ML Data: {ml_count} rows | "
                f"Score: {score:.2f}"
            )
            
            # Log at CRITICAL level to bypass WARNING filter
            logger.critical(heartbeat_msg)
            
            self.last_heartbeat = time.time()
        
        except Exception as e:
            logger.error(f"Error logging heartbeat: {e}", exc_info=True)
    
    async def run(self) -> None:
        """
        Run heartbeat monitor loop
        
        Logs system health every HEARTBEAT_INTERVAL seconds
        Runs indefinitely (call from background task)
        """
        logger.info(f"💓 System monitor started (heartbeat every {self.interval}s)")
        
        try:
            while True:
                try:
                    # Wait for next heartbeat interval
                    await asyncio.sleep(self.interval)
                    
                    # Log heartbeat
                    await self.log_heartbeat()
                
                except asyncio.CancelledError:
                    logger.info("💓 System monitor cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in system monitor: {e}")
                    await asyncio.sleep(5)  # Retry after 5 seconds
        
        except Exception as e:
            logger.error(f"System monitor fatal error: {e}", exc_info=True)


async def background_monitor_task(interval: int = HEARTBEAT_INTERVAL) -> None:
    """
    Standalone background task for system monitoring
    
    Usage:
        # In main.py
        asyncio.create_task(background_monitor_task())
    
    Args:
        interval: Heartbeat interval in seconds
    """
    monitor = SystemMonitor(interval_seconds=interval)
    await monitor.run()


def create_monitor(interval: int = HEARTBEAT_INTERVAL) -> SystemMonitor:
    """
    Factory function to create system monitor
    
    Args:
        interval: Heartbeat interval in seconds
    
    Returns:
        Initialized SystemMonitor instance
    """
    return SystemMonitor(interval_seconds=interval)
