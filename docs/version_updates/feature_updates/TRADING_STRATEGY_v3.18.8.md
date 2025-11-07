# 📊 SelfLearningTrader v3.18.8 交易策略与信号生成规则

**更新日期**: 2025-11-01  
**版本**: v3.18.8+  
**核心理念**: 模型拥有无限制杠杆控制权，唯一准则是胜率 × 信心度

---

## 🎯 核心策略架构

### 策略类型
- **主策略**: ICT/SMC (Inner Circle Trader / Smart Money Concepts)
- **信号生成器**: RuleBasedSignalGenerator（规则驱动）
- **决策引擎**: SelfLearningTrader（智能杠杆控制）

### 技术指标体系
| 指标 | 周期 | 用途 |
|------|------|------|
| **EMA** | 20, 50 | 趋势判断、支撑/阻力 |
| **MACD** | 12, 26, 9 | 动能确认 |
| **RSI** | 14 | 超买超卖、动能 |
| **ADX** | 14 | 趋势强度过滤（≥20） |
| **ATR** | 14 | 波动率、止损计算 |
| **Bollinger Bands** | 20, 2σ | 波动率、超买超卖 |

---

## 📈 信号生成流程（8步骤）

### Step 1: 数据验证
```python
必需时间框架: ['1h', '15m', '5m']
最小K线数量: 50根（每个时间框架）
数据完整性: 无缺失值，价格合理
```

### Step 2: 多时间框架趋势判断

#### v3.18.8+ 简化趋势逻辑（已优化）
```python
# 旧版（v3.18.7-）：极严格，96.8% neutral
价格 > EMA20 > EMA50 > EMA100  # Bullish（仅1.6%符合）
价格 < EMA20 < EMA50 < EMA100  # Bearish（仅1.6%符合）

# 新版（v3.18.8+）：简化，预估25-35% bullish/bearish
价格 > EMA20 AND EMA20 > EMA50  # Bullish
价格 < EMA20 AND EMA20 < EMA50  # Bearish
否则 → Neutral
```

**趋势确认增强**：
- ✅ **ADX过滤**: ADX < 20 → 震荡市，拒绝信号
- ✅ **EMA斜率**: 斜率 < 0.01% → 趋势衰竭，拒绝信号

**预期改善**：
- Bullish: 1.6% → 25-35%
- Bearish: 1.6% → 25-35%
- Neutral: 96.8% → 30-50%

### Step 3: 市场结构分析

```python
市场结构 = determine_market_structure(15m数据)

结构类型:
- Bullish: 高点抬升 + 低点抬升（上升趋势）
- Bearish: 高点降低 + 低点降低（下降趋势）
- Neutral: 横盘或结构不明确
```

### Step 4: Order Blocks 识别

```python
识别条件:
1. 大幅价格移动（突破）
2. 成交量 > 1.5倍平均值
3. 价格拒绝（rejection）≥ 0.5%
4. 最大测试次数: 3次
5. 时效衰减: 48小时后开始衰减

Order Block类型:
- Bullish OB: 强势上涨前最后一根阴线区域（支撑）
- Bearish OB: 强势下跌前最后一根阳线区域（阻力）
```

### Step 5: 流动性区域（Liquidity Zones）

```python
识别方法:
1. 回溯20根K线
2. 寻找价格聚集区域（容差: 0.2%）
3. 计数 ≥ 3次触碰
4. 强度评分: 触碰次数 / 总K线数

区域类型:
- Resistance（阻力）: 高点聚集区
- Support（支撑）: 低点聚集区
```

### Step 6: 信号方向决策

#### 🔥 v3.18.7+ 双模式支持

**严格模式（RELAXED_SIGNAL_MODE=false）**
```python
优先级1: 三时间框架完全一致（最高置信度）
- LONG: 1h=bullish AND 15m=bullish AND 5m=bullish AND structure∈[bullish,neutral]
- SHORT: 1h=bearish AND 15m=bearish AND 5m=bearish AND structure∈[bearish,neutral]

优先级2: 1h + 15m 一致（5m可不同）
- LONG: 1h=bullish AND 15m=bullish AND structure∈[bullish,neutral]
- SHORT: 1h=bearish AND 15m=bearish AND structure∈[bearish,neutral]

优先级3: 1h有趋势，15m neutral（等待确认）
- LONG: 1h=bullish AND 15m=neutral AND 5m=bullish AND structure=bullish
- SHORT: 1h=bearish AND 15m=neutral AND 5m=bearish AND structure=bearish

拒绝: 其他所有情况
```

