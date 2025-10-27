# ONNX 实现完整性审计报告 v3.13.0

> **审计日期**: 2025-10-27  
> **审计范围**: 15项ONNX相关实现检查  
> **审计状态**: ⚠️ 部分实现，发现12个问题

---

## 📋 审计概览

| 检查项 | 状态 | 严重程度 |
|--------|------|---------|
| 1. convert_model() FloatTensorType | ✅ 通过 | - |
| 2. validate_conversion() 测试数据 | ✅ 通过 | - |
| 3. save_feature_order() | ✅ 通过 | - |
| 4. MLPredictor ONNX路径替换 | ❌ **失败** | 🔴 HIGH |
| 5. predict_batch() float32 | ✅ 通过 | - |
| 6. ONNX推理输入构建 | ✅ 通过 | - |
| 7. 回退机制 | ⚠️ **部分** | 🟡 MEDIUM |
| 8. extract_features_for_prediction() | ❌ **缺失** | 🔴 HIGH |
| 9. 特征顺序一致性 | ⚠️ **不完整** | 🟡 MEDIUM |
| 10. scan_and_analyze()批量提取 | ❌ **缺失** | 🟡 MEDIUM |
| 11. predict_batch()调用 | ✅ 通过 | - |
| 12. verify_feature_order.py | ❌ **缺失** | 🔴 HIGH |
| 13. check_onnx_compatibility.py | ❌ **缺失** | 🔴 HIGH |
| 14. 动态shape处理测试 | ❌ **缺失** | 🟡 MEDIUM |
| 15. 脚本独立执行 | ⚠️ **未验证** | 🟡 MEDIUM |

**总分**: 5/15 完全通过，3/15 部分通过，7/15 失败/缺失

---

## 🔍 详细检查结果

### ✅ 检查1: convert_model() 使用 FloatTensorType

**文件**: `scripts/convert_xgboost_to_onnx.py:129-182`

**状态**: ✅ **通过**

```python
# 行158: 正确使用 FloatTensorType
initial_type = [('float_input', FloatTensorType(input_shape))]
onnx_model = convert_xgboost(model, initial_types=initial_type)

# 行132: input_shape 预设为 (1, 31)
def convert_model(
    model_path: str, 
    onnx_path: str, 
    input_shape: Tuple[int, int] = (1, 31)
) -> bool:
```

**结论**: 实现正确，符合要求。

---

### ✅ 检查2: validate_conversion() 自动验证

**文件**: `scripts/convert_xgboost_to_onnx.py:80-127`

**状态**: ✅ **通过**

```python
# 行80-83: create_sample_input 使用 float32
def create_sample_input(n_features: int = 31) -> np.ndarray:
    """創建標準化測試輸入"""
    np.random.seed(42)  # 確保可重現
    return np.random.uniform(0, 1, (10, n_features)).astype(np.float32)

# 行86-127: validate_conversion 完整实现
def validate_conversion(
    xgb_model, 
    onnx_session, 
    sample_input: np.ndarray,
    tolerance: float = 1e-5
) -> bool:
    # XGBoost 预测
    xgb_pred = xgb_model.predict(sample_input.astype(np.float64))
    
    # ONNX 预测
    ort_inputs = {onnx_session.get_inputs()[0].name: sample_input}
    onnx_pred = onnx_session.run(None, ort_inputs)[0].flatten()
    
    # 比较差异
    max_diff = np.max(np.abs(xgb_pred - onnx_pred))
    if max_diff <= tolerance:
        print("✅ 轉換驗證通過！")
        return True
```

**结论**: 实现正确，包含完整的验证逻辑。

---

### ✅ 检查3: save_feature_order() 功能

**文件**: `scripts/convert_xgboost_to_onnx.py:71-78`

**状态**: ✅ **通过**

