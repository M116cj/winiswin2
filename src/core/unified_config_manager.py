"""
🔥 UnifiedConfigManager v1.0 - 统一配置管理器
职责：单一的真理来源，所有环境变量在此读取

这个类解决了原有的"多个真理"问题：
- 之前: Config.py + ConfigProfile.py （两个独立的os.getenv源）
- 现在: UnifiedConfigManager （单一配置入口）

所有代码应该从这个管理器读取配置，而不是直接访问Config或ConfigProfile。
"""

import os
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class UnifiedConfigManager:
    """
    🔥 统一配置管理器 v1.0
    
    所有环境变量读取统一通过此类，确保单一真理来源。
    
    分类：
    - Binance配置
    - 数据库配置
    - 功能开关
    - 交易参数
    - 风险参数
    - WebSocket配置
    - 技术指标参数
    """
    
    # 单例实例
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化统一配置管理器（仅执行一次）"""
        if UnifiedConfigManager._initialized:
            return
        
        logger.info("=" * 80)
        logger.info("✅ UnifiedConfigManager 初始化中...")
        logger.info("=" * 80)
        
        # ===== Binance API 配置 =====
        self.BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
        self.BINANCE_API_SECRET: str = (
            os.getenv("BINANCE_API_SECRET", "") or 
            os.getenv("BINANCE_SECRET_KEY", "")
        )
        self.BINANCE_TRADING_API_KEY: str = os.getenv("BINANCE_TRADING_API_KEY", "") or self.BINANCE_API_KEY
        self.BINANCE_TRADING_API_SECRET: str = os.getenv("BINANCE_TRADING_API_SECRET", "") or self.BINANCE_API_SECRET
        self.BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
        
        # ===== 数据库配置 =====
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "")
        self.DATABASE_PUBLIC_URL: str = os.getenv("DATABASE_PUBLIC_URL", "")
        self.REDIS_URL: str = os.getenv("REDIS_URL", "")
        
        # 数据库连接池配置
        self.DB_MIN_CONNECTIONS: int = int(os.getenv("DB_MIN_CONNECTIONS", "2"))
        self.DB_MAX_CONNECTIONS: int = int(os.getenv("DB_MAX_CONNECTIONS", "10"))
        self.DB_CONNECTION_TIMEOUT: int = int(os.getenv("DB_CONNECTION_TIMEOUT", "30"))
        self.DB_QUERY_TIMEOUT: int = int(os.getenv("DB_QUERY_TIMEOUT", "30"))
        self.DB_BATCH_SIZE: int = int(os.getenv("DB_BATCH_SIZE", "1000"))
        
        # ===== 功能开关 =====
        self.DISABLE_MODEL_TRAINING: bool = os.getenv("DISABLE_MODEL_TRAINING", "false").lower() == "true"
        self.WEBSOCKET_ONLY_KLINES: bool = os.getenv("WEBSOCKET_ONLY_KLINES", "true").lower() == "true"
        self.DISABLE_REST_FALLBACK: bool = os.getenv("DISABLE_REST_FALLBACK", "true").lower() == "true"
        self.ENABLE_KLINE_WARMUP: bool = os.getenv("ENABLE_KLINE_WARMUP", "false").lower() == "true"
        self.RELAXED_SIGNAL_MODE: bool = os.getenv("RELAXED_SIGNAL_MODE", "true").lower() == "true"
        
        # ===== 通知配置 =====
        self.DISCORD_TOKEN: str = (
            os.getenv("DISCORD_TOKEN", "") or 
            os.getenv("DISCORD_BOT_TOKEN", "")
        )
        self.DISCORD_CHANNEL_ID: Optional[str] = os.getenv("DISCORD_CHANNEL_ID")
        self.DISCORD_WEBHOOK_URL: Optional[str] = os.getenv("DISCORD_WEBHOOK_URL")
        self.TELEGRAM_TOKEN: Optional[str] = os.getenv("TELEGRAM_TOKEN")
        self.TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")
        
        # ===== 交易配置 =====
        self.MAX_CONCURRENT_ORDERS: int = int(os.getenv("MAX_CONCURRENT_ORDERS", "5"))
        self.CYCLE_INTERVAL: int = int(os.getenv("CYCLE_INTERVAL", "60"))
        self.TRADING_ENABLED: bool = os.getenv("TRADING_ENABLED", "true").lower() == "true"
        self.VIRTUAL_POSITION_CYCLE_INTERVAL: int = int(os.getenv("VIRTUAL_POSITION_CYCLE_INTERVAL", "10"))
        
        # ===== 风险参数 =====
        self.MIN_CONFIDENCE: float = float(os.getenv("MIN_CONFIDENCE", "0.40"))
        self.MIN_WIN_PROBABILITY: float = float(os.getenv("MIN_WIN_PROBABILITY", "0.45"))
        self.MIN_RR_RATIO: float = float(os.getenv("MIN_RR_RATIO", "0.8"))
        self.MAX_RR_RATIO: float = float(os.getenv("MAX_RR_RATIO", "5.0"))
        
        # ===== Bootstrap配置 =====
        self.BOOTSTRAP_TRADE_LIMIT: int = int(os.getenv("BOOTSTRAP_TRADE_LIMIT", "50"))
        self.BOOTSTRAP_MIN_WIN_PROBABILITY: float = float(os.getenv("BOOTSTRAP_MIN_WIN_PROBABILITY", "0.20"))
        self.BOOTSTRAP_MIN_CONFIDENCE: float = float(os.getenv("BOOTSTRAP_MIN_CONFIDENCE", "0.25"))
        
        # ===== WebSocket配置 =====
        self.WEBSOCKET_SYMBOL_LIMIT: int = int(os.getenv("WEBSOCKET_SYMBOL_LIMIT", "200"))
        self.WEBSOCKET_SHARD_SIZE: int = int(os.getenv("WEBSOCKET_SHARD_SIZE", "50"))
        self.WEBSOCKET_HEARTBEAT_TIMEOUT: int = int(os.getenv("WEBSOCKET_HEARTBEAT_TIMEOUT", "30"))
        
        # ===== 技术指标参数 =====
        self.EMA_FAST: int = 20
        self.EMA_SLOW: int = 50
        self.RSI_PERIOD: int = 14
        self.ADX_PERIOD: int = 14
        self.ADX_TREND_THRESHOLD: float = 20.0
        self.ADX_HARD_REJECT_THRESHOLD: float = float(os.getenv("ADX_HARD_REJECT_THRESHOLD", "5.0"))
        self.ADX_WEAK_TREND_THRESHOLD: float = float(os.getenv("ADX_WEAK_TREND_THRESHOLD", "10.0"))
        
        # ===== 时间框架 =====
        self.TIMEFRAMES: List[str] = ["1h", "15m", "5m"]
        
        UnifiedConfigManager._initialized = True
        logger.info("✅ UnifiedConfigManager 初始化完成")
    
    # ==================== 数据库URL方法 ====================
    
    def get_database_url(self) -> Optional[str]:
        """获取数据库URL（优先使用DATABASE_URL）"""
        return self.DATABASE_URL or self.DATABASE_PUBLIC_URL
    
    def is_database_configured(self) -> bool:
        """检查数据库是否已配置"""
        return bool(self.get_database_url())
    
    def is_redis_available(self) -> bool:
        """检查Redis是否可用"""
        return bool(self.REDIS_URL)
    
    # ==================== 验证方法 ====================
    
    def validate_critical_config(self) -> tuple[bool, List[str]]:
        """
        验证关键配置
        
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        if not self.BINANCE_API_KEY:
            errors.append("缺少 BINANCE_API_KEY")
        if not self.BINANCE_API_SECRET:
            errors.append("缺少 BINANCE_API_SECRET")
        if not self.get_database_url():
            errors.append("缺少 DATABASE_URL 或 DATABASE_PUBLIC_URL")
        
        return len(errors) == 0, errors
    
    # ==================== 单例访问 ====================
    
    @staticmethod
    def get_instance() -> 'UnifiedConfigManager':
        """获取单例实例"""
        return UnifiedConfigManager()


# 全局单例实例
config_manager = UnifiedConfigManager()
