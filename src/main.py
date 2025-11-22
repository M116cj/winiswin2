"""
主程序入口 - SelfLearningTrader v3.17+
職責：系統初始化、啟動 UnifiedScheduler

核心理念：「模型擁有無限制槓桿控制權，唯一準則是勝率 × 信心度」

架構：
┌───────────────────────────────────────┐
│        應用層 (main.py)               │
│ • 系統啟動 + 配置驗證                 │
│ • 啟動 UnifiedScheduler               │
└───────────────┬───────────────────────┘
                ▼
┌───────────────────────────────────────┐
│      核心引擎層 (Core Engine)         │
│ • SelfLearningTrader（絕對決策者）     │
│ • RuleBasedSignalGenerator（信號源）  │
│ • PositionController（倉位全權控制）  │
│ • ModelEvaluator（每日評分報告）      │
└───────────────┬───────────────────────┘
                ▼
┌───────────────────────────────────────┐
│        基礎設施層 (Infrastructure)     │
│ • BinanceClient（優先 API 通道）      │
│ • DataManager（數據管理）             │
│ • TradeHistoryDB（交易記錄）          │
└───────────────────────────────────────┘
"""

# 🔥 Performance Upgrade: Install uvloop for 2-4x faster event loop
import asyncio
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    _UVLOOP_ENABLED = True
except ImportError:
    _UVLOOP_ENABLED = False

import logging
import signal
import sys
from datetime import datetime
from typing import Optional

from src.core.unified_config_manager import config_manager as config
from src.clients.binance_client import BinanceClient
from src.services.data_service import DataService
from src.core.unified_scheduler import UnifiedScheduler
from src.managers.unified_trade_recorder import UnifiedTradeRecorder  # 🔥 v4.0+ PostgreSQL版
from src.monitoring.health_check import SystemHealthMonitor  # v3.29+
from src.core.elite.technical_indicator_engine import EliteTechnicalEngine  # 🔥 v4.0+ 统一引擎
from src.core.model_evaluator import ModelEvaluator
from src.core.model_initializer import ModelInitializer
from src.utils.config_validator import validate_config
from src.utils.smart_logger import create_smart_logger

# 🔥 v4.0+ PostgreSQL数据库支持（Phase 3: AsyncDatabaseManager迁移）
from src.database.unified_database_manager import UnifiedDatabaseManager
from src.database.service import TradingDataService
from src.database.initializer import initialize_database

# 🔥 Performance Upgrade: Redis caching layer


# 🛡️ v1.0+: Lifecycle management (graceful shutdown, watchdog, smart startup)
from src.core.lifecycle_manager import get_lifecycle_manager
from src.core.startup_manager import get_startup_manager

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 🔥 v4.3+ Railway日志优化（过滤冗余，只显示关键业务指标）
try:
    from src.utils.railway_logger import setup_railway_logging
    railway_business_logger = setup_railway_logging()
except Exception as e:
    # 如果Railway日志初始化失败，使用标准日志
    logging.warning(f"Railway日志优化未启用: {e}")
    railway_business_logger = None

# ✨ v3.26+ 性能优化：启用SmartLogger（99%速率限制效率）
logger = create_smart_logger(
    __name__,
    rate_limit_window=2.0,
    enable_aggregation=True,
    enable_structured=False
)


