"""
v3.17+ 模型評級引擎
100 分制評分系統，6 大維度
"""

from src.utils.logger_factory import get_logger
from typing import Dict, List, Any
from datetime import datetime, timedelta
import numpy as np

logger = get_logger(__name__)


class ModelRatingEngine:
    """
    模型評級引擎（v3.17+）
    
    評分公式：
    - R:R 比率 (25%)
    - 勝率 (20%)
    - 期望值 EV (20%)
    - 最大回撤 MDD (15%)
    - Sharpe 比率 (10%)
    - 交易頻率 (10%)
    
    嚴懲：每筆 100% 虧損扣 15 分
    """
    
    def __init__(self, config_profile):
        """
        初始化評級引擎
        
        Args:
            config_profile: config manager instance
        """
        self.config = config_profile
        
        # 權重配置
        self.weights = {
            'rr_ratio': self.config.rating_rr_weight,
            'win_rate': self.config.rating_winrate_weight,
            'expected_value': self.config.rating_ev_weight,
            'max_drawdown': self.config.rating_mdd_weight,
            'sharpe_ratio': self.config.rating_sharpe_weight,
            'trade_frequency': self.config.rating_frequency_weight,
        }
        
        logger.info("✅ 模型評級引擎初始化完成（v3.17+）")
        logger.info(f"   📊 評分維度: 6 大維度 (總權重: {sum(self.weights.values()):.0%})")
        logger.info(f"   🚨 100% 虧損懲罰: -{self.config.rating_loss_penalty} 分/筆")
    
    def calculate_rating(
        self,
        trades: List[Dict[str, Any]],
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        計算模型評分
        
        Args:
            trades: 交易記錄列表
            period_days: 評分週期（天）
            
        Returns:
            評分結果字典
        """
        if not trades:
            return self._get_empty_rating()
        
        # 過濾指定期間的交易
        cutoff_date = datetime.now() - timedelta(days=period_days)
        period_trades = [
            t for t in trades
            if datetime.fromisoformat(str(t.get('timestamp', cutoff_date))) >= cutoff_date
        ]
        
        if not period_trades:
            return self._get_empty_rating()
        
        # 計算各維度分數
        rr_score = self._calculate_rr_score(period_trades)
        win_rate_score = self._calculate_win_rate_score(period_trades)
        ev_score = self._calculate_ev_score(period_trades)
        mdd_score = self._calculate_mdd_score(period_trades)
        sharpe_score = self._calculate_sharpe_score(period_trades)
        freq_score = self._calculate_frequency_score(period_trades, period_days)
        
        # 加權總分
        raw_score = (
            rr_score * self.weights['rr_ratio'] +
            win_rate_score * self.weights['win_rate'] +
            ev_score * self.weights['expected_value'] +
            mdd_score * self.weights['max_drawdown'] +
            sharpe_score * self.weights['sharpe_ratio'] +
            freq_score * self.weights['trade_frequency']
        ) * 100
        
        # 100% 虧損懲罰
        total_100_loss = self._count_100_percent_losses(period_trades)
        loss_penalty = total_100_loss * self.config.rating_loss_penalty
        
        # 最終分數（0-100）
        final_score = max(0, min(100, raw_score - loss_penalty))
        
        # 評級等級
        grade = self._get_grade(final_score)
        
        return {
            'final_score': round(final_score, 2),
            'grade': grade,
            'raw_score': round(raw_score, 2),
            'loss_penalty': round(loss_penalty, 2),
            'total_100_losses': total_100_loss,
            'component_scores': {
                'rr_ratio': round(rr_score * 100, 2),
                'win_rate': round(win_rate_score * 100, 2),
                'expected_value': round(ev_score * 100, 2),
                'max_drawdown': round(mdd_score * 100, 2),
                'sharpe_ratio': round(sharpe_score * 100, 2),
                'trade_frequency': round(freq_score * 100, 2),
            },
            'total_trades': len(period_trades),
            'period_days': period_days,
            'timestamp': datetime.now().isoformat(),
        }
    
    def _calculate_rr_score(self, trades: List[Dict]) -> float:
        """計算 R:R 比率分數（0-1）"""
        rr_ratios = []
        for t in trades:
            risk = t.get('risk_amount', 0)
            reward = t.get('reward_amount', 0)
            if risk > 0:
                rr_ratios.append(reward / risk)
        
        if not rr_ratios:
            return 0.0
        
        avg_rr = np.mean(rr_ratios)
        # 目標 R:R = 1.5，超過加分，低於扣分
        score = min(1.0, avg_rr / 1.5)
        return max(0.0, score)
    
    def _calculate_win_rate_score(self, trades: List[Dict]) -> float:
        """計算勝率分數（0-1）"""
        if not trades:
            return 0.0
        
        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        win_rate = wins / len(trades)
        
        # 目標勝率 = 55%，超過加分
        score = min(1.0, win_rate / 0.55)
        return max(0.0, score)
    
    def _calculate_ev_score(self, trades: List[Dict]) -> float:
        """計算期望值分數（0-1）"""
        if not trades:
            return 0.0
        
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        avg_pnl = total_pnl / len(trades)
        
        # 期望值 > 0 即可得分，越高越好
        if avg_pnl <= 0:
            return 0.0
        
        # 歸一化：$10/筆 = 滿分
        score = min(1.0, avg_pnl / 10.0)
        return max(0.0, score)
    
    def _calculate_mdd_score(self, trades: List[Dict]) -> float:
        """計算最大回撤分數（0-1）"""
        if not trades:
            return 1.0
        
        # 計算累積 PnL 曲線
        cumulative_pnl = np.cumsum([t.get('pnl', 0) for t in trades])
        
        # 計算最大回撤
        peak = np.maximum.accumulate(cumulative_pnl)
        drawdown = peak - cumulative_pnl
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
        
        # 回撤越小越好，目標 MDD < $100
        if max_drawdown <= 0:
            return 1.0
        
        score = 1.0 - min(1.0, max_drawdown / 100.0)
        return max(0.0, score)
    
    def _calculate_sharpe_score(self, trades: List[Dict]) -> float:
        """計算 Sharpe 比率分數（0-1）"""
        if not trades or len(trades) < 2:
            return 0.0
        
        pnls = [t.get('pnl', 0) for t in trades]
        mean_pnl = np.mean(pnls)
        std_pnl = np.std(pnls)
        
        if std_pnl == 0:
            return 0.0 if mean_pnl <= 0 else 1.0
        
        sharpe = mean_pnl / std_pnl
        
        # Sharpe > 1.0 = 優秀
        score = min(1.0, sharpe / 1.0)
        return max(0.0, score)
    
    def _calculate_frequency_score(self, trades: List[Dict], period_days: int) -> float:
        """計算交易頻率分數（0-1）"""
        if period_days <= 0:
            return 0.0
        
        trades_per_day = len(trades) / period_days
        
        # 目標頻率：1-5 筆/天
        if trades_per_day < 1:
            score = trades_per_day / 1.0
        elif trades_per_day <= 5:
            score = 1.0
        else:
            # 過度交易扣分
            score = max(0.0, 1.0 - (trades_per_day - 5) / 10.0)
        
        return score
    
    def _count_100_percent_losses(self, trades: List[Dict]) -> int:
        """統計 100% 虧損的交易數量"""
        count = 0
        for t in trades:
            risk = t.get('risk_amount', 0)
            pnl = t.get('pnl', 0)
            if risk > 0 and pnl <= -risk * 0.99:
                count += 1
        return count
    
    def _get_grade(self, score: float) -> str:
        """根據分數返回等級"""
        if score >= 90:
            return "S"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        else:
            return "C"
    
    def _get_empty_rating(self) -> Dict[str, Any]:
        """返回空評分（無數據）"""
        return {
            'final_score': 0.0,
            'grade': "N/A",
            'raw_score': 0.0,
            'loss_penalty': 0.0,
            'total_100_losses': 0,
            'component_scores': {k: 0.0 for k in self.weights.keys()},
            'total_trades': 0,
            'period_days': 0,
            'timestamp': datetime.now().isoformat(),
        }
    
    def get_recommendation(self, grade: str) -> str:
        """根據等級返回建議"""
        recommendations = {
            "S": "🎯 模型表現優異，建議加倉",
            "A": "✅ 模型表現良好，維持當前策略",
            "B": "⚠️ 模型表現一般，建議觀察",
            "C": "🚨 模型表現不佳，建議降低至純規則模式",
            "N/A": "📊 數據不足，無法評級",
        }
        return recommendations.get(grade, "")
