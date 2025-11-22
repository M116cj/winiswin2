"""
⚙️ Unified Configuration Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Single source of truth for environment variables and configuration.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class UnifiedConfig:
    """
    Environment variable configuration with sensible defaults
    """
    
    @staticmethod
    def get_binance_api_key() -> str:
        """Get Binance API key from env"""
        return os.getenv('BINANCE_API_KEY', '')
    
    @staticmethod
    def get_binance_api_secret() -> str:
        """Get Binance API secret from env"""
        return os.getenv('BINANCE_API_SECRET', '')
    
    @staticmethod
    def get_database_url() -> str:
        """Get PostgreSQL connection URL"""
        return os.getenv('DATABASE_URL', 'postgresql://localhost/slt')
    
    @staticmethod
    def get_redis_url() -> str:
        """Get Redis connection URL"""
        return os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    @staticmethod
    def get_rate_limit_requests() -> int:
        """Get rate limit for API requests"""
        return int(os.getenv('RATE_LIMIT_REQUESTS', '1200'))
    
    @staticmethod
    def get_log_level() -> str:
        """Get logging level"""
        return os.getenv('LOG_LEVEL', 'INFO')
    
    @staticmethod
    def is_production() -> bool:
        """Check if running in production"""
        return os.getenv('ENVIRONMENT', 'development') == 'production'
    
    @staticmethod
    def is_paper_trading() -> bool:
        """Check if paper trading enabled"""
        return os.getenv('PAPER_TRADING', 'false').lower() == 'true'
