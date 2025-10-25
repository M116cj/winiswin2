"""
主程序入口
職責：系統協調器、主循環控制
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime

from src.config import Config
from src.clients.binance_client import BinanceClient

logger = logging.getLogger(__name__)

class TradingBot:
    """交易機器人主類"""
    
    def __init__(self):
        self.running = False
        self.binance_client: BinanceClient = None
    
    async def initialize(self):
        """初始化系統"""
        logger.info("="*60)
        logger.info("🚀 Winiswin2 v1 Enhanced 啟動中...")
        logger.info("="*60)
        
        # 驗證配置
        is_valid, errors = Config.validate()
        if not is_valid:
            logger.error("❌ 配置驗證失敗:")
            for error in errors:
                logger.error(f"  - {error}")
            logger.error("\n請在 Replit Secrets 中設置以下環境變量:")
            logger.error("  - BINANCE_API_KEY")
            logger.error("  - BINANCE_API_SECRET")
            logger.error("  - DISCORD_TOKEN")
            return False
        
        logger.info("✅ 配置驗證通過")
        
        # 顯示配置摘要
        summary = Config.get_summary()
        logger.info("\n📋 系統配置:")
        for key, value in summary.items():
            logger.info(f"  {key}: {value}")
        
        # 初始化 Binance 客戶端
        logger.info("\n🔌 初始化 Binance 客戶端...")
        self.binance_client = BinanceClient()
        
        # 測試連接
        connected = await self.binance_client.test_connection()
        if not connected:
            logger.error("❌ 無法連接到 Binance API")
            return False
        
        # 獲取賬戶信息（如果有 API 密鑰）
        if Config.BINANCE_API_KEY and Config.BINANCE_API_SECRET:
            try:
                account_info = await self.binance_client.get_account_info()
                balance = float(account_info.get('totalWalletBalance', 0))
                logger.info(f"💰 賬戶餘額: ${balance:.2f} USDT")
            except Exception as e:
                logger.warning(f"⚠️  無法獲取賬戶信息: {e}")
        
        # 獲取交易對列表
        logger.info("\n📊 獲取交易對列表...")
        symbols = await self.binance_client.get_all_usdt_symbols()
        logger.info(f"✅ 找到 {len(symbols)} 個 USDT 永續合約")
        
        logger.info("\n" + "="*60)
        logger.info("✅ 系統初始化完成")
        logger.info("="*60)
        
        return True
    
    async def run_cycle(self):
        """執行一個交易週期"""
        cycle_start = datetime.now()
        logger.info(f"\n{'='*60}")
        logger.info(f"🔄 交易週期開始: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}")
        
        try:
            # 這裡將實現完整的交易邏輯
            # 目前只做基本的測試
            
            # 測試獲取價格
            symbols = await self.binance_client.get_all_usdt_symbols()
            sample_symbols = symbols[:5]
            
            logger.info(f"\n📈 獲取前 5 個交易對價格:")
            for symbol in sample_symbols:
                try:
                    price_data = await self.binance_client.get_ticker_price(symbol)
                    price = float(price_data['price'])
                    logger.info(f"  {symbol}: ${price:.4f}")
                except Exception as e:
                    logger.error(f"  {symbol}: 獲取失敗 - {e}")
            
            # 顯示緩存統計
            cache_stats = self.binance_client.cache.get_stats()
            logger.info(f"\n💾 緩存統計: {cache_stats}")
            
            # 顯示限流統計
            rate_stats = self.binance_client.rate_limiter.get_stats()
            logger.info(f"⏱️  限流統計: {rate_stats}")
            
        except Exception as e:
            logger.error(f"❌ 週期執行錯誤: {e}", exc_info=True)
        
        cycle_end = datetime.now()
        duration = (cycle_end - cycle_start).total_seconds()
        logger.info(f"\n✅ 週期完成，耗時: {duration:.2f} 秒")
        logger.info(f"{'='*60}")
    
    async def main_loop(self):
        """主循環"""
        self.running = True
        cycle_count = 0
        
        while self.running:
            try:
                cycle_count += 1
                logger.info(f"\n第 {cycle_count} 個週期")
                
                await self.run_cycle()
                
                # 等待下一個週期
                logger.info(f"\n⏳ 等待 {Config.CYCLE_INTERVAL} 秒...")
                await asyncio.sleep(Config.CYCLE_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("\n⚠️  收到中斷信號")
                break
            except Exception as e:
                logger.error(f"❌ 主循環錯誤: {e}", exc_info=True)
                await asyncio.sleep(5)
        
        await self.cleanup()
    
    async def cleanup(self):
        """清理資源"""
        logger.info("\n🧹 清理資源...")
        
        if self.binance_client:
            await self.binance_client.close()
        
        logger.info("👋 系統已停止")
    
    def handle_signal(self, signum, frame):
        """處理系統信號"""
        logger.info(f"\n收到信號 {signum}")
        self.running = False

async def main():
    """主函數"""
    # 設置日誌
    Config.setup_logging()
    
    # 創建機器人實例
    bot = TradingBot()
    
    # 設置信號處理
    signal.signal(signal.SIGINT, bot.handle_signal)
    signal.signal(signal.SIGTERM, bot.handle_signal)
    
    # 初始化
    success = await bot.initialize()
    if not success:
        logger.error("初始化失敗，退出程序")
        sys.exit(1)
    
    # 運行主循環
    try:
        await bot.main_loop()
    except Exception as e:
        logger.error(f"致命錯誤: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
