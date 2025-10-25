"""
全局配置管理
職責：環境變量、常量定義、配置驗證
"""

import os
from typing import Optional
import logging

class Config:
    """系統配置管理類"""
    
    # Binance API 配置
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
    
    # Discord 配置
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    DISCORD_CHANNEL_ID: Optional[str] = os.getenv("DISCORD_CHANNEL_ID")
    
    # 交易配置
    MAX_POSITIONS: int = int(os.getenv("MAX_POSITIONS", "3"))
    CYCLE_INTERVAL: int = int(os.getenv("CYCLE_INTERVAL", "60"))
    TRADING_ENABLED: bool = os.getenv("TRADING_ENABLED", "false").lower() == "true"
    
    # 風險管理配置
    BASE_LEVERAGE: int = 3
    MAX_LEVERAGE: int = 20
    MIN_LEVERAGE: int = 3
    BASE_MARGIN_PCT: float = 0.10
    MIN_MARGIN_PCT: float = 0.03
    MAX_MARGIN_PCT: float = 0.13
    
    # 策略配置
    MIN_CONFIDENCE: float = 0.70
    MAX_SIGNALS: int = 10
    IMMEDIATE_EXECUTION_RANK: int = 3
    
    # 技術指標配置
    EMA_FAST: int = 50
    EMA_SLOW: int = 200
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70
    RSI_OVERSOLD: float = 30
    ATR_PERIOD: int = 14
    ATR_MULTIPLIER: float = 2.0
    RISK_REWARD_RATIO: float = 2.0
    
    # Order Blocks 配置
    OB_REJECTION_PCT: float = 0.03
    OB_VOLUME_MULTIPLIER: float = 1.5
    OB_LOOKBACK: int = 20
    
    # Liquidity Zones 配置
    LZ_LOOKBACK: int = 20
    LZ_STRENGTH_THRESHOLD: float = 0.5
    
    # 信心度評分權重
    CONFIDENCE_WEIGHTS = {
        "trend_alignment": 0.40,
        "market_structure": 0.20,
        "price_position": 0.20,
        "momentum": 0.10,
        "volatility": 0.10
    }
    
    # 勝率門檻（用於槓桿調整）
    WINRATE_THRESHOLDS = {
        "good": 0.60,
        "great": 0.70,
        "excellent": 0.80
    }
    
    # API 限流配置
    RATE_LIMIT_REQUESTS: int = 1200
    RATE_LIMIT_PERIOD: int = 60
    
    # 緩存配置
    CACHE_TTL_KLINES: int = 30
    CACHE_TTL_TICKER: int = 5
    CACHE_TTL_ACCOUNT: int = 10
    
    # 熔斷器配置
    CIRCUIT_BREAKER_THRESHOLD: int = 5
    CIRCUIT_BREAKER_TIMEOUT: int = 60
    
    # 批量處理配置
    BATCH_SIZE: int = 50
    
    # 虛擬倉位配置
    VIRTUAL_POSITION_EXPIRY: int = 96
    
    # ML 數據收集配置
    ML_FLUSH_COUNT: int = 25
    ML_FLUSH_INTERVAL: int = 300
    
    # 日誌配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = "data/logs/trading_bot.log"
    
    # 數據文件路徑
    DATA_DIR: str = "data"
    TRADES_FILE: str = f"{DATA_DIR}/trades.json"
    ML_PENDING_FILE: str = f"{DATA_DIR}/ml_pending_entries.json"
    VIRTUAL_POSITIONS_FILE: str = f"{DATA_DIR}/virtual_positions.json"
    
    @classmethod
    def validate(cls) -> tuple[bool, list[str]]:
        """
        驗證配置完整性
        
        Returns:
            tuple[bool, list[str]]: (是否有效, 錯誤消息列表)
        """
        errors = []
        
        if not cls.BINANCE_API_KEY:
            errors.append("缺少 BINANCE_API_KEY 環境變量")
        
        if not cls.BINANCE_API_SECRET:
            errors.append("缺少 BINANCE_API_SECRET 環境變量")
        
        if not cls.DISCORD_TOKEN:
            errors.append("缺少 DISCORD_TOKEN 環境變量（通知系統需要）")
        
        if cls.MAX_POSITIONS < 1 or cls.MAX_POSITIONS > 10:
            errors.append(f"MAX_POSITIONS 必須在 1-10 之間，當前為 {cls.MAX_POSITIONS}")
        
        if cls.MIN_CONFIDENCE < 0 or cls.MIN_CONFIDENCE > 1:
            errors.append(f"MIN_CONFIDENCE 必須在 0-1 之間，當前為 {cls.MIN_CONFIDENCE}")
        
        return len(errors) == 0, errors
    
    @classmethod
    def setup_logging(cls):
        """設置日誌系統"""
        os.makedirs(os.path.dirname(cls.LOG_FILE), exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, cls.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(cls.LOG_FILE),
                logging.StreamHandler()
            ]
        )
    
    @classmethod
    def get_summary(cls) -> dict:
        """獲取配置摘要"""
        return {
            "binance_testnet": cls.BINANCE_TESTNET,
            "trading_enabled": cls.TRADING_ENABLED,
            "max_positions": cls.MAX_POSITIONS,
            "cycle_interval": cls.CYCLE_INTERVAL,
            "leverage_range": f"{cls.MIN_LEVERAGE}x - {cls.MAX_LEVERAGE}x",
            "margin_range": f"{cls.MIN_MARGIN_PCT*100}% - {cls.MAX_MARGIN_PCT*100}%",
            "min_confidence": f"{cls.MIN_CONFIDENCE*100}%",
            "log_level": cls.LOG_LEVEL
        }
