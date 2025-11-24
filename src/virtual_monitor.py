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
import time
from src.virtual_learning import check_virtual_tp_sl, get_virtual_state

logger = logging.getLogger(__name__)


async def run_virtual_monitor() -> None:
    """Run virtual TP/SL monitor + ML training + Data persistence continuously"""
    logger.critical("🎓 Virtual Learning Monitor started - Checking TP/SL every 5 seconds")
    
    check_interval = 5  # Check every 5 seconds
    report_interval = 300  # Report every 5 minutes
    training_interval = 600  # Train ML every 10 minutes
    persistence_interval = 600  # Persist experience buffer every 10 minutes
    check_count = 0
    
    last_report_time = time.time()
    last_training_time = time.time()
    last_persistence_time = time.time()
    
    while True:
        try:
            # Check virtual TP/SL
            check_count += 1
            await check_virtual_tp_sl()
            
            # Log performance report periodically
            current_time = time.time()
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
            
            # 💾 Persist experience buffer to PostgreSQL
            if current_time - last_persistence_time >= persistence_interval:
                try:
                    from src.experience_buffer import get_experience_buffer
                    from src.config import get_database_url
                    
                    exp_buffer = get_experience_buffer()
                    saved_count = await exp_buffer.save_to_database(get_database_url())
                    if saved_count > 0:
                        logger.critical(f"💾 Experience buffer persisted: {saved_count} records saved")
                    last_persistence_time = current_time
                except Exception as e:
                    logger.warning(f"⚠️ Experience buffer persistence skipped: {e}")
            
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
