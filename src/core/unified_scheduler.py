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
from src.config import Config

logger = logging.getLogger(__name__)


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
        model_initializer=None
    ):
        """
        初始化 UnifiedScheduler
        
        Args:
            config: 配置對象
            binance_client: Binance 客戶端
            data_service: 數據服務
            trade_recorder: 交易記錄器
            model_initializer: 模型初始化器（v3.17.10+）
        """
        self.config = config
        self.binance_client = binance_client
        self.data_service = data_service
        self.trade_recorder = trade_recorder
        self.model_initializer = model_initializer  # 🔥 v3.17.10+
        
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
            
            # 啟動任務
            tasks = [
                asyncio.create_task(self._position_monitoring_loop()),
                asyncio.create_task(self._trading_cycle_loop()),
                asyncio.create_task(self._daily_report_loop())
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
        """交易週期循環"""
        try:
            logger.info("🔄 交易週期循環已啟動")
            
            while self.is_running:
                try:
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
    
    async def _execute_trading_cycle(self):
        """執行單次交易週期"""
        try:
            self.stats['total_cycles'] += 1
            cycle_start = datetime.now()
            
            logger.info("=" * 80)
            logger.info(f"🔄 交易週期 #{self.stats['total_cycles']} | {cycle_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            logger.info("=" * 80)
            
            # 🔥 v3.17.10+：每10個週期檢查是否需要重訓練（動態觸發）
            if self.model_initializer and self.stats['total_cycles'] % 10 == 0:
                try:
                    if self.model_initializer.should_retrain():
                        logger.warning("⚠️ 觸發動態重訓練（性能驟降 or 市場狀態劇變 or 樣本累積）...")
                        await self.model_initializer.force_retrain()
                        logger.info("✅ 動態重訓練完成，模型已更新")
                except Exception as e:
                    logger.error(f"❌ 動態重訓練失敗: {e}")
            
            # 步驟 1：獲取並顯示持倉狀態
            positions = await self._get_and_display_positions()
            
            # 步驟 2：獲取賬戶餘額信息（v3.17.2+：優先使用WebSocket）
            account_info = None
            
            # 🔥 v3.17.2+：優先從WebSocket獲取（無REST API請求）
            if self.websocket_manager and self.websocket_manager.account_feed:
                account_info = self.websocket_manager.get_account_balance()
                if account_info:
                    logger.debug("📡 從WebSocket獲取帳戶餘額")
            
            # REST備援
            if not account_info:
                logger.debug("📡 WebSocket帳戶數據不可用，使用REST API備援")
                account_info = await self.binance_client.get_account_balance()
            
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
                logger.warning("⚠️  無可交易交易對")
                return
            
            logger.info(f"📊 掃描 {len(symbols)} 個交易對中...")
            
            # 步驟 5：批量分析並生成信號
            signals = []
            for symbol in symbols:
                try:
                    # 獲取多時間框架數據
                    multi_tf_data = await self.data_service.get_multi_timeframe_data(symbol)
                    
                    if not multi_tf_data:
                        continue
                    
                    # 調用 SelfLearningTrader 分析
                    signal = self.self_learning_trader.analyze(symbol, multi_tf_data)
                    
                    if signal:
                        signals.append(signal)
                        self.stats['total_signals'] += 1
                    
                except Exception as e:
                    logger.debug(f"分析 {symbol} 跳過: {e}")
            
            if signals:
                logger.info(f"✅ 發現 {len(signals)} 個交易信號")
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
                    max_positions=None  # 使用Config.MAX_CONCURRENT_ORDERS
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
        """獲取並顯示當前持倉狀態"""
        try:
            positions = await self.binance_client.get_positions()
            
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
                        all_trades = self.trade_recorder.get_trades()
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
            all_trades = self.trade_recorder.get_trades()
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
            all_trades = self.trade_recorder.get_trades()
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
            trades = self.trade_recorder.get_trades(days=1)
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
