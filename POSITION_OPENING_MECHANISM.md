# 📖 开仓机制完整分析

**版本**: v3.3.7  
**日期**: 2025-10-27

---

## 🔄 开仓决策流程图

```
信号生成 (ICTStrategy)
    ↓
ML增强 (XGBoost预测) [可选]
    ↓
信号排名 (按信心度排序)
    ↓
遍历每个信号 → _process_signal()
    ↓
┌─────────────────────────────────────┐
│ 1️⃣ 期望值检查                         │
│   - expectancy > 0                  │
│   - profit_factor >= 0.5            │
│   - consecutive_losses < 5          │
│   - daily_loss_pct < 3%             │
│   - 前30笔交易跳过期望值检查（学习模式）    │
└─────────────────────────────────────┘
    ↓ ❌ 拒绝 → 记录到archive，结束
    ↓ ✅ 通过
┌─────────────────────────────────────┐
│ 2️⃣ Rank检查 (决定真实 vs 虚拟)        │
│   - rank <= 3: 考虑真实交易            │
│   - rank > 3: 虚拟倉位                │
└─────────────────────────────────────┘
    ↓
    ├─ rank > 3 ────────────────────────┐
    │                                   │
    │   ┌──────────────────────────┐    │
    │   │ 创建虚拟倉位                │    │
    │   │ - 无数量限制               │    │
    │   │ - 记录到TradeRecorder    │    │
    │   │ - 记录到DataArchiver     │    │
    │   │ - 用于XGBoost学习         │    │
    │   └──────────────────────────┘    │
    │                                   ↓
    ↓ rank <= 3                        结束
    ↓
┌─────────────────────────────────────┐
│ 3️⃣ 真实交易检查                       │
│   A. 获取账户余额                      │
│   B. 风险管理检查:                     │
│      - should_trade() 检查倉位数      │
│      - 熔断器检查                     │
│      - 余额检查                       │
│   C. 杠杆计算:                        │
│      - 基于expectancy动态调整         │
│      - 范围: 3x - 20x                │
└─────────────────────────────────────┘
    ↓ ❌ 拒绝 → 记录到archive，结束
    ↓ ✅ 通过
┌─────────────────────────────────────┐
│ 4️⃣ TRADING_ENABLED检查               │
│   - true: 执行真实交易                 │
│   - false: 创建模擬交易（学习模式）      │
└─────────────────────────────────────┘
    ↓
    ├─ TRADING_ENABLED = false ─────┐
    │                               │
    │   ┌──────────────────────┐    │
    │   │ 模拟交易                │    │
    │   │ - 记录到TradeRecorder │    │
    │   │ - 用于学习模式         │    │
    │   └──────────────────────┘    │
    │                               ↓
    ↓ TRADING_ENABLED = true       结束
    ↓
┌─────────────────────────────────────┐
│ 5️⃣ 执行真实交易                       │
│   A. 计算仓位大小                      │
│   B. 下单 (市价/限价)                  │
│   C. 设置止损止盈                      │
│   D. 记录到TradeRecorder             │
│   E. 记录到DataArchiver              │
│   F. 发送Discord通知                 │
└─────────────────────────────────────┘
    ↓
   结束
```

---

## 📋 详细步骤说明

### 1️⃣ 期望值检查 (`ExpectancyCalculator.should_trade()`)

**检查项**：

| 条件 | 阈值 | 说明 |
|------|------|------|
| **学习模式** | total_trades < 30 | 前30笔交易跳过期望值检查，快速累积数据 |
| **日亏损上限** | daily_loss_pct >= 3% | 触发熔断 |
| **连续亏损** | consecutive_losses >= 5 | 触发冷却期 |
| **期望值** | expectancy < 0 | 禁止开仓 |
| **盈亏比** | profit_factor < 0.5 | 风险过高 |

**代码位置**: `src/main.py:370-385`

```python
can_trade, rejection_reason = self.expectancy_calculator.should_trade(
    expectancy=expectancy_metrics['expectancy'],
    profit_factor=expectancy_metrics['profit_factor'],
    consecutive_losses=expectancy_metrics['consecutive_losses'],
    daily_loss_pct=self.expectancy_calculator.get_daily_loss(completed_trades),
    total_trades=expectancy_metrics['total_trades']
)
```

