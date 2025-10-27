# XGBoost模型诊断报告

## 📅 诊断日期
2025-10-27

## 🎯 诊断范围
全面检查XGBoost模型的潜在问题：数据泄漏、类别不平衡、特征工程、权重设置、正则化、超参数

---

## 问题1️⃣：数据泄漏检查 ⚠️ 

### 当前特征列表

**基础特征（21个）**：
```python
'confidence_score', 'leverage', 'position_value',
'hold_duration_hours', 'risk_reward_ratio',
'order_blocks_count', 'liquidity_zones_count',
'rsi_entry', 'macd_entry', 'macd_signal_entry', 'macd_histogram_entry',
'atr_entry', 'bb_width_pct', 'volume_sma_ratio',
'price_vs_ema50', 'price_vs_ema200',
'trend_1h_encoded', 'trend_15m_encoded', 'trend_5m_encoded',
'market_structure_encoded', 'direction_encoded'
```

**增强特征（8个）**：
```python
'hour_of_day', 'day_of_week', 'is_weekend',
'stop_distance_pct', 'tp_distance_pct',
'confidence_x_leverage', 'rsi_x_trend', 'atr_x_bb_width'
```

### ⚠️ 潜在数据泄漏风险

#### 高风险特征 🔴
1. **`hold_duration_hours`** ❌ **数据泄漏！**
   - 这是交易结束后才知道的信息
   - 训练时使用了未来信息
   - **必须移除**

#### 中风险特征 🟡
1. **`position_value`** ⚠️ 可能泄漏
   - 如果包含实际成交后的价值，则是泄漏
   - 如果是开仓时计算的预期价值，则安全
   - **需要确认计算方式**

2. **`risk_reward_ratio`** ⚠️ 可能泄漏
   - 如果使用实际止损止盈价格，则安全
   - 如果使用实际成交价格，则可能泄漏
   - **需要确认计算方式**

#### 低风险特征 🟢
所有技术指标（RSI、MACD、ATR、EMA等）- ✅ 安全

### 🔧 修复建议

```python
# 需要从特征中移除
FEATURES_TO_REMOVE = [
    'hold_duration_hours'  # ❌ 数据泄漏，必须移除
]

# 需要确认的特征
FEATURES_TO_VERIFY = [
    'position_value',      # 确认是否使用开仓时计算的值
    'risk_reward_ratio'    # 确认是否使用预设的止损止盈
]
```

---

## 问题2️⃣：样本权重检查 ✅ 

### 当前权重设置

#### sample_weight计算（balanced模式）
```python
# Step 1: 计算类别权重
weights[cls] = total_samples / (len(class_counts) * count)

# Step 2: 归一化
weights = {cls: w / weight_sum * len(class_counts) for cls, w in weights.items()}

# Step 3: 乘以时间衰减权重
sample_weights = class_weights * time_weights  # time_weights = 0.95^t
```

#### scale_pos_weight计算
```python
scale_pos_weight = num_negative / num_positive
```

### ✅ 权重设置检查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| **权重是否过大** | ✅ 通过 | 归一化后权重不会>100 |
| **权重计算合理** | ✅ 通过 | 使用sklearn的balanced方法 |
| **scale_pos_weight合理** | ✅ 通过 | 标准公式 neg/pos |
| **权重日志记录** | ✅ 通过 | 记录min/max/mean |

### 📊 权重范围估算

假设类别比例为 7:3（胜率30%）：

```python
# 类别权重
weight_0 = total_samples / (2 * count_0) = 1000 / (2 * 700) ≈ 0.714
weight_1 = total_samples / (2 * count_1) = 1000 / (2 * 300) ≈ 1.667

# 归一化后
weight_sum = 0.714 + 1.667 = 2.381
weight_0 = 0.714 / 2.381 * 2 ≈ 0.6
weight_1 = 1.667 / 2.381 * 2 ≈ 1.4

# 乘以时间权重（0.95^t，范围约0.6-1.0）
final_weight_0 ≈ 0.36 - 0.6
final_weight_1 ≈ 0.84 - 1.4

# scale_pos_weight
scale_pos_weight = 700 / 300 ≈ 2.33
```

