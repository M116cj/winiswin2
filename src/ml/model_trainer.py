"""
XGBoost 模型訓練器（v3.4.0優化版）
職責：模型訓練、超參數優化、模型評估、增量學習、模型集成
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import pickle
import os
import logging
from datetime import datetime
import time

from src.config import Config
from src.ml.data_processor import MLDataProcessor
from src.ml.hyperparameter_tuner import HyperparameterTuner
from src.ml.adaptive_learner import AdaptiveLearner
from src.ml.ensemble_model import EnsembleModel
from src.ml.label_leakage_validator import LabelLeakageValidator
from src.ml.imbalance_handler import ImbalanceHandler
from src.ml.drift_detector import DriftDetector

logger = logging.getLogger(__name__)


class XGBoostTrainer:
    """XGBoost 模型訓練器（v3.4.0增強版）"""
    
    def __init__(self, use_tuning: bool = False, use_ensemble: bool = False):
        """
        初始化訓練器
        
        Args:
            use_tuning: 是否使用超參數調優
            use_ensemble: 是否使用模型集成
        """
        self.config = Config
        self.data_processor = MLDataProcessor()
        self.model = None
        self.model_path = "data/models/xgboost_model.pkl"
        self.metrics_path = "data/models/model_metrics.json"
        
        # ✨ v3.4.0新增：高級功能
        self.use_tuning = use_tuning
        self.use_ensemble = use_ensemble
        self.tuner = HyperparameterTuner() if use_tuning else None
        self.adaptive_learner = AdaptiveLearner()
        self.ensemble = EnsembleModel() if use_ensemble else None
        
        # 🚀 v3.9.0新增：優化功能
        self.leakage_validator = LabelLeakageValidator()
        self.imbalance_handler = ImbalanceHandler()
        self.drift_detector = DriftDetector(window_size=1000, drift_threshold=0.05)
        
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
    
    def train(
        self,
        params: Optional[Dict] = None,
        use_gpu: bool = True,
        incremental: bool = False
    ) -> Tuple[object, Dict]:
        """
        訓練 XGBoost 模型（v3.4.0增強版）
        
        Args:
            params: 模型參數
            use_gpu: 是否使用 GPU
            incremental: 是否使用增量學習
        
        Returns:
            Tuple[object, Dict]: (模型, 評估指標)
        """
        try:
            import xgboost as xgb
            from sklearn.metrics import (
                accuracy_score, precision_score, recall_score,
                f1_score, roc_auc_score, confusion_matrix
            )
            
            # ✨ v3.4.0：開始性能追蹤
            start_time = time.time()
            
            # 加載數據
            df = self.data_processor.load_training_data()
            
            min_samples = self.config.ML_MIN_TRAINING_SAMPLES
            if df.empty or len(df) < min_samples:
                logger.warning(f"訓練數據不足: {len(df)} 條記錄 (最少需要 {min_samples})")
                return None, {}
            
            # 🔍 v3.9.0：標籤泄漏驗證
            leakage_report = self.leakage_validator.validate_training_data(df)
            if leakage_report['has_leakage']:
                logger.warning(f"⚠️ 檢測到潛在標籤泄漏：{leakage_report['leakage_features']}")
            
            # 📊 v3.9.0：應用滑動窗口（防止舊數據影響過大）
            df = self.drift_detector.apply_sliding_window(df, window_size=1000)
            
            # 準備特徵
            X, y = self.data_processor.prepare_features(df)
            
            if X.empty or y.empty:
                logger.error("特徵準備失敗")
                return None, {}
            
            # 📊 v3.9.0：類別平衡分析
            balance_report = self.imbalance_handler.analyze_class_balance(y, X)
            
            # 🔍 v3.9.0：特徵分布漂移檢測
            drift_report = self.drift_detector.detect_feature_drift(
                X,
                X.columns.tolist(),
                update_baseline=True
            )
            
            # 分割數據
            X_train, X_test, y_train, y_test = self.data_processor.split_data(X, y)
            
            # 🛡️ v3.9.0：計算樣本權重（處理類別不平衡）
            sample_weights = None
            if balance_report.get('needs_balancing', False):
                logger.info("📊 檢測到類別不平衡，計算動態樣本權重...")
                sample_weights = self.imbalance_handler.calculate_sample_weight(y_train, method='balanced')
                
                # 同時結合時間衰減權重
                time_weights = self.drift_detector.calculate_sample_weights(
                    pd.DataFrame({'y': y_train}),
                    decay_factor=0.95
                )
                
                # 組合權重
                if sample_weights is not None:
                    sample_weights = sample_weights * time_weights
            
            # ✨ v3.4.0：超參數調優
            if params is None:
                if self.use_tuning and self.tuner:
                    logger.info("啟動超參數自動調優...")
                    params, _ = self.tuner.quick_tune(X_train, y_train, use_gpu)
                else:
                    # 默認參數
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
                    
                    # 🛡️ v3.9.0：添加成本感知參數（處理不平衡）
                    if balance_report.get('needs_balancing', False):
                        scale_pos_weight = self.imbalance_handler.get_scale_pos_weight(y_train)
                        params['scale_pos_weight'] = scale_pos_weight
                        logger.info(f"📊 啟用成本感知學習：scale_pos_weight = {scale_pos_weight:.2f}")
                    
                    # GPU 加速
                    if use_gpu:
                        if self._detect_gpu():
                            params['tree_method'] = 'gpu_hist'
                            params['predictor'] = 'gpu_predictor'
                            logger.info("✅ 使用 GPU 加速訓練")
                        else:
                            logger.warning("GPU 不可用，使用 CPU 訓練")
                            params['tree_method'] = 'hist'
                    else:
                        params['tree_method'] = 'hist'
            
            # ✨ v3.4.0：增量學習支持
            logger.info("開始訓練 XGBoost 模型...")
            logger.info(f"訓練集大小: {X_train.shape}, 測試集大小: {X_test.shape}")
            
            model = xgb.XGBClassifier(**params)
            
            # 增量學習：加載舊模型繼續訓練
            xgb_model_file = None
            temp_model_path = 'data/models/temp_xgb_model.json'
            
            if incremental and os.path.exists(self.model_path):
                try:
                    with open(self.model_path, 'rb') as f:
                        old_model = pickle.load(f)
                    
                    # 保存舊模型為JSON格式（XGBoost增量學習需要）
                    old_model.save_model(temp_model_path)
                    xgb_model_file = temp_model_path
                    
                    logger.info(f"✅ 增量學習啟用：基於舊模型繼續訓練")
                except Exception as e:
                    logger.warning(f"加載舊模型失敗，執行完整訓練: {e}")
                    xgb_model_file = None
            
            # 訓練（增量或完整）- 使用try-finally確保臨時文件清理
            try:
                if xgb_model_file:
                    # 增量學習（帶樣本權重）
                    if sample_weights is not None:
                        model.fit(
                            X_train, y_train,
                            sample_weight=sample_weights,
                            eval_set=[(X_train, y_train), (X_test, y_test)],
                            early_stopping_rounds=20,
                            verbose=False,
                            xgb_model=xgb_model_file  # ✨ 增量學習關鍵參數
                        )
                    else:
                        model.fit(
                            X_train, y_train,
                            eval_set=[(X_train, y_train), (X_test, y_test)],
                            early_stopping_rounds=20,
                            verbose=False,
                            xgb_model=xgb_model_file
                        )
                else:
                    # 完整訓練（帶樣本權重）
                    if sample_weights is not None:
                        model.fit(
                            X_train, y_train,
                            sample_weight=sample_weights,
                            eval_set=[(X_train, y_train), (X_test, y_test)],
                            early_stopping_rounds=20,
                            verbose=False
                        )
                    else:
                        model.fit(
                            X_train, y_train,
                            eval_set=[(X_train, y_train), (X_test, y_test)],
                            early_stopping_rounds=20,
                            verbose=False
                        )
            finally:
                # 清理臨時文件（確保即使訓練失敗也會清理）
                if xgb_model_file and os.path.exists(temp_model_path):
                    try:
                        os.remove(temp_model_path)
                        logger.debug("臨時模型文件已清理")
                    except:
                        pass
            
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
            
            # 📊 v3.9.0：詳細混淆矩陣報告（包含分方向評估）
            confusion_report = self.imbalance_handler.generate_confusion_matrix_report(
                y_test.values,
                y_pred,
                X_test
            )
            metrics['confusion_matrix_detailed'] = confusion_report
            
            # 保留原有混淆矩陣格式（向後兼容）
            cm = confusion_matrix(y_test, y_pred)
            metrics['confusion_matrix'] = cm.tolist()
            
            # 📊 v3.9.0：添加優化報告
            metrics['optimization_reports'] = {
                'label_leakage': leakage_report,
                'class_balance': balance_report,
                'feature_drift': drift_report
            }
            
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
            
            # ✨ v3.4.0：訓練性能追蹤
            training_time = time.time() - start_time
            metrics['training_time_seconds'] = training_time
            metrics['incremental'] = incremental
            logger.info(f"訓練耗時: {training_time:.2f}秒")
            
            # ✨ v3.4.0：自適應學習更新
            self.adaptive_learner.update_performance(
                metrics['accuracy'],
                datetime.now()
            )
            
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
    
    def _detect_gpu(self) -> bool:
        """
        檢測GPU是否可用（v3.4.0新增）
        
        Returns:
            bool: GPU是否可用
        """
        try:
            import subprocess
            subprocess.check_output(['nvidia-smi'])
            return True
        except:
            return False
    
    def train_with_ensemble(self, use_gpu: bool = True) -> Tuple[Optional[object], Dict]:
        """
        使用模型集成訓練（v3.4.0新增）
        
        Args:
            use_gpu: 是否使用GPU
        
        Returns:
            Tuple[Optional[object], Dict]: (集成模型, 評估指標)
        """
        if not self.use_ensemble or not self.ensemble:
            logger.warning("模型集成未啟用")
            return None, {}
        
        try:
            # 加載數據
            df = self.data_processor.load_training_data()
            X, y = self.data_processor.prepare_features(df)
            X_train, X_test, y_train, y_test = self.data_processor.split_data(X, y)
            
            # 訓練集成模型
            models, metrics = self.ensemble.train_ensemble(
                X_train, y_train,
                X_test, y_test,
                use_gpu=use_gpu
            )
            
            # 保存集成模型
            if models:
                self.ensemble.save()
            
            return self.ensemble, metrics
            
        except Exception as e:
            logger.error(f"集成模型訓練失敗: {e}", exc_info=True)
            return None, {}
