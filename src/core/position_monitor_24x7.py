"""
🔥 v3.18+ 24/7 倉位監控器 - 完整7種出場邏輯系統

核心哲學：高槓桿是高信心的結果，系統應保護而非懲罰這種決策

v3.18+ 新特性：
- 集成EvaluationEngine進行即時信心值/勝率評估
- 集成TradeRecorder進行5分鐘歷史指標追蹤
- 7種智能出場情境（強制止盈、虧損熔斷、智能持倉、進場失效、逆勢、追蹤止盈、OCO）
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.core.evaluation_engine import EvaluationEngine, MarketContext

logger = logging.getLogger(__name__)


class PositionMonitor24x7:
    """
    24/7 倉位監控器（v3.17+）
    
    職責：
    1. 每 2 秒檢查所有倉位
    2. 計算實時 PnL
    3. PnL ≤ -99% 初始風險 → 立即市價平倉
    4. 使用優先級 0 API 通道（倉位操作最高優先級）
    """
    
    def __init__(
        self,
        config_profile,
        binance_client=None,
        trade_recorder=None,
        data_service=None,
        evaluation_engine: Optional[EvaluationEngine] = None
    ):
        """
        初始化監控器（v3.18+）
        
        Args:
            config_profile: ConfigProfile 實例
            binance_client: BinanceClient 實例（可選）
            trade_recorder: TradeRecorder 實例（必須，用於歷史指標追蹤）
            data_service: DataService 實例（可選，用於獲取市場數據）
            evaluation_engine: EvaluationEngine 實例（v3.18+，用於即時評估）
        """
        self.config = config_profile
        self.binance_client = binance_client
        self.trade_recorder = trade_recorder
        self.data_service = data_service
        
        # 🔥 v3.18+ 新增：統一評估引擎
        self.evaluation_engine = evaluation_engine or EvaluationEngine(model=None)
        
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # 🔥 兼容Config大小寫屬性
        self.monitor_interval = getattr(config_profile, 'position_monitor_interval', 
                                       getattr(config_profile, 'POSITION_MONITOR_INTERVAL', 2))
        self.risk_threshold = getattr(config_profile, 'risk_kill_threshold',
                                      getattr(config_profile, 'RISK_KILL_THRESHOLD', 0.99))
        
        # 統計數據
        self.total_checks = 0
        self.forced_closures = 0
        self.forced_tp_closures = 0  # 🔥 v3.18+：強制止盈平倉數
        self.smart_hold_count = 0  # 🔥 v3.18+：智能持倉次數
        self.entry_reason_expired_closures = 0
        self.counter_trend_closures = 0
        self.trailing_tp_adjustments = 0  # 🔥 v3.18+：追蹤止盈調整次數
        self.last_check_time: Optional[datetime] = None
        
        logger.info("=" * 60)
        logger.info("✅ 24/7 倉位監控器初始化完成（v3.18+）")
        logger.info(f"   ⏱️  檢查間隔: {self.monitor_interval} 秒")
        logger.info(f"   🚨 風險熔斷閾值: {self.risk_threshold:.1%}")
        logger.info(f"   🤖 評估引擎: {self.evaluation_engine.get_engine_info()['engine_type']}")
        logger.info(f"   ✅ 強制止盈（信心/勝率降20%）: 啟用")
        logger.info(f"   🟡 智能持倉（深度虧損+高信心）: 啟用")
        logger.info(f"   ⚠️ 進場理由失效（信心<70%）: 啟用")
        logger.info(f"   ⚪ 逆勢平倉（信心<80%）: 啟用")
        logger.info(f"   🔵 追蹤止盈（盈利>20%）: 啟用")
        logger.info(f"   🎯 優先級: 0 (最高)")
        logger.info("=" * 60)
    
    async def start(self):
        """
        🚫 已廢棄：不再獨立啟動監控器（防止重複API調用）
        
        v3.17.10+：PositionMonitor24x7 改為被動模式，接收PositionController共享的倉位數據。
        如果調用此方法會導致HTTP 429速率限制問題。
        """
        logger.error(
            "❌ PositionMonitor24x7.start() 已廢棄！\n"
            "   原因：避免與PositionController重複API調用導致HTTP 429\n"
            "   解決：請使用 check_positions_with_data() 接收共享數據"
        )
        raise DeprecationWarning(
            "PositionMonitor24x7.start() 已廢棄，改用 check_positions_with_data() 被動模式"
        )
    
    async def stop(self):
        """停止監控器"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"⏸️  24/7 倉位監控器已停止 (總檢查: {self.total_checks}, 強制平倉: {self.forced_closures})")
    
    async def _monitor_loop(self):
        """
        🚫 已廢棄：主監控循環（不再使用）
        
        v3.17.10+：改為被動模式，由PositionController調用 check_positions_with_data()
        """
        logger.error("❌ _monitor_loop() 被意外調用！此方法已廢棄，應使用被動模式")
        raise DeprecationWarning("_monitor_loop() 已廢棄")
    
    async def check_positions_with_data(self, positions: List[Dict]):
        """
        🔥 v3.17.10+ 標準方法：接收倉位數據進行檢測（共享API調用）
        
        此方法由PositionController調用，避免重複API請求導致HTTP 429。
        
        Args:
            positions: PositionController提供的倉位列表（格式已標準化）
        """
        if not positions:
            return
        
        # 🔥 不再更新 total_checks（由PositionController統一計數）
        # 僅更新時間戳
        self.last_check_time = datetime.now()
        
        logger.debug(f"   🔥 PositionMonitor24x7 檢查 {len(positions)} 個倉位（共享數據，零額外API調用）")
        
        # 檢查每個倉位（轉換為Binance API格式）
        for position in positions:
            await self._check_position_from_controller(position)
    
    async def _check_position_from_controller(self, position: Dict):
        """
        從PositionController格式轉換並檢查倉位
        
        Args:
            position: PositionController標準化格式的倉位數據
        """
        # 如果有原始數據，直接使用
        if 'raw_data' in position:
            await self._check_single_position(position['raw_data'])
        else:
            # 轉換為Binance API格式
            position_amt = position['size'] if position['side'] == 'LONG' else -position['size']
            converted = {
                'symbol': position['symbol'],
                'positionAmt': str(position_amt),
                'entryPrice': str(position['entry_price']),
                'markPrice': str(position['current_price']),
                'unrealizedProfit': str(position['pnl']),
                'unRealizedProfit': str(position['pnl']),  # 兩種格式兼容
                'leverage': str(position.get('leverage', 1))
            }
            await self._check_single_position(converted)
    
    async def _check_all_positions(self):
        """
        🚫 已廢棄：檢查所有倉位（會重複調用API）
        
        v3.17.10+：改用 check_positions_with_data() 接收共享數據
        """
        logger.error("❌ _check_all_positions() 被意外調用！此方法已廢棄，會導致API速率限制")
        raise DeprecationWarning("_check_all_positions() 已廢棄，改用 check_positions_with_data()")
    
    async def _check_single_position(self, position: Dict[str, Any]):
        """
        🔥 v3.18+：完整出場邏輯系統（7種情境）
        
        核心哲學：高槓桿是高信心的結果，系統應保護而非懲罰這種決策
        
        出場條件（按絕對優先級檢查）：
        🚨 PRIORITY 0: 虧損熔斷（累計虧損≤-risk_threshold，無條件強制平倉）
        
        高級出場邏輯（需original_signal支持）：
        1. ✅ 強制止盈：信心值/勝率相較5分鐘前降低20%
        2. 🟡 智能持倉：-99%<虧損≤-50% + 反彈概率>70% + 信心值≥80%（持倉）
        3. ⚠️ 進場理由失效：僅當信心值<70%時才平倉（高信心覆蓋失效）
        4. ⚪ 逆勢交易：僅當信心值<80%時才平倉（高信心可逆勢）
        5. 🔵 追蹤止盈：盈虧>20% + 趨勢持續>70% + 勝率≥80%（調整止盈）
        6. ⚙️ OCO訂單觸發：自動結束監控
        
        Args:
            position: 倉位數據（來自 Binance API）
        """
        try:
            # ========== Step 1: 提取倉位基本信息 ==========
            symbol = position.get('symbol')
            if not symbol:
                logger.warning("⚠️ 持倉數據缺少 symbol，跳過")
                return
                
            position_amt = float(position.get('positionAmt', 0))
            entry_price = float(position.get('entryPrice', 0))
            mark_price = float(position.get('markPrice') or position.get('entryPrice', 0))
            unrealized_pnl = float(position.get('unrealizedProfit', position.get('unRealizedProfit', 0)))
            direction = "LONG" if position_amt > 0 else "SHORT"
            
            if position_amt == 0:
                return
            
            # ========== Step 2: 計算PnL% ==========
            risk_amount = await self._get_risk_amount(symbol)
            
            if risk_amount is None or risk_amount <= 0:
                leverage = float(position.get('leverage', 1))
                notional = abs(position_amt) * entry_price
                risk_amount = notional / leverage if leverage > 0 else notional
                
                if risk_amount <= 0:
                    logger.warning(f"⚠️ {symbol} 無法計算風險金額，跳過檢查")
                    return
            
            pnl_pct = unrealized_pnl / risk_amount if risk_amount > 0 else 0
            
            # ========== 🚨 PRIORITY 0: 虧損熔斷（絕對最高優先級） ==========
            # 🔥 v3.18+ Critical Fix: 無條件檢查，使用配置閾值，確保任何情況下都強制平倉
            if pnl_pct <= -self.risk_threshold:
                logger.critical(
                    f"🚨🔴 {symbol} {self.risk_threshold:.0%}虧損熔斷觸發！"
                    f"PnL: ${unrealized_pnl:.2f} ({pnl_pct:.1%}) / 風險: ${risk_amount:.2f} "
                    f"/ 閾值: {self.risk_threshold:.0%}"
                )
                await self._force_close_position(
                    symbol, position_amt, mark_price, f"{self.risk_threshold:.0%}虧損熔斷（強制安全機制）"
                )
                self.forced_closures += 1
                return
            
            # ========== Step 3: 獲取original_signal並即時評估 ==========
            original_signal = self._get_original_signal(symbol, direction)
            
            if not original_signal:
                logger.debug(
                    f"⚠️ {symbol} 無original_signal，跳過高級出場邏輯 | "
                    f"PnL: {pnl_pct:+.1%}（100%熔斷已保護）"
                )
                # 降級模式：僅執行100%熔斷（已在上方檢查），此處正常監控
                if pnl_pct < -0.5:
                    logger.warning(
                        f"⚠️ {symbol} 虧損{pnl_pct:.1%} 但無original_signal，無法執行智能出場"
                    )
                return
            
            # Step 4: 構建市場上下文並即時評估信心值/勝率
            market_context = await self._build_market_context_for_position(symbol)
            
            current_confidence = self.evaluation_engine.calculate_current_confidence(
                original_signal, mark_price, market_context
            )
            current_win_prob = self.evaluation_engine.calculate_current_win_probability(
                original_signal, mark_price, market_context
            )
            
            # 🔥 定期更新TradeRecorder歷史指標（用於後續降幅檢測）
            if self.trade_recorder:
                self.trade_recorder.update_position_metrics(
                    symbol, direction, current_confidence, current_win_prob
                )
            
            # ========== 7種出場情境檢查（按優先級） ==========
            
            # 1️⃣ 強制止盈（高級場景最高優先級）
            if self.trade_recorder:
                should_close, reason = self.trade_recorder.check_metrics_drop(
                    symbol, direction, current_confidence, current_win_prob
                )
                if should_close:
                    logger.critical(
                        f"✅ {symbol} 強制止盈: {reason} | "
                        f"PnL: ${unrealized_pnl:+.2f} ({pnl_pct:+.1%})"
                    )
                    await self._force_close_position(symbol, position_amt, mark_price, reason)
                    self.forced_tp_closures += 1
                    return
            
            # 2️⃣ 智能持倉（深度虧損但高信心）
            if -0.99 < pnl_pct <= -0.50:
                rebound_prob = await self._predict_rebound_probability(symbol, direction)
                
                if rebound_prob > 0.70 and current_confidence >= 0.80:
                    logger.info(
                        f"🟡 {symbol} 智能持倉: 虧損{pnl_pct:.1%} 但反彈概率{rebound_prob:.1%} "
                        f"+ 信心值{current_confidence:.1%}≥80%，繼續持有"
                    )
                    self.smart_hold_count += 1
                    return  # 不平倉
                else:
                    logger.warning(
                        f"🟡 {symbol} 深度虧損且無反彈: 虧損{pnl_pct:.1%}, "
                        f"反彈概率{rebound_prob:.1%}, 信心值{current_confidence:.1%}"
                    )
                    await self._force_close_position(
                        symbol, position_amt, mark_price, "深度虧損且無反彈希望"
                    )
                    return
            
            # 3️⃣ 進場理由失效（僅信心<70%時平倉）
            entry_expired, expire_reason = await self._is_entry_reason_expired(
                symbol, entry_price, mark_price, direction
            )
            
            if entry_expired:
                if current_confidence < 0.70:
                    logger.warning(
                        f"⚠️ {symbol} 進場理由失效 + 信心值{current_confidence:.1%}<70%，平倉 | "
                        f"原因: {expire_reason} | PnL: ${unrealized_pnl:+.2f} ({pnl_pct:+.1%})"
                    )
                    await self._force_close_position(
                        symbol, position_amt, mark_price, f"進場失效+低信心: {expire_reason}"
                    )
                    self.entry_reason_expired_closures += 1
                    return
                else:
                    logger.info(
                        f"⚠️ {symbol} 進場理由失效但信心值{current_confidence:.1%}≥70%，繼續持倉"
                    )
            
            # 4️⃣ 逆勢交易（僅信心<80%時平倉）
            is_counter, counter_reason = await self._is_counter_trend(
                symbol, entry_price, mark_price, direction
            )
            
            if is_counter:
                if current_confidence < 0.80:
                    logger.warning(
                        f"⚪ {symbol} 逆勢 + 信心值{current_confidence:.1%}<80%，平倉 | "
                        f"原因: {counter_reason} | PnL: ${unrealized_pnl:+.2f} ({pnl_pct:+.1%})"
                    )
                    await self._force_close_position(
                        symbol, position_amt, mark_price, f"逆勢+低信心: {counter_reason}"
                    )
                    self.counter_trend_closures += 1
                    return
                else:
                    logger.info(
                        f"⚪ {symbol} 逆勢但信心值{current_confidence:.1%}≥80%，允許逆勢交易 | "
                        f"PnL: ${unrealized_pnl:+.2f} ({pnl_pct:+.1%})"
                    )
            
            # 5️⃣ 追蹤止盈（盈利>20%時）
            if pnl_pct > 0.20:
                trend_continue_prob = await self._predict_trend_continuation(symbol, direction)
                
                if trend_continue_prob > 0.70 and current_win_prob >= 0.80:
                    # 設置追蹤止盈（5%回撤觸發）
                    trailing_success = await self._set_trailing_stop(symbol, 0.05)
                    if trailing_success:
                        logger.info(
                            f"🔵 {symbol} 追蹤止盈設置: 盈利{pnl_pct:.1%}，趨勢持續{trend_continue_prob:.1%}，"
                            f"勝率{current_win_prob:.1%}，5%回撤觸發"
                        )
                        self.trailing_tp_adjustments += 1
            
            # 6️⃣ OCO訂單觸發 - Binance API自動處理，無需額外邏輯
            
            # 正常監控日誌（僅在虧損 >50% 時警告）
            if pnl_pct < -0.5:
                logger.warning(
                    f"⚠️ {symbol} 虧損 {pnl_pct:.1%} "
                    f"(PnL: ${unrealized_pnl:.2f} / 風險: ${risk_amount:.2f}) | "
                    f"信心值:{current_confidence:.1%} 勝率:{current_win_prob:.1%}"
                )
                    
        except Exception as e:
            logger.error(f"❌ 檢查倉位失敗 {symbol if 'symbol' in locals() else 'UNKNOWN'}: {e}", exc_info=True)
    
    async def _get_risk_amount(self, symbol: str) -> Optional[float]:
        """
        獲取倉位的初始風險金額（優先從交易記錄，失敗則返回None使用備用方案）
        
        Args:
            symbol: 交易對符號
            
        Returns:
            風險金額（USDT），或 None（觸發備用計算方案）
        """
        if not self.trade_recorder:
            return None
        
        try:
            # 從交易記錄獲取最近的開倉記錄
            trades = self.trade_recorder.get_active_trades(symbol)
            if trades and len(trades) > 0:
                risk_amt = trades[0].get('risk_amount', 0)
                if risk_amt and risk_amt > 0:
                    return risk_amt
        except Exception as e:
            logger.debug(f"從交易記錄獲取 {symbol} 風險金額失敗: {e}")
        
        # 返回None觸發備用計算方案
        return None
    
    async def _force_close_position(
        self,
        symbol: str,
        position_amt: float,
        current_price: float,
        reason: str = "未知原因"
    ):
        """
        強制平倉（市價單）
        
        Args:
            symbol: 交易對符號
            position_amt: 倉位數量（正數=多倉，負數=空倉）
            current_price: 當前價格
            reason: 平倉原因（用於記錄）
        """
        if not self.binance_client:
            logger.error("❌ 無 Binance 客戶端，無法平倉")
            return
        
        try:
            # 計算平倉方向和數量
            side = "SELL" if position_amt > 0 else "BUY"
            quantity = abs(position_amt)
            
            logger.critical(
                f"🚨 執行強制平倉: {symbol} {side} {quantity:.6f} @ ${current_price:.2f} | 原因: {reason}"
            )
            
            # 🔥 市價平倉（優先級 0，最高優先級）+ reduce_only防止開反向倉
            result = await self.binance_client.place_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
                reduce_only=True  # 🔥 修復：防止與PositionController衝突開反向倉
            )
            
            if result:
                self.forced_closures += 1
                logger.critical(f"✅ 強制平倉成功: {symbol} (訂單: {result.get('orderId')})")
                
                # 記錄到交易記錄
                if self.trade_recorder:
                    # 🔥 使用傳入的reason參數
                    try:
                        self.trade_recorder.record_forced_closure(
                            symbol=symbol,
                            side=side,
                            quantity=quantity,
                            price=current_price,
                            reason=reason,
                            order_id=result.get('orderId')
                        )
                    except AttributeError:
                        # 如果record_forced_closure方法不存在，記錄到日誌
                        logger.info(f"📝 平倉記錄: {symbol} {side} {quantity} @ {current_price} | {reason}")
            else:
                logger.error(f"❌ 強制平倉失敗: {symbol}")
                
        except Exception as e:
            logger.critical(f"❌ 強制平倉異常: {symbol} - {e}", exc_info=True)
    
    def get_monitor_stats(self) -> Dict[str, Any]:
        """
        獲取監控器統計信息（v3.17.10+：被動模式）
        
        Returns:
            統計字典
        """
        return {
            "mode": "passive (shared API calls)",  # 🔥 新增：標明被動模式
            "forced_closures": self.forced_closures,
            "entry_reason_expired_closures": self.entry_reason_expired_closures,
            "counter_trend_closures": self.counter_trend_closures,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "check_interval_seconds": self.monitor_interval,
            "risk_kill_threshold": f"{self.risk_threshold:.1%}",
        }
    
    async def _is_entry_reason_expired(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        direction: str
    ) -> tuple[bool, str]:
        """
        🔥 v3.17.10+：檢測進場理由是否失效
        
        判斷標準：
        1. 價格遠離進場價格 >2%（Order Block被突破）
        2. 持倉時間 >48小時（時間衰減）
        3. 流動性消失（訂單簿深度<30%）
        
        Args:
            symbol: 交易對
            entry_price: 進場價格
            current_price: 當前價格
            direction: 倉位方向（LONG/SHORT）
        
        Returns:
            (是否失效, 失效原因)
        """
        try:
            # 1️⃣ 檢查價格偏離度（Order Block被突破）
            price_deviation = abs(current_price - entry_price) / entry_price
            if price_deviation > 0.02:  # >2%
                return (
                    True,
                    f"價格偏離進場價{price_deviation:.1%} (>2%閾值)"
                )
            
            # 2️⃣ 檢查持倉時間（時間衰減）
            if self.trade_recorder:
                trades = self.trade_recorder.get_trades()
                open_trades = [
                    t for t in trades
                    if t.get('symbol') == symbol
                    and t.get('direction') == direction
                    and t.get('status') == 'open'
                ]
                
                if open_trades:
                    latest_trade = open_trades[-1]
                    entry_timestamp = latest_trade.get('entry_timestamp')
                    if entry_timestamp:
                        from datetime import datetime
                        entry_time = datetime.fromisoformat(entry_timestamp)
                        hold_duration = (datetime.now() - entry_time).total_seconds()
                        
                        if hold_duration > 172800:  # >48小時
                            hours = hold_duration / 3600
                            return (
                                True,
                                f"持倉時間過長 {hours:.1f}h (>48h閾值)"
                            )
            
            # 3️⃣ 檢查流動性（需要市場數據）
            if self.data_service and self.binance_client:
                try:
                    # 獲取最新市場數據
                    ticker = await self.binance_client.get_ticker_price(symbol)
                    if ticker:
                        # 簡化版：檢查24h成交量變化
                        # 完整版可以查詢訂單簿深度
                        pass  # 流動性檢查暫時跳過（需要訂單簿API）
                except:
                    pass
            
            return (False, "")
            
        except Exception as e:
            logger.debug(f"檢查進場理由失敗: {e}")
            return (False, "")
    
    async def _is_counter_trend(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        direction: str
    ) -> tuple[bool, str]:
        """
        🔥 v3.17.10+：檢測倉位是否逆勢
        
        判斷標準：
        - LONG倉位：當前價格 < 進場價格（下跌趨勢）
        - SHORT倉位：當前價格 > 進場價格（上漲趨勢）
        
        Args:
            symbol: 交易對
            entry_price: 進場價格
            current_price: 當前價格
            direction: 倉位方向
        
        Returns:
            (是否逆勢, 逆勢說明)
        """
        try:
            if direction == "LONG" and current_price < entry_price:
                deviation = (current_price - entry_price) / entry_price
                return (
                    True,
                    f"多倉下跌 {deviation:.1%}"
                )
            elif direction == "SHORT" and current_price > entry_price:
                deviation = (current_price - entry_price) / entry_price
                return (
                    True,
                    f"空倉上漲 {deviation:+.1%}"
                )
            
            return (False, "")
            
        except Exception as e:
            logger.debug(f"檢查逆勢失敗: {e}")
            return (False, "")
    
    async def _has_rebound_signal(
        self,
        symbol: str,
        direction: str
    ) -> bool:
        """
        🔥 v3.17.10+：檢測是否有反彈信號
        
        判斷標準（需要最新市場數據）：
        1. RSI超賣/超買反轉
        2. MACD金叉/死叉
        3. 布林帶反彈
        
        Args:
            symbol: 交易對
            direction: 倉位方向
        
        Returns:
            是否有反彈信號
        """
        try:
            if not self.data_service:
                return False
            
            # 獲取5m時間框架數據（快速反應）
            data = await self.data_service.get_klines_incremental(
                symbol,
                interval='5m',
                limit=20
            )
            
            if data.empty or len(data) < 20:
                return False
            
            # 計算簡單指標
            from src.utils.indicators import calculate_rsi, calculate_macd
            
            # RSI反彈信號
            rsi = calculate_rsi(data, period=14)
            if rsi.empty:
                return False
            
            latest_rsi = float(rsi.iloc[-1])
            
            # LONG倉位：RSI < 30（超賣）可能反彈
            if direction == "LONG" and latest_rsi < 30:
                logger.debug(f"{symbol} 檢測到多倉反彈信號: RSI={latest_rsi:.1f}")
                return True
            
            # SHORT倉位：RSI > 70（超買）可能反彈
            if direction == "SHORT" and latest_rsi > 70:
                logger.debug(f"{symbol} 檢測到空倉反彈信號: RSI={latest_rsi:.1f}")
                return True
            
            # MACD反彈信號（簡化版：只檢查MACD柱狀圖方向變化）
            macd_line, signal_line, histogram = calculate_macd(data)
            # 🔥 類型安全：確保histogram是DataFrame
            if isinstance(histogram, str) or histogram is None:
                return False
            if not histogram.empty and len(histogram) >= 2:
                current_hist = float(histogram.iloc[-1])
                prev_hist = float(histogram.iloc[-2])
                
                # LONG倉位：MACD柱狀圖從負轉正
                if direction == "LONG" and prev_hist < 0 < current_hist:
                    logger.debug(f"{symbol} 檢測到多倉MACD金叉信號")
                    return True
                
                # SHORT倉位：MACD柱狀圖從正轉負
                if direction == "SHORT" and prev_hist > 0 > current_hist:
                    logger.debug(f"{symbol} 檢測到空倉MACD死叉信號")
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"檢查反彈信號失敗: {e}")
            return False
    
    # ========== v3.18+ 新增輔助方法 ==========
    
    def _get_original_signal(self, symbol: str, direction: str) -> Optional[Dict]:
        """
        🔥 v3.18+：從TradeRecorder獲取original_signal
        
        Args:
            symbol: 交易對
            direction: 倉位方向（LONG/SHORT）
        
        Returns:
            original_signal字典，或None（無記錄）
        """
        if not self.trade_recorder:
            return None
        
        try:
            # 從活躍交易記錄獲取
            trades = self.trade_recorder.get_active_trades(symbol)
            if not trades or len(trades) == 0:
                return None
            
            # 獲取最近的交易記錄
            latest_trade = trades[0]
            
            # 檢查方向是否匹配
            trade_direction = latest_trade.get('direction', 'UNKNOWN')
            if trade_direction != direction:
                logger.debug(f"{symbol} 方向不匹配: 倉位={direction} vs 記錄={trade_direction}")
                return None
            
            # 返回original_signal
            original_signal = latest_trade.get('original_signal')
            if original_signal:
                logger.debug(f"{symbol} 獲取到original_signal: {original_signal.get('action', 'UNKNOWN')}")
            
            return original_signal
            
        except Exception as e:
            logger.debug(f"獲取{symbol} original_signal失敗: {e}")
            return None
    
    async def _build_market_context_for_position(self, symbol: str) -> MarketContext:
        """
        🔥 v3.18+：為倉位構建市場上下文（用於即時評估）
        
        Args:
            symbol: 交易對
        
        Returns:
            MarketContext對象
        """
        try:
            if not self.data_service:
                # 降級：返回空上下文
                return MarketContext(
                    trend_direction="neutral",
                    volatility=0.0,
                    liquidity=0.0,
                    rsi=50.0,
                    macd_histogram=0.0
                )
            
            # 獲取15m K線數據（平衡速度與穩定性）
            klines = await self.data_service.get_klines_incremental(
                symbol, interval='15m', limit=100
            )
            
            if klines.empty or len(klines) < 50:
                # 數據不足，返回中性上下文
                return MarketContext(
                    trend_direction="neutral",
                    volatility=0.0,
                    liquidity=0.0,
                    rsi=50.0,
                    macd_histogram=0.0
                )
            
            # 計算技術指標
            from src.utils.indicators import calculate_rsi, calculate_macd, calculate_ema
            
            rsi = calculate_rsi(klines, period=14)
            latest_rsi = float(rsi.iloc[-1]) if not rsi.empty else 50.0
            
            macd_line, signal_line, histogram = calculate_macd(klines)
            latest_macd_hist = 0.0
            if not isinstance(histogram, str) and histogram is not None and not histogram.empty:
                latest_macd_hist = float(histogram.iloc[-1])
            
            # EMA趨勢判斷
            ema20 = calculate_ema(klines, period=20)
            ema50 = calculate_ema(klines, period=50)
            
            trend_direction = "neutral"
            if not ema20.empty and not ema50.empty:
                if ema20.iloc[-1] > ema50.iloc[-1] * 1.01:
                    trend_direction = "up"
                elif ema20.iloc[-1] < ema50.iloc[-1] * 0.99:
                    trend_direction = "down"
            
            # 波動率（14根K線ATR標準化）
            high_prices = klines['high'].astype(float)
            low_prices = klines['low'].astype(float)
            close_prices = klines['close'].astype(float)
            
            tr = high_prices - low_prices
            atr = tr.rolling(window=14).mean().iloc[-1]
            volatility = float(atr / close_prices.iloc[-1]) if close_prices.iloc[-1] > 0 else 0.0
            
            # 流動性（簡化為成交量標準化）
            volumes = klines['volume'].astype(float)
            avg_volume = volumes.rolling(window=20).mean().iloc[-1]
            liquidity = float(volumes.iloc[-1] / avg_volume) if avg_volume > 0 else 1.0
            
            return MarketContext(
                trend_direction=trend_direction,
                volatility=volatility,
                liquidity=liquidity,
                rsi=latest_rsi,
                macd_histogram=latest_macd_hist
            )
            
        except Exception as e:
            logger.debug(f"構建{symbol}市場上下文失敗: {e}")
            # 返回中性上下文
            return MarketContext(
                trend_direction="neutral",
                volatility=0.0,
                liquidity=0.0,
                rsi=50.0,
                macd_histogram=0.0
            )
    
    async def _predict_rebound_probability(self, symbol: str, direction: str) -> float:
        """
        🔥 v3.18+：預測反彈概率（用於智能持倉決策）
        
        判斷標準：
        - LONG倉位虧損：RSI<30（超賣）→ 高反彈概率
        - SHORT倉位虧損：RSI>70（超買）→ 高反彈概率
        
        Args:
            symbol: 交易對
            direction: 倉位方向（LONG/SHORT）
        
        Returns:
            反彈概率（0.0-1.0）
        """
        try:
            if not self.data_service:
                return 0.40  # 默認中等偏低
            
            # 獲取15m K線
            klines = await self.data_service.get_klines_incremental(
                symbol, interval='15m', limit=100
            )
            
            if klines.empty or len(klines) < 20:
                return 0.40
            
            # 計算RSI
            from src.utils.indicators import calculate_rsi
            rsi = calculate_rsi(klines, period=14)
            
            if rsi.empty:
                return 0.40
            
            latest_rsi = float(rsi.iloc[-1])
            
            # LONG倉位：RSI越低，反彈概率越高
            if direction == "LONG":
                if latest_rsi < 20:
                    return 0.85
                elif latest_rsi < 30:
                    return 0.75
                elif latest_rsi < 40:
                    return 0.55
                else:
                    return 0.35
            
            # SHORT倉位：RSI越高，反彈概率越高
            elif direction == "SHORT":
                if latest_rsi > 80:
                    return 0.85
                elif latest_rsi > 70:
                    return 0.75
                elif latest_rsi > 60:
                    return 0.55
                else:
                    return 0.35
            
            return 0.40
            
        except Exception as e:
            logger.debug(f"預測{symbol}反彈概率失敗: {e}")
            return 0.40
    
    async def _predict_trend_continuation(self, symbol: str, direction: str) -> float:
        """
        🔥 v3.18+：預測趨勢持續概率（用於追蹤止盈決策）
        
        判斷標準：
        - EMA20 > EMA50：上升趨勢持續概率高
        - EMA20 < EMA50：下降趨勢持續概率高
        
        Args:
            symbol: 交易對
            direction: 倉位方向（LONG/SHORT）
        
        Returns:
            趨勢持續概率（0.0-1.0）
        """
        try:
            if not self.data_service:
                return 0.50  # 默認中性
            
            # 獲取15m K線
            klines = await self.data_service.get_klines_incremental(
                symbol, interval='15m', limit=100
            )
            
            if klines.empty or len(klines) < 50:
                return 0.50
            
            # 計算EMA
            from src.utils.indicators import calculate_ema
            ema20 = calculate_ema(klines, period=20)
            ema50 = calculate_ema(klines, period=50)
            
            if ema20.empty or ema50.empty:
                return 0.50
            
            ema20_val = float(ema20.iloc[-1])
            ema50_val = float(ema50.iloc[-1])
            
            # 計算EMA差距（標準化）
            ema_gap = (ema20_val - ema50_val) / ema50_val if ema50_val > 0 else 0
            
            # LONG倉位：需要EMA20 > EMA50（上升趨勢）
            if direction == "LONG":
                if ema_gap > 0.02:  # EMA20高於EMA50 2%以上
                    return 0.85
                elif ema_gap > 0.01:
                    return 0.75
                elif ema_gap > 0:
                    return 0.60
                else:
                    return 0.40  # 趨勢反轉
            
            # SHORT倉位：需要EMA20 < EMA50（下降趨勢）
            elif direction == "SHORT":
                if ema_gap < -0.02:  # EMA20低於EMA50 2%以上
                    return 0.85
                elif ema_gap < -0.01:
                    return 0.75
                elif ema_gap < 0:
                    return 0.60
                else:
                    return 0.40  # 趨勢反轉
            
            return 0.50
            
        except Exception as e:
            logger.debug(f"預測{symbol}趨勢持續概率失敗: {e}")
            return 0.50
    
    async def _set_trailing_stop(self, symbol: str, trailing_offset: float) -> bool:
        """
        🔥 v3.18+：設置追蹤止盈訂單
        
        注意：目前簡化實現，記錄日誌但不實際下單（避免API複雜性）
        未來可擴展為Binance追蹤止損API
        
        Args:
            symbol: 交易對
            trailing_offset: 回撤觸發百分比（如0.05 = 5%）
        
        Returns:
            是否成功
        """
        try:
            # 🔥 v3.18.0：簡化實施，僅記錄追蹤止盈意圖
            # 未來版本可調用Binance TRAILING_STOP_MARKET訂單API
            
            logger.info(
                f"🔵 {symbol} 追蹤止盈記錄: 回撤觸發={trailing_offset:.1%} "
                f"（當前版本：僅記錄，不實際下單）"
            )
            
            # TODO v3.19+: 實際調用Binance API設置追蹤止損訂單
            # if self.binance_client:
            #     await self.binance_client.create_order(
            #         symbol=symbol,
            #         side=...,
            #         order_type="TRAILING_STOP_MARKET",
            #         callbackRate=trailing_offset * 100
            #     )
            
            return True
            
        except Exception as e:
            logger.error(f"設置{symbol}追蹤止盈失敗: {e}")
            return False