**宽松模式（RELAXED_SIGNAL_MODE=true）**
```python
允许部分时间框架对齐:
- LONG: (1h=bullish OR 15m=bullish) AND 5m≠bearish
- SHORT: (1h=bearish OR 15m=bearish) AND 5m≠bullish

预期信号增加: 50-70%
```

### Step 7: 信心度计算（五维评分系统）

#### 🔥 v3.18.8+ EMA偏差评分替代趋势对齐

**评分维度**（总分100分）：

| 维度 | 权重 | 评分逻辑 | 说明 |
|------|------|----------|------|
| **EMA偏差** | 40% | 基于价格与EMA20/50的偏离度 | v3.18.8+新增 |
| **市场结构** | 20% | structure与direction一致性 | 高点低点分析 |
| **价格位置** | 20% | 相对Order Blocks/流动性区域 | 风险评估 |
| **动能指标** | 10% | RSI + MACD方向 | 动能确认 |
| **波动率** | 10% | Bollinger带宽 | 市场活跃度 |

#### EMA偏差评分详解（40%权重）

**计算公式**:
```python
# 1. 计算6个时间框架的EMA偏差
h1_ema20_dev = (price - h1_ema20) / h1_ema20
h1_ema50_dev = (price - h1_ema50) / h1_ema50
m15_ema20_dev = (price - m15_ema20) / m15_ema20
m15_ema50_dev = (price - m15_ema50) / m15_ema50
m5_ema20_dev = (price - m5_ema20) / m5_ema20
m5_ema50_dev = (price - m5_ema50) / m5_ema50

# 2. 计算平均偏差
avg_ema20_dev = mean([h1, m15, m5]_ema20_dev)
avg_ema50_dev = mean([h1, m15, m5]_ema50_dev)

# 3. 偏差评分（0-40分）
For LONG:
  if avg_ema20_dev > 0.03: score = 40  # Excellent（>3%）
  elif avg_ema20_dev > 0.02: score = 32  # Good（2-3%）
  elif avg_ema20_dev > 0.01: score = 24  # Fair（1-2%）
  elif avg_ema20_dev > 0: score = 16  # Poor（0-1%）
  else: score = 0  # 价格低于EMA，无效

For SHORT: 反向逻辑（负偏差越大越好）
```

**偏差质量等级**:
- **Excellent** (40分): avg_ema20_dev > ±3%（强趋势）
- **Good** (32分): avg_ema20_dev > ±2%（中等趋势）
- **Fair** (24分): avg_ema20_dev > ±1%（弱趋势）
- **Poor** (16分): avg_ema20_dev > 0（极弱趋势）

**优势**:
- ✅ 量化趋势强度，不再是简单的bullish/bearish二元判断
- ✅ 多时间框架综合考虑，避免单一时间框架误导
- ✅ 区分信号质量等级（Excellent/Good/Fair/Poor）

#### 其他维度评分

**市场结构（20%）**:
```python
if direction == "LONG":
  if structure == "bullish": score = 20
  elif structure == "neutral": score = 10
  else: score = 0
```

**价格位置（20%）**:
```python
if direction == "LONG":
  if price在bullish OB上方: score = 20
  elif price远离OB: score = 10
  else: score = 5
```

**动能指标（10%）**:
```python
rsi_score = 5 if (LONG: 40<RSI<70) or (SHORT: 30<RSI<60)
macd_score = 5 if MACD方向与signal一致
total = rsi_score + macd_score
```

**波动率（10%）**:
```python
bb_width_percentile = bb_width在过去20根K线中的百分位
if percentile > 60%: score = 10  # 高波动
elif percentile > 40%: score = 7
else: score = 3  # 低波动
```

### Step 8: 止损止盈计算

