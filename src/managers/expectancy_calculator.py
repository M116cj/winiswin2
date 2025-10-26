"""
期望值计算模块
基于最近 N 笔交易滚动计算期望值、盈亏比、胜率等关键指标
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ExpectancyCalculator:
    """
    期望值计算器
    
    功能：
    1. 计算滚动期望值（Expectancy）
    2. 计算盈亏比（Profit Factor）
    3. 计算胜率（Win Rate）
    4. 支持连续亏损检测
    """
    
    def __init__(self, window_size: int = 30):
        """
        初始化期望值计算器
        
        Args:
            window_size: 滚动窗口大小（默认30笔交易）
        """
        self.window_size = window_size
        logger.info(f"期望值计算器已初始化，窗口大小: {window_size}")
    
    def calculate_expectancy(
        self,
        trades: List[Dict]
    ) -> Dict:
        """
        计算期望值和相关指标
        
        Args:
            trades: 交易记录列表，每条记录需包含：
                - pnl_pct: 盈亏百分比
                - pnl: 盈亏金额
                - timestamp: 时间戳
        
        Returns:
            Dict: {
                'expectancy': 期望值（百分比）,
                'profit_factor': 盈亏比,
                'win_rate': 胜率,
                'avg_win': 平均盈利,
                'avg_loss': 平均亏损,
                'total_trades': 总交易数,
                'consecutive_losses': 连续亏损数,
                'max_consecutive_losses': 最大连续亏损数
            }
        """
        if not trades:
            return self._default_metrics()
        
        recent_trades = trades[-self.window_size:] if len(trades) > self.window_size else trades
        
        if len(recent_trades) < 3:
            return self._default_metrics()
        
        pnl_values = [t.get('pnl_pct', 0) for t in recent_trades]
        
        winning_trades = [p for p in pnl_values if p > 0]
        losing_trades = [p for p in pnl_values if p < 0]
        
        win_rate = len(winning_trades) / len(pnl_values) if pnl_values else 0
        
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = abs(np.mean(losing_trades)) if losing_trades else 0
        
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        total_wins = sum(winning_trades) if winning_trades else 0
        total_losses = abs(sum(losing_trades)) if losing_trades else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        consecutive_losses = self._count_consecutive_losses(pnl_values)
        max_consecutive_losses = self._max_consecutive_losses(trades)
        
        return {
            'expectancy': expectancy,
            'profit_factor': profit_factor,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_trades': len(recent_trades),
            'consecutive_losses': consecutive_losses,
            'max_consecutive_losses': max_consecutive_losses,
        }
    
    def determine_leverage(
        self,
        expectancy: float,
        profit_factor: float,
        consecutive_losses: int = 0
    ) -> Tuple[float, float]:
        """
        根据期望值和盈亏比确定杠杆范围
        
        Args:
            expectancy: 期望值（百分比，如 1.5 表示 1.5%）
            profit_factor: 盈亏比
            consecutive_losses: 连续亏损数
        
        Returns:
            Tuple[float, float]: (最小杠杆, 最大杠杆)
        """
        if consecutive_losses >= 5:
            logger.warning(f"连续亏损 {consecutive_losses} 次，强制降低杠杆")
            return (1.0, 3.0)
        
        if consecutive_losses >= 3:
            logger.warning(f"连续亏损 {consecutive_losses} 次，进入保守模式")
            return (2.0, 5.0)
        
        if expectancy < 0:
            logger.warning(f"期望值为负 ({expectancy:.2f}%)，禁止开仓")
            return (0.0, 0.0)
        
        if expectancy > 1.5 and profit_factor > 1.5:
            return (15.0, 20.0)
        elif expectancy > 0.8 and profit_factor > 1.0:
            return (10.0, 15.0)
        elif expectancy > 0.3 and profit_factor > 0.8:
            return (5.0, 10.0)
        else:
            return (3.0, 5.0)
    
    def should_trade(
        self,
        expectancy: float,
        profit_factor: float,
        consecutive_losses: int = 0,
        daily_loss_pct: float = 0,
        total_trades: int = 0
    ) -> Tuple[bool, str]:
        """
        判断是否应该开仓
        
        Args:
            expectancy: 期望值
            profit_factor: 盈亏比
            consecutive_losses: 连续亏损数
            daily_loss_pct: 今日亏损百分比
            total_trades: 总交易数（用于冷启动判断）
        
        Returns:
            Tuple[bool, str]: (是否允许交易, 原因)
        """
        # 🆕 冷启动学习模式：前30笔交易跳过期望值检查，用于收集初始数据
        if total_trades < 30:
            logger.info(
                f"🎓 学习模式 ({total_trades}/30)：跳过期望值检查，收集初始交易数据"
            )
            # 仅检查日亏损上限和极端连续亏损
            if daily_loss_pct >= 3.0:
                return False, f"触发日亏损上限 ({daily_loss_pct:.1f}% >= 3%)"
            if consecutive_losses >= 5:
                return False, f"连续亏损 {consecutive_losses} 次，暂停学习"
            return True, f"学习模式允许交易 ({total_trades}/30)"
        
        # 正常模式：完整期望值检查
        if daily_loss_pct >= 3.0:
            return False, f"触发日亏损上限 ({daily_loss_pct:.1f}% >= 3%)"
        
        if consecutive_losses >= 5:
            return False, f"连续亏损 {consecutive_losses} 次，需要策略回测检讨"
        
        if expectancy < 0:
            return False, f"期望值为负 ({expectancy:.2f}%)，禁止开仓"
        
        if consecutive_losses >= 3 and expectancy < 1.0:
            return False, f"连续亏损 {consecutive_losses} 次且期望值 < 1.0%，进入冷却期"
        
        if profit_factor < 0.5:
            return False, f"盈亏比过低 ({profit_factor:.2f} < 0.5)"
        
        return True, "允许交易"
    
    def _count_consecutive_losses(self, pnl_values: List[float]) -> int:
        """计算当前连续亏损次数"""
        consecutive = 0
        for pnl in reversed(pnl_values):
            if pnl < 0:
                consecutive += 1
            else:
                break
        return consecutive
    
    def _max_consecutive_losses(self, trades: List[Dict]) -> int:
        """计算历史最大连续亏损次数"""
        if not trades:
            return 0
        
        pnl_values = [t.get('pnl_pct', 0) for t in trades]
        max_consecutive = 0
        current_consecutive = 0
        
        for pnl in pnl_values:
            if pnl < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def get_daily_loss(self, trades: List[Dict]) -> float:
        """
        计算今日亏损百分比
        
        Args:
            trades: 交易记录列表
        
        Returns:
            float: 今日亏损百分比
        """
        if not trades:
            return 0.0
        
        today = datetime.now().date()
        
        today_trades = []
        for t in trades:
            timestamp = t.get('timestamp')
            if timestamp and isinstance(timestamp, str):
                try:
                    trade_date = datetime.fromisoformat(timestamp).date()
                    if trade_date == today:
                        today_trades.append(t)
                except (ValueError, TypeError):
                    continue
        
        if not today_trades:
            return 0.0
        
        total_pnl_pct = sum(t.get('pnl_pct', 0) for t in today_trades)
        
        return abs(total_pnl_pct) if total_pnl_pct < 0 else 0.0
    
    def _default_metrics(self) -> Dict:
        """返回默认指标（数据不足时）"""
        return {
            'expectancy': 0.0,
            'profit_factor': 0.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'total_trades': 0,
            'consecutive_losses': 0,
            'max_consecutive_losses': 0,
        }
    
    def format_metrics(self, metrics: Dict) -> str:
        """格式化指标输出"""
        return (
            f"期望值: {metrics['expectancy']:.2f}% | "
            f"盈亏比: {metrics['profit_factor']:.2f} | "
            f"胜率: {metrics['win_rate']:.1%} | "
            f"平均盈利: {metrics['avg_win']:.2f}% | "
            f"平均亏损: {metrics['avg_loss']:.2f}% | "
            f"样本: {metrics['total_trades']} 笔 | "
            f"连续亏损: {metrics['consecutive_losses']} 次"
        )
