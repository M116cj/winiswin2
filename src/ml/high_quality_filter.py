"""
高质量信号过滤器
用于筛选高质量的交易信号作为ML训练数据
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class HighQualitySignalFilter:
    """高质量信号过滤器"""
    
    def __init__(self, config):
        self.config = config
    
    def is_high_quality_signal(self, signal: Dict[str, Any], trade_result: Dict[str, Any]) -> bool:
        """
        判断是否为高质量交易信号
        
        Args:
            signal: 交易信号字典
            trade_result: 交易结果字典
            
        Returns:
            是否为高质量信号
        """
        if not self._check_trade_quality(trade_result):
            return False
            
        if not self._check_signal_quality(signal):
            return False
            
        if not self._check_market_quality(signal):
            return False
            
        return True
    
    def _check_trade_quality(self, trade_result: Dict[str, Any]) -> bool:
        """检查交易结果质量"""
        if trade_result.get('risk_reward_ratio', 0) < 1.5:
            return False
            
        if trade_result.get('pnl_pct', 0) <= 0:
            return False
            
        risk_adjusted = trade_result.get('risk_adjusted_return', 0)
        if risk_adjusted < 0.5:
            return False
            
        hold_time = trade_result.get('hold_duration_hours', 0)
        if hold_time < 0.1 or hold_time > 48:
            return False
            
        return True
    
    def _check_signal_quality(self, signal: Dict[str, Any]) -> bool:
        """检查信号生成质量"""
        if signal.get('confidence_score', 0) < 0.6:
            return False
            
        if signal.get('ml_score', 0) < 0.5:
            return False
            
        market_state = signal.get('market_regime', 'unknown')
        if market_state not in ['trending', 'breakout']:
            return False
            
        reversal_risk = signal.get('reversal_risk_score', 1.0)
        if reversal_risk >= 0.2:
            return False
            
        return True
    
    def _check_market_quality(self, signal: Dict[str, Any]) -> bool:
        """检查市场环境质量"""
        volatility = signal.get('volatility', 0)
        if volatility < 0.005 or volatility > 0.05:
            return False
            
        volume_rank = signal.get('volume_rank_pct', 1.0)
        if volume_rank > 0.3:
            return False
            
        funding_rate = signal.get('funding_rate', 0)
        if abs(funding_rate) > 0.001:
            return False
            
        return True
