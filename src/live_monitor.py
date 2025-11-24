"""
🔴 Live Monitor - Real-time Signal/Trade/ML Tracking
Run this in a separate terminal to monitor system in real-time
"""

import asyncio
import sys
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Monitor] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def live_monitor():
    """Real-time monitoring loop"""
    
    logger.info("🟢 Live Monitor Started - Tracking Signals/Trades/ML")
    logger.info("=" * 80)
    
    try:
        from src.monitoring_dashboard import MonitoringDashboard
        
        dashboard = MonitoringDashboard()
        
        cycle = 0
        while True:
            cycle += 1
            
            logger.info(f"\n📊 MONITORING CYCLE #{cycle} - {datetime.now().strftime('%H:%M:%S')}")
            
            # Collect data
            stats = await dashboard.collect_statistics()
            db_data = await dashboard.query_trading_data()
            
            # Print current state
            if stats:
                if stats.get('account_status'):
                    s = stats['account_status']
                    logger.info(f"💼 Equity: ${s.get('total_equity', 0):,.0f} | Return: {s.get('total_return_pct', 0):.2f}% | Trades: {s.get('trade_count', 0)} | Win: {s.get('win_rate', 0):.0%}")
            
            if db_data:
                logger.info(f"📈 Signals: {db_data['total_signals']} | Market Data: {db_data['market_data_records']}")
                
                # Check ML readiness
                if stats and stats['experiences_count'] >= 10:
                    logger.critical(f"🤖 ✅ ML TRAINING READY! {stats['experiences_count']} experiences collected")
                elif stats:
                    logger.info(f"🤖 ML Training: {stats['experiences_count']}/10 trades needed")
            
            # Wait before next cycle
            await asyncio.sleep(10)  # Update every 10 seconds
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Monitor stopped")
    except Exception as e:
        logger.error(f"❌ Monitor error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(live_monitor())
    except KeyboardInterrupt:
        logger.info("Monitor shut down")
