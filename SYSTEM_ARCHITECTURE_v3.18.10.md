# 🏗️ SelfLearningTrader 系统架构 v3.18.10

**版本**: v3.18.10+  
**更新日期**: 2025-11-02  
**核心理念**: 模型拥有无限制杠杆控制权，唯一准则是胜率 × 信心度

---

## 📐 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                       应用层 (Application)                       │
│                           main.py                               │
│  • 系统初始化 • 配置验证 • 启动UnifiedScheduler • 优雅关闭       │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   核心调度层 (Scheduler Layer)                   │
│                    UnifiedScheduler                             │
│  • Trading Cycle (60s) • Position Monitor (2s) • Daily Report   │
│  • WebSocket Manager (530 USDT永续合约) • 任务协调              │
└────┬────────────────┬─────────────────┬──────────────────┬──────┘
     ▼                ▼                 ▼                  ▼
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐
│   决策引擎  │  │  仓位控制  │  │  数据服务  │  │  ML模型层   │
│ SelfLearning│  │  Position  │  │   Data     │  │   Model     │
│   Trader    │  │ Controller │  │  Service   │  │  Wrapper    │
└────┬────────┘  └────┬────────┘  └────┬────────┘  └─────┬───────┘
     │                │                │                  │
     ▼                ▼                ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    子系统层 (Subsystem Layer)                    │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│ │ 信号生成器    │ │ 三大引擎      │ │ 记录器        │            │
│ │ RuleBased    │ │ • Leverage   │ │ • Trade      │            │
│ │ SignalGen    │ │ • PosSizer   │ │ • Virtual    │            │
│ │ (ICT/SMC)    │ │ • SLTPAdj    │ │ • Feature    │            │
│ └──────────────┘ └──────────────┘ └──────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  基础设施层 (Infrastructure)                      │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│ │ Binance API  │ │ 保护机制      │ │ 监控系统      │            │
│ │ • REST API   │ │ • Circuit    │ │ • Health     │            │
│ │ • WebSocket  │ │   Breaker    │ │ • Perf       │            │
│ │ • 熔断器     │ │ • RateLimit  │ │ • Logger     │            │
│ └──────────────┘ └──────────────┘ └──────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 核心组件详解

### 1. **应用层 (Application Layer)**

#### **main.py** - 系统入口
**职责**:
- 系统初始化与配置验证
- 创建核心组件实例
- 启动UnifiedScheduler
- 优雅关闭处理

**关键代码**:
```python
class SelfLearningTradingSystem:
    async def initialize(self):
        # 1. 配置验证
        # 2. 创建BinanceClient
        # 3. 创建DataService
        # 4. 创建TradeRecorder + ModelInitializer
        # 5. 创建UnifiedScheduler
        # 6. 设置WebSocket连接
```

---

### 2. **核心调度层 (Scheduler Layer)**

#### **UnifiedScheduler** - 统一调度器
**位置**: `src/core/unified_scheduler.py`

**职责**:
- **Trading Cycle**: 每60秒扫描530个交易对，生成信号
- **Position Monitor**: 每2秒监控所有仓位，动态调整SL/TP
- **Daily Report**: 每日生成模型评分报告
- **WebSocket Manager**: 管理530个USDT永续合约的实时数据

**核心循环**:
```python
async def start(self):
    tasks = [
        self._trading_cycle_loop(),      # 60s循环
        self._position_monitor_loop(),   # 2s循环
        self._daily_report_loop()        # 24h循环
    ]
    await asyncio.gather(*tasks)
```

---

### 3. **决策引擎层 (Decision Engine)**

#### **SelfLearningTrader** - 智能决策核心
**位置**: `src/strategies/self_learning_trader.py`

**核心理念**: 
> "模型拥有无限制杠杆控制权，唯一准则是胜率 × 信心度"

**职责**:
1. **信号生成**: 调用RuleBasedSignalGenerator生成交易信号
2. **杠杆计算**: 基于胜率 × 信心度，无上限（豁免期1-3x）
3. **仓位计算**: 10 USDT下限，符合Binance规格
4. **动态SL/TP**: 高杠杆 → 宽止损，防止过早触发
5. **多信号竞价**: 加权评分（信心40% + 胜率40% + R:R 20%）

