"""
🔥 v4.0 ML模型包装器 (Pure ICT/SMC + Unified Schema)
职责：加载XGBoost模型并提供预测接口
v4.0更新：使用统一的12个ICT/SMC特征（与训练一致）
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict
import numpy as np
from src.ml.feature_schema import CANONICAL_FEATURE_NAMES, features_to_vector

logger = logging.getLogger(__name__)


class MLModelWrapper:
    """
    ML模型包装器（v4.0 Pure ICT/SMC + Unified Schema）
    
    职责：
    1. 加载训练好的XGBoost模型
    2. 提供12个ICT/SMC特征的预测接口（与训练一致）
    3. 处理模型不存在的fallback
    """
    
    def __init__(self, model_path: str = "models/xgboost_model.json"):
        """
        初始化ML模型包装器
        
        Args:
            model_path: 模型文件路径
        """
        self.model_path = Path(model_path)
        self.model = None
        self.is_loaded = False
        
        # 尝试加载模型
        self._load_model()
    
    def _load_model(self) -> bool:
        """
        加载XGBoost模型
        
        Returns:
            是否成功加载
        """
        if not self.model_path.exists():
            logger.warning(f"⚠️ ML模型不存在: {self.model_path}")
            logger.info("   将使用规则引擎作为fallback")
            return False
        
        try:
            import xgboost as xgb
            
            # 加载模型
            self.model = xgb.Booster()
            self.model.load_model(str(self.model_path))
            
            self.is_loaded = True
            
            model_size = os.path.getsize(self.model_path) / 1024
            logger.info("=" * 60)
            logger.info(f"✅ ML模型已加载: {self.model_path}")
            logger.info(f"   模型大小: {model_size:.2f} KB")
            logger.info(f"   🔥 v3.19：使用12个ICT/SMC特征进行预测")
            logger.info("=" * 60)
            
            return True
            
        except ImportError:
            logger.error("❌ XGBoost未安装，无法加载模型")
            logger.info("   请运行: pip install xgboost")
            return False
        except Exception as e:
            logger.error(f"❌ 加载模型失败: {e}")
            return False
    
    def predict(self, features: List[float]) -> Optional[float]:
        """
        预测获胜概率
        
        Args:
            features: 12个ICT/SMC特征的数值列表
        
        Returns:
            获胜概率（0-1），或None（如果模型未加载）
        """
        if not self.is_loaded or self.model is None:
            return None
        
        try:
            import xgboost as xgb
            
            # 验证特征数量
            if len(features) != 12:
                logger.warning(f"⚠️ 特征数量错误: {len(features)} != 12")
                return None
            
            # 创建DMatrix
            dmatrix = xgb.DMatrix([features])
            
            # 预测
            prediction = self.model.predict(dmatrix)[0]
            
            return float(prediction)
            
        except Exception as e:
            logger.error(f"❌ 预测失败: {e}")
            return None
    
    def predict_from_signal(self, signal: Dict) -> Optional[float]:
        """
        从信号字典预测获胜概率
        
        v4.0: 使用统一的12个ICT/SMC特征
        
        Args:
            signal: 包含12个ICT/SMC特征字段的信号字典
        
        Returns:
            获胜概率（0-1），或None（如果模型未加载或特征不完整）
        """
        if not self.is_loaded:
            return None
        
        try:
            # v4.0: 提取12个标准特征（与训练一致）
            features = self._extract_features_from_signal(signal)
            
            if features is None:
                return None
            
            # 预测
            return self.predict(features)
            
        except Exception as e:
            logger.error(f"❌ 从信号预测失败: {e}")
            return None
    
    def _extract_features_from_signal(self, signal: Dict) -> Optional[List[float]]:
        """
        🔥 v4.0: 从信号字典提取12个ICT/SMC特征（使用统一schema）
        
        Args:
            signal: 信号字典（包含ICT/SMC特征）
        
        Returns:
            12个ICT/SMC特征的数值列表（按CANONICAL_FEATURE_NAMES顺序）
        """
        try:
            # v4.0: 使用统一的特征顺序（与训练一致）
            features = [
                float(signal.get(name, 0.0))
                for name in CANONICAL_FEATURE_NAMES
            ]
            
            # 验证长度
            if len(features) != 12:
                logger.error(f"特徵數量錯誤: {len(features)} != 12")
                return None
            
            return features
            
        except (ValueError, TypeError) as e:
            logger.warning(f"特徵提取失敗（數據類型錯誤）: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ 提取特征异常: {e}")
            return None
    
    def reload(self) -> bool:
        """
        重新加载模型（用于模型更新后）
        
        Returns:
            是否成功重新加载
        """
        logger.info("🔄 重新加载ML模型...")
        self.model = None
        self.is_loaded = False
        return self._load_model()
