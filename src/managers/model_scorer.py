"""
模型预测评级系统 - v3.9.2.8.5

基于每次平仓的盈亏、信心度、胜率综合评估模型表现
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import statistics
from src.utils.logger import logger


class ModelScorer:
    """
    模型预测评级系统
    
    评分维度：
    1. 盈亏表现（50%权重）：实际盈亏是核心指标
    2. 信心度准确性（30%权重）：预测质量
    3. 胜率一致性（20%权重）：模型稳定性
    
    评分范围：0-100分
    """
    
    def __init__(self, history_limit: int = 100):
        """
        初始化评级系统
        
        Args:
            history_limit: 保留的历史评分数量
        """
        self.history_limit = history_limit
        self.score_history: List[Dict] = []
        
        # 权重配置
        self.weights = {
            'pnl': 0.50,        # 盈亏表现权重：50%
            'confidence': 0.30,  # 信心度准确性权重：30%
            'winrate': 0.20     # 胜率一致性权重：20%
        }
        
        logger.info("🎯 模型评级系统初始化完成")
        logger.info(f"   权重配置: 盈亏{self.weights['pnl']:.0%} | "
                   f"信心度{self.weights['confidence']:.0%} | "
                   f"胜率{self.weights['winrate']:.0%}")
    
    def calculate_pnl_score(self, pnl_pct: float) -> float:
        """
        计算盈亏评分（0-100）
        
        评分标准：
        +20%以上: 100分
        +10%到+20%: 80-100分（线性）
        +5%到+10%: 70-80分
        +0%到+5%: 60-70分
        0%到-5%: 40-60分
        -5%到-10%: 20-40分
        -10%以下: 0-20分
        
        Args:
            pnl_pct: 盈亏百分比（如 5.5 表示 +5.5%）
        
        Returns:
            盈亏评分（0-100）
        """
        if pnl_pct >= 20:
            return 100.0
        elif pnl_pct >= 10:
            # 线性插值：10% -> 80分，20% -> 100分
            return 80 + (pnl_pct - 10) * 2
        elif pnl_pct >= 5:
            # 5% -> 70分，10% -> 80分
            return 70 + (pnl_pct - 5) * 2
        elif pnl_pct >= 0:
            # 0% -> 60分，5% -> 70分
            return 60 + pnl_pct * 2
        elif pnl_pct >= -5:
            # -5% -> 40分，0% -> 60分
            return 40 + (pnl_pct + 5) * 4
        elif pnl_pct >= -10:
            # -10% -> 20分，-5% -> 40分
            return 20 + (pnl_pct + 10) * 4
        else:
            # -10%以下 -> 0-20分
            return max(0, 20 + (pnl_pct + 10) * 2)
    
    def calculate_confidence_score(
        self,
        pnl_pct: float,
        confidence: float
    ) -> float:
        """
        计算信心度准确性评分（0-100）
        
        评分逻辑：
        - 盈利 + 高信心度（>60%）：100分（预测准确）
        - 盈利 + 中等信心度（45-60%）：85分
        - 盈利 + 低信心度（<45%）：70分（超预期）
        - 亏损 + 高信心度（>60%）：20分（预测失败）
        - 亏损 + 中等信心度（45-60%）：35分
        - 亏损 + 低信心度（<45%）：50分（符合预期）
        
        Args:
            pnl_pct: 盈亏百分比
            confidence: 信心度（0-100）
        
        Returns:
            信心度评分（0-100）
        """
        is_profit = pnl_pct > 0
        
        if is_profit:
            # 盈利情况：高信心度应该盈利
            if confidence >= 60:
                return 100.0  # 完美预测
            elif confidence >= 45:
                return 85.0   # 良好预测
            else:
                return 70.0   # 超预期（低信心也盈利）
        else:
            # 亏损情况：低信心度亏损是符合预期的
            if confidence >= 60:
                return 20.0   # 预测失败（高信心却亏损）
            elif confidence >= 45:
                return 35.0   # 预测不准
            else:
                return 50.0   # 符合预期（低信心本就不该交易）
    
    def calculate_winrate_score(
        self,
        pnl_pct: float,
        winrate: Optional[float]
    ) -> float:
        """
        计算胜率一致性评分（0-100）
        
        评分逻辑：
        - 盈利 + 高胜率（>50%）：100分（模型稳定）
        - 盈利 + 中等胜率（40-50%）：85分
        - 盈利 + 低胜率（<40%）：70分（运气成分）
        - 亏损 + 高胜率（>50%）：30分（异常亏损）
        - 亏损 + 中等胜率（40-50%）：45分
        - 亏损 + 低胜率（<40%）：60分（符合低胜率预期）
        - 无胜率数据：50分（中性）
        
        Args:
            pnl_pct: 盈亏百分比
            winrate: 胜率（0-100），None表示无数据
        
        Returns:
            胜率评分（0-100）
        """
        if winrate is None:
            return 50.0  # 无数据时给中性分
        
        is_profit = pnl_pct > 0
        
        if is_profit:
            # 盈利情况：高胜率盈利是稳定的表现
            if winrate >= 50:
                return 100.0  # 稳定盈利
            elif winrate >= 40:
                return 85.0   # 良好表现
            else:
                return 70.0   # 运气成分较大
        else:
            # 亏损情况：低胜率亏损是正常的
            if winrate >= 50:
                return 30.0   # 异常亏损（高胜率却亏）
            elif winrate >= 40:
                return 45.0   # 可接受的亏损
            else:
                return 60.0   # 符合低胜率预期
    
    def score_trade(
        self,
        pnl_pct: float,
        confidence: float,
        winrate: Optional[float],
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float
    ) -> Dict:
        """
        评估单次交易并返回综合评分
        
        Args:
            pnl_pct: 盈亏百分比（如 5.5 表示 +5.5%）
            confidence: 开仓时的信心度（0-100）
            winrate: 开仓时的胜率（0-100），可为None
            symbol: 交易对
            direction: 方向（LONG/SHORT）
            entry_price: 入场价格
            exit_price: 出场价格
        
        Returns:
            评分结果字典
        """
        # 计算各维度评分
        pnl_score = self.calculate_pnl_score(pnl_pct)
        confidence_score = self.calculate_confidence_score(pnl_pct, confidence)
        winrate_score = self.calculate_winrate_score(pnl_pct, winrate)
        
        # 加权综合评分
        total_score = (
            pnl_score * self.weights['pnl'] +
            confidence_score * self.weights['confidence'] +
            winrate_score * self.weights['winrate']
        )
        
        # 构建评分记录
        score_record = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'direction': direction,
            'pnl_pct': pnl_pct,
            'confidence': confidence,
            'winrate': winrate,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'scores': {
                'pnl': pnl_score,
                'confidence': confidence_score,
                'winrate': winrate_score,
                'total': total_score
            }
        }
        
        # 添加到历史记录
        self.score_history.append(score_record)
        
        # 限制历史记录数量
        if len(self.score_history) > self.history_limit:
            self.score_history = self.score_history[-self.history_limit:]
        
        # 记录详细日志
        self._log_score(score_record)
        
        return score_record
    
    def _log_score(self, record: Dict):
        """记录评分详情到日志"""
        scores = record['scores']
        pnl_pct = record['pnl_pct']
        symbol = record['symbol']
        direction = record['direction']
        confidence = record['confidence']
        winrate = record['winrate']
        
        # 评分等级
        total_score = scores['total']
        if total_score >= 80:
            grade = "优秀 ⭐⭐⭐"
        elif total_score >= 60:
            grade = "良好 ⭐⭐"
        elif total_score >= 40:
            grade = "及格 ⭐"
        else:
            grade = "不及格 ❌"
        
        logger.info("=" * 60)
        logger.info(f"📊 模型评分 - {symbol} {direction}")
        logger.info(f"   盈亏: {pnl_pct:+.2f}% | 信心度: {confidence:.1f}% | 胜率: {winrate:.1f}%" if winrate else f"   盈亏: {pnl_pct:+.2f}% | 信心度: {confidence:.1f}% | 胜率: N/A")
        logger.info(f"   ├─ 盈亏评分: {scores['pnl']:.1f}/100 (权重{self.weights['pnl']:.0%})")
        logger.info(f"   ├─ 信心度评分: {scores['confidence']:.1f}/100 (权重{self.weights['confidence']:.0%})")
        logger.info(f"   └─ 胜率评分: {scores['winrate']:.1f}/100 (权重{self.weights['winrate']:.0%})")
        logger.info(f"   🎯 综合评分: {total_score:.1f}/100 ({grade})")
        logger.info("=" * 60)
    
    def get_current_score(self) -> float:
        """
        获取当前模型评分（基于最近N笔交易的滚动平均）
        
        Returns:
            当前模型评分（0-100）
        """
        if not self.score_history:
            return 50.0  # 无数据时返回中性分
        
        # 使用最近30笔交易计算滚动平均
        recent_trades = self.score_history[-30:]
        scores = [trade['scores']['total'] for trade in recent_trades]
        
        return statistics.mean(scores)
    
    def get_score_trend(self) -> str:
        """
        获取评分趋势（上升/下降/稳定）
        
        Returns:
            趋势描述
        """
        if len(self.score_history) < 10:
            return "数据不足"
        
        # 比较前半部分和后半部分的平均分
        mid = len(self.score_history) // 2
        first_half = [t['scores']['total'] for t in self.score_history[:mid]]
        second_half = [t['scores']['total'] for t in self.score_history[mid:]]
        
        avg_first = statistics.mean(first_half)
        avg_second = statistics.mean(second_half)
        
        diff = avg_second - avg_first
        
        if diff > 5:
            return "📈 上升"
        elif diff < -5:
            return "📉 下降"
        else:
            return "➡️ 稳定"
    
    def get_statistics(self) -> Dict:
        """
        获取评分统计信息
        
        Returns:
            统计字典
        """
        if not self.score_history:
            return {
                'current_score': 50.0,
                'total_trades': 0,
                'trend': '数据不足',
                'best_score': 0,
                'worst_score': 0,
                'std_dev': 0
            }
        
        scores = [t['scores']['total'] for t in self.score_history]
        
        return {
            'current_score': self.get_current_score(),
            'total_trades': len(self.score_history),
            'trend': self.get_score_trend(),
            'best_score': max(scores),
            'worst_score': min(scores),
            'std_dev': statistics.stdev(scores) if len(scores) > 1 else 0,
            'last_10_avg': statistics.mean(scores[-10:]) if len(scores) >= 10 else statistics.mean(scores)
        }
    
    def log_current_status(self):
        """在日志中显示当前模型评分状态"""
        stats = self.get_statistics()
        
        logger.info("=" * 60)
        logger.info("🎯 模型评分系统状态")
        logger.info(f"   📊 当前模型分数: {stats['current_score']:.1f}/100")
        logger.info(f"   📈 评分趋势: {stats['trend']}")
        logger.info(f"   📝 总交易数: {stats['total_trades']}")
        logger.info(f"   ⭐ 最高分: {stats['best_score']:.1f}")
        logger.info(f"   ❌ 最低分: {stats['worst_score']:.1f}")
        logger.info(f"   📊 近10笔平均: {stats['last_10_avg']:.1f}")
        logger.info("=" * 60)
