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
        
        # 🚀 v3.9.0新增：優化功能（默認全部啟用）
        self.leakage_validator = LabelLeakageValidator()
        self.imbalance_handler = ImbalanceHandler()
        self.drift_detector = DriftDetector(
            window_size=1000,
            drift_threshold=0.05,
            enable_dynamic_window=True,      # 動態窗口調整
            enable_multivariate_drift=True   # 多變量漂移檢測（MMD）
        )
        
        # 🎯 默認使用risk_adjusted目標（風險調整後收益）
        from src.ml.target_optimizer import TargetOptimizer
        from src.ml.uncertainty_quantifier import UncertaintyQuantifier
        from src.ml.feature_importance_monitor import FeatureImportanceMonitor
        
        self.target_optimizer = TargetOptimizer(target_type='risk_adjusted')
        self.uncertainty_quantifier = UncertaintyQuantifier()  # Quantile Regression
        self.importance_monitor = FeatureImportanceMonitor()
        
        # 🎯 v3.9.2.8.5: 質量權重計算器（給完美交易更高權重）
        from src.managers.model_scorer import ModelScorer
        self.model_scorer = ModelScorer(history_limit=100)
        
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
            
            # 📊 v3.9.1：應用動態滑動窗口（波動率自適應 500-2000）
            df = self.drift_detector.apply_sliding_window(df)  # 不傳window_size，使用動態計算
            
            # 🎯 v3.9.1：準備risk_adjusted目標變量（替代二分類）
            y, target_meta = self.target_optimizer.prepare_target(df)
            logger.info(f"📊 目標類型：{target_meta.get('target_type', 'unknown')}")
            
            # 準備特徵（不包含目標）
            X, _ = self.data_processor.prepare_features(df)
            
            # 只保留數值特徵（與目標對齊）
            X = X.loc[y.index]
            
            if X.empty or y.empty:
                logger.error("特徵準備失敗")
                return None, {}
            
            # 📊 v3.9.1：類別平衡分析（僅二分類模式）
            balance_report = {}
            is_classification = self.target_optimizer.target_type == 'binary'
            
            if is_classification:
                balance_report = self.imbalance_handler.analyze_class_balance(y, X)
            else:
                # 回歸模式：跳過類別平衡檢查
                balance_report = {'needs_balancing': False, 'class_distribution': {}}
            
            # 🔍 v3.9.0：特徵分布漂移檢測
            drift_report = self.drift_detector.detect_feature_drift(
                X,
                X.columns.tolist(),
                update_baseline=True
            )
            
            # 分割數據
            X_train, X_test, y_train, y_test = self.data_processor.split_data(X, y)
            
            # 🛡️ v3.9.1：計算樣本權重（分類：類別權重，回歸：時間權重）
            sample_weights = None
            
            if is_classification and balance_report.get('needs_balancing', False):
                logger.info("📊 分類模式：計算類別平衡權重...")
                sample_weights = self.imbalance_handler.calculate_sample_weight(y_train, method='balanced')
            
            # 所有模式：應用時間衰減權重（新數據權重更高）
            time_weights = self.drift_detector.calculate_sample_weights(
                pd.DataFrame({'y': y_train}),
                decay_factor=0.95
            )
            
            if sample_weights is not None:
                sample_weights = sample_weights * time_weights
            else:
                sample_weights = time_weights
            
            # 🎯 v3.9.2.8.5：應用質量權重（給完美交易更高權重）
            try:
                quality_weights = self._calculate_quality_weights(df, np.array(X_train.index.values))
                sample_weights = sample_weights * quality_weights
                logger.info(
                    f"✅ 已應用質量權重（完美交易3.0x，優秀交易2.0x，良好交易1.5x）"
                )
            except Exception as e:
                logger.warning(f"質量權重計算失敗，繼續使用基礎權重: {e}")
            
            logger.info(f"📊 最終樣本權重：min={sample_weights.min():.3f}, max={sample_weights.max():.3f}, mean={sample_weights.mean():.3f}")
            
            # ✨ v3.4.0：超參數調優
            if params is None:
                if self.use_tuning and self.tuner:
                    logger.info("啟動超參數自動調優...")
                    params, _ = self.tuner.quick_tune(X_train, y_train, use_gpu)
                else:
                    # 🎯 v3.9.1：根據目標類型設置默認參數
                    # 🎯 v3.9.2.9: 動態檢測CPU核心數（提升可移植性）
                    import multiprocessing
                    available_cores = multiprocessing.cpu_count()
                    n_jobs = min(available_cores, 32)  # 最多使用32核心
                    logger.info(f"💻 檢測到{available_cores}個CPU核心，使用{n_jobs}個進行訓練")
                    
                    base_params = {
                        'max_depth': 6,
                        'learning_rate': 0.1,
                        'n_estimators': 200,
                        'subsample': 0.8,
                        'colsample_bytree': 0.8,
                        'min_child_weight': 1,
                        'gamma': 0.1,
                        'reg_alpha': 0.1,
                        'reg_lambda': 1.0,
                        'random_state': 42,
                        'n_jobs': n_jobs  # 動態設置
                    }
                    
                    # 根據目標類型調整objective和eval_metric
                    params = self.target_optimizer.get_model_params(base_params)
                    logger.info(f"📊 模型參數：objective={params['objective']}, eval_metric={params['eval_metric']}")
                    
                    # 🛡️ v3.9.1：分類模式才添加成本感知參數
                    if is_classification and balance_report.get('needs_balancing', False):
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
            
            # ✨ v3.9.1：根據目標類型選擇模型
            logger.info("開始訓練 XGBoost 模型...")
            logger.info(f"訓練集大小: {X_train.shape}, 測試集大小: {X_test.shape}")
            
            if is_classification:
                model = xgb.XGBClassifier(**params)
            else:
                # 回歸模型（用於risk_adjusted和pnl_pct）
                model = xgb.XGBRegressor(**params)
            
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
                # 🎯 v3.9.2.9: 強化臨時文件清理日誌（避免累積臨時文件）
                if xgb_model_file and os.path.exists(temp_model_path):
                    try:
                        os.remove(temp_model_path)
                        logger.debug("✅ 臨時模型文件已清理")
                    except Exception as cleanup_error:
                        logger.warning(f"⚠️ 臨時模型文件清理失敗: {cleanup_error}")
                        logger.warning(f"   請手動刪除: {temp_model_path}")
            
            # 預測
            y_pred = model.predict(X_test)
            
            # ✨ v3.9.2.2：特徵重要性分析
            feature_importance_df = self._analyze_feature_importance(model, X_train)
            
            # ✨ v3.9.2.2：綜合評估（僅分類模式）
            if is_classification:
                y_pred_proba = model.predict_proba(X_test)[:, 1]
                
                # 計算額外評估指標
                from sklearn.metrics import average_precision_score
                avg_precision = average_precision_score(y_test, y_pred_proba)
                
                logger.info(f"\n📊 綜合評估：")
                logger.info(f"Average Precision: {avg_precision:.4f}")
                
                # 🎯 v3.9.2.9: 不同閾值表現（zero_division=0更可預測）
                logger.info(f"\n🎯 不同閾值下的表現：")
                for threshold in [0.3, 0.4, 0.5, 0.6, 0.7]:
                    y_pred_thresh = (y_pred_proba >= threshold).astype(int)
                    prec = precision_score(y_test, y_pred_thresh, zero_division=0)
                    rec = recall_score(y_test, y_pred_thresh, zero_division=0)
                    logger.info(f"  閾值{threshold:.1f}: Precision={prec:.3f}, Recall={rec:.3f}")
            
            # 🎯 v3.9.1：根據目標類型評估
            metrics = {
                'training_samples': len(df),
                'train_set_size': len(X_train),
                'test_set_size': len(X_test),
                'trained_at': datetime.now().isoformat(),
                'target_type': self.target_optimizer.target_type
            }
            
            if is_classification:
                # 分類評估
                y_pred_proba = model.predict_proba(X_test)[:, 1]
                
                # 🎯 v3.9.2.9: zero_division=0更可預測（避免警告噪音）
                metrics.update({
                    'accuracy': float(accuracy_score(y_test, y_pred)),
                    'precision': float(precision_score(y_test, y_pred, zero_division=0)),
                    'recall': float(recall_score(y_test, y_pred, zero_division=0)),
                    'f1_score': float(f1_score(y_test, y_pred, zero_division=0)),
                    'roc_auc': float(roc_auc_score(y_test, y_pred_proba))
                })
                
                # 混淆矩陣報告
                confusion_report = self.imbalance_handler.generate_confusion_matrix_report(
                    y_test.values,
                    y_pred,
                    X_test
                )
                metrics['confusion_matrix_detailed'] = confusion_report
                
                cm = confusion_matrix(y_test, y_pred)
                metrics['confusion_matrix'] = cm.tolist()
            else:
                # 回歸評估（risk_adjusted / pnl_pct）
                from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
                import numpy as np
                
                mae = mean_absolute_error(y_test, y_pred)
                mse = mean_squared_error(y_test, y_pred)
                rmse = np.sqrt(mse)
                r2 = r2_score(y_test, y_pred)
                
                # 方向準確率（預測符號是否正確）
                direction_accuracy = np.mean(np.sign(y_test) == np.sign(y_pred))
                
                metrics.update({
                    'mae': float(mae),
                    'mse': float(mse),
                    'rmse': float(rmse),
                    'r2_score': float(r2),
                    'direction_accuracy': float(direction_accuracy)
                })
            
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
            logger.info(f"模型訓練完成（目標類型：{self.target_optimizer.target_type}）")
            
            if is_classification:
                logger.info(f"準確率: {metrics['accuracy']:.4f}")
                logger.info(f"精確率: {metrics['precision']:.4f}")
                logger.info(f"召回率: {metrics['recall']:.4f}")
                logger.info(f"F1 分數: {metrics['f1_score']:.4f}")
                logger.info(f"ROC-AUC: {metrics['roc_auc']:.4f}")
            else:
                logger.info(f"MAE: {metrics['mae']:.4f}")
                logger.info(f"RMSE: {metrics['rmse']:.4f}")
                logger.info(f"R² Score: {metrics['r2_score']:.4f}")
                logger.info(f"方向準確率: {metrics['direction_accuracy']:.4f} ({metrics['direction_accuracy']*100:.1f}%)")
            
            # ✨ v3.4.0：訓練性能追蹤
            training_time = time.time() - start_time
            metrics['training_samples'] = len(df)
            metrics['training_time_seconds'] = training_time
            metrics['incremental'] = incremental
            logger.info(f"訓練耗時: {training_time:.2f}秒")
            
            # ✨ v3.9.1：自適應學習更新（根據目標類型選擇指標）
            if is_classification:
                # 分類模式：使用準確率
                performance_metric = metrics.get('accuracy', 0.0)
            else:
                # 回歸模式：使用方向準確率（0-1範圍）
                performance_metric = metrics.get('direction_accuracy', 0.0)
            
            self.adaptive_learner.update_performance(
                performance_metric,
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
    
    def _calculate_quality_weights(self, df: pd.DataFrame, train_indices: np.ndarray) -> np.ndarray:
        """
        🎯 v3.9.2.8.5: 計算基於模型評分的質量權重
        給100分的完美交易（盈利+高置信度）更高的訓練權重
        
        Args:
            df: 完整的訓練數據DataFrame
            train_indices: 訓練集索引
        
        Returns:
            np.ndarray: 質量權重數組（長度等於訓練集大小）
        """
        try:
            # 只處理訓練集樣本
            train_df = df.iloc[train_indices].copy()
            
            # 初始化權重為1.0
            quality_weights = np.ones(len(train_df))
            
            # 檢查必需欄位是否存在
            required_cols = ['pnl', 'confidence_score']
            if not all(col in train_df.columns for col in required_cols):
                logger.warning("缺少pnl或confidence_score欄位，無法計算質量權重")
                return quality_weights
            
            # 計算每個樣本的模型評分
            for idx, row in enumerate(train_df.itertuples()):
                try:
                    pnl_pct = row.pnl * 100  # 轉換為百分比
                    confidence = row.confidence_score
                    
                    # 使用ModelScorer的評分邏輯（不需要胜率）
                    # PnL分數（50%權重）
                    if pnl_pct > 0:
                        pnl_score = min(100, (pnl_pct / 10) * 100)  # 10%收益 = 100分
                    else:
                        pnl_score = max(0, 50 + pnl_pct * 5)  # -10%虧損 = 0分
                    
                    # 置信度準確性分數（30%權重）
                    is_profit = pnl_pct > 0
                    is_high_conf = confidence >= 0.7
                    
                    if is_profit and is_high_conf:
                        conf_score = 100  # 完美預測
                    elif is_profit and not is_high_conf:
                        conf_score = 70   # 幸運
                    elif not is_profit and is_high_conf:
                        conf_score = 20   # 誤判
                    else:
                        conf_score = 50   # 符合預期
                    
                    # 計算總評分（不考慮胜率，因為訓練時胜率不穩定）
                    score = (pnl_score * 0.5) + (conf_score * 0.5)
                    
                    # 🎯 根據評分調整權重
                    if score >= 95:
                        # 95-100分（完美交易）：3.0倍權重
                        quality_weights[idx] = 3.0
                    elif score >= 85:
                        # 85-94分（優秀交易）：2.0倍權重
                        quality_weights[idx] = 2.0
                    elif score >= 70:
                        # 70-84分（良好交易）：1.5倍權重
                        quality_weights[idx] = 1.5
                    elif score >= 50:
                        # 50-69分（一般交易）：1.0倍權重
                        quality_weights[idx] = 1.0
                    else:
                        # <50分（低質量交易）：0.5倍權重
                        quality_weights[idx] = 0.5
                
                except Exception as e:
                    # 🎯 v3.9.2.9: 提升錯誤日誌級別（發現數據質量問題）
                    logger.warning(f"⚠️ 計算第{idx}個樣本質量權重失敗: {e}，使用默認權重1.0")
                    quality_weights[idx] = 1.0
            
            # 統計質量權重分布
            perfect_count = np.sum(quality_weights >= 3.0)
            excellent_count = np.sum((quality_weights >= 2.0) & (quality_weights < 3.0))
            good_count = np.sum((quality_weights >= 1.5) & (quality_weights < 2.0))
            
            logger.info(
                f"📊 質量權重分布：完美交易(3.0x)={perfect_count}, "
                f"優秀交易(2.0x)={excellent_count}, "
                f"良好交易(1.5x)={good_count}"
            )
            
            return quality_weights
            
        except Exception as e:
            logger.error(f"計算質量權重失敗: {e}", exc_info=True)
            return np.ones(len(train_indices))
    
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

    
    def _analyze_feature_importance(self, model, X: pd.DataFrame) -> pd.DataFrame:
        """分析特徵重要性（v3.9.2.2新增）"""
        try:
            importance = model.feature_importances_
            feature_importance = pd.DataFrame({
                "feature": X.columns,
                "importance": importance
            }).sort_values("importance", ascending=False)
            
            top_3_sum = feature_importance.head(3)["importance"].sum()
            top_5_sum = feature_importance.head(5)["importance"].sum()
            
            logger.info("\n" + "=" * 60)
            logger.info("📊 特徵重要性分析（v3.9.2.2）")
            logger.info("=" * 60)
            logger.info(f"前3個特徵重要性：{top_3_sum:.1%}")
            logger.info(f"前5個特徵重要性：{top_5_sum:.1%}")
            
            if top_3_sum > 0.7:
                logger.warning(f"⚠️  特徵過度集中：前3個特徵占{top_3_sum:.1%}")
            else:
                logger.info("✅ 特徵重要性分布合理")
            
            logger.info("\n前10重要特徵：")
            for idx, row in feature_importance.head(10).iterrows():
                logger.info(f"  {row['feature']:30s}: {row['importance']:.4f}")
            logger.info("=" * 60 + "\n")
            
            return feature_importance
        except Exception as e:
            logger.error(f"特徵重要性分析失敗: {e}")
            return pd.DataFrame()

