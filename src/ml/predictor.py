"""
ML 預測器 - 兼容層（v3.17+）
原始 ML 功能已整合到 SelfLearningTrader
此文件僅保留向後兼容接口
"""

import logging

logger = logging.getLogger(__name__)


class MLPredictor:
    """ML 預測器兼容層"""
    
    def __init__(self, trade_recorder=None):
        """初始化 ML 預測器（兼容層）"""
        self.trade_recorder = trade_recorder
        logger.info("✅ ML 預測器（兼容層）已初始化")
    
    def initialize(self) -> bool:
        """初始化（兼容層）"""
        return True
    
    def get_recent_win_rate(self, window: int = 30) -> dict:
        """獲取最近勝率"""
        if self.trade_recorder:
            try:
                stats = self.trade_recorder.get_statistics(window_size=window)
                return {
                    'win_rate': stats.get('win_rate', 0.5),
                    'total_trades': stats.get('total_trades', 0)
                }
            except:
                pass
        
        return {'win_rate': 0.5, 'total_trades': 0}
    
    def predict_rebound(self, *args, **kwargs):
        """預測反彈（兼容層）"""
        return {'should_hold': False, 'confidence': 0}
