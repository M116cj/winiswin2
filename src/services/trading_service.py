"""
交易執行服務
職責：開倉、平倉、止損止盈設置、訂單管理
"""

from typing import Dict, Optional, List, Tuple
import logging
from datetime import datetime
import asyncio

from src.clients.binance_client import BinanceClient
from src.managers.risk_manager import RiskManager
from src.config import Config

logger = logging.getLogger(__name__)


class TradingService:
    """交易執行服務"""
    
    def __init__(
        self,
        binance_client: BinanceClient,
        risk_manager: RiskManager,
        trade_recorder=None
    ):
        """
        初始化交易服務
        
        Args:
            binance_client: Binance 客戶端
            risk_manager: 風險管理器
            trade_recorder: 交易記錄器（可選）
        """
        self.client = binance_client
        self.risk_manager = risk_manager
        self.trade_recorder = trade_recorder
        self.config = Config
        self.active_orders: Dict[str, dict] = {}
        self.symbol_filters: Dict[str, dict] = {}  # 交易對過濾器緩存
        self._price_cache: Dict[str, Tuple[float, float]] = {}  # (價格, 時間戳) 緩存
        self._filters_loaded = False  # 過濾器是否已預加載
    
    async def preload_symbol_filters(self, symbols: Optional[List[str]] = None):
        """
        預加載交易對過濾器（v3.5.0優化）
        
        Args:
            symbols: 交易對列表（None表示加載所有）
        """
        if self._filters_loaded and not symbols:
            return  # 已加載且不需要特定符號
        
        try:
            logger.info(f"⏳ 預加載交易對過濾器...")
            exchange_info = await self.client.get_exchange_info()
            
            loaded_count = 0
            for s in exchange_info.get('symbols', []):
                symbol = s['symbol']
                
                # 如果指定了symbols，只加載這些
                if symbols and symbol not in symbols:
                    continue
                
                # 提取過濾器
                filters_data = {}
                for f in s.get('filters', []):
                    if f['filterType'] == 'LOT_SIZE':
                        filters_data['stepSize'] = float(f['stepSize'])
                        filters_data['minQty'] = float(f['minQty'])
                        filters_data['maxQty'] = float(f['maxQty'])
                    elif f['filterType'] == 'PRICE_FILTER':
                        filters_data['tickSize'] = float(f['tickSize'])
                        filters_data['minPrice'] = float(f['minPrice'])
                        filters_data['maxPrice'] = float(f['maxPrice'])
                
                if filters_data:
                    self.symbol_filters[symbol] = filters_data
                    loaded_count += 1
            
            self._filters_loaded = True
            logger.info(f"✅ 已預加載 {loaded_count} 個交易對過濾器")
            
        except Exception as e:
            logger.error(f"預加載過濾器失敗: {e}")
    
    async def execute_signal(
        self,
        signal: Dict,
        account_balance: float,
        current_leverage: int
    ) -> Optional[Dict]:
        """
        執行交易信號（v3.9.2.2增強：熔斷器感知，防止無保護倉位）
        
        Args:
            signal: 交易信號
            account_balance: 賬戶餘額
            current_leverage: 當前槓桿
        
        Returns:
            Optional[Dict]: 交易結果
        """
        try:
            # 🛡️ v3.9.2.2: 熔斷器狀態檢查（最高優先級）
            can_proceed, block_reason = self.client.circuit_breaker.can_proceed()
            if not can_proceed:
                logger.warning(f"⚠️  {block_reason}，推遲交易信號")
                return None
            
            # 🛡️ v3.9.2: 賬戶保護檢查
            if not self.risk_manager.check_account_protection(account_balance):
                logger.error("🔴 賬戶保護觸發，拒絕交易")
                return None
            
            symbol = signal['symbol']
            direction = signal['direction']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            take_profit = signal['take_profit']
            confidence = signal['confidence']
            
            # 🛡️ v3.9.2: 檢查槓桿為0（期望值為負/回撤過大）
            if current_leverage == 0:
                logger.warning(f"⚠️  槓桿為0，拒絕交易 {symbol}")
                return None
            
            # 🛡️ v3.9.2: 檢查信號品質（謹慎模式/連續虧損保護）
            # 獲取歷史勝率（如果可用）
            win_rate = None
            if hasattr(self.risk_manager, 'trade_history') and len(self.risk_manager.trade_history) >= 10:
                stats = self.risk_manager.get_statistics()
                win_rate = stats.get('win_rate')
            
            can_trade, reason = self.risk_manager.can_trade_signal(confidence, win_rate)
            if not can_trade:
                logger.warning(f"⚠️  信號品質不符合：{reason}")
                logger.warning(f"   {symbol} 信心度 {confidence:.1%}, 勝率 {win_rate:.1% if win_rate else 'N/A'}")
                return None
            
            position_info = self.risk_manager.calculate_position_size(
                account_balance=account_balance,
                confidence_score=confidence,
                current_leverage=current_leverage
            )
            
            quantity = position_info['position_value'] / entry_price
            
            quantity = await self._round_quantity(symbol, quantity)
            
            # Binance最小訂單價值檢查（不同交易對有不同要求：5-20 USDT）
            # 使用配置值作為安全值，確保所有交易對都能通過
            MIN_NOTIONAL = self.config.MIN_NOTIONAL_VALUE
            notional_value = quantity * entry_price
            if notional_value < MIN_NOTIONAL:
                logger.info(
                    f"💰 訂單價值不足{MIN_NOTIONAL} USDT，自動補足 {symbol}: "
                    f"{notional_value:.2f} USDT → {MIN_NOTIONAL} USDT"
                )
                # 根據最低要求重新計算數量，並向上舍入確保滿足最小值
                quantity = MIN_NOTIONAL / entry_price
                quantity = await self._round_quantity(symbol, quantity, round_up=True)
                notional_value = quantity * entry_price
                
                # 二次檢查：如果舍入後仍然不足，增加一個最小單位
                if notional_value < MIN_NOTIONAL:
                    filters = self.symbol_filters.get(symbol, {})
                    step_size = filters.get('stepSize', 0.001)
                    quantity += step_size
                    notional_value = quantity * entry_price
                    logger.info(f"📈 增加最小單位後: 數量={quantity}, 訂單價值={notional_value:.2f} USDT")
            
            logger.info(
                f"準備開倉: {symbol} {direction} "
                f"數量: {quantity} 槓桿: {current_leverage}x "
                f"信心度: {confidence:.2%} "
                f"訂單價值: {notional_value:.2f} USDT"
            )
            
            if not self.config.TRADING_ENABLED:
                logger.warning("🎮 交易功能未啟用，創建模擬交易（用於學習模式）")
                simulated_trade = self._create_simulated_trade(
                    signal, position_info, quantity
                )
                
                # 添加到active_orders以便追踪
                self.active_orders[symbol] = simulated_trade
                
                # ✨ 記錄模擬開倉到TradeRecorder（修復學習模式0/30問題）
                if self.trade_recorder:
                    try:
                        self.trade_recorder.record_entry(signal, simulated_trade)
                        logger.info(f"📝 已記錄模擬開倉: {symbol} (學習模式)")
                    except Exception as e:
                        logger.error(f"記錄模擬開倉失敗: {e}")
                
                return simulated_trade
            
            # 智能下單：根據配置自動選擇訂單類型
            order = await self._place_smart_order(
                symbol=symbol,
                side="BUY" if direction == "LONG" else "SELL",
                quantity=quantity,
                expected_price=entry_price,
                direction=direction
            )
            
            if not order:
                logger.error(f"開倉失敗: {symbol}")
                return None
            
            # ✨ 重要：使用實際成交數量（處理部分成交情況）
            actual_quantity = float(order.get('executedQty', quantity))
            if abs(actual_quantity - quantity) > 0.001:  # 數量不同
                logger.warning(
                    f"⚠️  實際成交數量與計劃不同: {symbol} "
                    f"計劃={quantity} 實際={actual_quantity}"
                )
                quantity = actual_quantity
            
            # 🛡️ v3.9.2.2: 訂單間延遲，避免觸發熔斷器
            logger.debug(f"⏱️  等待{self.config.ORDER_INTER_DELAY}秒後設置止損止盈...")
            await asyncio.sleep(self.config.ORDER_INTER_DELAY)
            
            # ✨ 強化：同步設置止損止盈（建倉後延遲設置，5次重試+訂單驗證）
            try:
                sl_order_id, tp_order_id = await self._set_stop_loss_take_profit_parallel(
                    symbol, direction, quantity, stop_loss, take_profit, max_retries=5
                )
                
                # ✅ 驗證止損止盈訂單確實存在
                logger.info(f"🔍 驗證止損止盈訂單...")
                sl_verified = await self._verify_order_exists(symbol, sl_order_id)
                tp_verified = await self._verify_order_exists(symbol, tp_order_id)
                
                if not sl_verified or not tp_verified:
                    raise Exception(
                        f"止損止盈訂單驗證失敗: "
                        f"SL={'存在' if sl_verified else '不存在'}, "
                        f"TP={'存在' if tp_verified else '不存在'}"
                    )
                
                logger.info(f"✅ 止損止盈訂單已驗證: {symbol} (SL:{sl_order_id}, TP:{tp_order_id})")
                
            except Exception as e:
                logger.error(f"❌ 止損止盈設置/驗證失敗: {e}")
                logger.critical(f"🚨 建倉成功但無保護，必須立即平倉！{symbol}")
                
                # 🔴 v3.9.2.2：智能平倉（熔斷器感知重試）
                try:
                    close_success = await self._emergency_close_position(
                        symbol, direction, quantity
                    )
                    if close_success:
                        logger.warning(f"✅ 已緊急平倉無保護持倉: {symbol}")
                    else:
                        logger.critical(f"🚨🚨 致命錯誤：{symbol} 平倉失敗！請立即手動處理！")
                        logger.critical(f"⚠️  無保護倉位詳情: {symbol} {direction} {quantity}")
                except Exception as close_error:
                    logger.critical(f"🚨🚨 致命錯誤：{symbol} 平倉異常 {close_error}！請立即手動處理！")
                    logger.critical(f"⚠️  無保護倉位詳情: {symbol} {direction} {quantity}")
                
                return None
            
            trade_result = {
                'symbol': symbol,
                'direction': direction,
                'entry_price': float(order.get('avgPrice', entry_price)),
                'quantity': quantity,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'leverage': current_leverage,
                'confidence': confidence,
                'position_value': position_info['position_value'],
                'margin': position_info['position_margin'],
                'timestamp': datetime.now(),
                'order_id': order.get('orderId'),
                'status': 'open'
            }
            
            self.active_orders[symbol] = trade_result
            
            # 記錄開倉到TradeRecorder（用於學習模式）
            if self.trade_recorder:
                try:
                    self.trade_recorder.record_entry(signal, trade_result)
                    logger.debug(f"📝 已記錄開倉到TradeRecorder: {symbol}")
                except Exception as e:
                    logger.error(f"記錄開倉失敗: {e}")
            
            logger.info(f"✅ 開倉成功: {symbol} {direction} @ {trade_result['entry_price']}")
            
            return trade_result
            
        except Exception as e:
            logger.error(f"執行交易信號失敗: {e}")
            return None
    
    async def close_position(
        self,
        symbol: str,
        reason: str = "manual"
    ) -> Optional[Dict]:
        """
        平倉
        
        Args:
            symbol: 交易對
            reason: 平倉原因
        
        Returns:
            Optional[Dict]: 平倉結果
        """
        try:
            if symbol not in self.active_orders:
                logger.warning(f"未找到活躍訂單: {symbol}")
                return None
            
            trade = self.active_orders[symbol]
            
            side = "SELL" if trade['direction'] == "LONG" else "BUY"
            direction = trade['direction']
            
            # 模擬交易模式：使用市場價格模擬平倉
            if trade.get('simulated', False) or not self.config.TRADING_ENABLED:
                logger.info(f"🎮 模擬平倉: {symbol} (原因: {reason})")
                # 獲取當前市場價格
                try:
                    ticker = await self.client.get_ticker_price(symbol)
                    exit_price = float(ticker['price'])
                except Exception as e:
                    logger.error(f"獲取市場價格失敗: {e}，使用入場價")
                    exit_price = trade['entry_price']
            else:
                # 真實交易：執行市價平倉
                order = await self._place_market_order(
                    symbol=symbol,
                    side=side,
                    quantity=trade['quantity'],
                    direction=direction
                )
                
                if not order:
                    logger.error(f"平倉失敗: {symbol}")
                    return None
                
                exit_price = float(order.get('avgPrice', 0))
            
            if trade['direction'] == "LONG":
                pnl = (exit_price - trade['entry_price']) * trade['quantity']
            else:
                pnl = (trade['entry_price'] - exit_price) * trade['quantity']
            
            # 計算收益率（相對於保證金）
            # ⚠️ 防止除零錯誤
            if trade['margin'] <= 0:
                logger.error(f"異常保證金: {trade['margin']}, 設置為默認值1.0")
                trade['margin'] = 1.0
            
            pnl_pct = pnl / trade['margin']
            
            # ⚠️ 限制收益率最低為-100%（不能虧損超過本金）
            # 修復：避免出現-225%等異常收益率
            if pnl_pct < -1.0:
                logger.warning(
                    f"⚠️ 檢測到異常收益率 {pnl_pct:.2%}，限制為-100%。"
                    f"PnL: {pnl:.2f}, Margin: {trade['margin']:.2f}"
                )
                pnl_pct = -1.0
            
            close_result = {
                **trade,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'close_reason': reason,
                'close_timestamp': datetime.now(),
                'status': 'closed'
            }
            
            self.risk_manager.update_trade_result(close_result)
            
            # 記錄平倉到TradeRecorder
            if self.trade_recorder:
                try:
                    self.trade_recorder.record_exit(close_result)
                    logger.debug(f"📝 已記錄平倉到TradeRecorder: {symbol}")
                except Exception as e:
                    logger.error(f"記錄平倉失敗: {e}")
            
            # 清理止損止盈訂單（避免僵尸訂單）
            try:
                cancelled_count = await self._cancel_all_open_orders(symbol)
                if cancelled_count > 0:
                    logger.info(f"🧹 已清理 {cancelled_count} 個止損止盈訂單: {symbol}")
            except Exception as e:
                logger.warning(f"清理訂單失敗: {e}")
            
            del self.active_orders[symbol]
            
            logger.info(
                f"✅ 平倉成功: {symbol} "
                f"PnL: {pnl:+.2f} ({pnl_pct:+.2%}) "
                f"原因: {reason}"
            )
            
            return close_result
            
        except Exception as e:
            logger.error(f"平倉失敗: {e}")
            return None
    
    async def _get_current_price_cached(self, symbol: str, cache_ttl: float = 1.0) -> float:
        """
        獲取當前價格（帶緩存優化）
        
        Args:
            symbol: 交易對
            cache_ttl: 緩存有效期（秒）
        
        Returns:
            float: 當前價格
        """
        import time
        now = time.time()
        
        # 檢查緩存
        if symbol in self._price_cache:
            price, timestamp = self._price_cache[symbol]
            if now - timestamp < cache_ttl:
                return price
        
        # 獲取新價格
        ticker = await self.client.get_ticker_price(symbol)
        current_price = float(ticker['price'])
        
        # 更新緩存
        self._price_cache[symbol] = (current_price, now)
        
        return current_price
    
    async def _place_smart_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        expected_price: float,
        direction: Optional[str] = None
    ) -> Optional[Dict]:
        """
        智能下單：自動選擇市價單或限價單（v3.5.0優化）
        
        策略：
        1. 獲取當前市價（帶緩存）
        2. 計算滑點
        3. 如果滑點 < MAX_SLIPPAGE_PCT: 使用市價單
        4. 如果滑點 >= MAX_SLIPPAGE_PCT: 使用限價單（超時後轉市價單）
        
        Args:
            symbol: 交易對
            side: BUY / SELL
            quantity: 數量
            expected_price: 預期價格
            direction: 方向 (LONG/SHORT) - 用於雙向持倉模式
        
        Returns:
            訂單信息
        """
        try:
            # ✨ 優化：使用帶緩存的價格獲取（減少API調用）
            current_price = await self._get_current_price_cached(symbol, cache_ttl=0.5)
            
            # 計算滑點
            slippage_pct = abs(current_price - expected_price) / expected_price
            
            logger.info(
                f"價格檢查: {symbol} 預期={expected_price:.6f} "
                f"當前={current_price:.6f} 滑點={slippage_pct:.2%}"
            )
            
            # 如果滑點可接受，使用市價單（最快）
            if slippage_pct < self.config.MAX_SLIPPAGE_PCT or not self.config.AUTO_ORDER_TYPE:
                logger.info(f"✅ 滑點可接受，使用市價單: {symbol}")
                return await self._place_market_order(symbol, side, quantity, direction)
            
            # 滑點過大，使用限價單保護
            if self.config.USE_LIMIT_ORDERS:
                logger.warning(
                    f"⚠️  滑點過大 ({slippage_pct:.2%}), 使用限價單保護: {symbol}"
                )
                return await self._place_limit_order_with_fallback(
                    symbol, side, quantity, expected_price, direction  # 傳入預期價格和方向
                )
            else:
                # 配置禁用限價單，直接拒絕
                logger.error(
                    f"❌ 滑點過大且禁用限價單，拒絕下單: {symbol} "
                    f"(滑點 {slippage_pct:.2%} > {self.config.MAX_SLIPPAGE_PCT:.2%})"
                )
                return None
                
        except Exception as e:
            logger.error(f"智能下單失敗 {symbol}: {e}")
            return None
    
    async def _emergency_close_position(
        self,
        symbol: str,
        direction: str,
        quantity: float
    ) -> bool:
        """
        緊急平倉（v3.9.2.2新增：熔斷器感知智能重試）
        
        當止損止盈設置失敗時，智能地嘗試平倉以保護賬戶
        
        Args:
            symbol: 交易對
            direction: 方向
            quantity: 數量
        
        Returns:
            bool: 是否成功平倉
        """
        from src.clients.binance_errors import BinanceRequestError
        
        max_attempts = self.config.ORDER_RETRY_MAX_ATTEMPTS
        base_delay = self.config.ORDER_RETRY_BASE_DELAY
        max_delay = self.config.ORDER_RETRY_MAX_DELAY
        
        for attempt in range(max_attempts):
            try:
                # 檢查熔斷器狀態
                can_proceed, block_reason = self.client.circuit_breaker.can_proceed()
                
                if not can_proceed:
                    retry_after = self.client.circuit_breaker.get_retry_after()
                    wait_time = min(retry_after + 1, max_delay)  # +1秒安全邊際
                    logger.warning(
                        f"⏱️  熔斷器開啟，等待{wait_time:.0f}秒後重試平倉 "
                        f"(嘗試 {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                # 嘗試平倉
                logger.info(f"🔄 嘗試緊急平倉 {symbol} (嘗試 {attempt + 1}/{max_attempts})")
                
                close_order = await self._place_market_order(
                    symbol=symbol,
                    side="SELL" if direction == "LONG" else "BUY",
                    quantity=quantity,
                    direction=direction
                )
                
                if close_order:
                    logger.info(f"✅ 緊急平倉成功: {symbol}")
                    return True
                
                # 訂單失敗但沒有異常，等待後重試
                wait_time = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(f"⏱️  平倉訂單失敗，等待{wait_time:.1f}秒後重試...")
                await asyncio.sleep(wait_time)
                
            except BinanceRequestError as e:
                # 結構化錯誤，包含重試信息
                if e.retry_after_seconds:
                    wait_time = min(e.retry_after_seconds + 1, max_delay)
                    logger.warning(
                        f"⏱️  API建議等待{wait_time:.0f}秒後重試平倉 "
                        f"(嘗試 {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # 指數退避
                    wait_time = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        f"⏱️  平倉失敗({e.message})，等待{wait_time:.1f}秒後重試..."
                    )
                    await asyncio.sleep(wait_time)
                
            except Exception as e:
                # 其他錯誤，指數退避
                wait_time = min(base_delay * (2 ** attempt), max_delay)
                logger.error(
                    f"❌ 平倉異常: {e}, 等待{wait_time:.1f}秒後重試 "
                    f"(嘗試 {attempt + 1}/{max_attempts})"
                )
                await asyncio.sleep(wait_time)
        
        # 所有嘗試都失敗
        logger.critical(f"🚨 緊急平倉失敗（已嘗試{max_attempts}次）: {symbol}")
        return False
    
    async def _place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        direction: Optional[str] = None
    ) -> Optional[Dict]:
        """下市價單"""
        try:
            # 添加 positionSide 參數支持雙向持倉模式
            position_side = None
            if direction:
                position_side = "LONG" if direction == "LONG" else "SHORT"
            
            params = {}
            if position_side:
                params['positionSide'] = position_side
            
            order = await self.client.place_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
                **params
            )
            logger.info(f"✅ 市價單成交: {symbol} {side} {quantity}")
            return order
        except Exception as e:
            logger.error(f"市價單失敗 {symbol} {side} {quantity}: {e}")
            return None
    
    async def _place_limit_order_with_fallback(
        self,
        symbol: str,
        side: str,
        quantity: float,
        expected_price: float,
        direction: Optional[str] = None
    ) -> Optional[Dict]:
        """
        下限價單，超時後降級為市價單
        
        Args:
            symbol: 交易對
            side: BUY / SELL  
            quantity: 數量
            expected_price: 預期價格（來自信號）
            direction: 方向 (LONG/SHORT) - 用於雙向持倉模式
        
        Returns:
            訂單信息
        """
        try:
            # 🔧 修復：基於預期價格計算限價單，而非當前市價
            # 這樣才能真正限制滑點在MAX_SLIPPAGE_PCT範圍內
            if side == "BUY":
                # 買入：最高不超過預期價 + MAX_SLIPPAGE
                # 這確保成交價不會比信號價格高出0.2%以上
                limit_price = expected_price * (1 + self.config.MAX_SLIPPAGE_PCT)
            else:
                # 賣出：最低不低於預期價 - MAX_SLIPPAGE
                # 這確保成交價不會比信號價格低出0.2%以上
                limit_price = expected_price * (1 - self.config.MAX_SLIPPAGE_PCT)
            
            # 根據交易所規則四捨五入價格
            limit_price = await self._round_price(symbol, limit_price)
            
            logger.info(
                f"📝 下限價單: {symbol} {side} @ {limit_price} "
                f"(保護範圍 ±{self.config.MAX_SLIPPAGE_PCT:.2%})"
            )
            
            # 添加 positionSide 參數支持雙向持倉模式
            position_side = None
            if direction:
                position_side = "LONG" if direction == "LONG" else "SHORT"
            
            params = {
                "timeInForce": "GTC"  # Good Till Cancel
            }
            if position_side:
                params['positionSide'] = position_side
            
            # 下限價單
            order = await self.client.place_order(
                symbol=symbol,
                side=side,
                order_type="LIMIT",
                quantity=quantity,
                price=limit_price,
                **params
            )
            
            order_id = order.get('orderId')
            
            if not order_id:
                logger.error(f"限價單未返回訂單ID，拒絕下單: {symbol}")
                # 不降級為不受限制的市價單，保護滑點
                return None
            
            # ✨ 優化：使用快速訂單確認（0.5秒間隔，支持部分成交檢測）
            timeout = self.config.ORDER_TIMEOUT_SECONDS
            filled, order_status = await self._confirm_order_filled(
                symbol=symbol,
                order_id=str(order_id),
                timeout=timeout,
                check_interval=0.5  # 4倍提升：2秒 → 0.5秒
            )
            
            if filled and order_status:
                logger.info(f"✅ 限價單成交: {symbol}")
                return order_status
            
            # 未完全成交：檢查部分成交情況
            executed_qty = 0.0
            if order_status:
                executed_qty = float(order_status.get('executedQty', 0))
                status = order_status.get('status', '')
                
                if executed_qty > 0:
                    logger.info(
                        f"📊 限價單部分成交: {symbol} "
                        f"已成交={executed_qty}/{quantity} ({executed_qty/quantity:.1%})"
                    )
            
            # 超時：重新檢查滑點，決定是否降級為市價單
            logger.warning(
                f"⏰ 限價單超時 ({timeout}秒): {symbol}"
            )
            
            # 取消未成交部分
            try:
                await self.client.cancel_order(symbol, int(order_id))
            except:
                pass  # 忽略取消錯誤
            
            # 重新檢查當前滑點
            ticker = await self.client.get_ticker_price(symbol)
            current_price = float(ticker['price'])
            slippage_pct = abs(current_price - expected_price) / expected_price
            
            logger.info(
                f"限價單超時後價格檢查: {symbol} "
                f"預期={expected_price:.6f} 當前={current_price:.6f} "
                f"滑點={slippage_pct:.2%}"
            )
            
            # 如果滑點仍然過大，拒絕降級為市價單
            if slippage_pct >= self.config.MAX_SLIPPAGE_PCT:
                logger.error(
                    f"❌ 限價單超時且滑點仍超標，拒絕下單: {symbol} "
                    f"(滑點 {slippage_pct:.2%} >= {self.config.MAX_SLIPPAGE_PCT:.2%})"
                )
                # 如果有部分成交，返回部分成交結果
                if executed_qty > 0 and order_status:
                    logger.warning(
                        f"⚠️  保留部分成交結果: {symbol} "
                        f"已成交={executed_qty}/{quantity}"
                    )
                    return order_status
                return None
            
            # ✨ 重要：只對未成交部分下市價單，避免重複暴露
            remaining_qty = quantity - executed_qty
            
            if remaining_qty <= 0:
                # 已完全成交或超量成交
                logger.info(f"✅ 限價單已完全成交: {symbol}")
                return order_status
            
            # 四捨五入剩餘數量
            remaining_qty = await self._round_quantity(symbol, remaining_qty)
            
            # 滑點已回落，安全降級為市價單（僅剩餘部分）
            logger.info(
                f"✅ 滑點已回落，對剩餘部分降級為市價單: {symbol} "
                f"剩餘={remaining_qty}/{quantity} ({remaining_qty/quantity:.1%})"
            )
            
            # 下市價單補足剩餘部分
            market_order = await self._place_market_order(symbol, side, remaining_qty, direction)
            
            # ✨ 關鍵：合併部分成交和市價單結果，使用實際成交總量
            if executed_qty > 0 and market_order and order_status:
                # 獲取市價單實際成交數量（可能因舍入與remaining_qty不同）
                market_executed_qty = float(market_order.get('executedQty', remaining_qty))
                
                # 計算實際總成交數量
                total_executed_qty = executed_qty + market_executed_qty
                
                # 計算加權平均價格（使用實際成交數量）
                limit_price = float(order_status.get('avgPrice', expected_price))
                market_price = float(market_order.get('avgPrice', current_price))
                avg_price = (limit_price * executed_qty + market_price * market_executed_qty) / total_executed_qty
                
                # 合併訂單信息
                merged_order = {
                    **market_order,
                    'executedQty': str(total_executed_qty),  # ✨ 使用實際總成交量
                    'avgPrice': str(avg_price),               # 加權平均價
                    'mixed_fill': True,                       # 標記為混合成交
                    'limit_qty': executed_qty,
                    'market_qty': market_executed_qty
                }
                
                logger.info(
                    f"📊 訂單混合成交: {symbol} "
                    f"限價={executed_qty}@{limit_price:.6f} + "
                    f"市價={market_executed_qty}@{market_price:.6f} = "
                    f"{total_executed_qty}@{avg_price:.6f}"
                )
                
                return merged_order
            
            return market_order
            
        except Exception as e:
            logger.error(f"限價單失敗 {symbol}: {e}")
            # 異常情況下不降級為不受限制的市價單，保護滑點
            # 返回None表示下單失敗
            return None
    
    async def _set_stop_loss(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        stop_price: float
    ):
        """
        設置止損單
        
        Raises:
            Exception: 如果止損設置失敗
        """
        side = "SELL" if direction == "LONG" else "BUY"
        position_side = "LONG" if direction == "LONG" else "SHORT"
        
        # 四捨五入止損價格到交易所精度
        stop_price = await self._round_price(symbol, stop_price)
        
        order = await self.client.place_order(
            symbol=symbol,
            side=side,
            order_type="STOP_MARKET",
            quantity=quantity,
            stop_price=stop_price,
            positionSide=position_side
        )
        
        if not order:
            raise Exception(f"止損訂單返回空結果")
        
        logger.info(f"✅ 設置止損: {symbol} @ {stop_price} (訂單ID: {order.get('orderId')})")
        return order
    
    async def _set_take_profit(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        take_profit_price: float
    ):
        """
        設置止盈單
        
        Raises:
            Exception: 如果止盈設置失敗
        """
        side = "SELL" if direction == "LONG" else "BUY"
        position_side = "LONG" if direction == "LONG" else "SHORT"
        
        # 四捨五入止盈價格到交易所精度
        take_profit_price = await self._round_price(symbol, take_profit_price)
        
        order = await self.client.place_order(
            symbol=symbol,
            side=side,
            order_type="TAKE_PROFIT_MARKET",
            quantity=quantity,
            stop_price=take_profit_price,
            positionSide=position_side
        )
        
        if not order:
            raise Exception(f"止盈訂單返回空結果")
        
        logger.info(f"✅ 設置止盈: {symbol} @ {take_profit_price} (訂單ID: {order.get('orderId')})")
        return order
    
    async def _set_stop_loss_take_profit_parallel(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        stop_loss: float,
        take_profit: float,
        max_retries: int = 5
    ) -> Tuple[int, int]:
        """
        並行設置止損止盈（v3.6.0強化：5次重試+訂單ID返回）
        
        優化點：
        1. 並行執行止損和止盈訂單（2倍速度提升）
        2. 失敗自動重試機制（默認5次重試）
        3. 部分成功處理（一個成功一個失敗的情況）
        4. 返回訂單ID用於驗證
        
        Args:
            symbol: 交易對
            direction: 方向 (LONG/SHORT)
            quantity: 數量
            stop_loss: 止損價格
            take_profit: 止盈價格
            max_retries: 最大重試次數（默認5次）
        
        Returns:
            Tuple[int, int]: (止損訂單ID, 止盈訂單ID)
        
        Raises:
            Exception: 如果止損止盈設置失敗
        """
        for attempt in range(max_retries):
            try:
                # 🛡️ v3.9.2.2: 順序執行（非並行），避免熔斷器
                # 檢查熔斷器狀態
                can_proceed, block_reason = self.client.circuit_breaker.can_proceed()
                if not can_proceed:
                    retry_after = self.client.circuit_breaker.get_retry_after()
                    logger.warning(
                        f"⏱️  熔斷器開啟，等待{retry_after:.0f}秒後重試止損止盈 "
                        f"(嘗試 {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_after + 1)  # +1秒安全邊際
                    continue
                
                # 先設置止損
                sl_result = await self._set_stop_loss(symbol, direction, quantity, stop_loss)
                sl_success = sl_result is not None
                
                # 🛡️ v3.9.2.2: 訂單間延遲，避免觸發熔斷器
                if sl_success:
                    logger.debug(f"⏱️  止損成功，等待{self.config.ORDER_INTER_DELAY}秒後設置止盈...")
                    await asyncio.sleep(self.config.ORDER_INTER_DELAY)
                
                # 再設置止盈
                tp_result = await self._set_take_profit(symbol, direction, quantity, take_profit)
                tp_success = tp_result is not None
                
                if sl_success and tp_success:
                    sl_order_id = sl_result.get('orderId')
                    tp_order_id = tp_result.get('orderId')
                    logger.info(f"✅ 止損止盈並行設置成功: {symbol} (SL:{sl_order_id}, TP:{tp_order_id})")
                    return (sl_order_id, tp_order_id)
                
                # 部分失敗處理
                if sl_success and not tp_success:
                    logger.warning(f"⚠️  止損成功但止盈失敗 (第{attempt+1}次嘗試): {symbol}")
                    if attempt < max_retries - 1:
                        logger.info(f"🔄 重試止盈設置...")
                        tp_retry = await self._set_take_profit(symbol, direction, quantity, take_profit)
                        if tp_retry:
                            sl_order_id = sl_result.get('orderId')
                            tp_order_id = tp_retry.get('orderId')
                            logger.info(f"✅ 止盈重試成功: {symbol}")
                            return (sl_order_id, tp_order_id)
                    else:
                        raise Exception(f"止盈設置失敗（已重試{max_retries}次）: {tp_result}")
                
                if tp_success and not sl_success:
                    logger.warning(f"⚠️  止盈成功但止損失敗 (第{attempt+1}次嘗試): {symbol}")
                    if attempt < max_retries - 1:
                        logger.info(f"🔄 重試止損設置...")
                        sl_retry = await self._set_stop_loss(symbol, direction, quantity, stop_loss)
                        if sl_retry:
                            sl_order_id = sl_retry.get('orderId')
                            tp_order_id = tp_result.get('orderId')
                            logger.info(f"✅ 止損重試成功: {symbol}")
                            return (sl_order_id, tp_order_id)
                    else:
                        raise Exception(f"止損設置失敗（已重試{max_retries}次）: {sl_result}")
                
                # 兩者都失敗
                if not sl_success and not tp_success:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"⚠️  止損止盈都失敗 (第{attempt+1}次嘗試)，{1}秒後重試..."
                        )
                        await asyncio.sleep(1)
                        continue
                    else:
                        raise Exception(
                            f"止損止盈都設置失敗（已重試{max_retries}次）: "
                            f"SL={sl_result}, TP={tp_result}"
                        )
                        
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️  止損止盈設置異常 (第{attempt+1}次嘗試): {e}，重試中...")
                    await asyncio.sleep(1)
                    continue
                else:
                    raise Exception(f"止損止盈設置異常（已重試{max_retries}次）: {e}")
        
        raise Exception(f"止損止盈設置失敗（已用完{max_retries}次重試）")
    
    async def _verify_order_exists(
        self,
        symbol: str,
        order_id: int,
        max_retries: int = 3
    ) -> bool:
        """
        驗證訂單是否存在（v3.6.0新增）
        
        Args:
            symbol: 交易對
            order_id: 訂單ID
            max_retries: 最大重試次數
        
        Returns:
            bool: 訂單是否存在
        """
        for attempt in range(max_retries):
            try:
                order = await self.client.get_order(symbol, order_id)
                if order and order.get('orderId') == order_id:
                    status = order.get('status', 'UNKNOWN')
                    logger.debug(f"✅ 訂單驗證成功: {symbol} 訂單ID {order_id} 狀態 {status}")
                    return True
                else:
                    logger.warning(f"⚠️  訂單驗證失敗: {symbol} 訂單ID {order_id} 不匹配")
                    return False
            except Exception as e:
                logger.warning(f"⚠️  訂單驗證異常 (第{attempt+1}次嘗試): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    logger.error(f"❌ 訂單驗證失敗（已重試{max_retries}次）: {symbol} 訂單ID {order_id}")
                    return False
        
        return False
    
    async def _confirm_order_filled(
        self,
        symbol: str,
        order_id: str,
        timeout: int = 5,
        check_interval: float = 0.5
    ) -> Tuple[bool, Optional[Dict]]:
        """
        確認訂單是否成交（v3.5.0優化，支持部分成交檢測）
        
        Args:
            symbol: 交易對
            order_id: 訂單ID
            timeout: 超時時間（秒）
            check_interval: 檢查間隔（秒）
        
        Returns:
            Tuple[bool, Optional[Dict]]: (是否完全成交, 訂單狀態)
        """
        elapsed = 0.0
        last_status = None
        
        while elapsed < timeout:
            try:
                order_status = await self.client.get_order(symbol, int(order_id))
                status = order_status.get('status')
                last_status = order_status
                
                if status == 'FILLED':
                    return True, order_status
                elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    return False, order_status
                elif status == 'PARTIALLY_FILLED':
                    # 繼續等待，但記錄狀態
                    last_status = order_status
                    
                await asyncio.sleep(check_interval)
                elapsed += check_interval
                
            except Exception as e:
                logger.warning(f"檢查訂單狀態失敗: {e}")
                return False, None
        
        # 超時：返回最後狀態（可能是部分成交）
        return False, last_status
    
    async def _round_quantity(self, symbol: str, quantity: float, round_up: bool = False) -> float:
        """
        根據交易所的 LOT_SIZE 過濾器四捨五入數量
        
        Args:
            symbol: 交易對
            quantity: 原始數量
            round_up: 是否向上舍入（用於確保滿足最小訂單價值）
        
        Returns:
            float: 符合交易所規則的數量
        """
        try:
            # ✨ 優化：獲取交易對過濾器（帶緩存，支持預加載）
            if symbol not in self.symbol_filters:
                # 如果沒有預加載，按需加載單個symbol
                exchange_info = await self.client.get_exchange_info()
                for s in exchange_info.get('symbols', []):
                    if s['symbol'] == symbol:
                        # 提取 LOT_SIZE 和 PRICE_FILTER 過濾器
                        filters_data = {}
                        for f in s.get('filters', []):
                            if f['filterType'] == 'LOT_SIZE':
                                filters_data.update({
                                    'stepSize': float(f['stepSize']),
                                    'minQty': float(f['minQty']),
                                    'maxQty': float(f['maxQty'])
                                })
                            elif f['filterType'] == 'PRICE_FILTER':
                                filters_data.update({
                                    'tickSize': float(f['tickSize']),
                                    'minPrice': float(f['minPrice']),
                                    'maxPrice': float(f['maxPrice'])
                                })
                        self.symbol_filters[symbol] = filters_data
                        break
            
            # 如果沒有找到過濾器，使用默認精度
            if symbol not in self.symbol_filters:
                logger.warning(f"未找到 {symbol} 的 LOT_SIZE 過濾器，使用默認精度")
                if quantity >= 1:
                    return round(quantity, 3)
                elif quantity >= 0.1:
                    return round(quantity, 4)
                else:
                    return round(quantity, 5)
            
            filters = self.symbol_filters[symbol]
            step_size = filters['stepSize']
            min_qty = filters['minQty']
            max_qty = filters['maxQty']
            
            # 根據 stepSize 計算精度（小數位數）
            import math
            if step_size >= 1:
                precision = 0
            else:
                precision = abs(int(math.log10(step_size)))
            
            # 調整數量為 stepSize 的倍數
            if round_up:
                # 向上舍入到下一個stepSize倍數
                adjusted_qty = math.ceil(quantity / step_size) * step_size
            else:
                # 四捨五入
                adjusted_qty = round(quantity / step_size) * step_size
            
            # 四捨五入到正確精度
            adjusted_qty = round(adjusted_qty, precision)
            
            # 檢查最小/最大限制
            if adjusted_qty < min_qty:
                logger.warning(f"{symbol} 數量 {adjusted_qty} < 最小值 {min_qty}，調整為最小值")
                adjusted_qty = min_qty
            elif adjusted_qty > max_qty:
                logger.warning(f"{symbol} 數量 {adjusted_qty} > 最大值 {max_qty}，調整為最大值")
                adjusted_qty = max_qty
            
            logger.debug(
                f"{symbol} 數量調整: {quantity:.8f} -> {adjusted_qty} "
                f"(stepSize={step_size}, precision={precision})"
            )
            
            return adjusted_qty
            
        except Exception as e:
            logger.error(f"調整數量失敗: {e}，使用默認舍入")
            # 降級處理
            if quantity >= 1:
                return round(quantity, 3)
            elif quantity >= 0.1:
                return round(quantity, 4)
            else:
                return round(quantity, 5)
    
    async def _round_price(self, symbol: str, price: float) -> float:
        """
        根據交易所的 PRICE_FILTER 過濾器四捨五入價格
        
        Args:
            symbol: 交易對
            price: 原始價格
        
        Returns:
            float: 符合交易所規則的價格
        """
        try:
            # 如果過濾器中沒有價格信息，先獲取
            if symbol not in self.symbol_filters or 'tickSize' not in self.symbol_filters[symbol]:
                await self._round_quantity(symbol, 1.0)  # 這會觸發獲取過濾器
            
            # 如果仍然沒有找到價格過濾器，使用默認精度
            if symbol not in self.symbol_filters or 'tickSize' not in self.symbol_filters[symbol]:
                logger.warning(f"未找到 {symbol} 的 PRICE_FILTER，使用默認精度")
                return round(price, 6)
            
            filters = self.symbol_filters[symbol]
            tick_size = filters['tickSize']
            min_price = filters['minPrice']
            max_price = filters['maxPrice']
            
            # 根據 tickSize 計算精度
            import math
            if tick_size >= 1:
                precision = 0
            else:
                precision = abs(int(math.log10(tick_size)))
            
            # 調整價格為 tickSize 的倍數
            adjusted_price = round(price / tick_size) * tick_size
            
            # 四捨五入到正確精度
            adjusted_price = round(adjusted_price, precision)
            
            # 檢查最小/最大限制
            if adjusted_price < min_price:
                logger.warning(f"{symbol} 價格 {adjusted_price} < 最小值 {min_price}，調整為最小值")
                adjusted_price = min_price
            elif adjusted_price > max_price:
                logger.warning(f"{symbol} 價格 {adjusted_price} > 最大值 {max_price}，調整為最大值")
                adjusted_price = max_price
            
            logger.debug(
                f"{symbol} 價格調整: {price:.8f} -> {adjusted_price} "
                f"(tickSize={tick_size}, precision={precision})"
            )
            
            return adjusted_price
            
        except Exception as e:
            logger.error(f"調整價格失敗: {e}，使用默認舍入")
            return round(price, 6)
    
    async def _cancel_all_open_orders(self, symbol: str) -> int:
        """
        取消指定交易對的所有未成交訂單（止損止盈等）
        
        Args:
            symbol: 交易對
        
        Returns:
            int: 取消的訂單數量
        """
        try:
            # 獲取所有未成交訂單
            open_orders = await self.client.get_open_orders(symbol)
            
            if not open_orders:
                return 0
            
            cancelled_count = 0
            for order in open_orders:
                try:
                    await self.client.cancel_order(
                        symbol=symbol,
                        order_id=order['orderId']
                    )
                    cancelled_count += 1
                    logger.debug(f"已取消訂單: {order['orderId']} ({order.get('type', 'UNKNOWN')})")
                except Exception as e:
                    logger.warning(f"取消訂單失敗 {order['orderId']}: {e}")
            
            return cancelled_count
            
        except Exception as e:
            logger.error(f"獲取未成交訂單失敗: {e}")
            return 0
    
    def _create_simulated_trade(
        self,
        signal: Dict,
        position_info: Dict,
        quantity: float
    ) -> Dict:
        """創建模擬交易（當交易功能未啟用時）"""
        return {
            'symbol': signal['symbol'],
            'direction': signal['direction'],
            'entry_price': signal['entry_price'],
            'quantity': quantity,
            'stop_loss': signal['stop_loss'],
            'take_profit': signal['take_profit'],
            'leverage': position_info['leverage'],
            'confidence': signal['confidence'],
            'position_value': position_info['position_value'],
            'margin': position_info['position_margin'],
            'timestamp': datetime.now(),
            'status': 'simulated',
            'simulated': True
        }
    
    def get_active_positions_count(self) -> int:
        """獲取活躍持倉數量"""
        return len(self.active_orders)
    
    def get_active_positions(self) -> list:
        """獲取所有活躍持倉"""
        return list(self.active_orders.values())
    
    async def check_simulated_positions_for_close(self) -> int:
        """
        檢查模擬持倉並自動平倉（達到止損/止盈時）
        
        Returns:
            int: 平倉數量
        """
        if not self.active_orders:
            return 0
        
        closed_count = 0
        
        for symbol in list(self.active_orders.keys()):
            trade = self.active_orders[symbol]
            
            # 只處理模擬交易
            if not trade.get('simulated', False):
                continue
            
            try:
                # 獲取當前市場價
                ticker = await self.client.get_ticker_price(symbol)
                current_price = float(ticker['price'])
                
                should_close = False
                close_reason = ""
                
                # 檢查止損
                if trade['direction'] == "LONG":
                    if current_price <= trade['stop_loss']:
                        should_close = True
                        close_reason = "simulated_stop_loss"
                    elif current_price >= trade['take_profit']:
                        should_close = True
                        close_reason = "simulated_take_profit"
                else:  # SHORT
                    if current_price >= trade['stop_loss']:
                        should_close = True
                        close_reason = "simulated_stop_loss"
                    elif current_price <= trade['take_profit']:
                        should_close = True
                        close_reason = "simulated_take_profit"
                
                if should_close:
                    result = await self.close_position(symbol, reason=close_reason)
                    if result:
                        closed_count += 1
                        logger.info(f"✅ 模擬平倉觸發: {symbol} @ {current_price} ({close_reason})")
            
            except Exception as e:
                logger.error(f"檢查模擬持倉失敗 {symbol}: {e}")
        
        return closed_count
