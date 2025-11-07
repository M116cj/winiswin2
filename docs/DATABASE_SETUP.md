# Railway PostgreSQL 数据库设置指南

## 概述

本交易机器人系统使用Railway PostgreSQL数据库进行数据持久化，包括交易记录、ML模型存储、市场数据和交易信号。

## 环境变量配置

### Railway环境变量

在Railway项目中，PostgreSQL服务会自动提供以下环境变量：

```bash
DATABASE_URL=postgresql://postgres:password@postgres.railway.internal:5432/railway
DATABASE_PUBLIC_URL=postgresql://postgres:password@switchyard.proxy.rlwy.net:port/railway
PGHOST=postgres.railway.internal
PGPORT=5432
PGUSER=postgres
PGPASSWORD=your_password
PGDATABASE=railway
```

### 推荐使用

- **内部连接（推荐）**: 使用 `DATABASE_URL`
  - 更快（内部网络）
  - 更安全
  - 低延迟
  
- **外部连接**: 使用 `DATABASE_PUBLIC_URL`
  - 从本地开发环境连接
  - 从外部工具连接（如DBeaver）

## 系统架构

### 核心组件

```
src/database/
├── __init__.py          # 模块导出
├── config.py            # 数据库配置
├── manager.py           # DatabaseManager（连接池管理）
├── initializer.py       # 表结构初始化
└── service.py           # TradingDataService（数据操作）
```

### 数据表结构

#### 1. trades - 交易记录表
存储所有交易的完整信息，包括44个特征字段。

**核心字段**：
- 基本信息：symbol, direction, entry_price, exit_price, quantity, leverage
- 时间戳：entry_timestamp, exit_timestamp
- 盈亏：pnl, pnl_pct, won
- 策略：strategy, confidence, win_probability
- 技术指标：rsi, macd, atr, ema50, ema200等
- ICT/SMC特征：order_blocks_count, liquidity_grab, fvg_count等

#### 2. ml_models - ML模型存储表
存储训练好的机器学习模型（二进制格式）。

**核心字段**：
- model_name, version
- model_data（BYTEA - 序列化模型）
- features（JSONB - 特征列表）
- accuracy, precision_score, recall, f1_score
- is_active（是否为当前活跃模型）

#### 3. market_data - 市场数据表
存储K线和技术指标数据。

**核心字段**：
- symbol, timeframe, timestamp
- OHLCV：open, high, low, close, volume
- 技术指标：rsi, macd, bb_upper, ema20, atr等

#### 4. trading_signals - 交易信号表
存储生成的交易信号。

**核心字段**：
- symbol, direction, confidence
- entry_price, stop_loss, take_profit
- status（PENDING, EXECUTED, CANCELLED）
- features（JSONB - 信号特征）

## 使用指南

### 1. 初始化数据库

```python
from src.database import DatabaseManager, initialize_database

# 创建数据库管理器
db_manager = DatabaseManager(
    min_connections=1,
    max_connections=20
)

# 初始化所有表
initialize_database(db_manager)
```

### 2. 保存交易记录

```python
from src.database import TradingDataService
from datetime import datetime

# 创建服务实例
db_service = TradingDataService(db_manager)

# 准备交易数据
trade_data = {
    'symbol': 'BTCUSDT',
    'direction': 'LONG',
    'entry_price': 43250.50,
    'quantity': 0.1,
    'entry_timestamp': datetime.utcnow().isoformat() + 'Z',
    'leverage': 5,
    'confidence': 0.75,
    'win_probability': 0.70,
    'strategy': 'ICT_SMC',
    'position_value': 2162.53,
    'rsi': 58.3,
    'macd': 125.6,
    'order_blocks_count': 3,
    'status': 'OPEN'
}

# 保存交易
trade_id = db_service.save_trade(trade_data)
print(f"交易已保存，ID: {trade_id}")
```

### 3. 更新交易状态

```python
# 平仓时更新
success = db_service.update_trade_status(
    trade_id=trade_id,
    status='CLOSED',
    exit_price=43680.20,
    pnl=42.97,
    pnl_pct=1.99
)
```

### 4. 查询交易历史

```python
# 获取最近100笔BTCUSDT交易
trades = db_service.get_trade_history(
    symbol='BTCUSDT',
    limit=100,
    status='CLOSED'
)

# 获取统计数据
stats = db_service.get_statistics()
print(f"总交易数: {stats['total_trades']}")
print(f"胜率: {stats['win_rate']:.2%}")
print(f"平均盈亏: {stats['avg_pnl_pct']:.2%}")
```

### 5. 保存和加载ML模型