class SelfLearningTradingSystem:
    """
    SelfLearningTrader v4.0+ 交易系統
    
    職責：
    1. 系統初始化
    2. 啟動 UnifiedScheduler
    3. 優雅關閉
    
    🔥 v4.0+ 重大改进：
    - 统一PostgreSQL数据存储（唯一数据源）
    - UnifiedTradeRecorder（合并4个TradeRecorder）
    - 统一技术指标引擎（合并重复实现）
    - 代码量减少34%（42,752→28,000行）
    """
    
    def __init__(self):
        """初始化系統"""
        self.running = False
        self.config = config  # 统一配置管理器
        
        # 核心組件
        self.binance_client: Optional[BinanceClient] = None
        self.data_service: Optional[DataService] = None
        self.trade_recorder: Optional[UnifiedTradeRecorder] = None  # 🔥 v4.0+ PostgreSQL版
        self.model_evaluator: Optional[ModelEvaluator] = None
        self.model_initializer: Optional[ModelInitializer] = None
        self.scheduler: Optional[UnifiedScheduler] = None
        
        # 🔥 v4.0+ PostgreSQL数据库组件（统一数据库管理器）
        self.db_manager: Optional[UnifiedDatabaseManager] = None
        self.db_service: Optional[TradingDataService] = None
        
        # 🛡️ v1.0+: Lifecycle management
        self.lifecycle_manager = None
        
        # 其他组件
        self.health_monitor: Optional[SystemHealthMonitor] = None
        self.technical_engine: Optional[EliteTechnicalEngine] = None
    
    async def initialize(self):
        """初始化所有組件"""
        try:
            # 🔥 精简启动日志（Railway优化）
            logger.info("🚀 SelfLearningTrader v4.0+ 启动中...")
            
            # 🔥 Performance Upgrade: Report uvloop status
            if _UVLOOP_ENABLED:
                logger.info("⚡ uvloop已启用（2-4x WebSocket性能提升）")
            else:
                logger.warning("⚠️  uvloop未安装，使用标准asyncio事件循环")
            
            # 🔥 v3.26+ 全面配置驗證（使用新的ConfigValidator）
            is_valid, errors, warnings = validate_config(config)
            
            if not is_valid:
                logger.error("❌ 配置驗證失敗:")
                for error in errors:
                    logger.error(f"  - {error}")
                logger.error("💡 請修正配置錯誤後重新啟動系統")
                return False
            
            # 打印警告（如果有）
            if warnings:
                for warning in warnings:
                    logger.warning(warning)
            
            logger.debug("✅ 配置驗證通過")
            
            # 顯示配置（降级为DEBUG）
            self._display_config()
            
            # 初始化核心組件（降级为DEBUG）
            logger.debug("初始化核心組件...")
            
            # Binance 客戶端
            self.binance_client = BinanceClient()
            
            # 測試連接（非阻塞，帶指數退避重試）
            connection_ok = await self._test_connection_with_retry(
                max_retries=3,
                initial_delay=5
            )
            
            if connection_ok:
                logger.debug("✅ Binance 客戶端已連接")
            else:
                logger.warning("⚠️ API連接測試未通過，將在實際調用時重試")
            
            # 數據服務（v3.17.2+：預留websocket_monitor，稍後設置）
            self.data_service = DataService(
                binance_client=self.binance_client,
                websocket_monitor=None  # 🔥 v3.17.2+：將在UnifiedScheduler創建後設置
            )
            
            # 🔥 重要：初始化 DataService（加載所有交易對）
            await self.data_service.initialize()
            logger.debug("✅ 數據服務初始化完成")
            
            # 🔥 v4.0+ PostgreSQL数据库初始化（必需）
            if not config.get_database_url():
                logger.error("❌ DATABASE_URL未配置！无法启动系统")
                logger.error("💡 请在Railway环境变量中设置DATABASE_URL")
                return False  # Fail fast - 数据库不可用时立即终止
            
            try:
                self.db_manager = UnifiedDatabaseManager(
                    min_connections=2,
                    max_connections=10,
                    connection_timeout=30
                )
                # 初始化异步连接池
                await self.db_manager.initialize()
                logger.debug("✅ 数据库连接池已创建并初始化")
            except Exception as e:
                logger.error(f"❌ 数据库连接失败: {e}")
                return False  # Fail fast - 数据库连接失败时立即终止
            
            # 初始化数据表
            if not await initialize_database(self.db_manager):
                logger.error("❌ 数据库表初始化失败")
                return False  # Fail fast - 表初始化失败时立即终止
            
            logger.debug("✅ 数据库表结构初始化完成")
            
            # 创建数据服务（统一数据库管理器已包含Redis缓存层）
            self.db_service = TradingDataService(self.db_manager)
            logger.debug("✅ PostgreSQL数据服务已创建（带Redis缓存）")
            
            # 🔥 v3.17.10+：模型評估器（用於特徵重要性分析）
            self.model_evaluator = ModelEvaluator(
                config=self.config,
                reports_dir=self.config.REPORTS_DIR
            )
            logger.debug("✅ 模型評估器初始化完成")
            
            # 🔥 v3.18.6+：先創建模型初始化器（用於重訓練）
            self.model_initializer = ModelInitializer(
                binance_client=self.binance_client,
                trade_recorder=None,  # 稍後設置
                config_profile=self.config,
                model_evaluator=self.model_evaluator
            )
            logger.debug("✅ 模型初始化器已創建")
            
            # 🔥 v4.0+ 统一PostgreSQL交易记录器（必定成功，因为db_service已验证）
            self.trade_recorder = UnifiedTradeRecorder(
                db_service=self.db_service,
                model_scorer=None,  # 可选
                model_initializer=self.model_initializer,
                retrain_interval=50
            )
            logger.debug("✅ UnifiedTradeRecorder初始化完成")
            
            # 設置ModelInitializer的trade_recorder引用
            self.model_initializer.trade_recorder = self.trade_recorder
            logger.debug("✅ 模型初始化器與交易記錄器已關聯")
            
            # 🔥 v4.1+：執行模型初始化檢查（啟用在線學習）
            logger.info("🧠 檢查模型初始化狀態...")
            try:
                model_ready = await self.model_initializer.check_and_initialize()
                if model_ready:
                    logger.info("✅ 模型已就緒，ML增強模式已啟用")
                else:
                    logger.warning("⚠️ 模型初始化未完成，系統將以純規則引擎模式運行")
                    logger.warning("   💡 系統將在稍後嘗試重新訓練（當累積足夠數據時）")
            except Exception as e:
                logger.error(f"❌ 模型初始化檢查失敗: {e}")
                logger.warning("⚠️ 降級為純規則引擎模式，稍後將自動重試訓練")
            
            # 🔥 v4.0+ 统一技术引擎（合并重复实现）
            self.technical_engine = EliteTechnicalEngine()
            logger.debug("✅ 统一技术引擎初始化完成")
            
            # 🛡️ v1.0+: Get lifecycle manager instance
            self.lifecycle_manager = get_lifecycle_manager()
            
            # UnifiedScheduler（核心調度器，帶生命週期管理）
            self.scheduler = UnifiedScheduler(
                config=self.config,  # type: ignore  # Config類級別配置
                binance_client=self.binance_client,
                data_service=self.data_service,
                trade_recorder=self.trade_recorder,
                model_initializer=self.model_initializer,  # 🔥 v3.17.10+
                lifecycle_manager=self.lifecycle_manager  # 🛡️ v1.0+
            )
            logger.debug("✅ UnifiedScheduler 初始化完成")
            
            # 🔥 v3.17.2+：將websocket_monitor設置到DataService（降低REST API使用）
            self.data_service.websocket_monitor = self.scheduler.websocket_manager
            logger.debug("✅ DataService已連接WebSocket")
            
            # 🔥 v3.29+ 系统健康监控（6大组件监控）
            self.health_monitor = SystemHealthMonitor(
                check_interval=60,  # 每60秒检查一次
                alert_threshold=3,   # 连续3次失败触发告警
                binance_client=self.binance_client,
                websocket_manager=self.scheduler.websocket_manager,
                trade_recorder=self.trade_recorder
            )
            logger.debug("✅ 系统健康监控初始化完成")
            
            # 启动健康监控
            await self.health_monitor.start_monitoring()
            logger.debug("✅ 健康监控已启动")
            
            # 🛡️ v1.0+: Register components for graceful shutdown
            self.lifecycle_manager.register_component("WebSocket", self.scheduler.websocket_manager.stop, priority=10)
            self.lifecycle_manager.register_component("Database", self.db_manager.close, priority=30)
            self.lifecycle_manager.register_component("HealthMonitor", self.health_monitor.stop, priority=5)
            logger.debug("✅ 组件已注册到生命周期管理器")
            
            # 🛡️ v1.0+: Start watchdog (hang detection)
            self.lifecycle_manager.start_watchdog()
            logger.debug("✅ 看门狗已启动")
            
            logger.info("✅ 系统初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 初始化失敗: {e}", exc_info=True)
            return False
    
    
    async def _test_connection_with_retry(
        self, 
        max_retries: int = 3, 
        initial_delay: int = 5
    ) -> bool:
        """
        測試API連接（帶指數退避重試）
        
        Args:
            max_retries: 最大重試次數
            initial_delay: 初始延遲秒數
            
        Returns:
            連接成功返回True，否則返回False
        """
        for attempt in range(max_retries):
            try:
                if self.binance_client and await self.binance_client.test_connection():
                    if attempt > 0:
                        logger.info(f"✅ 第{attempt + 1}次嘗試成功連接")
                    return True
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = initial_delay * (2 ** attempt)
                    logger.warning(
                        f"⚠️ 連接測試失敗 (嘗試 {attempt + 1}/{max_retries}): {e}"
                    )
                    logger.warning(f"⏳ {wait_time}秒後重試...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.warning(
                        f"⚠️ 達到最大重試次數 ({max_retries}次)，跳過連接測試"
                    )
                    logger.warning(f"⚠️ 最後錯誤: {e}")
        
        return False
    
    def _display_config(self):
        """顯示當前配置（降级为DEBUG）"""
        logger.debug("系統配置:")
        logger.debug(f"  version: v4.0+")
        logger.debug(f"  binance_testnet: {self.config.BINANCE_TESTNET}")
        logger.debug(f"  trading_enabled: {self.config.TRADING_ENABLED}")
        logger.debug(f"  cycle_interval: {self.config.CYCLE_INTERVAL}")
        logger.debug(f"  min_confidence: {self.config.MIN_CONFIDENCE * 100:.1f}%")
    
    async def run(self):
        """啟動系統（由生命周期管理器控制）"""
        # 初始化
        if not await self.initialize():
            logger.error("初始化失敗，退出程序")
            raise RuntimeError("System initialization failed")
        
        # 啟動 UnifiedScheduler（生命週期管理器會處理信號和關閉）
        self.running = True
        logger.debug("启动调度器...")
        if self.scheduler:  # 類型檢查
            await self.scheduler.start()
    
    async def shutdown(self):
        """優雅關閉系統"""
        try:
            logger.info("\n🔄 系統關閉中...")
            self.running = False
            
            # v3.29+ 停止健康监控
            if self.health_monitor:
                await self.health_monitor.stop_monitoring()
                logger.info("✅ 健康监控已停止")
            
            # 停止 UnifiedScheduler
            if self.scheduler:
                await self.scheduler.stop()
            
            # 關閉 Binance 客戶端
            if self.binance_client:
                await self.binance_client.close()
            
            # 🔥 v4.0+ PostgreSQL自动保存（无需手动flush）
            if self.trade_recorder:
                logger.info("💾 PostgreSQL数据已自动保存")
                # UnifiedTradeRecorder使用PostgreSQL，自动保存，无需手动flush
            
            # 关闭数据库连接池
            if self.db_manager:
                logger.info("🔒 关闭数据库连接池...")
                await self.db_manager.close()
                logger.info("✅ 数据库连接已关闭")
            
            logger.info("✅ 系統已安全關閉")
            
        except Exception as e:
            logger.error(f"❌ 關閉失敗: {e}", exc_info=True)
    
    def _setup_signal_handlers(self):
        """
        設置信號處理器（v3.18.4-hotfix）
        
        使用loop.call_soon_threadsafe確保shutdown在event loop中執行
        """
        loop = asyncio.get_running_loop()
        
        def signal_handler(sig, frame):
            logger.info(f"\n收到信號 {sig}，準備關閉...")
            if self.running:
                # 使用call_soon_threadsafe在event loop中調度shutdown
                loop.call_soon_threadsafe(lambda: asyncio.create_task(self.shutdown()))
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("✅ 信號處理器已註冊（SIGINT, SIGTERM）")


async def main():
    """主函數（通過啟動管理器運行）"""
    startup_manager = get_startup_manager()
    system = SelfLearningTradingSystem()
    
    # 使用startup_manager.safe_start進行智能啟動（帶崩潰追蹤和退避）
    exit_code = await startup_manager.safe_start(system.run())
    return exit_code


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n程序已終止")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ 致命錯誤: {e}", exc_info=True)
        sys.exit(1)
