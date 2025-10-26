# v3.3.3 - XGBoost持续训练机制

## 📋 更新日期
2025-10-26

## 🎯 问题描述

### 用户需求
用户希望**确保XGBoost有在实时吸取最新的资料并且持续训练**。

### 当前问题

**现象**：
```python
# 系统启动时
ML 預測器已就緒 (訓練樣本: 100)

# 运行12小时后，累积了150笔新交易
# ❌ 模型仍然使用旧数据（100笔）
# ❌ 没有自动重训练
# ❌ 无法学习最新市场数据
```

**根本原因**：
1. **只在启动时训练一次**：
   ```python
   # src/ml/predictor.py
   def initialize(self):
       self.model = self.trainer.load_model()
       if self.model is None:
           self.trainer.auto_train_if_needed(min_samples=100)
       # ❌ 之后不再训练
   ```

2. **主循环没有重训练检查**：
   - 即使有新的完成交易数据
   - 模型永远不会自动更新
   - 无法适应市场变化

3. **影响**：
   - 模型预测准确率逐渐下降
   - 无法捕捉最新的市场模式
   - ML增强效果减弱

---

## ✅ 解决方案

### 方案1：在MLPredictor添加重训练检查

**修改文件**：`src/ml/predictor.py`

#### 1.1 添加训练追踪变量

```python
class MLPredictor:
    def __init__(self):
        self.trainer = XGBoostTrainer()
        self.data_processor = MLDataProcessor()
        self.model = None
        self.is_ready = False
        self.last_training_samples = 0  # ✨ 记录上次训练时的样本数
        self.retrain_threshold = 50     # ✨ 累积50笔新交易后重训练
```

**设计思路**：
- `last_training_samples`：记录上次训练时使用的数据量
- `retrain_threshold`：设置为50笔，平衡训练频率和计算成本
- 每次训练后更新计数器

#### 1.2 记录初始训练数据量

```python
def initialize(self) -> bool:
    ...
    if self.model is not None:
        self.is_ready = True
        # ✨ 记录初始训练时的样本数
        df = self.data_processor.load_training_data()
        self.last_training_samples = len(df)
        logger.info(f"✅ ML 預測器已就緒 (訓練樣本: {self.last_training_samples})")
        return True
```

#### 1.3 添加重训练检查方法

```python
def check_and_retrain_if_needed(self) -> bool:
    """
    检查是否需要重训练（基于新增数据量）
    
    Returns:
        bool: 是否成功重训练
    """
    try:
        # 加载当前数据
        df = self.data_processor.load_training_data()
        current_samples = len(df)
        
        # 计算新增样本数
        new_samples = current_samples - self.last_training_samples
        
        if new_samples < self.retrain_threshold:
            logger.debug(
                f"新增樣本數不足: {new_samples}/{self.retrain_threshold} "
                f"(總樣本: {current_samples})"
            )
            return False
        
        # ✨ 触发重训练
        logger.info(
            f"🔄 檢測到 {new_samples} 筆新交易數據，開始重訓練模型... "
            f"(總樣本: {current_samples})"
        )
        
        model, metrics = self.trainer.train()
        
        if model is not None:
            self.trainer.save_model(model, metrics)
            self.model = model
            self.last_training_samples = current_samples  # ✨ 更新计数器
            
            logger.info(
                f"✅ 模型重訓練完成！"
                f"準確率: {metrics.get('accuracy', 0):.2%}, "
                f"AUC: {metrics.get('roc_auc', 0):.3f}"
            )
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"重訓練檢查失敗: {e}")
        return False
```

**工作流程**：
1. 检查当前数据量
2. 计算与上次训练的差值
3. 如果新增 ≥ 50笔 → 触发重训练
4. 训练完成 → 保存模型 → 更新计数器

---

### 方案2：主循环调用重训练检查

**修改文件**：`src/main.py`

**修改位置**：`_update_positions()` 方法

