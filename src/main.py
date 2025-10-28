"""
主程序入口
職責：系統協調器、主循環控制

v3.13.0 全面轻量化：
- ✅ 异步批量更新虚拟仓位（asyncio.gather + aiofiles，200个仓位：20+秒→<1秒）
- ✅ 内存优化（__slots__ for OperationTimer, StateConfig）
- ✅ 线程安全异步化（threading.Lock替代asyncio.Lock）
- ✅ 全局进程池集成（复用进程，减少创建/销毁开销）
- ✅ 双循环架构：实盘交易循环60秒 + 虚拟仓位循环10秒
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
from src.strategies.strategy_factory import StrategyFactory
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
from typing import Any

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
        self.strategy: Optional[Any] = None
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
        
        # v3.13.0：异步虚拟仓位循环任务
        self.virtual_loop_task: Optional[asyncio.Task] = None  # 修复LSP类型错误
    
    async def initialize(self):
        """初始化系統"""
        logger.info("=" * 60)
        logger.info("🚀 高頻交易系統 v3.16.0 啟動中...")
        logger.info("📌 代碼版本: v3.16.0 (3大高级功能 - 市场状态预测器+动态特征生成+流动性狩猎)")
        logger.info("=" * 60)
        
        # 📊 显示评分系统说明
        logger.info("\n📊 五維ICT評分系統（v3.10.0增強版）：")
        logger.info("  1️⃣ 趨勢對齊 (40%) - 三時間框架EMA對齊")
        logger.info("     LONG: price > EMA | SHORT: price < EMA ✅ 對稱")
        logger.info("  2️⃣ 市場結構 (20%) - 結構與趨勢匹配度")
        logger.info("     bullish+bullish | bearish+bearish ✅ 對稱")
        logger.info("  3️⃣ 價格位置 (20%) - 距離Order Block的ATR距離")
        logger.info("     LONG/SHORT使用對稱的ATR距離評分 ✅ 對稱")
        logger.info("  4️⃣ 動量指標 (10%) - RSI + MACD同向確認")
        logger.info("     RSI: 50-70 (LONG) | 30-50 (SHORT) ✅ 對稱於50中線")
        logger.info("  5️⃣ 波動率 (10%) - 布林帶寬度分位數")
        logger.info("     LONG/SHORT使用相同的波動率標準 ✅ 對稱")
        logger.info("\n🎯 評分系統特點：")
        logger.info("  ✅ LONG/SHORT完全對稱，無方向偏向")
        logger.info("  ✅ 信心度範圍：35%-100%（MIN_CONFIDENCE=35%）🚨 已降低阈值")
        logger.info("  ✅ 五大維度綜合評分，確保信號品質")
        logger.info("  🚨 v3.9.2.3: 强制止损保护（-50%/-80%）")
        logger.info("  🎯 v3.9.2.5: ML反弹预测 + 智能平仓决策")
        logger.info("  🤖 v3.9.2.6: ML主动分析 + 正确PnL计算")
        logger.info("  📊 v3.9.2.7: ML实际胜率监控 + 性能优化")
        logger.info("  🚨 v3.9.2.8.4: 分級熔斷器（三級熔斷+Bypass機制）")
        logger.info("  🎯 v3.9.2.8.5: 模型評分系統（加權評分算法 - PnL 50% + 置信度 30% + 胜率 20%）")
        logger.info("  ⚡ v3.9.2.9: 性能優化（動態CPU檢測 + 臨時文件清理 + zero_division標準化）")
        logger.info("  🔥 v3.10.0: 策略增強三合一（ADX趨勢過濾 + ML泄漏阻斷 + 波動率熔斷）")
        logger.info("  🎯 v3.11.0: 高級優化（OB質量篩選+BOS/CHOCH+市場狀態分類+反轉預警）")
        logger.info("  🚀 v3.11.1: 移除持倉限制（允許無限同時持倉）")
        logger.info("  ⚡ v3.12.0: 性能優化五合一（進程池+增量緩存+批量ML+ONNX+雙循環，週期時間↓40%）")
        logger.info("  🚀 v3.13.0: 全面轻量化（异步批量更新+12项优化+内存↓30%+代码↓20%）")
        logger.info("  ✨ v3.14.0: 混合智能系统（策略工厂+深度学习+生命周期监控）")
        logger.info("  ⚡ v3.15.0: 5大性能优化（TFLite量化+增量缓存+批量预测+记忆体映射+智能监控）")
        logger.info("  🔥 v3.16.0: 3大高级功能（市场状态预测器+动态特征生成+流动性狩猎器）\n")
        
        # 🔥 v3.16.0 配置状态
        logger.info("\n🔥 v3.16.0 性能模块状态：")
        logger.info(f"  🎯 市场状态预测器: {'✅ 启用' if Config.ENABLE_MARKET_REGIME_PREDICTION else '⚪ 禁用 (默认)'}")
        logger.info(f"  🔧 动态特征生成器: {'✅ 启用' if Config.ENABLE_DYNAMIC_FEATURES else '⚪ 禁用 (默认)'}")
        logger.info(f"  🎣 流动性狩猎器: {'✅ 启用' if Config.ENABLE_LIQUIDITY_HUNTING else '⚪ 禁用 (默认)'}")
        logger.info("  💡 提示: 默认全部禁用，可通过环境变量启用新功能\n")
        
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
        
        self.strategy = StrategyFactory.create_strategy(Config)
        self.risk_manager = RiskManager()
        
        # 📊 输出风险管理状态
        self.risk_manager.log_risk_status()
        
        self.expectancy_calculator = ExpectancyCalculator(window_size=Config.EXPECTANCY_WINDOW)
        self.data_archiver = DataArchiver(data_dir=Config.ML_DATA_DIR)
        logger.info(f"✅ 期望值計算器已就緒 (窗口大小: {Config.EXPECTANCY_WINDOW} 筆交易)")
        logger.info(f"✅ 數據歸檔器已就緒 (目錄: {Config.ML_DATA_DIR})")
        
        # 🎯 v3.9.2.8.5: 初始化模型评分系统
        from src.managers.model_scorer import ModelScorer
        self.model_scorer = ModelScorer(history_limit=100)
        
        self.trade_recorder = TradeRecorder(model_scorer=self.model_scorer)
        
        def on_virtual_position_open(signal: Dict, position: Dict, rank: int):
            """虛擬倉位開倉回調：記錄開倉數據到 TradeRecorder"""
            try:
                signal_format = {
                    'symbol': signal['symbol'],
                    'direction': signal['direction'],
                    'entry_price': signal['entry_price'],
                    'confidence': signal['confidence'],
                    'timestamp': datetime.fromisoformat(position['entry_timestamp']),
                    'timeframes': position.get('timeframes', {}),
                    'market_structure': position.get('market_structure', 'neutral'),
                    'order_blocks': position.get('order_blocks', 0),
                    'liquidity_zones': position.get('liquidity_zones', 0),
                    'indicators': position.get('indicators', {})
                }
                
                position_info = {
                    'leverage': 1,
                    'position_value': 0,
                }
                
                self.trade_recorder.record_entry(signal_format, position_info)
                logger.debug(f"📝 已記錄虛擬倉位開倉: {signal['symbol']}")
                
            except Exception as e:
                logger.error(f"虛擬倉位開倉回調失敗: {e}", exc_info=True)
        
        def on_virtual_position_close(position_data: Dict, close_data: Dict):
            """虛擬倉位關閉回調：記錄平倉數據到 TradeRecorder 和 DataArchiver"""
            try:
                trade_result = {
                    'symbol': close_data['symbol'],
                    'exit_price': close_data['exit_price'],
                    'pnl': close_data['pnl'],
                    'pnl_pct': close_data['pnl_pct'],
                    'close_reason': close_data['close_reason'],
                    'close_timestamp': close_data['close_timestamp'],
                }
                
                # 获取当前胜率
                current_winrate = None
                if self.ml_predictor:
                    try:
                        from src.managers.risk_manager import RiskManager
                        recent_stats = self.ml_predictor.get_recent_win_rate(window=30)
                        if recent_stats:
                            current_winrate = recent_stats.get('win_rate', 0) * 100  # 转换为百分比
                    except:
                        pass
                
                ml_record = self.trade_recorder.record_exit(trade_result, current_winrate=current_winrate)
                
                if ml_record:
                    self.data_archiver.archive_position_close(
                        position_data=position_data,
                        close_data=close_data,
                        is_virtual=True
                    )
                    logger.info(f"✅ 虛擬倉位平倉數據已記錄到 ML 訓練集: {close_data['symbol']} PnL: {close_data['pnl']:+.2%}")
                
            except Exception as e:
                logger.error(f"虛擬倉位關閉回調失敗: {e}", exc_info=True)
        
        self.virtual_position_manager = VirtualPositionManager(
            on_open_callback=on_virtual_position_open,
            on_close_callback=on_virtual_position_close
        )
        
        # 初始化交易服務（傳入trade_recorder）
        self.trading_service = TradingService(
            self.binance_client,
            self.risk_manager,
            self.trade_recorder
        )
        
        # 初始化 ML 預測器（必須在position_monitor之前）🎯 v3.9.2.5
        # 🎯 v3.9.2.7: 传入trade_recorder以使用实际胜率
        self.ml_predictor = MLPredictor(trade_recorder=self.trade_recorder)
        ml_ready = await asyncio.to_thread(self.ml_predictor.initialize)
        if ml_ready:
            logger.info("✅ ML 預測器已就緒（含实际胜率监控）")
        else:
            logger.warning("⚠️  ML 預測器未就緒，使用傳統策略")
        
        # 初始化持仓监控器（动态止损止盈）🎯 v3.9.2.5：添加ML反弹预测
        # 🎯 v3.9.2.7增强：添加虚拟仓位监控
        self.position_monitor = PositionMonitor(
            self.binance_client,
            self.trading_service,
            self.data_archiver,
            self.ml_predictor,  # 🎯 v3.9.2.5新增：ML辅助持仓监控
            self.virtual_position_manager  # 🎯 v3.9.2.7新增：虚拟仓位监控
        )
        
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
        
        # 類型檢查：確保所有核心組件已初始化（解決LSP Optional類型警告）
        assert self.binance_client is not None
        assert self.data_service is not None
        assert self.smart_data_manager is not None
        assert self.parallel_analyzer is not None
        assert self.strategy is not None
        assert self.risk_manager is not None
        assert self.expectancy_calculator is not None
        assert self.data_archiver is not None
        assert self.trading_service is not None
        assert self.virtual_position_manager is not None
        assert self.trade_recorder is not None
        assert self.discord_bot is not None
        assert self.health_monitor is not None
        assert self.performance_monitor is not None
        assert self.ml_predictor is not None
        assert self.position_monitor is not None
        
        return True
    
    async def run_cycle(self):
        """執行一個交易週期"""
        cycle_start = datetime.now()
        logger.info(f"\n{'=' * 60}")
        logger.info(f"🔄 交易週期開始: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'=' * 60}")
        
        # 📚 顯示訓練數據統計
        if self.data_archiver:
            try:
                from pathlib import Path
                import pandas as pd
                
                signals_file = Path('ml_data/signals.csv')
                positions_file = Path('ml_data/positions.csv')
                
                total_positions = 0
                virtual_positions = 0
                real_positions = 0
                
                if positions_file.exists():
                    positions_df = pd.read_csv(positions_file)
                    total_positions = len(positions_df[positions_df['event'] == 'close'])
                    # 根據is_simulated欄位區分虛擬和真實倉位
                    if 'is_simulated' in positions_df.columns:
                        virtual_positions = len(positions_df[(positions_df['event'] == 'close') & (positions_df['is_simulated'] == True)])
                        real_positions = len(positions_df[(positions_df['event'] == 'close') & (positions_df['is_simulated'] == False)])
                    else:
                        virtual_positions = total_positions  # 如果沒有欄位，假設都是虛擬的
                
                logger.info(
                    f"📚 模型訓練數據: {total_positions}筆 "
                    f"(虛擬倉位: {virtual_positions}筆 | 真實倉位: {real_positions}筆)"
                )
            except Exception as e:
                logger.debug(f"讀取訓練數據統計失敗: {e}")
        
        # 📊 每个周期显示风险管理状态
        self.risk_manager.log_risk_status()
        
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
                    f"📊 已選擇 {len(market_data)} 個高流動性交易對 "
                    f"(平均24h交易額: ${avg_liquidity:,.0f} USDT)"
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
                # 🔥 v3.13.0: ML 批量預測增強（6倍性能提升）
                if self.ml_predictor and self.ml_predictor.is_ready:
                    logger.info(f"🤖 使用 ML 批量模型增強 {len(signals)} 個信號...")
                    
                    # 🔥 关键修复：predict_batch内部已经处理特征提取
                    # predict_batch接受signal字典列表，内部调用_prepare_signal_features
                    ml_predictions = self.ml_predictor.predict_batch(signals)
                    
                    # 附加預測結果和校準信心度
                    enhanced_signals = []
                    for signal, ml_prediction in zip(signals, ml_predictions):
                        if ml_prediction:
                            signal['ml_prediction'] = ml_prediction
                            
                            # 校準信心度
                            original_confidence = signal['confidence']
                            ml_confidence = ml_prediction.get('ml_confidence', 0.5)
                            signal['confidence'] = self.ml_predictor.calibrate_confidence(
                                original_confidence,
                                ml_prediction
                            )
                            
                            logger.debug(
                                f"  {signal['symbol']}: 原始 {original_confidence:.2%} "
                                f"→ ML校準 {signal['confidence']:.2%} (ML信心: {ml_confidence:.2%})"
                            )
                            
                            # 🔥 关键优化：只保留高质量信号（ML信心度>=40%）
                            if ml_confidence >= 0.40:
                                enhanced_signals.append(signal)
                            else:
                                logger.debug(f"  ❌ 过滤低质量信号 {signal['symbol']} (ML信心度: {ml_confidence:.2%})")
                        else:
                            # ML预测失败，保留原信号
                            enhanced_signals.append(signal)
                    
                    signals = enhanced_signals
                    logger.info(f"✅ ML批量预测完成，保留 {len(signals)} 个高质量信号")
                
                signals.sort(key=lambda x: x['confidence'], reverse=True)
                
                # 📊 统计信号方向分布
                long_signals = [s for s in signals if s['direction'] == 'LONG']
                short_signals = [s for s in signals if s['direction'] == 'SHORT']
                long_pct = len(long_signals) / len(signals) * 100 if signals else 0
                short_pct = len(short_signals) / len(signals) * 100 if signals else 0
                
                avg_confidence = sum(s['confidence'] for s in signals) / len(signals) if signals else 0
                avg_long_conf = sum(s['confidence'] for s in long_signals) / len(long_signals) if long_signals else 0
                avg_short_conf = sum(s['confidence'] for s in short_signals) / len(short_signals) if short_signals else 0
                
                # 計算系統評級（基於信號質量和方向平衡）
                balance_score = 50 - abs(long_pct - short_pct)  # 最高50分：完全平衡
                quality_score = avg_confidence * 50  # 最高50分：信心度100%
                system_rating = int(balance_score + quality_score)
                
                logger.info(f"\n🎯 生成 {len(signals)} 個信號 | 目前交易評級: {system_rating}分")
                logger.info(
                    f"   方向: LONG {len(long_signals)}個 | SHORT {len(short_signals)}個 | "
                    f"平均信心度: {avg_confidence:.1%}"
                )
                
                # 簡化信號列表顯示
                signal_list = ", ".join([
                    f"{s['symbol']}({s['direction'][0]}{s['confidence']:.0%})" 
                    for s in signals[:Config.MAX_SIGNALS]
                ])
                logger.info(f"   信號列表: {signal_list}")
                
                # 處理每個信號
                for rank, signal in enumerate(signals[:Config.MAX_SIGNALS], 1):
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
            
            # 🎯 v3.9.2.8.5: 显示模型评分状态
            if self.model_scorer and self.model_scorer.score_history:
                try:
                    stats = self.model_scorer.get_statistics()
                    logger.info(f"\n🎯 模型評分: {stats['current_score']:.1f}/100 ({stats['trend']})")
                except Exception as e:
                    logger.debug(f"显示模型评分失败: {e}")
            
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
                total_trades=expectancy_metrics['total_trades'],  # 傳入總交易數用於冷啟動判斷
                signal_confidence=signal.get('confidence', 0.0)  # 傳入信號信心度用於質量過濾
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
                    account_balance = Config.DEFAULT_ACCOUNT_BALANCE
                
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
                    win_rate=expectancy_metrics.get('win_rate'),
                    consecutive_losses=expectancy_metrics['consecutive_losses'],
                    current_drawdown=self.risk_manager.current_drawdown / account_balance if account_balance > 0 else 0.0
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
        """
        更新所有持倉（v3.12.0优化：仅用于实盘持仓）
        
        虚拟仓位更新已迁移到独立的 virtual_position_loop()
        """
        try:
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
    
    async def virtual_position_loop(self):
        """
        v3.13.0：异步虚拟仓位循环（使用批量并发更新）
        
        🔥 关键优化：
        - 使用 update_all_prices_async() 异步批量获取价格
        - 200个虚拟仓位更新：20+秒 → <1秒
        - 并发获取所有价格（asyncio.gather）
        - 异步文件I/O（aiofiles）
        
        优势：
        - 更快响应（10秒 vs 60秒）
        - 不阻塞实盘交易循环
        - 提高ML训练数据时效性
        - 减少虚拟仓位止损止盈延迟
        """
        logger.info(f"🔄 启动虚拟仓位循环（v3.13.0异步批量更新，间隔: {Config.VIRTUAL_POSITION_CYCLE_INTERVAL}秒）")
        cycle_count = 0
        
        while self.running:
            try:
                cycle_count += 1
                cycle_start = asyncio.get_event_loop().time()
                
                # 获取活跃虚拟仓位数量
                active_virtual = len(self.virtual_position_manager.get_active_virtual_positions())
                
                if active_virtual > 0:
                    logger.debug(f"📊 虚拟仓位循环 #{cycle_count} - {active_virtual} 个活跃虚拟仓位")
                    
                    # ✨ v3.13.0关键：异步批量更新所有虚拟仓位价格
                    # 直接调用update_all_prices_async，传入binance_client
                    closed_positions = await self.virtual_position_manager.update_all_prices_async(
                        binance_client=self.binance_client
                    )
                    
                    cycle_duration = asyncio.get_event_loop().time() - cycle_start
                    
                    # 处理关闭的虚拟仓位（文档步骤2要求）
                    if closed_positions:
                        logger.info(
                            f"✅ {len(closed_positions)} 个虚拟仓位已关闭 "
                            f"（异步批量更新耗时 {cycle_duration:.2f}秒）"
                        )
                        
                        # 存档和记录每个关闭的仓位
                        for pos in closed_positions:
                            try:
                                # 存档到数据归档器（用于ML训练）
                                if self.data_archiver:
                                    self.data_archiver.archive_position(pos.to_dict())
                                
                                # 记录到性能监控器
                                if self.performance_monitor:
                                    self.performance_monitor.record_operation(
                                        'virtual_position_closed',
                                        1.0
                                    )
                                
                                logger.debug(f"📦 虚拟仓位已存档: {pos.symbol} ({pos.side}) PnL={pos.pnl:.2f}")
                            except Exception as e:
                                logger.error(f"处理关闭虚拟仓位失败: {e}")
                    else:
                        logger.debug(
                            f"虚拟仓位更新完成 "
                            f"（异步批量更新耗时 {cycle_duration:.2f}秒）"
                        )
                    
                    # 性能警告
                    if cycle_duration > Config.VIRTUAL_POSITION_CYCLE_INTERVAL:
                        logger.warning(
                            f"⚠️  虚拟仓位更新超时！耗时 {cycle_duration:.1f}秒 > "
                            f"预期 {Config.VIRTUAL_POSITION_CYCLE_INTERVAL}秒"
                        )
                
                # 等待下一周期
                await asyncio.sleep(Config.VIRTUAL_POSITION_CYCLE_INTERVAL)
                
            except asyncio.CancelledError:
                logger.info("虚拟仓位循环被取消")
                break
            except Exception as e:
                logger.error(f"虚拟仓位循环错误: {e}", exc_info=True)
                await asyncio.sleep(5)
    
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
        """清理資源（v3.12.0：包含虚拟仓位循环清理）"""
        logger.info("\n🧹 清理資源...")
        
        if self.data_archiver:
            logger.info("💾 刷新所有數據到磁盤...")
            self.data_archiver.flush_all()
        
        if self.trade_recorder:
            self.trade_recorder.force_flush()
        
        # v3.12.0 优化5：清理虚拟仓位循环任务
        if self.virtual_loop_task:
            logger.info("🔄 停止虚拟仓位循环...")
            self.virtual_loop_task.cancel()
            try:
                await self.virtual_loop_task
            except asyncio.CancelledError:
                logger.info("✅ 虚拟仓位循环已停止")
        
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
    """
    主函數
    
    v3.12.0 优化5：启动双循环架构
    - 实盘交易循环（main_loop）
    - 虚拟仓位循环（virtual_position_loop）
    """
    Config.setup_logging()
    
    bot = TradingBot()
    
    signal.signal(signal.SIGINT, bot.handle_signal)
    signal.signal(signal.SIGTERM, bot.handle_signal)
    
    if await bot.initialize():
        # v3.12.0 优化5：同时启动双循环
        logger.info("🚀 启动双循环架构...")
        logger.info(f"  📊 实盘交易循环间隔: {Config.CYCLE_INTERVAL}秒")
        logger.info(f"  🔄 虚拟仓位循环间隔: {Config.VIRTUAL_POSITION_CYCLE_INTERVAL}秒")
        
        # 创建虚拟仓位循环任务
        bot.virtual_loop_task = asyncio.create_task(bot.virtual_position_loop())
        
        # 启动主循环（会阻塞直到停止）
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
