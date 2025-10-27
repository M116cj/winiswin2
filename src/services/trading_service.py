"""
交易執行服務
職責：開倉、平倉、止損止盈設置、訂單管理
"""

from typing import Dict, Optional
import logging
from datetime import datetime

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
    
    async def execute_signal(
        self,
        signal: Dict,
        account_balance: float,
        current_leverage: int
    ) -> Optional[Dict]:
        """
        執行交易信號
        
        Args:
            signal: 交易信號
            account_balance: 賬戶餘額
            current_leverage: 當前槓桿
        
        Returns:
            Optional[Dict]: 交易結果
        """
        try:
            symbol = signal['symbol']
            direction = signal['direction']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            take_profit = signal['take_profit']
            confidence = signal['confidence']
            
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
            
            # 設置止損止盈（如果失敗則回滾）
            try:
                await self._set_stop_loss(symbol, direction, quantity, stop_loss)
                await self._set_take_profit(symbol, direction, quantity, take_profit)
            except Exception as e:
                logger.error(f"❌ 止損止盈設置失敗: {e}")
                logger.error(f"⚠️ 嘗試平倉以避免無保護持倉...")
                try:
                    # 使用_place_market_order來處理positionSide（支持單向和對衝模式）
                    close_order = await self._place_market_order(
                        symbol=symbol,
                        side="SELL" if direction == "LONG" else "BUY",
                        quantity=quantity,
                        direction=direction
                    )
                    if close_order:
                        logger.warning(f"✅ 已平倉無保護持倉: {symbol}")
                    else:
                        logger.error(f"❌ 平倉失敗: 訂單返回空結果")
                        logger.critical(f"🚨 警告：{symbol} 持倉無止損止盈保護！請手動處理！")
                except Exception as close_error:
                    logger.error(f"❌ 平倉失敗: {close_error}")
                    logger.critical(f"🚨 警告：{symbol} 持倉無止損止盈保護！請手動處理！")
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
    
    async def _place_smart_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        expected_price: float,
        direction: Optional[str] = None
    ) -> Optional[Dict]:
        """
        智能下單：自動選擇市價單或限價單
        
        策略：
        1. 獲取當前市價
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
            # 獲取當前市價
            ticker = await self.client.get_ticker_price(symbol)
            current_price = float(ticker['price'])
            
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
            
            # 等待訂單成交或超時
            import asyncio
            timeout = self.config.ORDER_TIMEOUT_SECONDS
            elapsed = 0
            check_interval = 2  # 每2秒檢查一次
            
            while elapsed < timeout:
                await asyncio.sleep(check_interval)
                elapsed += check_interval
                
                # 檢查訂單狀態
                order_status = await self.client.get_order(symbol, int(order_id))
                status = order_status.get('status')
                
                if status == 'FILLED':
                    logger.info(f"✅ 限價單成交: {symbol}")
                    return order_status
                elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    logger.warning(f"⚠️  限價單失敗: {symbol} 狀態={status}")
                    break
            
            # 超時：重新檢查滑點，決定是否降級為市價單
            logger.warning(
                f"⏰ 限價單超時 ({timeout}秒): {symbol}"
            )
            
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
                return None
            
            # 滑點已回落到可接受範圍，安全降級為市價單
            logger.info(f"✅ 滑點已回落，安全降級為市價單: {symbol}")
            return await self._place_market_order(symbol, side, quantity, direction)
            
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
            # 獲取交易對過濾器（帶緩存）
            if symbol not in self.symbol_filters:
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
