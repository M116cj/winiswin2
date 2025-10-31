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

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Optional

from src.config import Config
from src.clients.binance_client import BinanceClient
from src.services.data_service import DataService
from src.core.unified_scheduler import UnifiedScheduler
from src.managers.trade_recorder import TradeRecorder
from src.core.model_evaluator import ModelEvaluator
from src.core.model_initializer import ModelInitializer

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class SelfLearningTradingSystem:
    """
    SelfLearningTrader v3.17+ 交易系統
    
    職責：
    1. 系統初始化
    2. 啟動 UnifiedScheduler
    3. 優雅關閉
    """
    
    def __init__(self):
        """初始化系統"""
        self.running = False
        self.config = Config  # Config類本身（類級別配置）
        
        # 核心組件
        self.binance_client: Optional[BinanceClient] = None
        self.data_service: Optional[DataService] = None
        self.trade_recorder: Optional[TradeRecorder] = None
        self.model_evaluator: Optional[ModelEvaluator] = None  # v3.17.10+
        self.model_initializer: Optional[ModelInitializer] = None  # v3.17.10+
        self.scheduler: Optional[UnifiedScheduler] = None
    
    async def initialize(self):
        """初始化所有組件"""
        try:
            logger.info("=" * 80)
            logger.info("🚀 SelfLearningTrader v3.17+ 啟動中...")
            logger.info("📌 核心理念: 模型擁有無限制槓桿控制權，唯一準則是勝率 × 信心度")
            logger.info("=" * 80)
            
            # 驗證配置
            is_valid, errors = self.config.validate()
            if not is_valid:
                logger.error("❌ 配置驗證失敗:")
                for error in errors:
                    logger.error(f"  - {error}")
                return False
            
            logger.info("✅ 配置驗證通過")
            
            # 顯示配置
            self._display_config()
            
            # 初始化核心組件
            logger.info("\n🔧 初始化核心組件...")
            
            # Binance 客戶端
            self.binance_client = BinanceClient()
            
            # 測試連接（非阻塞，帶指數退避重試）
            connection_ok = await self._test_connection_with_retry(
                max_retries=3,
                initial_delay=5
            )
            
            if connection_ok:
                logger.info("✅ Binance 客戶端已連接")
            else:
                logger.warning("⚠️ API連接測試未通過，將在實際調用時重試")
                logger.warning("⚠️ 系統將繼續初始化，實際API調用將由熔斷器保護")
            
            # 數據服務（v3.17.2+：預留websocket_monitor，稍後設置）
            self.data_service = DataService(
                binance_client=self.binance_client,
                websocket_monitor=None  # 🔥 v3.17.2+：將在UnifiedScheduler創建後設置
            )
            
            # 🔥 重要：初始化 DataService（加載所有交易對）
            await self.data_service.initialize()
            logger.info("✅ 數據服務初始化完成")
            
            # 交易記錄器
            self.trade_recorder = TradeRecorder()
            logger.info("✅ 交易記錄器初始化完成")
            
            # 🔥 v3.17.10+：模型評估器（用於特徵重要性分析）
            self.model_evaluator = ModelEvaluator(
                config=self.config,
                reports_dir=self.config.REPORTS_DIR
            )
            logger.info("✅ 模型評估器初始化完成（v3.17.10+）")
            
            # 🔥 v3.17.10+：模型初始化器（動態重訓練觸發）
            self.model_initializer = ModelInitializer(
                binance_client=self.binance_client,
                trade_recorder=self.trade_recorder,
                config_profile=self.config,
                model_evaluator=self.model_evaluator
            )
            logger.info("✅ 模型初始化器已創建（v3.17.10+）")
            
            # UnifiedScheduler（核心調度器）
            self.scheduler = UnifiedScheduler(
                config=self.config,  # type: ignore  # Config類級別配置
                binance_client=self.binance_client,
                data_service=self.data_service,
                trade_recorder=self.trade_recorder,
                model_initializer=self.model_initializer  # 🔥 v3.17.10+
            )
            logger.info("✅ UnifiedScheduler 初始化完成")
            
            # 🔥 v3.17.2+：將websocket_monitor設置到DataService（降低REST API使用）
            self.data_service.websocket_monitor = self.scheduler.websocket_manager
            logger.info("✅ DataService已連接WebSocket（優先使用WebSocket數據）")
            
            logger.info("\n✅ 所有核心組件初始化完成")
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
        """顯示當前配置"""
        logger.info("\n📋 系統配置:")
        logger.info(f"  version: v3.17+")
        logger.info(f"  binance_testnet: {self.config.BINANCE_TESTNET}")
        logger.info(f"  trading_enabled: {self.config.TRADING_ENABLED}")
        logger.info(f"  cycle_interval: {self.config.CYCLE_INTERVAL}")
        logger.info(f"  min_confidence: {self.config.MIN_CONFIDENCE * 100:.1f}%")
        logger.info(f"  log_level: {self.config.LOG_LEVEL}")
        logger.info(f"  note: 使用 SelfLearningTrader 無限制槓桿控制，無持倉上限")
        
        # 顯示 SelfLearningTrader 特性
        logger.info("\n🎯 SelfLearningTrader v3.17+ 特性:")
        logger.info("  ✅ 無限制槓桿（基於勝率 × 信心度）")
        logger.info("  ✅ 10 USDT 最小倉位（符合 Binance 規格）")
        logger.info("  ✅ 動態 SL/TP（高槓桿 → 寬止損）")
        logger.info("  ✅ 24/7 倉位監控（2 秒週期）")
        logger.info("  ✅ 100% 虧損熔斷（PnL ≤ -99% 立即平倉）")
        logger.info("  ✅ 100 分制模型評級（6 大維度 + 懲罰）")
        logger.info("  ✅ 每日自動報告（JSON + Markdown）")
    
    async def run(self):
        """啟動系統"""
        try:
            # 初始化
            if not await self.initialize():
                logger.error("初始化失敗，退出程序")
                return
            
            # 設置信號處理
            self._setup_signal_handlers()
            
            # 啟動 UnifiedScheduler
            self.running = True
            logger.info("\n🚀 啟動 UnifiedScheduler...")
            if self.scheduler:  # 類型檢查
                await self.scheduler.start()
            
        except KeyboardInterrupt:
            logger.info("\n⏸️  收到中斷信號，正在關閉...")
        except Exception as e:
            logger.error(f"❌ 系統運行失敗: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """優雅關閉系統"""
        try:
            logger.info("\n🔄 系統關閉中...")
            self.running = False
            
            # 停止 UnifiedScheduler
            if self.scheduler:
                await self.scheduler.stop()
            
            # 關閉 Binance 客戶端
            if self.binance_client:
                await self.binance_client.close()
            
            # 🔥 v3.18.4-hotfix: 強制保存ML訓練數據（防止數據丟失）
            if self.trade_recorder:
                logger.info("💾 正在保存ML訓練數據...")
                self.trade_recorder.force_flush()
                logger.info("✅ ML訓練數據已保存")
            
            logger.info("✅ 系統已安全關閉")
            
        except Exception as e:
            logger.error(f"❌ 關閉失敗: {e}", exc_info=True)
    
    def _setup_signal_handlers(self):
        """設置信號處理器"""
        def signal_handler(sig, frame):
            logger.info(f"\n收到信號 {sig}，準備關閉...")
            if self.running:
                asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """主函數"""
    system = SelfLearningTradingSystem()
    await system.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n程序已終止")
    except Exception as e:
        logger.error(f"❌ 致命錯誤: {e}", exc_info=True)
        sys.exit(1)
