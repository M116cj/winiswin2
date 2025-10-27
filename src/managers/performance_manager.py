"""
性能管理器 (v3.13.0 策略5)
职责：合并 trade_recorder + expectancy_calculator + model_scorer → 单一管理器

✅ 为什么合并3个小管理器：
1. 功能高度耦合（都操作 trades.json）
2. 减少文件I/O次数（共享状态）
3. 提升内聚性（所有性能指标集中管理）
4. 代码量减少 30%+

原有模块：
- trade_recorder.py (296行) - 交易记录
- expectancy_calculator.py (276行) - 期望值计算
- model_scorer.py (357行) - 模型评分
合并后：~600行（减少 329行，-35%）
"""

import json
import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import time

from src.config import Config

logger = logging.getLogger(__name__)


@dataclass
class TradeStats:
    """交易统计数据"""
    __slots__ = ('total_trades', 'wins', 'losses', 'win_rate', 'avg_pnl',
                 'total_pnl', 'max_win', 'max_loss', 'expectancy',
                 'profit_factor', 'sharpe_ratio')
    
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_pnl: float
    total_pnl: float
    max_win: float
    max_loss: float
    expectancy: float
    profit_factor: float
    sharpe_ratio: float


@dataclass
class ModelScore:
    """模型评分数据"""
    __slots__ = ('model_name', 'total_score', 'pnl_score', 'confidence_score',
                 'win_rate_score', 'trade_count', 'avg_pnl', 'win_rate')
    
    model_name: str
    total_score: float
    pnl_score: float
    confidence_score: float
    win_rate_score: float
    trade_count: int
    avg_pnl: float
    win_rate: float


