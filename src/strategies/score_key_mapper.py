"""
分数键名映射器 - 统一处理不同模式的键名

解决 KeyError 'trend_alignment' 问题：
- 传统模式和纯ICT模式使用不同的 sub_scores 键名
- 提供统一的访问接口，自动适配不同模式
"""
from src.utils.logger_factory import get_logger
from typing import Dict

logger = get_logger(__name__)


class ScoreKeyMapper:
    """分数键名映射器 - 统一处理不同模式的键名"""
    
    # 传统模式键名
    TRADITIONAL_KEYS = {
        'trend_alignment': 'timeframe_alignment',  # 修正打字错误
        'market_structure': 'market_structure',
        'order_block': 'order_block',
        'momentum': 'momentum',
        'volatility': 'volatility'
    }
    
    # 纯ICT模式键名
    PURE_ICT_KEYS = {
        'trend_alignment': 'timeframe_ict',  # 映射到ICT的对应键
        'market_structure': 'market_structure_ict',
        'order_block': 'order_block_ict',
        'momentum': 'liquidity_ict',  # 近似映射
        'volatility': 'institutional_ict'  # 近似映射
    }
    
    @classmethod
    def get_unified_score(cls, sub_scores: Dict, use_pure_ict: bool, key: str) -> float:
        """
        安全获取统一的分数值
        
        Args:
            sub_scores: 子分数字典
            use_pure_ict: 是否使用纯ICT模式
            key: 统一的键名
            
        Returns:
            分数值（如果不存在返回0.0）
        """
        key_map = cls.PURE_ICT_KEYS if use_pure_ict else cls.TRADITIONAL_KEYS
        actual_key = key_map.get(key)
        
        if not actual_key:
            logger.warning(f"⚠️ 未知的键名映射: {key}")
            return 0.0
        
        # 安全获取值
        value = sub_scores.get(actual_key, 0.0)
        logger.debug(f"🔍 键名映射: {key} -> {actual_key} = {value}")
        return value
    
    @classmethod
    def validate_sub_scores(cls, sub_scores: Dict, use_pure_ict: bool) -> bool:
        """
        验证 sub_scores 的完整性
        
        Args:
            sub_scores: 子分数字典
            use_pure_ict: 是否使用纯ICT模式
            
        Returns:
            是否验证通过
        """
        required_keys = ['trend_alignment', 'market_structure', 'order_block', 'momentum', 'volatility']
        key_map = cls.PURE_ICT_KEYS if use_pure_ict else cls.TRADITIONAL_KEYS
        
        for req_key in required_keys:
            actual_key = key_map.get(req_key)
            if actual_key not in sub_scores:
                logger.warning(f"⚠️ 缺失必要键: {req_key} -> {actual_key}")
                return False
        
        return True
