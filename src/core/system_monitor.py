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

logger = logging.getLogger(__name__)

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
        Get current account state (PnL, positions, balance)
        
        Returns:
            Dict with PnL, position_count, balance
        """
        try:
            # Import locally to avoid circular imports
            from src import trade
            
            state = trade._account_state
            
            # Calculate PnL (simplified: assume balance change = PnL)
            pnl = state.get('balance', 0) - 10000.0  # 10000 = initial balance
            positions = state.get('positions', {})
            
            return {
                'pnl': pnl,
                'position_count': len(positions),
                'balance': state.get('balance', 0),
                'trades': len(state.get('trades', []))
            }
        except Exception as e:
            logger.debug(f"Could not get account state: {e}")
            return {'pnl': 0, 'position_count': 0, 'balance': 0, 'trades': 0}
    
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
