"""
主程序入口
職責：系統協調器、主循環控制
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import List, Dict, Optional

from src.config import Config
from src.clients.binance_client import BinanceClient
from src.services.data_service import DataService
from src.services.parallel_analyzer import ParallelAnalyzer
from src.services.timeframe_scheduler import SmartDataManager
from src.strategies.ict_strategy import ICTStrategy
from src.managers.risk_manager import RiskManager
from src.services.trading_service import TradingService
from src.managers.virtual_position_manager import VirtualPositionManager
from src.managers.trade_recorder import TradeRecorder
from src.integrations.discord_bot import TradingDiscordBot
from src.monitoring.health_monitor import HealthMonitor
from src.monitoring.performance_monitor import PerformanceMonitor
from src.ml.predictor import MLPredictor

logger = logging.getLogger(__name__)


class TradingBot:
    """交易機器人主類"""
    
    def __init__(self):
        """初始化交易機器人"""
        self.running = False
        
        self.binance_client: Optional[BinanceClient] = None
        self.data_service: Optional[DataService] = None
        self.smart_data_manager: Optional[SmartDataManager] = None
        self.parallel_analyzer: Optional[ParallelAnalyzer] = None
        self.strategy: Optional[ICTStrategy] = None
        self.risk_manager: Optional[RiskManager] = None
        self.trading_service: Optional[TradingService] = None
        self.virtual_position_manager: Optional[VirtualPositionManager] = None
        self.trade_recorder: Optional[TradeRecorder] = None
        self.discord_bot: Optional[TradingDiscordBot] = None
        self.health_monitor: Optional[HealthMonitor] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None
        self.ml_predictor: Optional[MLPredictor] = None
        
        self.discord_task = None
        self.monitoring_task = None
    
    async def initialize(self):
        """初始化系統"""
        logger.info("=" * 60)
        logger.info("🚀 Winiswin2 v1 Enhanced 啟動中...")
        logger.info("📌 代碼版本: 2025-10-25-v2.2 (流動性優選 + 優化策略條件)")
        logger.info("=" * 60)
        
        is_valid, errors = Config.validate()
        if not is_valid:
            logger.error("❌ 配置驗證失敗:")
            for error in errors:
                logger.error(f"  - {error}")
            logger.error("\n請在環境變數中設置以下變量:")
            logger.error("  - BINANCE_API_KEY")
            logger.error("  - BINANCE_API_SECRET")
            logger.error("  - DISCORD_TOKEN")
            return False
        
        logger.info("✅ 配置驗證通過")
        
        summary = Config.get_summary()
        logger.info("\n📋 系統配置:")
        for key, value in summary.items():
            logger.info(f"  {key}: {value}")
        
        logger.info("\n🔧 初始化核心組件...")
        
        self.binance_client = BinanceClient()
        
        connected = await self.binance_client.test_connection()
        if not connected:
            logger.error("❌ 無法連接到 Binance API")
            return False
        
        self.data_service = DataService(self.binance_client)
        await self.data_service.initialize()
        
        # 初始化智能數據管理器（差異化時間框架掃描）
        self.smart_data_manager = SmartDataManager(self.data_service)
        logger.info("✅ 智能數據管理器已就緒")
        logger.info("   - 1h: 每小時掃描（趨勢確認）")
        logger.info("   - 15m: 每15分鐘掃描（趨勢確認）")
        logger.info("   - 5m: 每分鐘掃描（入場信號）")
        
        # 初始化並行分析器（32 核心）
        self.parallel_analyzer = ParallelAnalyzer(max_workers=32)
        
        self.strategy = ICTStrategy()
        self.risk_manager = RiskManager()
        self.trading_service = TradingService(
            self.binance_client,
            self.risk_manager
        )
        self.virtual_position_manager = VirtualPositionManager()
        self.trade_recorder = TradeRecorder()
        
        # 初始化 ML 預測器
        self.ml_predictor = MLPredictor()
        ml_ready = await asyncio.to_thread(self.ml_predictor.initialize)
        if ml_ready:
            logger.info("✅ ML 預測器已就緒")
        else:
            logger.warning("⚠️  ML 預測器未就緒，使用傳統策略")
        
        self.discord_bot = TradingDiscordBot()
        self.discord_task = asyncio.create_task(self.discord_bot.start())
        await asyncio.sleep(2)
        
        self.health_monitor = HealthMonitor()
        self.performance_monitor = PerformanceMonitor()
        
        # 啟動性能監控任務
        self.monitoring_task = asyncio.create_task(
            self.performance_monitor.start_monitoring(interval=300)
        )
        
        if Config.BINANCE_API_KEY and Config.BINANCE_API_SECRET:
            try:
                account_info = await self.binance_client.get_account_info()
                balance = float(account_info.get('totalWalletBalance', 0))
                logger.info(f"💰 賬戶餘額: ${balance:.2f} USDT")
            except Exception as e:
                logger.warning(f"⚠️  無法獲取賬戶信息: {e}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ 系統初始化完成")
        logger.info("=" * 60)
        
        await self.discord_bot.send_alert(
            "🚀 交易系統已啟動\n"
            f"模式: {'測試網' if Config.BINANCE_TESTNET else '主網'}\n"
            f"交易: {'啟用' if Config.TRADING_ENABLED else '禁用'}",
            "info"
        )
        
        return True
    
    async def run_cycle(self):
        """執行一個交易週期"""
        cycle_start = datetime.now()
        logger.info(f"\n{'=' * 60}")
        logger.info(f"🔄 交易週期開始: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'=' * 60}")
        
        # 輸出時間框架調度狀態
        scheduler_status = self.smart_data_manager.get_scheduler_status()
        logger.info("⏰ 時間框架調度狀態:")
        for tf, status in scheduler_status.items():
            logger.info(
                f"  {tf}: 間隔={status['interval']}, "
                f"上次掃描={status['last_scan']}, "
                f"下次掃描={status['next_scan']}, "
                f"需掃描={'是' if status['should_scan'] else '否'}"
            )
        
        try:
            # 掃描市場（流動性優先排序，返回前N個）
            logger.info(f"🔍 開始掃描市場，目標選擇前 {Config.TOP_VOLATILITY_SYMBOLS} 個高流動性交易對...")
            
            market_data = await self.data_service.scan_market(
                top_n=Config.TOP_VOLATILITY_SYMBOLS
            )
            
            if market_data:
                avg_liquidity = sum(x.get('liquidity', 0) for x in market_data)/len(market_data)
                logger.info(
                    f"📊 ✅ 已選擇 {len(market_data)} 個高流動性交易對 "
                    f"(平均24h交易額: ${avg_liquidity:,.0f} USDT)"
                )
                # 顯示前10個流動性最高的交易對
                top_10 = market_data[:10]
                logger.info("📈 流動性最高的前10個交易對:")
                for i, data in enumerate(top_10, 1):
                    logger.info(
                        f"  #{i} {data['symbol']}: {data['price']:.4f} USDT "
                        f"(24h交易額: ${data.get('liquidity', 0):,.0f})"
                    )
            else:
                logger.warning("未獲取到任何交易對數據")
            
            # 使用並行分析器處理流動性最高的前200個標的（充分利用 32 核心）
            symbols_to_analyze = market_data
            logger.info(
                f"🔍 使用 32 核心並行分析 {len(symbols_to_analyze)} 個高流動性交易對 "
                f"(已按流動性排序)..."
            )
            
            signals = await self.parallel_analyzer.analyze_batch(
                symbols_to_analyze,
                self.smart_data_manager  # 使用智能數據管理器
            )
            
            # 記錄性能指標
            self.performance_monitor.total_signals_generated += len(signals)
            
            if signals:
                # ML 預測增強（如果可用）
                if self.ml_predictor and self.ml_predictor.is_ready:
                    logger.info("🤖 使用 ML 模型增強信號...")
                    for signal in signals:
                        ml_prediction = self.ml_predictor.predict(signal)
                        if ml_prediction:
                            signal['ml_prediction'] = ml_prediction
                            # 校準信心度
                            original_confidence = signal['confidence']
                            signal['confidence'] = self.ml_predictor.calibrate_confidence(
                                original_confidence,
                                ml_prediction
                            )
                            logger.debug(
                                f"  {signal['symbol']}: 原始 {original_confidence:.2%} "
                                f"→ ML校準 {signal['confidence']:.2%}"
                            )
                
                signals.sort(key=lambda x: x['confidence'], reverse=True)
                
                logger.info(f"\n🎯 生成 {len(signals)} 個交易信號")
                
                for rank, signal in enumerate(signals[:Config.MAX_SIGNALS], 1):
                    ml_info = ""
                    if 'ml_prediction' in signal:
                        ml_pred = signal['ml_prediction']
                        ml_info = f" [ML勝率: {ml_pred['win_probability']:.1%}]"
                    
                    logger.info(
                        f"  #{rank} {signal['symbol']} {signal['direction']} "
                        f"信心度 {signal['confidence']:.2%}{ml_info}"
                    )
                    
                    await self.discord_bot.send_signal_notification(signal, rank)
                    
                    await self._process_signal(signal, rank)
            
            else:
                logger.info("ℹ️  本週期未生成交易信號")
            
            await self._update_positions()
            
            await self._perform_health_check()
            
            self.health_monitor.record_api_call(success=True)
            
        except Exception as e:
            logger.error(f"❌ 週期執行錯誤: {e}", exc_info=True)
            self.health_monitor.record_api_call(success=False)
        
        cycle_end = datetime.now()
        duration = (cycle_end - cycle_start).total_seconds()
        logger.info(f"\n✅ 週期完成，耗時: {duration:.2f} 秒")
        logger.info(f"{'=' * 60}")
    
    async def _process_signal(self, signal: Dict, rank: int):
        """處理交易信號"""
        try:
            if rank <= Config.IMMEDIATE_EXECUTION_RANK:
                account_balance = 10000.0
                
                can_trade, reason = self.risk_manager.should_trade(
                    account_balance,
                    self.trading_service.get_active_positions_count()
                )
                
                if not can_trade:
                    logger.warning(f"⏸️  跳過交易: {reason}")
                    return
                
                stats = self.risk_manager.get_statistics()
                leverage = self.risk_manager.calculate_leverage(
                    win_rate=stats.get('win_rate', 0.5),
                    consecutive_losses=stats.get('consecutive_losses', 0),
                    current_drawdown=stats.get('current_drawdown', 0)
                )
                
                trade_result = await self.trading_service.execute_signal(
                    signal,
                    account_balance,
                    leverage
                )
                
                if trade_result:
                    await self.discord_bot.send_trade_notification(trade_result, 'open')
                    
                    position_info = {
                        'leverage': leverage,
                        'position_value': trade_result.get('position_value', 0)
                    }
                    self.trade_recorder.record_entry(signal, position_info)
            
            else:
                self.virtual_position_manager.add_virtual_position(signal, rank)
        
        except Exception as e:
            logger.error(f"處理信號失敗: {e}")
    
    async def _update_positions(self):
        """更新所有持倉"""
        try:
            tickers = await self.data_service.get_batch_tickers(
                self.data_service.all_symbols
            )
            
            market_prices = {
                symbol: float(ticker.get('price', 0))
                for symbol, ticker in tickers.items()
            }
            
            self.virtual_position_manager.update_virtual_positions(market_prices)
            
        except Exception as e:
            logger.error(f"更新持倉失敗: {e}")
    
    async def _perform_health_check(self):
        """執行健康檢查"""
        try:
            health_status = await self.health_monitor.check_system_health()
            
            if health_status['status'] != 'healthy':
                logger.warning(f"⚠️  系統健康狀態: {health_status['status']}")
                
                for check_name, check_result in health_status['checks'].items():
                    if not check_result.get('healthy', True):
                        logger.warning(f"  - {check_name}: {check_result.get('message')}")
            
            metrics = self.health_monitor.get_performance_metrics()
            logger.info(
                f"📊 系統狀態: CPU {metrics['cpu']['percent']:.1f}% | "
                f"內存 {metrics['memory']['percent']:.1f}% | "
                f"API 調用 {metrics['api']['total_calls']}"
            )
            
            stats = {
                'active_positions': self.trading_service.get_active_positions_count(),
                'virtual_positions': len(self.virtual_position_manager.get_active_virtual_positions()),
                **self.risk_manager.get_statistics(),
                'positions': self.trading_service.get_active_positions()
            }
            
            self.discord_bot.update_statistics(stats)
            
        except Exception as e:
            logger.error(f"健康檢查失敗: {e}")
    
    async def main_loop(self):
        """主循環"""
        self.running = True
        cycle_count = 0
        
        while self.running:
            try:
                cycle_count += 1
                logger.info(f"\n🔢 週期 #{cycle_count}")
                
                await self.run_cycle()
                
                logger.info(f"\n⏳ 等待 {Config.CYCLE_INTERVAL} 秒...")
                await asyncio.sleep(Config.CYCLE_INTERVAL)
                
            except asyncio.CancelledError:
                logger.info("主循環被取消")
                break
            except Exception as e:
                logger.error(f"主循環錯誤: {e}", exc_info=True)
                await asyncio.sleep(5)
        
        await self.cleanup()
    
    async def cleanup(self):
        """清理資源"""
        logger.info("\n🧹 清理資源...")
        
        if self.trade_recorder:
            self.trade_recorder.force_flush()
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        if self.parallel_analyzer:
            await self.parallel_analyzer.close()
        
        if self.discord_bot:
            await self.discord_bot.send_alert("👋 交易系統已停止", "info")
            await self.discord_bot.close()
        
        if self.discord_task:
            self.discord_task.cancel()
            try:
                await self.discord_task
            except asyncio.CancelledError:
                pass
        
        if self.binance_client:
            try:
                await self.binance_client.close()
                logger.info("✅ Binance 客戶端已關閉")
            except Exception as e:
                logger.error(f"關閉 Binance 客戶端時出錯: {e}")
        
        logger.info("👋 系統已停止")
    
    def handle_signal(self, signum, frame):
        """處理系統信號"""
        logger.info(f"\n收到信號 {signum}")
        self.running = False


async def main():
    """主函數"""
    Config.setup_logging()
    
    bot = TradingBot()
    
    signal.signal(signal.SIGINT, bot.handle_signal)
    signal.signal(signal.SIGTERM, bot.handle_signal)
    
    if await bot.initialize():
        await bot.main_loop()
    else:
        logger.error("初始化失敗，退出程序")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n收到中斷信號，正在退出...")
    except Exception as e:
        logger.error(f"程序異常退出: {e}", exc_info=True)
        sys.exit(1)
