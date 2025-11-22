"""
UnifiedScheduler v3.17+ - 統一調度器
職責：整合所有組件、協調運行、定時任務
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Optional, Dict, List
import traceback

from src.strategies.self_learning_trader import SelfLearningTrader
from src.core.position_controller import PositionController
from src.core.model_evaluator import ModelEvaluator
from src.core.daily_reporter import DailyReporter
from src.core.websocket import WebSocketManager  # 🔥 v3.17.2+
from src.clients.binance_client import BinanceClient
from src.services.data_service import DataService
from src.core.unified_config_manager import config_manager as config
from src.utils.smart_logger import create_smart_logger
from src.core.account_state_cache import account_state_cache

# ✨ v3.26+ 性能优化：启用SmartLogger（减少重复日志）
logger = create_smart_logger(
    __name__,
    rate_limit_window=2.0,
    enable_aggregation=True,
    enable_structured=False
)


class UnifiedScheduler:
    """
    UnifiedScheduler v3.17+ - 統一調度器
    
    職責：
    1. 啟動 PositionController（24/7 監控）
    2. 定期執行交易週期（分析市場、生成信號、開倉）
    3. 每日生成報告（00:00 UTC）
    4. 協調所有組件
    
    架構（v3.17.2+ WebSocket整合）：
    ┌─────────────────────────────────┐
    │    UnifiedScheduler (調度器)    │
    ├─────────────────────────────────┤
    │ • WebSocketManager (即時數據)   │
    │   ├─ KlineFeed (即時K線)        │
    │   └─ AccountFeed (即時倉位)     │
    │ • SelfLearningTrader (決策)     │
    │ • PositionController (監控)     │
    │ • ModelEvaluator (評級)         │
    │ • DailyReporter (報告)          │
    └─────────────────────────────────┘
    """
    
    def __init__(
        self,
        config,  # Config類或實例（支持類級別配置）
        binance_client: BinanceClient,
        data_service: DataService,
        trade_recorder=None,
        model_initializer=None,
        lifecycle_manager=None  # 🛡️ v1.0+: System lifecycle manager
    ):
        """
        初始化 UnifiedScheduler
        
        Args:
            config: 配置對象
            binance_client: Binance 客戶端
            data_service: 數據服務
            trade_recorder: 交易記錄器
            model_initializer: 模型初始化器（v3.17.10+）
            lifecycle_manager: 生命周期管理器（v1.0+）
        """
        self.config = config
        self.binance_client = binance_client
        self.data_service = data_service
        self.trade_recorder = trade_recorder
        self.model_initializer = model_initializer  # 🔥 v3.17.10+
        self.lifecycle_manager = lifecycle_manager  # 🛡️ v1.0+
        
        # 🔥 v3.18.6+：初始化WebSocketManager（監控所有可交易的USDT永續合約）
        # 注意：初始化時使用空列表，稍後在start()中加載所有交易對
        self.websocket_manager = WebSocketManager(
            binance_client=binance_client,
            symbols=[],  # 🔥 v3.18.6+：初始化為空，稍後動態加載
            kline_interval="1m",
            shard_size=getattr(config, 'WEBSOCKET_SHARD_SIZE', 50),
            enable_kline_feed=getattr(config, 'WEBSOCKET_ENABLE_KLINE_FEED', True),
            enable_price_feed=getattr(config, 'WEBSOCKET_ENABLE_PRICE_FEED', True),
            enable_account_feed=getattr(config, 'WEBSOCKET_ENABLE_ACCOUNT_FEED', True),
            auto_fetch_symbols=False  # 🔥 v3.18+：不自動獲取，由scheduler控制
        )
        
        # 向後兼容：保留websocket_monitor屬性（指向websocket_manager）
        self.websocket_monitor = self.websocket_manager
        
        # ✅ v3.20 Phase 3: 初始化UnifiedDataPipeline（批量并行优化）
        from src.core.elite import UnifiedDataPipeline
        self.data_pipeline = UnifiedDataPipeline(
            binance_client=binance_client,
            websocket_monitor=self.websocket_manager
        )
        logger.info("✅ UnifiedDataPipeline已初始化（批量并行数据获取）")
        
        # 初始化核心組件（注入websocket_manager）
        self.self_learning_trader = SelfLearningTrader(
            config=config,
            binance_client=binance_client,
            trade_recorder=trade_recorder,  # 🔥 v3.18.4+ Critical Fix: 傳遞trade_recorder用於記錄開倉
            websocket_monitor=self.websocket_manager  # 🔥 v3.17.2+
        )
        
        self.position_controller = PositionController(
            binance_client=binance_client,
            self_learning_trader=self.self_learning_trader,
            monitor_interval=config.POSITION_MONITOR_INTERVAL,
            config=config,
            trade_recorder=trade_recorder,  # 🔥 v3.17.10+
            data_service=data_service,  # 🔥 v3.17.10+
            websocket_monitor=self.websocket_manager  # 🔥 v3.17.2+
        )
        
        self.model_evaluator = ModelEvaluator(
            config=config,
            reports_dir=config.REPORTS_DIR
        )
        
        self.daily_reporter = DailyReporter(
            config_profile=config,  # type: ignore
            model_rating_engine=self.model_evaluator
        )
        
        # 調度器狀態
        self.is_running = False
        self.last_report_date = None
        
        # 統計數據
        self.stats = {
            'total_cycles': 0,
            'total_signals': 0,
            'total_orders': 0,
            'total_reports': 0
        }
        
        logger.info("=" * 80)
        logger.info("✅ UnifiedScheduler v3.18.6+ 初始化完成（WebSocket整合）")
        logger.info("   🎯 模式: SelfLearningTrader")
        logger.info("   📡 WebSocketManager: 動態加載所有可交易USDT永續合約")
        logger.info("   📈 K線Feed: @kline_1m（取代REST輪詢）")
        logger.info("   📊 帳戶Feed: listenKey（即時倉位）")
        logger.info("   ⏱️  交易週期: 每 {} 秒".format(config.CYCLE_INTERVAL))
        logger.info("   🛡️  倉位監控: 每 {} 秒".format(config.POSITION_MONITOR_INTERVAL))
        logger.info("   📊 每日報告: 00:00 UTC")
        logger.info("=" * 80)
    
    async def start(self):
        """啟動調度器"""
        try:
            self.is_running = True
            logger.info("🚀 UnifiedScheduler 啟動中...")
            
            # 🔥 v3.18+：先獲取掃描交易對列表，再啟動WebSocket
            logger.info("📡 步驟1：獲取掃描交易對列表...")
            trading_symbols = await self._get_trading_symbols()
            if trading_symbols:
                logger.info(f"✅ 獲取 {len(trading_symbols)} 個交易對（掃描規則）")
                # 更新WebSocket監控列表
                self.websocket_manager.symbols = trading_symbols
            else:
                logger.warning("⚠️ 無法獲取交易對列表，WebSocket將使用fallback")
            
            # 啟動WebSocketManager（包含K線Feed和帳戶Feed）
            logger.info("📡 步驟2：啟動WebSocketManager...")
            await self.websocket_manager.start()
            logger.info(f"✅ WebSocketManager已啟動（監控{len(self.websocket_manager.symbols)}個交易對）")
            
            # 🔥 v4.6.0 Phase 2: 初始化交易計數緩存（避免event loop問題）
            logger.info("📊 步驟3：初始化交易計數緩存...")
            if hasattr(self.self_learning_trader, 'update_trade_count_cache'):
                try:
                    count = await self.self_learning_trader.update_trade_count_cache()
                    logger.info(f"✅ 交易計數緩存已初始化: {count}筆已完成交易")
                except Exception as e:
                    logger.warning(f"⚠️ 交易計數緩存初始化失敗: {e}（將使用默認值0）")
            
            # 啟動任務
            tasks = [
                asyncio.create_task(self._position_monitoring_loop()),
                asyncio.create_task(self._trading_cycle_loop()),
                asyncio.create_task(self._daily_report_loop()),
                asyncio.create_task(self._low_frequency_sync_loop())  # 🔥 每15分鐘一次缓存一致性检验
            ]
            
            logger.info("✅ 所有任務已啟動")
            
            # 等待所有任務
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"❌ UnifiedScheduler 啟動失敗: {e}", exc_info=True)
            self.is_running = False
    
    async def stop(self):
        """停止調度器"""
        logger.info("⏸️  UnifiedScheduler 停止中...")
        self.is_running = False
        
        # 🔥 v3.17.2+：停止WebSocketManager
        await self.websocket_manager.stop()
        
        # 停止 PositionController
        await self.position_controller.stop_monitoring()
        
        # 輸出統計
        logger.info("=" * 80)
        logger.info("📊 UnifiedScheduler 統計:")
        logger.info(f"   總週期: {self.stats['total_cycles']}")
        logger.info(f"   總信號: {self.stats['total_signals']}")
        logger.info(f"   總訂單: {self.stats['total_orders']}")
        logger.info(f"   總報告: {self.stats['total_reports']}")
        
        # 🔥 v3.17.2+：WebSocketManager統計
        ws_stats = self.websocket_manager.get_stats()
        if 'kline_feed' in ws_stats:
            logger.info(f"   K線Feed更新: {ws_stats['kline_feed']['total_updates']} 次")
            logger.info(f"   K線Feed重連: {ws_stats['kline_feed']['reconnections']} 次")
        if 'account_feed' in ws_stats:
            logger.info(f"   帳戶Feed更新: {ws_stats['account_feed']['total_updates']} 次")
        logger.info(f"   帳戶Feed重連: {ws_stats['account_feed']['reconnections']} 次")
        logger.info("=" * 80)
    
    async def _position_monitoring_loop(self):
        """倉位監控循環（24/7）"""
        try:
            logger.info("🛡️  倉位監控循環已啟動")
            await self.position_controller.start_monitoring()
            
        except Exception as e:
            logger.error(f"❌ 倉位監控循環失敗: {e}", exc_info=True)
    
    async def _trading_cycle_loop(self):
        """交易週期循環（帶看門狗心跳更新）"""
        try:
            logger.info("🔄 交易週期循環已啟動")
            
            while self.is_running:
                try:
                    # 🐶 Update watchdog heartbeat before execution
                    if hasattr(self, 'lifecycle_manager') and self.lifecycle_manager:
                        self.lifecycle_manager.update_heartbeat()
                    
                    await self._execute_trading_cycle()
                    await asyncio.sleep(self.config.CYCLE_INTERVAL)
                    
                except Exception as e:
                    logger.error(f"❌ 交易週期執行失敗: {e}", exc_info=True)
                    await asyncio.sleep(self.config.CYCLE_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ 交易週期循環失敗: {e}", exc_info=True)
    
    async def _daily_report_loop(self):
        """每日報告循環（00:00 UTC）"""
        try:
            logger.info("📊 每日報告循環已啟動")
            
            while self.is_running:
                try:
                    now = datetime.utcnow()
                    
                    # 檢查是否需要生成報告
                    if self._should_generate_report(now):
                        await self._generate_daily_report()
                        self.last_report_date = now.date()
                        self.stats['total_reports'] += 1
                    
                    # 每小時檢查一次
                    await asyncio.sleep(3600)
                    
                except Exception as e:
                    logger.error(f"❌ 每日報告生成失敗: {e}", exc_info=True)
                    await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"❌ 每日報告循環失敗: {e}", exc_info=True)
    
    async def _low_frequency_sync_loop(self):
        """🔥 低頻同步循環（每15分鐘一次）- 防止WebSocket缺包導致缓存漂移"""
        try:
            logger.info("🔄 低頻同步循環已啟動（每15分鐘檢查一次缓存一致性）")
            
            sync_count = 0
            while self.is_running:
                try:
                    await asyncio.sleep(900)  # 等待15分鐘（900秒）
                    
                    if not self.is_running:
                        break
                    
                    sync_count += 1
                    logger.info(f"🔄 低頻同步 #{sync_count}: 檢查缓存一致性...")
                    
                    # 從REST API获取账户数据（完整调用）
                    try:
                        account_info = await self.binance_client.get_account_info()
                        
                        if account_info:
                            # 通过 reconcile() 检查缓存是否存在漂移
                            result = account_state_cache.reconcile(account_info)
                            
                            if result['status'] == 'warning':
                                logger.warning(
                                    f"⚠️ 缓存漂移检测: 已自动修复 "
                                    f"{len(result['balance_mismatches'])} 个余额问题, "
                                    f"{len(result['position_mismatches'])} 个持仓问题。"
                                    f"WebSocket可能丢失了包。"
                                )
                            elif result['status'] == 'ok':
                                logger.debug("✅ 缓存一致性验证通过 - 无漂移")
                            else:
                                logger.error(f"❌ 缓存一致性验证失败: {result}")
                        else:
                            logger.warning("⚠️ REST API获取账户信息失败（回调将继续使用缓存）")
                    
                    except Exception as e:
                        logger.warning(f"⚠️ 低頻同步失敗: {e}（将继续使用缓存，下一个同步周期重试）")
                        # 不中断循环，继续等待下一个同步周期
                
                except asyncio.CancelledError:
                    logger.info("🛑 低頻同步循環已取消")
                    break
                
                except Exception as e:
                    logger.error(f"❌ 低頻同步循環異常: {e}", exc_info=True)
                    # 继续运行，不中断
        
        except Exception as e:
            logger.error(f"❌ 低頻同步循環啟動失敗: {e}", exc_info=True)
    
    async def _execute_trading_cycle(self):
        """執行單次交易週期"""
        try:
            self.stats['total_cycles'] += 1
            cycle_start = datetime.now()
            
            logger.debug(f"交易週期 #{self.stats['total_cycles']}")
            
            # 🔥 v3.17.10+：每10個週期檢查是否需要重訓練（動態觸發）
            if self.model_initializer and self.stats['total_cycles'] % 10 == 0:
                try:
                    if self.model_initializer.should_retrain():
                        logger.info("🔄 模型重訓練: 性能驟降/市場狀態劇變/樣本累積...")
                        await self.model_initializer.force_retrain()
                        logger.info("✅ 模型已更新")
                except Exception as e:
                    logger.error(f"❌ 模型重訓練失敗: {e}")
            
            # 步驟 1：獲取並顯示持倉狀態
            positions = await self._get_and_display_positions()
            
            # 🔥 步驟 2：獲取賬戶餘額信息（本地優先、零API調用）
            account_info = None
            
            # 🔥 v4.0+：優先從本地緩存獲取（由WebSocket AccountFeed實時更新、零API請求）
            usdt_balance = account_state_cache.get_balance('USDT')
            if usdt_balance:
                account_info = {
                    'total_balance': usdt_balance['total'],
                    'available_balance': usdt_balance['free'],
                    'total_margin': usdt_balance['locked'],
                    'unrealized_pnl': 0
                }
                logger.debug("💾 從本地緩存獲取帳戶餘額（零API調用）")
            
            # 備援：如果緩存為空，使用WebSocket（但緩存應該已被初始化）
            if not account_info and self.websocket_manager and self.websocket_manager.account_feed:
                account_info = self.websocket_manager.get_account_balance()
                if account_info:
                    logger.debug("📡 備援：從WebSocket獲取帳戶餘額")
            
            total_balance = account_info['total_balance']
            available_balance = account_info['available_balance']
            total_margin = account_info['total_margin']
            unrealized_pnl = account_info['unrealized_pnl']
            
            logger.info(
                f"💰 賬戶餘額: 總額=${total_balance:.2f} | "
                f"可用=${available_balance:.2f} | "
                f"保證金=${total_margin:.2f} | "
                f"未實現盈虧=${unrealized_pnl:+.2f}"
            )
            
            # 步驟 3：顯示模型評分狀態
            await self._display_model_rating()
            
            # 步驟 4：獲取交易對列表
            symbols = await self._get_trading_symbols()
            
            if not symbols:
                logger.warning("⚠️ 無可交易交易對")
                return
            
            logger.debug(f"掃描 {len(symbols)} 個交易對...")
            
            # 🔧 v3.19+ 修復：重置Pipeline統計計數器（防止多次掃描累加）
            # 🔥 v3.20.3 Phase 6: 修復缺失的ADX分布鍵，防止KeyError
            if hasattr(self.self_learning_trader, 'signal_generator'):
                self.self_learning_trader.signal_generator._pipeline_stats = {
                    'stage0_total_symbols': 0,
                    'stage1_valid_data': 0,
                    'stage1_rejected_data': 0,
                    'stage2_trend_ok': 0,
                    'stage3_signal_direction': 0,
                    'stage3_with_direction': 0,
                    'stage3_no_direction': 0,
                    'feature_calculation_success': 0,
                    'feature_calculation_failed': 0,
                    'stage3_priority1': 0,
                    'stage3_priority2': 0,
                    'stage3_priority3': 0,
                    'stage3_priority4_relaxed': 0,
                    'stage3_priority5_relaxed': 0,
                    'stage4_adx_rejected_lt10': 0,
                    'stage4_adx_penalty_10_15': 0,
                    'stage4_adx_penalty_15_20': 0,
                    'stage4_adx_ok_gte20': 0,
                    'stage5_confidence_calculated': 0,
                    'stage6_win_prob_calculated': 0,
                    'stage7_passed_double_gate': 0,
                    'stage7_rejected_win_prob': 0,
                    'stage7_rejected_confidence': 0,
                    'stage7_rejected_rr': 0,
                    'stage8_passed_quality': 0,
                    'stage8_rejected_quality': 0,
                    'stage9_ranked_signals': 0,
                    'stage9_executed_signals': 0,
                    'adx_distribution_lt10': 0,
                    'adx_distribution_10_15': 0,
                    'adx_distribution_15_20': 0,
                    'adx_distribution_20_25': 0,
                    'adx_distribution_gte25': 0
                }
                logger.info("✅ Pipeline統計計數器已完整重置（包含所有ADX分布鍵）")
            
            # 步驟 5：批量分析並生成信號
            signals = []
            data_unavailable_count = 0
            analyzed_count = 0
            signal_candidates = []  # 🔥 v3.19+：收集所有交易對的信心值/勝率用於診斷
            diagnostic_count = 0  # 🔥 v3.19.1: 數據診斷計數器
            
            # 🔥 Critical Fix v2: Data guard to prevent log noise during warmup
            # Check if data pipeline has warmed up before running analysis
            if hasattr(self, 'data_pipeline') and hasattr(self.data_pipeline, 'kline_manager'):
                # Quick check: verify at least some symbols have cached data
                test_batch = symbols[:10]  # Check first 10 symbols
                has_data = False
                try:
                    test_data = await self.data_pipeline.batch_get_multi_timeframe_data(
                        test_batch,
                        timeframes=['1h']
                    )
                    # Check if any symbol has valid data
                    for symbol, data_dict in test_data.items():
                        if data_dict and data_dict.get('1h') is not None and len(data_dict.get('1h', [])) > 0:
                            has_data = True
                            break
                except Exception:
                    pass
                
                if not has_data:
                    logger.warning("⚠️ 市場數據預熱中... 等待WebSocket數據積累（跳過本次掃描）")
                    logger.debug(f"   已重置 {len(symbols)} 個交易對的分析（避免無效日誌）")
                    return
            
            # 🔥 v3.19+ 診斷：時間分析（降级为DEBUG）
            import time
            total_data_time = 0
            total_analysis_time = 0
            analysis_times = []
            data_times = []
            scan_start = time.time()
            logger.debug("開始掃描時間分析（批量並行模式）")
            
            # ✅ v3.20 Phase 3: 批量並行數據獲取優化
            BATCH_SIZE = 64  # 每批64個symbols
            
            for batch_start in range(0, len(symbols), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(symbols))
                batch_symbols = symbols[batch_start:batch_end]
                
                try:
                    # 測量數據獲取時間（批量）
                    data_start = time.time()
                    batch_data = await self.data_pipeline.batch_get_multi_timeframe_data(
                        batch_symbols,
                        timeframes=['1h', '15m', '5m']
                    )
                    data_elapsed = time.time() - data_start
                    total_data_time += data_elapsed
                    
                    logger.debug(
                        f"批次 {batch_start//BATCH_SIZE + 1}: "
                        f"{len(batch_symbols)}个symbols数据获取完成，耗时{data_elapsed:.2f}秒"
                    )
                    
                    # 逐个分析每个symbol（数据已批量获取）
                    for i, symbol in enumerate(batch_symbols):
                        try:
                            multi_tf_data = batch_data.get(symbol, {})
                            
                            # 🔥 Stability Fix: Validate data quality before analysis
                            if not multi_tf_data:
                                data_unavailable_count += 1
                                continue
                            
                            # Check that at least one timeframe has valid data
                            has_valid_data = False
                            for tf, df in multi_tf_data.items():
                                if df is not None and len(df) > 0:
                                    has_valid_data = True
                                    break
                            
                            if not has_valid_data:
                                logger.debug(f"⚠️ {symbol}: 所有時間框架數據為空，跳過分析")
                                data_unavailable_count += 1
                                continue
                            
                            # 🔥 v3.19.1: 診斷前3個symbol的實際數據情況（降级为DEBUG）
                            if diagnostic_count < 3:
                                diagnostic_count += 1
                                logger.debug(f"數據診斷 #{diagnostic_count} - {symbol}:")
                                for tf, df in multi_tf_data.items():
                                    if df is not None and len(df) > 0:
                                        logger.debug(f"   {tf}: {len(df)}行")
                                    elif df is not None:
                                        logger.debug(f"   {tf}: DataFrame為空")
                                    else:
                                        logger.debug(f"   {tf}: DataFrame為None")
                            
                            # 測量分析時間
                            analysis_start = time.time()
                            signal, confidence, win_prob = self.self_learning_trader.analyze(symbol, multi_tf_data)
                            analysis_elapsed = time.time() - analysis_start
                            analysis_times.append(analysis_elapsed)
                            total_analysis_time += analysis_elapsed
                            
                            analyzed_count += 1
                            
                            # 🔥 v3.19+：收集所有交易對的診斷信息
                            signal_candidates.append({
                                'symbol': symbol,
                                'confidence': confidence,
                                'win_probability': win_prob,
                                'has_signal': signal is not None,
                                'analysis_time_ms': analysis_elapsed * 1000,
                                'data_time_ms': data_elapsed / len(batch_symbols) * 1000  # 平均每个symbol的数据时间
                            })
                            
                            # 🔥 Bug #6 診斷：記錄信號拒絕原因
                            if signal:
                                signals.append(signal)
                                self.stats['total_signals'] += 1
                            else:
                                # 檢查為什麼信號為None（雖然confidence和win_prob有值）
                                if confidence > 0 or win_prob > 0:
                                    if analyzed_count <= 5:  # 只診斷前5個
                                        logger.warning(
                                            f"⚠️ {symbol}: 有分數但無信號 | "
                                            f"confidence={confidence:.1f} | win_prob={win_prob:.1f}%"
                                        )
                            
                        except Exception as e:
                            logger.debug(f"分析 {symbol} 跳過: {e}")
                    
                    # 每批输出进度
                    if analyzed_count > 0:
                        avg_analysis = (total_analysis_time / analyzed_count * 1000) if analyzed_count > 0 else 0
                        avg_data = (total_data_time / (batch_start + len(batch_symbols)) * 1000) if batch_start + len(batch_symbols) > 0 else 0
                        logger.debug(f"進度: {batch_start + len(batch_symbols)}/{len(symbols)} | "
                                  f"已分析={analyzed_count} | "
                                  f"平均分析={avg_analysis:.1f}ms | "
                                  f"平均數據={avg_data:.1f}ms")
                    
                except Exception as e:
                    logger.error(f"批次處理失敗: {e}")
            
            # 🔥 v3.19+ 診斷：時間分析報告
            total_scan_time = time.time() - scan_start
            if analyzed_count > 0 and analysis_times:
                avg_analysis_ms = (total_analysis_time / analyzed_count) * 1000
                avg_data_ms = (total_data_time / len(data_times)) * 1000 if data_times else 0
                min_analysis_ms = min(analysis_times) * 1000
                max_analysis_ms = max(analysis_times) * 1000
                
                logger.info("=" * 80)
                logger.info("⏱️  ===== 掃描時間分析報告 =====")
                logger.info(f"📊 分析交易對: {analyzed_count}/{len(symbols)}")
                logger.info(f"📭 數據缺失: {data_unavailable_count}")
                logger.info(f"⏱️  總掃描時間: {total_scan_time:.1f}s")
                logger.info(f"📈 平均分析時間: {avg_analysis_ms:.1f}ms")
                logger.info(f"🚀 最快分析: {min_analysis_ms:.1f}ms")
                logger.info(f"🐌 最慢分析: {max_analysis_ms:.1f}ms")
                logger.info(f"💾 平均數據獲取: {avg_data_ms:.1f}ms")
                
                # 🔍 診斷異常情況
                # 🐛 Chain Reaction Fix: Reduce error spam when WebSocket recovers (no data)
                if avg_analysis_ms < 10:
                    logger.warning(f"⚠️  低分析時間: 平均分析時間僅{avg_analysis_ms:.1f}ms（WebSocket恢復中或數據驗證嚴格）")
                    logger.debug(f"   → 可能原因：數據驗證過嚴、方向判斷快速返回None、特徵計算失敗、等待PriceFeed恢復")
                elif avg_analysis_ms < 50:
                    logger.warning(f"⚠️  警告: 平均分析時間{avg_analysis_ms:.1f}ms，可能分析深度不足")
                else:
                    logger.info(f"✅ 合理: 平均分析時間{avg_analysis_ms:.1f}ms")
                logger.info("=" * 80)
            
            # 🔥 v3.19+：輸出掃描統計
            logger.info(f"📊 掃描統計: 總數={len(symbols)} | 數據可用={analyzed_count} | 數據缺失={data_unavailable_count}")
            
            # 🔥 v3.19+：輸出信心值最高的前10個交易對（用於診斷）
            if signal_candidates:
                sorted_candidates = sorted(signal_candidates, key=lambda x: x['confidence'], reverse=True)
                top_10 = sorted_candidates[:10]
                
                logger.info("=" * 80)
                logger.info("📊 信號分析診斷（信心值Top 10）")
                logger.info("=" * 80)
                for i, candidate in enumerate(top_10, 1):
                    signal_status = "✅ 信號" if candidate['has_signal'] else "❌ 無信號"
                    logger.info(
                        f"{i:2}. {candidate['symbol']:12} | "
                        f"信心={candidate['confidence']:5.1f} | "
                        f"勝率={candidate['win_probability']:5.1f}% | "
                        f"{signal_status}"
                    )
                logger.info("=" * 80)
            
            # 🔥 Stability Fix: Keep INFO summary for rejection visibility, only skip 0% entries
            # Preserves Bug #6 intent (operator sees rejection stats) while reducing 0% noise
            if signal_candidates and not signals:
                logger.info("=" * 80)
                logger.info("🔍 Stage7 - 雙門檻驗證詳細診斷（前15個候選信號）")
                logger.info("=" * 80)
                
                # 當前門檻設置 - Always show at INFO (critical context)
                logger.info(f"📋 當前門檻設置:")
                logger.info(f"   信心度  ≥ {self.config.MIN_CONFIDENCE*100:.0f}%")
                logger.info(f"   勝率    ≥ {self.config.MIN_WIN_PROBABILITY*100:.0f}%")
                logger.info(f"   R:R比   在 {self.config.MIN_RR_RATIO:.1f}-{self.config.MAX_RR_RATIO:.1f} 範圍內")
                logger.info("")
                
                # 顯示前15個候選信號的詳細信息
                sorted_candidates = sorted(signal_candidates, 
                                          key=lambda x: (x['confidence'] + x['win_probability']), 
                                          reverse=True)
                
                rejection_stats = {
                    'confidence_too_low': 0,
                    'win_rate_too_low': 0,
                    'total_candidates': len(signal_candidates),
                    'passed': len(signals),
                    'zero_score_count': 0
                }
                
                logger.info("📊 前15個候選信號詳情:")
                for i, candidate in enumerate(sorted_candidates[:15], 1):
                    symbol = candidate['symbol']
                    confidence = candidate['confidence']
                    win_rate = candidate['win_probability']
                    has_signal = candidate['has_signal']
                    
                    # 判斷拒絕原因
                    reasons = []
                    if confidence < self.config.MIN_CONFIDENCE * 100:
                        reasons.append(f"信心{confidence:.1f}<{self.config.MIN_CONFIDENCE*100:.0f}")
                        rejection_stats['confidence_too_low'] += 1
                    if win_rate < self.config.MIN_WIN_PROBABILITY * 100:
                        reasons.append(f"勝率{win_rate:.1f}<{self.config.MIN_WIN_PROBABILITY*100:.0f}")
                        rejection_stats['win_rate_too_low'] += 1
                    
                    status = "✅ 通過" if has_signal else f"❌ 拒絕({', '.join(reasons) if reasons else '未知'})"
                    
                    # 🔥 Stability Fix: Filter 0% entries to DEBUG, keep meaningful ones at INFO
                    if confidence > 0 or win_rate > 0:
                        logger.info(
                            f"  {i:2}. {symbol:12} | "
                            f"信心={confidence:5.1f}% | "
                            f"勝率={win_rate:5.1f}% | "
                            f"{status}"
                        )
                    else:
                        rejection_stats['zero_score_count'] += 1
                        logger.debug(
                            f"  {i:2}. {symbol:12} | "
                            f"信心={confidence:5.1f}% | "
                            f"勝率={win_rate:5.1f}% | "
                            f"{status} [0% spam]"
                        )
                
                # Summary - Always at INFO (critical for operators)
                logger.info("")
                logger.info("📊 Stage7 拒絕統計:")
                logger.info(f"   總候選信號: {rejection_stats['total_candidates']}")
                logger.info(f"   通過驗證: {rejection_stats['passed']}")
                logger.info(f"   被拒絕: {rejection_stats['total_candidates'] - rejection_stats['passed']}")
                if rejection_stats['confidence_too_low'] > 0:
                    logger.info(f"     - 信心度不足: {rejection_stats['confidence_too_low']}")
                if rejection_stats['win_rate_too_low'] > 0:
                    logger.info(f"     - 勝率不足: {rejection_stats['win_rate_too_low']}")
                if rejection_stats['zero_score_count'] > 0:
                    logger.info(f"     - 0%信號已隱藏: {rejection_stats['zero_score_count']}個（見DEBUG日志）")
                
                logger.info("=" * 80)
            
            if signals:
                logger.info(f"✅ 發現 {len(signals)} 個交易信號")
            else:
                if data_unavailable_count == len(symbols):
                    logger.warning("⚠️  所有交易對數據缺失（WebSocket可能未就緒或API不可用）")
                else:
                    logger.info("⏸️  本週期無新信號")
            
            # 步驟 6：執行信號（開倉）
            # 🔥 v3.18+: 使用動態預算池 + 質量加權分配
            executed_count = 0
            if signals and self.config.TRADING_ENABLED:
                logger.info(
                    f"📊 信號執行 | 可用保證金: ${available_balance:.2f} | "
                    f"已有倉位: {len(positions)} | 新信號數: {len(signals)}"
                )
                
                # 🔥 v3.18+: 使用CapitalAllocator進行動態分配
                executed_positions = await self.self_learning_trader.execute_best_trades(
                    signals=signals,
                    max_positions=None  # 使用config.MAX_CONCURRENT_ORDERS
                )
                
                executed_count = len(executed_positions)
                self.stats['total_orders'] += executed_count
                
                if executed_count > 0:
                    for pos in executed_positions:
                        if pos:
                            symbol = pos.get('symbol', 'UNKNOWN')
                            direction = pos.get('direction', 'UNKNOWN')
                            leverage = pos.get('leverage', 1)
                            logger.info(f"   ✅ 成交: {symbol} {direction} | 槓桿: {leverage}x")
            
            # 週期統計
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(f"✅ 週期完成 | 耗時: {cycle_duration:.1f}s | 新成交: {executed_count}")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ 交易週期執行失敗: {e}", exc_info=True)
    
    async def _get_trading_symbols(self) -> list:
        """
        獲取交易對列表（v3.18.6+ 監控所有可交易USDT永續合約）
        
        🔥 v3.18.6+改進：
        - 優先使用DataService已加載的所有交易對（所有可交易USDT永續合約）
        - 備選1：配置文件中的TRADING_SYMBOLS
        - 備選2：scan_market（使用1小時緩存）
        """
        try:
            # 🔥 v3.18.6+：優先使用DataService已加載的所有交易對
            if self.data_service and hasattr(self.data_service, 'all_symbols') and self.data_service.all_symbols:
                logger.info(f"✅ 使用DataService已加載的 {len(self.data_service.all_symbols)} 個交易對（所有可交易USDT永續合約）")
                return self.data_service.all_symbols
            
            # 備選1：從配置獲取交易對列表
            if hasattr(self.config, 'TRADING_SYMBOLS') and self.config.TRADING_SYMBOLS:
                logger.info(f"✅ 使用配置文件中的 {len(self.config.TRADING_SYMBOLS)} 個交易對")
                return self.config.TRADING_SYMBOLS
            
            # 備選2：使用scan_market（有1小時緩存，僅首次調用REST API）
            max_symbols = getattr(self.config, 'TOP_VOLATILITY_SYMBOLS', 200)
            market_data = await self.data_service.scan_market(top_n=max_symbols)
            
            # 提取symbol列表
            symbols = [item['symbol'] for item in market_data]
            
            logger.info(f"✅ 使用市場掃描結果：{len(symbols)} 個高流動性交易對（來自緩存）")
            return symbols
            
        except Exception as e:
            logger.error(f"❌ 獲取交易對列表失敗: {e}")
            return []
    
    async def _get_and_display_positions(self) -> List[Dict]:
        """獲取並顯示當前持倉狀態（本地優先、零API調用）"""
        try:
            # 🔥 v4.0+：優先從本地緩存獲取持倉（由WebSocket AccountFeed實時更新、零API請求）
            cache_positions = account_state_cache.get_all_positions()
            positions = []
            
            for symbol, pos_data in cache_positions.items():
                positions.append({
                    'symbol': symbol.upper(),
                    'positionAmt': str(pos_data.get('amount', 0)),
                    'entryPrice': str(pos_data.get('entry_price', 0)),
                    'unRealizedProfit': str(pos_data.get('unrealized_pnl', 0)),
                    'leverage': str(pos_data.get('leverage', 1)),
                    'unrealizedProfit': str(pos_data.get('unrealized_pnl', 0)),  # Binance API field
                    'is_cache_data': True
                })
            
            if not positions:
                logger.debug("💾 本地緩存無持倉（零API調用）")
            
            # 過濾出有持倉的交易對
            active_positions = [
                p for p in positions 
                if float(p.get('positionAmt', 0)) != 0
            ]
            
            # 顯示歷史統計
            await self._display_historical_stats()
            
            if not active_positions:
                logger.info("📦 當前持倉: 無")
                return []
            
            # 計算當前所有持倉總損益
            # 🔥 Binance API 字段名稱修正：/fapi/v2/account 使用 'unrealizedProfit' (全小寫)
            total_unrealized_pnl = sum(
                float(p.get('unrealizedProfit', p.get('unRealizedProfit', 0))) 
                for p in active_positions
            )
            
            logger.info(f"📦 當前持倉: {len(active_positions)} 個 | 總未實現盈虧: ${total_unrealized_pnl:+.2f}")
            logger.info("=" * 80)
            
            for pos in active_positions:
                symbol = pos['symbol']
                amt = float(pos['positionAmt'])
                direction = "LONG" if amt > 0 else "SHORT"
                entry_price = float(pos.get('entryPrice', 0))
                # 🔥 支持兩種字段名稱 (Binance API不一致)
                unrealized_pnl = float(pos.get('unrealizedProfit', pos.get('unRealizedProfit', 0)))
                
                # 計算盈虧百分比
                position_value = abs(amt) * entry_price
                pnl_pct = (unrealized_pnl / position_value * 100) if position_value > 0 else 0
                
                # 🔥 v3.18.4+：獲取模型信心值和勝率（從trade_recorder頂層字段）
                confidence = 0
                win_rate = 0
                
                try:
                    if self.trade_recorder:
                        # 🔥 CRITICAL FIX: Add missing await keyword
                        all_trades = await self.trade_recorder.get_trades()
                        open_trades = [
                            t for t in all_trades 
                            if t.get('symbol') == symbol 
                            and t.get('direction') == direction
                            and t.get('status') == 'open'
                        ]
                        
                        if open_trades:
                            latest_trade = open_trades[-1]
                            # 🔥 Critical Fix: 信心值和勝率存儲在頂層，不是metadata中
                            confidence = latest_trade.get('confidence', 0) * 100  # 0-1 → 0-100
                            win_rate = latest_trade.get('win_probability', 0) * 100  # 0-1 → 0-100
                except Exception as e:
                    logger.debug(f"獲取 {symbol} 信心值/勝率失敗: {e}")
                
                # 🎯 簡化日誌：只顯示信心值、勝率、盈虧
                logger.info(
                    f"   • {symbol} {direction} | "
                    f"信心值={confidence:.1f}% | "
                    f"勝率={win_rate:.1f}% | "
                    f"盈虧=${unrealized_pnl:+.2f} ({pnl_pct:+.2f}%)"
                )
            
            logger.info("=" * 80)
            return active_positions
            
        except Exception as e:
            logger.error(f"❌ 獲取持倉失敗: {e}")
            return []
    
    async def _display_historical_stats(self):
        """顯示歷史統計（歷史贏虧、歷史總報酬率、歷史總勝率）"""
        try:
            if not self.trade_recorder:
                return
            
            # 獲取所有已平倉交易
            all_trades = await self.trade_recorder.get_trades()
            closed_trades = [t for t in all_trades if t.get('status') == 'closed' and 'pnl' in t]
            
            if not closed_trades:
                logger.info("📊 歷史統計: 暫無交易記錄")
                return
            
            # 計算歷史贏虧
            total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
            
            # 計算歷史總勝率
            winning_trades = [t for t in closed_trades if t.get('pnl', 0) > 0]
            win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0
            
            # 計算歷史總報酬率（假設初始資金為首次交易的帳戶餘額）
            initial_balance = closed_trades[0].get('account_balance', 1000) if closed_trades else 1000
            total_return_rate = (total_pnl / initial_balance * 100) if initial_balance > 0 else 0
            
            logger.info("=" * 80)
            logger.info("📊 歷史統計摘要")
            logger.info(f"   總交易次數: {len(closed_trades)} 筆")
            logger.info(f"   歷史總盈虧: ${total_pnl:+.2f}")
            logger.info(f"   歷史總報酬率: {total_return_rate:+.2f}%")
            logger.info(f"   歷史總勝率: {win_rate:.2f}% ({len(winning_trades)}/{len(closed_trades)})")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ 顯示歷史統計失敗: {e}")
    
    async def _get_entry_reason(self, symbol: str, direction: str) -> str:
        """獲取進場理由（查詢trade_recorder中的信號記錄）"""
        try:
            if not self.trade_recorder:
                return ""
            
            # 獲取該交易對的未平倉交易記錄
            all_trades = await self.trade_recorder.get_trades()
            open_trades = [
                t for t in all_trades 
                if t.get('symbol') == symbol 
                and t.get('direction') == direction 
                and t.get('status') == 'open'
            ]
            
            if open_trades:
                latest_trade = open_trades[-1]
                # 獲取進場信號理由（可能包含在metadata中）
                metadata = latest_trade.get('metadata', {})
                return metadata.get('entry_reason', metadata.get('signal_type', ''))
            
            return ""
            
        except Exception as e:
            logger.debug(f"獲取進場理由失敗: {e}")
            return ""
    
    async def _display_model_rating(self):
        """顯示模型評分狀態（v3.18.4+：顯示當前持倉平均信心值和勝率）"""
        try:
            if not self.trade_recorder:
                return
            
            # 🔥 v3.18.4+：優先顯示已平倉交易的歷史評分
            trades = await self.trade_recorder.get_trades(days=1)
            closed_trades = [t for t in trades if t.get('status') == 'closed']
            
            if closed_trades:
                # 有已平倉交易，顯示歷史評分
                evaluation = self.model_evaluator.evaluate_model(trades, period_days=1)
                
                score = evaluation.get('final_score', 0)
                grade = evaluation.get('grade', 'N/A')
                action = evaluation.get('action', 'N/A')
                total_trades = evaluation.get('total_trades', 0)
                win_rate = evaluation.get('win_rate', 0) * 100
                
                logger.info(f"🎯 模型評分: {score:.1f}/100 ({grade} 級) | 勝率: {win_rate:.1f}% | 交易: {total_trades} 筆 | 建議: {action}")
                return
            
            # 🔥 v3.18.4+：沒有已平倉交易時，顯示當前持倉的平均信心值和勝率
            open_trades = [t for t in trades if t.get('status') == 'open']
            
            if not open_trades:
                logger.info("🎯 模型評分: 無交易記錄")
                return
            
            # 計算當前持倉的平均信心值和勝率
            total_confidence = 0
            total_win_prob = 0
            valid_count = 0
            
            for trade in open_trades:
                metadata = trade.get('metadata', {})
                confidence = metadata.get('confidence', 0)
                win_prob = metadata.get('win_probability', 0)
                
                if confidence > 0 and win_prob > 0:
                    total_confidence += confidence
                    total_win_prob += win_prob
                    valid_count += 1
            
            if valid_count > 0:
                avg_confidence = total_confidence / valid_count
                avg_win_rate = total_win_prob / valid_count
                
                logger.info(
                    f"🎯 當前持倉: {len(open_trades)} 個 | "
                    f"平均信心值: {avg_confidence:.1f}% | "
                    f"平均勝率: {avg_win_rate:.1f}%"
                )
            else:
                logger.info(f"🎯 當前持倉: {len(open_trades)} 個（無模型數據）")
            
        except Exception as e:
            logger.debug(f"模型評分跳過: {e}")
    
    async def _execute_signal(self, signal: Dict, margin_budget: float, available_balance: float) -> bool:
        """
        執行交易信號（開倉）
        
        Args:
            signal: 交易信號
            margin_budget: 此倉位的保證金預算（USDT）
            available_balance: 當前可用保證金（用於日誌）
            
        Returns:
            成功返回 True，失敗返回 False
        """
        try:
            symbol = signal['symbol']
            direction = signal['direction']
            entry_price = signal['entry_price']
            stop_loss = signal['adjusted_stop_loss']
            take_profit = signal['adjusted_take_profit']
            leverage = signal['leverage']
            
            # ✅ 使用保證金預算計算倉位數量（不是總權益）
            # margin_budget 已經是可用保證金的一部分，可以直接使用
            position_size = await self.self_learning_trader.calculate_position_size(
                account_equity=margin_budget,  # ✅ 使用分配的保證金預算
                entry_price=entry_price,
                stop_loss=stop_loss,
                leverage=leverage,
                symbol=symbol,
                verbose=True
            )
            
            # 設置槓桿（忽略錯誤，某些交易對可能有槓桿限制）
            safe_leverage = min(int(leverage), 125)  # ✅ 在 try 外定義
            try:
                # 限制槓桿最大 125x（Binance 通用上限）
                await self.binance_client.set_leverage(symbol, safe_leverage)
            except Exception as e:
                logger.warning(f"   ⚠️ 設置槓桿失敗 ({symbol} {safe_leverage}x): {e}")
                # 繼續執行，使用當前槓桿
            
            # 下單（One-Way Mode，不使用 positionSide）
            side = 'BUY' if direction == 'LONG' else 'SELL'
            
            order_result = await self.binance_client.place_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=position_size
            )
            
            # TODO: 設置 SL/TP 訂單
            
            return True
            
        except Exception as e:
            logger.error(f"   ❌ 執行信號失敗: {e}", exc_info=True)
            return False
    
    def _should_generate_report(self, now: datetime) -> bool:
        """檢查是否應該生成報告"""
        # 每天 00:00 UTC 生成一次
        if now.hour == 0 and now.minute < 5:
            # 檢查今天是否已生成
            if self.last_report_date != now.date():
                return True
        return False
    
    async def _generate_daily_report(self):
        """生成每日報告"""
        try:
            logger.info("📊 生成每日報告...")
            
            # 獲取交易記錄
            if self.trade_recorder:
                # TradeRecorder 存儲在內存中，獲取最近的交易
                trades = getattr(self.trade_recorder, 'completed_trades', [])
            else:
                trades = []
            
            # 使用 ModelEvaluator 生成報告
            report = self.model_evaluator.generate_daily_report(
                trades=trades,
                save_json=True,
                save_markdown=True
            )
            
            # DailyReporter 報告已包含在 ModelEvaluator 中
            # daily_stats = await self.daily_reporter.generate_report()
            
            logger.info("✅ 每日報告生成完成")
            
        except Exception as e:
            logger.error(f"❌ 生成每日報告失敗: {e}", exc_info=True)