**结论**: ✅ 权重范围合理，不会过大（远小于100）

---

## 问题3️⃣：类别不平衡处理 ✅

### 当前处理机制

```python
# 1. 分析类别平衡
balance_report = imbalance_handler.analyze_class_balance(y, X)

# 2. 如果不平衡比率 >= 2.0，启用平衡处理
if balance_report.get('needs_balancing', False):
    # 2.1 计算样本权重
    sample_weights = calculate_sample_weight(y_train, method='balanced')
    
    # 2.2 设置scale_pos_weight
    params['scale_pos_weight'] = get_scale_pos_weight(y_train)
```

### ✅ 不平衡处理检查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| **检测机制** | ✅ 完善 | 不平衡比率>=2.0触发 |
| **sample_weight** | ✅ 启用 | balanced模式 |
| **scale_pos_weight** | ✅ 启用 | neg/pos比率 |
| **双重保护** | ✅ 完善 | 同时使用两种方法 |

### 📊 不平衡处理方法对比

| 方法 | 使用情况 | 优点 | 缺点 |
|------|----------|------|------|
| **sample_weight** | ✅ 已使用 | 灵活，可结合时间权重 | 可能过拟合少数类 |
| **scale_pos_weight** | ✅ 已使用 | XGBoost原生支持 | 仅适用于二分类 |
| **SMOTE** | ❌ 未使用 | 生成新样本 | 可能引入噪声 |

**结论**: ✅ 当前双重保护机制已足够，暂不需要SMOTE

---

## 问题4️⃣：正则化参数检查 ✅

### 当前正则化设置

```python
base_params = {
    'reg_alpha': 0.1,    # L1正则化（Lasso）
    'reg_lambda': 1.0,   # L2正则化（Ridge）
    'gamma': 0.1,        # 最小损失减少
    'min_child_weight': 1,
    'max_depth': 6,
    'subsample': 0.8,
    'colsample_bytree': 0.8
}
```

### ✅ 正则化检查

| 参数 | 当前值 | 推荐范围 | 状态 |
|------|--------|----------|------|
| **reg_alpha** | 0.1 | 0-1.0 | ✅ 合理 |
| **reg_lambda** | 1.0 | 0.5-2.0 | ✅ 合理 |
| **gamma** | 0.1 | 0-0.5 | ✅ 合理 |
| **min_child_weight** | 1 | 1-10 | ✅ 合理 |
| **subsample** | 0.8 | 0.6-0.9 | ✅ 合理 |
| **colsample_bytree** | 0.8 | 0.6-0.9 | ✅ 合理 |

**结论**: ✅ 正则化参数设置合理，可以防止过拟合

---

## 问题5️⃣：超参数设置检查 ✅

### 当前超参数

```python
base_params = {
    'max_depth': 6,           # 树深度
    'learning_rate': 0.1,     # 学习率
    'n_estimators': 200,      # 树数量
    'subsample': 0.8,         # 样本采样
    'colsample_bytree': 0.8,  # 特征采样
    'early_stopping_rounds': 20
}
```

### ✅ 超参数检查

| 参数 | 当前值 | 推荐范围 | 状态 | 说明 |
|------|--------|----------|------|------|
| **max_depth** | 6 | 4-8 | ✅ 优秀 | 不会太深，防止过拟合 |
| **learning_rate** | 0.1 | 0.01-0.3 | ✅ 合理 | 标准学习率 |
| **n_estimators** | 200 | 100-500 | ✅ 合理 | 配合early_stopping |
| **subsample** | 0.8 | 0.6-0.9 | ✅ 合理 | 防止过拟合 |
| **colsample_bytree** | 0.8 | 0.6-0.9 | ✅ 合理 | 特征随机性 |

