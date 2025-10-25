"""
虛擬倉位管理器
職責：追蹤 Rank 4-10 信號、虛擬 PnL 計算、ML 數據收集
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

from src.config import Config

logger = logging.getLogger(__name__)


class VirtualPositionManager:
    """虛擬倉位管理器"""
    
    def __init__(self):
        """初始化虛擬倉位管理器"""
        self.config = Config
        self.virtual_positions: Dict[str, Dict] = {}
        self.positions_file = self.config.VIRTUAL_POSITIONS_FILE
        self._load_positions()
    
    def add_virtual_position(self, signal: Dict, rank: int):
        """
        添加虛擬倉位
        
        Args:
            signal: 交易信號
            rank: 信號排名
        """
        if rank <= self.config.IMMEDIATE_EXECUTION_RANK:
            return
        
        symbol = signal['symbol']
        
        position = {
            'symbol': symbol,
            'direction': signal['direction'],
            'entry_price': signal['entry_price'],
            'stop_loss': signal['stop_loss'],
            'take_profit': signal['take_profit'],
            'confidence': signal['confidence'],
            'rank': rank,
            'entry_timestamp': datetime.now().isoformat(),
            'expiry': (datetime.now() + timedelta(hours=self.config.VIRTUAL_POSITION_EXPIRY)).isoformat(),
            'status': 'active',
            'current_pnl': 0.0,
            'max_pnl': 0.0,
            'min_pnl': 0.0
        }
        
        self.virtual_positions[symbol] = position
        self._save_positions()
        
        logger.info(
            f"➕ 添加虛擬倉位: {symbol} {signal['direction']} "
            f"Rank {rank} 信心度 {signal['confidence']:.2%}"
        )
    
    def update_virtual_positions(self, market_data: Dict[str, float]):
        """
        更新虛擬倉位 PnL
        
        Args:
            market_data: 市場價格數據 {symbol: price}
        """
        closed_positions = []
        
        for symbol, position in list(self.virtual_positions.items()):
            if position['status'] != 'active':
                continue
            
            if datetime.fromisoformat(position['expiry']) < datetime.now():
                self._close_virtual_position(symbol, "expired")
                closed_positions.append(symbol)
                continue
            
            current_price = market_data.get(symbol)
            if current_price is None:
                continue
            
            entry_price = position['entry_price']
            direction = position['direction']
            
            if direction == "LONG":
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - current_price) / entry_price
            
            position['current_pnl'] = pnl_pct
            position['max_pnl'] = max(position['max_pnl'], pnl_pct)
            position['min_pnl'] = min(position['min_pnl'], pnl_pct)
            
            if self._should_close_virtual(position, current_price):
                reason = self._get_close_reason(position, current_price)
                self._close_virtual_position(symbol, reason)
                closed_positions.append(symbol)
        
        if closed_positions:
            self._save_positions()
    
    def _should_close_virtual(self, position: Dict, current_price: float) -> bool:
        """判斷是否應該關閉虛擬倉位"""
        direction = position['direction']
        stop_loss = position['stop_loss']
        take_profit = position['take_profit']
        
        if direction == "LONG":
            if current_price <= stop_loss:
                return True
            if current_price >= take_profit:
                return True
        else:
            if current_price >= stop_loss:
                return True
            if current_price <= take_profit:
                return True
        
        return False
    
    def _get_close_reason(self, position: Dict, current_price: float) -> str:
        """獲取關閉原因"""
        direction = position['direction']
        stop_loss = position['stop_loss']
        take_profit = position['take_profit']
        
        if direction == "LONG":
            if current_price <= stop_loss:
                return "stop_loss"
            if current_price >= take_profit:
                return "take_profit"
        else:
            if current_price >= stop_loss:
                return "stop_loss"
            if current_price <= take_profit:
                return "take_profit"
        
        return "unknown"
    
    def _close_virtual_position(self, symbol: str, reason: str):
        """關閉虛擬倉位"""
        if symbol not in self.virtual_positions:
            return
        
        position = self.virtual_positions[symbol]
        position['status'] = 'closed'
        position['close_reason'] = reason
        position['close_timestamp'] = datetime.now().isoformat()
        
        final_pnl = position['current_pnl']
        
        logger.info(
            f"✅ 虛擬倉位關閉: {symbol} "
            f"PnL: {final_pnl:+.2%} 原因: {reason}"
        )
    
    def get_active_virtual_positions(self) -> List[Dict]:
        """獲取所有活躍虛擬倉位"""
        return [
            pos for pos in self.virtual_positions.values()
            if pos['status'] == 'active'
        ]
    
    def get_closed_virtual_positions(self) -> List[Dict]:
        """獲取所有已關閉虛擬倉位"""
        return [
            pos for pos in self.virtual_positions.values()
            if pos['status'] == 'closed'
        ]
    
    def get_statistics(self) -> Dict:
        """獲取虛擬倉位統計"""
        closed = self.get_closed_virtual_positions()
        
        if not closed:
            return {
                'total': 0,
                'win_rate': 0.0,
                'avg_pnl': 0.0
            }
        
        winning = sum(1 for p in closed if p['current_pnl'] > 0)
        win_rate = winning / len(closed) if closed else 0.0
        avg_pnl = sum(p['current_pnl'] for p in closed) / len(closed) if closed else 0.0
        
        return {
            'total': len(closed),
            'winning': winning,
            'losing': len(closed) - winning,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'active': len(self.get_active_virtual_positions())
        }
    
    def _load_positions(self):
        """從文件加載虛擬倉位"""
        if os.path.exists(self.positions_file):
            try:
                with open(self.positions_file, 'r', encoding='utf-8') as f:
                    self.virtual_positions = json.load(f)
                logger.info(f"加載 {len(self.virtual_positions)} 個虛擬倉位")
            except Exception as e:
                logger.error(f"加載虛擬倉位失敗: {e}")
                self.virtual_positions = {}
        else:
            self.virtual_positions = {}
    
    def _save_positions(self):
        """保存虛擬倉位到文件"""
        try:
            os.makedirs(os.path.dirname(self.positions_file), exist_ok=True)
            with open(self.positions_file, 'w', encoding='utf-8') as f:
                json.dump(self.virtual_positions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存虛擬倉位失敗: {e}")
