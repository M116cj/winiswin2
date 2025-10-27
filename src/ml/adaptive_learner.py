"""
自适应学习器（v3.4.0）
职责：根据模型性能动态调整学习参数和训练策略
"""

import logging
from typing import Dict, Optional
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)


class AdaptiveLearner:
    """自适应学习管理器"""
    
    def __init__(
        self,
        base_lr: float = 0.1,
        min_lr: float = 0.01,
        max_lr: float = 0.3,
        history_window: int = 10
    ):
        """
        初始化自适应学习器
        
        Args:
            base_lr: 基础学习率
            min_lr: 最小学习率
            max_lr: 最大学习率
            history_window: 性能历史窗口大小
        """
        self.base_lr = base_lr
        self.min_lr = min_lr
        self.max_lr = max_lr
        
        # 性能历史（最近N次训练）
        self.performance_history = deque(maxlen=history_window)
        
        # 当前参数
        self.current_lr = base_lr
        self.current_n_estimators = 200
        
        # 自适应状态
        self.consecutive_improvements = 0
        self.consecutive_degradations = 0
    
    def update_performance(self, accuracy: float, timestamp: Optional[datetime] = None):
        """
        更新性能历史
        
        Args:
            accuracy: 模型准确率
            timestamp: 时间戳
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self.performance_history.append({
            'accuracy': accuracy,
            'timestamp': timestamp,
            'learning_rate': self.current_lr,
            'n_estimators': self.current_n_estimators
        })
        
        logger.debug(f"性能历史更新: 准确率={accuracy:.4f}, LR={self.current_lr}")
    
    def adjust_learning_rate(self, current_accuracy: float) -> float:
        """
        根据性能动态调整学习率
        
        Args:
            current_accuracy: 当前准确率
        
        Returns:
            float: 调整后的学习率
        """
        if len(self.performance_history) == 0:
            return self.base_lr
        
        # 获取最近的准确率
        recent_accuracies = [p['accuracy'] for p in list(self.performance_history)[-3:]]
        avg_recent = sum(recent_accuracies) / len(recent_accuracies)
        
        # 性能提升
        if current_accuracy > avg_recent + 0.02:
            self.consecutive_improvements += 1
            self.consecutive_degradations = 0
            
            # 连续提升，增加学习率（探索）
            if self.consecutive_improvements >= 2:
                new_lr = min(self.current_lr * 1.2, self.max_lr)
                logger.info(f"📈 性能持续提升，增加学习率: {self.current_lr:.4f} → {new_lr:.4f}")
                self.current_lr = new_lr
        
        # 性能下降
        elif current_accuracy < avg_recent - 0.03:
            self.consecutive_degradations += 1
            self.consecutive_improvements = 0
            
            # 连续下降，降低学习率（保守）
            if self.consecutive_degradations >= 2:
                new_lr = max(self.current_lr * 0.7, self.min_lr)
                logger.warning(f"📉 性能下降，降低学习率: {self.current_lr:.4f} → {new_lr:.4f}")
                self.current_lr = new_lr
        
        # 性能稳定
        else:
            self.consecutive_improvements = 0
            self.consecutive_degradations = 0
        
        return self.current_lr
    
    def adjust_n_estimators(self, current_accuracy: float, training_time: float) -> int:
        """
        根据性能和训练时间调整树的数量
        
        Args:
            current_accuracy: 当前准确率
            training_time: 训练耗时（秒）
        
        Returns:
            int: 调整后的树数量
        """
        # 训练时间过长（>60秒），减少树数量
        if training_time > 60 and self.current_n_estimators > 100:
            new_n = max(self.current_n_estimators - 50, 100)
            logger.info(f"⏱️  训练时间过长，减少树数量: {self.current_n_estimators} → {new_n}")
            self.current_n_estimators = new_n
        
        # 性能很好且训练快速，可以增加树数量
        elif current_accuracy > 0.80 and training_time < 30 and self.current_n_estimators < 400:
            new_n = min(self.current_n_estimators + 50, 400)
            logger.info(f"🌳 性能优秀且训练快速，增加树数量: {self.current_n_estimators} → {new_n}")
            self.current_n_estimators = new_n
        
        return self.current_n_estimators
    
    def should_retrain(self, new_samples: int, hours_since_training: float) -> bool:
        """
        判断是否应该重新训练
        
        Args:
            new_samples: 新增样本数
            hours_since_training: 距离上次训练的小时数
        
        Returns:
            bool: 是否应该重新训练
        """
        # 基础规则
        if new_samples >= 50:
            logger.info(f"✅ 触发重训练: 新增 {new_samples} 笔交易（>= 50）")
            return True
        
        if hours_since_training >= 24 and new_samples >= 10:
            logger.info(f"✅ 触发重训练: 距离上次 {hours_since_training:.1f}h（>= 24h）且有 {new_samples} 笔新数据")
            return True
        
        # 自适应规则：性能下降时更频繁训练
        if len(self.performance_history) >= 2:
            latest_acc = self.performance_history[-1]['accuracy']
            avg_acc = sum(p['accuracy'] for p in self.performance_history) / len(self.performance_history)
            
            if latest_acc < avg_acc - 0.05 and new_samples >= 20:
                logger.warning(f"⚠️  触发重训练: 性能下降 ({latest_acc:.2%} < {avg_acc:.2%})且有 {new_samples} 笔新数据")
                return True
        
        return False
    
    def get_adaptive_params(self, current_accuracy: float, training_time: float = 0) -> Dict:
        """
        获取自适应调整后的参数
        
        Args:
            current_accuracy: 当前准确率
            training_time: 训练耗时（秒）
        
        Returns:
            Dict: 调整后的参数
        """
        lr = self.adjust_learning_rate(current_accuracy)
        n_est = self.adjust_n_estimators(current_accuracy, training_time)
        
        return {
            'learning_rate': lr,
            'n_estimators': n_est
        }
    
    def get_stats(self) -> Dict:
        """
        获取自适应学习统计信息
        
        Returns:
            Dict: 统计信息
        """
        if len(self.performance_history) == 0:
            return {
                'history_size': 0,
                'avg_accuracy': 0.0,
                'current_lr': self.current_lr,
                'current_n_estimators': self.current_n_estimators
            }
        
        accuracies = [p['accuracy'] for p in self.performance_history]
        
        return {
            'history_size': len(self.performance_history),
            'avg_accuracy': sum(accuracies) / len(accuracies),
            'best_accuracy': max(accuracies),
            'worst_accuracy': min(accuracies),
            'current_lr': self.current_lr,
            'current_n_estimators': self.current_n_estimators,
            'consecutive_improvements': self.consecutive_improvements,
            'consecutive_degradations': self.consecutive_degradations
        }
