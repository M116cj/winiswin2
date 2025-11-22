"""
⚙️ Configuration - Runtime environment variables
"""

import os


class Config:
    """Environment configuration"""
    
    @staticmethod
    def get(key: str, default: str = "") -> str:
        return os.getenv(key, default)
    
    # Binance API
    BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
    BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/slt')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    # Trading
    MAX_LEVERAGE_TEACHER = 3.0
    MAX_LEVERAGE_STUDENT = 10.0
    TEACHER_THRESHOLD = 50
    MAX_OPEN_POSITIONS = 3  # Elite rotation: max 3 concurrent positions
    
    # Indicators
    ATR_PERIOD = 14
    RSI_PERIOD = 14
    
    # System
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
