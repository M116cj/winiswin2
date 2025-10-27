"""
XGBoost 模型訓練器
職責：模型訓練、超參數優化、模型評估
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import pickle
import os
import logging
from datetime import datetime

from src.config import Config
from src.ml.data_processor import MLDataProcessor

logger = logging.getLogger(__name__)


class XGBoostTrainer:
    """XGBoost 模型訓練器"""
    
    def __init__(self):
        """初始化訓練器"""
        self.config = Config
        self.data_processor = MLDataProcessor()
        self.model = None
        self.model_path = "data/models/xgboost_model.pkl"
        self.metrics_path = "data/models/model_metrics.json"
        
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
    
    def train(
        self,
        params: Optional[Dict] = None,
        use_gpu: bool = True
    ) -> Tuple[object, Dict]:
        """
        訓練 XGBoost 模型
        
        Args:
            params: 模型參數
            use_gpu: 是否使用 GPU
        
        Returns:
            Tuple[object, Dict]: (模型, 評估指標)
        """
        try:
            import xgboost as xgb
            from sklearn.metrics import (
                accuracy_score, precision_score, recall_score,
                f1_score, roc_auc_score, confusion_matrix
            )
            
            # 加載數據
            df = self.data_processor.load_training_data()
            
            min_samples = self.config.ML_MIN_TRAINING_SAMPLES
            if df.empty or len(df) < min_samples:
                logger.warning(f"訓練數據不足: {len(df)} 條記錄 (最少需要 {min_samples})")
                return None, {}
            
            # 準備特徵
            X, y = self.data_processor.prepare_features(df)
            
            if X.empty or y.empty:
                logger.error("特徵準備失敗")
                return None, {}
            
            # 分割數據
            X_train, X_test, y_train, y_test = self.data_processor.split_data(X, y)
            
            # 默認參數
            if params is None:
                params = {
                    'max_depth': 6,
                    'learning_rate': 0.1,
                    'n_estimators': 200,
                    'objective': 'binary:logistic',
                    'eval_metric': 'auc',
                    'subsample': 0.8,
                    'colsample_bytree': 0.8,
                    'min_child_weight': 1,
                    'gamma': 0.1,
                    'reg_alpha': 0.1,
                    'reg_lambda': 1.0,
                    'random_state': 42,
                    'n_jobs': 32  # 使用 32 核心
                }
                
                # GPU 加速
                if use_gpu:
                    try:
                        params['tree_method'] = 'gpu_hist'
                        params['predictor'] = 'gpu_predictor'
                        logger.info("使用 GPU 加速訓練")
                    except:
                        logger.warning("GPU 不可用，使用 CPU 訓練")
                        params['tree_method'] = 'hist'
            
            # 訓練模型
            logger.info("開始訓練 XGBoost 模型...")
            logger.info(f"訓練集大小: {X_train.shape}, 測試集大小: {X_test.shape}")
            
            model = xgb.XGBClassifier(**params)
            
            model.fit(
                X_train, y_train,
                eval_set=[(X_train, y_train), (X_test, y_test)],
                early_stopping_rounds=20,
                verbose=False
            )
            
            # 預測
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)[:, 1]
            
            # 評估指標
            metrics = {
                'training_samples': len(df),  # ✨ 保存總訓練樣本數（用於持續訓練）
                'accuracy': float(accuracy_score(y_test, y_pred)),
                'precision': float(precision_score(y_test, y_pred, zero_division='warn')),
                'recall': float(recall_score(y_test, y_pred, zero_division='warn')),
                'f1_score': float(f1_score(y_test, y_pred, zero_division='warn')),
                'roc_auc': float(roc_auc_score(y_test, y_pred_proba)),
                'train_set_size': len(X_train),
                'test_set_size': len(X_test),
                'trained_at': datetime.now().isoformat()
            }
            
            # 混淆矩陣
            cm = confusion_matrix(y_test, y_pred)
            metrics['confusion_matrix'] = cm.tolist()
            
            # 特徵重要性
            feature_importance = self.data_processor.get_feature_importance(
                model,
                X.columns.tolist()
            )
            metrics['feature_importance'] = feature_importance
            
            logger.info("=" * 60)
            logger.info("模型訓練完成")
            logger.info(f"準確率: {metrics['accuracy']:.4f}")
            logger.info(f"精確率: {metrics['precision']:.4f}")
            logger.info(f"召回率: {metrics['recall']:.4f}")
            logger.info(f"F1 分數: {metrics['f1_score']:.4f}")
            logger.info(f"ROC-AUC: {metrics['roc_auc']:.4f}")
            logger.info("=" * 60)
            
            self.model = model
            
            return model, metrics
            
        except ImportError:
            logger.error("XGBoost 或 scikit-learn 未安裝")
            return None, {}
        except Exception as e:
            logger.error(f"訓練模型失敗: {e}", exc_info=True)
            return None, {}
    
    def save_model(self, model, metrics: Dict):
        """
        保存模型和指標
        
        Args:
            model: 訓練好的模型
            metrics: 評估指標
        """
        try:
            # 保存模型
            with open(self.model_path, 'wb') as f:
                pickle.dump(model, f)
            logger.info(f"模型已保存: {self.model_path}")
            
            # 保存指標
            import json
            with open(self.metrics_path, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, ensure_ascii=False, indent=2)
            logger.info(f"指標已保存: {self.metrics_path}")
            
        except Exception as e:
            logger.error(f"保存模型失敗: {e}")
    
    def load_model(self) -> Optional[object]:
        """
        加載已訓練的模型
        
        Returns:
            Optional[object]: 模型對象
        """
        try:
            if not os.path.exists(self.model_path):
                logger.warning(f"模型文件不存在: {self.model_path}")
                return None
            
            with open(self.model_path, 'rb') as f:
                model = pickle.load(f)
            
            logger.info(f"模型已加載: {self.model_path}")
            self.model = model
            
            return model
            
        except Exception as e:
            logger.error(f"加載模型失敗: {e}")
            return None
    
    def auto_train_if_needed(self, min_samples: int = 100) -> bool:
        """
        如果有足夠數據則自動訓練模型
        
        Args:
            min_samples: 最小訓練樣本數
        
        Returns:
            bool: 是否成功訓練
        """
        try:
            df = self.data_processor.load_training_data()
            
            if len(df) < min_samples:
                logger.info(f"訓練數據不足: {len(df)}/{min_samples} (配置: ML_MIN_TRAINING_SAMPLES)")
                return False
            
            logger.info(f"檢測到 {len(df)} 條訓練數據，開始自動訓練...")
            
            model, metrics = self.train()
            
            if model is not None:
                self.save_model(model, metrics)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"自動訓練失敗: {e}")
            return False
