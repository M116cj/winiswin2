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
import uuid as uuid_module

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
        Save buffer to Postgres for persistent storage (修復版本 - 與實際表結構匹配)
        
        ✅ 表結構: experience_buffer (id, signal_id, features, outcome, created_at)
        ✅ 只在內存緩衝區中存儲完整交易（包含 outcome）
        ✅ 將內存的完整 experience 對象序列化為 features JSONB 和 outcome JSONB
        
        Args:
            db_url: Database connection URL
        
        Returns:
            Number of experiences saved
        """
        conn = None
        try:
            conn = await asyncpg.connect(db_url)
            
            # 插入所有完整的交易記錄
            count = 0
            error_count = 0
            async with self.lock:
                for exp in self.experiences:
                    # 只儲存有 outcome 的完整交易
                    if exp.get('type') == 'complete_trade' and exp.get('outcome') is not None:
                        try:
                            # 構建 features JSONB - 包含信號的所有特徵數據
                            features_data = {
                                'symbol': exp.get('symbol', ''),
                                'timestamp': exp.get('timestamp', 0),
                                'features': exp.get('features', {}),
                                'predicted_return_pct': exp.get('predicted_return_pct', 0.0),
                                'position_sizing': exp.get('position_sizing', {}),
                                'order_amount': exp.get('order_amount', 0.0),
                                'tp_pct': exp.get('tp_pct', 0.0),
                                'sl_pct': exp.get('sl_pct', 0.0),
                                'recorded_at': exp.get('recorded_at', 0),
                                'type': exp.get('type', '')
                            }
                            
                            # 轉換 signal_id 為 UUID（如果是字符串）
                            signal_id_val = exp.get('signal_id', '')
                            try:
                                # 嘗試轉換為 UUID
                                if signal_id_val and isinstance(signal_id_val, str):
                                    signal_id_uuid = uuid_module.UUID(signal_id_val)
                                else:
                                    # 無效的 signal_id，跳過
                                    logger.debug(f"⚠️ 跳過無效的 signal_id: {signal_id_val}")
                                    error_count += 1
                                    continue
                            except (ValueError, AttributeError) as uuid_err:
                                # 無效的 signal_id，跳過此記錄
                                logger.debug(f"⚠️ 跳過無效的 signal_id 格式: {signal_id_val}, 原因: {uuid_err}")
                                error_count += 1
                                continue
                            
                            # INSERT INTO experience_buffer (signal_id, features, outcome)
                            await conn.execute("""
                                INSERT INTO experience_buffer (signal_id, features, outcome)
                                VALUES ($1, $2::jsonb, $3::jsonb)
                            """,
                                signal_id_uuid,
                                json.dumps(features_data),
                                json.dumps(exp.get('outcome', {}))
                            )
                            count += 1
                            logger.debug(f"✅ 保存成功: signal_id={signal_id_uuid}")
                        
                        except asyncpg.UniqueViolationError as dup_err:
                            logger.debug(f"⚠️ 重複記錄 (signal_id 已存在): {dup_err}")
                            error_count += 1
                        
                        except Exception as e:
                            logger.debug(f"⚠️ 保存 experience 失敗: {type(e).__name__}: {e}")
                            error_count += 1
            
            logger.critical(f"💾 成功保存 {count} 筆 experience 到 PostgreSQL (失敗 {error_count} 筆)")
            return count
        
        except Exception as e:
            logger.error(f"❌ 保存到數據庫失敗: {e}", exc_info=True)
            return 0
        
        finally:
            if conn:
                try:
                    await conn.close()
                except:
                    pass
    
    async def read_from_database(self, db_url: str, limit: int = 100) -> List[Dict]:
        """
        從 PostgreSQL 讀取已保存的 experience 記錄
        
        Args:
            db_url: Database connection URL
            limit: 最多讀取記錄數
        
        Returns:
            List of experiences from database
        """
        conn = None
        try:
            conn = await asyncpg.connect(db_url)
            
            # SELECT 從 experience_buffer 讀取最新的記錄
            rows = await conn.fetch("""
                SELECT id, signal_id, features, outcome, created_at
                FROM experience_buffer
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)
            
            result = []
            for row in rows:
                try:
                    experience = {
                        'id': row['id'],
                        'signal_id': str(row['signal_id']) if row['signal_id'] else None,
                        'features': row['features'] if isinstance(row['features'], dict) else json.loads(row['features'] or '{}'),
                        'outcome': row['outcome'] if isinstance(row['outcome'], dict) else json.loads(row['outcome'] or '{}'),
                        'created_at': row['created_at']
                    }
                    result.append(experience)
                except Exception as e:
                    logger.debug(f"⚠️ 解析記錄失敗: {e}")
            
            logger.info(f"📖 從 PostgreSQL 讀取 {len(result)} 筆 experience")
            return result
        
        except Exception as e:
            logger.error(f"❌ 從數據庫讀取失敗: {e}", exc_info=True)
            return []
        
        finally:
            if conn:
                try:
                    await conn.close()
                except:
                    pass
    
    async def get_database_stats(self, db_url: str) -> Dict:
        """
        獲取 PostgreSQL experience_buffer 表的統計信息
        
        Args:
            db_url: Database connection URL
        
        Returns:
            Dictionary with statistics
        """
        conn = None
        try:
            conn = await asyncpg.connect(db_url)
            
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_records,
                    COUNT(CASE WHEN outcome IS NOT NULL THEN 1 END) as records_with_outcome,
                    COUNT(CASE WHEN features IS NOT NULL THEN 1 END) as records_with_features,
                    MAX(created_at) as latest_record,
                    MIN(created_at) as oldest_record
                FROM experience_buffer
            """)
            
            return dict(stats) if stats else {}
        
        except Exception as e:
            logger.error(f"❌ 獲取統計信息失敗: {e}", exc_info=True)
            return {}
        
        finally:
            if conn:
                try:
                    await conn.close()
                except:
                    pass
    
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