**结论**: ✅ 超参数保守合理，max_depth=6不会过度拟合

---

## 问题6️⃣：特征工程检查 ⚠️

### 当前特征数量
- **基础特征**: 21个
- **增强特征**: 8个
- **总计**: 29个

### ⚠️ 特征工程问题

#### 1. 缺少特征重要性分析 ⚠️
**问题**: 没有检查特征重要性，可能过度依赖单一特征

**建议**: 添加特征重要性分析
```python
def analyze_feature_importance(model, feature_names):
    """分析特征重要性"""
    importance = model.feature_importances_
    feature_importance = pd.DataFrame({
        'feature': feature_names,
        'importance': importance
    }).sort_values('importance', ascending=False)
    
    # 检查是否过度集中
    top_3_importance = feature_importance.head(3)['importance'].sum()
    if top_3_importance > 0.7:
        logger.warning(f"⚠️ 特征过度集中：前3个特征占{top_3_importance:.1%}")
    
    return feature_importance
```

#### 2. 缺少交叉特征 ⚠️
**问题**: 只有3个交叉特征（confidence_x_leverage, rsi_x_trend, atr_x_bb_width）

**建议**: 添加更多有意义的交叉特征
```python
# 建议添加的交叉特征
'price_momentum_x_trend',        # 价格动量 × 趋势
'volatility_x_confidence',       # 波动率 × 信心度
'ob_strength_x_structure',       # OB强度 × 市场结构
'rsi_distance_from_50',          # RSI距离中线的距离
'macd_strength',                 # MACD强度（histogram/signal比率）
```

#### 3. 缺少ID/时间戳清理验证 ⚠️
**问题**: 没有明确检查是否包含ID或时间戳特征

**建议**: 添加特征验证
```python
# 不应该在特征中的字段
FORBIDDEN_FEATURES = [
    'symbol', 'timestamp', 'entry_timestamp', 'exit_timestamp',
    'order_id', 'trade_id', 'signal_id'
]

# 验证
for feature in feature_columns:
    if any(forbidden in feature.lower() for forbidden in FORBIDDEN_FEATURES):
        raise ValueError(f"特征包含禁用字段：{feature}")
```

---

## 问题7️⃣：交叉验证检查 ❌

### 当前验证方法
```python
# 使用简单的train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# 使用early_stopping
model.fit(
    X_train, y_train,
    eval_set=[(X_train, y_train), (X_test, y_test)],
    early_stopping_rounds=20
)
```

### ❌ 缺少交叉验证

**问题**: 
1. 没有使用`xgb.cv`进行交叉验证
2. 可能导致超参数不稳定
3. 无法评估模型泛化能力

**建议**: 添加交叉验证
```python
def cross_validate_model(X, y, params, n_folds=5):
    """使用XGBoost原生CV"""
    dtrain = xgb.DMatrix(X, label=y)
    
    cv_results = xgb.cv(
        params=params,
        dtrain=dtrain,
        num_boost_round=params.get('n_estimators', 200),
        nfold=n_folds,
        stratified=True,  # 分层采样
        metrics=['auc', 'error'],
        early_stopping_rounds=20,
        verbose_eval=False
    )
    
    logger.info(f"📊 交叉验证结果：")
    logger.info(f"   最佳轮数：{len(cv_results)}")
    logger.info(f"   测试AUC：{cv_results['test-auc-mean'].iloc[-1]:.4f} "
               f"± {cv_results['test-auc-std'].iloc[-1]:.4f}")
    
    return cv_results
```

---

## 问题8️⃣：模型评估指标 ⚠️

### 当前评估指标

**分类模式**:
```python
metrics = {
    'accuracy': accuracy,
    'precision': precision,
    'recall': recall,
    'f1_score': f1
}
```

### ⚠️ 缺少重要指标

#### 缺少的指标
1. **AUC-ROC** ❌ 未计算
2. **precision_recall曲线** ❌ 未计算
3. **分类阈值分析** ❌ 未分析
4. **分方向详细评估** ⚠️ 有但不完整

