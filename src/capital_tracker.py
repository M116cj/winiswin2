"""
💼 Capital Tracker - Real-time Account Total Equity Tracking
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

追蹤帳戶總權益 (Total Equity)，而不僅僅是現金餘額

Total Equity = Available Balance + Open Position Value + Unrealized PnL

例子:
  Available Balance: $8,000
  Open Positions: 1 BTC @ $42,000 entry, current $43,000
    - Unrealized PnL: +$1,000
  Total Equity: $8,000 + $43,000 = $51,000
"""

import logging
from typing import Dict, Optional, List
import json

logger = logging.getLogger(__name__)


class CapitalTracker:
    """追蹤帳戶總權益和倉位"""
    
    def __init__(self, initial_balance: float):
        """
        Initialize tracker
        
        Args:
            initial_balance: 初始餘額 (USD)
        """
        self.initial_balance = initial_balance
        self.available_balance = initial_balance
        self.positions: Dict[str, Dict] = {}  # {symbol: {entry_price, quantity, unrealized_pnl, ...}}
        self.trade_history: List[Dict] = []
    
    def get_total_equity(self) -> float:
        """
        計算並返回當前總權益
        
        Total Equity = Available Balance + Sum(Position Values)
        
        Returns:
            float: 總權益 (USD)
        """
        
        equity = self.available_balance
        
        # 加上所有開倉的值
        for symbol, pos in self.positions.items():
            if pos.get('quantity', 0) > 0:
                # Position Value = Current Price × Quantity
                current_price = pos.get('current_price', pos.get('entry_price', 0))
                equity += current_price * pos.get('quantity', 0)
        
        return equity
    
    def get_unrealized_pnl(self) -> float:
        """
        計算所有開倉的未實現 PnL
        
        Unrealized PnL = Sum(Current Price - Entry Price) × Quantity for all positions
        
        Returns:
            float: 未實現 PnL (USD)
        """
        
        total_upnl = 0.0
        
        for symbol, pos in self.positions.items():
            if pos.get('quantity', 0) > 0:
                entry_price = pos.get('entry_price', 0)
                current_price = pos.get('current_price', entry_price)
                quantity = pos.get('quantity', 0)
                side = pos.get('side', 'BUY')
                
                if side == 'BUY':
                    upnl = (current_price - entry_price) * quantity
                else:  # SELL
                    upnl = (entry_price - current_price) * quantity
                
                total_upnl += upnl
                pos['unrealized_pnl'] = upnl
        
        return total_upnl
    
    def open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        order_amount: float
    ) -> Dict:
        """
        記錄開倉
        
        Args:
            symbol: 交易對 (e.g., BTCUSDT)
            side: 方向 (BUY or SELL)
            quantity: 數量
            entry_price: 進場價格
            order_amount: 下單金額 (USD)
        
        Returns:
            Position record
        """
        
        try:
            self.positions[symbol] = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'entry_price': entry_price,
                'current_price': entry_price,
                'order_amount': order_amount,
                'unrealized_pnl': 0.0,
                'status': 'OPEN',
                'timestamp': __import__('time').time()
            }
            
            # 從可用餘額中扣除
            self.available_balance -= order_amount
            
            logger.info(f"📈 Position Opened: {symbol} {side} {quantity} @ ${entry_price:.2f}")
            return self.positions[symbol]
        
        except Exception as e:
            logger.error(f"Error opening position: {e}")
            return {}
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        realized_pnl: float
    ) -> Dict:
        """
        記錄平倉
        
        Args:
            symbol: 交易對
            exit_price: 出場價格
            realized_pnl: 實現損益 (USD)
        
        Returns:
            Closed position record
        """
        
        try:
            if symbol not in self.positions:
                logger.warning(f"Position {symbol} not found")
                return {}
            
            pos = self.positions[symbol]
            pos['exit_price'] = exit_price
            pos['realized_pnl'] = realized_pnl
            pos['status'] = 'CLOSED'
            
            # 返還餘額
            self.available_balance += pos['order_amount'] + realized_pnl
            
            # 記錄到歷史
            self.trade_history.append({
                'symbol': symbol,
                'side': pos['side'],
                'quantity': pos['quantity'],
                'entry_price': pos['entry_price'],
                'exit_price': exit_price,
                'realized_pnl': realized_pnl,
                'return_pct': (realized_pnl / pos['order_amount']) * 100,
                'timestamp': pos['timestamp']
            })
            
            # 移除開倉記錄
            del self.positions[symbol]
            
            logger.info(f"📉 Position Closed: {symbol}, PnL: ${realized_pnl:.2f}")
            return {**pos, 'realized_pnl': realized_pnl}
        
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {}
    
    def update_position_price(self, symbol: str, current_price: float) -> None:
        """
        更新開倉的當前價格 (用於計算未實現 PnL)
        
        Args:
            symbol: 交易對
            current_price: 當前價格
        """
        
        if symbol in self.positions:
            self.positions[symbol]['current_price'] = current_price
    
    def get_account_status(self) -> Dict:
        """
        獲取完整的帳戶狀態
        
        Returns:
            {
                'total_equity': 總權益,
                'available_balance': 可用餘額,
                'unrealized_pnl': 未實現 PnL,
                'realized_pnl': 已實現 PnL (from history),
                'open_positions': 開倉數量,
                'trade_count': 總交易數,
                'win_rate': 勝率,
                'total_return_pct': 總回報率
            }
        """
        
        total_equity = self.get_total_equity()
        unrealized_pnl = self.get_unrealized_pnl()
        
        # 計算已實現 PnL
        realized_pnl = sum(t['realized_pnl'] for t in self.trade_history)
        
        # 計算勝率
        wins = len([t for t in self.trade_history if t['realized_pnl'] > 0])
        losses = len([t for t in self.trade_history if t['realized_pnl'] < 0])
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        
        # 總回報率
        total_pnl = realized_pnl + unrealized_pnl
        total_return_pct = (total_pnl / self.initial_balance) * 100
        
        return {
            'total_equity': total_equity,
            'available_balance': self.available_balance,
            'unrealized_pnl': unrealized_pnl,
            'realized_pnl': realized_pnl,
            'total_pnl': total_pnl,
            'open_positions': len(self.positions),
            'trade_count': len(self.trade_history),
            'win_rate': win_rate,
            'total_return_pct': total_return_pct,
            'initial_balance': self.initial_balance,
            'positions': list(self.positions.keys())
        }
    
    def to_dict(self) -> Dict:
        """序列化為 dict"""
        return {
            'initial_balance': self.initial_balance,
            'available_balance': self.available_balance,
            'positions': self.positions,
            'trade_history': self.trade_history
        }
    
    def to_json(self) -> str:
        """序列化為 JSON"""
        return json.dumps(self.to_dict(), indent=2)


# Global instance
_tracker: Optional[CapitalTracker] = None


def init_capital_tracker(initial_balance: float) -> CapitalTracker:
    """初始化全局 tracker"""
    global _tracker
    _tracker = CapitalTracker(initial_balance)
    logger.info(f"💼 Capital tracker initialized: Initial Balance = ${initial_balance:.2f}")
    return _tracker


def get_capital_tracker() -> Optional[CapitalTracker]:
    """獲取全局 tracker"""
    return _tracker


def get_total_equity() -> float:
    """快速獲取總權益"""
    if _tracker:
        return _tracker.get_total_equity()
    return 0.0


def get_account_status() -> Dict:
    """快速獲取帳戶狀態"""
    if _tracker:
        return _tracker.get_account_status()
    return {}
