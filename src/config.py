"""
v3.17+ 精簡配置管理
職責：環境變量、常量定義、配置驗證（移除所有固定槓桿參數）
"""

import os
import sys
from typing import Optional
import logging

class Config:
    """系統配置管理類（v3.17+ 精簡版）"""
    
    # ===== Binance API 配置 =====
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = (
        os.getenv("BINANCE_API_SECRET", "") or 
        os.getenv("BINANCE_SECRET_KEY", "")
    )
    BINANCE_TRADING_API_KEY: str = os.getenv("BINANCE_TRADING_API_KEY", "") or BINANCE_API_KEY
    BINANCE_TRADING_API_SECRET: str = os.getenv("BINANCE_TRADING_API_SECRET", "") or BINANCE_API_SECRET
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
    
    # ===== Discord 配置（可選）=====
    DISCORD_TOKEN: str = (
        os.getenv("DISCORD_TOKEN", "") or 
        os.getenv("DISCORD_BOT_TOKEN", "")
    )
    DISCORD_CHANNEL_ID: Optional[str] = os.getenv("DISCORD_CHANNEL_ID")
    
    # ===== 交易配置 =====
    MAX_POSITIONS: int = int(os.getenv("MAX_POSITIONS", "999"))
    CYCLE_INTERVAL: int = int(os.getenv("CYCLE_INTERVAL", "60"))
    TRADING_ENABLED: bool = os.getenv("TRADING_ENABLED", "true").lower() == "true"
    VIRTUAL_POSITION_CYCLE_INTERVAL: int = int(os.getenv("VIRTUAL_POSITION_CYCLE_INTERVAL", "10"))
    
    # ===== v3.17+ 核心策略配置 =====
    MIN_CONFIDENCE: float = float(os.getenv("MIN_CONFIDENCE", "0.50"))
    MAX_SIGNALS: int = 10
    IMMEDIATE_EXECUTION_RANK: int = 3
    
    # ===== v3.17+ SelfLearningTrader 開倉條件 =====
    MIN_WIN_PROBABILITY: float = float(os.getenv("MIN_WIN_PROBABILITY", "0.55"))
    MIN_RR_RATIO: float = float(os.getenv("MIN_RR_RATIO", "1.0"))
    MAX_RR_RATIO: float = float(os.getenv("MAX_RR_RATIO", "2.0"))
    
    # ===== 掃描配置（監控所有 U 本位合約）=====
    SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL", "60"))
    TOP_VOLATILITY_SYMBOLS: int = int(os.getenv("TOP_LIQUIDITY_SYMBOLS", "999"))
    
    # ===== 技術指標配置 =====
    EMA_FAST: int = 20
    EMA_SLOW: int = 50
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70
    RSI_OVERSOLD: float = 30
    ATR_PERIOD: int = 14
    ATR_MULTIPLIER: float = 2.0
    RISK_REWARD_RATIO: float = 2.0
    
    # ADX 趨勢過濾器
    ADX_PERIOD: int = 14
    ADX_TREND_THRESHOLD: float = 20.0
    ADX_STRONG_TREND: float = 25.0
    EMA_SLOPE_THRESHOLD: float = 0.01
    
    # Order Blocks 配置
    OB_REJECTION_PCT: float = 0.03
    OB_VOLUME_MULTIPLIER: float = 1.5
    OB_LOOKBACK: int = 20
    OB_MIN_VOLUME_RATIO: float = 1.5
    OB_REJECTION_THRESHOLD: float = 0.005
    OB_MAX_TEST_COUNT: int = 3
    OB_MAX_HISTORY: int = 20
    OB_DECAY_ENABLED: bool = True
    OB_TIME_DECAY_HOURS: int = 48
    OB_DECAY_RATE: float = 0.1
    
    # ===== 訂單配置 =====
    MAX_SLIPPAGE_PCT: float = 0.002
    ORDER_TIMEOUT_SECONDS: int = 30
    USE_LIMIT_ORDERS: bool = True
    AUTO_ORDER_TYPE: bool = True
    
    # Liquidity Zones 配置
    LZ_LOOKBACK: int = 20
    LZ_STRENGTH_THRESHOLD: float = 0.5
    
    # ===== 信心度評分權重 =====
    CONFIDENCE_WEIGHTS = {
        "trend_alignment": 0.40,
        "market_structure": 0.20,
        "price_position": 0.20,
        "momentum": 0.10,
        "volatility": 0.10
    }
    
    # ===== 勝率門檻（用於 v3.17+ 槓桿計算）=====
    WINRATE_THRESHOLDS = {
        "good": 0.60,
        "great": 0.70,
        "excellent": 0.80
    }
    
    # ===== API 限流配置 =====
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "1920"))
    RATE_LIMIT_PERIOD: int = 60
    
    # ===== 緩存配置 =====
    CACHE_TTL_KLINES_1H: int = 3600
    CACHE_TTL_KLINES_15M: int = 900
    CACHE_TTL_KLINES_5M: int = 300
    CACHE_TTL_KLINES_DEFAULT: int = 300
    CACHE_TTL_TICKER: int = 5
    CACHE_TTL_ACCOUNT: int = 10
    CACHE_TTL_KLINES_HISTORICAL: int = 86400
    INDICATOR_CACHE_TTL: int = 60
    
    # ===== 熔斷器配置 =====
    CIRCUIT_BREAKER_THRESHOLD: int = 5
    CIRCUIT_BREAKER_TIMEOUT: int = 60
    GRADED_CIRCUIT_BREAKER_ENABLED: bool = True
    CIRCUIT_BREAKER_WARNING_THRESHOLD: int = 2
    CIRCUIT_BREAKER_THROTTLED_THRESHOLD: int = 4
    CIRCUIT_BREAKER_BLOCKED_THRESHOLD: int = 5
    CIRCUIT_BREAKER_THROTTLE_DELAY: float = 2.0
    
    CIRCUIT_BREAKER_BYPASS_OPERATIONS: list = [
        "close_position",
        "emergency_stop_loss",
        "adjust_stop_loss",
        "adjust_take_profit",
        "get_positions",
        "cancel_order"
    ]
    
    # ===== 訂單執行配置 =====
    ORDER_INTER_DELAY: float = 1.5
    ORDER_RETRY_MAX_ATTEMPTS: int = 5
    ORDER_RETRY_BASE_DELAY: float = 1.0
    ORDER_RETRY_MAX_DELAY: float = 30.0
    PROTECTION_GUARDIAN_INTERVAL: int = 30
    PROTECTION_GUARDIAN_MAX_ATTEMPTS: int = 10
    
    # ===== 批量處理配置 =====
    BATCH_SIZE: int = 50
    
    # ===== 虛擬倉位配置 =====
    VIRTUAL_POSITION_EXPIRY: int = 96
    
    # ===== ML 數據收集配置 =====
    ML_FLUSH_COUNT: int = 25
    ML_FLUSH_INTERVAL: int = 300
    ML_DATA_DIR: str = "ml_data"
    ML_MIN_TRAINING_SAMPLES: int = 100
    
    # ===== 市場狀態規則 =====
    MARKET_STATE_RULES = {
        "strong_trending": {
            "adx_min": 25.0,
            "bb_width_quantile": 0.6,
            "volatility_min": 0.015,
            "allowed": True,
            "risk_multiplier": 1.2,
            "description": "強趨勢市場"
        },
        "trending": {
            "adx_min": 20.0,
            "adx_max": 25.0,
            "bb_width_quantile": 0.4,
            "allowed": True,
            "risk_multiplier": 1.0,
            "description": "正常趨勢市場"
        },
        "ranging": {
            "adx_max": 20.0,
            "bb_width_quantile": 0.3,
            "volatility_max": 0.01,
            "allowed": False,
            "risk_multiplier": 0.0,
            "description": "震盪市場（禁止交易）"
        },
        "choppy": {
            "adx_max": 15.0,
            "volatility_max": 0.005,
            "allowed": False,
            "risk_multiplier": 0.0,
            "description": "混亂市場（禁止交易）"
        }
    }
    
    # ===== 期望值計算配置 =====
    EXPECTANCY_WINDOW: int = 30
    MIN_EXPECTANCY_PCT: float = 0.3
    MIN_PROFIT_FACTOR: float = 0.8
    CONSECUTIVE_LOSS_LIMIT: int = 5
    DAILY_LOSS_LIMIT_PCT: float = 0.03
    COOLDOWN_HOURS: int = 24
    
    # ===== 性能優化配置 =====
    DEFAULT_ACCOUNT_BALANCE: float = float(os.getenv("DEFAULT_ACCOUNT_BALANCE", "10000"))
    
    # ===== v3.17+ 倉位計算配置 =====
    EQUITY_USAGE_RATIO: float = float(os.getenv("EQUITY_USAGE_RATIO", "0.8"))
    MIN_NOTIONAL_VALUE: float = float(os.getenv("MIN_NOTIONAL_VALUE", "10.0"))
    MIN_STOP_DISTANCE_PCT: float = float(os.getenv("MIN_STOP_DISTANCE_PCT", "0.003"))
    
    # ===== v3.17+ 動態 SL/TP 配置 =====
    SLTP_SCALE_FACTOR: float = float(os.getenv("SLTP_SCALE_FACTOR", "0.05"))
    SLTP_MAX_SCALE: float = float(os.getenv("SLTP_MAX_SCALE", "3.0"))
    
    # ===== v3.17+: ThreadPool 配置（避免序列化錯誤）=====
    MAX_WORKERS: int = min(
        int(os.getenv("MAX_WORKERS", "4")), 
        (os.cpu_count() or 1) + 4
    )
    
    # ===== v3.17+ PositionController 配置 =====
    POSITION_MONITOR_ENABLED: bool = os.getenv("POSITION_MONITOR_ENABLED", "true").lower() == "true"
    POSITION_MONITOR_INTERVAL: int = int(os.getenv("POSITION_MONITOR_INTERVAL", "2"))
    RISK_KILL_THRESHOLD: float = float(os.getenv("RISK_KILL_THRESHOLD", "0.99"))
    
    # ===== v3.17+ ModelEvaluator 配置 =====
    MODEL_RATING_ENABLED: bool = os.getenv("MODEL_RATING_ENABLED", "true").lower() == "true"
    ENABLE_DAILY_REPORT: bool = os.getenv("ENABLE_DAILY_REPORT", "true").lower() == "true"
    REPORTS_DIR: str = os.getenv("REPORTS_DIR", "reports/daily")
    RATING_LOSS_PENALTY: float = float(os.getenv("RATING_LOSS_PENALTY", "15.0"))
    
    # ===== v3.17+ UnifiedScheduler 配置 =====
    TRADING_SYMBOLS: list = os.getenv("TRADING_SYMBOLS", "").split(",") if os.getenv("TRADING_SYMBOLS") else []
    
    # ===== 日誌配置 =====
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = "data/logs/trading_bot.log"
    
    # ===== 小寫屬性別名（用於兼容 ConfigProfile 介面）=====
    @property
    def min_win_probability(self) -> float:
        return self.MIN_WIN_PROBABILITY
    
    @property
    def min_rr_ratio(self) -> float:
        return self.MIN_RR_RATIO
    
    @property
    def max_rr_ratio(self) -> float:
        return self.MAX_RR_RATIO
    
    @property
    def min_confidence(self) -> float:
        return self.MIN_CONFIDENCE
    
    @property
    def equity_usage_ratio(self) -> float:
        return self.EQUITY_USAGE_RATIO
    
    @property
    def min_notional_value(self) -> float:
        return self.MIN_NOTIONAL_VALUE
    
    @property
    def min_stop_distance_pct(self) -> float:
        return self.MIN_STOP_DISTANCE_PCT
    
    @property
    def sltp_scale_factor(self) -> float:
        return self.SLTP_SCALE_FACTOR
    
    @property
    def sltp_max_scale(self) -> float:
        return self.SLTP_MAX_SCALE
    
    @property
    def position_monitor_enabled(self) -> bool:
        return self.POSITION_MONITOR_ENABLED
    
    @property
    def position_monitor_interval(self) -> int:
        return self.POSITION_MONITOR_INTERVAL
    
    @property
    def risk_kill_threshold(self) -> float:
        return self.RISK_KILL_THRESHOLD
    
    @property
    def model_rating_enabled(self) -> bool:
        return self.MODEL_RATING_ENABLED
    
    @property
    def enable_daily_report(self) -> bool:
        return self.ENABLE_DAILY_REPORT
    
    @property
    def reports_dir(self) -> str:
        return self.REPORTS_DIR
    
    @property
    def rating_loss_penalty(self) -> float:
        return self.RATING_LOSS_PENALTY
    
    @property
    def binance_api_key(self) -> str:
        return self.BINANCE_API_KEY
    
    @property
    def binance_api_secret(self) -> str:
        return self.BINANCE_API_SECRET
    
    @property
    def binance_testnet(self) -> bool:
        return self.BINANCE_TESTNET
    
    @property
    def trading_enabled(self) -> bool:
        return self.TRADING_ENABLED
    
    @property
    def max_positions(self) -> int:
        return self.MAX_POSITIONS
    
    @property
    def cycle_interval(self) -> int:
        return self.CYCLE_INTERVAL
    
    # 槓桿計算參數（ConfigProfile 兼容）
    leverage_base: float = 1.0
    leverage_win_threshold: float = 0.55
    leverage_win_scale: float = 0.15
    leverage_win_multiplier: float = 11.0
    leverage_conf_scale: float = 0.5
    min_leverage: float = 0.5
    
    # 模型評級權重（ConfigProfile 兼容）
    rating_rr_weight: float = 0.25
    rating_winrate_weight: float = 0.20
    rating_ev_weight: float = 0.20
    rating_mdd_weight: float = 0.15
    rating_sharpe_weight: float = 0.10
    rating_frequency_weight: float = 0.10
    
    # ===== 數據文件路徑 =====
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
        warnings = []
        
        if not cls.BINANCE_API_KEY:
            errors.append("缺少 BINANCE_API_KEY 環境變量")
        
        if not cls.BINANCE_API_SECRET:
            errors.append("缺少 BINANCE_API_SECRET 環境變量")
        
        if not cls.DISCORD_TOKEN:
            warnings.append("未設置 DISCORD_TOKEN - Discord 通知將被禁用")
        
        if cls.MAX_POSITIONS < 1:
            errors.append(f"MAX_POSITIONS 必須 >= 1，當前為 {cls.MAX_POSITIONS}")
        
        if cls.MIN_CONFIDENCE < 0 or cls.MIN_CONFIDENCE > 1:
            errors.append(f"MIN_CONFIDENCE 必須在 0-1 之間，當前為 {cls.MIN_CONFIDENCE}")
        
        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for warning in warnings:
                logger.warning(f"⚠️  {warning}")
        
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
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    @classmethod
    def get_summary(cls) -> dict:
        """獲取配置摘要（v3.17+ 版本）"""
        return {
            "version": "v3.17+",
            "binance_testnet": cls.BINANCE_TESTNET,
            "trading_enabled": cls.TRADING_ENABLED,
            "max_positions": cls.MAX_POSITIONS,
            "cycle_interval": cls.CYCLE_INTERVAL,
            "min_confidence": f"{cls.MIN_CONFIDENCE*100}%",
            "log_level": cls.LOG_LEVEL,
            "note": "使用 ConfigProfile 進行 v3.17+ 槓桿控制"
        }