**关键组件**:
```python
self.signal_generator = RuleBasedSignalGenerator(config)
self.leverage_engine = LeverageEngine(config)
self.position_sizer = PositionSizer(config, binance_client)
self.sltp_adjuster = SLTPAdjuster(config)
self.ml_model = MLModelWrapper()  # v3.18.6+
```

**决策流程**:
```
1. 生成信号 (RuleBasedSignalGenerator)
   ↓
2. ML预测 (MLModelWrapper, 可选)
   ↓
3. 杠杆计算 (LeverageEngine: 勝率 × 信心 × 3.75)
   ↓
4. 仓位计算 (PositionSizer: ≥10 USDT)
   ↓
5. SL/TP调整 (SLTPAdjuster: 高杠杆 → 宽止损)
   ↓
6. 多信号竞价 (加权评分排序)
   ↓
7. 执行前验证 (双门槛 + 质量评分 + OrderBlock)
   ↓
8. 开仓执行 (PositionController)
```

---

### 4. **信号生成层 (Signal Generation)**

#### **RuleBasedSignalGenerator** - ICT/SMC信号生成器
**位置**: `src/strategies/rule_based_signal_generator.py`

**职责**:
- **多时间框架分析**: 1h主趋势 + 15m中期 + 5m入场
- **ICT/SMC策略**: Order Block + Liquidity Zone + FVG
- **12种技术指标**: RSI, MACD, ATR, BB, EMA50/200等
- **5个优先级**: 严格模式(1-3) + 宽松模式(4-5)
- **ADX过滤**: 3层惩罚机制（v3.18.10+）

**信号优先级**:
```python
优先级1: H1+M15+M5+结构 完美对齐（最高质量）
优先级2: H1+M15 强趋势
优先级3: 趋势初期（M15+M5对齐）
优先级4: H1主导（宽松模式）
优先级5: M15+M5对齐（宽松模式）
```

**v3.18.10+ ADX专项调整**:
```python
if adx < 10:      # 硬拒绝
    return None
elif adx < 15:    # 强惩罚×0.6
    confidence *= 0.6
elif adx < 20:    # 中惩罚×0.8
    confidence *= 0.8
```

**10阶段Pipeline诊断**:
```
Stage0: 总扫描530个交易对
Stage1: 数据验证
Stage2: 趋势判断
Stage3: 信号方向（5个优先级）
Stage4: ADX过滤（3层惩罚）
Stage5: 信心度计算
Stage6: 胜率计算
Stage7: 双门槛验证
Stage8: 质量评分
Stage9: 排序&执行
```

---

### 5. **三大引擎 (Core Engines)**

#### **LeverageEngine** - 杠杆控制引擎
**位置**: `src/core/leverage_engine.py`

**核心公式**:
```python
# 杠杆 = 勝率 × 信心度 × 3.75
leverage = win_probability * confidence * 3.75

# 豁免期（前100笔交易）：强制1-3x
if bootstrap_enabled and leverage > 3.0:
    leverage = min(leverage, 3.0)
```

#### **PositionSizer** - 仓位计算引擎
**位置**: `src/core/position_sizer.py`

**职责**:
- 计算仓位大小（≥10 USDT）
- 符合Binance交易规格（最小数量、步长）
- 动态预算池管理（80%可用保证金）
- 质量加权分配（高质量信号获得更多资金）

#### **SLTPAdjuster** - 止损止盈调整器
**位置**: `src/core/sltp_adjuster.py`

**职责**:
- 动态SL/TP调整（高杠杆 → 宽止损）
- 防止过早触发（杠杆>10x时扩大SL 20-30%）
- R:R比率控制（1.0-3.0）

---

### 6. **ML模型层 (Machine Learning Layer)**

#### **MLModelWrapper** - XGBoost模型包装器
**位置**: `src/ml/model_wrapper.py`

**职责**:
- 加载训练好的XGBoost模型
- 提供44个特征的预测接口
- 输出胜率预测（0-1）

**44个特征**:
- 基本特征（8个）: confidence, leverage, position_value, rr_ratio...
- 技术指标（10个）: RSI, MACD, ATR, BB...
- 趋势特征（6个）: trend_1h, trend_15m, trend_5m, trend_alignment...
- 其他特征（14个）: ema_slope, fvg_count, order_flow...
- 竞价特征（3个）: competition_rank, score_gap_to_best...
- WebSocket特征（3个）: latency_zscore, shard_load...

