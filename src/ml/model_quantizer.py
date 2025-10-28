"""
TensorFlow Lite 模型量化器
优化1：TensorFlow Lite 量化（推理速度提升 3-5 倍）
"""
import logging

logger = logging.getLogger(__name__)

try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.warning("⚠️ TensorFlow 不可用，量化功能将不可用")


class QuantizedModelWrapper:
    """量化模型包装器，提供与原始模型相同的接口"""
    
    def __init__(self, interpreter):
        """
        初始化包装器
        
        Args:
            interpreter: TFLite Interpreter
        """
        self.interpreter = interpreter
        self.input_details = interpreter.get_input_details()
        self.output_details = interpreter.get_output_details()
    
    def encode_structure(self, price_data):
        """
        编码市场结构（与 MarketStructureAutoencoder 接口兼容）
        
        Args:
            price_data: 价格数据数组
        
        Returns:
            编码后的结构向量（float32）
        """
        import numpy as np
        
        # 准备输入数据（取最后50个价格点）
        input_data = np.array([price_data[-50:]], dtype=np.float32)
        
        # 获取量化参数
        input_scale = self.input_details[0].get('quantization', (0.0, 0))[0]
        input_zero_point = self.input_details[0].get('quantization', (0.0, 0))[1]
        
        # 量化输入：float32 -> int8
        if input_scale > 0:
            quantized_input = (input_data / input_scale + input_zero_point).astype(np.int8)
        else:
            # 如果没有量化参数，使用float32（可能是FLOAT16模型）
            quantized_input = input_data
        
        # 设置输入张量
        self.interpreter.set_tensor(self.input_details[0]['index'], quantized_input)
        
        # 运行推理
        self.interpreter.invoke()
        
        # 获取输出张量
        output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
        
        # 获取输出量化参数
        output_scale = self.output_details[0].get('quantization', (0.0, 0))[0]
        output_zero_point = self.output_details[0].get('quantization', (0.0, 0))[1]
        
        # 反量化输出：int8 -> float32
        if output_scale > 0:
            dequantized_output = (output_data.astype(np.float32) - output_zero_point) * output_scale
        else:
            # 如果没有量化参数，直接使用
            dequantized_output = output_data.astype(np.float32)
        
        return dequantized_output[0]  # 返回第一个结果


class ModelQuantizer:
    """TensorFlow Lite 模型量化器"""
    
    @staticmethod
    def quantize_model(model, representative_data_gen):
        """
        量化模型到 INT8
        
        Args:
            model: Keras 模型
            representative_data_gen: 代表性数据生成器
        
        Returns:
            量化后的 TFLite 模型（字节）
        """
        if not TF_AVAILABLE:
            raise RuntimeError("TensorFlow 不可用，无法量化模型")
        
        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.representative_dataset = representative_data_gen
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8
        
        logger.info("🔄 正在量化模型到 INT8...")
        tflite_model = converter.convert()
        logger.info(f"✅ 模型量化完成，大小: {len(tflite_model) / 1024:.2f} KB")
        
        return tflite_model
    
    @staticmethod
    def load_quantized_model(tflite_model_path):
        """
        载入量化模型并返回包装器
        
        Args:
            tflite_model_path: TFLite 模型路径
        
        Returns:
            QuantizedModelWrapper（提供与原始模型相同的接口）
        """
        if not TF_AVAILABLE:
            raise RuntimeError("TensorFlow 不可用，无法加载量化模型")
        
        interpreter = tf.lite.Interpreter(model_path=tflite_model_path)
        interpreter.allocate_tensors()
        
        logger.info(f"✅ 载入量化模型: {tflite_model_path}")
        
        # 获取输入输出详情
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        logger.info(f"  输入形状: {input_details[0]['shape']}")
        logger.info(f"  输出形状: {output_details[0]['shape']}")
        
        # 返回包装器而非原始 Interpreter
        return QuantizedModelWrapper(interpreter)
    
    @staticmethod
    def predict_with_quantized_model(interpreter, input_data):
        """
        使用量化模型进行预测
        
        Args:
            interpreter: TFLite Interpreter
            input_data: 输入数据（numpy array）
        
        Returns:
            预测结果
        """
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        # 设置输入张量
        interpreter.set_tensor(input_details[0]['index'], input_data)
        
        # 运行推理
        interpreter.invoke()
        
        # 获取输出张量
        output_data = interpreter.get_tensor(output_details[0]['index'])
        
        return output_data
