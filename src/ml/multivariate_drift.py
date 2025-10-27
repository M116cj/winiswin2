"""
多变量漂移检测
职责：使用MMD（Maximum Mean Discrepancy）检测高维特征的联合分布漂移
优点：比逐特征KS检验更准确，能捕捉特征间相关性变化
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
import logging
from sklearn.decomposition import PCA

logger = logging.getLogger(__name__)


class MultivariateDriftDetector:
    """多变量漂移检测器（PCA + MMD）"""
    
    def __init__(self, n_components: int = 10, mmd_threshold: float = 0.1):
        """
        初始化检测器
        
        Args:
            n_components: PCA降维后的维度
            mmd_threshold: MMD阈值（>threshold则认为漂移）
        """
        self.n_components = n_components
        self.mmd_threshold = mmd_threshold
        self.pca = None
        self.baseline_pca_data = None
    
    def fit_baseline(self, X: pd.DataFrame):
        """
        拟合基准数据（训练PCA并保存基准）
        
        Args:
            X: 基准特征数据
        """
        # PCA降维
        self.pca = PCA(n_components=min(self.n_components, X.shape[1]))
        baseline_transformed = self.pca.fit_transform(X)
        
        self.baseline_pca_data = baseline_transformed
        
        logger.info(
            f"📊 多变量漂移检测基准建立：PCA降维 {X.shape[1]} → {self.pca.n_components_} 维, "
            f"解释方差 {self.pca.explained_variance_ratio_.sum():.2%}"
        )
    
    def detect_drift(self, X_current: pd.DataFrame) -> Dict:
        """
        检测多变量漂移（使用MMD）
        
        Args:
            X_current: 当前特征数据
        
        Returns:
            Dict: 漂移检测报告
        """
        if self.pca is None or self.baseline_pca_data is None:
            logger.warning("基准数据未建立，无法检测漂移")
            return {
                'has_drift': False,
                'reason': '基准数据未建立'
            }
        
        # PCA变换当前数据
        current_transformed = self.pca.transform(X_current)
        
        # 计算MMD
        mmd_value = self._compute_mmd(
            self.baseline_pca_data,
            current_transformed
        )
        
        # 判断是否漂移
        has_drift = mmd_value > self.mmd_threshold
        
        report = {
            'has_drift': has_drift,
            'mmd_value': float(mmd_value),
            'mmd_threshold': self.mmd_threshold,
            'pca_dims': self.pca.n_components_,
            'explained_variance': float(self.pca.explained_variance_ratio_.sum())
        }
        
        if has_drift:
            logger.warning(
                f"⚠️ 检测到多变量漂移！MMD={mmd_value:.4f} > 阈值{self.mmd_threshold}"
            )
        else:
            logger.info(f"✅ 多变量分布稳定：MMD={mmd_value:.4f}")
        
        return report
    
    def _compute_mmd(
        self,
        X: np.ndarray,
        Y: np.ndarray,
        kernel: str = 'rbf',
        gamma: Optional[float] = None
    ) -> float:
        """
        计算Maximum Mean Discrepancy
        
        MMD衡量两个分布之间的距离
        
        Args:
            X: 基准数据 (n_samples_X, n_features)
            Y: 当前数据 (n_samples_Y, n_features)
            kernel: 核函数类型 ('rbf' or 'linear')
            gamma: RBF核的带宽参数
        
        Returns:
            float: MMD值
        """
        if kernel == 'rbf':
            # RBF核（高斯核）
            if gamma is None:
                # 自动计算gamma（中位数启发式）
                gamma = 1.0 / X.shape[1]
            
            # K(X, X)
            K_XX = self._rbf_kernel(X, X, gamma)
            # K(Y, Y)
            K_YY = self._rbf_kernel(Y, Y, gamma)
            # K(X, Y)
            K_XY = self._rbf_kernel(X, Y, gamma)
            
        elif kernel == 'linear':
            # 线性核
            K_XX = np.dot(X, X.T)
            K_YY = np.dot(Y, Y.T)
            K_XY = np.dot(X, Y.T)
        
        else:
            raise ValueError(f"不支持的核函数：{kernel}")
        
        # MMD^2 = E[K(X,X)] + E[K(Y,Y)] - 2*E[K(X,Y)]
        m = X.shape[0]
        n = Y.shape[0]
        
        mmd_squared = (
            K_XX.sum() / (m * m) +
            K_YY.sum() / (n * n) -
            2 * K_XY.sum() / (m * n)
        )
        
        # 返回MMD（取平方根）
        mmd = np.sqrt(max(mmd_squared, 0))  # max确保非负
        
        return mmd
    
    def _rbf_kernel(self, X: np.ndarray, Y: np.ndarray, gamma: float) -> np.ndarray:
        """
        RBF（高斯）核函数
        
        K(x, y) = exp(-gamma * ||x - y||^2)
        
        Args:
            X: 数据矩阵1 (n_samples_X, n_features)
            Y: 数据矩阵2 (n_samples_Y, n_features)
            gamma: 带宽参数
        
        Returns:
            np.ndarray: 核矩阵 (n_samples_X, n_samples_Y)
        """
        # 计算欧氏距离的平方
        # ||x - y||^2 = ||x||^2 + ||y||^2 - 2*<x, y>
        X_norm_sq = np.sum(X ** 2, axis=1, keepdims=True)
        Y_norm_sq = np.sum(Y ** 2, axis=1, keepdims=True)
        
        distances_sq = X_norm_sq + Y_norm_sq.T - 2 * np.dot(X, Y.T)
        
        # RBF核
        K = np.exp(-gamma * distances_sq)
        
        return K
    
    def get_principal_components_drift(self, X_current: pd.DataFrame) -> Dict:
        """
        分析各主成分的漂移情况
        
        Args:
            X_current: 当前特征数据
        
        Returns:
            Dict: 各主成分漂移分析
        """
        if self.pca is None or self.baseline_pca_data is None:
            return {}
        
        current_transformed = self.pca.transform(X_current)
        
        # 计算各主成分的均值和标准差变化
        pc_drift = {}
        for i in range(self.pca.n_components_):
            baseline_mean = self.baseline_pca_data[:, i].mean()
            baseline_std = self.baseline_pca_data[:, i].std()
            
            current_mean = current_transformed[:, i].mean()
            current_std = current_transformed[:, i].std()
            
            # 均值漂移（标准化）
            mean_shift = abs(current_mean - baseline_mean) / (baseline_std + 1e-6)
            
            # 标准差变化率
            std_change = abs(current_std - baseline_std) / (baseline_std + 1e-6)
            
            pc_drift[f'PC{i+1}'] = {
                'mean_shift': float(mean_shift),
                'std_change': float(std_change),
                'explained_variance': float(self.pca.explained_variance_ratio_[i])
            }
        
        return pc_drift