#### 建议添加
```python
from sklearn.metrics import roc_auc_score, average_precision_score

# 1. AUC-ROC
y_proba = model.predict_proba(X_test)[:, 1]
auc_score = roc_auc_score(y_test, y_proba)
metrics['auc_roc'] = auc_score

# 2. Average Precision
ap_score = average_precision_score(y_test, y_proba)
metrics['average_precision'] = ap_score

# 3. 不同阈值下的表现
for threshold in [0.3, 0.4, 0.5, 0.6, 0.7]:
    y_pred_thresh = (y_proba >= threshold).astype(int)
    precision = precision_score(y_test, y_pred_thresh)
    recall = recall_score(y_test, y_pred_thresh)
    logger.info(f"阈值{threshold}: Precision={precision:.3f}, Recall={recall:.3f}")
```

---

## 🎯 总结和优先级修复清单

### 🔴 高优先级（必须修复）

1. **数据泄漏** ❌ **必须修复**
   ```python
   # 移除泄漏特征
   - 'hold_duration_hours'  # 未来信息
   ```

2. **验证其他特征** ⚠️ **需要确认**
   ```python
   # 确认这些特征的计算方式
   - 'position_value'
   - 'risk_reward_ratio'
   ```

### 🟡 中优先级（强烈建议）

3. **添加特征重要性分析**
   - 检测特征过度集中
   - 识别冗余特征

4. **添加交叉验证**
   - 使用xgb.cv
   - 评估模型稳定性

5. **添加更多评估指标**
   - AUC-ROC
   - Precision-Recall曲线
   - 阈值分析

### 🟢 低优先级（可选优化）

6. **增加交叉特征**
   - 更多有意义的交互特征

7. **添加特征验证**
   - 禁止ID/时间戳字段

---

## 📊 当前系统评分

| 维度 | 评分 | 状态 |
|------|------|------|
| **数据泄漏风险** | ⭐⭐⚠️ 2/5 | 有泄漏，需修复 |
| **类别不平衡处理** | ⭐⭐⭐⭐⭐ 5/5 | 优秀，双重保护 |
| **权重设置** | ⭐⭐⭐⭐⭐ 5/5 | 合理，不会过大 |
| **正则化** | ⭐⭐⭐⭐⭐ 5/5 | 完善，防止过拟合 |
| **超参数** | ⭐⭐⭐⭐⭐ 5/5 | 保守合理 |
| **特征工程** | ⭐⭐⭐⚠️ 3.5/5 | 良好但可改进 |
| **交叉验证** | ⭐⭐⚠️ 2/5 | 缺少，需添加 |
| **评估指标** | ⭐⭐⭐⚠️ 3.5/5 | 基础齐全但不完整 |

**总体评分**: ⭐⭐⭐⭐☆ **4.0/5.0**

---

## 📝 修复建议的代码

### 1. 移除数据泄漏特征

```python
# src/ml/data_processor.py
class MLDataProcessor:
    def __init__(self):
        # 基础特征（移除hold_duration_hours）
        self.basic_features = [
            'confidence_score', 'leverage', 'position_value',
            # 'hold_duration_hours',  # ❌ 移除：数据泄漏
            'risk_reward_ratio',
            'order_blocks_count', 'liquidity_zones_count',
            'rsi_entry', 'macd_entry', 'macd_signal_entry', 'macd_histogram_entry',
            'atr_entry', 'bb_width_pct', 'volume_sma_ratio',
            'price_vs_ema50', 'price_vs_ema200',
            'trend_1h_encoded', 'trend_15m_encoded', 'trend_5m_encoded',
            'market_structure_encoded', 'direction_encoded'
        ]
```

### 2. 添加特征重要性分析

