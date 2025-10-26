# 📊 v3.2.8 - 动态持仓监控系统

**发布日期**: 2025-10-26  
**状态**: ✅ 已实现，等待部署  
**优先级**: 高（新功能 + 利润保护）

---

## 🎯 核心功能

**自动持仓监控 + 动态止损止盈追踪 + XGBoost特征学习**

每60秒自动监控所有活跃持仓，根据盈亏状态动态调整止损止盈订单，并记录所有调整特征供机器学习优化。

---

## ✨ 新增功能

### 1. PositionMonitor（持仓监控器）

**文件**: `src/services/position_monitor.py`

**功能**：
- 每个交易周期（60秒）自动执行
- 监控所有活跃持仓状态
- 根据盈亏动态调整止损止盈
- 记录21个XGBoost特征

### 2. 追踪止损（Trailing Stop Loss）

**激活条件**: 盈利 > 0.5%

**逻辑**：
```python
# LONG持仓
新止损 = 当前价格 × (1 - 0.3%)
条件: 新止损 > 入场价 AND 新止损 > 当前止损

# SHORT持仓
新止损 = 当前价格 × (1 + 0.3%)
条件: 新止损 < 入场价 AND 新止损 < 当前止损
```

**效果**：
- 随价格有利移动，止损跟随上移/下移
- **保证止损只向有利方向移动**（不会回退）
- 锁定部分利润，防止盈利完全回吐

### 3. 追踪止盈（Trailing Take Profit）

**激活条件**: 盈利 > 1.0%

**逻辑**：
```python
# LONG持仓
新止盈 = 峰值价格 × (1 - 0.5%)
条件: 新止盈 > 当前价格 × 1.005 AND 新止盈 > 当前止盈

# SHORT持仓
新止盈 = 谷值价格 × (1 + 0.5%)
条件: 新止盈 < 当前价格 × 0.995 AND 新止盈 < 当前止盈
```

**效果**：
- 允许利润继续增长
- 从峰值回撤0.5%时触发
- **保证止盈只向有利方向移动**

### 4. XGBoost特征记录

**文件**: `ml_data/adjustments.csv`

**21个特征**：

#### 基本信息
- timestamp, symbol, direction, event_type

#### 价格数据
- entry_price, current_price, highest_price, lowest_price

#### 止损止盈
- old_stop_loss, new_stop_loss, old_take_profit, new_take_profit

#### 盈亏指标
- current_pnl_pct, max_profit_pct, unrealized_pnl_pct

#### 追踪状态
- trailing_stop_active, trailing_profit_active, adjustment_count

#### 计算特征
- price_from_entry_pct, price_from_peak_pct, profit_to_max_profit_ratio

#### 调整原因
- adjustment_reason

---

## 🐛 修复的Bug

### Bug #1: 追踪止损可能倒退

**问题**：价格回撤时，追踪止损会重新计算并可能向不利方向移动，减少保护。

**示例**：
```
LONG持仓 @ 100
价格涨到105 → 止损设为104.685 (105 × 0.997)
价格回落到103 → 止损重算为102.691 (103 × 0.997) ❌ 减少保护！
```

**修复**：
```python
# 只有当新止损比当前止损更有利时才更新
if state['current_stop_loss'] is None or calculated_stop > state['current_stop_loss']:
    new_stop_loss = calculated_stop  # 仅LONG，SHORT相反
```

### Bug #2: 旧值记录时机错误

**问题**：在状态更新之后记录old_stop_loss/old_take_profit，导致记录的是新值而不是旧值。

**修复**：
```python
# 【重要】在更新状态之前记录旧值
old_stop_loss = state['current_stop_loss']
old_take_profit = state['current_take_profit']

# 然后才更新状态
state['current_stop_loss'] = new_stop_loss
```

### Bug #3: 订单丢失

**问题**：当只更新止损时，取消了两个订单但只重新设置了止损，导致止盈订单丢失。

