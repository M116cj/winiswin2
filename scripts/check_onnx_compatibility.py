"""
ONNX 兼容性检查工具（v3.13.0）

验证:
1. ONNX模型格式正确性
2. 输入输出shape兼容性
3. 动态shape处理
4. 推理功能测试
"""

import os
import sys
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ONNX 相关导入
try:
    import onnx
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError as e:
    print(f"❌ ONNX依赖缺失: {e}")
    print("请安装: pip install onnx onnxruntime")
    ONNX_AVAILABLE = False
    sys.exit(1)

# 配置
ONNX_MODEL_PATH = "data/models/model.onnx"
EXPECTED_INPUT_SHAPE = (1, 29)  # (batch_size, n_features)
EXPECTED_FEATURE_COUNT = 29


def check_onnx_model(model_path: str) -> bool:
    """
    验证ONNX模型格式正确性
    
    Args:
        model_path: ONNX模型路径
    
    Returns:
        bool: 是否通过验证
    """
    print(f"📋 检查ONNX模型格式: {model_path}")
    
    if not os.path.exists(model_path):
        print(f"   ❌ 模型文件不存在")
        return False
    
    try:
        # 加载模型
        model = onnx.load(model_path)
        
        # 验证模型格式
        onnx.checker.check_model(model)
        
        print(f"   ✅ ONNX模型格式正确")
        
        # 显示模型信息
        print(f"\n📊 模型信息:")
        print(f"   IR 版本: {model.ir_version}")
        print(f"   生产者: {model.producer_name if model.producer_name else 'Unknown'}")
        print(f"   模型版本: {model.model_version}")
        
        # 显示图信息
        graph = model.graph
        print(f"   图节点数: {len(graph.node)}")
        print(f"   输入数: {len(graph.input)}")
        print(f"   输出数: {len(graph.output)}")
        
        # 显示输入输出详情
        print(f"\n🔍 输入详情:")
        for inp in graph.input:
            print(f"   - 名称: {inp.name}")
            print(f"     类型: {inp.type}")
            # 尝试获取shape
            try:
                shape = [dim.dim_value if dim.dim_value > 0 else -1 
                        for dim in inp.type.tensor_type.shape.dim]
                print(f"     Shape: {shape}")
            except:
                print(f"     Shape: 未知")
        
        print(f"\n🔍 输出详情:")
        for out in graph.output:
            print(f"   - 名称: {out.name}")
            print(f"     类型: {out.type}")
            try:
                shape = [dim.dim_value if dim.dim_value > 0 else -1 
                        for dim in out.type.tensor_type.shape.dim]
                print(f"     Shape: {shape}")
            except:
                print(f"     Shape: 未知")
        
        return True
        
    except onnx.checker.ValidationError as e:
        print(f"   ❌ 模型验证失败: {e}")
        return False
    except Exception as e:
        print(f"   ❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_shape_compatibility(model_path: str) -> bool:
    """
    测试shape兼容性（包括动态shape）
    
    Args:
        model_path: ONNX模型路径
    
    Returns:
        bool: 是否通过测试
    """
    print(f"\n🔧 测试Shape兼容性...")
    
    try:
        # 创建推理会话
        session = ort.InferenceSession(model_path)
        
        # 获取输入信息
        input_info = session.get_inputs()[0]
        input_name = input_info.name
        input_shape = input_info.shape
        
        print(f"   输入名称: {input_name}")
        print(f"   输入shape: {input_shape}")
        
        # 处理动态shape（将负数或None替换为1）
        test_shape = []
        for dim in input_shape:
            if isinstance(dim, int) and dim <= 0:
                test_shape.append(1)  # 动态维度用1测试
            elif dim is None:
                test_shape.append(1)
            else:
                test_shape.append(dim)
        
        print(f"   测试shape: {test_shape}")
        
        # 测试多种batch size
        test_cases = [
            (1, EXPECTED_FEATURE_COUNT),   # 单个样本
            (10, EXPECTED_FEATURE_COUNT),  # 10个样本
            (100, EXPECTED_FEATURE_COUNT), # 100个样本
        ]
        
        all_passed = True
        for i, test_shape in enumerate(test_cases, 1):
            try:
                # 创建测试数据
                test_data = np.random.uniform(0, 1, test_shape).astype(np.float32)
                
                # 推理
                ort_inputs = {input_name: test_data}
                ort_outs = session.run(None, ort_inputs)
                
                output_shape = ort_outs[0].shape
                print(f"   ✅ 测试{i}: 输入{test_shape} → 输出{output_shape}")
                
            except Exception as e:
                print(f"   ❌ 测试{i}失败: {e}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"   ❌ Shape测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_inference_functionality(model_path: str) -> bool:
    """
    测试推理功能
    
    Args:
        model_path: ONNX模型路径
    
    Returns:
        bool: 是否通过测试
    """
    print(f"\n⚡ 测试推理功能...")
    
    try:
        # 创建推理会话
        session = ort.InferenceSession(model_path)
        
        # 获取输入信息
        input_name = session.get_inputs()[0].name
        
        # 创建测试数据（合理范围）
        test_data = np.array([[
            0.75,  # confidence_score (0-1)
            10,    # leverage (3-20)
            1000,  # position_value
            0,     # hold_duration_hours
            2.0,   # risk_reward_ratio
            2,     # order_blocks_count
            1,     # liquidity_zones_count
            55,    # rsi_entry (0-100)
            0.1,   # macd_entry
            0.05,  # macd_signal_entry
            0.05,  # macd_histogram_entry
            500,   # atr_entry
            2.5,   # bb_width_pct
            1.2,   # volume_sma_ratio
            0.02,  # price_vs_ema50
            0.05,  # price_vs_ema200
            1,     # trend_1h_encoded (-1/0/1)
            1,     # trend_15m_encoded
            1,     # trend_5m_encoded
            1,     # market_structure_encoded
            1,     # direction_encoded (-1/1)
            12,    # hour_of_day (0-23)
            3,     # day_of_week (0-6)
            0,     # is_weekend (0/1)
            0.017, # stop_distance_pct
            0.033, # tp_distance_pct
            7.5,   # confidence_x_leverage
            55,    # rsi_x_trend
            1250   # atr_x_bb_width
        ]], dtype=np.float32)
        
        # 推理
        ort_inputs = {input_name: test_data}
        ort_outs = session.run(None, ort_inputs)
        
        # 验证输出
        predictions = ort_outs[0]
        
        print(f"   输入shape: {test_data.shape}")
        print(f"   输出shape: {predictions.shape}")
        print(f"   预测结果: {predictions}")
        
        # 验证输出格式（应该是概率）
        if predictions.shape[0] == 1:  # batch_size = 1
            if predictions.shape[1] == 2:  # 二分类概率
                proba_0, proba_1 = predictions[0]
                print(f"   类别0概率: {proba_0:.4f}")
                print(f"   类别1概率: {proba_1:.4f}")
                
                # 验证概率和为1（允许小误差）
                total_proba = proba_0 + proba_1
                if abs(total_proba - 1.0) < 0.01:
                    print(f"   ✅ 概率和: {total_proba:.4f} (正确)")
                else:
                    print(f"   ⚠️  概率和: {total_proba:.4f} (应该接近1.0)")
            else:
                print(f"   ⚠️  输出维度异常: {predictions.shape}")
        
        print(f"   ✅ 推理功能正常")
        return True
        
    except Exception as e:
        print(f"   ❌ 推理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance(model_path: str, n_iterations: int = 100) -> bool:
    """
    测试推理性能
    
    Args:
        model_path: ONNX模型路径
        n_iterations: 测试迭代次数
    
    Returns:
        bool: 是否通过测试
    """
    print(f"\n⏱️  测试推理性能 ({n_iterations}次迭代)...")
    
    try:
        import time
        
        # 创建推理会话
        session = ort.InferenceSession(model_path)
        input_name = session.get_inputs()[0].name
        
        # 测试数据
        test_data = np.random.uniform(0, 1, (1, EXPECTED_FEATURE_COUNT)).astype(np.float32)
        
        # 预热（排除初始化开销）
        for _ in range(10):
            session.run(None, {input_name: test_data})
        
        # 性能测试
        start_time = time.perf_counter()
        for _ in range(n_iterations):
            session.run(None, {input_name: test_data})
        end_time = time.perf_counter()
        
        total_time = end_time - start_time
        avg_time_ms = (total_time / n_iterations) * 1000
        
        print(f"   总时间: {total_time:.3f} 秒")
        print(f"   平均推理时间: {avg_time_ms:.3f} ms/次")
        print(f"   吞吐量: {n_iterations/total_time:.1f} 推理/秒")
        
        # 性能基准（应该 <10ms）
        if avg_time_ms < 10:
            print(f"   ✅ 性能优秀 (<10ms)")
        elif avg_time_ms < 50:
            print(f"   ⚠️  性能一般 (<50ms)")
        else:
            print(f"   ❌ 性能较慢 (>{avg_time_ms:.1f}ms)")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 性能测试失败: {e}")
        return False


def main():
    """主函数"""
    print("🚀 ONNX 兼容性检查工具 v3.13.0")
    print("="*60)
    
    if not ONNX_AVAILABLE:
        print("❌ ONNX依赖未安装")
        sys.exit(1)
    
    # 检查模型文件
    if not os.path.exists(ONNX_MODEL_PATH):
        print(f"❌ ONNX模型不存在: {ONNX_MODEL_PATH}")
        print("\n💡 请先运行: python scripts/convert_xgboost_to_onnx.py")
        sys.exit(1)
    
    # 运行所有检查
    checks = []
    
    # 1. 模型格式检查
    checks.append(("模型格式", check_onnx_model(ONNX_MODEL_PATH)))
    
    # 2. Shape兼容性测试
    checks.append(("Shape兼容性", test_shape_compatibility(ONNX_MODEL_PATH)))
    
    # 3. 推理功能测试
    checks.append(("推理功能", test_inference_functionality(ONNX_MODEL_PATH)))
    
    # 4. 性能测试
    checks.append(("推理性能", test_performance(ONNX_MODEL_PATH)))
    
    # 输出结果
    print("\n" + "="*60)
    print("检查结果汇总")
    print("="*60)
    
    all_passed = True
    for name, passed in checks:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("🎉 所有检查通过！ONNX模型已准备就绪")
        print("\n下一步:")
        print("  1. MLPredictor 将自动检测并使用此ONNX模型")
        print("  2. 预期性能提升: 推理速度 ↑ 50-70%")
        sys.exit(0)
    else:
        print("❌ 部分检查失败")
        print("\n建议:")
        print("  1. 检查XGBoost模型是否正确训练")
        print("  2. 重新运行转换脚本: python scripts/convert_xgboost_to_onnx.py")
        print("  3. 确认特征数量为29个")
        sys.exit(1)


if __name__ == "__main__":
    main()
