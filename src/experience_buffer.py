"""
💾 Experience Buffer - Collect trading data for ML model training
Records every signal and its outcome for supervised learning
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import asyncpg

logger = logging.getLogger(__name__)


class ExperienceBuffer:
    """
    Collects trading experiences (signals, outcomes) for ML training
    
    Flow:
    1. Record signal generated (features + confidence)
    2. Track order execution (actual price, size)
    3. Record trade result (PnL, win/loss)
    4. Use data to train ML model
    """
    
    def __init__(self, max_size: int = 10000):
        """
        Initialize experience buffer
        
        Args:
            max_size: Maximum number of experiences to keep in memory
        """
        self.max_size = max_size
        self.experiences: List[Dict] = []
        self.lock = asyncio.Lock()
    
    async def record_signal(self, signal_id: str, signal_data: Dict) -> None:
        """
        Record a new trading signal (統一格式 + 百分比收益率)
        
        Args:
            signal_id: Unique signal identifier
            signal_data: {symbol, confidence, features, position_size, predicted_return_pct, position_sizing, timestamp (milliseconds)}
        """
        try:
            async with self.lock:
                experience = {
                    'signal_id': signal_id,
                    'type': 'signal',
                    'symbol': signal_data.get('symbol', ''),
                    'timestamp': int(signal_data.get('timestamp', int(datetime.now().timestamp() * 1000))),  # ✓ 毫秒
                    'features': signal_data.get('features', {}),
                    # ✅ NEW: Percentage return data
                    'predicted_return_pct': signal_data.get('predicted_return_pct', 0.0),
                    'position_sizing': signal_data.get('position_sizing', {}),
                    'order_amount': signal_data.get('order_amount', 0.0),
                    'tp_pct': signal_data.get('tp_pct', 0.0),
                    'sl_pct': signal_data.get('sl_pct', 0.0),
                    'outcome': None,
                    'recorded_at': int(datetime.now().timestamp() * 1000)  # ✓ 毫秒
                }
                
                self.experiences.append(experience)
                
                # Keep buffer size bounded
                if len(self.experiences) > self.max_size:
                    self.experiences.pop(0)
                
                logger.debug(f"📝 Signal recorded: {signal_data['symbol']} @ {signal_data.get('confidence', 0.5):.2f} | Return +{signal_data.get('predicted_return_pct', 0):.2%}")
        
        except Exception as e:
            logger.error(f"❌ Error recording signal: {e}", exc_info=True)
    
    async def record_trade_outcome(self, signal_id: str, trade_data: Dict) -> None:
        """
        Record the outcome of a trade (統一格式 + 百分比收益率結果)
        
        Args:
            signal_id: Unique signal identifier
            trade_data: {price, quantity, side, pnl, return_pct, status, close_reason}
        """
        try:
            async with self.lock:
                # Find corresponding signal
                for exp in self.experiences:
                    if exp.get('signal_id') == signal_id:
                        pnl = trade_data.get('pnl', 0)
                        exp['outcome'] = {
                            'entry_price': trade_data.get('entry_price', trade_data.get('price', 0)),
                            'exit_price': trade_data.get('exit_price', trade_data.get('price', 0)),
                            'quantity': trade_data.get('quantity', 0),
                            'side': trade_data.get('side', 'BUY'),
                            'pnl': pnl,
                            'pnl_percent': trade_data.get('pnl_percent', 0),
                            'status': trade_data.get('status', 'FILLED'),
                            'close_reason': trade_data.get('close_reason', 'UNKNOWN'),
                            'win': pnl > 0
                        }
                        exp['type'] = 'complete_trade'
                        logger.debug(f"✅ Trade outcome recorded: PnL ${pnl:.2f}")
                        break
        
        except Exception as e:
            logger.error(f"❌ Error recording outcome: {e}", exc_info=True)
    
    async def get_training_data(self) -> List[Dict]:
        """
        Get all recorded experiences with outcomes (for training)
        
        Returns:
            List of complete trades with features and labels
        """
        try:
            async with self.lock:
                # Filter only complete trades
                complete = [
                    exp for exp in self.experiences
                    if exp.get('type') == 'complete_trade'
                ]
                
                logger.info(f"📊 Training data available: {len(complete)} complete trades")
                return complete
        
        except Exception as e:
            logger.error(f"❌ Error getting training data: {e}")
            return []
    
    async def save_to_database(self, db_url: str) -> int:
        """
        Save buffer to Postgres for persistent storage
        
        Args:
            db_url: Database connection URL
        
        Returns:
            Number of experiences saved
        """
        try:
            conn = await asyncpg.connect(db_url)
            
            # Create table if not exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS experience_buffer (
                    id SERIAL PRIMARY KEY,
                    signal_id VARCHAR NOT NULL,
                    symbol VARCHAR NOT NULL,
                    confidence FLOAT NOT NULL,
                    patterns JSONB,
                    position_size FLOAT,
                    outcome JSONB,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert all experiences
            count = 0
            async with self.lock:
                for exp in self.experiences:
                    try:
                        await conn.execute("""
                            INSERT INTO experience_buffer 
                            (signal_id, symbol, confidence, patterns, position_size, outcome)
                            VALUES ($1, $2, $3, $4::jsonb, $5, $6::jsonb)
                        """,
                            exp.get('signal_id', ''),
                            exp.get('symbol', ''),
                            exp.get('confidence', 0),
                            json.dumps(exp.get('patterns', {})),
                            exp.get('position_size', 0),
                            json.dumps(exp.get('outcome', {}))
                        )
                        count += 1
                    except Exception as e:
                        logger.debug(f"⚠️ Error saving experience: {e}")
            
            await conn.close()
            logger.critical(f"💾 Saved {count} experiences to database")
            return count
        
        except Exception as e:
            logger.error(f"❌ Error saving to database: {e}", exc_info=True)
            return 0
    
    async def clear(self) -> None:
        """Clear all experiences from buffer"""
        async with self.lock:
            self.experiences.clear()
            logger.info("🧹 Experience buffer cleared")


# Global instance
_buffer: Optional[ExperienceBuffer] = None


def get_experience_buffer() -> ExperienceBuffer:
    """Get or create global experience buffer"""
    global _buffer
    if _buffer is None:
        _buffer = ExperienceBuffer()
        logger.info("✅ Experience buffer initialized")
    return _buffer
