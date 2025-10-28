"""
混合策略
结合ICT策略和ML过滤，实现协同增强
"""

import logging
from typing import Optional, Dict
import pandas as pd

from src.strategies.ict_strategy import ICTStrategy
from src.ml.predictor import MLPredictor

logger = logging.getLogger(__name__)


class HybridStrategy:
    """混合策略：ICT + ML过滤"""
    
    def __init__(self, config):
        self.config = config
        # 🔧 修复：ICTStrategy 不接受参数，直接使用 Config 类
        self.ict_strategy = ICTStrategy()
        self.ml_predictor = MLPredictor(config)
        
        self.ml_min_confidence = 0.5
        
        logger.info("✅ 混合策略初始化完成 (ICT + ML过滤)")
    
    def analyze(self, symbol: str, multi_tf_data: Dict[str, pd.DataFrame]) -> Optional[Dict]:
        """
        混合分析：ICT生成信号，ML过滤质量
        
        Args:
            symbol: 交易对符号
            multi_tf_data: 多时间框架数据
            
        Returns:
            过滤后的交易信号或None
        """
        ict_signal = self.ict_strategy.analyze(symbol, multi_tf_data)
        
        if ict_signal is None:
            return None
        
        if self.ml_predictor and self.ml_predictor.is_ready:
            ml_prediction = self.ml_predictor.predict(ict_signal)
            
            if ml_prediction is None:
                return ict_signal
            
            ml_confidence = ml_prediction.get('ml_confidence', 0.5)
            
            if ml_confidence < self.ml_min_confidence:
                logger.debug(
                    f"ML过滤拒绝信号 {symbol}: ML信心度 {ml_confidence:.2%} < {self.ml_min_confidence:.2%}"
                )
                return None
            
            original_confidence = ict_signal['confidence']
            calibrated_confidence = self.ml_predictor.calibrate_confidence(
                original_confidence, ml_prediction
            )
            
            ict_signal['confidence'] = calibrated_confidence
            ict_signal['ml_prediction'] = ml_prediction
            
            logger.debug(
                f"ML增强信号 {symbol}: {original_confidence:.2%} → {calibrated_confidence:.2%}"
            )
        
        return ict_signal