#### **FeatureEngine** - 特征工程引擎
**位置**: `src/ml/feature_engine.py`

**职责**:
- 构建44个特征
- 竞价上下文特征提取
- WebSocket质量特征计算

---

### 7. **仓位控制层 (Position Control)**

#### **PositionController** - 仓位全权控制
**位置**: `src/core/position_controller.py`

**职责**:
- **开仓执行**: 批量下单，多信号竞价分配
- **24/7监控**: 每2秒检查所有仓位
- **智能出场**: 6种出场策略
  1. 止损触发
  2. 止盈触发
  3. 100%亏损熔断
  4. 进场失效（反向突破）
  5. 逆势平仓（趋势反转）
  6. 时间止损（48小时未触发TP）

#### **VirtualPositionManager** - 虚拟仓位管理
**位置**: `src/managers/virtual_position_manager.py`

**职责**:
- 虚拟仓位追踪（测试模式）
- 实时盈亏计算
- 倉位状态管理

---

### 8. **数据服务层 (Data Service)**

#### **DataService** - 数据管理中心
**位置**: `src/services/data_service.py`

**职责**:
- **K线数据获取**: 批量获取多时间框架数据（1h/15m/5m）
- **市场扫描**: 530个USDT永续合约
- **智能缓存**: 减少API调用
- **WebSocket优先**: 优先使用WebSocket数据（v3.17.2+）

#### **WebSocket Manager** - 实时数据管理
**位置**: `src/core/websocket/websocket_manager.py`

**职责**:
- 管理530个交易对的WebSocket连接
- 分片管理（每片50个符号，共11片）
- 实时K线数据（1h/15m/5m/1m）
- 账户余额监控

---

### 9. **记录与评估层 (Recording & Evaluation)**

#### **TradeRecorder** - 交易记录器
**位置**: `src/managers/trade_recorder.py`

**职责**:
- 记录所有交易数据（JSON Lines格式）
- 生成ML训练数据（training_data.jsonl）
- 竞价结果记录（signal_competitions.jsonl）
- 触发模型重训练（每100笔交易）

#### **ModelEvaluator** - 模型评估器
**位置**: `src/core/model_evaluator.py`

**职责**:
- 每日模型评分报告
- 特征重要性分析
- 性能指标追踪
- 生成Markdown报告

---

### 10. **基础设施层 (Infrastructure)**

#### **BinanceClient** - Binance API客户端
**位置**: `src/clients/binance_client.py`

**职责**:
- REST API调用（带重试机制）
- WebSocket连接管理
- 分级熔断器保护
- 速率限制控制

**熔断器状态**:
```
NORMAL (0失败) → WARNING (1-2失败) → CRITICAL (3-4失败) → OPEN (5+失败)
```

#### **CircuitBreaker** - 熔断器
**位置**: `src/core/circuit_breaker.py`

**职责**:
- 自动故障恢复
- 分级保护（Normal → Warning → Critical → Open）
- 冷却时间管理

#### **RateLimiter** - 速率限制器
**位置**: `src/core/rate_limiter.py`

**职责**:
- 令牌桶算法
- API调用限流

---

## 🔄 数据流图

### **交易信号生成流程**

```
1. UnifiedScheduler (60s循环)
   ↓
2. 扫描530个USDT永续合约 (DataService)
   ↓
3. 多时间框架数据获取 (WebSocket优先)
   ↓
4. RuleBasedSignalGenerator (10阶段Pipeline)
   Stage0: 总扫描530个
   Stage1: 数据验证
   Stage2: 趋势判断
   Stage3: 信号方向（5个优先级）
   Stage4: ADX过滤（3层惩罚）
   Stage5: 信心度计算
   Stage6: 胜率计算
   ↓
5. SelfLearningTrader (决策引擎)
   • ML预测（可选）
   • 杠杆计算（勝率 × 信心 × 3.75）
   • 仓位计算（≥10 USDT）
   • SL/TP调整
   ↓
6. 多信号竞价 (加权评分排序)
   • 信心40% + 胜率40% + R:R 20%
   ↓
7. 双门槛验证 (Stage7)
   • 胜率≥门槛（豁免期40%，正常期60%）
   • 信心≥门槛（豁免期40%，正常期50%）
   • R:R在1.0-3.0范围
   ↓
8. 质量评分 (Stage8)
   • 质量≥门槛（豁免期0.4，正常期0.6）
   ↓
9. 排序&执行 (Stage9)
   • 按质量分数排序
   • 动态预算池分配
   • 最多5个并发仓位
   ↓
10. PositionController开仓执行
    ↓
11. TradeRecorder记录交易
    ↓
12. 每100笔触发模型重训练
```

