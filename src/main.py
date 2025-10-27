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
from src.managers.expectancy_calculator import ExpectancyCalculator
from src.services.trading_service import TradingService
from src.managers.virtual_position_manager import VirtualPositionManager
from src.managers.trade_recorder import TradeRecorder
from src.integrations.discord_bot import TradingDiscordBot
from src.monitoring.health_monitor import HealthMonitor
from src.monitoring.performance_monitor import PerformanceMonitor
from src.ml.predictor import MLPredictor
from src.ml.data_archiver import DataArchiver
from src.services.position_monitor import PositionMonitor

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
        self.expectancy_calculator: Optional[ExpectancyCalculator] = None
        self.data_archiver: Optional[DataArchiver] = None
        self.trading_service: Optional[TradingService] = None
        self.virtual_position_manager: Optional[VirtualPositionManager] = None
        self.trade_recorder: Optional[TradeRecorder] = None
        self.discord_bot: Optional[TradingDiscordBot] = None
        self.health_monitor: Optional[HealthMonitor] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None
        self.ml_predictor: Optional[MLPredictor] = None
        self.position_monitor: Optional[PositionMonitor] = None
        
        self.discord_task = None
        self.monitoring_task = None
    
    async def initialize(self):
        """初始化系統"""
        logger.info("=" * 60)
        logger.info("🚀 高頻交易系統 v3.0 啟動中...")
        logger.info("📌 代碼版本: 2025-10-25-v3.0 (期望值驅動+五維評分系統)")
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
        self.expectancy_calculator = ExpectancyCalculator(window_size=Config.EXPECTANCY_WINDOW)
        self.data_archiver = DataArchiver(data_dir=Config.ML_DATA_DIR)
        logger.info(f"✅ 期望值計算器已就緒 (窗口大小: {Config.EXPECTANCY_WINDOW} 筆交易)")
        logger.info(f"✅ 數據歸檔器已就緒 (目錄: {Config.ML_DATA_DIR})")
        
        self.trade_recorder = TradeRecorder()
        
        def on_virtual_position_close(position_data: Dict, close_data: Dict):
            """虛擬倉位關閉回調：記錄平倉數據到 TradeRecorder 和 DataArchiver"""
            try:
                signal_format = {
                    'symbol': position_data['symbol'],
                    'direction': position_data['direction'],
                    'entry_price': position_data['entry_price'],
                    'confidence': position_data['confidence'],
                    'timestamp': datetime.fromisoformat(position_data['entry_timestamp']),
                    'timeframes': {},
                    'market_structure': 'neutral',
                    'order_blocks': 0,
                    'liquidity_zones': 0,
                    'indicators': {}
                }
                
                position_info = {
                    'leverage': 1,
                    'position_value': 0,
                }
                
                self.trade_recorder.record_entry(signal_format, position_info)
                
                trade_result = {
                    'symbol': close_data['symbol'],
                    'exit_price': close_data['exit_price'],
                    'pnl': close_data['pnl'],
                    'pnl_pct': close_data['pnl_pct'],
                    'close_reason': close_data['close_reason'],
                    'close_timestamp': close_data['timestamp'],
                }
                
                ml_record = self.trade_recorder.record_exit(trade_result)
                
                if ml_record:
                    self.data_archiver.archive_position_close(
                        position_data=position_data,
                        close_data=close_data,
                        is_virtual=True
                    )
                    logger.info(f"✅ 虛擬倉位平倉數據已記錄到 ML 訓練集: {close_data['symbol']} PnL: {close_data['pnl']:+.2%}")
                
            except Exception as e:
                logger.error(f"虛擬倉位關閉回調失敗: {e}", exc_info=True)
        
        self.virtual_position_manager = VirtualPositionManager(on_close_callback=on_virtual_position_close)
        
        # 初始化交易服務（傳入trade_recorder）
        self.trading_service = TradingService(
            self.binance_client,
            self.risk_manager,
            self.trade_recorder
        )
        
        # 初始化持仓监控器（动态止损止盈）
        self.position_monitor = PositionMonitor(
            self.binance_client,
            self.trading_service,
            self.data_archiver
        )
        
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
            # === 持仓监控：动态调整止损止盈 ===
            logger.info("👁️  監控活躍持倉...")
            position_stats = await self.position_monitor.monitor_all_positions()
            if position_stats['total'] > 0:
                logger.info(
                    f"📊 持倉統計: 總計={position_stats['total']}, "
                    f"盈利={position_stats['in_profit']}, "
                    f"虧損={position_stats['in_loss']}, "
                    f"已調整={position_stats['adjusted']}"
                )
                if position_stats['adjusted'] > 0:
                    logger.info(f"🔄 本週期調整了 {position_stats['adjusted']} 個持倉的止損止盈")
            else:
                logger.debug("當前無活躍持倉")
            
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
                logger.info(f"ℹ️  本週期未生成交易信號 (分析了 {len(symbols_to_analyze)} 個交易對)")
                logger.info("💡 提示：設置 LOG_LEVEL=DEBUG 查看拒絕原因詳情")
            
            await self._update_positions()
            
            await self._perform_health_check()
            
            self.health_monitor.record_api_call(success=True)
            
            if self.data_archiver:
                self.data_archiver.flush_all()
                logger.debug("✅ 數據已刷新到磁盤")
            
        except Exception as e:
            logger.error(f"❌ 週期執行錯誤: {e}", exc_info=True)
            self.health_monitor.record_api_call(success=False)
        
        cycle_end = datetime.now()
        duration = (cycle_end - cycle_start).total_seconds()
        logger.info(f"\n✅ 週期完成，耗時: {duration:.2f} 秒")
        logger.info(f"{'=' * 60}")
    
    async def _process_signal(self, signal: Dict, rank: int):
        """處理交易信號（期望值驅動版本）"""
        try:
            # 使用TradeRecorder的完成交易（包含pnl）而不是all_trades
            completed_trades = self.trade_recorder.get_all_completed_trades()
            expectancy_metrics = self.expectancy_calculator.calculate_expectancy(completed_trades)
            
            can_trade, rejection_reason = self.expectancy_calculator.should_trade(
                expectancy=expectancy_metrics['expectancy'],
                profit_factor=expectancy_metrics['profit_factor'],
                consecutive_losses=expectancy_metrics['consecutive_losses'],
                daily_loss_pct=self.expectancy_calculator.get_daily_loss(completed_trades),
                total_trades=expectancy_metrics['total_trades']  # 傳入總交易數用於冷啟動判斷
            )
            
            if not can_trade:
                logger.warning(f"🚫 期望值檢查拒絕: {rejection_reason}")
                self.data_archiver.archive_signal(
                    signal_data=signal,
                    accepted=False,
                    rejection_reason=rejection_reason
                )
                return
            
            if rank <= Config.IMMEDIATE_EXECUTION_RANK:
                # 自動從 Binance 獲取 U 本位合約餘額
                try:
                    balance_info = await self.binance_client.get_account_balance()
                    account_balance = balance_info['total_balance']
                    logger.info(
                        f"💰 使用實時餘額: {account_balance:.2f} USDT "
                        f"(可用: {balance_info['available_balance']:.2f} USDT)"
                    )
                except Exception as e:
                    logger.error(f"獲取賬戶餘額失敗: {e}，使用默認值")
                    account_balance = 10000.0  # 降級為默認值
                
                # 🎯 關鍵修復：虛擬倉位不占據實際倉位限制
                # - 實際倉位上限：3個（只在TRADING_ENABLED=true時檢查）
                # - 虛擬倉位：無限制（供XGBoost學習）
                can_trade_risk, reason = self.risk_manager.should_trade(
                    account_balance,
                    self.trading_service.get_active_positions_count(),
                    is_real_trading=Config.TRADING_ENABLED  # 只有真實交易才檢查倉位限制
                )
                
                if not can_trade_risk:
                    logger.warning(f"⏸️  風險管理拒絕: {reason}")
                    self.data_archiver.archive_signal(
                        signal_data=signal,
                        accepted=False,
                        rejection_reason=reason
                    )
                    return
                
                leverage = self.risk_manager.calculate_leverage(
                    expectancy=expectancy_metrics['expectancy'],
                    profit_factor=expectancy_metrics['profit_factor'],
                    consecutive_losses=expectancy_metrics['consecutive_losses']
                )
                
                if leverage == 0:
                    logger.warning("🚫 期望值為負，禁止開倉")
                    self.data_archiver.archive_signal(
                        signal_data=signal,
                        accepted=False,
                        rejection_reason="期望值為負"
                    )
                    return
                
                logger.info(
                    f"✅ 期望值檢查通過 - "
                    f"期望值: {expectancy_metrics['expectancy']:.2f}%, "
                    f"盈虧比: {expectancy_metrics['profit_factor']:.2f}, "
                    f"建議槓桿: {leverage}x"
                )
                
                self.data_archiver.archive_signal(signal_data=signal, accepted=True)
                
                trade_result = await self.trading_service.execute_signal(
                    signal,
                    account_balance,
                    leverage
                )
                
                if trade_result:
                    await self.discord_bot.send_trade_notification(trade_result, 'open')
                    
                    # 注意：record_entry已在trading_service.execute_signal中調用
                    # 不需要重複調用
                    
                    position_info = {
                        'leverage': leverage,
                        'position_value': trade_result.get('position_value', 0),
                        **signal
                    }
                    
                    self.data_archiver.archive_position_open(
                        position_data=position_info,
                        is_virtual=False
                    )
            
            else:
                self.data_archiver.archive_signal(signal_data=signal, accepted=True)
                self.virtual_position_manager.add_virtual_position(signal, rank)
                
                position_info = {**signal, 'rank': rank}
                self.data_archiver.archive_position_open(
                    position_data=position_info,
                    is_virtual=True
                )
        
        except Exception as e:
            logger.error(f"處理信號失敗: {e}", exc_info=True)
    
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
            
            # ✨ 檢查模擬持倉並自動平倉（修復學習模式）
            if not Config.TRADING_ENABLED:
                closed_count = await self.trading_service.check_simulated_positions_for_close()
                if closed_count > 0:
                    logger.info(f"🎮 本週期模擬平倉: {closed_count} 筆")
            
            # 🔄 檢查是否需要重訓練XGBoost模型（每累積50筆新交易）
            if self.ml_predictor and self.ml_predictor.is_ready:
                retrained = await asyncio.to_thread(
                    self.ml_predictor.check_and_retrain_if_needed
                )
                if retrained:
                    await self.discord_bot.send_alert(
                        "🎯 XGBoost模型已完成重訓練\n"
                        "使用最新交易數據更新模型",
                        "success"
                    )
            
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
        
        if self.data_archiver:
            logger.info("💾 刷新所有數據到磁盤...")
            self.data_archiver.flush_all()
        
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