**修复**：
```python
# 确定最终的止损止盈（新的或保持旧的）
final_stop_loss = new_stop_loss if new_stop_loss else state['current_stop_loss']
final_take_profit = new_take_profit if new_take_profit else state['current_take_profit']

# 两个都重新设置
if final_stop_loss:
    await self.trading_service._set_stop_loss(...)
if final_take_profit:
    await self.trading_service._set_take_profit(...)
```

---

## 📝 修改的文件

### 新增文件
1. `src/services/position_monitor.py` - 持仓监控器
2. `POSITION_MONITORING_FEATURE.md` - 功能说明文档
3. `UPDATE_V3.2.8_POSITION_MONITORING.md` - 本文档

### 修改文件
1. `src/ml/data_archiver.py`
   - 添加`adjustments_buffer`
   - 添加`archive_adjustment()`方法
   - 添加`_flush_adjustments()`方法
   - 更新`flush_all()`包含调整缓冲区

2. `src/main.py`
   - 导入`PositionMonitor`
   - 初始化`self.position_monitor`
   - 在主循环中调用`monitor_all_positions()`

---

## 📊 监控日志示例

### 启动监控
```
👁️  監控活躍持倉...
📊 持倉統計: 總計=3, 盈利=2, 虧損=1, 已調整=2
🔄 本週期調整了 2 個持倉的止損止盈
```

### 追踪激活
```
🎯 启动追踪止损: ETHUSDT (当前盈利: 0.8%)
🎯 启动追踪止盈: BTCUSDT (当前盈利: 1.5%)
```

### 调整执行
```
🔄 调整止损止盈: ETHUSDT LONG 盈亏=0.8% 峰值=1.2% 调整次数=1 原因: 追踪止损(LONG)至3955.5
🔄 调整止损止盈: BTCUSDT LONG 盈亏=1.5% 峰值=2.0% 调整次数=2 原因: 追踪止盈(LONG)至112500
```

---

## 🎯 预期效果

### 风险控制
✅ 盈利持仓不会完全回吐  
✅ 小盈利快速锁定  
✅ 大盈利允许继续增长  

### 盈利优化
✅ 捕捉更大的趋势行情  
✅ 减少过早离场  
✅ 提高平均盈亏比  

### 机器学习
✅ 积累调整数据  
✅ 学习最佳参数  
✅ 未来自动优化  

---

## 🚀 部署步骤

### 建议：分两次部署

#### 第一步：v3.2.7（修复开仓问题）
```bash
git add .
git commit -m "v3.2.7 - Fix timestamp parsing + auto topup + 20 USDT minimum"
git push origin main
```

**验证**：
- ✅ 开仓成功
- ✅ 止损止盈设置成功
- ✅ 没有-4164/-4061错误

#### 第二步：v3.2.8（添加持仓监控）
```bash
git add .
git commit -m "v3.2.8 - Add position monitoring with trailing stop/profit + XGBoost features"
git push origin main
```

**验证**：
```bash
# 查看持仓监控
railway logs | grep "監控活躍持倉"

# 查看追踪激活
railway logs | grep "启动追踪"

# 查看调整记录
railway logs | grep "调整止损止盈"
```

---

## ✅ 代码审查

**架构师审查**: 已通过  
**Bug修复**: 3个关键bug已修复  
**LSP检查**: 通过  
**集成测试**: 待部署后验证  

---

## 📚 相关文档

- `POSITION_MONITORING_FEATURE.md` - 完整功能说明
- `UPDATE_V3.2.7_FINAL_FIX.md` - v3.2.7修复说明
- `UPDATE_V3.2.6_HEDGE_MODE.md` - v3.2.6对冲模式支持
- `examples/XGBOOST_DATA_FORMAT.md` - XGBoost数据格式

---

## 🎓 学习目标

通过记录调整特征，XGBoost模型可以学习：

1. **最佳激活时机**：什么盈亏水平启动追踪？
2. **最佳追踪距离**：0.3%/0.5%是否最优？
3. **调整频率影响**：多久调整一次最好？
4. **市场条件适应**：不同波动率下的最佳参数
5. **结果关联**：哪些调整提高了盈利？

---

**准备好了吗？立即部署v3.2.8，开启智能持仓管理！** 🚀
