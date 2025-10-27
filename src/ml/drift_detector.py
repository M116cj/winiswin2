"""
模型漂移检测器
职责：监控特征分布漂移、触发重训练、滑动窗口管理
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timedelta
from scipy import stats
import json
import os

logger = logging.getLogger(__name__)


class DriftDetector:
    """模型漂移检测器"""
    
    def __init__(self, window_size: int = 1000, drift_threshold: float = 0.05):
        """
        初始化漂移检测器
        
        Args:
            window_size: 滑动窗口大小（保留最近N笔数据）
            drift_threshold: KS检验p值阈值（<threshold则认为漂移）
        """
        self.window_size = window_size
        self.drift_threshold = drift_threshold
        self.baseline_stats = {}  # 基准特征统计
        self.drift_history = []  # 漂移历史记录
        self.stats_path = "data/models/baseline_stats.json"
        
        os.makedirs(os.path.dirname(self.stats_path), exist_ok=True)
        self._load_baseline_stats()
    
    def apply_sliding_window(
        self,
        df: pd.DataFrame,
        window_size: Optional[int] = None
    ) -> pd.DataFrame:
        """
        应用滑动窗口（只保留最近N笔数据）
        
        Args:
            df: 完整数据集
            window_size: 窗口大小（默认使用self.window_size）
        
        Returns:
            pd.DataFrame: 窗口内数据
        """
        if window_size is None:
            window_size = self.window_size
        
        original_size = len(df)
        
        if original_size <= window_size:
            logger.info(f"📊 数据量{original_size} <= 窗口{window_size}，使用全部数据")
            return df
        
        # 按时间排序（假设有timestamp字段）
        if 'timestamp' in df.columns:
            df_sorted = df.sort_values('timestamp', ascending=False)
        elif 'entry_time' in df.columns:
            df_sorted = df.sort_values('entry_time', ascending=False)
        else:
            # 没有时间字段，使用最后N行
            df_sorted = df
        
        # 取最近N笔
        windowed_df = df_sorted.head(window_size).copy()
        
        logger.info(
            f"📊 应用滑动窗口：保留最近{window_size}笔数据，"
            f"丢弃{original_size - window_size}笔旧数据"
        )
        
        return windowed_df
    
    def calculate_sample_weights(
        self,
        df: pd.DataFrame,
        decay_factor: float = 0.95
    ) -> np.ndarray:
        """
        计算动态样本权重（新样本权重 > 旧样本）
        
        使用指数衰减：weight = decay_factor ^ age
        
        Args:
            df: 数据集
            decay_factor: 衰减因子（0-1），越接近1衰减越慢
        
        Returns:
            np.ndarray: 样本权重
        """
        n_samples = len(df)
        
        # 计算每个样本的年龄（0=最新，n-1=最旧）
        if 'timestamp' in df.columns or 'entry_time' in df.columns:
            time_col = 'timestamp' if 'timestamp' in df.columns else 'entry_time'
            df_sorted = df.sort_values(time_col, ascending=False)
            ages = np.arange(n_samples)
        else:
            # 没有时间字段，假设后面的行更新
            ages = np.arange(n_samples)[::-1]
        
        # 指数衰减权重
        weights = decay_factor ** ages
        
        # 归一化（使总权重 = n_samples）
        weights = weights / weights.sum() * n_samples
        
        logger.info(
            f"📊 动态权重：最新样本权重{weights[0]:.2f}，"
            f"最旧样本权重{weights[-1]:.2f}，"
            f"衰减因子{decay_factor}"
        )
        
        return weights
    
    def detect_feature_drift(
        self,
        current_data: pd.DataFrame,
        feature_columns: List[str],
        update_baseline: bool = False
    ) -> Dict:
        """
        检测特征分布漂移（使用KS检验）
        
        Args:
            current_data: 当前数据
            feature_columns: 要检测的特征列表
            update_baseline: 是否更新基准统计
        
        Returns:
            Dict: 漂移检测报告
        """
        if not self.baseline_stats:
            logger.info("📊 首次检测，建立基准统计")
            self._build_baseline_stats(current_data, feature_columns)
            return {
                'has_drift': False,
                'reason': '首次建立基准',
                'drifted_features': []
            }
        
        drifted_features = []
        drift_details = {}
        
        for feature in feature_columns:
            if feature not in current_data.columns:
                continue
            
            if feature not in self.baseline_stats:
                continue
            
            # 获取当前数据
            current_values = current_data[feature].dropna().values
            
            if len(current_values) < 30:  # 样本太少，跳过
                continue
            
            # 获取基准统计
            baseline = self.baseline_stats[feature]
            
            # KS检验（比较分布）
            ks_stat, p_value = self._ks_test(
                current_values,
                baseline['mean'],
                baseline['std']
            )
            
            # 判断是否漂移
            if p_value < self.drift_threshold:
                drifted_features.append(feature)
                drift_details[feature] = {
                    'ks_statistic': float(ks_stat),
                    'p_value': float(p_value),
                    'baseline_mean': baseline['mean'],
                    'current_mean': float(np.mean(current_values)),
                    'baseline_std': baseline['std'],
                    'current_std': float(np.std(current_values))
                }
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'has_drift': len(drifted_features) > 0,
            'drifted_features': drifted_features,
            'drift_details': drift_details,
            'total_features_checked': len(feature_columns),
            'drift_threshold': self.drift_threshold
        }
        
        # 记录漂移历史
        self.drift_history.append(report)
        
        if report['has_drift']:
            logger.warning(
                f"⚠️ 检测到特征分布漂移！"
                f"漂移特征：{drifted_features}"
            )
            
            # 如果漂移严重（>30%特征漂移），建议完整重训练
            drift_ratio = len(drifted_features) / len(feature_columns)
            if drift_ratio > 0.3:
                report['recommendation'] = 'full_retrain'
                logger.warning(
                    f"⚠️ 漂移严重（{drift_ratio:.1%}特征漂移），"
                    f"建议完整重训练"
                )
            else:
                report['recommendation'] = 'incremental_retrain'
        else:
            logger.info("✅ 未检测到特征分布漂移")
            report['recommendation'] = 'continue'
        
        # 更新基准统计
        if update_baseline:
            self._build_baseline_stats(current_data, feature_columns)
        
        return report
    
    def _ks_test(
        self,
        current_values: np.ndarray,
        baseline_mean: float,
        baseline_std: float
    ) -> Tuple[float, float]:
        """
        Kolmogorov-Smirnov检验
        
        比较当前分布与基准正态分布的差异
        
        Args:
            current_values: 当前数据
            baseline_mean: 基准均值
            baseline_std: 基准标准差
        
        Returns:
            Tuple[float, float]: (KS统计量, p值)
        """
        # 生成基准正态分布
        baseline_dist = stats.norm(loc=baseline_mean, scale=baseline_std)
        
        # KS检验
        ks_stat, p_value = stats.kstest(current_values, baseline_dist.cdf)
        
        return ks_stat, p_value
    
    def _build_baseline_stats(
        self,
        df: pd.DataFrame,
        feature_columns: List[str]
    ):
        """
        建立基准特征统计
        
        Args:
            df: 数据集
            feature_columns: 特征列表
        """
        self.baseline_stats = {}
        
        for feature in feature_columns:
            if feature not in df.columns:
                continue
            
            values = df[feature].dropna().values
            
            if len(values) < 10:  # 样本太少，跳过
                continue
            
            self.baseline_stats[feature] = {
                'mean': float(np.mean(values)),
                'std': float(np.std(values)),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'median': float(np.median(values)),
                'sample_count': len(values)
            }
        
        # 保存基准统计
        self._save_baseline_stats()
        
        logger.info(f"✅ 建立基准统计：{len(self.baseline_stats)}个特征")
    
    def _save_baseline_stats(self):
        """保存基准统计到文件"""
        try:
            with open(self.stats_path, 'w') as f:
                json.dump(self.baseline_stats, f, indent=2)
            logger.debug(f"✅ 基准统计已保存：{self.stats_path}")
        except Exception as e:
            logger.error(f"保存基准统计失败：{e}")
    
    def _load_baseline_stats(self):
        """从文件加载基准统计"""
        try:
            if os.path.exists(self.stats_path):
                with open(self.stats_path, 'r') as f:
                    self.baseline_stats = json.load(f)
                logger.info(f"✅ 加载基准统计：{len(self.baseline_stats)}个特征")
            else:
                logger.info("📊 基准统计文件不存在，将在首次训练时创建")
        except Exception as e:
            logger.error(f"加载基准统计失败：{e}")
            self.baseline_stats = {}
    
    def should_retrain(
        self,
        current_samples: int,
        last_training_samples: int,
        last_training_time: Optional[datetime],
        new_sample_threshold: int = 50,
        time_threshold_hours: int = 24,
        min_new_samples_for_time: int = 10
    ) -> Tuple[bool, str]:
        """
        判断是否应该重训练
        
        触发条件：
        1. 累积N笔新交易（如50笔）
        2. 距上次训练超过T小时且有至少M笔新数据（如24小时+10笔）
        3. 检测到严重特征漂移
        
        Args:
            current_samples: 当前样本数
            last_training_samples: 上次训练时的样本数
            last_training_time: 上次训练时间
            new_sample_threshold: 新样本数阈值
            time_threshold_hours: 时间阈值（小时）
            min_new_samples_for_time: 时间触发的最小新样本数
        
        Returns:
            Tuple[bool, str]: (是否重训练, 原因)
        """
        new_samples = current_samples - last_training_samples
        
        # 条件1：累积足够新样本
        if new_samples >= new_sample_threshold:
            return True, f"累积{new_samples}笔新交易（≥{new_sample_threshold}）"
        
        # 条件2：时间+最小新样本
        if last_training_time is not None:
            hours_since_training = (datetime.now() - last_training_time).total_seconds() / 3600
            
            if hours_since_training >= time_threshold_hours and new_samples >= min_new_samples_for_time:
                return True, (
                    f"距上次训练{hours_since_training:.1f}小时（≥{time_threshold_hours}）"
                    f"且有{new_samples}笔新数据（≥{min_new_samples_for_time}）"
                )
        
        # 条件3：检测到严重漂移
        if self.drift_history:
            latest_drift = self.drift_history[-1]
            if latest_drift.get('recommendation') == 'full_retrain':
                return True, "检测到严重特征漂移"
        
        return False, f"不需要重训练（新样本{new_samples}笔）"
    
    def get_drift_summary(self) -> Dict:
        """
        获取漂移检测摘要
        
        Returns:
            Dict: 漂移摘要
        """
        if not self.drift_history:
            return {
                'total_checks': 0,
                'drift_events': 0,
                'most_drifted_features': []
            }
        
        # 统计漂移事件
        drift_events = [h for h in self.drift_history if h['has_drift']]
        
        # 统计各特征漂移次数
        feature_drift_counts = {}
        for event in drift_events:
            for feature in event['drifted_features']:
                feature_drift_counts[feature] = feature_drift_counts.get(feature, 0) + 1
        
        # 排序
        most_drifted = sorted(
            feature_drift_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return {
            'total_checks': len(self.drift_history),
            'drift_events': len(drift_events),
            'drift_rate': len(drift_events) / len(self.drift_history),
            'most_drifted_features': [
                {'feature': f, 'drift_count': c} for f, c in most_drifted
            ]
        }
