"""
風險管理器
職責：動態槓桿計算、倉位大小計算、止損止盈設置
"""

from typing import Dict, Tuple
import logging
from datetime import datetime, timedelta

from src.config import Config

logger = logging.getLogger(__name__)


class RiskManager:
    """風險管理器"""
    
    def __init__(self):
        """初始化風險管理器"""
        self.config = Config
        self.trade_history: list = []
        self.consecutive_losses = 0
        self.max_drawdown = 0.0
        self.current_drawdown = 0.0
    
    def calculate_position_size(
        self,
        account_balance: float,
        confidence_score: float,
        current_leverage: int
    ) -> Dict:
        """
        計算倉位大小
        
        Args:
            account_balance: 賬戶餘額
            confidence_score: 信心度分數 (0-1)
            current_leverage: 當前槓桿
        
        Returns:
            Dict: 倉位信息
        """
        base_margin = account_balance * self.config.BASE_MARGIN_PCT
        
        confidence_adjusted = base_margin * (confidence_score / 1.0)
        
        position_margin = max(
            account_balance * self.config.MIN_MARGIN_PCT,
            min(confidence_adjusted, account_balance * self.config.MAX_MARGIN_PCT)
        )
        
        position_value = position_margin * current_leverage
        
        risk_per_trade = position_margin
        max_risk = account_balance * 0.02
        
        if risk_per_trade > max_risk:
            position_margin = max_risk
            position_value = position_margin * current_leverage
        
        return {
            'position_margin': position_margin,
            'position_value': position_value,
            'leverage': current_leverage,
            'margin_pct': position_margin / account_balance,
            'risk_pct': risk_per_trade / account_balance
        }
    
    def calculate_leverage(
        self,
        win_rate: float,
        consecutive_losses: int,
        current_drawdown: float
    ) -> int:
        """
        計算動態槓桿
        
        Args:
            win_rate: 勝率 (0-1)
            consecutive_losses: 連續虧損次數
            current_drawdown: 當前回撤 (0-1)
        
        Returns:
            int: 槓桿倍數
        """
        base_leverage = self.config.BASE_LEVERAGE
        
        if win_rate > self.config.WINRATE_THRESHOLDS['excellent']:
            base_leverage += 6
        elif win_rate > self.config.WINRATE_THRESHOLDS['great']:
            base_leverage += 4
        elif win_rate > self.config.WINRATE_THRESHOLDS['good']:
            base_leverage += 2
        
        loss_penalty = consecutive_losses * 1
        base_leverage -= loss_penalty
        
        if current_drawdown > 0.10:
            base_leverage = self.config.BASE_LEVERAGE
        
        leverage = max(
            self.config.MIN_LEVERAGE,
            min(base_leverage, self.config.MAX_LEVERAGE)
        )
        
        return leverage
    
    def calculate_stop_loss_take_profit(
        self,
        entry_price: float,
        direction: str,
        atr: float,
        risk_reward_ratio: float = None
    ) -> Tuple[float, float]:
        """
        計算止損和止盈價格
        
        Args:
            entry_price: 入場價格
            direction: 方向 ('LONG' 或 'SHORT')
            atr: ATR 值
            risk_reward_ratio: 風險回報比
        
        Returns:
            Tuple[float, float]: (止損價格, 止盈價格)
        """
        if risk_reward_ratio is None:
            risk_reward_ratio = self.config.RISK_REWARD_RATIO
        
        stop_distance = atr * self.config.ATR_MULTIPLIER
        take_profit_distance = stop_distance * risk_reward_ratio
        
        if direction == "LONG":
            stop_loss = entry_price - stop_distance
            take_profit = entry_price + take_profit_distance
        else:
            stop_loss = entry_price + stop_distance
            take_profit = entry_price - take_profit_distance
        
        return stop_loss, take_profit
    
    def update_trade_result(self, trade: Dict):
        """
        更新交易結果
        
        Args:
            trade: 交易記錄
        """
        self.trade_history.append(trade)
        
        if trade.get('pnl', 0) < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        self._update_drawdown(trade)
        
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]
    
    def get_statistics(self) -> Dict:
        """
        獲取交易統計
        
        Returns:
            Dict: 統計信息
        """
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_pnl': 0.0,
                'max_drawdown': 0.0,
                'consecutive_losses': 0
            }
        
        total_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t.get('pnl', 0) > 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        total_pnl = sum(t.get('pnl', 0) for t in self.trade_history)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'total_pnl': total_pnl,
            'max_drawdown': self.max_drawdown,
            'current_drawdown': self.current_drawdown,
            'consecutive_losses': self.consecutive_losses
        }
    
    def _update_drawdown(self, trade: Dict):
        """更新回撤統計"""
        pnl = trade.get('pnl', 0)
        
        if pnl < 0:
            self.current_drawdown += abs(pnl)
            self.max_drawdown = max(self.max_drawdown, self.current_drawdown)
        else:
            self.current_drawdown = max(0, self.current_drawdown - pnl * 0.5)
    
    def should_trade(self, account_balance: float, current_positions: int) -> Tuple[bool, str]:
        """
        判斷是否應該交易
        
        Args:
            account_balance: 賬戶餘額
            current_positions: 當前持倉數
        
        Returns:
            Tuple[bool, str]: (是否可以交易, 原因)
        """
        if not self.config.TRADING_ENABLED:
            return False, "交易功能未啟用"
        
        if current_positions >= self.config.MAX_POSITIONS:
            return False, f"已達到最大持倉數 {self.config.MAX_POSITIONS}"
        
        if self.consecutive_losses >= 5:
            return False, f"連續虧損 {self.consecutive_losses} 次，暫停交易"
        
        if self.current_drawdown / account_balance > 0.15:
            return False, f"回撤過大 {self.current_drawdown/account_balance:.1%}，暫停交易"
        
        return True, "可以交易"
