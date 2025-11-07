"""
Database Configuration
数据库配置管理
"""

import os
from typing import Optional


class DatabaseConfig:
    """数据库配置类"""
    
    # 连接池配置
    MIN_CONNECTIONS: int = 1
    MAX_CONNECTIONS: int = 20
    CONNECTION_TIMEOUT: int = 30  # 秒
    
    # 重试配置
    AUTO_RETRY: bool = True
    MAX_RETRIES: int = 3
    
    # 查询配置
    QUERY_TIMEOUT: int = 30  # 秒
    
    # 批量操作配置
    BATCH_SIZE: int = 1000
    
    @staticmethod
    def get_database_url() -> Optional[str]:
        """
        获取数据库URL
        
        Returns:
            数据库连接URL，优先使用内部URL
        """
        # 优先使用Railway内部URL（更快）
        return os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_PUBLIC_URL')
    
    @staticmethod
    def is_database_configured() -> bool:
        """
        检查数据库是否已配置
        
        Returns:
            True if configured, False otherwise
        """
        return DatabaseConfig.get_database_url() is not None