#### 止损（Stop Loss）
```python
# 基于ATR动态计算
sl_distance = ATR × 2.0

For LONG:
  stop_loss = entry_price - sl_distance
  
For SHORT:
  stop_loss = entry_price + sl_distance

# Order Block增强
if 存在nearby_bullish_OB:
  stop_loss = min(stop_loss, OB.low - 0.1%)
```

#### 止盈（Take Profit）
```python
# 基于风报比
tp_distance = sl_distance × 1.5  # Config.SLTP_TP_TO_SL_RATIO

For LONG:
  take_profit = entry_price + tp_distance
  
For SHORT:
  take_profit = entry_price - tp_distance

# 流动性区域调整
if 存在阻力位:
  take_profit = min(take_profit, resistance - 0.1%)
```

---

## 🎓 勝率估算（v3.18.8+ EMA偏差驱动）

### 预估公式
```python
win_probability = base_rate × structure_boost × deviation_boost × rr_penalty

base_rate（基础胜率）:
- Excellent deviation (>3%): 0.65
- Good deviation (2-3%): 0.58
- Fair deviation (1-2%): 0.50
- Poor deviation (0-1%): 0.42

structure_boost（市场结构加成）:
- structure一致: ×1.1
- structure neutral: ×1.0
- structure相反: ×0.9

deviation_boost（偏差加成）:
- avg_ema20_dev > 4%: ×1.15（超强趋势）
- avg_ema20_dev > 3%: ×1.10
- avg_ema20_dev > 2%: ×1.05
- 其他: ×1.0

rr_penalty（风报比惩罚）:
- RR > 2.5: ×0.95（目标过高）
- RR > 2.0: ×0.98
- 其他: ×1.0

最终限制: 0.35 ≤ win_probability ≤ 0.85
```

### 示例计算
```python
# 案例1: Excellent信号
deviation = 3.5% (Excellent)
structure = bullish (一致)
rr_ratio = 1.8

win_prob = 0.65 × 1.1 × 1.10 × 1.0 = 0.7865 → 78.65%

# 案例2: Poor信号
deviation = 0.5% (Poor)
structure = neutral
rr_ratio = 2.3

win_prob = 0.42 × 1.0 × 1.0 × 0.95 = 0.399 → 39.9%
```

---

## 🚀 信号质量分级（v3.18.8+）

基于**confidence分数**和**EMA偏差质量**的双维度分级：

| 等级 | Confidence | EMA偏差 | 特征 | 适用阶段 |
|------|------------|---------|------|----------|
| **Excellent** | 70-100% | >3% | 三时间框架完美对齐，强趋势 | 正常期 |
| **Good** | 60-70% | 2-3% | 1h+15m对齐，中等趋势 | 正常期 |
| **Fair** | 50-60% | 1-2% | 部分对齐，弱趋势 | 豁免期 |
| **Poor** | 40-50% | 0-1% | 单时间框架，极弱趋势 | 豁免期 |
| **Rejected** | <40% | 负偏差 | 不符合基本条件 | 拒绝 |

### 豁免期（前100笔交易）
```python
BOOTSTRAP_MIN_CONFIDENCE = 0.40  # 允许Poor/Fair信号
BOOTSTRAP_MIN_WIN_PROBABILITY = 0.40

正常期（100笔后）:
MIN_CONFIDENCE = 0.60  # 仅接受Good/Excellent
MIN_WIN_PROBABILITY = 0.60
```

---

## 📊 标准化信号格式

