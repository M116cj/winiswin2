"""
策略工廠 (v3.17+)
根據配置創建合適的交易策略
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class StrategyFactory:
    """策略工廠（v3.17+ 僅支持 ICT 策略）"""
    
    @staticmethod
    def create_strategy(config: Any):
        """
        根據配置創建策略
        
        Args:
            config: 配置對象
            
        Returns:
            策略實例
        """
        strategy_mode = getattr(config, 'STRATEGY_MODE', 'ict')
        
        if strategy_mode == "ict":
            from src.strategies.ict_strategy import ICTStrategy
            logger.info("✅ 使用 ICT 策略（五維評分系統）")
            logger.info("   📊 v3.17+ 槓桿引擎已啟用（無限制槓桿）")
            return ICTStrategy()
        
        else:
            logger.warning(f"⚠️ 未知策略模式: {strategy_mode}, 回退到 ICT 策略")
            from src.strategies.ict_strategy import ICTStrategy
            return ICTStrategy()
