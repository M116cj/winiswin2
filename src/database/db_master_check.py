"""
🎯 DB Master Check - Carpet Bombing Diagnostic Suite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Comprehensive database health verification:
- PostgreSQL schema enforcer
- Redis functional testing
- Data bridge verification
- Latency measurements
"""

import logging
import asyncio
import time
from typing import Dict, List, Tuple
import json

logger = logging.getLogger(__name__)


class DBMasterCheck:
    """
    Comprehensive database diagnostic suite
    
    Performs:
    1. PostgreSQL schema validation + auto-creation
    2. Redis connectivity and serialization tests
    3. Data bridge verification (Redis + Postgres dual writes)
    4. Latency measurements
    """
    
    def __init__(self):
        self.results: Dict[str, Dict] = {}
        self.health_matrix: List[List[str]] = []
    
    # ============================================================================
    # PHASE 1: PostgreSQL Schema Enforcer
    # ============================================================================
    
    async def check_postgres(self) -> bool:
        """
        PostgreSQL Schema Enforcer
        
        1. Connect to PostgreSQL
        2. Check if account_state and trade_history tables exist
        3. Auto-create if missing
        4. Functional test: insert → read → delete
        """
        try:
            import asyncpg
            from src.config import get_database_url
            
            db_url = get_database_url()
            
            # Step 1: Connection Test
            logger.info("🔍 PostgreSQL: Testing connection...")
            start_time = time.time()
            conn = await asyncpg.connect(db_url)
            connection_latency = (time.time() - start_time) * 1000  # ms
            logger.info(f"✅ PostgreSQL: Connected in {connection_latency:.2f}ms")
            
            self.results['postgres_connection'] = {
                'status': '✅',
                'latency': f"{connection_latency:.2f}ms"
            }
            
            # Step 2: Check and create account_state table
            logger.info("🔍 PostgreSQL: Checking account_state table...")
            account_state_exists = await self._check_table(conn, 'account_state')
            
            if not account_state_exists:
                logger.warning("⚠️ PostgreSQL: account_state table missing - creating...")
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS account_state (
                        id SERIAL PRIMARY KEY,
                        balance DOUBLE PRECISION NOT NULL DEFAULT 10000.0,
                        pnl DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                        trade_count INTEGER NOT NULL DEFAULT 0,
                        positions JSONB NOT NULL DEFAULT '{}',
                        last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.critical("✅ PostgreSQL: account_state table created")
                self.results['postgres_account_state'] = {
                    'status': '✅',
                    'note': 'Created'
                }
            else:
                logger.info("✅ PostgreSQL: account_state table exists")
                self.results['postgres_account_state'] = {
                    'status': '✅',
                    'note': 'Exists'
                }
            
            # Step 3: Check and create trade_history table
            logger.info("🔍 PostgreSQL: Checking trade_history table...")
            trade_history_exists = await self._check_table(conn, 'trade_history')
            
            if not trade_history_exists:
                logger.warning("⚠️ PostgreSQL: trade_history table missing - creating...")
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS trade_history (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        side VARCHAR(10) NOT NULL,
                        price NUMERIC(20, 8) NOT NULL,
                        quantity NUMERIC(20, 8) NOT NULL,
                        pnl NUMERIC(20, 8),
                        strategy_score DOUBLE PRECISION,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.critical("✅ PostgreSQL: trade_history table created")
                self.results['postgres_trade_history'] = {
                    'status': '✅',
                    'note': 'Created'
                }
            else:
                logger.info("✅ PostgreSQL: trade_history table exists")
                self.results['postgres_trade_history'] = {
                    'status': '✅',
                    'note': 'Exists'
                }
            
            # Step 4: Functional Test - Insert → Read → Delete
            logger.info("🔍 PostgreSQL: Running functional test...")
            test_passed = await self._postgres_functional_test(conn)
            
            if test_passed:
                logger.critical("✅ PostgreSQL: Functional test passed (Insert/Select/Delete OK)")
                self.results['postgres_write_test'] = {
                    'status': '✅',
                    'note': 'Insert/Select/Delete OK'
                }
            else:
                logger.error("❌ PostgreSQL: Functional test failed")
                self.results['postgres_write_test'] = {
                    'status': '❌',
                    'note': 'Test failed'
                }
            
            await conn.close()
            return True
        
        except Exception as e:
            logger.error(f"❌ PostgreSQL: {e}", exc_info=True)
            self.results['postgres_connection'] = {
                'status': '❌',
                'error': str(e)
            }
            return False
    
    async def _check_table(self, conn, table_name: str) -> bool:
        """Check if table exists in PostgreSQL"""
        result = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = $1
            )
        """, table_name)
        return result
    
    async def _postgres_functional_test(self, conn) -> bool:
        """Test insert → read → delete on account_state"""
        try:
            # Insert
            test_balance = 9999.99
            test_pnl = 50.00
            await conn.execute(
                "INSERT INTO account_state (balance, pnl, trade_count, positions) VALUES ($1, $2, $3, $4::jsonb)",
                test_balance, test_pnl, 1, '{}'
            )
            
            # Read
            row = await conn.fetchrow(
                "SELECT balance, pnl FROM account_state WHERE balance = $1 LIMIT 1",
                test_balance
            )
            
            if not row or row['balance'] != test_balance:
                return False
            
            # Delete (cleanup)
            await conn.execute(
                "DELETE FROM account_state WHERE balance = $1",
                test_balance
            )
            
            return True
        except Exception as e:
            logger.error(f"Functional test error: {e}")
            return False
    
    # ============================================================================
    # PHASE 2: Redis Functional Test
    # ============================================================================
    
    async def check_redis(self) -> bool:
        """
        Redis Functional Test
        
        1. Connect to Redis
        2. Measure PING latency
        3. Test orjson serialization
        4. Write and read back test data
        """
        try:
            import redis.asyncio as redis_async
            from src.config import get_redis_url
            
            redis_url = get_redis_url()
            
            # Step 1: Connection Test
            logger.info("🔍 Redis: Testing connection...")
            start_time = time.time()
            redis_client = await redis_async.from_url(redis_url, decode_responses=False)
            
            # PING test
            ping_start = time.time()
            await redis_client.ping()
            ping_latency = (time.time() - ping_start) * 1000  # ms
            
            logger.info(f"✅ Redis: Connected and PING OK ({ping_latency:.2f}ms)")
            self.results['redis_connection'] = {
                'status': '✅',
                'latency': f"{ping_latency:.2f}ms"
            }
            
            # Step 2: Serialization Test with orjson
            logger.info("🔍 Redis: Testing orjson serialization...")
            try:
                import orjson
                HAS_ORJSON = True
            except ImportError:
                HAS_ORJSON = False
                logger.warning("⚠️ Redis: orjson not available, using json fallback")
            
            test_data = {'test': 123, 'key': 'value', 'array': [1, 2, 3]}
            
            if HAS_ORJSON:
                # Serialize with orjson
                encoded = orjson.dumps(test_data)
                
                # Write to Redis
                await redis_client.setex("system:test_integrity", 60, encoded)
                
                # Read back
                retrieved = await redis_client.get("system:test_integrity")
                
                # Deserialize
                decoded = orjson.loads(retrieved)
                
                if decoded == test_data:
                    logger.critical("✅ Redis: orjson serialization OK (data matches)")
                    self.results['redis_serialization'] = {
                        'status': '✅',
                        'note': 'orjson verified'
                    }
                else:
                    logger.error("❌ Redis: Data mismatch after serialization")
                    self.results['redis_serialization'] = {
                        'status': '❌',
                        'note': 'Data mismatch'
                    }
            else:
                # Fallback to json
                encoded = json.dumps(test_data).encode('utf-8')
                await redis_client.setex("system:test_integrity", 60, encoded)
                retrieved = await redis_client.get("system:test_integrity")
                decoded = json.loads(retrieved.decode('utf-8'))
                
                if decoded == test_data:
                    logger.critical("✅ Redis: json serialization OK (data matches)")
                    self.results['redis_serialization'] = {
                        'status': '✅',
                        'note': 'json fallback verified'
                    }
                else:
                    self.results['redis_serialization'] = {
                        'status': '❌',
                        'note': 'Data mismatch'
                    }
            
            await redis_client.close()
            return True
        
        except Exception as e:
            logger.error(f"❌ Redis: {e}", exc_info=True)
            self.results['redis_connection'] = {
                'status': '❌',
                'error': str(e)
            }
            return False
    
    # ============================================================================
    # PHASE 3: Data Bridge Verification
    # ============================================================================
    
    async def check_data_bridge(self) -> bool:
        """
        Data Bridge Verification
        
        Scan src/trade.py to verify dual persistence:
        1. Check for _sync_state_to_postgres()
        2. Check for _sync_state_to_redis()
        3. Flag if only writes to one layer
        """
        try:
            logger.info("🔍 Data Bridge: Verifying dual persistence...")
            
            with open('src/trade.py', 'r') as f:
                trade_code = f.read()
            
            has_postgres_sync = '_sync_state_to_postgres' in trade_code
            has_redis_sync = '_sync_state_to_redis' in trade_code
            has_update_state = '_update_state' in trade_code
            
            # Check if both sync functions are called in _update_state
            if '_update_state' in trade_code:
                update_state_section = trade_code[trade_code.find('async def _update_state'):trade_code.find('async def _update_state') + 2000]
                calls_postgres = 'await _sync_state_to_postgres()' in update_state_section or '_sync_state_to_postgres' in update_state_section
                calls_redis = 'await _sync_state_to_redis()' in update_state_section or '_sync_state_to_redis' in update_state_section
            else:
                calls_postgres = False
                calls_redis = False
            
            if has_postgres_sync and has_redis_sync and calls_postgres and calls_redis:
                logger.critical("✅ Data Bridge: Dual persistence confirmed (Redis + Postgres)")
                self.results['data_bridge_postgres'] = {
                    'status': '✅',
                    'note': 'Writes enabled'
                }
                self.results['data_bridge_redis'] = {
                    'status': '✅',
                    'note': 'Writes enabled'
                }
                return True
            elif has_postgres_sync and calls_postgres:
                logger.warning("⚠️ Data Bridge: Only Postgres write detected (Redis optional)")
                self.results['data_bridge_postgres'] = {
                    'status': '✅',
                    'note': 'Writes enabled'
                }
                self.results['data_bridge_redis'] = {
                    'status': '⚠️',
                    'note': 'Writes optional'
                }
                return True
            else:
                logger.error("❌ Data Bridge: Dual persistence NOT found")
                self.results['data_bridge'] = {
                    'status': '❌',
                    'note': 'PARTIAL DATA LOSS RISK'
                }
                return False
        
        except Exception as e:
            logger.error(f"❌ Data Bridge: {e}", exc_info=True)
            self.results['data_bridge'] = {
                'status': '❌',
                'error': str(e)
            }
            return False
    
    # ============================================================================
    # Reporting
    # ============================================================================
    
    def generate_health_matrix(self) -> str:
        """Generate DB Health Matrix table"""
        matrix = [
            "╔════════════════════════════════════════════════════════════════════════╗",
            "║              🎯 DB Master Check - Health Matrix                        ║",
            "╚════════════════════════════════════════════════════════════════════════╝",
            "",
            "| Component          | Check                      | Status | Note          |",
            "|:-------------------|:---------------------------|:-------|:--------------|",
        ]
        
        # PostgreSQL section
        if 'postgres_connection' in self.results:
            status = self.results['postgres_connection']['status']
            latency = self.results['postgres_connection'].get('latency', 'N/A')
            matrix.append(f"| **PostgreSQL**     | Connection                 | {status}     | {latency}       |")
        
        if 'postgres_account_state' in self.results:
            status = self.results['postgres_account_state']['status']
            note = self.results['postgres_account_state'].get('note', 'N/A')
            matrix.append(f"| **PostgreSQL**     | Schema (account_state)     | {status}     | {note}       |")
        
        if 'postgres_trade_history' in self.results:
            status = self.results['postgres_trade_history']['status']
            note = self.results['postgres_trade_history'].get('note', 'N/A')
            matrix.append(f"| **PostgreSQL**     | Schema (trade_history)     | {status}     | {note}       |")
        
        if 'postgres_write_test' in self.results:
            status = self.results['postgres_write_test']['status']
            note = self.results['postgres_write_test'].get('note', 'N/A')
            matrix.append(f"| **PostgreSQL**     | Write Test                 | {status}     | {note}       |")
        
        # Redis section
        if 'redis_connection' in self.results:
            status = self.results['redis_connection']['status']
            latency = self.results['redis_connection'].get('latency', 'N/A')
            matrix.append(f"| **Redis**          | Connection & PING          | {status}     | {latency}       |")
        
        if 'redis_serialization' in self.results:
            status = self.results['redis_serialization']['status']
            note = self.results['redis_serialization'].get('note', 'N/A')
            matrix.append(f"| **Redis**          | Serialization              | {status}     | {note}       |")
        
        # Data Bridge section
        if 'data_bridge_postgres' in self.results:
            status = self.results['data_bridge_postgres']['status']
            note = self.results['data_bridge_postgres'].get('note', 'N/A')
            matrix.append(f"| **Data Bridge**    | Postgres Writes            | {status}     | {note}       |")
        
        if 'data_bridge_redis' in self.results:
            status = self.results['data_bridge_redis']['status']
            note = self.results['data_bridge_redis'].get('note', 'N/A')
            matrix.append(f"| **Data Bridge**    | Redis Writes               | {status}     | {note}       |")
        
        return "\n".join(matrix)


async def run_db_master_check():
    """Execute the complete diagnostic suite"""
    
    checker = DBMasterCheck()
    
    logger.critical("🚀 Starting DB Master Check - Carpet Bombing Diagnostics...")
    logger.critical("━" * 75)
    
    # Phase 1: PostgreSQL
    logger.critical("📊 PHASE 1: PostgreSQL Schema Enforcer")
    postgres_ok = await checker.check_postgres()
    logger.critical("✅ PostgreSQL check complete\n")
    
    # Phase 2: Redis
    logger.critical("📊 PHASE 2: Redis Functional Test")
    redis_ok = await checker.check_redis()
    logger.critical("✅ Redis check complete\n")
    
    # Phase 3: Data Bridge
    logger.critical("📊 PHASE 3: Data Bridge Verification")
    bridge_ok = await checker.check_data_bridge()
    logger.critical("✅ Data bridge check complete\n")
    
    # Generate and display health matrix
    logger.critical("━" * 75)
    health_report = checker.generate_health_matrix()
    logger.critical(health_report)
    logger.critical("━" * 75)
    
    # Final verdict
    all_ok = postgres_ok and redis_ok and bridge_ok
    if all_ok:
        logger.critical("🟢 ALL SYSTEMS GO - Database infrastructure is healthy")
    else:
        logger.critical("🔴 WARNINGS DETECTED - Review the health matrix above")
    
    return all_ok


if __name__ == '__main__':
    # For standalone execution
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(run_db_master_check())
