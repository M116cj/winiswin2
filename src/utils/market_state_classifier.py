"""
配置驱动市场状态分类器 (v3.13.0 策略19)
职责：基于config.MARKET_STATE_RULES动态分类市场状态

✅ 为什么配置驱动：
1. 硬编码if/elif链难以维护
2. 调整策略需要修改代码
3. 配置驱动→运行时调整（无需重启）
4. 规则即数据（便于A/B测试）

使用示例：
    classifier = MarketStateClassifier()
    state = classifier.classify(adx=30, bb_width_quantile=0.7, volatility=0.02)
    # → "strong_trending"
    
    # 获取风险倍数
    multiplier = classifier.get_risk_multiplier(state)
    # → 1.2x
"""

import logging
from typing import Dict, Optional
import pandas as pd

from src.core.unified_config_manager import config_manager as config

logger = logging.getLogger(__name__)


class MarketStateClassifier:
    """
    配置驱动的市场状态分类器（v3.13.0）
    
    基于 config.MARKET_STATE_RULES 动态分类市场状态
    """
    
    def __init__(self, rules: Optional[Dict] = None):
        """
        初始化分类器
        
        Args:
            rules: 市场状态规则（None=使用config.MARKET_STATE_RULES）
        """
        self.rules = rules or config.MARKET_STATE_RULES
        
        logger.info(f"✅ 市场状态分类器初始化（{len(self.rules)} 种状态）")
    
    def classify(
        self,
        adx: float,
        bb_width_quantile: float,
        volatility: float
    ) -> str:
        """
        分类市场状态
        
        Args:
            adx: ADX值
            bb_width_quantile: 布林带宽度百分位
            volatility: 波动率
        
        Returns:
            str: 市场状态名称
        """
        # 按优先级检查每种状态
        # 注：优先检查更严格的条件（strong_trending > trending）
        
        for state_name, rule in self.rules.items():
            if self._matches_rule(adx, bb_width_quantile, volatility, rule):
                logger.debug(f"市场状态: {state_name} (ADX={adx:.1f}, BB={bb_width_quantile:.2f}, Vol={volatility:.3f})")
                return state_name
        
        # 默认：trending
        return "trending"
    
    def _matches_rule(
        self,
        adx: float,
        bb_width_quantile: float,
        volatility: float,
        rule: Dict
    ) -> bool:
        """
        检查是否匹配规则
        
        Args:
            adx: ADX值
            bb_width_quantile: 布林带宽度百分位
            volatility: 波动率
            rule: 规则字典
        
        Returns:
            bool: 是否匹配
        """
        # 检查ADX范围
        if 'adx_min' in rule and adx < rule['adx_min']:
            return False
        if 'adx_max' in rule and adx >= rule['adx_max']:
            return False
        
        # 检查BB宽度
        if 'bb_width_quantile' in rule and bb_width_quantile < rule['bb_width_quantile']:
            return False
        
        # 检查波动率范围
        if 'volatility_min' in rule and volatility < rule['volatility_min']:
            return False
        if 'volatility_max' in rule and volatility >= rule['volatility_max']:
            return False
        
        return True
    
    def is_allowed(self, state: str) -> bool:
        """
        检查某状态是否允许交易
        
        Args:
            state: 市场状态
        
        Returns:
            bool: 是否允许交易
        """
        rule = self.rules.get(state, {})
        return rule.get('allowed', True)
    
    def get_risk_multiplier(self, state: str) -> float:
        """
        获取风险倍数
        
        Args:
            state: 市场状态
        
        Returns:
            float: 风险倍数
        """
        rule = self.rules.get(state, {})
        return rule.get('risk_multiplier', 1.0)
    
    def get_description(self, state: str) -> str:
        """
        获取状态描述
        
        Args:
            state: 市场状态
        
        Returns:
            str: 描述
        """
        rule = self.rules.get(state, {})
        return rule.get('description', state)
    
    def classify_from_df(self, df: pd.DataFrame, adx_col: str = 'adx', bb_col: str = 'bb_width_pct', volatility_col: str = 'volatility') -> pd.Series:
        """
        从DataFrame分类市场状态
        
        Args:
            df: K线数据
            adx_col: ADX列名
            bb_col: BB宽度列名
            volatility_col: 波动率列名
        
        Returns:
            pd.Series: 市场状态序列
        """
        states = []
        
        for i in range(len(df)):
            adx = df[adx_col].iloc[i] if adx_col in df.columns else 20.0
            bb_width_quantile = df[bb_col].iloc[i] if bb_col in df.columns else 0.5
            volatility = df[volatility_col].iloc[i] if volatility_col in df.columns else 0.01
            
            state = self.classify(adx, bb_width_quantile, volatility)
            states.append(state)
        
        return pd.Series(states, index=df.index)
    
    def get_all_states(self) -> Dict:
        """获取所有状态信息"""
        return {
            name: {
                'description': rule.get('description', ''),
                'allowed': rule.get('allowed', True),
                'risk_multiplier': rule.get('risk_multiplier', 1.0)
            }
            for name, rule in self.rules.items()
        }


# 全局分类器实例（单例）
_global_classifier: Optional[MarketStateClassifier] = None


def get_global_classifier() -> MarketStateClassifier:
    """获取全局市场状态分类器（单例）"""
    global _global_classifier
    if _global_classifier is None:
        _global_classifier = MarketStateClassifier()
    return _global_classifier
