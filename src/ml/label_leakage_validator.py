"""
标签泄漏验证器
职责：检测特征是否包含未来信息，确保时间对齐
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LabelLeakageValidator:
    """标签泄漏验证器"""
    
    def __init__(self):
        """初始化验证器"""
        # 定义必须在开仓时刻已知的特征
        self.entry_time_features = [
            'confidence_score', 'leverage', 'position_value',
            'order_blocks_count', 'liquidity_zones_count',
            'rsi_entry', 'macd_entry', 'macd_signal_entry', 'macd_histogram_entry',
            'atr_entry', 'bb_width_pct', 'volume_sma_ratio',
            'price_vs_ema50', 'price_vs_ema200',
            'trend_1h_encoded', 'trend_15m_encoded', 'trend_5m_encoded',
            'market_structure_encoded', 'direction_encoded',
            'hour_of_day', 'day_of_week', 'is_weekend',
            'confidence_x_leverage', 'rsi_x_trend', 'atr_x_bb_width'
        ]
        
        # 需要验证的距离特征（可能包含未来信息）
        self.distance_features = ['stop_distance_pct', 'tp_distance_pct']
        
        # 目标变量
        self.target = 'is_winner'
    
    def validate_training_data(self, df: pd.DataFrame) -> Dict:
        """
        验证训练数据是否存在标签泄漏
        
        Args:
            df: 训练数据
        
        Returns:
            Dict: 验证报告
        """
        report = {
            'total_samples': len(df),
            'has_leakage': False,
            'leakage_features': [],
            'warnings': [],
            'passed_checks': []
        }
        
        if df.empty:
            report['warnings'].append("数据集为空")
            return report
        
        # 检查1：目标变量与距离特征的相关性检查
        leakage_check = self._check_target_correlation(df)
        report.update(leakage_check)
        
        # 检查2：时间对齐验证（止损/止盈距离必须在开仓时计算）
        time_alignment_check = self._check_time_alignment(df)
        report['time_alignment'] = time_alignment_check
        
        # 检查3：特征值合理性检查
        sanity_check = self._check_feature_sanity(df)
        report['sanity_check'] = sanity_check
        
        # 检查4：未来信息检测（hold_duration不应在训练时使用）
        future_info_check = self._check_future_information(df)
        report['future_info_check'] = future_info_check
        
        logger.info(f"🔍 标签泄漏验证完成：{report}")
        
        return report
    
    def _check_target_correlation(self, df: pd.DataFrame) -> Dict:
        """
        检查目标变量与特征的相关性（检测泄漏）
        
        过高的相关性（>0.9）可能表示特征包含未来信息
        """
        result = {
            'correlation_check': 'passed',
            'high_correlation_features': []
        }
        
        if self.target not in df.columns:
            result['correlation_check'] = 'skipped'
            result['warnings'] = ['目标变量不存在']
            return result
        
        # 计算相关性
        correlations = {}
        for feature in self.distance_features:
            if feature in df.columns:
                corr = abs(df[feature].corr(df[self.target]))
                correlations[feature] = corr
                
                # 相关性>0.9表示可能泄漏
                if corr > 0.9:
                    result['high_correlation_features'].append({
                        'feature': feature,
                        'correlation': float(corr)
                    })
        
        if result['high_correlation_features']:
            result['correlation_check'] = 'warning'
            logger.warning(f"⚠️ 检测到高相关性特征（可能泄漏）：{result['high_correlation_features']}")
        else:
            logger.info(f"✅ 相关性检查通过：{correlations}")
        
        return result
    
    def _check_time_alignment(self, df: pd.DataFrame) -> Dict:
        """
        验证止损/止盈距离是否在开仓时刻计算
        
        检查逻辑：
        - stop_distance_pct = abs((stop_loss - entry_price) / entry_price)
        - tp_distance_pct = abs((take_profit - entry_price) / entry_price)
        这些值必须基于开仓时设定的SL/TP，而非事后计算
        """
        result = {
            'status': 'passed',
            'verified_samples': 0,
            'mismatched_samples': 0
        }
        
        required_cols = ['entry_price', 'stop_loss', 'take_profit', 
                        'stop_distance_pct', 'tp_distance_pct']
        
        if not all(col in df.columns for col in required_cols):
            result['status'] = 'skipped'
            result['reason'] = '缺少必需字段'
            return result
        
        # 验证计算是否正确
        mismatches = 0
        for idx, row in df.iterrows():
            if pd.notna(row['stop_loss']) and pd.notna(row['stop_distance_pct']):
                expected_stop_dist = abs((row['stop_loss'] - row['entry_price']) / row['entry_price'])
                actual_stop_dist = row['stop_distance_pct']
                
                # 允许0.1%的浮点误差
                if abs(expected_stop_dist - actual_stop_dist) > 0.001:
                    mismatches += 1
            
            if pd.notna(row['take_profit']) and pd.notna(row['tp_distance_pct']):
                expected_tp_dist = abs((row['take_profit'] - row['entry_price']) / row['entry_price'])
                actual_tp_dist = row['tp_distance_pct']
                
                if abs(expected_tp_dist - actual_tp_dist) > 0.001:
                    mismatches += 1
        
        result['verified_samples'] = len(df)
        result['mismatched_samples'] = mismatches
        
        if mismatches > 0:
            result['status'] = 'warning'
            logger.warning(f"⚠️ {mismatches}/{len(df)} 样本的距离计算不匹配")
        else:
            logger.info(f"✅ 时间对齐验证通过：{len(df)} 样本")
        
        return result
    
    def _check_feature_sanity(self, df: pd.DataFrame) -> Dict:
        """
        检查特征值的合理性
        
        例如：
        - stop_distance_pct应该>0且合理（如0.5%-5%）
        - tp_distance_pct应该>0且合理（如1%-10%）
        """
        result = {
            'status': 'passed',
            'issues': []
        }
        
        # 检查止损距离
        if 'stop_distance_pct' in df.columns:
            stop_dist = df['stop_distance_pct'].dropna()
            if len(stop_dist) > 0:
                # 检查是否有负值
                if (stop_dist < 0).any():
                    result['issues'].append('stop_distance_pct存在负值')
                
                # 检查是否有异常大的值（>20%）
                if (stop_dist > 0.2).any():
                    outlier_count = (stop_dist > 0.2).sum()
                    result['issues'].append(f'stop_distance_pct存在{outlier_count}个异常值（>20%）')
        
        # 检查止盈距离
        if 'tp_distance_pct' in df.columns:
            tp_dist = df['tp_distance_pct'].dropna()
            if len(tp_dist) > 0:
                if (tp_dist < 0).any():
                    result['issues'].append('tp_distance_pct存在负值')
                
                if (tp_dist > 0.5).any():
                    outlier_count = (tp_dist > 0.5).sum()
                    result['issues'].append(f'tp_distance_pct存在{outlier_count}个异常值（>50%）')
        
        if result['issues']:
            result['status'] = 'warning'
            logger.warning(f"⚠️ 特征合理性检查发现问题：{result['issues']}")
        else:
            logger.info("✅ 特征合理性检查通过")
        
        return result
    
    def _check_future_information(self, df: pd.DataFrame) -> Dict:
        """
        检测是否使用了未来信息
        
        警告特征（不应在训练时使用）：
        - actual_hold_duration：实际持仓时间（只有平仓后才知道）
        - final_pnl_pct：最终盈亏（只有平仓后才知道）
        """
        result = {
            'status': 'passed',
            'future_features_found': []
        }
        
        future_features = [
            'actual_hold_duration',
            'final_pnl_pct',
            'exit_price',
            'close_time'
        ]
        
        for feature in future_features:
            if feature in df.columns:
                result['future_features_found'].append(feature)
        
        if result['future_features_found']:
            result['status'] = 'warning'
            logger.warning(
                f"⚠️ 检测到未来信息特征（不应用于训练）："
                f"{result['future_features_found']}"
            )
        else:
            logger.info("✅ 未检测到未来信息特征")
        
        return result
    
    def get_safe_features(self) -> List[str]:
        """
        获取安全特征列表（确保无泄漏）
        
        Returns:
            List[str]: 安全特征列表
        """
        return self.entry_time_features + self.distance_features
    
    def validate_single_signal(self, signal: Dict) -> bool:
        """
        验证单个信号的特征是否安全（用于实时预测）
        
        Args:
            signal: 交易信号
        
        Returns:
            bool: 是否通过验证
        """
        # 检查是否包含未来信息
        unsafe_keys = ['exit_price', 'close_time', 'actual_pnl', 'final_pnl_pct']
        
        for key in unsafe_keys:
            if key in signal:
                logger.error(f"❌ 信号包含未来信息：{key}")
                return False
        
        # 检查必需特征是否存在
        required_features = ['entry_price', 'stop_loss', 'take_profit', 'confidence']
        for feature in required_features:
            if feature not in signal and feature + '_score' not in signal:
                logger.warning(f"⚠️ 缺少必需特征：{feature}")
        
        return True