```python
signal = {
    # 基本信息
    'symbol': 'BTCUSDT',
    'direction': 'LONG' | 'SHORT',
    'timestamp': datetime,
    
    # 价格水平
    'entry_price': 50000.0,
    'stop_loss': 49000.0,
    'take_profit': 51500.0,
    
    # 评估指标
    'confidence': 0.65,  # 0-1范围
    'win_probability': 0.68,  # 0-1范围
    'rr_ratio': 1.5,  # 风报比
    
    # 技术指标
    'indicators': {
        'rsi': 55.0,
        'macd': 120.5,
        'macd_signal': 110.2,
        'macd_hist': 10.3,
        'adx': 28.5,
        'di_plus': 25.0,
        'di_minus': 15.0,
        'atr': 500.0,
        'bb_upper': 51000,
        'bb_middle': 50000,
        'bb_lower': 49000,
        'bb_width': 0.04
    },
    
    # EMA偏差（v3.18.8+）
    'ema_deviation': {
        'h1_ema20_dev': 0.025,  # 2.5%
        'h1_ema50_dev': 0.035,  # 3.5%
        'm15_ema20_dev': 0.020,
        'm15_ema50_dev': 0.030,
        'm5_ema20_dev': 0.015,
        'm5_ema50_dev': 0.025,
        'avg_ema20_dev': 0.020,  # 平均2.0%
        'avg_ema50_dev': 0.030,  # 平均3.0%
        'deviation_score': 32,  # Good等级（40分满分）
        'deviation_quality': 'Good'
    },
    
    # 市场环境
    'timeframes': {
        '1h_trend': 'bullish',
        '15m_trend': 'bullish',
        '5m_trend': 'neutral'
    },
    'market_structure': 'bullish',
    'order_blocks': 2,
    'liquidity_zones': 3,
    
    # 评分细节
    'sub_scores': {
        'ema_deviation': 32,  # v3.18.8+替代trend_alignment
        'market_structure': 20,
        'price_position': 15,
        'momentum': 8,
        'volatility': 7,
        'total': 82
    },
    
    # 信号原因
    'reasoning': "LONG信号 | EMA偏差2.0%(Good) | 1h/15m多头对齐 | 市场结构看涨 | RSI中性区 | 总分82/100"
}
```

---

## 🛡️ 风险控制规则

### 开仓前检查
```python
1. ✅ 信号质量检查
   - 豁免期: confidence ≥ 0.40, win_prob ≥ 0.40
   - 正常期: confidence ≥ 0.60, win_prob ≥ 0.60

2. ✅ 风报比验证
   - 最小: 1.0（保本）
   - 最大: 3.0（避免目标过高）

3. ✅ 全倉保护
   - 总保证金 ≤ 90%账户权益
   - 单仓 ≤ 50%账户权益

4. ✅ 并发限制
   - 每周期最多5个新仓位
   - 总持仓数量无上限（v3.17+）
```

### 持仓监控（24/7）
```python
监控频率: 每2秒

触发平仓条件:
1. 🔴 100%虧損熔斷: PnL% ≤ -99%（立即平仓）
2. 🟡 止损触发: price ≤ stop_loss
3. 🟢 止盈触发: price ≥ take_profit
4. 🔵 强制止盈: 持仓24h + PnL > 5%
5. 🟠 逆势平仓: 趋势反转 + PnL < 0
6. 🟣 手动平仓: 用户操作
7. ⚫ 全倉保护: 总保证金 > 85%权益（平最差仓）
```

---

## 🎯 SelfLearningTrader决策流程

### 1. 信号接收与验证
```python
base_signal = RuleBasedSignalGenerator.generate_signal(symbol, data)

if base_signal is None:
    return None  # 无有效信号
```

### 2. ML模型增强（v3.18.6+）
```python
if ML模型已加载:
    ml_win_prob = MLModel.predict(signal的44个特征)
    
    if ml_win_prob is not None:
        signal['win_probability'] = ml_win_prob  # 覆盖规则引擎
        signal['prediction_source'] = 'ml_model'
    else:
        signal['prediction_source'] = 'rule_engine_fallback'
else:
    signal['prediction_source'] = 'rule_engine_only'
```

### 3. 杠杆计算（无上限）
```python
leverage = LeverageEngine.calculate(
    win_probability=signal['win_probability'],
    confidence=signal['confidence']
)

公式:
leverage = max(0.5, win_prob × confidence × 100)

示例:
- win_prob=0.70, confidence=0.65 → leverage = 45.5x
- win_prob=0.45, confidence=0.42 → leverage = 18.9x
- win_prob=0.30, confidence=0.50 → leverage = 15.0x

最小值: 0.5x（Config.MIN_LEVERAGE）
最大值: 无上限
```

