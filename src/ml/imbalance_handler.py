"""
样本不平衡处理器
职责：处理类别不平衡、生成混淆矩阵、分方向评估
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import logging
from sklearn.metrics import confusion_matrix, classification_report
from collections import Counter

logger = logging.getLogger(__name__)


class ImbalanceHandler:
    """样本不平衡处理器"""
    
    def __init__(self):
        """初始化处理器"""
        self.balance_threshold = 0.3  # 最小类别占比阈值
    
    def analyze_class_balance(self, y: pd.Series, X: Optional[pd.DataFrame] = None) -> Dict:
        """
        分析类别平衡情况
        
        Args:
            y: 目标变量
            X: 特征数据（可选，用于分析方向平衡）
        
        Returns:
            Dict: 平衡分析报告
        """
        # 总体类别分布
        class_counts = y.value_counts().to_dict()
        total_samples = len(y)
        
        class_distribution = {}
        for cls, count in class_counts.items():
            class_distribution[f'class_{cls}'] = {
                'count': count,
                'percentage': count / total_samples * 100
            }
        
        # 计算不平衡比率
        if len(class_counts) == 2:
            minority_count = min(class_counts.values())
            majority_count = max(class_counts.values())
            imbalance_ratio = majority_count / minority_count if minority_count > 0 else float('inf')
        else:
            imbalance_ratio = 1.0
        
        report = {
            'total_samples': total_samples,
            'class_distribution': class_distribution,
            'imbalance_ratio': imbalance_ratio,
            'is_balanced': imbalance_ratio < 2.0,  # 2:1以内认为平衡
            'needs_balancing': imbalance_ratio >= 2.0
        }
        
        # 如果提供了特征数据，分析方向平衡
        if X is not None and 'direction_encoded' in X.columns:
            direction_balance = self._analyze_direction_balance(X, y)
            report['direction_balance'] = direction_balance
        
        logger.info(
            f"📊 类别平衡分析：不平衡比率 {imbalance_ratio:.2f}, "
            f"分布 {class_distribution}"
        )
        
        return report
    
    def _analyze_direction_balance(self, X: pd.DataFrame, y: pd.Series) -> Dict:
        """
        分析做多/做空方向的平衡性
        
        Args:
            X: 特征数据
            y: 目标变量
        
        Returns:
            Dict: 方向平衡报告
        """
        df = pd.DataFrame({'direction': X['direction_encoded'], 'is_winner': y})
        
        # LONG=1, SHORT=-1
        long_stats = df[df['direction'] == 1]['is_winner']
        short_stats = df[df['direction'] == -1]['is_winner']
        
        report = {
            'long': {
                'total': len(long_stats),
                'winners': long_stats.sum() if len(long_stats) > 0 else 0,
                'win_rate': long_stats.mean() if len(long_stats) > 0 else 0
            },
            'short': {
                'total': len(short_stats),
                'winners': short_stats.sum() if len(short_stats) > 0 else 0,
                'win_rate': short_stats.mean() if len(short_stats) > 0 else 0
            }
        }
        
        # 检查方向偏差
        total = len(df)
        long_pct = len(long_stats) / total if total > 0 else 0
        short_pct = len(short_stats) / total if total > 0 else 0
        
        report['balance'] = {
            'long_percentage': long_pct * 100,
            'short_percentage': short_pct * 100,
            'is_balanced': abs(long_pct - short_pct) < 0.3  # 差异<30%认为平衡
        }
        
        logger.info(
            f"📊 方向平衡：LONG {report['long']['total']}笔({long_pct:.1%}), "
            f"SHORT {report['short']['total']}笔({short_pct:.1%})"
        )
        
        return report
    
    def calculate_sample_weight(
        self,
        y: pd.Series,
        method: str = 'balanced'
    ) -> np.ndarray:
        """
        计算样本权重以处理不平衡
        
        Args:
            y: 目标变量
            method: 权重计算方法 ('balanced', 'sqrt', 'log')
        
        Returns:
            np.ndarray: 样本权重
        """
        class_counts = Counter(y)
        total_samples = len(y)
        
        if method == 'balanced':
            # sklearn的balanced模式
            weights = {}
            for cls, count in class_counts.items():
                weights[cls] = total_samples / (len(class_counts) * count)
        
        elif method == 'sqrt':
            # 平方根缩放（更温和）
            weights = {}
            for cls, count in class_counts.items():
                weights[cls] = np.sqrt(total_samples / count)
        
        elif method == 'log':
            # 对数缩放（最温和）
            weights = {}
            for cls, count in class_counts.items():
                weights[cls] = np.log1p(total_samples / count)
        
        else:
            raise ValueError(f"不支持的权重方法：{method}")
        
        # 归一化权重
        weight_sum = sum(weights.values())
        weights = {cls: w / weight_sum * len(class_counts) for cls, w in weights.items()}
        
        # 生成样本权重数组
        sample_weights = np.array([weights[label] for label in y])
        
        logger.info(f"✅ 计算样本权重（{method}）：类别权重 {weights}")
        
        return sample_weights
    
    def get_scale_pos_weight(self, y: pd.Series) -> float:
        """
        计算XGBoost的scale_pos_weight参数
        
        用于二分类不平衡问题
        scale_pos_weight = num_negative / num_positive
        
        Args:
            y: 目标变量
        
        Returns:
            float: scale_pos_weight值
        """
        class_counts = Counter(y)
        
        if len(class_counts) != 2:
            logger.warning("scale_pos_weight仅适用于二分类问题")
            return 1.0
        
        # 假设1是正类（winner），0是负类（loser）
        num_positive = class_counts.get(1, 1)
        num_negative = class_counts.get(0, 1)
        
        scale_weight = num_negative / num_positive
        
        logger.info(
            f"📊 XGBoost不平衡参数：scale_pos_weight = {scale_weight:.2f} "
            f"(负样本 {num_negative} / 正样本 {num_positive})"
        )
        
        return scale_weight
    
    def generate_confusion_matrix_report(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        X: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        生成详细的混淆矩阵报告
        
        Args:
            y_true: 真实标签
            y_pred: 预测标签
            X: 特征数据（可选，用于分方向评估）
        
        Returns:
            Dict: 混淆矩阵报告
        """
        # 总体混淆矩阵
        cm = confusion_matrix(y_true, y_pred)
        
        # 计算各项指标
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
        
        total = tn + fp + fn + tp
        accuracy = (tp + tn) / total if total > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        report = {
            'confusion_matrix': {
                'true_negative': int(tn),
                'false_positive': int(fp),
                'false_negative': int(fn),
                'true_positive': int(tp)
            },
            'overall_metrics': {
                'accuracy': float(accuracy),
                'precision': float(precision),
                'recall': float(recall),
                'f1_score': float(f1)
            }
        }
        
        # 如果提供了特征数据，分方向评估
        if X is not None and 'direction_encoded' in X.columns:
            direction_metrics = self._evaluate_by_direction(y_true, y_pred, X)
            report['direction_metrics'] = direction_metrics
        
        # 打印混淆矩阵
        logger.info("\n" + "=" * 50)
        logger.info("🎯 混淆矩阵报告")
        logger.info("=" * 50)
        logger.info(f"              预测负类    预测正类")
        logger.info(f"实际负类        {tn:6d}      {fp:6d}")
        logger.info(f"实际正类        {fn:6d}      {tp:6d}")
        logger.info("=" * 50)
        logger.info(f"准确率 (Accuracy):  {accuracy:.4f}")
        logger.info(f"精确率 (Precision): {precision:.4f}")
        logger.info(f"召回率 (Recall):    {recall:.4f}")
        logger.info(f"F1分数 (F1-Score):  {f1:.4f}")
        logger.info("=" * 50)
        
        return report
    
    def _evaluate_by_direction(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        X: pd.DataFrame
    ) -> Dict:
        """
        按做多/做空方向分别评估
        
        Args:
            y_true: 真实标签
            y_pred: 预测标签
            X: 特征数据
        
        Returns:
            Dict: 分方向评估报告
        """
        df = pd.DataFrame({
            'direction': X['direction_encoded'],
            'y_true': y_true,
            'y_pred': y_pred
        })
        
        # LONG方向评估
        long_df = df[df['direction'] == 1]
        long_metrics = self._calculate_metrics(
            long_df['y_true'].values,
            long_df['y_pred'].values
        )
        
        # SHORT方向评估
        short_df = df[df['direction'] == -1]
        short_metrics = self._calculate_metrics(
            short_df['y_true'].values,
            short_df['y_pred'].values
        )
        
        report = {
            'long': {
                'samples': len(long_df),
                **long_metrics
            },
            'short': {
                'samples': len(short_df),
                **short_metrics
            }
        }
        
        logger.info("\n📊 分方向评估：")
        logger.info(f"  LONG:  样本数{report['long']['samples']:4d}, "
                   f"准确率{report['long']['accuracy']:.2%}, "
                   f"F1={report['long']['f1_score']:.4f}")
        logger.info(f"  SHORT: 样本数{report['short']['samples']:4d}, "
                   f"准确率{report['short']['accuracy']:.2%}, "
                   f"F1={report['short']['f1_score']:.4f}")
        
        return report
    
    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        """计算评估指标"""
        if len(y_true) == 0:
            return {
                'accuracy': 0.0,
                'precision': 0.0,
                'recall': 0.0,
                'f1_score': 0.0
            }
        
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        
        if cm.size == 4:
            tn, fp, fn, tp = cm.ravel()
        else:
            tn, fp, fn, tp = 0, 0, 0, 0
        
        total = tn + fp + fn + tp
        accuracy = (tp + tn) / total if total > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1)
        }
