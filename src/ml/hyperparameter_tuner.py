"""
超参数调优器（v3.4.0）
职责：自动调优XGBoost超参数，提升模型性能
"""

import numpy as np
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class HyperparameterTuner:
    """超参数自动调优器"""
    
    def __init__(self):
        """初始化调优器"""
        self.best_params = None
        self.best_score = 0.0
        self.search_history = []
    
    def tune(
        self,
        X_train,
        y_train,
        n_iter: int = 20,
        cv: int = 5,
        n_jobs: int = 32,
        use_gpu: bool = False
    ) -> Tuple[Dict, float]:
        """
        使用随机搜索调优超参数
        
        Args:
            X_train: 训练特征
            y_train: 训练标签
            n_iter: 随机搜索迭代次数
            cv: 交叉验证折数
            n_jobs: 并行任务数
            use_gpu: 是否使用GPU
        
        Returns:
            Tuple[Dict, float]: (最佳参数, 最佳分数)
        """
        try:
            import xgboost as xgb
            from sklearn.model_selection import RandomizedSearchCV
            from scipy.stats import randint, uniform
            
            logger.info(f"开始超参数调优（迭代{n_iter}次，{cv}-fold CV）...")
            
            # 参数搜索空间
            param_dist = {
                'max_depth': randint(4, 11),                    # 4-10
                'learning_rate': uniform(0.01, 0.19),           # 0.01-0.2
                'n_estimators': randint(100, 401),              # 100-400
                'subsample': uniform(0.6, 0.3),                 # 0.6-0.9
                'colsample_bytree': uniform(0.6, 0.3),          # 0.6-0.9
                'min_child_weight': randint(1, 8),              # 1-7
                'gamma': uniform(0, 0.3),                       # 0-0.3
                'reg_alpha': uniform(0, 1.0),                   # 0-1.0
                'reg_lambda': uniform(0.5, 1.5)                 # 0.5-2.0
            }
            
            # 基础参数
            base_params = {
                'objective': 'binary:logistic',
                'eval_metric': 'auc',
                'random_state': 42,
                'n_jobs': 1  # RandomizedSearchCV会并行
            }
            
            # GPU加速
            if use_gpu:
                try:
                    base_params['tree_method'] = 'gpu_hist'
                    base_params['predictor'] = 'gpu_predictor'
                    logger.info("使用GPU加速调优")
                except:
                    logger.warning("GPU不可用，使用CPU")
                    base_params['tree_method'] = 'hist'
            else:
                base_params['tree_method'] = 'hist'
            
            # 创建基础模型
            base_model = xgb.XGBClassifier(**base_params)
            
            # 随机搜索
            random_search = RandomizedSearchCV(
                estimator=base_model,
                param_distributions=param_dist,
                n_iter=n_iter,
                scoring='roc_auc',
                cv=cv,
                n_jobs=n_jobs,
                verbose=1,
                random_state=42,
                return_train_score=True
            )
            
            # 执行搜索
            start_time = datetime.now()
            random_search.fit(X_train, y_train)
            duration = (datetime.now() - start_time).total_seconds()
            
            # 获取最佳参数
            self.best_params = random_search.best_params_
            self.best_score = random_search.best_score_
            
            # 合并基础参数
            final_params = {**base_params, **self.best_params}
            
            # 记录搜索历史
            self.search_history.append({
                'timestamp': datetime.now().isoformat(),
                'best_params': self.best_params,
                'best_score': self.best_score,
                'cv_results': random_search.cv_results_,
                'duration_seconds': duration
            })
            
            # 输出结果
            logger.info("=" * 60)
            logger.info("✅ 超参数调优完成")
            logger.info(f"   调优耗时: {duration:.2f}秒")
            logger.info(f"   最佳ROC-AUC: {self.best_score:.4f}")
            logger.info("   最佳参数:")
            for param, value in self.best_params.items():
                logger.info(f"     {param}: {value}")
            logger.info("=" * 60)
            
            return final_params, self.best_score
            
        except ImportError:
            logger.error("缺少依赖: xgboost, scikit-learn, scipy")
            return {}, 0.0
        except Exception as e:
            logger.error(f"超参数调优失败: {e}", exc_info=True)
            return {}, 0.0
    
    def quick_tune(
        self,
        X_train,
        y_train,
        use_gpu: bool = False
    ) -> Tuple[Dict, float]:
        """
        快速调优（较少迭代，适合生产环境）
        
        Args:
            X_train: 训练特征
            y_train: 训练标签
            use_gpu: 是否使用GPU
        
        Returns:
            Tuple[Dict, float]: (最佳参数, 最佳分数)
        """
        logger.info("执行快速调优（10次迭代，3-fold CV）...")
        return self.tune(
            X_train, y_train,
            n_iter=10,
            cv=3,
            n_jobs=32,
            use_gpu=use_gpu
        )
    
    def get_search_history(self) -> list:
        """
        获取搜索历史
        
        Returns:
            list: 搜索历史记录
        """
        return self.search_history
