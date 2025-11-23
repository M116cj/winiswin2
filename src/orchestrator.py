"""
🔄 Orchestrator Process - Cache Reconciliation, Monitoring & Maintenance
Runs background tasks including system monitoring and automated maintenance
"""

import logging
import asyncio

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """
    Orchestrator main loop
    - Cache reconciliation (15 min)
    - System monitoring (heartbeat)
    - Auto-maintenance (4 tasks on schedules)
    """
    logger.info("🔄 Orchestrator Process started")
    
    try:
        from src import reconciliation
        from src.core import system_monitor
        from src import maintenance
        
        # Run all background tasks in parallel
        reconciliation_task = asyncio.create_task(reconciliation.background_reconciliation_task())
        monitor_task = asyncio.create_task(system_monitor.background_monitor_task())
        maintenance_task = asyncio.create_task(maintenance.background_maintenance_task())
        
        # Wait for all tasks (they run indefinitely)
        await asyncio.gather(reconciliation_task, monitor_task, maintenance_task)
    
    except KeyboardInterrupt:
        logger.info("⏹️ Orchestrator shutdown")
    except Exception as e:
        logger.critical(f"Orchestrator error: {e}", exc_info=True)


if __name__ == "__main__":
    """Entry point for supervisord"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🔄 Orchestrator process stopped")
    except Exception as e:
        logger.critical(f"Fatal error in Orchestrator: {e}", exc_info=True)
