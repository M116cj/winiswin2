# Binance USDT永续合约 24/7高频自动交易系统 v3.14.0

## 🚀 系统概述

混合智能交易系统，支持ICT/SMC策略、自我学习AI交易员、混合模式三种策略切换。集成XGBoost ML、ONNX推理加速、深度学习模型（TensorFlow），监控Top 200高流动性交易对，跨3时间框架生成平衡LONG/SHORT信号。

### 核心特性

- **三种策略模式**：ICT策略、自我学习AI、混合模式（可配置切换）
- **深度学习模块**：市场结构自动编码器、特征发现网络、流动性预测、强化学习策略进化
- **虚拟仓位全生命周期监控**：11种事件类型追踪（创建、价格更新、止盈止损接近/触发、过期、关闭）
- **高质量信号过滤**：多维度质量评估、质量加权训练样本生成
- **双循环架构**：实盘交易60秒 + 虚拟仓位10秒
- **智能风险管理**：ML驱动动态杠杆、分级熔断保护、无限同时持仓

## 📁 项目结构

```
src/
├── strategies/                      # 策略模块
│   ├── strategy_factory.py         # 策略工厂（ICT/自我学习/混合）
│   ├── ict_strategy.py             # ICT/SMC策略
│   ├── self_learning_trader.py     # 自我学习交易员（核心）
│   └── hybrid_strategy.py          # 混合策略（ICT + ML过滤）
│
├── ml/                              # 机器学习模块
│   ├── predictor.py                # ML预测器（XGBoost + ONNX）
│   ├── market_structure_autoencoder.py  # 市场结构自动编码器
│   ├── feature_discovery_network.py     # 特征发现网络
│   ├── liquidity_prediction_model.py    # 流动性预测模型
│   ├── adaptive_strategy_evolver.py     # 自适应策略进化器（DQN）
│   ├── high_quality_filter.py          # 高质量信号过滤器
│   └── quality_training_pipeline.py     # 质量训练数据管道
│
├── managers/                        # 管理模块
│   ├── virtual_position_manager.py     # 虚拟仓位管理器
│   ├── virtual_position_lifecycle.py   # 虚拟仓位全生命周期监控
│   ├── virtual_position_events.py      # 虚拟仓位事件定义
│   ├── risk_manager.py                 # 风险管理器
│   └── trade_recorder.py               # 交易记录器
│
├── async_core/                      # 异步核心
│   └── async_main_loop.py          # 双循环管理器
│
├── services/                        # 服务模块
│   ├── data_service.py             # 数据服务
│   ├── trading_service.py          # 交易服务
│   └── parallel_analyzer.py        # 并行分析器
│
├── clients/                         # 客户端
│   └── binance_client.py           # Binance API客户端
│
└── main.py                          # 主程序入口
```

## 🎯 策略系统（v3.14.0新增）

### 策略工厂模式

通过配置环境变量切换策略：

```python
# 配置选项
STRATEGY_MODE = "hybrid"  # "ict", "self_learning", "hybrid"

# 策略工厂自动创建对应策略实例
strategy = StrategyFactory.create_strategy(config)
```

### 1. ICT策略（Inner Circle Trader）

**核心技术**：
- Order Blocks（OB）质量筛选 + 动态衰减
- Break of Structure（BOS）/ Change of Character（CHOCH）
- Fair Value Gaps（FVG）
- Liquidity Zones
- ADX趋势过滤

**五维评分系统**：
1. 趋势对齐 (40%)：三时间框架EMA对齐
2. 市场结构 (20%)：结构与趋势匹配度
3. 价格位置 (20%)：距离Order Block的ATR距离
4. 动量指标 (10%)：RSI + MACD同向确认
5. 波动率 (10%)：布林带宽度分位数

### 2. 自我学习交易员（Self-Learning Trader）

**核心组件**：

#### 2.1 市场结构自动编码器
```python
# 无监督学习市场结构
structure_model.encode_structure(price_series)
# 输出：16维市场结构向量
```

**架构**：
- Conv1D(64, 5) → Conv1D(32, 3) → GlobalMaxPooling → Dense(16)
- 自动压缩价格序列到结构向量
- 支持TensorFlow不可用时的fallback模式

