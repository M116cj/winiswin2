"""
不确定性量化器
职责：使用Bootstrap生成预测区间，评估预测不确定性
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)


class UncertaintyQuantifier:
    """不确定性量化器（Bootstrap方法）"""
    
    def __init__(self, n_bootstrap: int = 50, confidence_level: float = 0.95):
        """
        初始化量化器
        
        Args:
            n_bootstrap: Bootstrap采样次数
            confidence_level: 置信水平（如0.95表示95%置信区间）
        """
        self.n_bootstrap = n_bootstrap
        self.confidence_level = confidence_level
        self.bootstrap_models = []
    
    def fit_bootstrap_models(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        base_model,
        sample_ratio: float = 0.8
    ):
        """
        训练Bootstrap集成模型
        
        Args:
            X: 特征数据
            y: 目标变量
            base_model: 基础模型（XGBoost）
            sample_ratio: 每次采样比例
        """
        self.bootstrap_models = []
        n_samples = len(X)
        sample_size = int(n_samples * sample_ratio)
        
        logger.info(f"🔄 开始训练{self.n_bootstrap}个Bootstrap模型...")
        
        for i in range(self.n_bootstrap):
            # Bootstrap采样（有放回）
            indices = np.random.choice(n_samples, size=sample_size, replace=True)
            X_boot = X.iloc[indices]
            y_boot = y.iloc[indices]
            
            # 训练模型
            model = base_model.__class__(**base_model.get_params())
            model.fit(X_boot, y_boot, verbose=False)
            
            self.bootstrap_models.append(model)
        
        logger.info(f"✅ Bootstrap模型训练完成：{len(self.bootstrap_models)}个模型")
    
    def predict_with_uncertainty(
        self,
        X: pd.DataFrame
    ) -> Dict:
        """
        带不确定性的预测
        
        Args:
            X: 特征数据
        
        Returns:
            Dict: 预测结果（包含区间）
        """
        if not self.bootstrap_models:
            logger.warning("Bootstrap模型未训练")
            return {}
        
        # 收集所有模型的预测
        predictions = []
        for model in self.bootstrap_models:
            try:
                pred = model.predict_proba(X)[:, 1]  # 假设二分类
            except AttributeError:
                pred = model.predict(X)  # 回归
            predictions.append(pred)
        
        predictions = np.array(predictions)  # shape: (n_bootstrap, n_samples)
        
        # 计算统计量
        mean_pred = np.mean(predictions, axis=0)
        std_pred = np.std(predictions, axis=0)
        
        # 计算置信区间
        alpha = 1 - self.confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100
        
        lower_bound = np.percentile(predictions, lower_percentile, axis=0)
        upper_bound = np.percentile(predictions, upper_percentile, axis=0)
        
        # 计算不确定性分数（标准差 / 均值）
        uncertainty_score = std_pred / (np.abs(mean_pred) + 1e-6)
        
        return {
            'mean_prediction': mean_pred,
            'std_prediction': std_pred,
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'uncertainty_score': uncertainty_score,
            'confidence_level': self.confidence_level
        }
    
    def filter_high_confidence_predictions(
        self,
        predictions: Dict,
        uncertainty_threshold: float = 0.2
    ) -> np.ndarray:
        """
        过滤高信心预测（低不确定性）
        
        Args:
            predictions: 预测结果
            uncertainty_threshold: 不确定性阈值（<threshold则认为高信心）
        
        Returns:
            np.ndarray: 高信心样本的布尔掩码
        """
        uncertainty_scores = predictions.get('uncertainty_score', np.array([]))
        
        if len(uncertainty_scores) == 0:
            return np.array([])
        
        # 低不确定性 = 高信心
        high_confidence_mask = uncertainty_scores < uncertainty_threshold
        
        high_conf_count = high_confidence_mask.sum()
        total_count = len(uncertainty_scores)
        
        logger.info(
            f"📊 高信心过滤：{high_conf_count}/{total_count} "
            f"({high_conf_count/total_count:.1%}) 样本通过"
        )
        
        return high_confidence_mask
    
    def get_prediction_interval_width(self, predictions: Dict) -> np.ndarray:
        """
        获取预测区间宽度
        
        区间越窄，预测越可靠
        
        Args:
            predictions: 预测结果
        
        Returns:
            np.ndarray: 区间宽度
        """
        lower = predictions.get('lower_bound', np.array([]))
        upper = predictions.get('upper_bound', np.array([]))
        
        if len(lower) == 0 or len(upper) == 0:
            return np.array([])
        
        interval_width = upper - lower
        
        return interval_width
