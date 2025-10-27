"""
模型集成系统（v3.4.0）
职责：组合多个模型提升预测性能和鲁棒性
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
import pickle
import os

logger = logging.getLogger(__name__)


class EnsembleModel:
    """模型集成管理器"""
    
    def __init__(self, models_dir: str = 'data/models'):
        """
        初始化模型集成
        
        Args:
            models_dir: 模型保存目录
        """
        self.models_dir = models_dir
        self.models = {}
        self.weights = {}
        self.is_ready = False
        
        os.makedirs(models_dir, exist_ok=True)
    
    def train_ensemble(
        self,
        X_train,
        y_train,
        X_test,
        y_test,
        use_gpu: bool = False
    ) -> Tuple[Dict, Dict]:
        """
        训练集成模型
        
        Args:
            X_train: 训练特征
            y_train: 训练标签
            X_test: 测试特征
            y_test: 测试标签
            use_gpu: 是否使用GPU
        
        Returns:
            Tuple[Dict, Dict]: (模型字典, 性能指标)
        """
        try:
            from sklearn.metrics import accuracy_score, roc_auc_score
            
            logger.info("开始训练集成模型...")
            
            models = {}
            metrics = {}
            
            # 1. 训练XGBoost（主模型）
            xgb_model, xgb_metrics = self._train_xgboost(
                X_train, y_train, X_test, y_test, use_gpu
            )
            if xgb_model is not None:
                models['xgboost'] = xgb_model
                metrics['xgboost'] = xgb_metrics
            
            # 2. 训练LightGBM（轻量级）
            lgb_model, lgb_metrics = self._train_lightgbm(
                X_train, y_train, X_test, y_test, use_gpu
            )
            if lgb_model is not None:
                models['lightgbm'] = lgb_model
                metrics['lightgbm'] = lgb_metrics
            
            # 3. 训练CatBoost（类别特征优化）
            cat_model, cat_metrics = self._train_catboost(
                X_train, y_train, X_test, y_test, use_gpu
            )
            if cat_model is not None:
                models['catboost'] = cat_model
                metrics['catboost'] = cat_metrics
            
            # 计算权重（基于验证集性能）
            self.weights = self._calculate_weights(metrics)
            
            self.models = models
            self.is_ready = len(models) > 0
            
            # 集成预测评估
            if len(models) > 1:
                ensemble_metrics = self._evaluate_ensemble(X_test, y_test)
                metrics['ensemble'] = ensemble_metrics
            
            logger.info("=" * 60)
            logger.info("✅ 集成模型训练完成")
            logger.info(f"   训练模型数: {len(models)}")
            for name, weight in self.weights.items():
                logger.info(f"   {name}: 权重={weight:.3f}, 准确率={metrics[name]['accuracy']:.4f}")
            if 'ensemble' in metrics:
                logger.info(f"   集成准确率: {metrics['ensemble']['accuracy']:.4f}")
            logger.info("=" * 60)
            
            return models, metrics
            
        except Exception as e:
            logger.error(f"训练集成模型失败: {e}", exc_info=True)
            return {}, {}
    
    def _train_xgboost(
        self,
        X_train,
        y_train,
        X_test,
        y_test,
        use_gpu: bool
    ) -> Tuple[Optional[Any], Dict]:
        """训练XGBoost模型"""
        try:
            import xgboost as xgb
            from sklearn.metrics import accuracy_score, roc_auc_score
            
            params = {
                'max_depth': 6,
                'learning_rate': 0.1,
                'n_estimators': 200,
                'objective': 'binary:logistic',
                'eval_metric': 'auc',
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42,
                'n_jobs': -1
            }
            
            if use_gpu:
                try:
                    params['tree_method'] = 'gpu_hist'
                    params['predictor'] = 'gpu_predictor'
                except:
                    params['tree_method'] = 'hist'
            else:
                params['tree_method'] = 'hist'
            
            model = xgb.XGBClassifier(**params)
            model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
            
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)[:, 1]
            
            metrics = {
                'accuracy': float(accuracy_score(y_test, y_pred)),
                'roc_auc': float(roc_auc_score(y_test, y_pred_proba))
            }
            
            logger.info(f"XGBoost训练完成: 准确率={metrics['accuracy']:.4f}")
            return model, metrics
            
        except ImportError:
            logger.warning("XGBoost未安装，跳过")
            return None, {}
        except Exception as e:
            logger.error(f"XGBoost训练失败: {e}")
            return None, {}
    
    def _train_lightgbm(
        self,
        X_train,
        y_train,
        X_test,
        y_test,
        use_gpu: bool
    ) -> Tuple[Optional[Any], Dict]:
        """训练LightGBM模型"""
        try:
            import lightgbm as lgb
            from sklearn.metrics import accuracy_score, roc_auc_score
            
            params = {
                'max_depth': 6,
                'learning_rate': 0.1,
                'n_estimators': 200,
                'objective': 'binary',
                'metric': 'auc',
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42,
                'n_jobs': -1,
                'verbose': -1
            }
            
            if use_gpu:
                params['device'] = 'gpu'
            
            model = lgb.LGBMClassifier(**params)
            model.fit(X_train, y_train, eval_set=[(X_test, y_test)])
            
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)[:, 1]
            
            metrics = {
                'accuracy': float(accuracy_score(y_test, y_pred)),
                'roc_auc': float(roc_auc_score(y_test, y_pred_proba))
            }
            
            logger.info(f"LightGBM训练完成: 准确率={metrics['accuracy']:.4f}")
            return model, metrics
            
        except ImportError:
            logger.warning("LightGBM未安装，跳过")
            return None, {}
        except Exception as e:
            logger.error(f"LightGBM训练失败: {e}")
            return None, {}
    
    def _train_catboost(
        self,
        X_train,
        y_train,
        X_test,
        y_test,
        use_gpu: bool
    ) -> Tuple[Optional[Any], Dict]:
        """训练CatBoost模型"""
        try:
            from catboost import CatBoostClassifier
            from sklearn.metrics import accuracy_score, roc_auc_score
            
            params = {
                'depth': 6,
                'learning_rate': 0.1,
                'iterations': 200,
                'loss_function': 'Logloss',
                'eval_metric': 'AUC',
                'random_seed': 42,
                'verbose': False
            }
            
            if use_gpu:
                params['task_type'] = 'GPU'
            
            model = CatBoostClassifier(**params)
            model.fit(X_train, y_train, eval_set=(X_test, y_test))
            
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)[:, 1]
            
            metrics = {
                'accuracy': float(accuracy_score(y_test, y_pred)),
                'roc_auc': float(roc_auc_score(y_test, y_pred_proba))
            }
            
            logger.info(f"CatBoost训练完成: 准确率={metrics['accuracy']:.4f}")
            return model, metrics
            
        except ImportError:
            logger.warning("CatBoost未安装，跳过")
            return None, {}
        except Exception as e:
            logger.error(f"CatBoost训练失败: {e}")
            return None, {}
    
    def _calculate_weights(self, metrics: Dict) -> Dict:
        """根据性能计算模型权重"""
        weights = {}
        total_score = 0.0
        
        # 使用ROC-AUC计算权重
        for name, metric in metrics.items():
            score = metric.get('roc_auc', 0.0)
            weights[name] = score
            total_score += score
        
        # 归一化
        if total_score > 0:
            weights = {k: v / total_score for k, v in weights.items()}
        
        return weights
    
    def predict_proba(self, X) -> np.ndarray:
        """
        集成预测概率
        
        Args:
            X: 特征
        
        Returns:
            np.ndarray: 预测概率
        """
        if not self.is_ready or not self.models:
            raise ValueError("集成模型未就绪")
        
        predictions = []
        weights = []
        
        for name, model in self.models.items():
            try:
                proba = model.predict_proba(X)[:, 1]
                predictions.append(proba)
                weights.append(self.weights.get(name, 1.0 / len(self.models)))
            except Exception as e:
                logger.warning(f"模型 {name} 预测失败: {e}")
        
        if not predictions:
            raise ValueError("所有模型预测失败")
        
        # 加权平均
        ensemble_proba = np.average(predictions, axis=0, weights=weights)
        return ensemble_proba
    
    def _evaluate_ensemble(self, X_test, y_test) -> Dict:
        """评估集成模型"""
        from sklearn.metrics import accuracy_score, roc_auc_score
        
        proba = self.predict_proba(X_test)
        pred = (proba >= 0.5).astype(int)
        
        return {
            'accuracy': float(accuracy_score(y_test, pred)),
            'roc_auc': float(roc_auc_score(y_test, proba))
        }
    
    def save(self, filename: str = 'ensemble_model.pkl'):
        """保存集成模型"""
        filepath = os.path.join(self.models_dir, filename)
        
        try:
            with open(filepath, 'wb') as f:
                pickle.dump({
                    'models': self.models,
                    'weights': self.weights
                }, f)
            logger.info(f"集成模型已保存: {filepath}")
        except Exception as e:
            logger.error(f"保存集成模型失败: {e}")
    
    def load(self, filename: str = 'ensemble_model.pkl') -> bool:
        """加载集成模型"""
        filepath = os.path.join(self.models_dir, filename)
        
        try:
            if not os.path.exists(filepath):
                logger.warning(f"集成模型不存在: {filepath}")
                return False
            
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            self.models = data['models']
            self.weights = data['weights']
            self.is_ready = True
            
            logger.info(f"集成模型已加载: {len(self.models)} 个模型")
            return True
        except Exception as e:
            logger.error(f"加载集成模型失败: {e}")
            return False
