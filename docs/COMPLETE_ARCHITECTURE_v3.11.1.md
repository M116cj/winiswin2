# 🏗️ Binance 高频交易系统 - 完整架构文档 v3.11.1

**更新日期**: 2025-10-27  
**版本**: v3.11.1 (移除持仓限制 - 无限倉位)

---

## 📋 目录

1. [系统概览](#系统概览)
2. [整体架构](#整体架构)
3. [核心模块详解](#核心模块详解)
4. [数据流图](#数据流图)
5. [技术栈](#技术栈)
6. [部署架构](#部署架构)
7. [安全与风险控制](#安全与风险控制)

---

## 🎯 系统概览

### 系统定位
24/7 高频自动化交易系统，专注于 Binance USDT 永续合约，采用 ICT/SMC 策略结合 XGBoost 机器学习增强。

### 核心特性
- ✅ **多时间框架分析**：1h/15m/5m 三层确认
- ✅ **智能信号筛选**：ICT/SMC + ML 双重验证
- ✅ **动态风险管理**：无持仓限制 + 多层风险保护
- ✅ **高性能并行处理**：32核心并行分析 200 个交易对
- ✅ **实时监控通知**：Discord 集成

### 关键指标
- **监控交易对**: 648 个 → 选择流动性最高的 200 个
- **扫描周期**: 60 秒/周期
- **信号生成**: 10-30 个/周期（目标）
- **持仓数量**: 无限制（v3.11.1）
- **风险控制**: 5次连续亏损 / 15%回撤自动暂停

---

## 🏛️ 整体架构

### 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Railway Cloud Platform                     │
│                   (32vCPU / 32GB RAM / Asia)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Main Coordinator                        │
│                          (src/main.py)                          │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  - 系统初始化与生命周期管理                                 │ │
│  │  - 组件协调与错误处理                                       │ │
│  │  - 60秒主循环控制                                           │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Clients   │ │  Services   │ │  Managers   │ │     ML      │
│   Layer     │ │    Layer    │ │    Layer    │ │   Engine    │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
      │                │                │                │
      ▼                ▼                ▼                ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Binance  │    │   Data   │    │   Risk   │    │ XGBoost  │
│   API    │    │ Service  │    │ Manager  │    │ Training │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
│ Discord  │    │Parallel  │    │ Virtual  │    │Predictor │
│   Bot    │    │Analyzer  │    │Position  │    │FeatureEng│
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                │Timeframe │    │ Trade    │    │Ensemble  │
                │Scheduler │    │ Recorder │    │ Models   │
                └──────────┘    └──────────┘    └──────────┘
                │ Trading  │    │Expectancy│    │ Drift    │
                │ Service  │    │Calculator│    │ Detector │
                └──────────┘    └──────────┘    └──────────┘
                                │  Model   │
                                │  Scorer  │
                                └──────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        Core Infrastructure                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │    Cache     │  │ Rate Limiter │  │   Circuit    │         │
│  │   Manager    │  │   (1920/min) │  │   Breaker    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      External Integrations                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Binance    │  │   Discord    │  │   Railway    │         │
│  │  Futures API │  │  Webhook     │  │   Platform   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### 架构层次

#### 1️⃣ **应用层 (Application Layer)**
- **Main Coordinator** (`main.py`): 主控制器，协调所有模块

#### 2️⃣ **业务逻辑层 (Business Logic Layer)**
- **Services**: 数据服务、并行分析、时间框架调度
- **Strategies**: ICT/SMC 策略引擎
- **Managers**: 风险管理、仓位管理、交易记录

#### 3️⃣ **机器学习层 (ML Layer)**
- **Training**: 模型训练、超参数调优、集成学习
- **Prediction**: 实时预测、不确定性量化
- **Monitoring**: 漂移检测、特征重要性追踪

#### 4️⃣ **基础设施层 (Infrastructure Layer)**
- **Clients**: Binance API 客户端、Discord 集成
- **Core**: 缓存管理、限流、熔断器
- **Utils**: 技术指标计算、辅助函数

#### 5️⃣ **数据层 (Data Layer)**
- **Persistent Storage**: JSON 文件存储（交易记录、虚拟仓位、ML数据）
- **Cache**: 内存缓存（K线数据、账户信息）
- **Logs**: 文件日志系统

---

## 🧩 核心模块详解

### 📁 1. 主入口模块 (Main)

**文件**: `src/main.py`

**职责**:
- 系统初始化与生命周期管理
- 组件协调与错误处理
- 60秒主循环控制

**核心类**:
```python
class TradingBot:
    - initialize(): 初始化所有组件
    - run(): 主循环逻辑
    - scan_and_analyze(): 市场扫描与信号生成
    - execute_signals(): 信号执行
    - monitor_positions(): 仓位监控
```

**工作流程**:
```
1. 加载配置 (Config.validate())
2. 初始化 Binance 客户端
3. 初始化所有管理器和服务
4. 启动 Discord 监控任务（异步）
5. 进入主循环（每60秒）:
   ├─ 扫描市场（DataService.scan_market）
   ├─ 并行分析（ParallelAnalyzer.analyze_symbols）
   ├─ ML预测（MLPredictor.predict）
   ├─ 执行信号（TradingService.execute_signal）
   └─ 监控仓位（PositionMonitor.monitor）
```

---

### 📁 2. 配置管理 (Config)

**文件**: `src/config.py`

**职责**:
- 环境变量加载与验证
- 全局常量定义
- 配置完整性检查

**关键配置**:
```python
# 交易配置
MAX_POSITIONS = 999          # v3.11.1: 无限制
CYCLE_INTERVAL = 60          # 扫描周期（秒）
TRADING_ENABLED = False      # 默认模拟模式

# 风险管理
MIN_LEVERAGE = 3             # 最小杠杆
MAX_LEVERAGE = 20            # 最大杠杆
MIN_MARGIN_PCT = 0.03        # 最小仓位3%
MAX_MARGIN_PCT = 0.13        # 最大仓位13%

# 策略配置
MIN_CONFIDENCE = 0.35        # 最小信心度35%
ADX_TREND_THRESHOLD = 20.0   # ADX趋势阈值

# ICT/SMC配置（v3.11.0）
OB_REJECTION_THRESHOLD = 0.005   # OB拒绝率0.5%
OB_VOLUME_MULTIPLIER = 1.5       # OB成交量1.5x
OB_MAX_HISTORY = 20              # 保留20个OB

# 熔断器配置
GRADED_CIRCUIT_BREAKER_ENABLED = True
CIRCUIT_BREAKER_WARNING_THRESHOLD = 2
CIRCUIT_BREAKER_BLOCKED_THRESHOLD = 5
```

---

### 📁 3. 客户端层 (Clients)

#### 3.1 Binance API 客户端

**文件**: `src/clients/binance_client.py`

**职责**:
- Binance Futures API 封装
- 请求重试与错误处理
- 限流与熔断保护

**核心方法**:
```python
class BinanceClient:
    # 数据获取
    - get_klines(symbol, interval, limit): 获取K线数据
    - get_ticker_price(symbol): 获取最新价格
    - get_account_balance(): 获取账户余额
    - get_all_positions(): 获取所有持仓
    
    # 订单管理
    - create_market_order(symbol, side, quantity, leverage)
    - create_limit_order(symbol, side, price, quantity, leverage)
    - cancel_order(symbol, order_id)
    - set_leverage(symbol, leverage)
    
    # 风险控制
    - _make_request(): 统一请求包装（限流+熔断）
    - _handle_binance_error(): 错误分类处理
```

**限流策略**:
- 请求限制: 1920 req/min（官方2400的80%）
- 令牌桶算法
- 自动延迟重试

**熔断策略** (v3.9.2.8.4):
```
Level 1: Warning   (2次失败) → 记录警告
Level 2: Throttled (4次失败) → 延迟2秒
Level 3: Blocked   (5次失败) → 阻断60秒
Bypass: 白名单操作（平仓、调整止损等）
```

#### 3.2 Discord 集成

**文件**: `src/integrations/discord_bot.py`

**职责**:
- Discord 机器人管理
- 实时通知推送
- 交易统计展示

**通知类型**:
- 🔔 信号生成通知
- ✅ 交易执行通知
- 💰 仓位盈亏更新
- ⚠️ 风险警告
- 📊 每日统计报告

---

### 📁 4. 服务层 (Services)

#### 4.1 数据服务

**文件**: `src/services/data_service.py`

**职责**:
- 市场数据获取与缓存
- 波动率排序
- 多时间框架数据管理

**核心方法**:
```python
class DataService:
    - scan_market(): 扫描所有交易对，选择前200个高流动性
    - get_multi_timeframe_data(symbol): 获取1h/15m/5m数据
    - calculate_volatility(df): 计算24h波动率
    - _fetch_with_cache(symbol, interval): 带缓存的数据获取
```

**缓存策略**:
```
1h K线  → 缓存3600秒（1小时）
15m K线 → 缓存900秒（15分钟）
5m K线  → 缓存300秒（5分钟）
```

#### 4.2 并行分析器

**文件**: `src/services/parallel_analyzer.py`

**职责**:
- 32核心并行处理
- 批量信号生成
- CPU资源优化

**核心逻辑**:
```python
class ParallelAnalyzer:
    - analyze_symbols(symbols, multi_tf_data):
        → 使用ProcessPoolExecutor并行分析
        → 每个进程独立运行ICTStrategy.analyze()
        → 收集所有信号并按confidence排序
```

**性能优化**:
- 动态CPU核心检测
- 批量处理（batch_size=50）
- 进程池复用

#### 4.3 时间框架调度器

**文件**: `src/services/timeframe_scheduler.py`

**职责**:
- 差异化扫描频率控制
- API请求优化

**调度策略**:
```python
1h  → 每3600秒扫描一次（趋势确认）
15m → 每900秒扫描一次（趋势确认）
5m  → 每60秒扫描一次（入场信号）
```

#### 4.4 交易服务

**文件**: `src/services/trading_service.py`

**职责**:
- 订单执行
- 止损止盈设置
- 保护监护任务

**核心功能**:
```python
class TradingService:
    - execute_signal(signal, account_balance):
        1. 计算仓位大小
        2. 设置杠杆
        3. 下单（限价优先，市价降级）
        4. 设置止损/止盈
        5. 启动保护监护任务
    
    - _protection_guardian_task():
        → 每30秒检查止损/止盈是否设置成功
        → 最多尝试10次
        → 失败时强制平仓
```

---

### 📁 5. 策略引擎 (Strategies)

**文件**: `src/strategies/ict_strategy.py`

**职责**:
- ICT/SMC 理论实现
- 多时间框架分析
- 信号生成与置信度评分

**核心流程**:
```python
class ICTStrategy:
    def analyze(symbol, multi_tf_data):
        1. 数据验证
        2. 趋势判断（1h/15m/5m）
        3. 市场结构分析
        4. Order Blocks识别（v3.11.0质量筛选）
        5. Liquidity Zones识别
        6. BOS/CHOCH检测（v3.11.0新增）
        7. 市场状态分类（v3.11.0新增）
        8. 反转风险评估（v3.11.0新增）
        9. 信号方向判断
        10. 置信度计算（5维度加权）
        11. 止损/止盈计算
        12. 返回信号
```

**五维置信度评分系统**:
```python
confidence_score = (
    trend_alignment    * 40%  +  # 三时间框架EMA对齐
    market_structure   * 20%  +  # 结构与趋势匹配
    price_position     * 20%  +  # 距离Order Block的ATR距离
    momentum           * 10%  +  # RSI + MACD同向确认
    volatility         * 10%     # 布林带宽度分位数
)
```

**ICT/SMC 功能** (v3.11.0增强):

1. **Order Blocks 质量筛选**:
```python
- 成交量验证: volume >= 1.5× 均量
- 拒绝率验证: wick_height / candle_height >= 0.5%
- 质量分数: volume×30% + body×30% + rejection×40%
- 动态衰减: 时间5%/天 + 测试10%/次
```

2. **BOS/CHOCH 检测**:
```python
- BOS (Break of Structure): 趋势延续
  → 上升趋势突破swing high
  → 下降趋势跌破swing low
  
- CHOCH (Change of Character): 趋势反转
  → 上升趋势失守swing low
  → 下降趋势突破swing high
```

3. **市场状态分类**:
```python
- trending: ADX>25 + BB宽度>50分位
- ranging: ADX<20 + 价格在中轨
- breakout: 价格在BB外 + ADX上升
- drift: ADX 20-25
- choppy: 低波动 + ADX<15
- transitioning: 过渡期
```

4. **反转预警滤网**:
```python
- 流动性扫荡: Bull/Bear Trap检测
- RSI背离: 价格新高但RSI未新高
- MACD衰减: 柱状图收敛>70%
- 风险评分: >=0.4 跳过交易
```

---

### 📁 6. 管理器层 (Managers)

#### 6.1 风险管理器

**文件**: `src/managers/risk_manager.py`

**职责**:
- 动态杠杆调整
- 仓位大小计算
- 连续亏损保护
- 回撤保护

**核心方法**:
```python
class RiskManager:
    - calculate_position_size(signal, account_balance):
        → 基础仓位: 10%
        → 信心度调整: ±3%（35%-100% → 3%-13%）
        → 胜率调整: 优秀胜率+2%
        
    - calculate_leverage(confidence, win_rate):
        → 基础杠杆: 3x
        → 信心度加成: 每10%信心度 +2x
        → 胜率加成: >60% +2x, >70% +3x
        → 最大: 20x
        
    - should_trade(account_balance, current_positions):
        ✅ 检查TRADING_ENABLED
        ❌ v3.11.1: 不再检查MAX_POSITIONS
        ✅ 检查连续亏损（5次自动暂停）
        ✅ 检查回撤（15%自动暂停）
        
    - check_account_protection(current_balance):
        → -10% 日亏损: 降低杠杆50%
        → -20% 日亏损: 停止新仓位
        → -25% 总亏损: 紧急停止
```

**波动率熔断** (v3.10.0):
```python
if current_ATR > 7_day_avg_ATR × 2.0:
    max_leverage = 5  # 波动突变时限制杠杆
```

#### 6.2 虚拟仓位管理器

**文件**: `src/managers/virtual_position_manager.py`

**职责**:
- 虚拟仓位追踪
- ML训练数据生成
- 虚拟仓位止损/止盈模拟

**核心逻辑**:
```python
class VirtualPositionManager:
    - create_virtual_position(signal):
        → 记录入场价格、止损、止盈
        → 设置过期时间（96小时）
        
    - monitor_virtual_positions():
        → 每个周期检查所有虚拟仓位
        → 模拟止损/止盈触发
        → 计算盈亏
        → 生成ML训练数据
        
    - _check_virtual_exit(position, current_price):
        if price >= take_profit: 平仓（盈利）
        if price <= stop_loss: 平仓（止损）
        if duration > 96h: 过期平仓
```

**ML数据生成**:
```python
training_data = {
    'entry_price': ...,
    'exit_price': ...,
    'pnl_pct': ...,
    'is_winner': 1 if pnl > 0 else 0,
    'confidence_score': ...,
    'leverage': ...,
    'rsi_entry': ...,
    # ... 31个特征
}
```

#### 6.3 交易记录器

**文件**: `src/managers/trade_recorder.py`

**职责**:
- 交易历史记录
- JSON文件持久化
- 交易统计生成

#### 6.4 期望值计算器

**文件**: `src/managers/expectancy_calculator.py`

**职责**:
- 计算策略期望值
- 胜率统计
- 平均盈亏比

**公式**:
```python
expectancy = (win_rate × avg_win) - (loss_rate × avg_loss)
```

#### 6.5 模型评分器

**文件**: `src/managers/model_scorer.py`

**职责**:
- ML模型质量评分
- 加权评分算法

**评分公式** (v3.9.2.8.5):
```python
model_score = (
    PnL          × 50%  +
    Confidence   × 30%  +
    Win_Rate     × 20%
)
```

---

### 📁 7. 机器学习引擎 (ML)

#### 7.1 模型训练器

**文件**: `src/ml/model_trainer.py`

**职责**:
- XGBoost模型训练
- 超参数调优（可选）
- 集成学习（可选）
- 增量学习支持

**训练流程**:
```python
class XGBoostTrainer:
    def train():
        1. 加载训练数据
        2. 标签泄漏验证（v3.10.0强化）
        3. 动态滑动窗口（500-2000样本）
        4. 准备目标变量（risk_adjusted）
        5. 准备特征矩阵（31个特征）
        6. 类别平衡处理
        7. 特征漂移检测
        8. 计算样本权重:
           - 类别权重（少数类）
           - 时间衰减权重（新数据）
           - 质量权重（完美交易3x）
        9. 超参数调优（可选）
        10. 模型训练（XGBoost）
        11. 模型评估
        12. 保存模型
```

**目标类型**:
```python
# 当前默认: risk_adjusted
target = pnl_pct / atr_entry

# 其他选项:
# - binary: is_winner (1/0)
# - pnl_pct: 收益率百分比
```

**XGBoost参数**:
```python
{
    'max_depth': 6,
    'learning_rate': 0.1,
    'n_estimators': 200,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'objective': 'reg:squarederror',  # 回归
    'eval_metric': 'rmse',
    'n_jobs': <动态CPU核心数>
}
```

#### 7.2 数据处理器

**文件**: `src/ml/data_processor.py`

**职责**:
- 特征工程
- 数据验证
- 训练/测试分割

**31个特征**:
```python
# 基础特征（19个）
basic_features = [
    'confidence_score', 'leverage', 'position_value',
    'risk_reward_ratio', 'order_blocks_count', 'liquidity_zones_count',
    'rsi_entry', 'macd_entry', 'macd_signal_entry', 'macd_histogram_entry',
    'atr_entry', 'bb_width_pct', 'volume_sma_ratio',
    'price_vs_ema50', 'price_vs_ema200',
    'trend_1h_encoded', 'trend_15m_encoded', 'trend_5m_encoded',
    'market_structure_encoded', 'direction_encoded'
]

# 增强特征（12个）
enhanced_features = [
    'hour_of_day', 'day_of_week', 'is_weekend',
    'stop_distance_pct', 'tp_distance_pct',
    'confidence_x_leverage', 'rsi_x_trend', 'atr_x_bb_width',
    'price_momentum_strength', 'volatility_x_confidence',
    'rsi_distance_from_neutral', 'macd_strength_ratio',
    'trend_alignment_score'
]
```

#### 7.3 预测器

**文件**: `src/ml/predictor.py`

**职责**:
- 实时预测
- 批量预测
- 预测结果后处理

**预测流程**:
```python
class MLPredictor:
    def predict(signal):
        1. 提取特征（31个）
        2. 加载模型
        3. 预测
        4. 后处理（概率→0/1 或 回归值）
        5. 返回结果
```

#### 7.4 标签泄漏验证器

**文件**: `src/ml/label_leakage_validator.py`

**职责**:
- 检测未来信息泄漏
- 高相关性特征识别
- 阻止泄漏训练（v3.10.0）

**验证逻辑**:
```python
class LabelLeakageValidator:
    def validate_training_data(df):
        1. 检查禁用特征（pnl, exit, hold_duration等）
        2. 计算特征与标签的相关性
        3. 标记>0.95相关性的特征（潜在泄漏）
        4. 检测到严重泄漏时返回错误
        5. 阻止训练
```

#### 7.5 其他ML组件

**超参数调优器** (`hyperparameter_tuner.py`):
- RandomizedSearchCV
- 5-fold 交叉验证

**集成模型** (`ensemble_model.py`):
- XGBoost + LightGBM + CatBoost
- Soft Voting

**漂移检测器** (`drift_detector.py`):
- 特征分布漂移检测
- 多变量漂移（MMD）
- 动态窗口调整

**不确定性量化** (`uncertainty_quantifier.py`):
- Quantile Regression
- 置信区间估计

**特征重要性监控** (`feature_importance_monitor.py`):
- 实时追踪特征贡献
- 检测重要性漂移

**类别平衡处理** (`imbalance_handler.py`):
- 样本权重计算
- 类别平衡分析

**自适应学习器** (`adaptive_learner.py`):
- 动态学习率调整
- 动态树数量调整

**特征缓存** (`feature_cache.py`):
- MD5哈希缓存
- 1小时TTL
- 特征计算加速60-80%

---

### 📁 8. 核心基础设施 (Core)

#### 8.1 缓存管理器

**文件**: `src/core/cache_manager.py`

**职责**:
- 内存缓存管理
- 时间戳版本控制
- 缓存命中率统计

**缓存策略**:
```python
cache_key = f"{symbol}_{interval}_{timestamp}"
# 时间戳精确到分钟，确保同一分钟内复用
```

#### 8.2 限流器

**文件**: `src/core/rate_limiter.py`

**职责**:
- 令牌桶算法
- API请求限流
- 1920 req/min

#### 8.3 熔断器

**文件**: `src/core/circuit_breaker.py`

**职责**:
- 三级熔断保护
- 白名单bypass
- 自动恢复

**三级熔断** (v3.9.2.8.4):
```python
Level 1: WARNING   (2次失败) → 记录警告
Level 2: CRITICAL  (4次失败) → 延迟2秒
Level 3: EMERGENCY (5次失败) → 阻断60秒
```

---

### 📁 9. 监控模块 (Monitoring)

#### 9.1 健康监控

**文件**: `src/monitoring/health_monitor.py`

**职责**:
- 系统健康检查
- 组件状态监控

#### 9.2 性能监控

**文件**: `src/monitoring/performance_monitor.py`

**职责**:
- 性能指标追踪
- 缓存命中率
- API响应时间

---

### 📁 10. 工具层 (Utils)

#### 10.1 技术指标

**文件**: `src/utils/indicators.py`

**职责**:
- 所有技术指标计算
- ICT/SMC功能实现

**函数列表**:
```python
# 基础指标
- calculate_ema(df, period)
- calculate_macd(df)
- calculate_rsi(df, period)
- calculate_atr(df, period)
- calculate_bollinger_bands(df, period)
- calculate_adx(df, period)
- calculate_ema_slope(df, period)

# ICT/SMC功能
- identify_order_blocks(df, lookback, volume_multiplier, rejection_threshold, max_history)
- calculate_ob_decay_factor(ob, time_decay_hours, decay_rate, max_test_count)
- identify_swing_points(df, lookback)
- determine_market_structure(df)

# v3.11.0新增
- detect_bos_choch(df, swing_lookback)
- classify_market_regime(df, adx_trend, adx_strong, bb_period)
- detect_reversal_risk(df, liquidity_sweep_threshold, rsi_extreme_bull, rsi_extreme_bear, macd_convergence_ratio)
```

#### 10.2 辅助函数

**文件**: `src/utils/helpers.py`

**职责**:
- 时间转换
- 数值格式化
- 其他通用函数

---

## 📊 数据流图

### 主循环数据流

```
                    ┌─────────────────┐
                    │  Main Loop      │
                    │  (每60秒)       │
                    └────────┬────────┘
                             │
                    ┌────────▼─────────┐
                    │ DataService      │
                    │ scan_market()    │
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │  选择200个高流动性交易对    │
              └──────────────┬──────────────┘
                             │
                    ┌────────▼─────────┐
                    │ ParallelAnalyzer │
                    │ 32核心并行分析   │
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │  ICTStrategy.analyze()      │
              │  - 趋势分析                 │
              │  - Order Blocks识别         │
              │  - BOS/CHOCH检测            │
              │  - 市场状态分类             │
              │  - 反转风险评估             │
              │  - 置信度计算               │
              └──────────────┬──────────────┘
                             │
                    ┌────────▼─────────┐
                    │ MLPredictor      │
                    │ predict()        │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ RiskManager      │
                    │ should_trade()   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ TradingService   │
                    │ execute_signal() │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
     ┌────────▼─────────┐        ┌─────────▼────────┐
     │ 真实交易执行     │        │ 虚拟仓位记录     │
     └────────┬─────────┘        └─────────┬────────┘
              │                             │
     ┌────────▼─────────┐        ┌─────────▼────────┐
     │ PositionMonitor  │        │VirtualPositionMgr│
     │ 监控真实仓位     │        │ 监控虚拟仓位     │
     └────────┬─────────┘        └─────────┬────────┘
              │                             │
              └──────────────┬──────────────┘
                             │
                    ┌────────▼─────────┐
                    │ TradeRecorder    │
                    │ 记录交易数据     │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ ML Training Data │
                    │ (ml_data/)       │
                    └──────────────────┘
```

### ML训练数据流

```
┌──────────────────┐
│ Virtual Positions│
│ 虚拟仓位数据     │
└────────┬─────────┘
         │
┌────────▼─────────┐
│ TradeRecorder    │
│ 收集特征+标签    │
└────────┬─────────┘
         │
┌────────▼─────────┐
│ ml_data/         │
│ training_*.json  │
└────────┬─────────┘
         │
┌────────▼─────────┐
│ XGBoostTrainer   │
│ train()          │
├──────────────────┤
│ 1. 加载数据      │
│ 2. 泄漏验证      │
│ 3. 特征工程      │
│ 4. 样本权重      │
│ 5. 训练模型      │
│ 6. 评估保存      │
└────────┬─────────┘
         │
┌────────▼─────────┐
│ data/models/     │
│ xgboost_model.pkl│
└────────┬─────────┘
         │
┌────────▼─────────┐
│ MLPredictor      │
│ predict()        │
└──────────────────┘
```

---

## 🛠️ 技术栈

### 核心技术

| 类别 | 技术 | 用途 |
|------|------|------|
| **语言** | Python 3.11+ | 主开发语言 |
| **异步框架** | asyncio, aiohttp | 异步I/O处理 |
| **并行计算** | multiprocessing | 32核心并行分析 |
| **机器学习** | XGBoost, LightGBM, CatBoost | 模型训练与预测 |
| **数据处理** | pandas, numpy | 数据处理与计算 |
| **技术分析** | ta-lib（可选）| 技术指标计算 |
| **API客户端** | ccxt（未使用）, 自实现 | Binance API |
| **缓存** | 内存字典 | 数据缓存 |
| **存储** | JSON文件 | 持久化存储 |
| **日志** | logging | 日志系统 |
| **部署** | Railway | 云部署平台 |
| **通知** | Discord.py | Discord集成 |

### 依赖库

**核心依赖** (`requirements.txt`):
```
pandas>=2.0.0
numpy>=1.24.0
xgboost>=2.0.0
lightgbm>=4.0.0
catboost>=1.2.0
scikit-learn>=1.3.0
aiohttp>=3.9.0
discord.py>=2.3.0
```

---

## 🚀 部署架构

### Railway 部署拓扑

```
┌─────────────────────────────────────────────────────────────┐
│                     Railway Platform                        │
│                                                             │
│  Region: Asia (Singapore/Tokyo)                            │
│  Instance: 32vCPU / 32GB RAM                               │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │               Trading Bot Container                   │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────────┐ │ │
│  │  │  Environment Variables:                         │ │ │
│  │  │  - BINANCE_API_KEY                             │ │ │
│  │  │  - BINANCE_API_SECRET                          │ │ │
│  │  │  - DISCORD_TOKEN                               │ │ │
│  │  │  - TRADING_ENABLED=true                        │ │ │
│  │  │  - MAX_POSITIONS=999                           │ │ │
│  │  └─────────────────────────────────────────────────┘ │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────────┐ │ │
│  │  │  Persistent Volume:                             │ │ │
│  │  │  /app/data/                                    │ │ │
│  │  │  ├── logs/                                     │ │ │
│  │  │  ├── models/                                   │ │ │
│  │  │  ├── trades.json                               │ │ │
│  │  │  └── virtual_positions.json                    │ │ │
│  │  └─────────────────────────────────────────────────┘ │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────────┐ │ │
│  │  │  Network:                                       │ │ │
│  │  │  - Outbound: Binance API (低延迟)              │ │ │
│  │  │  - Outbound: Discord Webhook                   │ │ │
│  │  └─────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
     ┌────────▼────────┐          ┌────────▼────────┐
     │  Binance Futures│          │  Discord Server │
     │  API (Asia)     │          │  Notifications  │
     └─────────────────┘          └─────────────────┘
```

### 本地开发架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Local Development                        │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  python -m src.main                                   │ │
│  │                                                       │ │
│  │  TRADING_ENABLED=false (模拟模式)                     │ │
│  │  Binance Testnet (可选)                              │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔒 安全与风险控制

### 多层风险控制架构

```
┌─────────────────────────────────────────────────────────────┐
│                    第一层：信号质量控制                     │
│  - MIN_CONFIDENCE >= 35%                                   │
│  - ADX趋势过滤（>= 20）                                    │
│  - Order Block质量筛选（v3.11.0）                          │
│  - BOS/CHOCH结构验证（v3.11.0）                            │
│  - 市场状态筛选（trending/breakout only）（v3.11.0）       │
│  - 反转风险评估（<0.4）（v3.11.0）                         │
└─────────────────────────────────────────────────────────────┘
                             │
┌─────────────────────────────────────────────────────────────┐
│                    第二层：ML预测验证                       │
│  - XGBoost预测（risk_adjusted模型）                       │
│  - 标签泄漏检测（v3.10.0强化）                             │
│  - 特征漂移监控                                            │
│  - 不确定性量化                                            │
└─────────────────────────────────────────────────────────────┘
                             │
┌─────────────────────────────────────────────────────────────┐
│                    第三层：风险管理                         │
│  - v3.11.1: 无持仓数量限制                                 │
│  - 动态杠杆调整（3x-20x）                                  │
│  - 动态仓位大小（3%-13%）                                  │
│  - 连续亏损保护（5次暂停）                                 │
│  - 回撤保护（15%暂停）                                     │
│  - 波动率熔断（v3.10.0）                                   │
└─────────────────────────────────────────────────────────────┘
                             │
┌─────────────────────────────────────────────────────────────┐
│                    第四层：执行保护                         │
│  - 限价单优先（降低滑点）                                  │
│  - 保护监护任务（确保止损/止盈）                           │
│  - 订单重试机制（最多5次）                                 │
│  - 熔断器bypass（平仓优先）                                │
└─────────────────────────────────────────────────────────────┘
                             │
┌─────────────────────────────────────────────────────────────┐
│                    第五层：账户保护                         │
│  - 日亏损-10%: 降低杠杆50%                                 │
│  - 日亏损-20%: 停止新仓位                                  │
│  - 总亏损-25%: 紧急停止                                    │
│  - API限流保护（1920 req/min）                             │
│  - 三级熔断保护                                            │
└─────────────────────────────────────────────────────────────┘
```

### 安全检查清单

**数据安全**:
- ✅ 环境变量存储API密钥
- ✅ 密钥不写入日志
- ✅ 密钥不提交到Git

**交易安全**:
- ✅ 默认模拟模式（TRADING_ENABLED=false）
- ✅ 强制止损保护
- ✅ 保护监护任务
- ✅ 多层熔断机制

**代码安全**:
- ✅ 标签泄漏验证（阻止训练）
- ✅ 特征验证（禁用未来信息）
- ✅ 异常处理与日志记录

---

## 📈 性能指标

### 系统性能

| 指标 | 数值 | 说明 |
|------|------|------|
| **扫描周期** | 60秒 | 主循环间隔 |
| **并行核心** | 32核 | 充分利用32vCPU |
| **分析速度** | ~6秒 | 200个交易对完整分析 |
| **缓存命中率** | 60-80% | K线数据缓存 |
| **API请求** | <1920/min | 80%官方限额 |

### ML模型性能

| 指标 | 目标 | 说明 |
|------|------|------|
| **训练准确率** | 75-82% | 回归/分类准确率 |
| **ROC-AUC** | 0.80-0.85 | 分类模式 |
| **训练速度** | 5-10倍 | GPU加速（有GPU时） |
| **增量学习** | 70-80% | 训练加速 |

### 交易性能

| 指标 | 目标 | 说明 |
|------|------|------|
| **信号生成** | 10-30/周期 | 筛选后的高质量信号 |
| **胜率** | 60-80% | 期望胜率 |
| **风险收益比** | 1:1 - 1:2 | 动态调整 |
| **最大回撤** | <15% | 触发暂停交易 |

---

## 🔧 配置文件说明

### 主配置文件

**位置**: `src/config.py`

**关键配置段**:

```python
# ===== 交易配置 =====
MAX_POSITIONS = 999          # v3.11.1: 无限持仓
CYCLE_INTERVAL = 60          # 扫描周期
TRADING_ENABLED = False      # 默认模拟模式

# ===== 风险配置 =====
MIN_LEVERAGE = 3
MAX_LEVERAGE = 20
MIN_MARGIN_PCT = 0.03
MAX_MARGIN_PCT = 0.13
MIN_CONFIDENCE = 0.35

# ===== 策略配置 =====
EMA_FAST = 20
EMA_SLOW = 50
ADX_TREND_THRESHOLD = 20.0
VOLATILITY_CIRCUIT_BREAKER_ENABLED = True

# ===== ICT/SMC配置（v3.11.0）=====
OB_REJECTION_THRESHOLD = 0.005
OB_VOLUME_MULTIPLIER = 1.5
OB_MAX_HISTORY = 20
OB_DECAY_ENABLED = True

# ===== 缓存配置 =====
CACHE_TTL_KLINES_1H = 3600
CACHE_TTL_KLINES_15M = 900
CACHE_TTL_KLINES_5M = 300

# ===== 熔断器配置 =====
GRADED_CIRCUIT_BREAKER_ENABLED = True
CIRCUIT_BREAKER_WARNING_THRESHOLD = 2
CIRCUIT_BREAKER_BLOCKED_THRESHOLD = 5
```

### 环境变量配置

**必需变量**:
```bash
BINANCE_API_KEY=<你的API密钥>
BINANCE_API_SECRET=<你的API密钥>
DISCORD_TOKEN=<Discord Bot Token>
SESSION_SECRET=<随机字符串>
```

**可选变量**:
```bash
BINANCE_TESTNET=true           # 测试网模式
TRADING_ENABLED=true           # 启用真实交易
MAX_POSITIONS=999              # 持仓限制（默认999）
LOG_LEVEL=INFO                 # 日志级别
TOP_LIQUIDITY_SYMBOLS=200      # 监控交易对数量
```

---

## 📂 目录结构总览

```
.
├── src/                          # 源代码目录
│   ├── main.py                   # 主入口
│   ├── config.py                 # 配置管理
│   ├── clients/                  # 客户端层
│   │   ├── binance_client.py
│   │   └── binance_errors.py
│   ├── core/                     # 核心基础设施
│   │   ├── cache_manager.py
│   │   ├── rate_limiter.py
│   │   └── circuit_breaker.py
│   ├── services/                 # 服务层
│   │   ├── data_service.py
│   │   ├── parallel_analyzer.py
│   │   ├── timeframe_scheduler.py
│   │   ├── trading_service.py
│   │   └── position_monitor.py
│   ├── strategies/               # 策略引擎
│   │   └── ict_strategy.py
│   ├── managers/                 # 管理器层
│   │   ├── risk_manager.py
│   │   ├── virtual_position_manager.py
│   │   ├── trade_recorder.py
│   │   ├── expectancy_calculator.py
│   │   └── model_scorer.py
│   ├── ml/                       # 机器学习引擎
│   │   ├── model_trainer.py
│   │   ├── predictor.py
│   │   ├── data_processor.py
│   │   ├── hyperparameter_tuner.py
│   │   ├── ensemble_model.py
│   │   ├── label_leakage_validator.py
│   │   ├── drift_detector.py
│   │   ├── imbalance_handler.py
│   │   ├── target_optimizer.py
│   │   ├── uncertainty_quantifier.py
│   │   ├── feature_importance_monitor.py
│   │   ├── adaptive_learner.py
│   │   └── feature_cache.py
│   ├── integrations/             # 第三方集成
│   │   └── discord_bot.py
│   ├── monitoring/               # 监控模块
│   │   ├── health_monitor.py
│   │   └── performance_monitor.py
│   └── utils/                    # 工具层
│       ├── indicators.py
│       └── helpers.py
├── data/                         # 数据目录
│   ├── logs/                     # 日志文件
│   ├── models/                   # ML模型
│   ├── trades.json               # 交易记录
│   └── virtual_positions.json    # 虚拟仓位
├── ml_data/                      # ML训练数据
│   └── training_*.json
├── docs/                         # 文档目录
│   ├── COMPLETE_ARCHITECTURE_v3.11.1.md  # 本文档
│   ├── DEPLOYMENT_GUIDE.md
│   ├── QUICK_START.md
│   └── ...
├── examples/                     # 示例文件
├── scripts/                      # 工具脚本
├── requirements.txt              # Python依赖
├── railway.json                  # Railway配置
├── replit.md                     # 项目说明
└── README.md                     # 项目README
```

---

## 🎓 关键设计模式

### 1. 策略模式
- **ICTStrategy**: 封装交易策略逻辑
- 可扩展为多策略系统

### 2. 观察者模式
- **PositionMonitor**: 监控仓位变化
- **Discord通知**: 订阅交易事件

### 3. 工厂模式
- **TargetOptimizer**: 根据类型创建不同目标变量
- **EnsembleModel**: 创建不同ML模型

### 4. 单例模式
- **Config**: 全局配置单例
- **CacheManager**: 缓存管理单例

### 5. 模板方法模式
- **XGBoostTrainer.train()**: 定义训练流程模板
- 子类可覆盖特定步骤

### 6. 责任链模式
- **风险控制五层架构**: 逐层验证
- **熔断器三级保护**: 逐级升级

---

## 📝 版本演进历史

| 版本 | 日期 | 核心特性 |
|------|------|---------|
| **v3.11.1** | 2025-10-27 | 🚀 移除持仓限制（无限倉位）|
| **v3.11.0** | 2025-10-27 | 🎯 OB质量筛选+BOS/CHOCH+市场状态分类+反转预警 |
| **v3.10.0** | 2025-10-27 | 🔥 ADX趋势过滤+ML泄漏阻断+波动率熔断 |
| **v3.9.2.9** | 2025-10-27 | ⚡ 性能优化（动态CPU检测+临时文件清理）|
| **v3.9.2.8.5** | 2025-10-26 | 🎯 模型评分系统（质量权重）|
| **v3.9.2.8.4** | 2025-10-26 | 🚨 分级熔断器（三级熔断+Bypass）|
| **v3.4.0** | 2025-10-25 | ✨ XGBoost超参数调优+集成学习+特征缓存 |
| **v3.1.0** | 2025-10-25 | 🔴 P0性能优化（缓存+期望值整合）|
| **v2.0** | 2025-10-25 | 📊 200个高波动率交易对+32核并行 |

---

## 🚦 快速开始指引

### 1. 本地开发

```bash
# 克隆项目
git clone <repo-url>
cd <project-dir>

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
export DISCORD_TOKEN="your_token"
export SESSION_SECRET="random_string"
export TRADING_ENABLED="false"  # 模拟模式

# 运行
python -m src.main
```

### 2. Railway部署

```bash
# 推送代码
git push origin main

# 在Railway控制台:
# 1. 选择亚洲区域（新加坡/东京）
# 2. 配置环境变量
# 3. 选择32vCPU / 32GB RAM
# 4. 部署
```

### 3. 验证部署

查看启动日志确认:
```
✅ v3.11.1成功启动
✅ 配置验证通过
✅ Binance API连接成功
✅ 成功加载 XXX 个交易对
✅ 已选择 200 个高波动率交易对
```

---

## 📞 支持与维护

### 日志位置
- **主日志**: `data/logs/trading_bot.log`
- **Railway日志**: 控制台实时查看

### 常见问题

**Q: 为什么没有信号生成？**
A: 检查以下条件:
- MIN_CONFIDENCE是否过高（默认35%）
- ADX_TREND_THRESHOLD是否过严（默认20）
- 市场状态是否为trending/breakout
- 反转风险评分是否<0.4

**Q: 如何启用真实交易？**
A: 设置环境变量 `TRADING_ENABLED=true`

**Q: 如何调整持仓数量？**
A: v3.11.1已移除限制，通过风险控制自动管理

**Q: 如何查看ML模型性能？**
A: 查看 `data/models/model_metrics.json`

---

## 📄 许可证

本项目为私有项目，仅供授权用户使用。

---

**文档生成时间**: 2025-10-27  
**文档版本**: v3.11.1  
**作者**: Replit Agent  
**最后更新**: 2025-10-27 17:05 UTC