#### 2.2 特征发现网络
```python
# 自动发现有效特征
feature_model.discover_features(market_structure, recent_data)
# 输出：32维动态特征向量
```

**架构**：
- Dense(64) → Dropout(0.3) → Dense(128) → Dense(32)
- 基于市场结构动态生成特征
- Fallback：基于技术指标生成特征

#### 2.3 流动性预测模型
```python
# 预测流动性聚集点
liquidity_model.predict_liquidity(symbol, recent_data)
# 输出：买卖流动性价格 + 置信度
```

**架构**：
- LSTM(64) → Dropout(0.2) → LSTM(32) → Dense(2)
- 预测未来流动性聚集点
- Fallback：基于成交量分布分析

#### 2.4 自适应策略进化器（DQN）
```python
# 强化学习进化策略
evolver.evolve_strategy(state, reward, next_state, done)
action = evolver.get_trading_action(state)
# 动作：0=做多, 1=做空, 2=观望
```

**架构**：
- Deep Q-Network：Dense(128) → Dense(64) → Dense(3)
- 经验回放（10000样本缓存）
- ε-greedy探索（ε衰减：1.0 → 0.01）

### 3. 混合策略（Hybrid Strategy）

**工作流程**：
1. ICT策略生成初始信号
2. ML预测器评估信号质量
3. 信心度校准（ICT × ML）
4. 低质量信号过滤（ML信心度 < 0.5）

**优势**：
- 结合规则策略的可解释性
- ML过滤提高信号质量
- 动态信心度调整

## 🔄 虚拟仓位全生命周期监控（v3.14.0新增）

### 事件系统

11种生命周期事件：
1. **CREATED**: 仓位创建
2. **PRICE_UPDATED**: 价格更新
3. **MAX_PNL_UPDATED**: 最大盈利更新
4. **MIN_PNL_UPDATED**: 最大亏损更新
5. **TP_APPROACHING**: 接近止盈（80%距离）
6. **SL_APPROACHING**: 接近止损（80%距离）
7. **TP_TRIGGERED**: 止盈触发
8. **SL_TRIGGERED**: 止损触发
9. **EXPIRED**: 过期平仓（96小时）
10. **MANUAL_CLOSE**: 手动平仓
11. **CLOSED**: 仓位关闭（最终状态）

### 使用示例

```python
# 创建生命周期监控器
monitor = VirtualPositionLifecycleMonitor(
    event_callback=default_event_handler
)

# 添加虚拟仓位
monitor.add_position(virtual_position)

# 获取仓位摘要
summary = monitor.get_position_summary(position_id)
# {
#   'symbol': 'BTCUSDT',
#   'direction': 'LONG',
#   'pnl_pct': 2.5,
#   'max_pnl': 3.2,
#   'min_pnl': -0.5,
#   'event_count': 15,
#   'is_closed': False
# }

# 获取事件历史
events = monitor.get_position_events(position_id)
```

## 📊 高质量信号过滤（v3.14.0新增）

### 质量评估维度

#### 1. 交易结果质量
- 风险回报比 >= 1.5
- PnL > 0
- 风险调整收益 >= 0.5
- 持仓时间：0.1h - 48h

#### 2. 信号生成质量
- 信心度 >= 0.6
- ML评分 >= 0.5
- 市场状态：trending / breakout
- 反转风险 < 0.2

#### 3. 市场环境质量
- 波动率：0.5% - 5%
- 成交量排名 < 30%
- 资金费率 < 0.1%

### 质量加权训练样本

```python
# 样本权重计算
weight = base_weight × rr_ratio × confidence × pnl_factor

# 质量评分
quality_score = (
    trade_score × 0.4 +
    signal_score × 0.3 +
    pnl_score × 0.3
)
```

## ⚙️ 配置选项（v3.14.0）

### 策略配置
```python
# 策略模式
STRATEGY_MODE = "hybrid"  # "ict", "self_learning", "hybrid"
ENABLE_SELF_LEARNING = True

# 自我学习配置
SELF_LEARNING_MODE = "end_to_end"  # "end_to_end" or "modular"
STRUCTURE_VECTOR_DIM = 16
FEATURE_DISCOVERY_RATE = 0.1
STRATEGY_EVOLUTION_INTERVAL = 3600  # 每小时进化策略
```

