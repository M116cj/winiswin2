"""
🔥 Railway PostgreSQL Database Module v5.0+
完整的数据库连接和管理系统（统一管理器）

Phase 3+: 迁移到 UnifiedDatabaseManager (asyncpg + Redis)
"""

from .unified_database_manager import UnifiedDatabaseManager

__all__ = [
    'UnifiedDatabaseManager',
]
