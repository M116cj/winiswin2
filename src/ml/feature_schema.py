"""
统一特征Schema v4.0 - 12个ICT/SMC核心特征
确保训练和预测使用完全相同的特征集

v4.0 特征构成：
- 8个基础特征：market_structure, order_blocks_count, institutional_candle, 
                liquidity_grab, order_flow, fvg_count, trend_alignment_enhanced, swing_high_distance
- 4个合成特征：structure_integrity, institutional_participation, 
                timeframe_convergence, liquidity_context

总特征数：12个（纯ICT/SMC）
"""

from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

CANONICAL_FEATURE_NAMES: List[str] = [
    'market_structure',           
    'order_blocks_count',         
    'institutional_candle',       
    'liquidity_grab',             
    'order_flow',                 
    'fvg_count',                  
    'trend_alignment_enhanced',   
    'swing_high_distance',        
    'structure_integrity',        
    'institutional_participation', 
    'timeframe_convergence',      
    'liquidity_context'           
]

FEATURE_DEFAULTS: Dict[str, float] = {
    'market_structure': 0.0,
    'order_blocks_count': 0.0,
    'institutional_candle': 0.0,
    'liquidity_grab': 0.0,
    'order_flow': 0.0,
    'fvg_count': 0.0,
    'trend_alignment_enhanced': 0.0,
    'swing_high_distance': 0.0,
    'structure_integrity': 0.5,
    'institutional_participation': 0.0,
    'timeframe_convergence': 0.5,
    'liquidity_context': 0.5
}


def validate_feature_vector(features: Dict) -> bool:
    """
    验证特征向量是否完整
    
    Args:
        features: 特征字典
        
    Returns:
        True if all required features are present, False otherwise
    """
    missing_features = [f for f in CANONICAL_FEATURE_NAMES if f not in features]
    
    if missing_features:
        logger.warning(f"⚠️ 缺失特征: {missing_features}")
        return False
    
    return True


def extract_canonical_features(features: Dict) -> Dict:
    """
    从特征字典中提取12个标准特征，忽略其他特征
    
    Args:
        features: 包含所有特征的字典（可能>12个）
        
    Returns:
        只包含12个标准特征的字典
    """
    canonical = {}
    
    for feature_name in CANONICAL_FEATURE_NAMES:
        canonical[feature_name] = features.get(feature_name, FEATURE_DEFAULTS[feature_name])
    
    return canonical


def features_to_vector(features: Dict) -> List[float]:
    """
    将特征字典转换为固定顺序的向量（用于ML模型）
    
    Args:
        features: 特征字典
        
    Returns:
        12维特征向量
    """
    return [features.get(f, FEATURE_DEFAULTS[f]) for f in CANONICAL_FEATURE_NAMES]


def vector_to_features(vector: List[float]) -> Dict:
    """
    将特征向量转换为字典
    
    Args:
        vector: 12维特征向量
        
    Returns:
        特征字典
    """
    if len(vector) != len(CANONICAL_FEATURE_NAMES):
        raise ValueError(
            f"特征向量长度不匹配: 期望{len(CANONICAL_FEATURE_NAMES)}，实际{len(vector)}"
        )
    
    return dict(zip(CANONICAL_FEATURE_NAMES, vector))


logger.info("=" * 60)
logger.info("✅ 统一特征Schema已加载 v4.0")
logger.info(f"   📊 标准特征数量: {len(CANONICAL_FEATURE_NAMES)}")
logger.info(f"   🎯 特征: {', '.join(CANONICAL_FEATURE_NAMES[:4])}...")
logger.info("=" * 60)
