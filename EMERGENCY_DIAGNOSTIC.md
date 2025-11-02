# 🚨 紧急诊断方案 - Railway 0信号问题

## 🎯 问题确认

- ✅ RELAXED_SIGNAL_MODE = true (已启用宽松模式)
- ❌ 仍然 0 信号产生
- ✅ WebSocket 运行正常 (100% 命中率)

---

## 🔍 深度诊断步骤

### 步骤1: 检查系统运行时长

**问题**: WebSocket预热失败时，需要等待数据累积

```
检查方法 (Railway Dashboard):
1. 查看部署时间 (Deploy Time)
2. 如果 < 60分钟:
   - H1数据不足 → 无法计算指标
   - 等待至少 60-90 分钟后再检查

解决方案:
• 如果刚重启 < 1小时: 等待数据累积
• 如果已运行 > 1小时: 继续下一步
```

---

### 步骤2: 确认日志中的信号模式

**问题**: 环境变量可能未正确加载

```
在 Railway 日志中搜索:
"信號模式" 或 "Signal Mode"

预期输出:
✅ RuleBasedSignalGenerator 初始化完成
   🎚️ 信號模式: 寬鬆模式  ← 必须显示"寬鬆模式"

如果显示 "嚴格模式":
• 环境变量未生效
• 需要在 Railway → Variables 中添加:
  RELAXED_SIGNAL_MODE=true
• 然后重新部署
```

---

### 步骤3: 检查趋势分布

**问题**: 市场极度震荡

```
在 Railway 日志中搜索:
"信號生成統計" 或 "已掃描"

预期每扫描50个交易对输出一次:
🔍 信號生成統計（已掃描50個，0信號）：
   H1趨勢: bullish=10, bearish=15, neutral=25
   M15趨勢: bullish=12, bearish=13, neutral=25
   M5趨勢: bullish=8, bearish=10, neutral=32

诊断标准:
• 如果 neutral > 70% (H1/M15/M5任一): 极度震荡市 ✅
• 如果没有这个日志: 数据不足或系统未扫描
```

---

### 步骤4: 检查信号拒绝原因

**问题**: 信号生成但被门槛拒绝

```
在 Railway 日志中搜索:
"拒絕開倉" 或 "rejected"

预期输出 (如果有信号生成):
❌ BTCUSDT 拒絕開倉: 勝率不足 | 勝率=38% 信心=42% R:R=2.1
❌ ETHUSDT 拒絕開倉: 信心不足 | 勝率=45% 信心=38% R:R=1.8

诊断标准:
• 如果有拒绝日志: 信号生成正常，但质量不足 40%
• 如果没有拒绝日志: 根本没有生成信号方向
```

---

### 步骤5: 检查 WebSocket 预热状态

**问题**: 数据源问题

```
在 Railway 日志中搜索:
"預熱結果" 或 "Warmup"

预期输出:
預熱結果:
⏱️  耗時: 5秒
✅ 成功: 50/50 (100.0%)
❌ 失敗: 0/50

诊断标准:
• 成功率 100%: 数据正常 ✅
• 成功率 0%: REST API 失败，等待 WebSocket 累积 (60分钟)
• 成功率 50-90%: 部分交易对数据异常
```

---

## 💡 根据诊断结果的解决方案

### 场景A: 系统刚启动 < 1小时

```
原因: H1数据不足 (需要100根K线)
解决: 等待 60-90 分钟

验证: 90分钟后检查日志，应该看到信号
```

---

### 场景B: 市场极度震荡 (neutral > 70%)

```
原因: 即使宽松模式也无法匹配
解决方案:

方案B1: 降低豁免期门槛 (Railway Variables)
BOOTSTRAP_MIN_WIN_PROBABILITY=0.30  # 40% → 30%
BOOTSTRAP_MIN_CONFIDENCE=0.30       # 40% → 30%

方案B2: 创建"超宽松模式"(需修改代码)
• 允许单一时间框架 (仅 H1 或 M15 或 M5)
• 移除 ADX < 15 硬性拒绝
• 接受所有 neutral 市场结构
```

---

### 场景C: 信号生成但被拒绝 (勝率/信心 < 40%)