class PerformanceManager:
    """
    统一性能管理器（v3.13.0合并版）
    
    集成功能：
    1. 交易记录（TradeRecorder）
    2. 期望值计算（ExpectancyCalculator）
    3. 模型评分（ModelScorer）
    4. 每日报告生成
    """
    
    def __init__(self, trades_file: Optional[str] = None):
        """
        初始化性能管理器
        
        Args:
            trades_file: 交易记录文件路径
        """
        self.config = Config
        self.trades_file = trades_file or self.config.TRADES_FILE
        
        # 内部状态（共享）
        self.trades: List[Dict] = []
        self.daily_stats: Dict[str, Dict] = {}
        
        # 缓存
        self._stats_cache: Optional[TradeStats] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 300.0  # 5分钟缓存
        
        # 加载现有交易
        self._load_trades()
        
        logger.info(f"✅ 性能管理器初始化（已加载 {len(self.trades)} 笔交易）")
    
    # =========================================================================
    # 交易记录功能（原 TradeRecorder）
    # =========================================================================
    
    def record_trade_open(self, position_data: Dict, signal_data: Dict, is_virtual: bool = False):
        """
        记录开仓
        
        Args:
            position_data: 持仓数据
            signal_data: 信号数据
            is_virtual: 是否虚拟仓位
        """
        trade = {
            'event': 'open',
            'timestamp': datetime.now().isoformat(),
            'symbol': position_data.get('symbol'),
            'direction': position_data.get('direction'),
            'entry_price': position_data.get('entry_price'),
            'stop_loss': position_data.get('stop_loss'),
            'take_profit': position_data.get('take_profit'),
            'confidence': signal_data.get('confidence', 0.0),
            'is_virtual': is_virtual,
            'leverage': position_data.get('leverage', 10),
            
            # 技术指标
            'indicators': signal_data.get('indicators', {}),
            'scores': signal_data.get('scores', {}),
            'trends': signal_data.get('trends', {}),
        }
        
        self.trades.append(trade)
        self._save_trades()
        self._invalidate_cache()
        
        logger.debug(f"📝 记录开仓: {trade['symbol']} {trade['direction']}")
    
    def record_trade_close(self, position_data: Dict, close_data: Dict):
        """
        记录平仓
        
        Args:
            position_data: 持仓数据
            close_data: 平仓数据
        """
        trade = {
            'event': 'close',
            'timestamp': close_data.get('timestamp', datetime.now().isoformat()),
            'symbol': position_data.get('symbol'),
            'direction': position_data.get('direction'),
            'entry_price': position_data.get('entry_price'),
            'exit_price': close_data.get('exit_price', close_data.get('close_price')),
            'pnl': close_data.get('pnl', 0.0),
            'pnl_pct': close_data.get('pnl_pct', 0.0),
            'close_reason': close_data.get('close_reason', 'unknown'),
            'is_virtual': close_data.get('is_virtual', False),
            'confidence': position_data.get('confidence', 0.0),
        }
        
        self.trades.append(trade)
        self._save_trades()
        self._invalidate_cache()
        
        result = '✅' if trade['pnl'] > 0 else '❌'
        logger.info(
            f"{result} 记录平仓: {trade['symbol']} "
            f"PnL: {trade['pnl_pct']:+.2%} 原因: {trade['close_reason']}"
        )
    
    # =========================================================================
    # 期望值计算功能（原 ExpectancyCalculator）
    # =========================================================================
    
    def calculate_expectancy(self, window: Optional[int] = None) -> Tuple[float, Dict]:
        """
        计算期望值
        
        Args:
            window: 计算窗口（最近N笔交易，None=全部）
        
        Returns:
            (expectancy, stats_dict)
        """
        closed_trades = [t for t in self.trades if t.get('event') == 'close']
        
        if window:
            closed_trades = closed_trades[-window:]
        
        if not closed_trades:
            return 0.0, {'message': '无交易数据'}
        
        wins = [t for t in closed_trades if t.get('pnl', 0) > 0]
        losses = [t for t in closed_trades if t.get('pnl', 0) <= 0]
        
        win_count = len(wins)
        loss_count = len(losses)
        total_count = len(closed_trades)
        
        win_rate = win_count / total_count if total_count > 0 else 0.0
        
        avg_win = sum(t['pnl'] for t in wins) / win_count if win_count > 0 else 0.0
        avg_loss = sum(t['pnl'] for t in losses) / loss_count if loss_count > 0 else 0.0
        
        # 期望值公式：E = (Win% × Avg Win) - (Loss% × |Avg Loss|)
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))
        
        # 盈亏比
        profit_factor = abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses else float('inf')
        
        stats = {
            'expectancy': expectancy,
            'expectancy_pct': expectancy * 100,
            'win_rate': win_rate,
            'total_trades': total_count,
            'wins': win_count,
            'losses': loss_count,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
        }
        
        return expectancy, stats
    
    def should_continue_trading(self) -> Tuple[bool, str]:
        """
        判断是否应该继续交易（基于期望值）
        
        Returns:
            (should_continue, reason)
        """
        expectancy, stats = self.calculate_expectancy(window=self.config.EXPECTANCY_WINDOW)
        
        # 检查1：期望值过低
        if stats['total_trades'] >= 10 and expectancy < self.config.MIN_EXPECTANCY_PCT:
            return False, f"期望值过低 ({expectancy:.2%} < {self.config.MIN_EXPECTANCY_PCT:.2%})"
        
        # 检查2：盈亏比过低
        if stats['total_trades'] >= 10 and stats['profit_factor'] < self.config.MIN_PROFIT_FACTOR:
            return False, f"盈亏比过低 ({stats['profit_factor']:.2f} < {self.config.MIN_PROFIT_FACTOR:.2f})"
        
        # 检查3：连续亏损
        recent_trades = [t for t in self.trades if t.get('event') == 'close'][-self.config.CONSECUTIVE_LOSS_LIMIT:]
        if len(recent_trades) >= self.config.CONSECUTIVE_LOSS_LIMIT:
            if all(t.get('pnl', 0) < 0 for t in recent_trades):
                return False, f"连续亏损 {self.config.CONSECUTIVE_LOSS_LIMIT} 次"
        
        return True, "OK"
    
    # =========================================================================
    # 模型评分功能（原 ModelScorer）
    # =========================================================================
    
    def score_model(self, model_name: str = "XGBoost") -> ModelScore:
        """
        评分ML模型
        
        评分算法（加权）：
        - PnL得分（50%）：总盈亏 / 交易数
        - 置信度得分（30%）：平均信心度准确性
        - 胜率得分（20%）：胜率
        
        Args:
            model_name: 模型名称
        
        Returns:
            ModelScore: 模型评分
        """
        closed_trades = [t for t in self.trades if t.get('event') == 'close']
        
        if not closed_trades:
            return ModelScore(
                model_name=model_name,
                total_score=0.0,
                pnl_score=0.0,
                confidence_score=0.0,
                win_rate_score=0.0,
                trade_count=0,
                avg_pnl=0.0,
                win_rate=0.0
            )
        
        # 1. PnL得分（50%权重）
        total_pnl = sum(t.get('pnl', 0.0) for t in closed_trades)
        avg_pnl = total_pnl / len(closed_trades)
        pnl_score = min(max(avg_pnl * 10, -100), 100)  # 归一化到 -100~100
        
        # 2. 置信度得分（30%权重）
        confidence_scores = []
        for trade in closed_trades:
            confidence = trade.get('confidence', 0.5)
            is_win = trade.get('pnl', 0) > 0
            # 如果预测正确（高信心度+盈利 或 低信心度+亏损），得分高
            if is_win:
                score = confidence * 100
            else:
                score = (1 - confidence) * 100
            confidence_scores.append(score)
        
        confidence_score = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        # 3. 胜率得分（20%权重）
        wins = sum(1 for t in closed_trades if t.get('pnl', 0) > 0)
        win_rate = wins / len(closed_trades)
        win_rate_score = win_rate * 100
        
        # 加权总分
        total_score = (pnl_score * 0.5) + (confidence_score * 0.3) + (win_rate_score * 0.2)
        
        return ModelScore(
            model_name=model_name,
            total_score=total_score,
            pnl_score=pnl_score,
            confidence_score=confidence_score,
            win_rate_score=win_rate_score,
            trade_count=len(closed_trades),
            avg_pnl=avg_pnl,
            win_rate=win_rate
        )
    
    # =========================================================================
    # 统计与报告功能
    # =========================================================================
    
    def get_statistics(self, use_cache: bool = True) -> TradeStats:
        """
        获取交易统计
        
        Args:
            use_cache: 是否使用缓存
        
        Returns:
            TradeStats: 统计数据
        """
        # 检查缓存
        if use_cache and self._stats_cache and (time.time() - self._cache_timestamp) < self._cache_ttl:
            return self._stats_cache
        
        closed_trades = [t for t in self.trades if t.get('event') == 'close']
        
        if not closed_trades:
            stats = TradeStats(
                total_trades=0, wins=0, losses=0, win_rate=0.0,
                avg_pnl=0.0, total_pnl=0.0, max_win=0.0, max_loss=0.0,
                expectancy=0.0, profit_factor=0.0, sharpe_ratio=0.0
            )
        else:
            wins = [t for t in closed_trades if t.get('pnl', 0) > 0]
            losses = [t for t in closed_trades if t.get('pnl', 0) <= 0]
            
            total_pnl = sum(t.get('pnl', 0.0) for t in closed_trades)
            
            # 夏普比率（简化版：假设无风险利率=0）
            import numpy as np
            pnls = [t.get('pnl', 0.0) for t in closed_trades]
            sharpe = (np.mean(pnls) / np.std(pnls)) if np.std(pnls) > 0 else 0.0
            
            expectancy, _ = self.calculate_expectancy()
            
            stats = TradeStats(
                total_trades=len(closed_trades),
                wins=len(wins),
                losses=len(losses),
                win_rate=len(wins) / len(closed_trades),
                avg_pnl=total_pnl / len(closed_trades),
                total_pnl=total_pnl,
                max_win=max((t.get('pnl', 0.0) for t in wins), default=0.0),
                max_loss=min((t.get('pnl', 0.0) for t in losses), default=0.0),
                expectancy=expectancy,
                profit_factor=abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses else float('inf'),
                sharpe_ratio=sharpe
            )
        
        # 更新缓存
        self._stats_cache = stats
        self._cache_timestamp = time.time()
        
        return stats
    
    def generate_daily_report(self) -> Dict:
        """
        生成每日报告
        
        Returns:
            Dict: 报告数据
        """
        today = datetime.now().date().isoformat()
        
        # 今日交易
        today_trades = [
            t for t in self.trades 
            if t.get('timestamp', '').startswith(today) and t.get('event') == 'close'
        ]
        
        if not today_trades:
            return {
                'date': today,
                'trades': 0,
                'message': '今日无交易'
            }
        
        wins = [t for t in today_trades if t.get('pnl', 0) > 0]
        total_pnl = sum(t.get('pnl', 0.0) for t in today_trades)
        
        report = {
            'date': today,
            'trades': len(today_trades),
            'wins': len(wins),
            'losses': len(today_trades) - len(wins),
            'win_rate': len(wins) / len(today_trades),
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(today_trades),
            'best_trade': max((t.get('pnl', 0.0) for t in today_trades), default=0.0),
            'worst_trade': min((t.get('pnl', 0.0) for t in today_trades), default=0.0),
        }
        
        return report
    
    # =========================================================================
    # 内部辅助方法
    # =========================================================================
    
    def _load_trades(self):
        """加载交易记录"""
        if os.path.exists(self.trades_file):
            try:
                with open(self.trades_file, 'r', encoding='utf-8') as f:
                    self.trades = json.load(f)
                logger.debug(f"加载 {len(self.trades)} 笔交易记录")
            except Exception as e:
                logger.error(f"加载交易记录失败: {e}")
                self.trades = []
        else:
            self.trades = []
    
    def _save_trades(self):
        """保存交易记录"""
        try:
            os.makedirs(os.path.dirname(self.trades_file), exist_ok=True)
            with open(self.trades_file, 'w', encoding='utf-8') as f:
                json.dump(self.trades, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存交易记录失败: {e}")
    
    def _invalidate_cache(self):
        """使缓存失效"""
        self._stats_cache = None
        self._cache_timestamp = 0.0
