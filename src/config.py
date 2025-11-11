"""
v3.17+ 精簡配置管理
職責：環境變量、常量定義、配置驗證（移除所有固定槓桿參數）
"""

import os
import sys
from typing import Optional, List
import logging

class Config:
    """系統配置管理類（v4.0+ 支持PostgreSQL）"""
    
    # ===== Binance API 配置 =====
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = (
        os.getenv("BINANCE_API_SECRET", "") or 
        os.getenv("BINANCE_SECRET_KEY", "")
    )
    BINANCE_TRADING_API_KEY: str = os.getenv("BINANCE_TRADING_API_KEY", "") or BINANCE_API_KEY
    BINANCE_TRADING_API_SECRET: str = os.getenv("BINANCE_TRADING_API_SECRET", "") or BINANCE_API_SECRET
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
    
    # ===== 🔥 v4.0+ PostgreSQL数据库配置 =====
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATABASE_PUBLIC_URL: str = os.getenv("DATABASE_PUBLIC_URL", "")
    
    # 数据库连接池配置
    DB_MIN_CONNECTIONS: int = int(os.getenv("DB_MIN_CONNECTIONS", "2"))
    DB_MAX_CONNECTIONS: int = int(os.getenv("DB_MAX_CONNECTIONS", "10"))
    DB_CONNECTION_TIMEOUT: int = int(os.getenv("DB_CONNECTION_TIMEOUT", "30"))
    
    # 数据库查询配置
    DB_QUERY_TIMEOUT: int = int(os.getenv("DB_QUERY_TIMEOUT", "30"))
    DB_BATCH_SIZE: int = int(os.getenv("DB_BATCH_SIZE", "1000"))
    
    @staticmethod
    def get_database_url() -> Optional[str]:
        """获取数据库URL（优先使用内部URL）"""
        return Config.DATABASE_URL or Config.DATABASE_PUBLIC_URL
    
    @staticmethod
    def is_database_configured() -> bool:
        """检查数据库是否已配置"""
        return bool(Config.get_database_url())
    
    # ========================================
    # 🔒 功能锁定开关 (v3.18.7+)
    # ========================================
    # 🔥 v4.1+：默认启用模型训练以支持在线学习
    DISABLE_MODEL_TRAINING: bool = os.getenv("DISABLE_MODEL_TRAINING", "false").lower() == "true"  # 启用模型训练（初始训练+重训练）
    DISABLE_REST_FALLBACK: bool = os.getenv("DISABLE_REST_FALLBACK", "false").lower() == "true"  # 禁用REST API fallback（仅在WebSocket稳定时使用）
    
    # ========================================
    # 🚀 K线预热配置 (v4.2+ Binance速率限制优化)
    # ========================================
    # 🔥 v4.2：默认禁用REST API预热以避免IP封禁
    # - false（默认）：仅使用WebSocket实时数据（需等待60分钟累积1h数据）
    # - true：启动时通过REST API预热历史K线（风险：可能触发速率限制）
    ENABLE_KLINE_WARMUP: bool = os.getenv("ENABLE_KLINE_WARMUP", "false").lower() == "true"
    
    # 预热配置（仅在ENABLE_KLINE_WARMUP=true时生效）
    WARMUP_SYMBOL_LIMIT: int = int(os.getenv("WARMUP_SYMBOL_LIMIT", "50"))  # 最多预热50个交易对（避免速率限制）
    WARMUP_BATCH_SIZE: int = int(os.getenv("WARMUP_BATCH_SIZE", "5"))  # 每批5个交易对（降低并发）
    WARMUP_BATCH_DELAY: float = float(os.getenv("WARMUP_BATCH_DELAY", "2.0"))  # 每批间隔2秒（避免burst）
    WARMUP_TIMEFRAME: str = os.getenv("WARMUP_TIMEFRAME", "1h")  # 只预热1h数据（单时间框架，减少请求）
    
    # ========================================
    # 🎚️ 信号生成模式 (v3.18.7+)
    # ========================================
    # RELAXED_SIGNAL_MODE: 宽松信号生成模式（增加信号数量，降低精度要求）
    # - false: 严格模式 - 只在多时间框架完美对齐时生成信号（高质量，低频率）
    # - true（默认）: 宽松模式 - 允许部分时间框架对齐（中等质量，中等频率）
    # 🔥 v3.18.10+ 默认启用宽松模式以解决0信号问题
    RELAXED_SIGNAL_MODE: bool = os.getenv("RELAXED_SIGNAL_MODE", "true").lower() == "true"
    
    # ===== Discord 配置（可選）=====
    DISCORD_TOKEN: str = (
        os.getenv("DISCORD_TOKEN", "") or 
        os.getenv("DISCORD_BOT_TOKEN", "")
    )
    DISCORD_CHANNEL_ID: Optional[str] = os.getenv("DISCORD_CHANNEL_ID")
    
    # ===== 交易配置 =====
    MAX_CONCURRENT_ORDERS: int = int(os.getenv("MAX_CONCURRENT_ORDERS", "5"))  # 每個週期最多同時開倉數量
    CYCLE_INTERVAL: int = int(os.getenv("CYCLE_INTERVAL", "60"))
    TRADING_ENABLED: bool = os.getenv("TRADING_ENABLED", "true").lower() == "true"
    VIRTUAL_POSITION_CYCLE_INTERVAL: int = int(os.getenv("VIRTUAL_POSITION_CYCLE_INTERVAL", "10"))
    
    # ===== v3.31+ 滑點保護配置 =====
    SLIPPAGE_TOLERANCE: float = float(os.getenv("SLIPPAGE_TOLERANCE", "0.002"))  # 滑點容忍度 0.2% (適合主流幣種)
    USE_LIMIT_ORDER_FOR_ENTRY: bool = os.getenv("USE_LIMIT_ORDER_FOR_ENTRY", "true").lower() == "true"  # 使用限價單開倉（防滑點）
    
    # ===== v3.17+ 核心策略配置 =====
    MIN_CONFIDENCE: float = float(os.getenv("MIN_CONFIDENCE", "0.40"))  # 🔥 v3.20.7: 50%→40% (Bug #6修復)
    MAX_SIGNALS: int = 10
    IMMEDIATE_EXECUTION_RANK: int = 3
    
    # ===== v3.17+ SelfLearningTrader 開倉條件 =====
    MIN_WIN_PROBABILITY: float = float(os.getenv("MIN_WIN_PROBABILITY", "0.45"))  # 🔥 v3.20.7: 60%→45% (Bug #6修復)
    MIN_RR_RATIO: float = float(os.getenv("MIN_RR_RATIO", "0.8"))  # 🔥 v3.20.7: 1.0→0.8 (擴大接受範圍)
    MAX_RR_RATIO: float = float(os.getenv("MAX_RR_RATIO", "5.0"))  # 🔥 v3.20.7: 3.0→5.0 (擴大接受範圍)
    
    # ========================================
    # 🎓 模型啟動豁免方案 (v3.19+ 優化)
    # ========================================
    # 🔥 v3.19：大幅降低門檻以解決0信號問題（特別是小資金賬戶）
    # 前N筆交易使用降低的門檻，加速初期數據採集
    # 所有交易資料和56個特徵仍會被完整保存到訓練檔案
    BOOTSTRAP_TRADE_LIMIT: int = int(os.getenv("BOOTSTRAP_TRADE_LIMIT", "50"))  # 🔥 v3.19：豁免期縮短至50筆（100→50）
    BOOTSTRAP_MIN_WIN_PROBABILITY: float = float(os.getenv("BOOTSTRAP_MIN_WIN_PROBABILITY", "0.20"))  # 🔥 v3.19：豁免期最低勝率20%（40%→20%）
    BOOTSTRAP_MIN_CONFIDENCE: float = float(os.getenv("BOOTSTRAP_MIN_CONFIDENCE", "0.25"))  # 🔥 v3.19：豁免期最低信心值25%（40%→25%）
    
    # ===== v3.19+ 資金分配配置（動態預算池 + 質量加權）=====
    SIGNAL_QUALITY_THRESHOLD: float = float(os.getenv("SIGNAL_QUALITY_THRESHOLD", "0.40"))  # 🔥 v3.20.7: 60%→40% (Bug #6修復)
    BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD: float = float(os.getenv("BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD", "0.25"))  # 🔥 v3.19：豁免期質量門檻25%（40%→25%）
    
    # ========================================
    # 🗄️ 數據庫增強系統 (v3.20+)
    # ========================================
    ENABLE_DATABASE_ENHANCEMENTS: bool = os.getenv("ENABLE_DATABASE_ENHANCEMENTS", "false").lower() == "true"  # 數據庫增強功能（默認禁用）
    MAX_TOTAL_BUDGET_RATIO: float = float(os.getenv("MAX_TOTAL_BUDGET_RATIO", "0.90"))  # 🔥 v3.19：總預算提升至90%（80%→90%，小資金優化）
    MAX_SINGLE_POSITION_RATIO: float = float(os.getenv("MAX_SINGLE_POSITION_RATIO", "0.5"))  # 單倉 ≤ 50% 帳戶權益
    MAX_TOTAL_MARGIN_RATIO: float = float(os.getenv("MAX_TOTAL_MARGIN_RATIO", "0.9"))  # 總倉位保證金 ≤ 90% 帳戶總金額（不含浮盈浮虧）
    
    # ===== v3.18+ 全倉保護配置（防止虧損稀釋10%預留緩衝）=====
    CROSS_MARGIN_PROTECTOR_ENABLED: bool = os.getenv("CROSS_MARGIN_PROTECTOR_ENABLED", "true").lower() == "true"  # 啟用全倉保護
    CROSS_MARGIN_PROTECTOR_THRESHOLD: float = float(os.getenv("CROSS_MARGIN_PROTECTOR_THRESHOLD", "0.85"))  # 85%觸發閾值（90%上限前5%預警）
    CROSS_MARGIN_PROTECTOR_COOLDOWN: int = int(os.getenv("CROSS_MARGIN_PROTECTOR_COOLDOWN", "120"))  # 平倉後冷卻時間（秒）
    
    # ===== v3.28+ 基於時間的強制止損配置 =====
    TIME_BASED_STOP_LOSS_ENABLED: bool = os.getenv("TIME_BASED_STOP_LOSS_ENABLED", "true").lower() == "true"  # 啟用時間基礎止損
    TIME_BASED_STOP_LOSS_HOURS: float = float(os.getenv("TIME_BASED_STOP_LOSS_HOURS", "2.0"))  # 持倉時間閾值（小時）
    TIME_BASED_STOP_LOSS_CHECK_INTERVAL: int = int(os.getenv("TIME_BASED_STOP_LOSS_CHECK_INTERVAL", "300"))  # 檢查間隔（秒，默認5分鐘）
    
    # ===== 掃描配置（監控所有 U 本位合約）=====
    SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL", "60"))
    TOP_VOLATILITY_SYMBOLS: int = int(os.getenv("TOP_VOLATILITY_SYMBOLS", "999"))
    
    # ===== WebSocket 優化配置（v3.17.2+）=====
    WEBSOCKET_SYMBOL_LIMIT: int = int(os.getenv("WEBSOCKET_SYMBOL_LIMIT", "200"))  # 🔥 v3.17.2+ 優化：監控前200個高品質交易對（流動性×波動率）
    WEBSOCKET_SHARD_SIZE: int = int(os.getenv("WEBSOCKET_SHARD_SIZE", "50"))  # 每分片50個符號（200/50 = 4個分片）
    WEBSOCKET_HEARTBEAT_TIMEOUT: int = int(os.getenv("WEBSOCKET_HEARTBEAT_TIMEOUT", "30"))  # 心跳超時30秒
    REST_COOLDOWN_BASE: int = int(os.getenv("REST_COOLDOWN_BASE", "60"))  # REST備援基礎冷卻60秒
    
    # ===== 時間框架配置 =====
    TIMEFRAMES: List[str] = ["1h", "15m", "5m"]  # 多時間框架分析：1h主趨勢, 15m中期, 5m入場
    
    # ===== 技術指標配置 =====
    EMA_FAST: int = 20
    EMA_SLOW: int = 50
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70
    RSI_OVERSOLD: float = 30
    ATR_PERIOD: int = 14
    ATR_MULTIPLIER: float = 2.0
    RISK_REWARD_RATIO: float = 2.0
    
    # ===== ADX 趨勢過濾器（v3.18.10+ 專項優化）=====
    ADX_PERIOD: int = 14
    ADX_TREND_THRESHOLD: float = 20.0
    ADX_STRONG_TREND: float = 25.0
    EMA_SLOPE_THRESHOLD: float = 0.01
    
    # 🔥 v3.19+ ADX激進優化（進一步降低門檻，解決0信號問題）
    ADX_HARD_REJECT_THRESHOLD: float = float(os.getenv("ADX_HARD_REJECT_THRESHOLD", "5.0"))  # 🔥 v3.19：硬拒絕門檻降至5.0（10.0→5.0）
    ADX_WEAK_TREND_THRESHOLD: float = float(os.getenv("ADX_WEAK_TREND_THRESHOLD", "10.0"))   # 🔥 v3.19：弱趨勢門檻降至10.0（15.0→10.0）
    
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
    ML_FLUSH_COUNT: int = 1  # 🔥 v3.18.4-hotfix: 實時保存，防止數據丟失
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
    MIN_NOTIONAL_VALUE: float = float(os.getenv("MIN_NOTIONAL_VALUE", "5.0"))  # 🔥 v3.19：降低最小交易額至5 USDT（10→5，適配小資金）
    MIN_STOP_DISTANCE_PCT: float = float(os.getenv("MIN_STOP_DISTANCE_PCT", "0.003"))
    
    # ===== v3.17+ 動態 SL/TP 配置 =====
    SLTP_SCALE_FACTOR: float = float(os.getenv("SLTP_SCALE_FACTOR", "0.05"))
    SLTP_MAX_SCALE: float = float(os.getenv("SLTP_MAX_SCALE", "3.0"))
    SLTP_TP_TO_SL_RATIO: float = float(os.getenv("SLTP_TP_TO_SL_RATIO", "1.5"))  # TP = SL × 1.5
    
    # ===== v3.18+ 槓桿限制配置 =====
    MIN_LEVERAGE: float = float(os.getenv("MIN_LEVERAGE", "0.5"))  # 最小槓桿0.5x（防止過低導致倉位無意義）
    
    # ===== v3.17+: ThreadPool 配置（避免序列化錯誤）=====
    MAX_WORKERS: int = min(
        int(os.getenv("MAX_WORKERS", "4")), 
        (os.cpu_count() or 1) + 4
    )
    
    # ===== v3.17+ PositionController 配置 =====
    POSITION_MONITOR_ENABLED: bool = os.getenv("POSITION_MONITOR_ENABLED", "true").lower() == "true"
    POSITION_MONITOR_INTERVAL: int = int(os.getenv("POSITION_MONITOR_INTERVAL", "60"))  # v3.17.2+: 改為1分鐘
    RISK_KILL_THRESHOLD: float = float(os.getenv("RISK_KILL_THRESHOLD", "0.99"))
    
    # ===== v3.17.2+ WebSocket 配置 =====
    WEBSOCKET_SHARD_SIZE: int = int(os.getenv("WEBSOCKET_SHARD_SIZE", "50"))  # 每個分片50個符號
    WEBSOCKET_AUTO_FETCH_SYMBOLS: bool = os.getenv("WEBSOCKET_AUTO_FETCH_SYMBOLS", "true").lower() == "true"
    WEBSOCKET_ENABLE_KLINE_FEED: bool = os.getenv("WEBSOCKET_ENABLE_KLINE_FEED", "true").lower() == "true"
    WEBSOCKET_ENABLE_PRICE_FEED: bool = os.getenv("WEBSOCKET_ENABLE_PRICE_FEED", "true").lower() == "true"
    WEBSOCKET_ENABLE_ACCOUNT_FEED: bool = os.getenv("WEBSOCKET_ENABLE_ACCOUNT_FEED", "true").lower() == "true"
    WEBSOCKET_HEARTBEAT_TIMEOUT: int = int(os.getenv("WEBSOCKET_HEARTBEAT_TIMEOUT", "30"))  # 心跳超時30秒
    WEBSOCKET_REST_COOLDOWN_MIN: int = int(os.getenv("WEBSOCKET_REST_COOLDOWN_MIN", "60"))  # REST冷卻最小60秒
    WEBSOCKET_REST_COOLDOWN_MAX: int = int(os.getenv("WEBSOCKET_REST_COOLDOWN_MAX", "300"))  # REST冷卻最大300秒
    
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
    # 直接引用大寫變量，避免 @property 格式化問題
    min_win_probability: float = MIN_WIN_PROBABILITY
    min_rr_ratio: float = MIN_RR_RATIO
    max_rr_ratio: float = MAX_RR_RATIO
    min_confidence: float = MIN_CONFIDENCE
    equity_usage_ratio: float = EQUITY_USAGE_RATIO
    min_notional_value: float = MIN_NOTIONAL_VALUE
    min_stop_distance_pct: float = MIN_STOP_DISTANCE_PCT
    sltp_scale_factor: float = SLTP_SCALE_FACTOR
    sltp_max_scale: float = SLTP_MAX_SCALE
    sltp_tp_to_sl_ratio: float = SLTP_TP_TO_SL_RATIO
    min_leverage: float = MIN_LEVERAGE
    position_monitor_enabled: bool = POSITION_MONITOR_ENABLED
    position_monitor_interval: int = POSITION_MONITOR_INTERVAL
    risk_kill_threshold: float = RISK_KILL_THRESHOLD
    model_rating_enabled: bool = MODEL_RATING_ENABLED
    enable_daily_report: bool = ENABLE_DAILY_REPORT
    reports_dir: str = REPORTS_DIR
    rating_loss_penalty: float = RATING_LOSS_PENALTY
    binance_api_key: str = BINANCE_API_KEY
    binance_api_secret: str = BINANCE_API_SECRET
    binance_testnet: bool = BINANCE_TESTNET
    trading_enabled: bool = TRADING_ENABLED
    cycle_interval: int = CYCLE_INTERVAL
    
    # 槓桿計算參數（ConfigProfile 兼容）
    leverage_base: float = 1.0
    leverage_win_threshold: float = 0.55
    leverage_win_scale: float = 0.15
    leverage_win_multiplier: float = 11.0
    leverage_conf_scale: float = 0.5
    
    # 模型評級權重（ConfigProfile 兼容）
    rating_rr_weight: float = 0.25
    rating_winrate_weight: float = 0.20
    rating_ev_weight: float = 0.20
    rating_mdd_weight: float = 0.15
    rating_sharpe_weight: float = 0.10
    rating_frequency_weight: float = 0.10
    
    # ===== 數據文件路徑 =====
    DATA_DIR: str = "data"
    TRADES_FILE: str = f"{DATA_DIR}/trades.jsonl"  # 🔥 v3.18.4-hotfix: 正確的JSON Lines格式
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
            "cycle_interval": cls.CYCLE_INTERVAL,
            "min_confidence": f"{cls.MIN_CONFIDENCE*100}%",
            "log_level": cls.LOG_LEVEL,
            "note": "使用 ConfigProfile 進行 v3.17+ 槓桿控制"
        }
