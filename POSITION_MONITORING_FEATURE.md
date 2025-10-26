# 📊 动态止损止盈追踪系统

**版本**: v3.2.8  
**功能**: 自动持仓监控 + 动态止损止盈调整 + XGBoost特征记录  
**状态**: ✅ 已实现

---

## 🎯 功能概述

每60秒自动监控所有活跃持仓，根据市场变化动态调整止损止盈位置，并将所有调整特征记录到数据归档器供XGBoost学习。

---

## ⚙️ 核心组件

### 1. PositionMonitor（持仓监控器）

**文件**: `src/services/position_monitor.py`

**功能**：
- 每个交易周期（60秒）自动执行
- 监控所有活跃持仓的盈亏状态
- 自动调整止损止盈订单
- 记录所有调整特征供XGBoost学习

---

## 🔄 动态调整策略

### 追踪止损（Trailing Stop Loss）

**触发条件**：
- 当前盈利 > 0.5%

**调整规则**：
```python
# LONG持仓
新止损 = 当前价格 × (1 - 0.3%)
条件: 新止损必须 > 入场价（保护利润）

# SHORT持仓
新止损 = 当前价格 × (1 + 0.3%)
条件: 新止损必须 < 入场价（保护利润）
```

**效果**：
- 随着价格朝有利方向移动，止损也跟随上移/下移
- 确保锁定至少部分利润
- 防止盈利回吐

---

### 追踪止盈（Trailing Take Profit）

**触发条件**：
- 当前盈利 > 1.0%

**调整规则**：
```python
# LONG持仓
峰值价格 = 持仓期间的最高价
新止盈 = 峰值价格 × (1 - 0.5%)

# SHORT持仓
谷值价格 = 持仓期间的最低价
新止盈 = 谷值价格 × (1 + 0.5%)
```

**效果**：
- 允许利润继续增长
- 当价格从峰值回撤0.5%时触发平仓
- 最大化盈利空间

---

## 📊 监控日志示例

### 启动持仓监控
```
👁️  監控活躍持倉...
📊 持倉統計: 總計=3, 盈利=2, 虧損=1, 已調整=1
🔄 本週期調整了 1 個持倉的止損止盈
```

### 追踪止损激活
```
🎯 启动追踪止损: ETHUSDT (当前盈利: 0.8%)
🔄 调整止损止盈: ETHUSDT LONG 盈亏=0.8% 峰值=1.2% 调整次数=1 原因: 追踪止损(LONG)至3955.5
```

### 追踪止盈激活
```
🎯 启动追踪止盈: BTCUSDT (当前盈利: 1.5%)
🔄 调整止损止盈: BTCUSDT LONG 盈亏=1.5% 峰值=2.0% 调整次数=2 原因: 追踪止盈(LONG)至112500
```

---

## 🤖 XGBoost特征记录

每次调整都会记录以下特征到`ml_data/adjustments.csv`：

### 基本信息
- `timestamp`: 调整时间
- `symbol`: 交易对
- `direction`: 方向（LONG/SHORT）
- `event_type`: "stop_loss_take_profit_adjustment"

### 价格数据
- `entry_price`: 入场价
- `current_price`: 当前价
- `highest_price`: 持仓期间最高价
- `lowest_price`: 持仓期间最低价

### 止损止盈
- `old_stop_loss`: 旧止损价
- `new_stop_loss`: 新止损价
- `old_take_profit`: 旧止盈价
- `new_take_profit`: 新止盈价

### 盈亏指标
- `current_pnl_pct`: 当前盈亏百分比
- `max_profit_pct`: 历史最大盈利百分比
- `unrealized_pnl_pct`: 未实现盈亏百分比

### 追踪状态
- `trailing_stop_active`: 追踪止损是否激活
- `trailing_profit_active`: 追踪止盈是否激活
- `adjustment_count`: 累计调整次数

### 计算特征
- `price_from_entry_pct`: 当前价格距入场价百分比
- `price_from_peak_pct`: 当前价格距峰值百分比
- `profit_to_max_profit_ratio`: 当前盈利/最大盈利比率

### 调整原因
- `adjustment_reason`: 调整原因描述

---

## 📈 工作流程

```
每60秒循环:
    ↓
1. 获取所有活跃持仓
    ↓
2. 对每个持仓:
    ├─ 计算当前盈亏
    ├─ 更新峰值/谷值
    ├─ 检查是否需要调整
    └─ 如果需要:
        ├─ 取消旧的止损止盈订单
        ├─ 设置新的止损止盈订单
        └─ 记录调整特征到DataArchiver
    ↓
3. 输出监控统计
```

---

## 🎓 XGBoost学习目标

通过记录这些特征，XGBoost模型可以学习：

### 1. 最佳调整时机
- 什么盈亏水平应该启动追踪？
- 调整频率如何影响最终收益？

