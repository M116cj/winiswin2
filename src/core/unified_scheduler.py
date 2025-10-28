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
    
    架構：
    ┌─────────────────────────────────┐
    │    UnifiedScheduler (調度器)    │
    ├─────────────────────────────────┤
    │ • SelfLearningTrader (決策)     │
    │ • PositionController (監控)     │
    │ • ModelEvaluator (評級)         │
    │ • DailyReporter (報告)          │
    └─────────────────────────────────┘
    """
    
    def __init__(
        self,
        config: Config,
        binance_client: BinanceClient,
        data_service: DataService,
        trade_recorder=None
    ):
        """
        初始化 UnifiedScheduler
        
        Args:
            config: 配置對象
            binance_client: Binance 客戶端
            data_service: 數據服務
            trade_recorder: 交易記錄器
        """
        self.config = config
        self.binance_client = binance_client
        self.data_service = data_service
        self.trade_recorder = trade_recorder
        
        # 初始化核心組件
        self.self_learning_trader = SelfLearningTrader(
            config=config,
            binance_client=binance_client
        )
        
        self.position_controller = PositionController(
            binance_client=binance_client,
            self_learning_trader=self.self_learning_trader,
            monitor_interval=config.POSITION_MONITOR_INTERVAL,
            config=config
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
        logger.info("✅ UnifiedScheduler v3.17+ 初始化完成")
        logger.info("   🎯 模式: SelfLearningTrader")
        logger.info("   ⏱️  交易週期: 每 {} 秒".format(config.CYCLE_INTERVAL))
        logger.info("   🛡️  倉位監控: 每 {} 秒".format(config.POSITION_MONITOR_INTERVAL))
        logger.info("   📊 每日報告: 00:00 UTC")
        logger.info("=" * 80)
    
    async def start(self):
        """啟動調度器"""
        try:
            self.is_running = True
            logger.info("🚀 UnifiedScheduler 啟動中...")
            
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
        
        # 停止 PositionController
        await self.position_controller.stop_monitoring()
        
        # 輸出統計
        logger.info("=" * 80)
        logger.info("📊 UnifiedScheduler 統計:")
        logger.info(f"   總週期: {self.stats['total_cycles']}")
        logger.info(f"   總信號: {self.stats['total_signals']}")
        logger.info(f"   總訂單: {self.stats['total_orders']}")
        logger.info(f"   總報告: {self.stats['total_reports']}")
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
            
            # 步驟 1：獲取並顯示持倉狀態
            positions = await self._get_and_display_positions()
            
            # 步驟 2：獲取賬戶餘額信息
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
            executed_count = 0
            if signals and self.config.TRADING_ENABLED:
                # ✅ 保證金預算管理
                max_concurrent_orders = getattr(self.config, 'MAX_CONCURRENT_ORDERS', 5)
                
                # ✅ 計算可用倉位數量（減去已有持倉）
                active_position_count = len(positions)
                available_slots = max(0, max_concurrent_orders - active_position_count)
                
                if available_slots == 0:
                    logger.warning(f"⚠️ 已達最大倉位數量 ({active_position_count}/{max_concurrent_orders})，跳過本週期開倉")
                else:
                    available_for_trading = available_balance * 0.8  # 使用80%可用保證金
                    
                    logger.info(
                        f"📊 保證金預算: 可用=${available_balance:.2f} | "
                        f"可分配=${available_for_trading:.2f} | "
                        f"已有倉位={active_position_count} | "
                        f"可開倉位={available_slots}"
                    )
                    
                    # 限制信號數量（考慮已有持倉）
                    signals_to_execute = signals[:available_slots]
                    if len(signals) > available_slots:
                        logger.warning(f"⚠️ 信號過多({len(signals)}個)，僅執行前{available_slots}個")
                    
                    # 檢查保證金預算是否足夠
                    if len(signals_to_execute) == 0:
                        logger.info("⏸️ 無可執行信號")
                    else:
                        budget_per_position = available_for_trading / len(signals_to_execute)
                        
                        # ✅ 最小名義價值檢查（避免 "Margin insufficient"）
                        min_notional = getattr(self.config, 'MIN_NOTIONAL_VALUE', 10.0)
                        if budget_per_position < min_notional / 10:  # 預算太小（< 1 USDT）
                            logger.warning(
                                f"⚠️ 保證金預算不足: 每倉位${budget_per_position:.2f} < 最小要求${min_notional / 10:.2f}，"
                                f"跳過本週期開倉"
                            )
                        else:
                            for signal in signals_to_execute:
                                try:
                                    # 使用保證金預算而不是總權益
                                    success = await self._execute_signal(signal, budget_per_position, available_balance)
                                    if success:
                                        executed_count += 1
                                        self.stats['total_orders'] += 1
                                        logger.info(f"   ✅ 成交: {signal['symbol']} {signal['direction']} | 槓桿: {signal.get('leverage', 1)}x")
                                        # 重新獲取可用保證金（已更新）
                                        try:
                                            updated_info = await self.binance_client.get_account_balance()
                                            available_balance = updated_info['available_balance']
                                            logger.debug(f"   💰 更新可用保證金: ${available_balance:.2f}")
                                        except:
                                            pass
                                except Exception as e:
                                    logger.error(f"   ❌ 執行失敗 {signal['symbol']}: {e}")
            
            # 週期統計
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(f"✅ 週期完成 | 耗時: {cycle_duration:.1f}s | 新成交: {executed_count}")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ 交易週期執行失敗: {e}", exc_info=True)
    
    async def _get_trading_symbols(self) -> list:
        """獲取交易對列表（監控所有 USDT 永續合約）"""
        try:
            # 從配置獲取交易對列表
            if hasattr(self.config, 'TRADING_SYMBOLS') and self.config.TRADING_SYMBOLS:
                return self.config.TRADING_SYMBOLS
            
            # 否則獲取所有 USDT 永續合約
            exchange_info = await self.binance_client.get_exchange_info()
            symbols = [
                s['symbol'] for s in exchange_info.get('symbols', [])
                if s['symbol'].endswith('USDT') and s['status'] == 'TRADING'
            ]
            
            # 使用配置的限制數量（默認 200，可設為 999 監控所有）
            max_symbols = getattr(self.config, 'TOP_VOLATILITY_SYMBOLS', 200)
            logger.info(f"📊 掃描到 {len(symbols)} 個 USDT 永續合約，監控前 {max_symbols} 個")
            return symbols[:max_symbols]
            
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
            
            if not active_positions:
                logger.info("📦 當前持倉: 無")
                return []
            
            logger.info(f"📦 當前持倉: {len(active_positions)} 個")
            for pos in active_positions:
                symbol = pos['symbol']
                amt = float(pos['positionAmt'])
                direction = "LONG" if amt > 0 else "SHORT"
                entry_price = float(pos.get('entryPrice', 0))
                unrealized_pnl = float(pos.get('unRealizedProfit', 0))
                pnl_pct = (unrealized_pnl / (abs(amt) * entry_price) * 100) if entry_price > 0 else 0
                
                logger.info(f"   • {symbol} {direction} | 盈虧: ${unrealized_pnl:+.2f} ({pnl_pct:+.2f}%)")
            
            return active_positions
            
        except Exception as e:
            logger.error(f"❌ 獲取持倉失敗: {e}")
            return []
    
    async def _display_model_rating(self):
        """顯示模型評分狀態"""
        try:
            # 獲取交易記錄
            if not self.trade_recorder:
                return
            
            trades = self.trade_recorder.get_trades(days=1)
            
            if not trades:
                logger.info("🎯 模型評分: 無交易記錄")
                return
            
            # 評估模型
            evaluation = self.model_evaluator.evaluate_model(trades, period_days=1)
            
            score = evaluation.get('final_score', 0)
            grade = evaluation.get('grade', 'N/A')
            action = evaluation.get('action', 'N/A')
            total_trades = evaluation.get('total_trades', 0)
            win_rate = evaluation.get('win_rate', 0) * 100
            
            logger.info(f"🎯 模型評分: {score:.1f}/100 ({grade} 級) | 勝率: {win_rate:.1f}% | 交易: {total_trades} 筆 | 建議: {action}")
            
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
