"""
🔥 Railway PostgreSQL Database Module v5.0+
完整的数据库连接和管理系统（统一管理器）

Phase 3+: 迁移到 UnifiedDatabaseManager (asyncpg + Redis)
"""

from .async_manager import AsyncDatabaseManager, initialize_global_instance, close_global_instance
from .service import TradingDataService
from .initializer import initialize_database
from .config import DatabaseConfig
from .monitor import DatabaseMonitor
from .unified_database_manager import UnifiedDatabaseManager, database_manager

__all__ = [
    # 旧API（后向兼容）
    'AsyncDatabaseManager',
    'initialize_global_instance',
    'close_global_instance',
    
    # 新API（统一管理器）
    'UnifiedDatabaseManager',
    'database_manager',
    
    # 服务
    'TradingDataService',
    'initialize_database',
    'DatabaseConfig',
    'DatabaseMonitor',
]
