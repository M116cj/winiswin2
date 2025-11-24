"""
🎓 Virtual Learning Monitor - Background Task
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Runs continuously in background to:
1. Check virtual positions for TP/SL
2. Close positions automatically
3. Log performance metrics
4. 🤖 Train ML model with virtual data (bias-checked)
"""

import asyncio
import logging
from src.virtual_learning import check_virtual_tp_sl, get_virtual_state

logger = logging.getLogger(__name__)


async def run_virtual_monitor() -> None:
    """Run virtual TP/SL monitor + ML training continuously"""
    logger.info("🎓 Virtual Learning Monitor started")
    
    check_interval = 5  # Check every 5 seconds
    report_interval = 300  # Report every 5 minutes
    training_interval = 600  # Train ML every 10 minutes
    last_report_time = 0
    last_training_time = 0
    
    while True:
        try:
            # Check virtual TP/SL
            await check_virtual_tp_sl()
            
            # Log performance report periodically
            current_time = asyncio.get_event_loop().time()
            if current_time - last_report_time >= report_interval:
                state = await get_virtual_state()
                logger.critical(
                    f"🎓 [VIRTUAL REPORT] Balance: ${state['balance']:.2f} | "
                    f"PnL: ${state['total_pnl']:.2f} | "
                    f"Open: {state['open_positions']} | "
                    f"Closed: {state['closed_positions']} | "
                    f"Win Rate: {state['win_rate']:.1f}%"
                )
                last_report_time = current_time
            
            # 🤖 Train ML model with virtual data periodically
            if current_time - last_training_time >= training_interval:
                try:
                    from src.ml_virtual_integrator import train_ml_with_virtual_data
                    from src.ml_model import get_ml_model
                    
                    ml_model = get_ml_model()
                    success = await train_ml_with_virtual_data(ml_model)
                    
                    if success:
                        logger.critical("🤖 ML model training completed successfully")
                    
                    last_training_time = current_time
                except Exception as e:
                    logger.warning(f"⚠️ ML training skipped: {e}")
            
            await asyncio.sleep(check_interval)
        
        except Exception as e:
            logger.error(f"❌ Virtual monitor error: {e}", exc_info=True)
            await asyncio.sleep(check_interval)
