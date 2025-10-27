"""
風險管理器
職責：動態槓桿計算、倉位大小計算、止損止盈設置
"""

from typing import Dict, Tuple, Optional
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
        
        # 🛡️ 硬性限制：單個倉位保證金不得超過可用資金50%
        # 無論信心指數、勝率、槓桿如何，這是絕對上限
        max_position_margin = account_balance * 0.5
        if position_margin > max_position_margin:
            logger.warning(
                f"⚠️  倉位保證金超過50%上限: "
                f"{position_margin:.2f} USDT ({position_margin/account_balance:.1%}) "
                f"→ 強制限制為 {max_position_margin:.2f} USDT (50%)"
            )
            position_margin = max_position_margin
            position_value = position_margin * current_leverage
        
        # ✅ 使用最終的保證金計算風險百分比（修復Architect建議）
        final_risk_pct = position_margin / account_balance
        
        return {
            'position_margin': position_margin,
            'position_value': position_value,
            'leverage': current_leverage,
            'margin_pct': final_risk_pct,
            'risk_pct': final_risk_pct
        }
    
    def calculate_leverage(
        self,
        expectancy: Optional[float] = None,
        profit_factor: Optional[float] = None,
        win_rate: Optional[float] = None,
        consecutive_losses: int = 0,
        current_drawdown: float = 0.0
    ) -> int:
        """
        計算動態槓桿（期望值驅動版本）
        
        優先使用期望值和盈亏比，降級使用勝率
        
        Args:
            expectancy: 期望值百分比 (如 1.5 表示 1.5%)
            profit_factor: 盈亏比
            win_rate: 勝率 (0-1) - 僅在期望值不可用時使用
            consecutive_losses: 連續虧損次數
            current_drawdown: 當前回撤 (0-1)
        
        Returns:
            int: 槓桿倍數
        """
        if consecutive_losses >= 5:
            logger.warning(f"連續虧損 {consecutive_losses} 次，強制最低槓桿")
            return self.config.MIN_LEVERAGE
        
        if consecutive_losses >= 3:
            logger.warning(f"連續虧損 {consecutive_losses} 次，進入保守模式")
            return min(5, self.config.BASE_LEVERAGE)
        
        # 優先級1：使用期望值（有或沒有盈亏比）
        if expectancy is not None:
            # 🎓 永久學習模式：期望值為負也允許交易，使用保守槓桿
            if expectancy < 0:
                logger.info(f"🎓 學習模式：期望值為負 ({expectancy:.2f}%)，使用基礎槓桿 {self.config.BASE_LEVERAGE}x")
                return self.config.BASE_LEVERAGE  # 返回3x而非0
            
            # 根據期望值和盈亏比動態調整槓桿
            if profit_factor is not None:
                # 有盈亏比數據，使用完整評分
                if expectancy > 1.5 and profit_factor > 1.5:
                    base_leverage = 17
                    logger.info(f"✅ 優秀期望值 ({expectancy:.2f}%, PF:{profit_factor:.2f}) → 槓桿 17x")
                elif expectancy > 0.8 and profit_factor > 1.0:
                    base_leverage = 12
                    logger.info(f"✅ 良好期望值 ({expectancy:.2f}%, PF:{profit_factor:.2f}) → 槓桿 12x")
                elif expectancy > 0.3 and profit_factor > 0.8:
                    base_leverage = 7
                    logger.info(f"⚠️  一般期望值 ({expectancy:.2f}%, PF:{profit_factor:.2f}) → 槓桿 7x")
                else:
                    base_leverage = 4
                    logger.warning(f"⚠️  低期望值 ({expectancy:.2f}%, PF:{profit_factor:.2f}) → 槓桿 4x")
            else:
                # 只有期望值，沒有盈亏比
                if expectancy > 1.5:
                    base_leverage = 15
                    logger.info(f"✅ 優秀期望值 ({expectancy:.2f}%) → 槓桿 15x")
                elif expectancy > 0.8:
                    base_leverage = 10
                    logger.info(f"✅ 良好期望值 ({expectancy:.2f}%) → 槓桿 10x")
                elif expectancy > 0.3:
                    base_leverage = 6
                    logger.info(f"⚠️  一般期望值 ({expectancy:.2f}%) → 槓桿 6x")
                else:
                    base_leverage = 4
                    logger.warning(f"⚠️  低期望值 ({expectancy:.2f}%) → 槓桿 4x")
        
        # 優先級2：使用勝率（數據不足時降級方案）
        elif win_rate is not None:
            base_leverage = self.config.BASE_LEVERAGE
            
            if win_rate > self.config.WINRATE_THRESHOLDS.get('excellent', 0.80):
                base_leverage += 6
                logger.info(f"勝率優秀 ({win_rate:.1%}) → 槓桿 {base_leverage}x")
            elif win_rate > self.config.WINRATE_THRESHOLDS.get('great', 0.70):
                base_leverage += 4
                logger.info(f"勝率良好 ({win_rate:.1%}) → 槓桿 {base_leverage}x")
            elif win_rate > self.config.WINRATE_THRESHOLDS.get('good', 0.60):
                base_leverage += 2
                logger.info(f"勝率一般 ({win_rate:.1%}) → 槓桿 {base_leverage}x")
        
        # 優先級3：默認基礎槓桿（完全沒有數據時）
        else:
            base_leverage = self.config.BASE_LEVERAGE
            logger.info(f"無歷史數據 → 使用基礎槓桿 {base_leverage}x")
        
        if current_drawdown > 0.10:
            base_leverage = self.config.BASE_LEVERAGE
        
        leverage = max(
            self.config.MIN_LEVERAGE,
            min(base_leverage, self.config.MAX_LEVERAGE)
        )
        
        return leverage
    
    def calculate_position_size_with_hard_rules(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        leverage: float,
        max_risk_pct: float = 0.01
    ) -> Dict:
        """
        计算符合硬规则的仓位大小
        
        硬规则：单笔风险 ≤ 总资金 1%
        
        Args:
            account_balance: 賬戶餘額
            entry_price: 入場價格
            stop_loss: 止損價格
            leverage: 槓桿倍數
            max_risk_pct: 最大風險百分比（默認 1%）
        
        Returns:
            Dict: 倉位信息
        """
        stop_loss_pct = abs(entry_price - stop_loss) / entry_price
        
        max_position_value = (max_risk_pct * account_balance) / stop_loss_pct
        
        max_position_value = min(max_position_value, account_balance * leverage * 0.95)
        
        position_margin = max_position_value / leverage
        
        quantity = max_position_value / entry_price
        
        return {
            'quantity': quantity,
            'position_value': max_position_value,
            'position_margin': position_margin,
            'leverage': leverage,
            'risk_amount': account_balance * max_risk_pct,
            'risk_pct': max_risk_pct,
            'stop_loss_pct': stop_loss_pct
        }
    
    def calculate_stop_loss_take_profit(
        self,
        entry_price: float,
        direction: str,
        atr: float,
        risk_reward_ratio: Optional[float] = None
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
    
    def should_trade(
        self, 
        account_balance: float, 
        current_positions: int,
        is_real_trading: bool = True
    ) -> Tuple[bool, str]:
        """
        判斷是否應該交易
        
        Args:
            account_balance: 賬戶餘額
            current_positions: 當前持倉數
            is_real_trading: 是否為真實交易（False=模擬/虛擬倉位，不受MAX_POSITIONS限制）
        
        Returns:
            Tuple[bool, str]: (是否可以交易, 原因)
        """
        # 🎯 關鍵修復：區分真實交易和模擬交易
        # - 真實交易（TRADING_ENABLED=true）：檢查TRADING_ENABLED + MAX_POSITIONS
        # - 模擬交易（TRADING_ENABLED=false）：允許通過，不受MAX_POSITIONS限制
        
        if is_real_trading:
            # 真實交易模式：必須啟用交易功能
            if not self.config.TRADING_ENABLED:
                return False, "交易功能未啟用"
            
            # 真實交易模式：檢查倉位限制
            if current_positions >= self.config.MAX_POSITIONS:
                return False, f"已達到最大持倉數 {self.config.MAX_POSITIONS}"
        # else: 模擬/虛擬倉位模式，不檢查TRADING_ENABLED和MAX_POSITIONS
        
        if self.consecutive_losses >= 5:
            return False, f"連續虧損 {self.consecutive_losses} 次，暫停交易"
        
        if self.current_drawdown / account_balance > 0.15:
            return False, f"回撤過大 {self.current_drawdown/account_balance:.1%}，暫停交易"
        
        return True, "可以交易"
