"""
交易状态机 (v3.13.0 策略8)
职责：统一风险管理逻辑，清晰的状态转换

✅ 为什么使用状态机：
1. 风险逻辑集中管理（替代分散在多个文件的if/else）
2. 清晰的状态转换（便于调试和监控）
3. 自动化决策（基于市场条件和账户状态）
4. 易于扩展新风险规则

状态转换逻辑：
    NORMAL → CAUTIOUS → RISK_AVERSE → SHUTDOWN
    
    触发条件：
    - NORMAL: 一切正常
    - CAUTIOUS: 连续亏损3次 或 小幅回撤(5-10%)
    - RISK_AVERSE: 连续亏损5次 或 中等回撤(10-15%)
    - SHUTDOWN: 回撤>15% 或 连续亏损7次

使用示例：
    state_machine = TradingStateMachine()
    
    # 更新状态（每次交易后）
    state_machine.update_state(
        consecutive_losses=3,
        drawdown_pct=0.08,
        current_equity=10000
    )
    
    # 获取风险倍数
    if state_machine.current_state == TradingState.RISK_AVERSE:
        position_size *= state_machine.get_risk_multiplier()  # 0.5x
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict
import time

logger = logging.getLogger(__name__)


class TradingState(Enum):
    """交易状态枚举"""
    NORMAL = "normal"                    # 正常交易
    CAUTIOUS = "cautious"                # 谨慎（小心）
    RISK_AVERSE = "risk_averse"          # 风险规避（保守）
    SHUTDOWN = "shutdown"                # 停止交易


@dataclass
class StateConfig:
    """状态配置"""
    name: str
    risk_multiplier: float               # 仓位倍数
    max_positions: Optional[int]         # 最大持仓数（None=无限制）
    min_confidence: float                # 最小信心度阈值
    allowed_to_open: bool                # 是否允许开新仓
    description: str
    
    # 状态转换条件
    max_consecutive_losses: int          # 最大连续亏损次数
    max_drawdown_pct: float              # 最大回撤百分比


# 状态配置表（策略2：配置驱动）
STATE_CONFIGS: Dict[TradingState, StateConfig] = {
    TradingState.NORMAL: StateConfig(
        name="正常",
        risk_multiplier=1.0,
        max_positions=None,              # 无限制
        min_confidence=0.35,              # 35%
        allowed_to_open=True,
        description="一切正常，全力交易",
        max_consecutive_losses=2,
        max_drawdown_pct=0.05
    ),
    
    TradingState.CAUTIOUS: StateConfig(
        name="谨慎",
        risk_multiplier=0.7,             # 减少30%仓位
        max_positions=None,
        min_confidence=0.45,              # 提高信心度要求
        allowed_to_open=True,
        description="小幅亏损，谨慎交易",
        max_consecutive_losses=4,
        max_drawdown_pct=0.10
    ),
    
    TradingState.RISK_AVERSE: StateConfig(
        name="风险规避",
        risk_multiplier=0.5,             # 减半仓位
        max_positions=5,                 # 限制持仓数
        min_confidence=0.55,              # 大幅提高信心度要求
        allowed_to_open=True,
        description="中等亏损，保守交易",
        max_consecutive_losses=6,
        max_drawdown_pct=0.15
    ),
    
    TradingState.SHUTDOWN: StateConfig(
        name="停止交易",
        risk_multiplier=0.0,             # 不开新仓
        max_positions=0,
        min_confidence=1.0,              # 实际上不允许开仓
        allowed_to_open=False,
        description="严重亏损，停止交易",
        max_consecutive_losses=999,
        max_drawdown_pct=1.0
    )
}


class TradingStateMachine:
    """
    交易状态机
    
    集中管理所有风险相关的状态转换和决策
    """
    
    def __init__(self, initial_equity: float = 10000.0):
        """
        初始化状态机
        
        Args:
            initial_equity: 初始资金
        """
        self.current_state = TradingState.NORMAL
        self.initial_equity = initial_equity
        self.peak_equity = initial_equity
        
        # 统计数据
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.total_trades = 0
        self.total_wins = 0
        self.total_losses = 0
        
        # 状态历史
        self.state_history = [(time.time(), TradingState.NORMAL)]
        
        logger.info(f"🎰 交易状态机初始化: {self.current_state.value}, 初始资金: ${initial_equity:.2f}")
    
    def update_state(
        self,
        current_equity: float,
        last_trade_pnl: Optional[float] = None
    ) -> bool:
        """
        更新交易状态
        
        Args:
            current_equity: 当前权益
            last_trade_pnl: 上一笔交易PnL（可选）
        
        Returns:
            状态是否发生变化
        """
        # 更新峰值权益
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        # 计算回撤
        drawdown_pct = (self.peak_equity - current_equity) / self.peak_equity
        
        # 更新交易统计
        if last_trade_pnl is not None:
            self.total_trades += 1
            if last_trade_pnl > 0:
                self.total_wins += 1
                self.consecutive_wins += 1
                self.consecutive_losses = 0
            else:
                self.total_losses += 1
                self.consecutive_losses += 1
                self.consecutive_wins = 0
        
        # 确定新状态
        old_state = self.current_state
        new_state = self._determine_state(drawdown_pct)
        
        # 状态转换
        if new_state != old_state:
            self._transition_to(new_state)
            return True
        
        return False
    
    def _determine_state(self, drawdown_pct: float) -> TradingState:
        """
        根据当前条件确定应该处于的状态
        
        Args:
            drawdown_pct: 当前回撤百分比
        
        Returns:
            应该处于的状态
        """
        # 检查是否应该 SHUTDOWN
        if (drawdown_pct >= 0.15 or self.consecutive_losses >= 7):
            return TradingState.SHUTDOWN
        
        # 检查是否应该 RISK_AVERSE
        if (drawdown_pct >= 0.10 or self.consecutive_losses >= 5):
            return TradingState.RISK_AVERSE
        
        # 检查是否应该 CAUTIOUS
        if (drawdown_pct >= 0.05 or self.consecutive_losses >= 3):
            return TradingState.CAUTIOUS
        
        # 恢复到 NORMAL（如果连胜2次以上）
        if self.consecutive_wins >= 2:
            return TradingState.NORMAL
        
        # 保持当前状态
        return self.current_state
    
    def _transition_to(self, new_state: TradingState):
        """
        执行状态转换
        
        Args:
            new_state: 新状态
        """
        old_state = self.current_state
        self.current_state = new_state
        
        # 记录历史
        self.state_history.append((time.time(), new_state))
        
        # 日志
        old_config = STATE_CONFIGS[old_state]
        new_config = STATE_CONFIGS[new_state]
        
        logger.warning(
            f"🔄 状态转换: {old_config.name} → {new_config.name}\n"
            f"   原因: 连续亏损={self.consecutive_losses}, 回撤={self._get_current_drawdown():.1%}\n"
            f"   新规则: 仓位倍数={new_config.risk_multiplier:.1f}x, "
            f"最小信心度={new_config.min_confidence:.0%}, "
            f"允许开仓={new_config.allowed_to_open}"
        )
        
        # 如果进入 SHUTDOWN，发送告警
        if new_state == TradingState.SHUTDOWN:
            logger.critical(
                f"🚨 交易系统已关闭！\n"
                f"   触发原因: 连续亏损={self.consecutive_losses}, 回撤={self._get_current_drawdown():.1%}\n"
                f"   请检查策略和市场条件，手动重启后再继续交易"
            )
    
    def get_risk_multiplier(self) -> float:
        """获取当前状态的风险倍数"""
        return STATE_CONFIGS[self.current_state].risk_multiplier
    
    def get_min_confidence(self) -> float:
        """获取当前状态的最小信心度"""
        return STATE_CONFIGS[self.current_state].min_confidence
    
    def get_max_positions(self) -> Optional[int]:
        """获取当前状态的最大持仓数"""
        return STATE_CONFIGS[self.current_state].max_positions
    
    def can_open_position(self) -> bool:
        """是否允许开新仓"""
        return STATE_CONFIGS[self.current_state].allowed_to_open
    
    def _get_current_drawdown(self) -> float:
        """获取当前回撤（用于日志）"""
        # 这个方法需要外部传入 current_equity
        # 这里只是占位符，实际调用时会在 update_state 中计算
        return 0.0
    
    def get_state_description(self) -> str:
        """获取当前状态描述"""
        config = STATE_CONFIGS[self.current_state]
        return (
            f"状态: {config.name} ({self.current_state.value})\n"
            f"仓位倍数: {config.risk_multiplier:.1f}x\n"
            f"最小信心度: {config.min_confidence:.0%}\n"
            f"最大持仓: {config.max_positions or '无限制'}\n"
            f"允许开仓: {'是' if config.allowed_to_open else '否'}\n"
            f"连续亏损: {self.consecutive_losses}\n"
            f"连续盈利: {self.consecutive_wins}"
        )
    
    def get_statistics(self) -> Dict:
        """获取状态机统计信息"""
        return {
            'current_state': self.current_state.value,
            'consecutive_losses': self.consecutive_losses,
            'consecutive_wins': self.consecutive_wins,
            'total_trades': self.total_trades,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'win_rate': self.total_wins / self.total_trades if self.total_trades > 0 else 0.0,
            'risk_multiplier': self.get_risk_multiplier(),
            'min_confidence': self.get_min_confidence(),
            'can_open': self.can_open_position()
        }
    
    def force_reset_to_normal(self):
        """强制重置到NORMAL状态（手动干预）"""
        logger.warning("⚠️  手动重置状态机到NORMAL状态")
        self.current_state = TradingState.NORMAL
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.state_history.append((time.time(), TradingState.NORMAL))
    
    def get_state_duration(self) -> float:
        """获取当前状态持续时间（秒）"""
        if len(self.state_history) < 1:
            return 0.0
        last_transition_time = self.state_history[-1][0]
        return time.time() - last_transition_time


# 全局状态机实例（单例）
_global_state_machine: Optional[TradingStateMachine] = None


def get_global_state_machine(initial_equity: float = 10000.0) -> TradingStateMachine:
    """
    获取全局状态机实例（单例模式）
    
    Args:
        initial_equity: 初始资金（仅首次调用时有效）
    
    Returns:
        全局状态机实例
    """
    global _global_state_machine
    if _global_state_machine is None:
        _global_state_machine = TradingStateMachine(initial_equity)
    return _global_state_machine
