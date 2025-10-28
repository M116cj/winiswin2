"""
風險管理器 - 輕量級兼容層（v3.17+）
原始 RiskManager 功能已整合到 LeverageEngine 和 SelfLearningTrader
此文件僅保留向後兼容接口
"""

import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)


class RiskManager:
    """
    風險管理器輕量級兼容層
    
    v3.17+ 注意：
    - 真正的槓桿計算在 LeverageEngine
    - 真正的開倉邏輯在 SelfLearningTrader
    - 此類僅保留向後兼容
    """
    
    def __init__(self):
        """初始化風險管理器（兼容層）"""
        self.current_drawdown = 0.0
        logger.info("✅ 風險管理器（兼容層）已初始化")
    
    def should_trade(
        self,
        account_balance: float,
        active_positions: int,
        is_real_trading: bool = False
    ) -> Tuple[bool, str]:
        """
        檢查是否可以交易（簡化版本）
        
        v3.17+: 真正的風險控制在 SelfLearningTrader
        
        Args:
            account_balance: 賬戶餘額
            active_positions: 活躍倉位數
            is_real_trading: 是否為真實交易
            
        Returns:
            (可交易, 原因)
        """
        # 僅做基礎檢查
        if account_balance <= 0:
            return False, "賬戶餘額不足"
        
        # v3.17+: 無持倉上限限制
        return True, "風險檢查通過"
    
    def calculate_leverage(
        self,
        expectancy: float = 0,
        profit_factor: float = 1.0,
        win_rate: float = 0.5,
        consecutive_losses: int = 0,
        current_drawdown: float = 0
    ) -> int:
        """
        計算槓桿（兼容舊系統）
        
        v3.17+: 真正的槓桿計算在 LeverageEngine.calculate_leverage()
        此方法僅返回保守值用於向後兼容
        
        Args:
            expectancy: 期望值
            profit_factor: 盈虧比
            win_rate: 勝率
            consecutive_losses: 連續虧損次數
            current_drawdown: 當前回撤
            
        Returns:
            槓桿倍數（保守值）
        """
        # 期望值為負，禁止開倉
        if expectancy <= 0:
            return 0
        
        # 返回保守槓桿值
        if win_rate >= 0.6:
            return 5
        elif win_rate >= 0.5:
            return 3
        else:
            return 1
    
    def log_risk_status(self):
        """輸出風險狀態（簡化版）"""
        logger.info("📊 風險管理狀態（兼容層）")
        logger.info(f"   回撤: {self.current_drawdown:.2f} USDT")
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取風險統計（簡化版）"""
        return {
            'current_drawdown': self.current_drawdown,
            'max_drawdown': 0,
            'risk_level': 'normal'
        }