### 训练配置
```python
REINFORCEMENT_LEARNING_ENABLED = True
AUTOENCODER_TRAINING_ENABLED = True
FEATURE_DISCOVERY_ENABLED = True
```

### 虚拟仓位配置
```python
VIRTUAL_POSITION_CYCLE_INTERVAL = 10  # 虚拟仓位循环间隔（秒）
VIRTUAL_POSITION_EXPIRY = 96  # 过期时间（小时）
```

## 🔧 技术栈

### 核心依赖
- **Python 3.11+**
- **TensorFlow 2.13+** (深度学习)
- **XGBoost** (ML预测)
- **ONNX Runtime** (推理加速)
- **asyncio** (异步编程)
- **numpy/pandas** (数据处理)

### TensorFlow Fallback机制

所有深度学习模块都实现了fallback机制：
```python
try:
    from tensorflow.keras.models import Sequential
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    # 使用简化版实现（统计特征/规则）
```

**优势**：
- TensorFlow不可用时系统仍可运行
- 自动降级到简化版实现
- 生产环境灵活性

## 🚀 部署指南

### 1. 环境变量配置

```bash
# Binance API
export BINANCE_API_KEY="your_api_key"
export BINANCE_API_SECRET="your_api_secret"

# Discord通知
export DISCORD_TOKEN="your_discord_token"
export DISCORD_CHANNEL_ID="channel_id"

# 策略配置
export STRATEGY_MODE="hybrid"
export ENABLE_SELF_LEARNING="true"

# 交易配置
export TRADING_ENABLED="false"  # 虚拟模式
export MAX_POSITIONS="999"
```

### 2. 依赖安装

```bash
# 基础依赖
pip install -r requirements.txt

# TensorFlow（可选）
pip install tensorflow>=2.13.0 tensorflow-addons>=0.19.0
```

### 3. 运行系统

```bash
python -m src.main
```

## 📈 性能优化（v3.13.0 - v3.14.0）

### v3.13.0优化
- ✅ 异步批量更新虚拟仓位（200个：20+秒→<1秒）
- ✅ 内存优化（__slots__）
- ✅ 双循环架构（交易60秒 + 虚拟仓位10秒）
- ✅ 批量ML预测（6倍提升）
- ✅ 向量化技术指标（20-30倍加速）

### v3.14.0新增
- ✅ 策略工厂模式（灵活切换）
- ✅ 深度学习模块（TensorFlow）
- ✅ 虚拟仓位全生命周期监控
- ✅ 高质量信号过滤系统
- ✅ TensorFlow fallback机制

## 📊 监控与日志

### 虚拟仓位事件监控
```
🎯 **止盈触发**
BTCUSDT 盈利 2.50%

⚠️ **止损触发**
ETHUSDT 亏损 1.20%

🚀 **接近止盈**
SOLUSDT 距离止盈 85.0%

⏰ **仓位过期**
BNBUSDT PnL: 0.50%
```

### 策略切换日志
```
🎯 使用 ICT 策略
🤖 使用自我学习策略
🔥 使用混合策略 (ICT + ML)
```

## 🔮 未来规划

### 待验证功能
1. **TensorFlow模块训练**：在支持环境中验证深度学习模型训练
2. **策略自动进化**：实现完整的强化学习策略进化循环
3. **多策略集成**：支持多个策略并行运行和投票机制
4. **实时性能对比**：不同策略模式的A/B测试

### 待优化
1. **模型持久化**：保存和加载训练好的模型
2. **增量训练**：在线学习和模型更新
3. **超参数优化**：自动调优模型参数
4. **分布式训练**：支持多GPU训练

## 📝 版本历史

- **v3.14.0** (2025-10-28): 混合智能系统（策略工厂+深度学习+生命周期监控）
- **v3.13.0** (2025-10-27): 全面轻量化（异步化+12项优化）
- **v3.12.0** (2025-10-26): 性能优化五合一（进程池+批量ML+ONNX+双循环）
- **v3.11.1** (2025-10-25): 移除持仓限制（无限同时持仓）
- **v3.11.0** (2025-10-24): 高级优化（OB质量+BOS/CHOCH+市场状态）

---

## 📞 支持

有问题或建议？请联系开发团队。