---

## 📁 目录结构

```
src/
├── clients/                  # Binance API客户端
│   ├── binance_client.py     # REST + WebSocket
│   └── binance_errors.py     # 错误处理
│
├── core/                     # 核心引擎
│   ├── websocket/            # WebSocket管理
│   │   ├── websocket_manager.py  # 530交易对管理
│   │   ├── kline_feed.py         # K线数据流
│   │   ├── price_feed.py         # 价格数据流
│   │   └── shard_feed.py         # 分片管理
│   ├── unified_scheduler.py      # 统一调度器
│   ├── leverage_engine.py        # 杠杆控制
│   ├── position_sizer.py         # 仓位计算
│   ├── sltp_adjuster.py          # SL/TP调整
│   ├── position_controller.py    # 仓位全权控制
│   ├── model_evaluator.py        # 模型评估
│   └── model_initializer.py      # 模型初始化
│
├── strategies/               # 交易策略
│   ├── self_learning_trader.py   # 智能决策核心
│   └── rule_based_signal_generator.py  # ICT/SMC信号
│
├── ml/                       # 机器学习
│   ├── model_wrapper.py          # XGBoost封装
│   └── feature_engine.py         # 44特征工程
│
├── managers/                 # 数据管理
│   ├── trade_recorder.py         # 交易记录
│   └── virtual_position_manager.py  # 虚拟仓位
│
├── services/                 # 服务层
│   ├── data_service.py           # 数据管理
│   └── position_monitor.py       # 仓位监控
│
├── monitoring/               # 监控系统
│   ├── health_monitor.py         # 健康监控
│   └── performance_monitor.py    # 性能监控
│
├── config.py                 # 配置管理
└── main.py                   # 程序入口
```

---

## 🔧 配置管理

**文件**: `src/config.py`

**核心配置项**:
```python
# 交易配置
MAX_CONCURRENT_ORDERS = 5           # 最多5个并发仓位
CYCLE_INTERVAL = 60                 # 60秒扫描周期
TRADING_ENABLED = true              # 开启实盘交易

# 开仓条件
MIN_WIN_PROBABILITY = 0.60          # 最低胜率60%
MIN_CONFIDENCE = 0.50               # 最低信心50%
MIN_RR_RATIO = 1.0                  # 最低R:R 1.0
MAX_RR_RATIO = 3.0                  # 最高R:R 3.0

# 豁免期（前100笔交易）
BOOTSTRAP_TRADE_LIMIT = 100         # 豁免期100笔
BOOTSTRAP_MIN_WIN_PROBABILITY = 0.40  # 豁免期胜率40%
BOOTSTRAP_MIN_CONFIDENCE = 0.40     # 豁免期信心40%
BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD = 0.4  # 豁免期质量0.4

# ADX过滤（v3.18.10+）
ADX_HARD_REJECT_THRESHOLD = 10.0    # 硬拒绝门槛
ADX_WEAK_TREND_THRESHOLD = 15.0     # 弱趋势门槛

# 资金分配
SIGNAL_QUALITY_THRESHOLD = 0.6      # 质量门槛
MAX_TOTAL_BUDGET_RATIO = 0.8        # 总预算80%
MAX_SINGLE_POSITION_RATIO = 0.5     # 单仓≤50%

# WebSocket配置
WEBSOCKET_SYMBOL_LIMIT = 200        # 监控200个高质量交易对
WEBSOCKET_SHARD_SIZE = 50           # 每片50个符号
```

---

## 🚀 启动流程

```python
# 1. 配置验证
is_valid, errors = Config.validate()

# 2. 初始化BinanceClient
binance_client = BinanceClient()

# 3. 初始化DataService
data_service = DataService(binance_client, websocket_monitor=None)
await data_service.initialize()

# 4. 初始化ModelEvaluator
model_evaluator = ModelEvaluator(config, reports_dir)

# 5. 初始化ModelInitializer
model_initializer = ModelInitializer(
    binance_client, trade_recorder=None, config, model_evaluator
)

# 6. 初始化TradeRecorder
trade_recorder = TradeRecorder(model_initializer)
model_initializer.trade_recorder = trade_recorder

# 7. 初始化UnifiedScheduler
scheduler = UnifiedScheduler(
    config, binance_client, data_service, 
    trade_recorder, model_initializer
)

# 8. 设置WebSocket连接
data_service.websocket_monitor = scheduler.websocket_manager

# 9. 启动调度器
await scheduler.start()
```

