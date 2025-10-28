"""
高质量训练数据管道
收集和管理高质量的训练数据
"""

import logging
import numpy as np
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class QualityTrainingPipeline:
    """高质量训练数据管道"""
    
    def __init__(self, high_quality_filter, model):
        self.filter = high_quality_filter
        self.model = model
        self.quality_threshold = 0.8
        
    def collect_quality_training_data(self) -> List[Dict[str, Any]]:
        """收集高质量训练数据"""
        quality_data = []
        
        all_trades = self._get_all_trades()
        
        for trade in all_trades:
            signal = trade['signal']
            result = trade['result']
            
            if self.filter.is_high_quality_signal(signal, result):
                training_sample = self._build_training_sample(signal, result)
                quality_data.append(training_sample)
        
        logger.info(f"收集到 {len(quality_data)} 个高质量训练样本")
        return quality_data
    
    def _build_training_sample(self, signal: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """构建训练样本"""
        return {
            'features': self._extract_features(signal),
            'label': self._create_label(result),
            'weight': self._calculate_quality_weight(signal, result),
            'metadata': {
                'symbol': signal['symbol'],
                'timestamp': signal['timestamp'],
                'quality_score': self._calculate_quality_score(signal, result)
            }
        }
    
    def _calculate_quality_weight(self, signal: Dict[str, Any], result: Dict[str, Any]) -> float:
        """计算品质权重"""
        base_weight = 1.0
        
        rr_weight = min(result.get('risk_reward_ratio', 1.0), 3.0)
        confidence_weight = signal.get('confidence_score', 0.5) * 2
        pnl_weight = max(1.0, abs(result.get('pnl_pct', 0)) / 1.0)
        
        return base_weight * rr_weight * confidence_weight * pnl_weight
    
    def _calculate_quality_score(self, signal: Dict[str, Any], result: Dict[str, Any]) -> float:
        """计算质量评分"""
        trade_score = result.get('risk_reward_ratio', 0) * 0.4
        signal_score = signal.get('confidence_score', 0) * 0.3
        pnl_score = min(abs(result.get('pnl_pct', 0)) / 10.0, 1.0) * 0.3
        
        return trade_score + signal_score + pnl_score
    
    def _extract_features(self, signal: Dict[str, Any]) -> np.ndarray:
        """提取特征"""
        features = []
        
        features.append(signal.get('confidence_score', 0))
        features.append(signal.get('ml_score', 0))
        features.append(signal.get('volatility', 0))
        features.append(signal.get('volume_rank_pct', 0))
        features.append(signal.get('funding_rate', 0))
        
        return np.array(features, dtype=np.float32)
    
    def _create_label(self, result: Dict[str, Any]) -> int:
        """创建标签"""
        pnl = result.get('pnl_pct', 0)
        return 1 if pnl > 0 else 0
    
    def _get_all_trades(self) -> List[Dict[str, Any]]:
        """获取所有交易数据"""
        return []
