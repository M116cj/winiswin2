"""
HybridMLProcessor回归测试：验证缓冲区污染bug已修复
"""

from src.ml.hybrid_ml_processor import HybridMLProcessor


class MockMLModel:
    """模拟ML模型，记录每次predict调用的特征"""
    def __init__(self):
        self.predict_calls = []
        self.batch_predict_calls = []
    
    def predict(self, features):
        """单个预测"""
        self.predict_calls.append(features.copy())
        return features.get('value', 0.5)
    
    def predict_batch(self, features_batch):
        """批量预测"""
        self.batch_predict_calls.append([f.copy() for f in features_batch])
        return [f.get('value', 0.5) for f in features_batch]


def test_no_buffer_pollution():
    """
    测试场景：验证单个预测不会污染缓冲区
    
    Bug重现步骤（修复前）：
    1. 请求A到达（缓冲区未满，使用单个预测）
    2. A被错误地加入缓冲区
    3. 后续4个请求B,C,D,E到达，触发批量（缓冲区：[A,B,C,D,E]）
    4. 批量处理使用过期的A特征
    5. 再次请求A时，得到过期的缓存结果
    
    预期行为（修复后）：
    1. 请求A直接单个预测（不加入缓冲区）
    2. 后续5个请求触发批量（缓冲区：[B,C,D,E,F]，不含A）
    3. 再次请求A时，重新预测（新特征）
    """
    print("\n" + "="*60)
    print("回归测试：验证单个预测不污染缓冲区")
    print("="*60)
    
    model = MockMLModel()
    processor = HybridMLProcessor(
        model=model,
        batch_size=5,
        max_buffer_time=10.0,  # 长超时避免时间触发
        enable_batching=True
    )
    
    # 步骤1：单个请求A（value=1.0）
    print("\n步骤1: 单个请求A（缓冲区未满，应直接单个预测）")
    result_a1 = processor.predict("A", {"value": 1.0})
    print(f"  结果A1: {result_a1}")
    print(f"  单个预测调用数: {len(model.predict_calls)}")
    print(f"  批量预测调用数: {len(model.batch_predict_calls)}")
    
    assert len(model.predict_calls) == 1, "应该有1次单个预测调用"
    assert len(model.batch_predict_calls) == 0, "不应该有批量预测"
    assert result_a1 == 1.0, f"A1结果应该是1.0，实际是{result_a1}"
    
    # 步骤2：5个新请求B,C,D,E,F（触发批量）
    print("\n步骤2: 5个新请求B,C,D,E,F（应触发批量，不含A）")
    symbols_batch = ["B", "C", "D", "E", "F"]
    values_batch = [2.0, 3.0, 4.0, 5.0, 6.0]
    
    for sym, val in zip(symbols_batch, values_batch):
        result = processor.predict(sym, {"value": val})
        print(f"  请求{sym}: 结果={result}")
    
    print(f"\n  单个预测调用数: {len(model.predict_calls)}")
    print(f"  批量预测调用数: {len(model.batch_predict_calls)}")
    
    assert len(model.batch_predict_calls) == 1, "应该有1次批量预测"
    batch_features = model.batch_predict_calls[0]
    print(f"  批量处理的特征数: {len(batch_features)}")
    
    # 关键验证：批量中不应该包含A
    batch_values = [f['value'] for f in batch_features]
    print(f"  批量处理的value值: {batch_values}")
    
    assert 1.0 not in batch_values, "❌ Bug未修复：批量中包含过期的A！"
    assert len(batch_features) == 5, f"批量应该有5个请求，实际{len(batch_features)}"
    assert batch_values == [2.0, 3.0, 4.0, 5.0, 6.0], f"批量值应该是[2.0-6.0]，实际{batch_values}"
    
    # 步骤3：再次请求A（value=10.0，新特征）
    print("\n步骤3: 再次请求A（新特征value=10.0）")
    model.predict_calls.clear()
    model.batch_predict_calls.clear()
    
    result_a2 = processor.predict("A", {"value": 10.0})
    print(f"  结果A2: {result_a2}")
    print(f"  单个预测调用数: {len(model.predict_calls)}")
    
    # 关键验证：应该使用新特征，不应该返回缓存的1.0
    assert result_a2 == 10.0, f"❌ Bug未修复：返回了缓存的旧值！应该是10.0，实际{result_a2}"
    
    print("\n" + "="*60)
    print("✅ 回归测试通过：缓冲区污染bug已修复")
    print("="*60)
    print("\n验证要点:")
    print("  1. ✅ 单个预测不加入缓冲区")
    print("  2. ✅ 批量处理不含过期请求")
    print("  3. ✅ 后续请求使用新特征（无缓存污染）")


if __name__ == "__main__":
    test_no_buffer_pollution()
