"""
特征重要性监控器
职责：监控特征重要性变化，检测突变，触发特征工程审查
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class FeatureImportanceMonitor:
    """特征重要性监控器"""
    
    def __init__(self, history_path: str = "data/models/feature_importance_history.json"):
        """
        初始化监控器
        
        Args:
            history_path: 历史记录文件路径
        """
        self.history_path = history_path
        self.importance_history = []
        
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        self._load_history()
    
    def record_importance(
        self,
        feature_importance: Dict[str, float],
        model_metrics: Optional[Dict] = None
    ):
        """
        记录特征重要性
        
        Args:
            feature_importance: 特征重要性字典
            model_metrics: 模型评估指标（可选）
        """
        record = {
            'timestamp': datetime.now().isoformat(),
            'feature_importance': feature_importance,
            'model_metrics': model_metrics or {}
        }
        
        self.importance_history.append(record)
        
        # 只保留最近100次记录
        if len(self.importance_history) > 100:
            self.importance_history = self.importance_history[-100:]
        
        self._save_history()
        
        logger.debug(f"✅ 记录特征重要性：{len(feature_importance)}个特征")
    
    def detect_importance_shift(
        self,
        current_importance: Dict[str, float],
        shift_threshold: float = 0.3
    ) -> Dict:
        """
        检测特征重要性突变
        
        Args:
            current_importance: 当前特征重要性
            shift_threshold: 变化阈值（>threshold则认为突变）
        
        Returns:
            Dict: 检测报告
        """
        if len(self.importance_history) < 2:
            return {
                'has_shift': False,
                'reason': '历史记录不足'
            }
        
        # 获取上一次记录
        previous_record = self.importance_history[-2]
        previous_importance = previous_record['feature_importance']
        
        # 计算变化
        shifted_features = []
        importance_changes = {}
        
        for feature, current_imp in current_importance.items():
            if feature not in previous_importance:
                continue
            
            previous_imp = previous_importance[feature]
            
            # 计算相对变化
            if previous_imp > 0:
                relative_change = abs(current_imp - previous_imp) / previous_imp
            else:
                relative_change = abs(current_imp - previous_imp)
            
            importance_changes[feature] = {
                'previous': previous_imp,
                'current': current_imp,
                'relative_change': relative_change
            }
            
            if relative_change > shift_threshold:
                shifted_features.append({
                    'feature': feature,
                    'previous_importance': previous_imp,
                    'current_importance': current_imp,
                    'relative_change': relative_change
                })
        
        # 排序（按变化幅度）
        shifted_features.sort(key=lambda x: x['relative_change'], reverse=True)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'has_shift': len(shifted_features) > 0,
            'shifted_features': shifted_features,
            'total_features_checked': len(current_importance),
            'shift_threshold': shift_threshold
        }
        
        if report['has_shift']:
            logger.warning(
                f"⚠️ 检测到特征重要性突变！{len(shifted_features)}个特征"
            )
            for shift in shifted_features[:5]:  # 显示前5个
                logger.warning(
                    f"  - {shift['feature']}: "
                    f"{shift['previous_importance']:.4f} → {shift['current_importance']:.4f} "
                    f"(变化 {shift['relative_change']:.1%})"
                )
        else:
            logger.info("✅ 特征重要性稳定，无明显突变")
        
        return report
    
    def get_top_features(
        self,
        current_importance: Dict[str, float],
        top_n: int = 10
    ) -> List[Tuple[str, float]]:
        """
        获取最重要的N个特征
        
        Args:
            current_importance: 当前特征重要性
            top_n: 返回前N个
        
        Returns:
            List[Tuple[str, float]]: 特征列表（特征名，重要性）
        """
        sorted_features = sorted(
            current_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        top_features = sorted_features[:top_n]
        
        logger.info(f"📊 Top {min(top_n, len(top_features))} 特征：")
        for i, (feature, importance) in enumerate(top_features, 1):
            logger.info(f"  {i}. {feature}: {importance:.4f}")
        
        return top_features
    
    def analyze_importance_trend(
        self,
        feature_name: str,
        window_size: int = 10
    ) -> Dict:
        """
        分析单个特征的重要性趋势
        
        Args:
            feature_name: 特征名
            window_size: 分析窗口大小
        
        Returns:
            Dict: 趋势分析
        """
        if len(self.importance_history) < window_size:
            return {
                'feature': feature_name,
                'trend': 'insufficient_data',
                'data_points': len(self.importance_history)
            }
        
        # 提取最近N次的重要性值
        recent_records = self.importance_history[-window_size:]
        importance_values = []
        
        for record in recent_records:
            imp = record['feature_importance'].get(feature_name, 0)
            importance_values.append(imp)
        
        # 计算趋势
        if len(importance_values) < 3:
            trend = 'stable'
        else:
            # 简单线性拟合
            x = np.arange(len(importance_values))
            y = np.array(importance_values)
            
            # 计算斜率
            slope = np.polyfit(x, y, 1)[0]
            
            if slope > 0.01:
                trend = 'increasing'
            elif slope < -0.01:
                trend = 'decreasing'
            else:
                trend = 'stable'
        
        return {
            'feature': feature_name,
            'trend': trend,
            'recent_values': importance_values,
            'mean': float(np.mean(importance_values)),
            'std': float(np.std(importance_values)),
            'min': float(np.min(importance_values)),
            'max': float(np.max(importance_values))
        }
    
    def recommend_feature_engineering(
        self,
        shift_report: Dict,
        importance_drop_threshold: float = 0.5
    ) -> List[str]:
        """
        基于重要性变化推荐特征工程改进
        
        Args:
            shift_report: 突变检测报告
            importance_drop_threshold: 重要性下降阈值
        
        Returns:
            List[str]: 推荐列表
        """
        recommendations = []
        
        if not shift_report.get('has_shift', False):
            return ["特征重要性稳定，暂无改进建议"]
        
        shifted_features = shift_report.get('shifted_features', [])
        
        for shift in shifted_features:
            feature = shift['feature']
            prev_imp = shift['previous_importance']
            curr_imp = shift['current_importance']
            change = shift['relative_change']
            
            # 重要性大幅下降
            if curr_imp < prev_imp and change > importance_drop_threshold:
                recommendations.append(
                    f"⚠️ {feature} 重要性下降{change:.1%}，"
                    f"考虑移除或替换为更有效的特征"
                )
            
            # 重要性大幅上升
            elif curr_imp > prev_imp and change > importance_drop_threshold:
                recommendations.append(
                    f"✅ {feature} 重要性上升{change:.1%}，"
                    f"考虑基于此特征创建衍生特征"
                )
        
        if not recommendations:
            recommendations.append("特征重要性变化在正常范围内")
        
        return recommendations
    
    def _save_history(self):
        """保存历史记录到文件"""
        try:
            with open(self.history_path, 'w') as f:
                json.dump(self.importance_history, f, indent=2)
            logger.debug(f"✅ 特征重要性历史已保存：{self.history_path}")
        except Exception as e:
            logger.error(f"保存特征重要性历史失败：{e}")
    
    def _load_history(self):
        """从文件加载历史记录"""
        try:
            if os.path.exists(self.history_path):
                with open(self.history_path, 'r') as f:
                    self.importance_history = json.load(f)
                logger.info(f"✅ 加载特征重要性历史：{len(self.importance_history)}条记录")
            else:
                logger.info("📊 特征重要性历史文件不存在，将在首次记录时创建")
        except Exception as e:
            logger.error(f"加载特征重要性历史失败：{e}")
            self.importance_history = []
