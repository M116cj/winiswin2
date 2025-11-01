"""
模拟 Binance 客户端 - 用于本地测试
生成随机K线数据和账户信息，无需真实API连接
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MockBinanceClient:
    """
    模拟 Binance 客户端
    
    功能：
    - 生成随机K线数据
    - 返回模拟账户余额
    - 模拟下单和平仓
    - 记录模拟交易历史
    """
    
    def __init__(self, initial_balance: float = 10000.0):
        """
        初始化模拟客户端
        
        Args:
            initial_balance: 初始余额（USDT）
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.margin_used = 0.0
        self.positions: Dict[str, Dict] = {}
        self.orders_history: List[Dict] = []
        
        # 支持的交易对列表（50个主流币对）
        self.symbols = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOGEUSDT',
            'XRPUSDT', 'DOTUSDT', 'UNIUSDT', 'LTCUSDT', 'LINKUSDT',
            'SOLUSDT', 'MATICUSDT', 'ETCUSDT', 'XLMUSDT', 'VETUSDT',
            'FILUSDT', 'TRXUSDT', 'EOSUSDT', 'AAVEUSDT', 'MKRUSDT',
            'ATOMUSDT', 'AXSUSDT', 'SANDUSDT', 'MANAUSDT', 'ALGOUSDT',
            'ICPUSDT', 'NEARUSDT', 'APTUSDT', 'ARBUSDT', 'OPUSDT',
            'LDOUSDT', 'INJUSDT', 'SUIUSDT', 'SEIUSDT', 'TIAUSDT',
            'WLDUSDT', 'AVAXUSDT', 'FTMUSDT', 'HBARUSDT', 'RUNEUSDT',
            'GALAUSDT', 'APEUSDT', 'GRTUSDT', 'FLOWUSDT', 'CHZUSDT',
            'STXUSDT', 'IMXUSDT', 'GMXUSDT', 'BLURUSDT', 'CRVUSDT'
        ]
        
        # 模拟价格（美元）
        self.current_prices = {
            'BTCUSDT': 68000.0,
            'ETHUSDT': 2500.0,
            'BNBUSDT': 580.0,
            'ADAUSDT': 0.45,
            'DOGEUSDT': 0.12,
            'XRPUSDT': 0.55,
            'DOTUSDT': 6.8,
            'UNIUSDT': 12.5,
            'LTCUSDT': 85.0,
            'LINKUSDT': 15.2,
            'SOLUSDT': 155.0,
            'MATICUSDT': 0.85,
            'ETCUSDT': 28.0,
            'XLMUSDT': 0.11,
            'VETUSDT': 0.025,
            'FILUSDT': 5.2,
            'TRXUSDT': 0.095,
            'EOSUSDT': 0.75,
            'AAVEUSDT': 165.0,
            'MKRUSDT': 1450.0,
            'ATOMUSDT': 9.5,
            'AXSUSDT': 8.2,
            'SANDUSDT': 0.52,
            'MANAUSDT': 0.48,
            'ALGOUSDT': 0.18,
            'ICPUSDT': 12.8,
            'NEARUSDT': 6.2,
            'APTUSDT': 9.8,
            'ARBUSDT': 1.15,
            'OPUSDT': 2.05,
            'LDOUSDT': 2.8,
            'INJUSDT': 28.5,
            'SUIUSDT': 3.2,
            'SEIUSDT': 0.55,
            'TIAUSDT': 8.5,
            'WLDUSDT': 2.2,
            'AVAXUSDT': 38.0,
            'FTMUSDT': 0.68,
            'HBARUSDT': 0.075,
            'RUNEUSDT': 5.8,
            'GALAUSDT': 0.042,
            'APEUSDT': 1.25,
            'GRTUSDT': 0.18,
            'FLOWUSDT': 0.95,
            'CHZUSDT': 0.082,
            'STXUSDT': 1.85,
            'IMXUSDT': 1.65,
            'GMXUSDT': 38.5,
            'BLURUSDT': 0.35,
            'CRVUSDT': 0.68,
        }
        
        logger.info("=" * 80)
        logger.info("🎮 MockBinanceClient 初始化完成")
        logger.info(f"   💰 初始余额: ${initial_balance:,.2f}")
        logger.info(f"   📊 支持币对: {len(self.symbols)}个")
        logger.info("=" * 80)
    
    def test_connectivity(self) -> bool:
        """测试连接（模拟总是成功）"""
        logger.info("✅ 模拟API连接测试通过")
        return True
    
    def get_account_balance(self) -> Dict:
        """
        获取账户余额
        
        Returns:
            {
                'totalWalletBalance': float,  # 总余额
                'availableBalance': float,     # 可用余额
                'totalMarginBalance': float,   # 总保证金余额
                'totalUnrealizedProfit': float # 未实现盈亏
            }
        """
        # 计算未实现盈亏
        unrealized_pnl = sum(
            pos.get('unrealizedProfit', 0.0) 
            for pos in self.positions.values()
        )
        
        total_balance = self.balance + unrealized_pnl
        available_balance = total_balance - self.margin_used
        
        return {
            'totalWalletBalance': total_balance,
            'availableBalance': available_balance,
            'totalMarginBalance': total_balance,
            'totalUnrealizedProfit': unrealized_pnl
        }
    
    def get_klines(
        self, 
        symbol: str, 
        interval: str = '15m', 
        limit: int = 100
    ) -> List[List]:
        """
        生成随机K线数据
        
        Args:
            symbol: 交易对
            interval: K线周期
            limit: 数量
            
        Returns:
            K线数据列表 [[时间, 开, 高, 低, 收, 成交量, ...], ...]
        """
        if symbol not in self.current_prices:
            # 随机价格
            base_price = random.uniform(0.1, 100.0)
        else:
            base_price = self.current_prices[symbol]
        
        klines = []
        current_time = datetime.now()
        
        # 时间间隔映射
        interval_minutes = {
            '1m': 1, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '4h': 240, '1d': 1440
        }
        minutes = interval_minutes.get(interval, 15)
        
        for i in range(limit):
            # 生成随机价格波动
            open_price = base_price * (1 + random.uniform(-0.02, 0.02))
            close_price = open_price * (1 + random.uniform(-0.015, 0.015))
            high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.01))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.01))
            volume = random.uniform(1000, 10000)
            
            timestamp = int((current_time - timedelta(minutes=minutes * (limit - i))).timestamp() * 1000)
            
            klines.append([
                timestamp,
                str(open_price),
                str(high_price),
                str(low_price),
                str(close_price),
                str(volume),
                timestamp + minutes * 60000,
                str(volume * base_price),
                100 + random.randint(-20, 20),
                str(volume * 0.5),
                str(volume * base_price * 0.5),
                '0'
            ])
            
            base_price = close_price
        
        return klines
    
    def get_symbol_ticker(self, symbol: str) -> Dict:
        """
        获取交易对价格
        
        Returns:
            {'symbol': str, 'price': str}
        """
        price = self.current_prices.get(symbol, random.uniform(0.1, 100.0))
        return {'symbol': symbol, 'price': str(price)}
    
    def get_open_positions(self) -> List[Dict]:
        """获取当前持仓"""
        return [
            {
                'symbol': symbol,
                'positionAmt': str(pos['quantity']),
                'entryPrice': str(pos['entry_price']),
                'markPrice': str(self.current_prices.get(symbol, pos['entry_price'])),
                'unrealizedProfit': str(pos.get('unrealizedProfit', 0.0)),
                'leverage': str(pos['leverage']),
                'positionSide': pos['side']
            }
            for symbol, pos in self.positions.items()
        ]
    
    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        **kwargs
    ) -> Dict:
        """
        模拟下单
        
        Args:
            symbol: 交易对
            side: BUY/SELL
            order_type: MARKET/LIMIT
            quantity: 数量
            price: 价格（限价单）
            
        Returns:
            订单信息
        """
        current_price = self.current_prices.get(symbol, random.uniform(0.1, 100.0))
        execution_price = price if price and order_type == 'LIMIT' else current_price
        
        # 计算保证金
        leverage = kwargs.get('leverage', 1)
        notional = quantity * execution_price
        margin_required = notional / leverage
        
        order = {
            'orderId': len(self.orders_history) + 1,
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'origQty': str(quantity),
            'price': str(execution_price),
            'executedQty': str(quantity),
            'status': 'FILLED',
            'leverage': leverage,
            'margin': margin_required
        }
        
        self.orders_history.append(order)
        
        # 更新持仓
        if symbol in self.positions:
            # 平仓逻辑
            pos = self.positions[symbol]
            pnl = (execution_price - pos['entry_price']) * quantity
            if pos['side'] == 'SHORT':
                pnl = -pnl
            
            self.balance += pnl
            self.margin_used -= pos['margin']
            del self.positions[symbol]
            
            logger.info(f"✅ {symbol} 平仓完成 | PnL: ${pnl:.2f}")
        else:
            # 开仓
            self.positions[symbol] = {
                'quantity': quantity,
                'entry_price': execution_price,
                'side': 'LONG' if side == 'BUY' else 'SHORT',
                'leverage': leverage,
                'margin': margin_required,
                'unrealizedProfit': 0.0
            }
            self.margin_used += margin_required
            
            logger.info(
                f"✅ {symbol} 开仓完成 | "
                f"{side} {quantity} @ ${execution_price:.4f} | "
                f"杠杆: {leverage}x"
            )
        
        return order
    
    def close_position(self, symbol: str) -> bool:
        """平仓"""
        if symbol not in self.positions:
            return False
        
        pos = self.positions[symbol]
        current_price = self.current_prices.get(symbol, pos['entry_price'])
        
        # 平仓
        side = 'SELL' if pos['side'] == 'LONG' else 'BUY'
        self.place_order(
            symbol=symbol,
            side=side,
            order_type='MARKET',
            quantity=pos['quantity'],
            leverage=pos['leverage']
        )
        
        return True
    
    def get_exchange_info(self) -> Dict:
        """获取交易所信息"""
        symbols_info = []
        for symbol in self.symbols:
            symbols_info.append({
                'symbol': symbol,
                'status': 'TRADING',
                'baseAsset': symbol[:-4],
                'quoteAsset': 'USDT',
                'contractType': 'PERPETUAL',
                'filters': [
                    {'filterType': 'LOT_SIZE', 'minQty': '0.001', 'stepSize': '0.001'},
                    {'filterType': 'PRICE_FILTER', 'minPrice': '0.01', 'tickSize': '0.01'},
                    {'filterType': 'MIN_NOTIONAL', 'notional': '10'}
                ]
            })
        
        return {'symbols': symbols_info}