```python
async def _update_positions(self):
    """更新所有持仓"""
    try:
        # ... 现有持仓更新逻辑 ...
        
        # ✨ 检查模拟持仓并自动平仓（v3.3.2）
        if not Config.TRADING_ENABLED:
            closed_count = await self.trading_service.check_simulated_positions_for_close()
            if closed_count > 0:
                logger.info(f"🎮 本週期模擬平倉: {closed_count} 筆")
        
        # 🔄 检查是否需要重训练XGBoost模型（每累积50笔新交易）
        if self.ml_predictor and self.ml_predictor.is_ready:
            retrained = await asyncio.to_thread(
                self.ml_predictor.check_and_retrain_if_needed
            )
            if retrained:
                await self.discord_bot.send_alert(
                    "🎯 XGBoost模型已完成重訓練\n"
                    "使用最新交易數據更新模型",
                    "success"
                )
    
    except Exception as e:
        logger.error(f"更新持倉失敗: {e}")
```

**调用频率**：
- 每个交易周期（60秒）检查一次
- 只有累积足够新数据时才真正训练
- 使用`asyncio.to_thread`避免阻塞主循环

---

## 🔄 完整工作流程

### 持续训练生命周期

```
系统启动
    ↓
MLPredictor.initialize()
    ↓
加载或训练初始模型（100笔数据）
    ↓
last_training_samples = 100
    ↓
═════════════════════════════════════
主循环运行（每60秒）
═════════════════════════════════════
    ↓
生成交易信号 → 记录交易数据
    ↓
模拟/真实平仓 → ml_data/trades.jsonl
    ↓
_update_positions() 调用
    ↓
check_and_retrain_if_needed()
    ↓
当前样本: 150, 上次: 100
新增样本: 50 ✅ (≥ 50)
    ↓
🔄 开始重训练...
    ↓
使用最新150笔数据训练
    ↓
保存新模型
    ↓
last_training_samples = 150
    ↓
发送Discord通知
    ↓
继续主循环...
    ↓
（等待下一次累积50笔新数据）
```

---

## 📊 预期效果

### 修复前

```bash
# 系统启动
✅ ML 預測器已就緒 (訓練樣本: 100)

# 12小时后，累积了150笔交易
# ❌ 模型仍然使用旧数据
# ❌ 没有重训练日志
# ❌ 预测准确率可能下降
```

### 修复后

```bash
# 系统启动
✅ ML 預測器已就緒 (訓練樣本: 100)

# 2小时后，累积了50笔新交易
🔄 檢測到 50 筆新交易數據，開始重訓練模型... (總樣本: 150)
開始訓練 XGBoost 模型...
訓練集大小: (120, 21), 測試集大小: (30, 21)
✅ 模型重訓練完成！準確率: 68.50%, AUC: 0.723

# Discord通知
🎯 XGBoost模型已完成重訓練
使用最新交易數據更新模型

# 继续运行...
# 4小时后，又累积了50笔
🔄 檢測到 51 筆新交易數據，開始重訓練模型... (總樣本: 201)
✅ 模型重訓練完成！準確率: 71.20%, AUC: 0.756

# 持续学习...
```

---

## 🎯 技术细节

### 重训练触发条件

```python
# 阈值设置
retrain_threshold = 50

# 触发逻辑
new_samples = current_samples - last_training_samples
if new_samples >= 50:
    # 重训练
```

**为什么选择50笔？**

| 阈值 | 优点 | 缺点 |
|------|------|------|
| **20笔** | 更频繁更新 | CPU消耗高，过拟合风险 |
| **50笔** ✅ | 平衡更新频率和成本 | 适中 |
| **100笔** | CPU消耗低 | 更新太慢，适应性差 |

**50笔的理由**：
- 学习模式需要30笔初始数据
- 50笔提供足够的统计显著性
- 平均每天可能触发1-2次重训练
- 计算成本可控（XGBoost训练<5秒）

### 异步执行策略

```python
# 使用asyncio.to_thread避免阻塞
retrained = await asyncio.to_thread(
    self.ml_predictor.check_and_retrain_if_needed
)
```

**原因**：
- XGBoost训练是CPU密集型操作
- 使用线程池避免阻塞事件循环
- 主循环可以继续处理其他任务

---

## 📁 修改文件