```python
# src/ml/model_trainer.py
def analyze_feature_importance(self, model, X: pd.DataFrame) -> pd.DataFrame:
    """分析特征重要性"""
    importance = model.feature_importances_
    feature_importance = pd.DataFrame({
        'feature': X.columns,
        'importance': importance
    }).sort_values('importance', ascending=False)
    
    # 检查特征过度集中
    top_3_sum = feature_importance.head(3)['importance'].sum()
    top_5_sum = feature_importance.head(5)['importance'].sum()
    
    logger.info("\n📊 特征重要性分析：")
    logger.info(f"前3个特征重要性：{top_3_sum:.1%}")
    logger.info(f"前5个特征重要性：{top_5_sum:.1%}")
    
    if top_3_sum > 0.7:
        logger.warning(f"⚠️ 特征过度集中：前3个特征占{top_3_sum:.1%}")
    
    # 打印前10个特征
    logger.info("\n前10重要特征：")
    for idx, row in feature_importance.head(10).iterrows():
        logger.info(f"  {row['feature']:25s}: {row['importance']:.4f}")
    
    return feature_importance
```

### 3. 添加交叉验证

```python
# src/ml/model_trainer.py
def cross_validate(self, X, y, params, n_folds=5):
    """XGBoost交叉验证"""
    import xgboost as xgb
    
    dtrain = xgb.DMatrix(X, label=y)
    
    cv_results = xgb.cv(
        params=params,
        dtrain=dtrain,
        num_boost_round=params.get('n_estimators', 200),
        nfold=n_folds,
        stratified=True,
        metrics=['auc', 'error'],
        early_stopping_rounds=20,
        verbose_eval=False,
        seed=42
    )
    
    logger.info("\n📊 交叉验证结果：")
    logger.info(f"最佳轮数：{len(cv_results)}")
    logger.info(f"训练AUC：{cv_results['train-auc-mean'].iloc[-1]:.4f} "
               f"± {cv_results['train-auc-std'].iloc[-1]:.4f}")
    logger.info(f"测试AUC：{cv_results['test-auc-mean'].iloc[-1]:.4f} "
               f"± {cv_results['test-auc-std'].iloc[-1]:.4f}")
    
    # 检查过拟合
    train_auc = cv_results['train-auc-mean'].iloc[-1]
    test_auc = cv_results['test-auc-mean'].iloc[-1]
    overfitting_gap = train_auc - test_auc
    
    if overfitting_gap > 0.1:
        logger.warning(f"⚠️ 可能过拟合：训练AUC - 测试AUC = {overfitting_gap:.4f}")
    
    return cv_results
```

### 4. 添加更多评估指标

```python
# src/ml/model_trainer.py
def comprehensive_evaluation(self, model, X_test, y_test):
    """综合评估"""
    from sklearn.metrics import (
        roc_auc_score, average_precision_score,
        precision_recall_curve, roc_curve
    )
    
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = model.predict(X_test)
    
    metrics = {
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred),
        'f1_score': f1_score(y_test, y_pred),
        'auc_roc': roc_auc_score(y_test, y_proba),
        'average_precision': average_precision_score(y_test, y_proba)
    }
    
    logger.info("\n📊 综合评估指标：")
    logger.info(f"AUC-ROC: {metrics['auc_roc']:.4f}")
    logger.info(f"Average Precision: {metrics['average_precision']:.4f}")
    logger.info(f"F1-Score: {metrics['f1_score']:.4f}")
    
    # 不同阈值的表现
    logger.info("\n🎯 不同阈值下的表现：")
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7]:
        y_pred_thresh = (y_proba >= threshold).astype(int)
        prec = precision_score(y_test, y_pred_thresh)
        rec = recall_score(y_test, y_pred_thresh)
        f1 = f1_score(y_test, y_pred_thresh)
        logger.info(f"阈值{threshold:.1f}: Precision={prec:.3f}, "
                   f"Recall={rec:.3f}, F1={f1:.3f}")
    
    return metrics
```

---

**诊断完成日期**: 2025-10-27  
**诊断人**: Replit Agent  
**下一步**: 根据优先级修复清单进行改进
