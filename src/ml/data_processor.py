"""
ML 數據處理器
職責：特徵工程、數據清洗、數據集準備
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
import json
import os
import logging
from datetime import datetime

from src.config import Config

logger = logging.getLogger(__name__)


class MLDataProcessor:
    """ML 數據處理器"""
    
    def __init__(self):
        """初始化數據處理器"""
        self.config = Config
        self.feature_columns = [
            'confidence_score', 'leverage', 'position_value',
            'hold_duration_hours', 'risk_reward_ratio',
            'order_blocks_count', 'liquidity_zones_count',
            'rsi_entry', 'macd_entry', 'macd_signal_entry', 'macd_histogram_entry',
            'atr_entry', 'bb_width_pct', 'volume_sma_ratio',
            'price_vs_ema50', 'price_vs_ema200',
            'trend_1h_encoded', 'trend_15m_encoded', 'trend_5m_encoded',
            'market_structure_encoded', 'direction_encoded'
        ]
        self.target_column = 'is_winner'
    
    def load_training_data(self) -> pd.DataFrame:
        """
        從文件加載訓練數據
        
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
                        trades.append(json.loads(line))
            
            if not trades:
                logger.warning("沒有可用的訓練數據")
                return pd.DataFrame()
            
            df = pd.DataFrame(trades)
            logger.info(f"加載 {len(df)} 條交易記錄")
            
            return df
            
        except Exception as e:
            logger.error(f"加載訓練數據失敗: {e}")
            return pd.DataFrame()
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        準備特徵和標籤
        
        Args:
            df: 原始數據
        
        Returns:
            Tuple[pd.DataFrame, pd.Series]: (特徵矩陣, 標籤向量)
        """
        if df.empty:
            return pd.DataFrame(), pd.Series()
        
        try:
            df_processed = df.copy()
            
            # 編碼類別變量
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
            
            # 填充缺失值
            for col in self.feature_columns:
                if col in df_processed.columns:
                    df_processed[col] = df_processed[col].fillna(0)
            
            # 提取特徵
            available_features = [col for col in self.feature_columns if col in df_processed.columns]
            X = df_processed[available_features]
            
            # 提取標籤
            y = df_processed[self.target_column].astype(int)
            
            logger.info(f"準備特徵矩陣: {X.shape}, 標籤向量: {y.shape}")
            
            return X, y
            
        except Exception as e:
            logger.error(f"準備特徵失敗: {e}")
            return pd.DataFrame(), pd.Series()
    
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
