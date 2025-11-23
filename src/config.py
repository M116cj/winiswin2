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
