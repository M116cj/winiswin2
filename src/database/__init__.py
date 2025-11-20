"""
Railway PostgreSQL Database Module
完整的数据库连接和管理系统

Phase 3: Migrated to AsyncDatabaseManager (asyncpg)
"""

from .async_manager import AsyncDatabaseManager, initialize_global_instance, close_global_instance
from .service import TradingDataService
from .initializer import initialize_database
from .config import DatabaseConfig
from .monitor import DatabaseMonitor

__all__ = [
    'AsyncDatabaseManager',
    'initialize_global_instance',
    'close_global_instance',
    'TradingDataService',
    'initialize_database',
    'DatabaseConfig',
    'DatabaseMonitor',
]
