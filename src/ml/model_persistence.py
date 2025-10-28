"""
模型持久化管理器（v3.16.3 - TensorFlow 兼容版本）
職責：保存/加載深度學習模型狀態，支持增量學習
"""

import os
import json
import logging
from typing import Any, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

# 檢查 TensorFlow 是否可用
try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False


class ModelPersistence:
    """模型持久化管理器（支持 TensorFlow SavedModel）"""
    
    def __init__(self, model_dir: str = "data/models/self_learning"):
        """
        初始化持久化管理器
        
        Args:
            model_dir: 模型保存目錄
        """
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        logger.info(f"✅ 模型持久化管理器初始化: {self.model_dir}")
    
    def save_model(self, model: Any, model_name: str, metadata: Optional[Dict] = None) -> bool:
        """
        保存模型和元數據（支持 TensorFlow 模型）
        
        Args:
            model: 模型對象
            model_name: 模型名稱
            metadata: 額外的元數據（訓練次數、時間戳等）
        
        Returns:
            bool: 是否成功保存
        """
        try:
            model_path = os.path.join(self.model_dir, model_name)
            metadata_path = os.path.join(self.model_dir, f"{model_name}_metadata.json")
            
            # 保存模型
            if hasattr(model, 'encoder') and hasattr(model, 'decoder'):
                # MarketStructureAutoencoder (有 encoder 和 decoder)
                if model.encoder is not None and TF_AVAILABLE:
                    encoder_path = os.path.join(self.model_dir, f"{model_name}_encoder")
                    decoder_path = os.path.join(self.model_dir, f"{model_name}_decoder")
                    model.encoder.save(encoder_path, save_format='tf')
                    model.decoder.save(decoder_path, save_format='tf')
                    logger.info(f"  ✅ 保存 TensorFlow 模型: {model_name} (encoder + decoder)")
                else:
                    logger.debug(f"  ⏭️  跳過 TensorFlow 未安裝的模型: {model_name}")
                    
            elif hasattr(model, 'model'):
                # FeatureDiscoveryNetwork 或 LiquidityPredictionModel (有單個 model)
                if model.model is not None and TF_AVAILABLE:
                    model.model.save(model_path, save_format='tf')
                    logger.info(f"  ✅ 保存 TensorFlow 模型: {model_name}")
                else:
                    logger.debug(f"  ⏭️  跳過 TensorFlow 未安裝的模型: {model_name}")
            else:
                logger.warning(f"  ⚠️ 未知模型類型: {model_name}，跳過保存")
                return False
            
            # 保存元數據
            if metadata is None:
                metadata = {}
            
            metadata['saved_at'] = datetime.now().isoformat()
            metadata['model_name'] = model_name
            metadata['tensorflow_available'] = TF_AVAILABLE
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"  ❌ 保存模型失敗 {model_name}: {e}", exc_info=True)
            return False
    
    def load_model(self, model_name: str, model_class: Any) -> Optional[tuple]:
        """
        加載模型和元數據（支持 TensorFlow 模型）
        
        Args:
            model_name: 模型名稱
            model_class: 模型類（用於創建實例）
            
        Returns:
            tuple: (model, metadata) 或 None
        """
        try:
            model_path = os.path.join(self.model_dir, model_name)
            metadata_path = os.path.join(self.model_dir, f"{model_name}_metadata.json")
            
            # 檢查元數據是否存在
            if not os.path.exists(metadata_path):
                return None
            
            # 加載元數據
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # 檢查 TensorFlow 是否可用
            if not TF_AVAILABLE:
                logger.warning(f"  ⚠️ TensorFlow 未安裝，無法加載模型: {model_name}")
                return None
            
            # 創建模型實例
            model = model_class()
            
            # 加載權重
            if hasattr(model, 'encoder') and hasattr(model, 'decoder'):
                # MarketStructureAutoencoder
                encoder_path = os.path.join(self.model_dir, f"{model_name}_encoder")
                decoder_path = os.path.join(self.model_dir, f"{model_name}_decoder")
                
                if os.path.exists(encoder_path) and os.path.exists(decoder_path):
                    model.encoder = tf.keras.models.load_model(encoder_path)
                    model.decoder = tf.keras.models.load_model(decoder_path)
                    logger.info(f"  ✅ 加載模型: {model_name} (保存於: {metadata.get('saved_at', '未知')})")
                    return (model, metadata)
                    
            elif hasattr(model, 'model'):
                # FeatureDiscoveryNetwork 或 LiquidityPredictionModel
                if os.path.exists(model_path):
                    model.model = tf.keras.models.load_model(model_path)
                    logger.info(f"  ✅ 加載模型: {model_name} (保存於: {metadata.get('saved_at', '未知')})")
                    return (model, metadata)
            
            return None
            
        except Exception as e:
            logger.error(f"  ❌ 加載模型失敗 {model_name}: {e}", exc_info=True)
            return None
    
    def model_exists(self, model_name: str) -> bool:
        """檢查模型是否存在"""
        metadata_path = os.path.join(self.model_dir, f"{model_name}_metadata.json")
        return os.path.exists(metadata_path)
    
    def delete_model(self, model_name: str) -> bool:
        """刪除模型文件"""
        try:
            import shutil
            
            model_path = os.path.join(self.model_dir, model_name)
            metadata_path = os.path.join(self.model_dir, f"{model_name}_metadata.json")
            encoder_path = os.path.join(self.model_dir, f"{model_name}_encoder")
            decoder_path = os.path.join(self.model_dir, f"{model_name}_decoder")
            
            # 刪除所有可能的文件/目錄
            for path in [model_path, encoder_path, decoder_path]:
                if os.path.exists(path):
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
            
            if os.path.exists(metadata_path):
                os.remove(metadata_path)
            
            logger.info(f"  ✅ 刪除模型: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"  ❌ 刪除模型失敗 {model_name}: {e}")
            return False
    
    def list_models(self) -> list:
        """列出所有已保存的模型"""
        try:
            models = []
            for file in os.listdir(self.model_dir):
                if file.endswith('_metadata.json'):
                    model_name = file.replace('_metadata.json', '')
                    models.append(model_name)
            return models
        except Exception as e:
            logger.error(f"列出模型失敗: {e}")
            return []
