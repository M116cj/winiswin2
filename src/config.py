"""
全局配置管理
職責：環境變量、常量定義、配置驗證
"""

import os
import sys
from typing import Optional
import logging

class Config:
    """系統配置管理類"""
    
    # Binance API 配置
    # 主 API（數據收集）
    # 支持多種命名方式以兼容不同配置
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = (
        os.getenv("BINANCE_API_SECRET", "") or 
        os.getenv("BINANCE_SECRET_KEY", "")  # 兼容舊命名
    )
    
    # 可選：交易專用 API（避免訂單限制影響數據收集）
    BINANCE_TRADING_API_KEY: str = os.getenv("BINANCE_TRADING_API_KEY", "") or BINANCE_API_KEY
    BINANCE_TRADING_API_SECRET: str = os.getenv("BINANCE_TRADING_API_SECRET", "") or BINANCE_API_SECRET
    
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
    
    # Discord 配置
    # 支持多種命名方式以兼容不同配置
    DISCORD_TOKEN: str = (
        os.getenv("DISCORD_TOKEN", "") or 
        os.getenv("DISCORD_BOT_TOKEN", "")  # 兼容舊命名
    )
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
    
    # 策略配置（v3.9.2.3紧急修复）
    MIN_CONFIDENCE: float = 0.35  # 🚨 降低到 0.35 进一步提高信号生成率
    MAX_SIGNALS: int = 10
    IMMEDIATE_EXECUTION_RANK: int = 3
    
    # 掃描配置
    SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL", "60"))  # 掃描間隔（秒，默認60秒）
    TOP_VOLATILITY_SYMBOLS: int = int(os.getenv("TOP_LIQUIDITY_SYMBOLS", "200"))  # 監控流動性最高的前N個（默認200）
    
    # 技術指標配置（v3.10.0：ADX趨勢過濾）
    EMA_FAST: int = 20   # 從50降到20，更快捕捉趨勢
    EMA_SLOW: int = 50   # 從200降到50，更靈敏
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70
    RSI_OVERSOLD: float = 30
    ATR_PERIOD: int = 14
    ATR_MULTIPLIER: float = 2.0
    RISK_REWARD_RATIO: float = 2.0
    
    # ADX趨勢強度過濾器（v3.10.0新增）
    ADX_PERIOD: int = 14
    ADX_TREND_THRESHOLD: float = 20.0  # ADX > 20 才視為有效趨勢
    ADX_STRONG_TREND: float = 25.0     # ADX > 25 視為強趨勢
    EMA_SLOPE_THRESHOLD: float = 0.01  # EMA斜率閾值（0.01% = 有效斜率）
    
    # 實時波動率熔斷器（v3.10.0新增）
    VOLATILITY_CIRCUIT_BREAKER_ENABLED: bool = True
    VOLATILITY_WINDOW_DAYS: int = 7    # 7日波動率參考窗口
    VOLATILITY_SPIKE_MULTIPLIER: float = 2.0  # 當前ATR > 7日均值2倍 = 波動突變
    VOLATILITY_SPIKE_MAX_LEVERAGE: int = 5    # 波動突變時最大槓桿
    
    # Order Blocks 配置（v3.11.0增强：质量筛选+动态衰减）
    OB_REJECTION_PCT: float = 0.03
    OB_VOLUME_MULTIPLIER: float = 1.5  # 成交量必须 >= 20根均量的1.5倍
    OB_LOOKBACK: int = 20
    OB_MIN_VOLUME_RATIO: float = 1.5   # 最小成交量倍数（筛选低质量OB）
    OB_REJECTION_THRESHOLD: float = 0.005  # 拒绝率阈值（0.5%体积 - 更实用）
    OB_MAX_TEST_COUNT: int = 3         # OB最多被测试3次后失效
    OB_MAX_HISTORY: int = 20           # 最多保留20个历史OB（用于衰减追踪）
    OB_DECAY_ENABLED: bool = True      # 启用动态衰减
    OB_TIME_DECAY_HOURS: int = 48      # 48小时后OB开始衰减
    OB_DECAY_RATE: float = 0.1         # 每24小时衰减10%强度
    
    # 訂單配置
    MAX_SLIPPAGE_PCT: float = 0.002  # 最大滑點容忍度 0.2% （也用作限價單保護範圍）
    ORDER_TIMEOUT_SECONDS: int = 30  # 限價單超時時間（秒）
    USE_LIMIT_ORDERS: bool = True  # 是否使用限價單（滑點過大時）
    AUTO_ORDER_TYPE: bool = True  # 自動選擇訂單類型
    
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
    # 使用 80% 官方限額（2400 * 0.8 = 1920）留 20% 安全邊際
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "1920"))
    RATE_LIMIT_PERIOD: int = 60
    
    # 緩存配置（根據時間框架優化）
    # K線緩存時間應該匹配時間框架的持續時間
    CACHE_TTL_KLINES_1H: int = 3600    # 1小時 K線緩存1小時
    CACHE_TTL_KLINES_15M: int = 900    # 15分鐘 K線緩存15分鐘
    CACHE_TTL_KLINES_5M: int = 300     # 5分鐘 K線緩存5分鐘
    CACHE_TTL_KLINES_DEFAULT: int = 300  # 其他默認5分鐘
    CACHE_TTL_TICKER: int = 5
    CACHE_TTL_ACCOUNT: int = 10
    
    # 熔斷器配置（v3.9.2.8.4：分級熔斷）
    CIRCUIT_BREAKER_THRESHOLD: int = 5  # 舊版閾值（向後兼容）
    CIRCUIT_BREAKER_TIMEOUT: int = 60
    
    # 分級熔斷器配置（v3.9.2.8.4新增）
    GRADED_CIRCUIT_BREAKER_ENABLED: bool = True  # 啟用分級熔斷器
    CIRCUIT_BREAKER_WARNING_THRESHOLD: int = 2   # 警告級閾值
    CIRCUIT_BREAKER_THROTTLED_THRESHOLD: int = 4  # 限流級閾值
    CIRCUIT_BREAKER_BLOCKED_THRESHOLD: int = 5   # 阻斷級閾值
    CIRCUIT_BREAKER_THROTTLE_DELAY: float = 2.0  # 限流延遲（秒）
    
    # Bypass白名單（可繞過熔斷的關鍵操作）
    CIRCUIT_BREAKER_BYPASS_OPERATIONS: list = [
        "close_position",        # 平倉
        "emergency_stop_loss",   # 緊急止損
        "adjust_stop_loss",      # 調整止損
        "adjust_take_profit",    # 調整止盈
        "get_positions",         # 查詢持倉
        "cancel_order"           # 取消訂單
    ]
    
    # v3.9.2.2新增：訂單執行配置（防止熔斷器觸發導致無保護倉位）
    ORDER_INTER_DELAY: float = 1.5  # 訂單間延遲（秒）- 避免觸發熔斷器
    ORDER_RETRY_MAX_ATTEMPTS: int = 5  # 訂單重試最大次數
    ORDER_RETRY_BASE_DELAY: float = 1.0  # 重試基礎延遲（秒）
    ORDER_RETRY_MAX_DELAY: float = 30.0  # 重試最大延遲（秒）
    PROTECTION_GUARDIAN_INTERVAL: int = 30  # 保護監護任務檢查間隔（秒）
    PROTECTION_GUARDIAN_MAX_ATTEMPTS: int = 10  # 保護監護最大嘗試次數
    
    # 批量處理配置
    BATCH_SIZE: int = 50
    
    # 虛擬倉位配置
    VIRTUAL_POSITION_EXPIRY: int = 96
    
    # ML 數據收集配置
    ML_FLUSH_COUNT: int = 25
    ML_FLUSH_INTERVAL: int = 300
    ML_DATA_DIR: str = "ml_data"
    
    # 期望值計算配置
    EXPECTANCY_WINDOW: int = 30
    MIN_EXPECTANCY_PCT: float = 0.3
    MIN_PROFIT_FACTOR: float = 0.8
    CONSECUTIVE_LOSS_LIMIT: int = 5
    DAILY_LOSS_LIMIT_PCT: float = 0.03
    COOLDOWN_HOURS: int = 24
    
    # 性能優化配置
    DEFAULT_ACCOUNT_BALANCE: float = float(os.getenv("DEFAULT_ACCOUNT_BALANCE", "10000"))
    MIN_NOTIONAL_VALUE: float = 20.0  # Binance最小訂單價值
    ML_MIN_TRAINING_SAMPLES: int = 100  # XGBoost最小訓練樣本數
    INDICATOR_CACHE_TTL: int = 60  # 技術指標緩存時間（秒）
    CACHE_TTL_KLINES_HISTORICAL: int = 86400  # 歷史K線緩存24小時（不會改變）
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "32"))  # 並行分析工作線程數
    
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
        warnings = []
        
        # 必需的配置
        if not cls.BINANCE_API_KEY:
            errors.append("缺少 BINANCE_API_KEY 環境變量")
        
        if not cls.BINANCE_API_SECRET:
            errors.append("缺少 BINANCE_API_SECRET 環境變量")
        
        # 可選的配置（僅警告）
        if not cls.DISCORD_TOKEN:
            warnings.append("未設置 DISCORD_TOKEN - Discord 通知將被禁用")
        
        if cls.MAX_POSITIONS < 1 or cls.MAX_POSITIONS > 10:
            errors.append(f"MAX_POSITIONS 必須在 1-10 之間，當前為 {cls.MAX_POSITIONS}")
        
        if cls.MIN_CONFIDENCE < 0 or cls.MIN_CONFIDENCE > 1:
            errors.append(f"MIN_CONFIDENCE 必須在 0-1 之間，當前為 {cls.MIN_CONFIDENCE}")
        
        # 如果有警告，記錄但不阻止啟動
        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for warning in warnings:
                logger.warning(f"⚠️  {warning}")
        
        return len(errors) == 0, errors
    
    @classmethod
    def setup_logging(cls):
        """設置日誌系統（輸出到 stdout 避免 Railway [err] 標籤）"""
        os.makedirs(os.path.dirname(cls.LOG_FILE), exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, cls.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(cls.LOG_FILE),
                logging.StreamHandler(sys.stdout)  # 輸出到 stdout 而非 stderr
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