---

### 2️⃣ Rank检查 - 决定真实交易 vs 虚拟倉位

**关键配置**: `IMMEDIATE_EXECUTION_RANK = 3`

| Rank | 处理方式 | 数量限制 | 用途 |
|------|---------|---------|------|
| **1-3** | 考虑真实交易 | ≤ 3个 | 高信心度信号 |
| **4+** | 虚拟倉位 | 无限制 | XGBoost学习数据 |

**代码位置**: `src/main.py:387-473`

```python
if rank <= Config.IMMEDIATE_EXECUTION_RANK:
    # 尝试真实交易
    ...
else:
    # 创建虚拟倉位
    self.virtual_position_manager.add_virtual_position(signal, rank)
```

---

### 3️⃣ 风险管理检查 (`RiskManager.should_trade()`)

**检查项**：

| 检查项 | 条件 | 说明 |
|-------|------|------|
| **倉位数限制** | active_positions < MAX_POSITIONS (3) | 只检查真实交易 |
| **账户余额** | balance > 最小开仓金额 | 确保有足够资金 |
| **熔断器** | circuit_breaker未触发 | API错误保护 |

**关键修复** (v3.3.7):
```python
can_trade_risk, reason = self.risk_manager.should_trade(
    account_balance,
    self.trading_service.get_active_positions_count(),
    is_real_trading=Config.TRADING_ENABLED  # 🔑 只有真实交易才检查倉位限制
)
```

**虚拟倉位不占用真实倉位限制** ✅

---

### 4️⃣ 杠杆计算 (`RiskManager.calculate_leverage()`)

**动态杠杆策略** (基于期望值和盈亏比):

| Expectancy | Profit Factor | 杠杆 | 说明 |
|------------|--------------|------|------|
| > 1.5% | > 1.5 | **17x** | 优秀表现 |
| > 0.8% | > 1.0 | **12x** | 良好表现 |
| > 0.3% | > 0.8 | **7x** | 一般表现 |
| 其他 | 其他 | **4x** | 保守模式 |
| < 0 | 任意 | **0x** | 禁止开仓 |

**代码位置**: `src/managers/risk_manager.py:115-150`

---

### 5️⃣ TRADING_ENABLED检查

**决定是否执行真实交易**：

| TRADING_ENABLED | Rank ≤ 3 | 行为 |
|----------------|----------|------|
| ✅ **true** | ✅ | **真实交易** - Binance下单 |
| ❌ **false** | ✅ | **模拟交易** - 记录数据但不下单 |
| 任意 | ❌ (rank > 3) | **虚拟倉位** - 仅学习模式 |

**代码位置**: `src/services/trading_service.py:105-122`

```python
if not self.config.TRADING_ENABLED:
    logger.warning("🎮 交易功能未啟用，創建模擬交易（用於學習模式）")
    simulated_trade = self._create_simulated_trade(signal, position_info, quantity)
    # 记录到TradeRecorder以供学习
    self.trade_recorder.record_entry(signal, simulated_trade)
    return simulated_trade
```

---

### 6️⃣ 仓位大小计算 (`RiskManager.calculate_position_size()`)

**计算逻辑**：

```python
# 1. 基础保证金
base_margin = account_balance * 0.10  # 10%

# 2. 信心度调整
confidence_adjusted = base_margin * confidence_score

# 3. 限制范围
position_margin = clamp(
    confidence_adjusted,
    min=account_balance * 0.03,  # 最小3%
    max=account_balance * 0.13   # 最大13%
)

# 4. 风险上限
max_risk = account_balance * 0.02  # 单笔风险≤2%
if position_margin > max_risk:
    position_margin = max_risk

# 5. 硬性限制（v3.3.7新增）
max_position_margin = account_balance * 0.50  # 单个倉位≤50%
if position_margin > max_position_margin:
    position_margin = max_position_margin

# 6. 计算倉位价值
position_value = position_margin * leverage
```

**代码位置**: `src/managers/risk_manager.py:26-82`

---

## 🎯 关键参数总结

