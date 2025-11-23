"""
🗄️ Unified Database Manager - Auto-Migration & Schema Management
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Manages database schema initialization and migrations.
Ensures all required tables exist on startup.
"""

import logging
import asyncpg
from typing import Optional
from src.config import get_database_url

logger = logging.getLogger(__name__)


class UnifiedDatabaseManager:
    """
    Centralized database schema management
    
    Handles:
    - Table creation with CREATE TABLE IF NOT EXISTS
    - Index creation for performance
    - Schema validation
    - Connection pooling
    """
    
    _instance: Optional['UnifiedDatabaseManager'] = None
    _connection_pool: Optional[asyncpg.Pool] = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @staticmethod
    async def get_connection() -> Optional[asyncpg.connection.Connection]:
        """Get a single database connection"""
        try:
            db_url = get_database_url()
            conn = await asyncpg.connect(db_url)
            return conn
        except Exception as e:
            logger.warning(f"⚠️ Failed to get database connection: {e}")
            return None
    
    @staticmethod
    async def init_schema() -> bool:
        """
        Initialize database schema on startup
        
        Creates all required tables if they don't exist.
        Includes indexes for performance optimization.
        
        Returns:
            True if successful, False otherwise
        """
        conn = None
        try:
            conn = await UnifiedDatabaseManager.get_connection()
            if not conn:
                logger.warning("⚠️ Could not connect to database for schema initialization")
                return False
            
            logger.info("🔧 Initializing database schema...")
            
            # Create account_state table
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
            logger.debug("✅ account_state table ready")
            
            # Create index for fast retrieval of latest state
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_account_state_time 
                ON account_state(updated_at DESC)
            """)
            logger.debug("✅ account_state index created")
            
            # Create signals table (if not exists)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    symbol VARCHAR(20) NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    patterns JSONB,
                    position_size DOUBLE PRECISION,
                    timestamp BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.debug("✅ signals table ready")
            
            # Create index on signals
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_symbol_timestamp 
                ON signals(symbol, timestamp DESC)
            """)
            logger.debug("✅ signals index created")
            
            # Create trades table (if not exists)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    direction VARCHAR(10) NOT NULL,
                    entry_price NUMERIC(20, 8) NOT NULL,
                    exit_price NUMERIC(20, 8),
                    quantity NUMERIC(20, 8) NOT NULL,
                    leverage INTEGER DEFAULT 1,
                    pnl NUMERIC(20, 8),
                    pnl_percent NUMERIC(10, 2),
                    win BOOLEAN,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    features JSONB,
                    exit_reason VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    signal_id UUID REFERENCES signals(id) ON DELETE SET NULL
                )
            """)
            logger.debug("✅ trades table ready")
            
            # Create indexes on trades
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_signal_id 
                ON trades(signal_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_symbol 
                ON trades(symbol)
            """)
            logger.debug("✅ trades indexes created")
            
            # Create experience_buffer table (if not exists)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS experience_buffer (
                    id SERIAL PRIMARY KEY,
                    signal_id UUID REFERENCES signals(id) ON DELETE CASCADE,
                    features JSONB NOT NULL,
                    outcome JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.debug("✅ experience_buffer table ready")
            
            # Create index on experience_buffer
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_experience_signal 
                ON experience_buffer(signal_id)
            """)
            logger.debug("✅ experience_buffer index created")
            
            # Create position_entry_times table (if not exists)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS position_entry_times (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    entry_time TIMESTAMP NOT NULL,
                    entry_price NUMERIC(20, 8) NOT NULL,
                    quantity NUMERIC(20, 8) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.debug("✅ position_entry_times table ready")
            
            await conn.close()
            
            logger.critical("✅ Database schema initialized successfully")
            return True
        
        except asyncpg.PostgresError as e:
            logger.error(f"❌ PostgreSQL error during schema initialization: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error initializing database schema: {e}", exc_info=True)
            return False
        finally:
            if conn:
                try:
                    await conn.close()
                except:
                    pass
