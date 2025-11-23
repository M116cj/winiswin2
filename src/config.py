"""
⚙️ Configuration - Runtime environment variables
"""

import os


class Config:
    """Environment configuration"""
    
    @staticmethod
    def get(key: str, default: str = "") -> str:
        return os.getenv(key, default)
    
    # Trading
    MAX_OPEN_POSITIONS = 3  # Elite rotation: max 3 concurrent positions


def get_redis_url() -> str:
    """
    Get Redis connection URL
    For production: Use external Redis service (Railway, Redis Cloud, etc.)
    For development: Use local Redis at localhost:6379
    """
    # Try environment variable first (for deployed services)
    if redis_url := os.getenv('REDIS_URL'):
        return redis_url
    
    # Fallback to localhost for development
    return "redis://localhost:6379"


def get_database_url() -> str:
    """
    Get Postgres connection URL
    Uses DATABASE_URL environment variable (from Replit Postgres setup)
    """
    if database_url := os.getenv('DATABASE_URL'):
        return database_url
    
    # Fallback to local Postgres for development
    return "postgresql://localhost/aegis"
