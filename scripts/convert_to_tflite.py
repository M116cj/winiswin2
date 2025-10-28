"""
模型量化转换脚本
将 TensorFlow 模型转换为 TensorFlow Lite 量化模型
"""
import sys
import os
import logging
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ml.model_quantizer import ModelQuantizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.error("❌ TensorFlow 不可用，无法进行模型量化")
    sys.exit(1)


def representative_data_gen():
    """
    生成代表性数据用于量化
    """
    # 生成随机数据作为代表性数据集
    for _ in range(100):
        # 假设输入是 50 个价格数据点
        data = np.random.randn(1, 50).astype(np.float32)
        yield [data]


def convert_structure_encoder():
    """转换市场结构自动编码器"""
    logger.info("=" * 60)
    logger.info("转换市场结构自动编码器到 TFLite INT8")
    logger.info("=" * 60)
    
    try:
        # 创建模型
        from src.ml.market_structure_autoencoder import MarketStructureAutoencoder
        
        encoder = MarketStructureAutoencoder()
        
        if hasattr(encoder, 'model') and encoder.model is not None:
            # 量化模型
            quantized_model = ModelQuantizer.quantize_model(
                encoder.model,
                representative_data_gen
            )
            
            # 保存量化模型
            output_path = "models/structure_encoder_quant.tflite"
            os.makedirs("models", exist_ok=True)
            
            with open(output_path, "wb") as f:
                f.write(quantized_model)
            
            logger.info(f"✅ 市场结构自动编码器量化完成: {output_path}")
            logger.info(f"   模型大小: {len(quantized_model) / 1024:.2f} KB")
            
            return True
        else:
            logger.warning("⚠️ 市场结构自动编码器没有 TensorFlow 模型（fallback 模式）")
            return False
    
    except Exception as e:
        logger.error(f"❌ 转换市场结构自动编码器失败: {e}")
        return False


def convert_feature_discovery():
    """转换特征发现网络"""
    logger.info("=" * 60)
    logger.info("转换特征发现网络到 TFLite INT8")
    logger.info("=" * 60)
    
    try:
        from src.ml.feature_discovery_network import FeatureDiscoveryNetwork
        
        network = FeatureDiscoveryNetwork()
        
        if hasattr(network, 'model') and network.model is not None:
            # 代表性数据生成器（16维市场结构向量）
            def feature_data_gen():
                for _ in range(100):
                    data = np.random.randn(1, 16).astype(np.float32)
                    yield [data]
            
            # 量化模型
            quantized_model = ModelQuantizer.quantize_model(
                network.model,
                feature_data_gen
            )
            
            # 保存量化模型
            output_path = "models/feature_discovery_quant.tflite"
            
            with open(output_path, "wb") as f:
                f.write(quantized_model)
            
            logger.info(f"✅ 特征发现网络量化完成: {output_path}")
            logger.info(f"   模型大小: {len(quantized_model) / 1024:.2f} KB")
            
            return True
        else:
            logger.warning("⚠️ 特征发现网络没有 TensorFlow 模型（fallback 模式）")
            return False
    
    except Exception as e:
        logger.error(f"❌ 转换特征发现网络失败: {e}")
        return False


def convert_liquidity_prediction():
    """转换流动性预测模型"""
    logger.info("=" * 60)
    logger.info("转换流动性预测模型到 TFLite INT8")
    logger.info("=" * 60)
    
    try:
        from src.ml.liquidity_prediction_model import LiquidityPredictionModel
        
        model = LiquidityPredictionModel()
        
        if hasattr(model, 'model') and model.model is not None:
            # 代表性数据生成器（20个价格数据点）
            def liquidity_data_gen():
                for _ in range(100):
                    data = np.random.randn(1, 20, 4).astype(np.float32)  # OHLC数据
                    yield [data]
            
            # 量化模型
            quantized_model = ModelQuantizer.quantize_model(
                model.model,
                liquidity_data_gen
            )
            
            # 保存量化模型
            output_path = "models/liquidity_prediction_quant.tflite"
            
            with open(output_path, "wb") as f:
                f.write(quantized_model)
            
            logger.info(f"✅ 流动性预测模型量化完成: {output_path}")
            logger.info(f"   模型大小: {len(quantized_model) / 1024:.2f} KB")
            
            return True
        else:
            logger.warning("⚠️ 流动性预测模型没有 TensorFlow 模型（fallback 模式）")
            return False
    
    except Exception as e:
        logger.error(f"❌ 转换流动性预测模型失败: {e}")
        return False


def main():
    """主函数"""
    logger.info("🚀 开始模型量化转换...")
    
    if not TF_AVAILABLE:
        logger.error("❌ TensorFlow 不可用，无法进行模型量化")
        logger.info("💡 安装 TensorFlow: pip install tensorflow>=2.13.0")
        return
    
    # 转换所有模型
    results = {
        "structure_encoder": convert_structure_encoder(),
        "feature_discovery": convert_feature_discovery(),
        "liquidity_prediction": convert_liquidity_prediction()
    }
    
    # 汇总结果
    logger.info("=" * 60)
    logger.info("转换结果汇总:")
    logger.info("=" * 60)
    
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    for model_name, success in results.items():
        status = "✅ 成功" if success else "⚠️ 跳过（fallback模式）"
        logger.info(f"  {model_name}: {status}")
    
    logger.info(f"\n🎯 转换完成: {success_count}/{total_count} 个模型成功量化")
    
    if success_count > 0:
        logger.info("\n📝 使用说明:")
        logger.info("1. 设置环境变量启用量化:")
        logger.info("   export ENABLE_QUANTIZATION=true")
        logger.info("   export QUANTIZED_MODEL_PATH=models/")
        logger.info("2. 重启交易系统")
        logger.info("3. 检查日志确认量化模型加载成功")
    else:
        logger.warning("\n⚠️ 没有模型被量化（可能所有模型都在 fallback 模式）")
        logger.info("💡 这是正常的，系统会在 TensorFlow 不可用时使用 fallback 实现")


if __name__ == "__main__":
    main()
