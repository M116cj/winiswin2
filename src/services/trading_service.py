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
        risk_manager: RiskManager
    ):
        """
        初始化交易服務
        
        Args:
            binance_client: Binance 客戶端
            risk_manager: 風險管理器
        """
        self.client = binance_client
        self.risk_manager = risk_manager
        self.config = Config
        self.active_orders: Dict[str, dict] = {}
    
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
            
            quantity = self._round_quantity(symbol, quantity)
            
            logger.info(
                f"準備開倉: {symbol} {direction} "
                f"數量: {quantity} 槓桿: {current_leverage}x "
                f"信心度: {confidence:.2%}"
            )
            
            if not self.config.TRADING_ENABLED:
                logger.warning("交易功能未啟用，跳過實際下單")
                return self._create_simulated_trade(
                    signal, position_info, quantity
                )
            
            order = await self._place_market_order(
                symbol=symbol,
                side="BUY" if direction == "LONG" else "SELL",
                quantity=quantity
            )
            
            if not order:
                logger.error(f"開倉失敗: {symbol}")
                return None
            
            await self._set_stop_loss(symbol, direction, quantity, stop_loss)
            await self._set_take_profit(symbol, direction, quantity, take_profit)
            
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
            
            order = await self._place_market_order(
                symbol=symbol,
                side=side,
                quantity=trade['quantity']
            )
            
            if not order:
                logger.error(f"平倉失敗: {symbol}")
                return None
            
            exit_price = float(order.get('avgPrice', 0))
            
            if trade['direction'] == "LONG":
                pnl = (exit_price - trade['entry_price']) * trade['quantity']
            else:
                pnl = (trade['entry_price'] - exit_price) * trade['quantity']
            
            pnl_pct = pnl / trade['margin']
            
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
    
    async def _place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float
    ) -> Optional[Dict]:
        """下市價單"""
        try:
            order = await self.client.place_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity
            )
            return order
        except Exception as e:
            logger.error(f"下單失敗 {symbol} {side} {quantity}: {e}")
            return None
    
    async def _set_stop_loss(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        stop_price: float
    ):
        """設置止損單"""
        try:
            side = "SELL" if direction == "LONG" else "BUY"
            
            await self.client.place_order(
                symbol=symbol,
                side=side,
                order_type="STOP_MARKET",
                quantity=quantity,
                stop_price=stop_price
            )
            
            logger.info(f"設置止損: {symbol} @ {stop_price}")
            
        except Exception as e:
            logger.error(f"設置止損失敗: {e}")
    
    async def _set_take_profit(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        take_profit_price: float
    ):
        """設置止盈單"""
        try:
            side = "SELL" if direction == "LONG" else "BUY"
            
            await self.client.place_order(
                symbol=symbol,
                side=side,
                order_type="TAKE_PROFIT_MARKET",
                quantity=quantity,
                stop_price=take_profit_price
            )
            
            logger.info(f"設置止盈: {symbol} @ {take_profit_price}")
            
        except Exception as e:
            logger.error(f"設置止盈失敗: {e}")
    
    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """
        四捨五入數量到合適精度
        
        Args:
            symbol: 交易對
            quantity: 原始數量
        
        Returns:
            float: 四捨五入後的數量
        """
        if quantity >= 1:
            return round(quantity, 3)
        elif quantity >= 0.1:
            return round(quantity, 4)
        else:
            return round(quantity, 5)
    
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