```
原因: 信号质量普遍低于 40%
解决方案:

方案C1: 降低豁免期门槛 (同方案B1)
BOOTSTRAP_MIN_WIN_PROBABILITY=0.30
BOOTSTRAP_MIN_CONFIDENCE=0.30

方案C2: 调整信心度计算权重 (需修改代码)
• 降低 EMA 偏差权重
• 提高市场结构权重
```

---

### 场景D: 根本没有生成信号方向

```
原因: 宽松模式优先级4-5未被触发
可能性:

1. RELAXED_SIGNAL_MODE 环境变量未生效
   → 检查日志是否显示"寬鬆模式"
   → 如果显示"嚴格模式"，重新设置环境变量

2. 所有交易对都不满足任何优先级
   → 查看趋势统计
   → 如果全是 neutral，继续下一步

3. 代码逻辑问题（极低可能性）
   → 需要检查代码执行路径
```

---

### 场景E: WebSocket 预热失败 (0% 成功率)

```
原因: REST API 不可用，数据尚未累积
解决: 等待 60 分钟后重新检查

验证:
• 60分钟后应该看到 "5m数据将在5分鐘後可用" 等消息
• WebSocket 会自动累积数据
```

---

## 🚀 立即可执行的诊断脚本

### 方案1: 极低门槛测试 (Railway Variables)

```bash
# 在 Railway Dashboard → Variables 添加:
BOOTSTRAP_MIN_WIN_PROBABILITY=0.25  # 极低门槛
BOOTSTRAP_MIN_CONFIDENCE=0.25       # 极低门槛
RELAXED_SIGNAL_MODE=true           # 确认启用

# 然后重新部署
# 如果这样都没信号，问题在数据层
```

---

### 方案2: 禁用 ADX 过滤测试 (需修改代码)

修改 `src/strategies/rule_based_signal_generator.py` 第178行：

```python
# 修改前:
if adx_value < 15:
    logger.debug(f"{symbol} ADX={adx_value:.1f}<15，純震盪市，拒絕信號")
    return None

# 修改后 (临时测试):
if adx_value < 5:  # 极低阈值，基本不过滤
    logger.debug(f"{symbol} ADX={adx_value:.1f}<5，極端震盪市，拒絕信號")
    return None
```

---

### 方案3: 超宽松模式 (需修改代码)

修改 `src/strategies/rule_based_signal_generator.py` 第459行后添加：

```python
if self.config.RELAXED_SIGNAL_MODE:
    # 现有优先级4-5
    # ... (保留原代码)
    
    # 🔥 新增优先级6: 超宽松（任何明确趋势）
    if h1_trend == 'bullish' or m15_trend == 'bullish' or m5_trend == 'bullish':
        if (h1_trend != 'bearish' and m15_trend != 'bearish' and 
            m5_trend != 'bearish' and market_structure != 'bearish'):
            return 'LONG'
    
    if h1_trend == 'bearish' or m15_trend == 'bearish' or m5_trend == 'bearish':
        if (h1_trend != 'bullish' and m15_trend != 'bullish' and 
            m5_trend != 'bullish' and market_structure != 'bullish'):
            return 'SHORT'
```

---

## 📋 诊断清单

请按顺序检查并回答：

- [ ] **系统运行时长**: Railway 部署后已运行 ___ 小时
- [ ] **信号模式确认**: 日志显示 "寬鬆模式" 或 "嚴格模式"？
- [ ] **WebSocket 预热**: 成功率 ___%
- [ ] **趋势统计**: H1 neutral __%, M15 neutral __%, M5 neutral __%
- [ ] **信号拒绝日志**: 有 / 无 "拒絕開倉" 消息
- [ ] **当前豁免期门槛**: 勝率≥__%, 信心≥__%

---

## 🎯 我的下一步建议

根据您的回答，我将：

1. **如果运行 < 60分钟**: 建议等待数据累积
2. **如果市场震荡 > 70%**: 实施方案B1（降低门槛）
3. **如果有拒绝日志**: 实施方案C1（降低门槛）
4. **如果无信号方向**: 实施方案3（超宽松模式）
5. **如果预热失败**: 等待60分钟或检查API配置

请提供上述诊断清单的答案，或直接粘贴 Railway 最新日志（最近2-3个周期），我将精准定位问题！