| 参数 | 值 | 说明 |
|------|-----|------|
| **IMMEDIATE_EXECUTION_RANK** | 3 | 只有前3名信号考虑真实交易 |
| **MAX_POSITIONS** | 3 | 最多同时持有3个真实倉位 |
| **TRADING_ENABLED** | false (默认) | Railway环境禁用真实交易 |
| **MIN_CONFIDENCE** | 0.45 (45%) | 信号最低信心度 |
| **BASE_LEVERAGE** | 3x | 基础杠杆 |
| **MAX_LEVERAGE** | 20x | 最大杠杆 |
| **MIN_MARGIN_PCT** | 0.03 (3%) | 最小保证金比例 |
| **MAX_MARGIN_PCT** | 0.13 (13%) | 最大保证金比例 |
| **EXPECTANCY_WINDOW** | 30 | 期望值计算窗口 |

---

## 🔍 示例场景

### 场景1: 高信心度信号 (Rank #1)

```
信号生成: BTCUSDT LONG, 信心度 78%
    ↓
期望值检查: expectancy = 1.2%, profit_factor = 1.4 ✅
    ↓
Rank检查: rank = 1 ≤ 3 ✅ → 考虑真实交易
    ↓
风险管理: 活跃倉位 = 2/3 ✅
    ↓
杠杆计算: 12x (良好期望值)
    ↓
TRADING_ENABLED: false → 创建模拟交易
    ↓
结果: 记录到TradeRecorder，用于学习
```

### 场景2: 中等信心度信号 (Rank #5)

```
信号生成: ETHUSDT SHORT, 信心度 62%
    ↓
期望值检查: expectancy = 0.8%, profit_factor = 1.1 ✅
    ↓
Rank检查: rank = 5 > 3 → 虚拟倉位
    ↓
创建虚拟倉位: 
  - 记录开倉到TradeRecorder
  - 记录到DataArchiver
  - 用于XGBoost学习
    ↓
结果: 虚拟倉位，不占用真实倉位限制
```

### 场景3: 期望值为负

```
信号生成: SOLUSDT LONG, 信心度 55%
    ↓
期望值检查: expectancy = -0.3% ❌
    ↓
拒绝: "期望值为负"
    ↓
结果: 记录拒绝原因，不开倉
```

---

## 🐛 常见问题排查

### 问题1: 为什么没有真实交易？

**检查清单**：
1. ✅ `TRADING_ENABLED = true` ?
2. ✅ 信号rank ≤ 3 ?
3. ✅ 期望值 > 0 ?
4. ✅ 活跃倉位数 < 3 ?
5. ✅ 日亏损 < 3% ?
6. ✅ 连续亏损 < 5 ?

### 问题2: 虚拟倉位没有被创建？

**检查清单**：
1. ✅ 信号rank > 3 ?
2. ✅ 期望值检查通过?
3. ✅ 虚拟倉位manager初始化成功?

### 问题3: 模拟交易没有记录到TradeRecorder？

**这是v3.3.7之前的bug**:
- ❌ v3.3.6: 模拟交易不记录
- ✅ v3.3.7: 修复，现在会记录

**代码位置**: `src/services/trading_service.py:114-120`

---

## 📊 数据流总结

### 真实交易数据流 (TRADING_ENABLED=true, rank≤3)

```
Signal → execute_signal() → Binance API
                          ↓
                   record_entry() → TradeRecorder
                          ↓
                   archive_position_open() → DataArchiver
                          ↓
                   Discord通知
```

### 模拟交易数据流 (TRADING_ENABLED=false, rank≤3)

```
Signal → execute_signal() → 模拟下单 (不调用Binance)
                          ↓
                   record_entry() → TradeRecorder ✅ v3.3.7修复
                          ↓
                   archive_position_open() → DataArchiver
```

### 虚拟倉位数据流 (rank>3)

```
Signal → add_virtual_position() → VirtualPositionManager
                                ↓
                         on_open_callback() → record_entry()
                                ↓
                         archive_position_open(is_virtual=True)
```

---

## 🎯 结论

**开仓机制设计合理**：
1. ✅ 多层风险检查（期望值→风险管理→杠杆）
2. ✅ 智能分级（rank 1-3真实，4+虚拟）
3. ✅ 学习模式友好（模拟交易+虚拟倉位）
4. ✅ 数据完整记录（v3.3.7修复）

**没有只做多限制**：
- 代码中LONG和SHORT完全对称
- 如果出现偏向，原因是数据不平衡（已在v3.3.7修复）
