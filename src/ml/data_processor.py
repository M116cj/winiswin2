"""
ML 數據處理器
職責：特徵工程、數據清洗、數據集準備、增強特徵
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import json
import os
import logging
from datetime import datetime

from src.config import Config

logger = logging.getLogger(__name__)


class MLDataProcessor:
    """ML 數據處理器（優化版v3.3.7）"""
    
    def __init__(self):
        """初始化數據處理器"""
        self.config = Config
        
        # 基礎特徵（21個）
        self.basic_features = [
            'confidence_score', 'leverage', 'position_value',
            'hold_duration_hours', 'risk_reward_ratio',
            'order_blocks_count', 'liquidity_zones_count',
            'rsi_entry', 'macd_entry', 'macd_signal_entry', 'macd_histogram_entry',
            'atr_entry', 'bb_width_pct', 'volume_sma_ratio',
            'price_vs_ema50', 'price_vs_ema200',
            'trend_1h_encoded', 'trend_15m_encoded', 'trend_5m_encoded',
            'market_structure_encoded', 'direction_encoded'
        ]
        
        # 增強特徵（只包含推理時可用的特徵，移除目標泄漏）
        self.enhanced_features = [
            'hour_of_day', 'day_of_week', 'is_weekend',
            'stop_distance_pct', 'tp_distance_pct',
            'confidence_x_leverage', 'rsi_x_trend', 'atr_x_bb_width'
        ]
        
        self.feature_columns = self.basic_features + self.enhanced_features
        self.target_column = 'is_winner'
    
    def load_training_data(self, validate=True) -> pd.DataFrame:
        """
        從文件加載訓練數據（優化版）
        
        Args:
            validate: 是否進行數據驗證和清理
        
        Returns:
            pd.DataFrame: 訓練數據集
        """
        trades_file = self.config.TRADES_FILE
        
        if not os.path.exists(trades_file):
            logger.warning(f"訓練數據文件不存在: {trades_file}")
            return pd.DataFrame()
        
        try:
            trades = []
            with open(trades_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            trades.append(json.loads(line))
                        except json.JSONDecodeError:
                            logger.warning(f"跳過無效JSON行")
                            continue
            
            if not trades:
                logger.warning("沒有可用的訓練數據")
                return pd.DataFrame()
            
            df = pd.DataFrame(trades)
            logger.info(f"加載 {len(df)} 條交易記錄")
            
            # 數據驗證和清理
            if validate and not df.empty:
                df = self._validate_and_clean(df)
                logger.info(f"驗證後: {len(df)} 條記錄")
            
            return df
            
        except Exception as e:
            logger.error(f"加載訓練數據失敗: {e}")
            return pd.DataFrame()
    
    def _validate_and_clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        驗證和清理數據（v3.3.7優化）
        
        Args:
            df: 原始數據
        
        Returns:
            pd.DataFrame: 清理後的數據
        """
        original_count = len(df)
        
        # 1. 移除必需字段缺失的記錄
        required_fields = ['symbol', 'direction', 'entry_price', 'is_winner']
        df = df.dropna(subset=required_fields)
        
        if len(df) < original_count:
            logger.info(f"移除缺失必需字段: {original_count - len(df)} 條")
        
        # 2. 移除異常值
        df = self._remove_outliers(df)
        
        # 3. 檢查類別平衡
        balance_info = self._check_class_balance(df)
        logger.info(f"類別平衡: {balance_info}")
        
        return df
    
    def _remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """移除異常值（使用IQR方法）"""
        numeric_cols = ['leverage', 'position_value', 'hold_duration_hours', 'pnl_pct']
        
        for col in numeric_cols:
            if col not in df.columns:
                continue
            
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            # 使用3倍IQR（較寬鬆的閾值）
            lower = Q1 - 3 * IQR
            upper = Q3 + 3 * IQR
            
            before_count = len(df)
            df = df[(df[col] >= lower) & (df[col] <= upper)]
            
            if len(df) < before_count:
                logger.debug(f"移除 {col} 異常值: {before_count - len(df)} 條")
        
        return df
    
    def _check_class_balance(self, df: pd.DataFrame) -> Dict:
        """檢查類別平衡"""
        if 'is_winner' not in df.columns:
            return {}
        
        winners = df['is_winner'].sum()
        losers = len(df) - winners
        
        return {
            'winners': int(winners),
            'losers': int(losers),
            'win_rate': winners / len(df) if len(df) > 0 else 0,
            'ratio': winners / losers if losers > 0 else 0,
            'balance': 'good' if 0.3 <= (winners / len(df)) <= 0.7 else 'skewed'
        }
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        準備特徵和標籤（v3.3.7優化版 - 增強特徵工程）
        
        Args:
            df: 原始數據
        
        Returns:
            Tuple[pd.DataFrame, pd.Series]: (特徵矩陣, 標籤向量)
        """
        if df.empty:
            return pd.DataFrame(), pd.Series()
        
        try:
            df_processed = df.copy()
            
            # 1. 編碼類別變量
            df_processed['trend_1h_encoded'] = df_processed['trend_1h'].map({
                'bullish': 1, 'bearish': -1, 'neutral': 0
            }).fillna(0)
            
            df_processed['trend_15m_encoded'] = df_processed['trend_15m'].map({
                'bullish': 1, 'bearish': -1, 'neutral': 0
            }).fillna(0)
            
            df_processed['trend_5m_encoded'] = df_processed['trend_5m'].map({
                'bullish': 1, 'bearish': -1, 'neutral': 0
            }).fillna(0)
            
            df_processed['market_structure_encoded'] = df_processed['market_structure'].map({
                'bullish': 1, 'bearish': -1, 'neutral': 0
            }).fillna(0)
            
            df_processed['direction_encoded'] = df_processed['direction'].map({
                'LONG': 1, 'SHORT': -1
            }).fillna(0)
            
            # 2. ✨ 增強特徵工程（v3.3.7新增）
            df_processed = self._add_enhanced_features(df_processed)
            
            # 3. 填充缺失值
            for col in self.feature_columns:
                if col in df_processed.columns:
                    df_processed[col] = df_processed[col].fillna(0)
            
            # 4. 提取特徵
            available_features = [col for col in self.feature_columns if col in df_processed.columns]
            X = df_processed[available_features]
            
            # 5. 提取標籤
            y = df_processed[self.target_column].astype(int)
            
            logger.info(
                f"準備特徵矩陣: {X.shape} "
                f"(基礎特徵: {len(self.basic_features)}, "
                f"增強特徵: {len(self.enhanced_features)})"
            )
            
            return X, y
            
        except Exception as e:
            logger.error(f"準備特徵失敗: {e}", exc_info=True)
            return pd.DataFrame(), pd.Series()
    
    def _add_enhanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        添加增強特徵（v3.3.7）
        
        Args:
            df: 數據框
        
        Returns:
            pd.DataFrame: 添加增強特徵後的數據框
        """
        # 時間特徵
        if 'entry_timestamp' in df.columns:
            df['hour_of_day'] = pd.to_datetime(df['entry_timestamp']).dt.hour
            df['day_of_week'] = pd.to_datetime(df['entry_timestamp']).dt.dayofweek
            df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        else:
            df['hour_of_day'] = 0
            df['day_of_week'] = 0
            df['is_weekend'] = 0
        
        # 價格波動特徵（移除price_move_pct - 目標泄漏）
        if 'entry_price' in df.columns and 'stop_loss' in df.columns:
            df['stop_distance_pct'] = abs(df['stop_loss'] - df['entry_price']) / df['entry_price']
        else:
            df['stop_distance_pct'] = 0
        
        if 'entry_price' in df.columns and 'take_profit' in df.columns:
            df['tp_distance_pct'] = abs(df['take_profit'] - df['entry_price']) / df['entry_price']
        else:
            df['tp_distance_pct'] = 0
        
        # 交互特徵
        if 'confidence_score' in df.columns and 'leverage' in df.columns:
            df['confidence_x_leverage'] = df['confidence_score'] * df['leverage']
        else:
            df['confidence_x_leverage'] = 0
        
        if 'rsi_entry' in df.columns and 'trend_15m_encoded' in df.columns:
            df['rsi_x_trend'] = df['rsi_entry'] * df['trend_15m_encoded']
        else:
            df['rsi_x_trend'] = 0
        
        if 'atr_entry' in df.columns and 'bb_width_pct' in df.columns:
            df['atr_x_bb_width'] = df['atr_entry'] * df['bb_width_pct']
        else:
            df['atr_x_bb_width'] = 0
        
        return df
    
    def split_data(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.2
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """
        分割訓練集和測試集
        
        Args:
            X: 特徵矩陣
            y: 標籤向量
            test_size: 測試集比例
        
        Returns:
            Tuple: (X_train, X_test, y_train, y_test)
        """
        if X.empty or y.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.Series(), pd.Series()
        
        try:
            from sklearn.model_selection import train_test_split
            
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=test_size,
                random_state=42,
                stratify=y if len(y.unique()) > 1 else None
            )
            
            logger.info(f"訓練集: {X_train.shape}, 測試集: {X_test.shape}")
            
            return X_train, X_test, y_train, y_test
            
        except Exception as e:
            logger.error(f"分割數據失敗: {e}")
            return pd.DataFrame(), pd.DataFrame(), pd.Series(), pd.Series()
    
    def get_feature_importance(self, model, feature_names: List[str]) -> Dict[str, float]:
        """
        獲取特徵重要性
        
        Args:
            model: 訓練好的模型
            feature_names: 特徵名稱列表
        
        Returns:
            Dict[str, float]: 特徵重要性字典
        """
        try:
            importance = model.feature_importances_
            feature_importance = dict(zip(feature_names, importance))
            
            # 按重要性排序
            feature_importance = dict(
                sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            )
            
            return feature_importance
            
        except Exception as e:
            logger.error(f"獲取特徵重要性失敗: {e}")
            return {}