---

## 📊 关键数据文件

```
data/
├── training_data.jsonl           # ML训练数据（每笔交易的44特征 + 结果）
├── signal_competitions.jsonl     # 竞价结果记录
├── trade_history.json            # 交易历史
├── virtual_positions.json        # 虚拟仓位
└── reports/                      # 每日报告
    ├── model_rating_YYYYMMDD.md
    └── model_rating_YYYYMMDD.json

models/
└── xgboost_model.json            # XGBoost模型文件
```

---

## 🎯 重构建议

### 1. **模块化改进**

**当前问题**:
- 部分组件耦合度较高
- 循环依赖（如`ModelInitializer` ↔ `TradeRecorder`）

**建议**:
```python
# 使用依赖注入容器
class ServiceContainer:
    def __init__(self):
        self.services = {}
    
    def register(self, name, service):
        self.services[name] = service
    
    def get(self, name):
        return self.services.get(name)

# 示例
container = ServiceContainer()
container.register('binance_client', binance_client)
container.register('data_service', data_service)
```

### 2. **配置管理优化**

**当前问题**:
- 配置分散在多个文件
- 环境变量管理较复杂

**建议**:
```python
# 使用pydantic进行配置验证
from pydantic import BaseSettings

class AppConfig(BaseSettings):
    # 交易配置
    max_concurrent_orders: int = 5
    cycle_interval: int = 60
    
    # 门槛配置
    min_win_probability: float = 0.60
    min_confidence: float = 0.50
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
```

### 3. **事件驱动架构**

**当前问题**:
- 组件间通信耦合紧密
- 难以扩展新功能

**建议**:
```python
# 使用事件总线
class EventBus:
    def __init__(self):
        self.subscribers = {}
    
    def subscribe(self, event_type, handler):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    def publish(self, event_type, data):
        for handler in self.subscribers.get(event_type, []):
            handler(data)

# 示例
event_bus = EventBus()
event_bus.subscribe('signal_generated', on_signal_generated)
event_bus.subscribe('position_opened', on_position_opened)
```

### 4. **测试覆盖**

**当前问题**:
- 缺乏单元测试
- 集成测试不足

**建议**:
```python
# 添加单元测试
import pytest

def test_leverage_calculation():
    engine = LeverageEngine(config)
    leverage = engine.calculate_leverage(
        win_probability=0.70,
        confidence=0.75
    )
    assert 1.0 <= leverage <= 125.0
```

### 5. **日志与监控增强**

**当前问题**:
- 日志分散
- 缺乏集中监控

**建议**:
```python
# 使用结构化日志
import structlog

logger = structlog.get_logger()
logger.info("signal_generated", 
    symbol="BTCUSDT",
    direction="LONG",
    confidence=0.75,
    priority=1
)
```

### 6. **异步优化**

**当前问题**:
- 部分同步代码阻塞
- 并发性能可提升

**建议**:
```python
# 使用asyncio优化并发
async def parallel_signal_generation(symbols):
    tasks = [generate_signal(symbol) for symbol in symbols]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

---

## ✅ 总结

**系统优势**:
1. ✅ 清晰的分层架构
2. ✅ 无限制杠杆控制（基于胜率×信心）
3. ✅ 44特征ML模型集成
4. ✅ 10阶段Pipeline诊断
5. ✅ WebSocket实时数据（530交易对）
6. ✅ 豁免期策略（前100笔低门槛）
7. ✅ 多信号竞价机制

**可改进点**:
1. ⚠️ 降低模块耦合度
2. ⚠️ 增强配置管理
3. ⚠️ 引入事件驱动
4. ⚠️ 补充测试覆盖
5. ⚠️ 优化异步并发

**下一步**:
根据您的重构需求，我可以帮您：
1. 设计新的模块化架构
2. 实现依赖注入容器
3. 添加单元测试框架
4. 优化配置管理
5. 引入事件总线

请告诉我您想先从哪个方向开始重构！