### 2. 最佳调整幅度
- 追踪距离设置多少最优？
- 不同市场条件下的最佳参数？

### 3. 调整与结果的关联
- 调整后的持仓表现如何？
- 哪些调整提高了盈利？
- 哪些调整导致过早出场？

### 4. 模式识别
- 盈利回撤模式
- 趋势持续性
- 最佳离场时机

---

## 🔧 配置参数

可以在`PositionMonitor`中调整以下参数：

```python
# 追踪止损
self.trailing_stop_pct = 0.5  # 盈利>0.5%时启动
self.trailing_distance_pct = 0.3  # 距离当前价0.3%

# 追踪止盈
self.trailing_profit_trigger_pct = 1.0  # 盈利>1%时启动
self.trailing_profit_distance_pct = 0.5  # 距离峰值0.5%
```

---

## 📊 数据文件

### adjustments.csv（新增）

记录所有止损止盈调整事件：

```csv
timestamp,symbol,direction,event_type,entry_price,current_price,highest_price,...
2025-10-26 10:00:00,ETHUSDT,LONG,stop_loss_take_profit_adjustment,3950.0,3970.0,3980.0,...
2025-10-26 10:05:00,BTCUSDT,LONG,stop_loss_take_profit_adjustment,111000,111500,111800,...
```

**用途**：
- 分析调整策略效果
- 训练XGBoost模型优化参数
- 回测不同调整策略

---

## ✅ 实施清单

### 已完成
- [x] 创建PositionMonitor服务
- [x] 实现追踪止损逻辑
- [x] 实现追踪止盈逻辑
- [x] DataArchiver添加archive_adjustment方法
- [x] 集成到主循环（每60秒执行）
- [x] 记录XGBoost特征
- [x] 添加监控日志输出

### 下一步优化（可选）
- [ ] 基于ATR动态调整追踪距离
- [ ] 不同交易对使用不同参数
- [ ] 基于波动率调整触发阈值
- [ ] 添加部分止盈功能
- [ ] XGBoost模型自动优化参数

---

## 🧪 测试验证

### 步骤1：部署v3.2.8
```bash
git add .
git commit -m "v3.2.8 - Add position monitoring with trailing stop/profit + XGBoost features"
git push origin main
```

### 步骤2：观察日志

等待有活跃持仓后，检查Railway日志：

```bash
# 查看持仓监控
railway logs | grep "監控活躍持倉"

# 查看追踪止损激活
railway logs | grep "启动追踪止损"

# 查看调整记录
railway logs | grep "调整止损止盈"
```

### 步骤3：检查数据文件

下载或查看`ml_data/adjustments.csv`，确认记录格式正确。

---

## 📚 相关文档

- `STOP_LOSS_TAKEPROFIT_CHECK.md` - 止损止盈执行情况分析
- `examples/XGBOOST_DATA_FORMAT.md` - XGBoost数据格式说明
- `src/services/position_monitor.py` - 持仓监控器源代码
- `src/ml/data_archiver.py` - 数据归档器源代码

---

## 💡 使用示例

### 场景1：LONG持仓盈利扩大

```
10:00 - 开仓: ETHUSDT LONG @ 3950
10:05 - 价格: 3970 (+0.5%) → 启动追踪止损
        新止损: 3970 × 0.997 = 3958
10:10 - 价格: 3990 (+1.0%) → 启动追踪止盈
        峰值: 3990
        新止损: 3990 × 0.997 = 3978
        新止盈: 3990 × 0.995 = 3970
10:15 - 价格: 4010 (+1.5%)
        峰值: 4010
        新止损: 4010 × 0.997 = 3998
        新止盈: 4010 × 0.995 = 3990
10:20 - 价格回落到3995 → 触发止盈 @ 3990
结果: 锁定+1.0%利润
```

### 场景2：LONG持仓盈利回撤

```
10:00 - 开仓: BTCUSDT LONG @ 111000
10:05 - 价格: 111600 (+0.54%) → 启动追踪止损
        新止损: 111600 × 0.997 = 111265
10:10 - 价格回落到111200 (-0.36%)
        追踪止损触发 @ 111265
结果: 锁定+0.24%利润（避免回吐）
```

---

## 🎯 预期效果

### 风险控制
- ✅ 盈利持仓不会完全回吐
- ✅ 小亏损快速止损
- ✅ 大盈利允许继续增长

### 盈利优化
- ✅ 捕捉更大的趋势行情
- ✅ 减少过早离场
- ✅ 提高平均盈利/亏损比

### 机器学习
- ✅ 积累大量调整数据
- ✅ 学习最佳调整策略
- ✅ 持续优化参数

---

**准备好了吗？现在就部署v3.2.8，开启智能持仓管理！** 🚀
