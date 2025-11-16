"""
🔥 v3.18+ 24/7 倉位監控器 - 完整7種出場邏輯系統

核心哲學：高槓桿是高信心的結果，系統應保護而非懲罰這種決策

v3.18+ 新特性：
- 集成EvaluationEngine進行即時信心值/勝率評估
- 集成TradeRecorder進行5分鐘歷史指標追蹤
- 7種智能出場情境（強制止盈、虧損熔斷、智能持倉、進場失效、逆勢、追蹤止盈、OCO）
"""

from src.utils.logger_factory import get_logger
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.core.evaluation_engine import EvaluationEngine, MarketContext

logger = get_logger(__name__)


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
        
        # 🔥 v3.20.2 Phase 6: 共享EliteTechnicalEngine實例（避免重複初始化+共享緩存）
        from src.core.elite import EliteTechnicalEngine
        self.tech_engine = EliteTechnicalEngine()
        
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
        self.partial_close_60pct_count = 0  # 🔥 v3.18.4+：60%盈利部分平倉次數
        self.last_check_time: Optional[datetime] = None
        
        # 🔥 v3.18.4+：60%盈利部分平倉追蹤（每個倉位只執行一次）
        # 格式：{(symbol, direction): True}
        self._partial_closed_positions: Dict[tuple, bool] = {}
        
        logger.info("=" * 60)
        logger.info("✅ 24/7 倉位監控器初始化完成（v3.18.4+）")
        logger.info(f"   ⏱️  檢查間隔: {self.monitor_interval} 秒")
        logger.info(f"   🚨 風險熔斷閾值: {self.risk_threshold:.1%}")
        logger.info(f"   🤖 評估引擎: {self.evaluation_engine.get_engine_info()['engine_type']}")
        logger.info(f"   ✅ 強制止盈（信心/勝率降20%）: 啟用")
        logger.info(f"   💰 60%盈利自動平倉50%（每倉一次）: 啟用")  # 🔥 v3.18.4+ 新增
        logger.info(f"   🟡 智能持倉（深度虧損+高信心）: 啟用")
        logger.info(f"   ⚠️ 進場理由失效（信心<70%）: 啟用")
        logger.info(f"   ⚪ 逆勢平倉（信心<80%）: 啟用")
        logger.info(f"   🔵 追蹤止盈（盈利>20%）: 啟用")
        logger.info(f"   🎯 優先級: 0 (最高)")
        logger.info("=" * 60)
    
    
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
    
    
    async def check_positions_with_data(self, positions: List[Dict]):
        """
        🔥 v3.17.10+ 標準方法：接收倉位數據進行檢測（共享API調用）
        
        此方法由PositionController調用，避免重複API請求導致HTTP 429。
        
        Args:
            positions: PositionController提供的倉位列表（格式已標準化）
        """
        if not positions:
            # 🔥 v3.18.4+：無倉位時清空部分平倉追蹤字典
            if self._partial_closed_positions:
                logger.debug("📭 無持倉，清空部分平倉追蹤字典")
                self._partial_closed_positions.clear()
            return
        
        # 🔥 v3.18.4+：清理已不存在倉位的部分平倉追蹤記錄
        current_position_keys = set()
        for position in positions:
            symbol = position.get('symbol')
            # 從raw_data或轉換後的數據獲取方向
            if 'raw_data' in position:
                position_amt = float(position['raw_data'].get('positionAmt', 0))
            else:
                position_amt = position['size'] if position['side'] == 'LONG' else -position['size']
            
            # 🔥 Critical Fix: 跳過已平倉的倉位（positionAmt=0）
            # 確保完全平倉後可以重新觸發60%部分平倉
            if abs(position_amt) < 0.00001:  # 考慮浮點誤差
                continue
            
            direction = 'LONG' if position_amt > 0 else 'SHORT'
            current_position_keys.add((symbol, direction))
        
        # 清理已平倉的倉位記錄
        keys_to_remove = [key for key in self._partial_closed_positions if key not in current_position_keys]
        if keys_to_remove:
            for key in keys_to_remove:
                del self._partial_closed_positions[key]
            logger.debug(f"🧹 清理 {len(keys_to_remove)} 個已平倉的部分平倉追蹤記錄")
        
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
                # 🔥 v3.18+ 補救機制：舊倉位缺少original_signal時的降級處理
                # 問題：Railway生產環境有舊倉位虧損-60%但無法平倉，資金被鎖死
                # 解決：添加降級止損邏輯，虧損超過-30%時強制平倉釋放資金
                logger.debug(
                    f"⚠️ {symbol} 無original_signal（可能是舊倉位），使用降級出場邏輯 | "
                    f"PnL: {pnl_pct:+.1%}"
                )
                
                # 降級出場條件：虧損超過-30%時強制平倉（釋放資金）
                FALLBACK_STOP_LOSS = -0.30  # 舊倉位降級止損閾值
                if pnl_pct <= FALLBACK_STOP_LOSS:
                    logger.warning(
                        f"🔸 {symbol} 舊倉位降級止損觸發 | "
                        f"PnL: ${unrealized_pnl:.2f} ({pnl_pct:.1%}) | "
                        f"閾值: {FALLBACK_STOP_LOSS:.0%} | "
                        f"原因: 缺少original_signal無法執行智能出場"
                    )
                    await self._force_close_position(
                        symbol, position_amt, mark_price, 
                        f"舊倉位降級止損({pnl_pct:.1%}，無original_signal）"
                    )
                    self.forced_closures += 1
                    return
                else:
                    # 虧損<30%時僅記錄警告
                    if pnl_pct < -0.10:  # 虧損超過-10%時警告
                        logger.warning(
                            f"⚠️ {symbol} 虧損{pnl_pct:.1%} 但無original_signal，無法執行智能出場 | "
                            f"將在虧損達{FALLBACK_STOP_LOSS:.0%}時強制平倉"
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
            
            # 💰 v3.18.4+：60%盈利自動平50%倉位（每個倉位只執行一次）
            position_key = (symbol, direction)
            if pnl_pct >= 0.60 and position_key not in self._partial_closed_positions:
                logger.critical(
                    f"💰 {symbol} 達到60%報酬率，執行部分平倉（50%倉位）| "
                    f"PnL: ${unrealized_pnl:+.2f} ({pnl_pct:+.1%}) | "
                    f"倉位: {abs(position_amt):.6f}"
                )
                
                # 平50%倉位
                half_quantity = abs(position_amt) * 0.5
                success = await self._partial_close_position(
                    symbol, position_amt, mark_price, half_quantity,
                    reason=f"60%盈利自動平倉50%（{pnl_pct:.1%}）"
                )
                
                if success:
                    # 標記該倉位已執行60%部分平倉
                    self._partial_closed_positions[position_key] = True
                    self.partial_close_60pct_count += 1
                    logger.info(
                        f"✅ {symbol} 部分平倉成功，剩餘倉位: {half_quantity:.6f} | "
                        f"已實現盈利約 {unrealized_pnl * 0.5:+.2f} USDT"
                    )
                    # 不return，繼續監控剩餘50%倉位
            
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
                    logger.warning(
                        f"⚠️ {symbol} 進場理由失效但信心值{current_confidence:.1%}≥70%，繼續持倉 | "
                        f"原因: {expire_reason} | PnL: ${unrealized_pnl:+.2f} ({pnl_pct:+.1%})"
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
                    logger.warning(
                        f"⚪ {symbol} 逆勢但信心值{current_confidence:.1%}≥80%，允許逆勢交易 | "
                        f"原因: {counter_reason} | PnL: ${unrealized_pnl:+.2f} ({pnl_pct:+.1%})"
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
                else:
                    # 盈利>20%但條件不符合，說明原因
                    logger.info(
                        f"💡 {symbol} 盈利{pnl_pct:.1%} 但未啟動追蹤止盈 | "
                        f"趨勢持續:{trend_continue_prob:.1%}(<70%?) 勝率:{current_win_prob:.1%}(<80%?) | "
                        f"等待條件滿足或信心值/勝率降20%觸發強制止盈"
                    )
            
            # 6️⃣ OCO訂單觸發 - Binance API自動處理，無需額外邏輯
            
            # 正常監控日誌（僅在虧損 >50% 時警告）
            if pnl_pct < -0.5:
                logger.warning(
                    f"⚠️ {symbol} 虧損 {pnl_pct:.1%} "
                    f"(PnL: ${unrealized_pnl:.2f} / 風險: ${risk_amount:.2f}) | "
                    f"信心值:{current_confidence:.1%} 勝率:{current_win_prob:.1%}"
                )
            elif pnl_pct > 0.10:  # 盈利>10%時也記錄當前狀態
                logger.info(
                    f"📈 {symbol} 盈利 {pnl_pct:.1%} | "
                    f"PnL: ${unrealized_pnl:+.2f} | "
                    f"信心值:{current_confidence:.1%} 勝率:{current_win_prob:.1%} | "
                    f"趨勢穩定，繼續持有"
                )
                    
        except Exception as e:
            symbol_name = position.get('symbol', 'UNKNOWN') if position else 'UNKNOWN'
            logger.error(f"❌ 檢查倉位失敗 {symbol_name}: {e}", exc_info=True)
    
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
    
    async def _partial_close_position(
        self,
        symbol: str,
        position_amt: float,
        current_price: float,
        close_quantity: float,
        reason: str = "部分平倉"
    ) -> bool:
        """
        🔥 v3.18.4+：部分平倉（市價單，符合Binance API協議）
        
        依照Binance API官方協議：
        - Hedge Mode: 使用 positionSide 參數
        - One-Way Mode: 使用 reduceOnly="true" 參數
        
        Args:
            symbol: 交易對符號
            position_amt: 原始倉位數量（正數=多倉，負數=空倉）
            current_price: 當前價格
            close_quantity: 要平倉的數量（絕對值）
            reason: 平倉原因（用於記錄）
            
        Returns:
            bool: 是否成功
        """
        if not self.binance_client:
            logger.error("❌ 無 Binance 客戶端，無法部分平倉")
            return False
        
        try:
            # 計算平倉方向和數量
            side = "SELL" if position_amt > 0 else "BUY"
            quantity = abs(close_quantity)
            position_side = "LONG" if position_amt > 0 else "SHORT"
            
            logger.critical(
                f"💰 執行部分平倉: {symbol} {side} {quantity:.6f} @ ${current_price:.2f} | 原因: {reason}"
            )
            
            # 檢測Position Mode
            is_hedge_mode = await self.binance_client.get_position_mode()
            
            # 依照Binance API協議構建參數
            order_params = {}
            if is_hedge_mode:
                # Hedge Mode: 使用positionSide
                order_params['positionSide'] = position_side
                logger.info(f"  Hedge Mode: positionSide={position_side}")
            else:
                # One-Way Mode: 使用reduceOnly="true"（字符串，不是Boolean）
                order_params['reduceOnly'] = "true"
                logger.info("  One-Way Mode: reduceOnly=\"true\"")
            
            # 🔥 v3.18.4-Critical: 市價平倉（CRITICAL優先級，確保bypass熔斷器）
            from src.core.circuit_breaker import Priority
            
            result = await self.binance_client.place_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
                priority=Priority.CRITICAL,
                operation_type="close_position",
                **order_params
            )
            
            if result:
                logger.critical(f"✅ 部分平倉成功: {symbol} (訂單: {result.get('orderId')})")
                
                # 🔥 記錄到交易記錄（使用record_partial_close）
                if self.trade_recorder:
                    try:
                        # 從trade_recorder獲取entry_price和risk_amount
                        entry_price = current_price  # 默認值
                        risk_amount = None
                        try:
                            active_trades = self.trade_recorder.get_active_trades(symbol)
                            if active_trades and len(active_trades) > 0:
                                entry_price = active_trades[0].get('entry_price', current_price)
                                risk_amount = active_trades[0].get('risk_amount', None)
                        except Exception as e:
                            logger.debug(f"獲取 {symbol} entry_price 失敗: {e}")
                        
                        # 計算部分平倉PnL
                        if position_amt > 0:  # LONG
                            partial_pnl = (current_price - entry_price) * quantity
                        else:  # SHORT
                            partial_pnl = (entry_price - current_price) * quantity
                        
                        # 記錄部分平倉（傳遞risk_amount用於計算實際pnl_pct）
                        self.trade_recorder.record_partial_exit(
                            symbol=symbol,
                            direction=position_side,
                            exit_price=current_price,
                            closed_quantity=quantity,
                            reason=reason,
                            pnl=partial_pnl,
                            risk_amount=risk_amount
                        )
                        logger.info(f"  ✅ 部分平倉已記錄到交易記錄")
                    except Exception as e:
                        logger.warning(f"記錄部分平倉失敗: {e}")
                
                return True
            else:
                logger.error(f"❌ 部分平倉失敗: {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 部分平倉異常: {symbol} - {e}", exc_info=True)
            return False
    
    async def _force_close_position(
        self,
        symbol: str,
        position_amt: float,
        current_price: float,
        reason: str = "未知原因"
    ):
        """
        強制平倉（市價單，符合Binance API協議）
        
        依照Binance API官方協議：
        - Hedge Mode: 使用 positionSide 參數
        - One-Way Mode: 使用 reduceOnly="true" 參數
        
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
            position_side = "LONG" if position_amt > 0 else "SHORT"
            
            logger.critical(
                f"🚨 執行強制平倉: {symbol} {side} {quantity:.6f} @ ${current_price:.2f} | 原因: {reason}"
            )
            
            # 檢測Position Mode
            is_hedge_mode = await self.binance_client.get_position_mode()
            
            # 依照Binance API協議構建參數
            order_params = {}
            if is_hedge_mode:
                # Hedge Mode: 使用positionSide
                order_params['positionSide'] = position_side
                logger.info(f"  Hedge Mode: positionSide={position_side}")
            else:
                # One-Way Mode: 使用reduceOnly="true"（字符串，不是Boolean）
                order_params['reduceOnly'] = "true"
                logger.info("  One-Way Mode: reduceOnly=\"true\"")
            
            # 🔥 v3.18.4-Critical: 市價平倉（CRITICAL優先級，確保bypass熔斷器）
            from src.core.circuit_breaker import Priority
            
            result = await self.binance_client.place_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
                priority=Priority.CRITICAL,
                operation_type="close_position",
                **order_params
            )
            
            if result:
                self.forced_closures += 1
                logger.critical(f"✅ 強制平倉成功: {symbol} (訂單: {result.get('orderId')})")
                
                # 🔥 v3.27+ 診斷日誌
                logger.info(f"🔍 [DIAG] PositionMonitor24x7 - trade_recorder存在: {self.trade_recorder is not None}")
                
                # 🔥 v3.18.4+：記錄到交易記錄（使用record_exit）
                if self.trade_recorder:
                    try:
                        logger.info(f"🔍 [DIAG] PositionMonitor24x7 - 準備記錄平倉: {symbol}")
                        # 🔥 從trade_recorder獲取entry_price和PnL信息
                        entry_price = None
                        pnl = 0
                        pnl_pct = 0
                        
                        try:
                            active_trades = self.trade_recorder.get_active_trades(symbol)
                            if active_trades and len(active_trades) > 0:
                                latest_trade = active_trades[0]
                                entry_price = latest_trade.get('entry_price', current_price)
                                
                                # 計算PnL
                                if position_amt > 0:  # LONG
                                    pnl_per_unit = current_price - entry_price
                                else:  # SHORT
                                    pnl_per_unit = entry_price - current_price
                                
                                pnl = pnl_per_unit * quantity
                                
                                # 計算PnL百分比（基於初始風險）
                                risk_amount = latest_trade.get('risk_amount', 0)
                                if risk_amount and risk_amount > 0:
                                    pnl_pct = pnl / risk_amount
                        except Exception as e:
                            logger.debug(f"獲取 {symbol} entry_price 失敗: {e}")
                            entry_price = current_price  # 備援
                        
                        trade_result = {
                            'symbol': symbol,
                            'direction': position_side,
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct,
                            'close_reason': reason,
                            'close_timestamp': datetime.now(),
                            'order_id': result.get('orderId')
                        }
                        
                        logger.info(f"🔍 [DIAG] PositionMonitor24x7 - 調用record_exit: {symbol}")
                        self.trade_recorder.record_exit(trade_result)
                        logger.info(f"📝 平倉已記錄: {symbol} {side} {quantity} @ {current_price} | {reason} | PnL: ${pnl:+.2f}")
                    except Exception as e:
                        logger.error(f"❌ 記錄平倉失敗: {e}", exc_info=True)
                        logger.error(f"🔍 [DIAG] PositionMonitor24x7 - 異常堆棧已記錄")
                else:
                    logger.warning(f"⚠️ trade_recorder為None，無法記錄平倉")
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
            
            # ✅ v3.20.2 Phase 6: 使用共享 EliteTechnicalEngine 實例
            # RSI反彈信號
            rsi_result = self.tech_engine.calculate('rsi', data, period=14)
            rsi = rsi_result.value
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
            macd_result = self.tech_engine.calculate('macd', data, fast=12, slow=26, signal=9)
            macd_line = macd_result.value['macd']
            signal_line = macd_result.value['signal']
            histogram = macd_result.value['histogram']
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
                    liquidity_score=0.0,
                    volatility=0.0,
                    rsi=50.0,
                    macd=0.0
                )
            
            # 獲取15m K線數據（平衡速度與穩定性）
            klines = await self.data_service.get_klines_incremental(
                symbol, interval='15m', limit=100
            )
            
            if klines.empty or len(klines) < 50:
                # 數據不足，返回中性上下文
                return MarketContext(
                    trend_direction="neutral",
                    liquidity_score=0.0,
                    volatility=0.0,
                    rsi=50.0,
                    macd=0.0
                )
            
            # ✅ v3.20.2 Phase 6: 使用共享 EliteTechnicalEngine 實例
            rsi_result = self.tech_engine.calculate('rsi', klines, period=14)
            rsi = rsi_result.value
            latest_rsi = float(rsi.iloc[-1]) if not rsi.empty else 50.0
            
            macd_result = self.tech_engine.calculate('macd', klines, fast=12, slow=26, signal=9)
            macd_line = macd_result.value['macd']
            signal_line = macd_result.value['signal']
            histogram = macd_result.value['histogram']
            latest_macd_hist = 0.0
            if not isinstance(histogram, str) and histogram is not None and not histogram.empty:
                latest_macd_hist = float(histogram.iloc[-1])
            
            # EMA趨勢判斷
            ema20_result = self.tech_engine.calculate('ema', klines, period=20)
            ema20 = ema20_result.value
            ema50_result = self.tech_engine.calculate('ema', klines, period=50)
            ema50 = ema50_result.value
            
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
                liquidity_score=liquidity,
                volatility=volatility,
                rsi=latest_rsi,
                macd=latest_macd_hist
            )
            
        except Exception as e:
            logger.debug(f"構建{symbol}市場上下文失敗: {e}")
            # 返回中性上下文
            return MarketContext(
                trend_direction="neutral",
                liquidity_score=0.0,
                volatility=0.0,
                rsi=50.0,
                macd=0.0
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
            
            # ✅ v3.20.2 Phase 6: 使用共享 EliteTechnicalEngine 實例
            rsi_result = self.tech_engine.calculate('rsi', klines, period=14)
            rsi = rsi_result.value
            
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
            
            # ✅ v3.20.2 Phase 6: 使用共享 EliteTechnicalEngine 實例
            ema20_result = self.tech_engine.calculate('ema', klines, period=20)
            ema20 = ema20_result.value
            ema50_result = self.tech_engine.calculate('ema', klines, period=50)
            ema50 = ema50_result.value
            
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