### 4. 仓位计算
```python
position_size = PositionSizer.calculate(
    balance=账户余额,
    leverage=计算出的杠杆,
    entry_price=入场价,
    stop_loss=止损价
)

约束:
- 名义价值 ≥ 10 USDT（Binance最小）
- 单仓保证金 ≤ 50%账户权益
- 总保证金 ≤ 90%账户权益
```

### 5. 动态SL/TP调整
```python
adjusted_sl, adjusted_tp = SLTPAdjuster.adjust(
    original_sl=base_signal['stop_loss'],
    original_tp=base_signal['take_profit'],
    leverage=计算出的杠杆
)

放大公式:
scale_factor = 1 + (leverage - 1) × 0.05
scale_factor = min(scale_factor, 3.0)  # 最大3倍

adjusted_sl = entry ± (original_sl_distance × scale_factor)
adjusted_tp = entry ± (original_tp_distance × scale_factor)

原因: 高杠杆需要更宽止损，防止正常波动触发
```

### 6. 订单执行
```python
if 所有检查通过:
    order = BinanceClient.place_order(
        symbol=symbol,
        side='BUY' | 'SELL',
        quantity=position_size,
        leverage=leverage,
        stop_loss=adjusted_sl,
        take_profit=adjusted_tp
    )
    
    TradeRecorder.record_entry(order, signal, features)
```

---

## 📈 预期性能指标（v3.18.8+）

### 信号生成频率
| 模式 | 每周期信号数 | 质量分布 |
|------|-------------|----------|
| **严格模式** | 5-15个 | Excellent(30%) Good(40%) Fair(30%) |
| **宽松模式** | 30-60个 | Excellent(15%) Good(25%) Fair(35%) Poor(25%) |

### 豁免期（前100笔）
- **接受**: Poor + Fair + Good + Excellent
- **预期胜率**: 40-55%
- **目标**: 快速采集训练数据

### 正常期（100笔后）
- **接受**: Good + Excellent
- **预期胜率**: 60-75%
- **目标**: 稳定盈利

---

## 🔧 关键配置参数

### Railway部署必需配置
```bash
# 信号生成模式
RELAXED_SIGNAL_MODE=true  # 启用宽松模式

# 豁免期阈值（解决0信号）
MIN_WIN_PROBABILITY=0.40  # 前100笔使用40%
MIN_CONFIDENCE=0.40       # 前100笔使用40%

# 豁免机制
BOOTSTRAP_TRADE_LIMIT=100
BOOTSTRAP_MIN_WIN_PROBABILITY=0.40
BOOTSTRAP_MIN_CONFIDENCE=0.40

# 正常期阈值（自动切换）
# 系统会在100笔后自动提升到60%/60%
```

### 高级配置（可选）
```bash
# 风险管理
MAX_TOTAL_BUDGET_RATIO=0.8
MAX_SINGLE_POSITION_RATIO=0.5
MAX_CONCURRENT_ORDERS=5

# WebSocket优化
WEBSOCKET_SYMBOL_LIMIT=200
WEBSOCKET_SHARD_SIZE=50

# 技术指标
EMA_FAST=20
EMA_SLOW=50
RSI_PERIOD=14
ADX_PERIOD=14
ATR_PERIOD=14
```

---

## 📝 v3.18.8 重大改进总结

### 1. 趋势判断简化 ✅
- **前**: 需要4个EMA完美排列（极罕见）
- **后**: 仅需价格与EMA20/50关系（常见）
- **影响**: Bullish/Bearish从3.2% → 50-70%

### 2. EMA偏差评分系统 ✅
- **前**: 简单的趋势对齐（二元判断）
- **后**: 量化偏差评分（Excellent/Good/Fair/Poor）
- **影响**: 信号质量分级更精细

### 3. 双模式支持 ✅
- **严格模式**: 高质量，低频率（5-15信号/周期）
- **宽松模式**: 中等质量，中频率（30-60信号/周期）
- **影响**: 适应不同交易阶段

### 4. 架构优化 ✅
- **集中化配置**: 所有常量统一管理
- **共享指标管道**: 缓存减少重复计算
- **ADX计算修复**: 正确的DI+/DI-计算

---

**文档版本**: v3.18.8  
**最后更新**: 2025-11-01  
**维护者**: SelfLearningTrader Team