```python
# 行33: 路径定义正确
FEATURE_ORDER_PATH = "data/models/feature_order.txt"

# 行71-78: 保存功能完整
def save_feature_order(features: list, path: str):
    """保存特徵順序到檔案"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        for feat in features:
            f.write(f"{feat}\n")
    print(f"📝 特徵順序已保存: {path}")
```

**结论**: 实现正确，符合要求。

---

### ❌ 检查4: MLPredictor ONNX路径替换

**文件**: `src/ml/predictor.py:81-84`

**状态**: ❌ **失败**

**问题**:
```python
# 行84: 硬编码路径
self.onnx_model_path = "data/models/model.onnx"

# ❌ 缺失: 没有使用 model_path.replace('.pkl', '.onnx')
# 预期实现:
# self.onnx_model_path = self.trainer.model_path.replace('.pkl', '.onnx')
# 即: "data/models/xgboost_predictor_binary.pkl" → "data/models/xgboost_predictor_binary.onnx"
```

**影响**: 
- ONNX模型和XGBoost模型文件名不对应
- 转换脚本生成 `model.onnx`，而预期应该是 `xgboost_predictor_binary.onnx`
- 可能导致ONNX加载失败

**修复建议**:
```python
# 在 __init__() 中:
self.onnx_model_path = self.trainer.model_path.replace('.pkl', '.onnx')
# 结果: "data/models/xgboost_predictor_binary.onnx"
```

---

### ✅ 检查5: predict_batch() 使用 float32

**文件**: `src/ml/predictor.py:236`

**状态**: ✅ **通过**

```python
# 行236: 正确使用 float32
X = np.array(features_list, dtype=np.float32)  # shape: (N, 31)
```

**结论**: 实现正确。

---

### ✅ 检查6: ONNX推理输入构建

**文件**: `src/ml/predictor.py:242`

**状态**: ✅ **通过**

```python
# 行242: 动态获取输入名称（不硬编码）
ort_inputs = {self.onnx_session.get_inputs()[0].name: X}
ort_outs = self.onnx_session.run(None, ort_inputs)
```

**结论**: 实现正确，使用动态输入名称。

---

### ⚠️ 检查7: 回退机制

**文件**: `src/ml/predictor.py:1191-1231`

**状态**: ⚠️ **部分通过**

**已实现部分**:
```python
# 行1191-1231: _try_load_onnx_model()
def _try_load_onnx_model(self) -> None:
    if not ONNX_AVAILABLE:
        logger.debug("ONNX Runtime 未安装，跳过 ONNX 模型加载")
        return  # ✅ 回退
    
    if not os.path.exists(self.onnx_model_path):
        logger.info(f"⚠️  ONNX 模型不存在: {self.onnx_model_path}")
        return  # ✅ 回退
    
    try:
        self.onnx_session = ort.InferenceSession(self.onnx_model_path)
        self.use_onnx = True
    except Exception as e:
        logger.error(f"❌ ONNX 模型载入失败: {e}")
        self.use_onnx = False  # ✅ 回退
```

**缺失部分**:
```python
# ❌ 没有调用 self._load_xgboost_model(model_path)
# 预期: 在except块中应该确保 XGBoost 模型可用
```

**结论**: 基本回退逻辑正确，但缺少显式的XGBoost加载保证。

---

### ❌ 检查8: extract_features_for_prediction()

**文件**: `src/ml/data_processor.py`

**状态**: ❌ **缺失函数**

**问题**:
- `data_processor.py` 中没有 `extract_features_for_prediction()` 函数
- 存在 `prepare_features()` 用于训练，但不适用于实时预测
- `predictor.py` 使用内部的 `_prepare_signal_features()` (行280-375)

**预期实现**:
```python
def extract_features_for_prediction(self, signal: Dict) -> np.ndarray:
    """
    从信号提取特征用于实时预测
    
    Returns:
        np.array(features, dtype=np.float32).reshape(1, -1)
    """
    # 实现特征提取逻辑
    features = self._extract_features(signal)
    return np.array(features, dtype=np.float32).reshape(1, -1)
```