### 核心修改
- ✅ `src/ml/predictor.py`
  - `__init__()` - 添加训练追踪变量
  - `initialize()` - 记录初始训练数据量
  - `check_and_retrain_if_needed()` - 新增重训练检查方法

- ✅ `src/main.py`
  - `_update_positions()` - 调用重训练检查

- ✅ `UPDATE_V3.3.3_XGBOOST_CONTINUOUS_TRAINING.md`
  - 本文档

---

## 🧪 测试验证

### 本地测试

```bash
# 1. 确保有初始训练数据
cat ml_data/trades.jsonl | wc -l  # 应该 ≥ 100

# 2. 启动系统
python -m src.main

# 3. 观察初始训练
grep "ML 預測器已就緒" logs.txt
# 输出: ✅ ML 預測器已就緒 (訓練樣本: 150)

# 4. 等待累积50笔新交易
# （在模拟模式下，可能需要几小时）

# 5. 观察重训练日志
grep "重訓練" logs.txt
# 输出:
# 🔄 檢測到 52 筆新交易數據，開始重訓練模型... (總樣本: 202)
# ✅ 模型重訓練完成！準確率: 69.50%, AUC: 0.735

# 6. 检查Discord通知
# 应该收到 "🎯 XGBoost模型已完成重訓練"
```

### Railway部署后验证

```bash
# 1. 检查初始训练
railway logs | grep "ML 預測器已就緒"

# 2. 监控重训练触发
railway logs --tail 500 | grep "重訓練"

# 3. 验证Discord通知
# 在Discord频道检查是否收到重训练通知

# 4. 检查训练频率
railway logs | grep "模型重訓練完成" | tail -10

# 5. 观察模型性能改进
railway logs | grep "準確率\|AUC"
```

---

## ⚙️ 配置选项

### 调整重训练阈值

如果需要修改重训练频率：

```python
# src/ml/predictor.py
class MLPredictor:
    def __init__(self):
        ...
        self.retrain_threshold = 50  # 修改这里
```

**建议值**：
- **测试环境**：`30` - 快速迭代
- **生产环境**：`50` - 平衡性能
- **高频交易**：`100` - 减少训练频率

---

## 🔮 后续优化

### 计划功能（v3.3.4）

1. **智能重训练调度**
   ```python
   # 基于模型性能动态调整阈值
   if accuracy_dropping:
       retrain_threshold = 20  # 更频繁
   else:
       retrain_threshold = 100  # 节省资源
   ```

2. **A/B测试机制**
   ```python
   # 保留旧模型，新模型影子测试
   old_model_predictions = old_model.predict(X)
   new_model_predictions = new_model.predict(X)
   # 比较性能后决定是否切换
   ```

3. **模型版本管理**
   ```python
   # 保存多个版本
   models/
       xgboost_model_v1.pkl  (100 samples)
       xgboost_model_v2.pkl  (150 samples)
       xgboost_model_v3.pkl  (200 samples)
   ```

4. **性能衰减检测**
   ```python
   # 监控模型准确率趋势
   if current_accuracy < baseline_accuracy * 0.9:
       trigger_urgent_retrain()
   ```

---

## 📝 总结

### 本次更新解决了

✅ **核心需求**：XGBoost持续学习最新数据
- 自动检测新交易数据
- 累积50笔后自动重训练
- 无需手动干预

✅ **系统改进**：
- 模型始终使用最新市场数据
- 提高预测准确率
- Discord实时通知重训练状态

✅ **设计优势**：
- 异步执行不阻塞主循环
- 可配置的重训练阈值
- 完整的日志追踪

### 核心价值

1. **自适应学习** - 模型随市场变化而进化
2. **零干预** - 全自动化训练流程
3. **可观测性** - 清晰的日志和通知
4. **性能保护** - 异步执行避免阻塞

---

## 🔗 相关更新

- **v3.3.1**: 修复止损止盈订单残留问题
- **v3.3.2**: 修复学习模式0/30和PnL异常
- **v3.3.3**: ✨ XGBoost持续训练机制（本次）

---

**版本**: v3.3.3  
**状态**: ✅ 已完成  
**下一步**: 部署到Railway并观察重训练日志
