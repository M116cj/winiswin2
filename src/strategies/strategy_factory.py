"""
策略工厂
根据配置创建合适的交易策略
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class StrategyFactory:
    """策略工厂"""
    
    @staticmethod
    def create_strategy(config: Any):
        """
        根据配置创建策略
        
        Args:
            config: 配置对象
            
        Returns:
            策略实例
        """
        strategy_mode = getattr(config, 'STRATEGY_MODE', 'ict')
        
        if strategy_mode == "ict":
            from src.strategies.ict_strategy import ICTStrategy
            logger.info("🎯 使用 ICT 策略")
            return ICTStrategy()
            
        elif strategy_mode == "self_learning":
            from src.strategies.self_learning_trader import SelfLearningTrader
            logger.info("🤖 使用自我学习策略")
            return SelfLearningTrader(config)
            
        elif strategy_mode == "hybrid":
            from src.strategies.hybrid_strategy import HybridStrategy
            logger.info("🔥 使用混合策略 (ICT + ML)")
            return HybridStrategy(config)
            
        else:
            logger.warning(f"未知策略模式: {strategy_mode}, 使用默认ICT策略")
            from src.strategies.ict_strategy import ICTStrategy
            return ICTStrategy()
