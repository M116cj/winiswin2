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
    
    # Validate API credentials (fail fast if misconfigured)
    @staticmethod
    def validate_binance_keys():
        """Validate Binance API keys are properly configured"""
        if not Config.BINANCE_API_KEY or not Config.BINANCE_API_SECRET:
            raise ValueError(
                "❌ Binance API credentials not configured!\n"
                "Set environment variables:\n"
                "  BINANCE_API_KEY=your_key\n"
                "  BINANCE_API_SECRET=your_secret"
            )
    
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