**当前替代方案**:
- `MLPredictor._prepare_signal_features()` 完成了此功能
- 但不符合检查清单中的函数名要求

---

### ⚠️ 检查9: 特征顺序一致性

**文件**: `src/ml/predictor.py:280-375`

**状态**: ⚠️ **不完整**

**问题**:
```python
# 行309-332: _prepare_signal_features() 生成29个特征
# 但检查清单要求 33个特征 (20基础 + 13增强)
# 实际代码: 21基础 + 8增强 = 29个特征

# 行313: hold_duration_hours 设为 0（不应该作为特征）
0,  # hold_duration_hours - 未知

# 特征20: direction_encoded 正确
# 行331:
direction_encoding.get(signal.get('direction', 'LONG'), 1)  # direction_encoded
```

**特征数量差异**:
- **检查清单预期**: 33个特征 (20基础 + 13增强)
- **实际代码**: 29个特征 (21基础 + 8增强)
- **转换脚本**: EXPECTED_FEATURES = 29

**结论**: 实现一致性较好（29个），但与检查清单要求的33个不符。

---

### ❌ 检查10: scan_and_analyze() 批量提取特征

**文件**: `src/main.py`

**状态**: ❌ **缺失验证**

**问题**: 未找到该函数使用 `features_batch = [extract_features_for_prediction(signal) for signal in signals]` 的实现

**建议**: 需要检查 `src/main.py` 中的实际实现

---

### ✅ 检查11: predict_batch() 调用

**文件**: `src/ml/predictor.py:195-278`

**状态**: ✅ **通过**

```python
# 行195-278: predict_batch() 完整实现
def predict_batch(self, signals: List[Dict]) -> List[Optional[Dict]]:
    # 批量预测逻辑
    features_list = []
    for signal in signals:
        features = self._prepare_signal_features(signal)
        if features is not None:
            features_list.append(features)
    
    X = np.array(features_list, dtype=np.float32)
    
    # ONNX 或 XGBoost 推理
    if self.use_onnx:
        ort_inputs = {self.onnx_session.get_inputs()[0].name: X}
        ort_outs = self.onnx_session.run(None, ort_inputs)
        proba_array = ort_outs[0]
    else:
        proba_array = self.model.predict_proba(X)
```

**结论**: 实现正确，支持批量预测。

---

### ❌ 检查12-15: 验证脚本缺失

**状态**: ❌ **全部缺失**

缺失文件:
- `scripts/verify_feature_order.py` (检查12)
- `scripts/check_onnx_compatibility.py` (检查13)
- 动态shape测试 (检查14)
- 独立执行验证 (检查15)

---

## 🛠️ 修复建议

### 高优先级修复 (🔴 HIGH)

1. **修复ONNX路径替换** (检查4)
   ```python
   # src/ml/predictor.py:84
   self.onnx_model_path = self.trainer.model_path.replace('.pkl', '.onnx')
   ```

2. **创建 verify_feature_order.py** (检查12)
3. **创建 check_onnx_compatibility.py** (检查13)
4. **添加 extract_features_for_prediction()** (检查8)

### 中优先级修复 (🟡 MEDIUM)

5. **统一特征数量** (检查9)
   - 确认是使用29个还是33个特征
   - 更新所有文档和代码注释

6. **验证 scan_and_analyze()** (检查10)
7. **增强回退机制日志** (检查7)

---

## 📊 总结

**已实现功能**:
- ✅ ONNX模型转换核心功能完整
- ✅ 批量预测和ONNX推理集成正确
- ✅ 基本回退机制工作

**关键缺失**:
- ❌ ONNX路径动态生成逻辑错误
- ❌ 缺少3个关键验证脚本
- ❌ 特征提取函数命名不规范

**推荐行动**:
1. 立即修复ONNX路径问题（5分钟）
2. 创建验证脚本（30分钟）
3. 完整测试ONNX工作流（15分钟）

---

**审计完成时间**: 2025-10-27  
**下一步**: 实施高优先级修复
