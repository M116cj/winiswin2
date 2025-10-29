"""
v3.17+ 24/7 倉位監控器
每 2 秒檢查所有倉位，-99% 風險立即平倉
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

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
        data_service=None
    ):
        """
        初始化監控器
        
        Args:
            config_profile: ConfigProfile 實例
            binance_client: BinanceClient 實例（可選）
            trade_recorder: TradeRecorder 實例（可選）
            data_service: DataService 實例（可選，用於獲取市場數據）
        """
        self.config = config_profile
        self.binance_client = binance_client
        self.trade_recorder = trade_recorder
        self.data_service = data_service
        
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
        self.entry_reason_expired_closures = 0  # 🔥 新增：進場理由失效平倉數
        self.counter_trend_closures = 0  # 🔥 新增：逆勢平倉數
        self.last_check_time: Optional[datetime] = None
        
        logger.info("=" * 60)
        logger.info("✅ 24/7 倉位監控器初始化完成（v3.17.10+）")
        logger.info(f"   ⏱️  檢查間隔: {self.monitor_interval} 秒")
        logger.info(f"   🚨 風險熔斷閾值: {self.risk_threshold:.1%}")
        logger.info(f"   🔥 進場理由失效自動平倉: 啟用")
        logger.info(f"   🔥 逆勢無反彈自動平倉: 啟用")
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
        🔥 v3.17.10+：檢查單個倉位（新增進場理由失效和逆勢平倉邏輯）
        
        平倉條件（按優先級）：
        1. PnL ≤ -99% → 100%虧損熔斷
        2. 進場理由失效 → 立即平倉
        3. 逆勢 + 無反彈信號 → 立即平倉
        
        Args:
            position: 倉位數據（來自 Binance API）
        """
        try:
            symbol = position.get('symbol')
            if not symbol:
                logger.warning("⚠️ 持倉數據缺少 symbol，跳過")
                return
                
            position_amt = float(position.get('positionAmt', 0))
            entry_price = float(position.get('entryPrice', 0))
            # markPrice 可能缺失，使用 entryPrice 作為備選
            mark_price = float(position.get('markPrice') or position.get('entryPrice', 0))
            unrealized_pnl = float(position.get('unrealizedProfit', position.get('unRealizedProfit', 0)))
            direction = "LONG" if position_amt > 0 else "SHORT"
            
            if position_amt == 0:
                return
            
            # 獲取原始風險金額（從交易記錄）
            risk_amount = await self._get_risk_amount(symbol)
            
            if risk_amount is None or risk_amount <= 0:
                logger.warning(f"⚠️ {symbol} 無法獲取風險金額，跳過檢查")
                return
            
            # 計算 PnL 百分比（相對於初始風險）
            pnl_pct = unrealized_pnl / risk_amount if risk_amount > 0 else 0
            
            # 🔥 檢查1：100% 虧損熔斷（最高優先級）
            if pnl_pct <= -self.risk_threshold:
                logger.critical(
                    f"🚨🚨🚨 {symbol} 觸發 100% 虧損熔斷！"
                    f"PnL: ${unrealized_pnl:.2f} ({pnl_pct:.1%}) "
                    f"風險: ${risk_amount:.2f}"
                )
                
                # 立即市價平倉（優先級 0）
                await self._force_close_position(
                    symbol,
                    position_amt,
                    mark_price,
                    reason="100% 虧損熔斷"
                )
                return
            
            # 🔥 檢查2：進場理由失效（v3.17.10+）
            entry_expired, expire_reason = await self._is_entry_reason_expired(
                symbol,
                entry_price,
                mark_price,
                direction
            )
            
            if entry_expired:
                logger.warning(
                    f"⚠️ {symbol} 進場理由失效: {expire_reason} | "
                    f"PnL: ${unrealized_pnl:+.2f} ({pnl_pct:+.1%}) → 執行平倉"
                )
                
                await self._force_close_position(
                    symbol,
                    position_amt,
                    mark_price,
                    reason=f"進場理由失效: {expire_reason}"
                )
                self.entry_reason_expired_closures += 1
                return
            
            # 🔥 檢查3：逆勢 + 無反彈信號（v3.17.10+）
            is_counter, counter_reason = await self._is_counter_trend(
                symbol,
                entry_price,
                mark_price,
                direction
            )
            
            if is_counter:
                # 檢查是否有反彈信號
                has_rebound = await self._has_rebound_signal(symbol, direction)
                
                if not has_rebound:
                    logger.warning(
                        f"⚠️ {symbol} 逆勢且無反彈信號: {counter_reason} | "
                        f"PnL: ${unrealized_pnl:+.2f} ({pnl_pct:+.1%}) → 執行平倉"
                    )
                    
                    await self._force_close_position(
                        symbol,
                        position_amt,
                        mark_price,
                        reason=f"逆勢無反彈: {counter_reason}"
                    )
                    self.counter_trend_closures += 1
                    return
                else:
                    # 有反彈信號，暫時保留
                    logger.info(
                        f"📊 {symbol} 逆勢但有反彈信號，繼續持有 | "
                        f"PnL: ${unrealized_pnl:+.2f} ({pnl_pct:+.1%})"
                    )
            
            # 正常監控日誌（僅在虧損 >50% 時警告）
            if pnl_pct < -0.5:
                logger.warning(
                    f"⚠️ {symbol} 虧損 {pnl_pct:.1%} "
                    f"(PnL: ${unrealized_pnl:.2f} / 風險: ${risk_amount:.2f})"
                )
                    
        except Exception as e:
            logger.error(f"❌ 檢查倉位失敗: {e}")
    
    async def _get_risk_amount(self, symbol: str) -> Optional[float]:
        """
        獲取倉位的初始風險金額
        
        Args:
            symbol: 交易對符號
            
        Returns:
            風險金額（USDT），或 None
        """
        if not self.trade_recorder:
            return None
        
        try:
            # 從交易記錄獲取最近的開倉記錄
            trades = self.trade_recorder.get_active_trades(symbol)
            if trades:
                return trades[0].get('risk_amount', 0)
        except Exception as e:
            logger.debug(f"獲取 {symbol} 風險金額失敗: {e}")
        
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
