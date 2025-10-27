"""
目标变量优化器
职责：支持多种目标变量类型（二分类、期望收益、风险调整收益）
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class TargetOptimizer:
    """目标变量优化器"""
    
    def __init__(self, target_type: str = 'binary'):
        """
        初始化优化器
        
        Args:
            target_type: 目标变量类型
                - 'binary': 二分类（is_winner: 0/1）
                - 'pnl_pct': 预测盈亏百分比（连续值）
                - 'risk_adjusted': 风险调整后收益（PnL / ATR）
        """
        self.target_type = target_type
        self.supported_types = ['binary', 'pnl_pct', 'risk_adjusted']
        
        if target_type not in self.supported_types:
            raise ValueError(f"不支持的目标类型：{target_type}，支持：{self.supported_types}")
    
    def prepare_target(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict]:
        """
        准备目标变量
        
        Args:
            df: 数据集
        
        Returns:
            Tuple[pd.Series, Dict]: (目标变量, 元信息)
        """
        if self.target_type == 'binary':
            return self._prepare_binary_target(df)
        elif self.target_type == 'pnl_pct':
            return self._prepare_pnl_target(df)
        elif self.target_type == 'risk_adjusted':
            return self._prepare_risk_adjusted_target(df)
        else:
            raise ValueError(f"不支持的目标类型：{self.target_type}")
    
    def _prepare_binary_target(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict]:
        """
        准备二分类目标（标准模式）
        
        is_winner: 1=盈利, 0=亏损
        """
        if 'is_winner' not in df.columns:
            logger.error("数据集缺少 is_winner 字段")
            return pd.Series(), {}
        
        target = df['is_winner']
        
        # 统计
        win_rate = target.mean()
        
        meta = {
            'target_type': 'binary',
            'win_rate': float(win_rate),
            'winners': int(target.sum()),
            'losers': int((1 - target).sum())
        }
        
        logger.info(f"📊 二分类目标：胜率 {win_rate:.2%}, 赢家 {meta['winners']}, 输家 {meta['losers']}")
        
        return target, meta
    
    def _prepare_pnl_target(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict]:
        """
        准备盈亏百分比目标（回归模式）
        
        直接预测 pnl_pct（期望收益）
        """
        if 'pnl_pct' not in df.columns:
            logger.error("数据集缺少 pnl_pct 字段")
            return pd.Series(), {}
        
        target = df['pnl_pct']
        
        # 统计
        mean_pnl = target.mean()
        median_pnl = target.median()
        std_pnl = target.std()
        
        meta = {
            'target_type': 'pnl_pct',
            'mean_pnl': float(mean_pnl),
            'median_pnl': float(median_pnl),
            'std_pnl': float(std_pnl),
            'min_pnl': float(target.min()),
            'max_pnl': float(target.max())
        }
        
        logger.info(
            f"📊 盈亏百分比目标：均值 {mean_pnl:.2f}%, "
            f"中位数 {median_pnl:.2f}%, 标准差 {std_pnl:.2f}%"
        )
        
        return target, meta
    
    def _prepare_risk_adjusted_target(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict]:
        """
        准备风险调整后收益目标（回归模式）
        
        risk_adjusted_return = pnl_pct / atr_entry
        
        优点：
        - 考虑市场波动率，避免高波动期的虚假收益
        - 更稳定的评估指标
        """
        if 'pnl_pct' not in df.columns or 'atr_entry' not in df.columns:
            logger.error("数据集缺少 pnl_pct 或 atr_entry 字段")
            return pd.Series(), {}
        
        # 计算风险调整收益
        # 避免除零：ATR太小时用中位数替代
        atr_values = df['atr_entry'].copy()
        median_atr = atr_values.median()
        atr_values = atr_values.replace(0, median_atr)
        atr_values[atr_values < median_atr * 0.1] = median_atr
        
        risk_adjusted = df['pnl_pct'] / atr_values
        
        # 统计
        mean_ra = risk_adjusted.mean()
        median_ra = risk_adjusted.median()
        std_ra = risk_adjusted.std()
        
        meta = {
            'target_type': 'risk_adjusted',
            'mean_risk_adjusted': float(mean_ra),
            'median_risk_adjusted': float(median_ra),
            'std_risk_adjusted': float(std_ra),
            'min_risk_adjusted': float(risk_adjusted.min()),
            'max_risk_adjusted': float(risk_adjusted.max())
        }
        
        logger.info(
            f"📊 风险调整收益目标：均值 {mean_ra:.2f}, "
            f"中位数 {median_ra:.2f}, 标准差 {std_ra:.2f}"
        )
        
        return risk_adjusted, meta
    
    def get_model_params(self, base_params: Dict) -> Dict:
        """
        根据目标类型调整模型参数
        
        Args:
            base_params: 基础参数
        
        Returns:
            Dict: 调整后的参数
        """
        params = base_params.copy()
        
        if self.target_type == 'binary':
            # 二分类
            params['objective'] = 'binary:logistic'
            params['eval_metric'] = 'auc'
        
        elif self.target_type in ['pnl_pct', 'risk_adjusted']:
            # 回归
            params['objective'] = 'reg:squarederror'
            params['eval_metric'] = 'rmse'
        
        logger.info(f"📊 模型参数调整：目标类型 {self.target_type}, objective {params['objective']}")
        
        return params
    
    def evaluate_prediction(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict:
        """
        评估预测结果
        
        Args:
            y_true: 真实值
            y_pred: 预测值
        
        Returns:
            Dict: 评估指标
        """
        if self.target_type == 'binary':
            return self._evaluate_binary(y_true, y_pred)
        elif self.target_type in ['pnl_pct', 'risk_adjusted']:
            return self._evaluate_regression(y_true, y_pred)
        else:
            return {}
    
    def _evaluate_binary(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        """评估二分类"""
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        
        return {
            'accuracy': float(accuracy_score(y_true, y_pred)),
            'precision': float(precision_score(y_true, y_pred, zero_division='warn')),
            'recall': float(recall_score(y_true, y_pred, zero_division='warn')),
            'f1_score': float(f1_score(y_true, y_pred, zero_division='warn'))
        }
    
    def _evaluate_regression(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        """评估回归"""
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        
        mae = mean_absolute_error(y_true, y_pred)
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_true, y_pred)
        
        # 方向准确率（预测符号是否正确）
        direction_accuracy = np.mean(np.sign(y_true) == np.sign(y_pred))
        
        return {
            'mae': float(mae),
            'mse': float(mse),
            'rmse': float(rmse),
            'r2_score': float(r2),
            'direction_accuracy': float(direction_accuracy)
        }
    
    def convert_prediction_to_confidence(
        self,
        prediction: float,
        prediction_range: Optional[Tuple[float, float]] = None
    ) -> float:
        """
        将预测值转换为信心度（0-1）
        
        Args:
            prediction: 预测值
            prediction_range: 预测值范围（min, max）
        
        Returns:
            float: 信心度（0-1）
        """
        if self.target_type == 'binary':
            # 二分类预测已经是概率
            return max(0.0, min(1.0, prediction))
        
        elif self.target_type in ['pnl_pct', 'risk_adjusted']:
            # 回归预测：将预测值映射到0-1
            # 正值越大信心越高，负值信心低
            
            if prediction_range is None:
                # 默认范围：-10% to +10%
                prediction_range = (-10.0, 10.0)
            
            min_val, max_val = prediction_range
            
            # 归一化到0-1
            normalized = (prediction - min_val) / (max_val - min_val)
            confidence = max(0.0, min(1.0, normalized))
            
            return confidence
        
        return 0.5