```python
import xgboost as xgb

# 训练模型
model = xgb.XGBClassifier()
model.fit(X_train, y_train)

# 保存到数据库
model_id = db_service.save_ml_model(
    model_name='xgboost_v1',
    model=model,
    features=['rsi', 'macd', 'atr', 'trend_1h'],
    accuracy=0.85,
    parameters={
        'max_depth': 5,
        'learning_rate': 0.1,
        'training_samples': 1000
    },
    is_active=True
)

# 从数据库加载
loaded_model = db_service.load_ml_model('xgboost_v1')
predictions = loaded_model.predict(X_test)
```

## 与现有系统集成

### 整合到EnhancedTradeRecorder

```python
# src/managers/enhanced_trade_recorder.py

from src.database import DatabaseManager, TradingDataService

class EnhancedTradeRecorder:
    def __init__(self):
        # 现有初始化...
        
        # 添加数据库支持
        try:
            self.db_manager = DatabaseManager()
            self.db_service = TradingDataService(self.db_manager)
            self.db_enabled = True
        except:
            self.db_enabled = False
    
    def record_exit(self, symbol, exit_price, pnl, pnl_pct, reason):
        # 现有JSONL记录...
        
        # 同时保存到PostgreSQL
        if self.db_enabled:
            try:
                self.db_service.save_trade({
                    'symbol': symbol,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    # ... 其他字段
                })
            except Exception as e:
                logger.error(f"数据库保存失败: {e}")
```

### 整合到ModelInitializer

```python
# src/core/model_initializer.py

from src.database import TradingDataService

class ModelInitializer:
    async def _train_xgboost_model(self, training_data):
        # 训练模型...
        model.fit(X_train, y_train)
        
        # 保存到数据库
        if hasattr(self, 'db_service'):
            self.db_service.save_ml_model(
                model_name='xgboost_production',
                model=model,
                features=feature_names,
                accuracy=accuracy_score,
                is_active=True
            )
```

## 运行测试

```bash
# 设置环境变量（本地测试）
export DATABASE_URL="postgresql://postgres:password@localhost:5432/trading_bot"

# 运行测试
python tests/test_database.py
```

## 性能优化

### 连接池配置

```python
db_manager = DatabaseManager(
    min_connections=2,      # 最小连接数
    max_connections=20,     # 最大连接数（根据Railway限制调整）
    connection_timeout=30,  # 连接超时
    auto_retry=True,        # 自动重试
    max_retries=3          # 最大重试次数
)
```

### 索引优化

系统已自动创建以下索引：
- `idx_trades_symbol_time` - 按交易对和时间查询
- `idx_trades_status` - 按状态过滤
- `idx_trades_won` - 按胜负统计
- `idx_ml_models_active` - 查询活跃模型

### 批量操作

```python
# 批量插入市场数据（待实现）
market_data_batch = [...]
db_service.bulk_insert_market_data(market_data_batch)
```

## 故障处理

### 连接失败

系统会自动重试（最多3次），使用指数退避策略。

### 健康检查

```python
# 定期检查数据库健康状态
is_healthy = db_manager.check_health()
if not is_healthy:
    logger.error("数据库连接异常，请检查Railway服务状态")
```

### 日志监控

所有数据库操作都会记录详细日志：
- ✅ 成功操作
- ⚠️ 警告信息
- ❌ 错误详情

## 安全最佳实践

1. **永不硬编码凭证** - 始终使用环境变量
2. **使用参数化查询** - 防止SQL注入
3. **限制连接数** - 避免耗尽数据库资源
4. **定期备份** - Railway自动提供备份功能
5. **监控日志** - 及时发现异常

## 数据迁移

从JSONL迁移到PostgreSQL：

```python
# 读取现有JSONL数据
with open('data/trades.jsonl', 'r') as f:
    for line in f:
        trade = json.loads(line)
        db_service.save_trade(trade)
```

## 常见问题

### Q: 如何从本地连接Railway数据库？
A: 使用 `DATABASE_PUBLIC_URL` 环境变量。

### Q: 数据库满了怎么办？
A: 在Railway控制台升级数据库容量，或清理旧数据。

### Q: 如何查看SQL查询？
A: 在代码中启用DEBUG日志级别。

### Q: 支持事务吗？
A: 是的，使用上下文管理器：
```python
with db_manager.get_connection() as conn:
    # 事务操作
    conn.commit()
```

## 技术支持

- Railway文档: https://docs.railway.app/databases/postgresql
- PostgreSQL文档: https://www.postgresql.org/docs/
- psycopg2文档: https://www.psycopg.org/docs/

---

**注意**: 在部署到Railway之前，请确保在环境变量中正确配置 `DATABASE_URL`。
