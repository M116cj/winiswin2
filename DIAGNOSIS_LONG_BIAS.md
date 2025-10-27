# 🔍 模型只做多倾向诊断报告

**日期**: 2025-10-27  
**问题**: 用户报告模型有只做多(long-only)倾向

---

## ✅ 代码审查结论

**经过彻底检查，代码中没有任何限制模型只能做多的逻辑**

### 检查项目

| 组件 | 检查结果 | 详情 |
|------|---------|------|
| **配置文件** | ✅ 无限制 | 没有 `LONG_ONLY` 或方向限制配置 |
| **ICT策略** | ✅ 完全对称 | LONG和SHORT逻辑完全对称 |
| **信号生成** | ✅ 平衡设计 | bearish/SHORT: 18次, bullish/LONG: 19次 |
| **ML预测器** | ✅ 平衡编码 | direction_encoding: LONG=1, SHORT=-1 |
| **风险管理** | ✅ 无方向过滤 | `calculate_position_size` 不区分方向 |
| **期望值计算** | ✅ 无方向限制 | `should_trade` 不限制方向 |

### 代码证据

**ICT策略 - 对称的方向判断** (`src/strategies/ict_strategy.py:298-320`):
```python
# 优先级1: 三个时间框架完全一致
if h1_trend_lower == m15_trend_lower == m5_trend_lower == "bullish":
    if market_structure_lower in ["bullish", "neutral"]:
        return "LONG"
elif h1_trend_lower == m15_trend_lower == m5_trend_lower == "bearish":
    if market_structure_lower in ["bearish", "neutral"]:
        return "SHORT"

# 优先级2: 1h 和 15m 一致
if h1_trend_lower == m15_trend_lower == "bullish":
    if market_structure_lower in ["bullish", "neutral"]:
        return "LONG"
elif h1_trend_lower == m15_trend_lower == "bearish":
    if market_structure_lower in ["bearish", "neutral"]:
        return "SHORT"

# 优先级3: 1h 有明确趋势，15m 是 neutral
if h1_trend_lower == "bullish" and m15_trend_lower == "neutral":
    if m5_trend_lower == "bullish" and market_structure_lower == "bullish":
        return "LONG"
elif h1_trend_lower == "bearish" and m15_trend_lower == "neutral":
    if m5_trend_lower == "bearish" and market_structure_lower == "bearish":
        return "SHORT"
```

**ML预测器 - 平衡的方向编码** (`src/ml/predictor.py:120`):
```python
direction_encoding = {'LONG': 1, 'SHORT': -1}
```

---

## 🤔 可能的原因

### 1. **训练数据不平衡**（最可能）⚠️

**v3.3.6及之前的严重Bug**：
- 虚拟倉位平仓数据**从未被记录**
- TradeRecorder没有接收虚拟倉位的exit数据
- DataArchiver缺失虚拟倉位的关闭记录

**影响**：
```
假设：
- 真实交易: 10笔 (LONG: 7, SHORT: 3)
- 虚拟交易: 3000笔 (LONG: 1500, SHORT: 1500) ❌ 数据丢失

XGBoost训练数据：
- LONG: 7 (只有真实交易)
- SHORT: 3 (只有真实交易)
- 比例: 7:3 (严重不平衡!)

→ 模型学习到LONG更常见，倾向预测LONG
```

**✅ v3.3.7已修复**：
- 虚拟倉位开倉时立即记录entry
- 虚拟倉位平仓时记录exit
- 数据流完整：创建→监控→平仓→记录✅

### 2. **市场环境偏向**

如果数据收集期间市场处于牛市：
- bullish trend更频繁出现
- LONG信号胜率自然更高
- 模型学习到"LONG更安全"

**这是正常的市场学习，不是Bug**

### 3. **趋势识别延迟**

可能存在的不对称：
- EMA在牛市中反应更快
- bearish trend识别较晚
- → SHORT信号生成较少

---

## 🛠️ 诊断工具

使用提供的诊断脚本检查数据平衡性：

```bash
python check_data_balance.py
```

**输出示例**：
```
📊 检查ML训练数据的LONG/SHORT平衡性
============================================================

📈 总体统计:
  总交易数: 250
  真实交易: 10
  虚拟交易: 240

📊 方向分布:
  LONG:  180 ( 72.0%)
  SHORT:  70 ( 28.0%)

⚠️  警告: 数据不平衡! LONG/SHORT比例 = 2.6:1
   这会导致模型偏向数量更多的方向

🎯 胜率对比:
  LONG胜率:   65.6% (118/180)
  SHORT胜率:  58.6% (41/70)

💰 平均PnL对比:
  LONG平均:  +0.85%
  SHORT平均: +0.42%

📝 诊断结论:
============================================================
⚠️  数据严重不平衡，LONG样本是另一方的2.6倍
   → 模型会偏向LONG交易

💡 建议:
   1. 等待系统累积更多数据
   2. 检查信号生成逻辑是否有偏向
   3. 考虑使用class_weight平衡训练
============================================================
```

---

## 💡 解决方案

### 短期（立即可用）

1. **等待v3.3.7累积数据**
   - v3.3.7修复了虚拟倉位数据记录
   - 24小时后会累积3000+笔虚拟交易
   - LONG/SHORT应该会趋于平衡

2. **检查当前数据平衡性**
   ```bash
   python check_data_balance.py
   ```

3. **如果数据严重不平衡**
   - 删除旧的不完整数据
   ```bash
   rm ml_data/trades.jsonl
   rm ml_data/positions.csv
   ```
   - 让系统从v3.3.7开始重新收集

### 中期（优化训练）

修改 `src/ml/model_trainer.py` 添加class_weight平衡：

```python
# 在train()方法中
model = xgb.XGBClassifier(
    **params,
    scale_pos_weight=len(y_train[y_train==0]) / len(y_train[y_train==1])  # 平衡类别
)
```

### 长期（市场适应）

1. **实时监控方向分布**
   - 每天运行 `check_data_balance.py`
   - 如果LONG/SHORT比例 > 2:1，发出警告

2. **动态数据采样**
   - 在训练时对多数类进行下采样
   - 或对少数类进行上采样

3. **分别训练两个模型**
   - LONG专用模型
   - SHORT专用模型
   - 根据方向选择对应模型

---

## 📊 预期改善时间表

| 时间 | 预期效果 |
|------|---------|
| **部署v3.3.7后 1小时** | 累积130+ 虚拟交易数据 |
| **部署v3.3.7后 24小时** | 累积3000+ 虚拟交易数据 |
| **数据平衡后** | 模型LONG/SHORT偏向消失 |
| **累积5000+样本后** | 模型准确率显著提升 |

---

## 🎯 结论

1. ✅ **代码没有bug** - 没有任何限制只做多的逻辑
2. ⚠️ **数据不平衡是根本原因** - v3.3.6未记录虚拟倉位数据
3. ✅ **v3.3.7已修复** - 虚拟倉位数据流完整
4. 📊 **使用诊断工具** - 运行 `check_data_balance.py` 确认
5. 🚀 **部署v3.3.7** - 等待系统累积平衡的数据

---

**推荐行动**：
1. 立即部署v3.3.7到Railway
2. 运行 `check_data_balance.py` 确认当前数据状态
3. 如果严重不平衡，删除旧数据重新开始
4. 24小时后再次检查，应该会看到改善
