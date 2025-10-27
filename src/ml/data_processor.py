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
        
        # 基礎特徵（20個 - 移除hold_duration_hours避免數據泄漏）
        self.basic_features = [
            'confidence_score', 'leverage', 'position_value',
            # 'hold_duration_hours',  # ❌ 移除：這是交易結束後才知道的信息，會導致數據泄漏
            'risk_reward_ratio',
            'order_blocks_count', 'liquidity_zones_count',
            'rsi_entry', 'macd_entry', 'macd_signal_entry', 'macd_histogram_entry',
            'atr_entry', 'bb_width_pct', 'volume_sma_ratio',
            'price_vs_ema50', 'price_vs_ema200',
            'trend_1h_encoded', 'trend_15m_encoded', 'trend_5m_encoded',
            'market_structure_encoded', 'direction_encoded'
        ]
        
        # 增強特徵（推理時可用 + 更多交叉特徵）
        self.enhanced_features = [
            # 時間特徵
            'hour_of_day', 'day_of_week', 'is_weekend',
            # 價格距離特徵
            'stop_distance_pct', 'tp_distance_pct',
            # 交叉特徵（原有）
            'confidence_x_leverage', 'rsi_x_trend', 'atr_x_bb_width',
            # 交叉特徵（新增）
            'price_momentum_strength',    # EMA50與EMA200的距離
            'volatility_x_confidence',    # 波動率 × 信心度
            'rsi_distance_from_neutral',  # RSI距離50的距離
            'macd_strength_ratio',        # MACD histogram相對強度
            'trend_alignment_score'       # 三時間框架趨勢對齊度
        ]
        
        # 禁用特徵（不應該出現在特徵中）
        self.forbidden_features = [
            'symbol', 'timestamp', 'entry_timestamp', 'exit_timestamp',
            'order_id', 'trade_id', 'signal_id', 'hold_duration',
            'pnl', 'pnl_pct', 'exit_price', 'is_winner'  # 目標變量和結果相關
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
            
            # 4.5 ✨ v3.9.2.2：特徵驗證（防止數據泄漏）
            if not self.validate_features(X):
                logger.error("特徵驗證失敗，停止處理")
                return pd.DataFrame(), pd.Series()
            
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
    
    def validate_features(self, df: pd.DataFrame) -> bool:
        """
        驗證特徵是否包含禁用字段
        
        Args:
            df: 數據框
        
        Returns:
            bool: 是否通過驗證
        """
        invalid_features = []
        
        for col in df.columns:
            # 檢查是否包含禁用關鍵字
            col_lower = col.lower()
            for forbidden in self.forbidden_features:
                if forbidden.lower() in col_lower:
                    invalid_features.append(col)
                    break
        
        if invalid_features:
            logger.error(f"❌ 特徵驗證失敗：包含禁用字段 {invalid_features}")
            return False
        
        logger.info(f"✅ 特徵驗證通過：無禁用字段")
        return True
    
    def _add_enhanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        添加增強特徵（v3.9.2.2 - 更多交叉特徵）
        
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
        
        # 交互特徵（原有）
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
        
        # 交叉特徵（新增 v3.9.2.2）
        # 1. 價格動量強度（EMA50與EMA200的相對距離）
        if 'price_vs_ema50' in df.columns and 'price_vs_ema200' in df.columns:
            df['price_momentum_strength'] = df['price_vs_ema50'] - df['price_vs_ema200']
        else:
            df['price_momentum_strength'] = 0
        
        # 2. 波動率 × 信心度（高波動高信心 vs 低波動低信心）
        if 'bb_width_pct' in df.columns and 'confidence_score' in df.columns:
            df['volatility_x_confidence'] = df['bb_width_pct'] * df['confidence_score']
        else:
            df['volatility_x_confidence'] = 0
        
        # 3. RSI距離中線的距離（衡量超買超賣程度）
        if 'rsi_entry' in df.columns:
            df['rsi_distance_from_neutral'] = abs(df['rsi_entry'] - 50)
        else:
            df['rsi_distance_from_neutral'] = 0
        
        # 4. MACD強度比率（histogram相對於signal的強度）
        if 'macd_histogram_entry' in df.columns and 'macd_signal_entry' in df.columns:
            # 避免除以零
            df['macd_strength_ratio'] = df['macd_histogram_entry'] / (abs(df['macd_signal_entry']) + 1e-6)
        else:
            df['macd_strength_ratio'] = 0
        
        # 5. 趨勢對齊度（三時間框架趨勢一致性）
        if all(col in df.columns for col in ['trend_1h_encoded', 'trend_15m_encoded', 'trend_5m_encoded']):
            # 計算趨勢一致性：如果三個都是1或都是-1，則為3；否則為各自絕對值之和
            df['trend_alignment_score'] = (
                df['trend_1h_encoded'] + 
                df['trend_15m_encoded'] + 
                df['trend_5m_encoded']
            )
        else:
            df['trend_alignment_score'] = 0
        
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
