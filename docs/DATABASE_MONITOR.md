# PostgreSQL 数据库监控系统使用指南

## 概述

DatabaseMonitor 是一个**生产级的PostgreSQL实时数据监控系统**，专为Railway部署的交易机器人设计。它可以在日志中自动显示详细的数据库统计信息，帮助您实时了解系统状态。

## 核心功能

### ✨ 主要特性

- ✅ **实时统计** - 自动收集并显示数据库各项指标
- ✅ **后台监控** - 独立线程运行，不影响主业务
- ✅ **性能优化** - 查询缓存，轻量级设计
- ✅ **智能警告** - 可配置阈值，自动检测异常
- ✅ **格式化输出** - 清晰易读的日志显示
- ✅ **资源安全** - 自动错误恢复，资源清理

### 📊 监控指标

#### 1. 交易记录统计
- 总交易数
- 今日新增交易
- 未平仓数量
- 已平仓数量
- 胜率
- 平均盈亏百分比
- 总盈亏金额

#### 2. ML模型统计
- 总模型数
- 活跃模型数
- 最新版本号
- 平均准确率

#### 3. 市场数据统计
- 总记录数
- 今日更新数
- 交易对数量
- 时间周期数

#### 4. 交易信号统计
- 总信号数
- 待执行信号
- 已执行信号
- 今日信号数

#### 5. 性能指标
- 数据库健康状态
- 连接池状态
- 查询响应时间
- 错误率

---

## 快速开始

### 方式1: 一次性显示统计摘要

```python
from src.database import DatabaseManager, DatabaseMonitor

# 创建数据库管理器
db_manager = DatabaseManager()

# 创建监控器
monitor = DatabaseMonitor(db_manager, auto_start=False)

# 显示统计摘要（一次性）
summary = monitor.get_summary()
```

**输出示例:**
```
======================================================================
🕒 [2025-01-15 14:30:25 UTC] 📊 数据库实时统计
======================================================================
📈 交易记录:
   • 总交易数: 1,250
   • 今日新增: 15
   • 未平仓: 3
   • 已平仓: 1,247
   • 胜率: 85.2%
   • 平均盈亏: 1.45%
   • 总盈亏: $18,125.50

🤖 ML 模型:
   • 总模型数: 8
   • 活跃模型: 2
   • 最新版本: v3
   • 平均准确率: 84.5%

📊 市场数据:
   • 总记录数: 45,820
   • 今日更新: 1,245
   • 交易对数: 5
   • 时间周期: 3

🚦 交易信号:
   • 总信号数: 890
   • 待执行: 2
   • 已执行: 875
   • 今日信号: 42

⚡ 性能指标:
   • 数据库状态: ✅ 健康
   • 连接数: 3/20
   • 查询响应: 45.2ms
   • 错误率: 0.0%
======================================================================
```

### 方式2: 后台自动监控（推荐用于生产环境）

```python
from src.database import DatabaseManager, DatabaseMonitor, initialize_database

async def main():
    # 1. 初始化数据库
    db_manager = DatabaseManager(
        min_connections=2,
        max_connections=20
    )
    
    initialize_database(db_manager)
    
    # 2. 启动后台监控
    monitor = DatabaseMonitor(
        db_manager=db_manager,
        refresh_interval=60,    # 每60秒刷新一次
        auto_start=True,        # 自动启动
        enable_alerts=True      # 启用警告
    )
    
    # 3. 运行交易机器人
    try:
        await run_trading_bot()
    finally:
        # 4. 清理资源
        monitor.stop_monitoring()
        db_manager.close_all_connections()
```

---

## 配置选项

### 初始化参数

```python
monitor = DatabaseMonitor(
    db_manager=db_manager,      # 必需：数据库管理器
    refresh_interval=60,        # 刷新间隔（秒），默认60
    auto_start=False,           # 是否自动启动，默认False
    enable_alerts=True          # 是否启用警告，默认True
)
```

### 自定义警告阈值

```python
# 修改阈值配置
monitor.thresholds = {
    'max_response_time_ms': 500,   # 最大响应时间（毫秒）
    'max_error_rate': 0.02,        # 最大错误率（2%）
    'max_open_positions': 5,       # 最大未平仓数量
    'min_connection_pool': 1,      # 最小连接数
}
```

**警告示例输出:**
```
🚨 阈值警告:
   ⚠️ 查询响应时间过长: 650.2ms > 500ms
   ⚠️ 未平仓数量过多: 7 > 5
```

---

## API参考

### DatabaseMonitor 类

#### 初始化
```python
def __init__(
    self,
    db_manager: DatabaseManager,
    refresh_interval: int = 60,
    auto_start: bool = False,
    enable_alerts: bool = True
)
```

#### 方法

##### start_monitoring()
启动后台监控服务
```python
success = monitor.start_monitoring()
# Returns: bool - 是否成功启动
```

##### stop_monitoring()
停止监控服务
```python
monitor.stop_monitoring()
```

##### get_real_time_stats(use_cache=True)
获取实时统计数据
```python
stats = monitor.get_real_time_stats(use_cache=True)
# Returns: Dict[str, Any] - 统计数据字典
```

**返回数据结构:**
```python
{
    'timestamp': '2025-01-15T14:30:25.123456',
    'trades': {
        'total_trades': 1250,
        'open_positions': 3,
        'closed_trades': 1247,
        'winning_trades': 1062,
        'today_trades': 15,
        'avg_pnl_pct': 1.45,
        'total_pnl': 18125.50,
        'win_rate': 85.2
    },
    'ml_models': {...},
    'market_data': {...},
    'trading_signals': {...},
    'performance': {
        'database_healthy': True,
        'connection_count': 3,
        'max_connections': 20,
        'error_rate': 0.0,
        'query_time_ms': 45.2
    }
}
```

##### get_summary()
一次性显示统计摘要（不启动后台监控）
```python
summary = monitor.get_summary()
# Returns: Dict[str, Any] - 统计摘要
```

##### display_stats(stats)
显示格式化的统计信息
```python
monitor.display_stats(stats)
```

##### check_alerts(stats)
检查阈值并发出警告
```python
monitor.check_alerts(stats)
```

---

## 整合到交易机器人

### 在 src/main.py 中整合

```python
# src/main.py

import asyncio
import logging
from src.database import (
    DatabaseManager,
    TradingDataService,
    DatabaseMonitor,
    initialize_database,
    DatabaseConfig
)

logger = logging.getLogger(__name__)

async def main():
    logger.info("🚀 启动交易机器人...")
    
    # 初始化数据库
    db_manager = None
    db_service = None
    db_monitor = None
    
    if DatabaseConfig.is_database_configured():
        try:
            logger.info("📊 正在初始化PostgreSQL数据库...")
            
            # 1. 创建数据库管理器
            db_manager = DatabaseManager(
                min_connections=2,
                max_connections=10
            )
            
            # 2. 初始化表结构
            if initialize_database(db_manager):
                db_service = TradingDataService(db_manager)
                logger.info("✅ 数据库初始化成功")
                
                # 3. 启动数据库监控（后台运行）
                db_monitor = DatabaseMonitor(
                    db_manager=db_manager,
                    refresh_interval=300,  # 每5分钟刷新一次
                    auto_start=True,
                    enable_alerts=True
                )
                logger.info("✅ 数据库监控已启动")
                
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            logger.warning("⚠️ 将使用JSONL文件存储（降级模式）")
    
    # 运行交易机器人主逻辑
    try:
        # 现有的交易逻辑...
        await run_trading_logic()
        
    finally:
        # 清理资源
        if db_monitor:
            db_monitor.stop_monitoring()
        
        if db_manager:
            db_manager.close_all_connections()
            logger.info("✅ 数据库连接已关闭")

if __name__ == "__main__":
    asyncio.run(main())
```

### 配置建议

#### 开发环境
```python
monitor = DatabaseMonitor(
    db_manager=db_manager,
    refresh_interval=30,    # 30秒刷新，快速调试
    auto_start=True,
    enable_alerts=True
)
```

#### 生产环境（Railway）
```python
monitor = DatabaseMonitor(
    db_manager=db_manager,
    refresh_interval=300,   # 5分钟刷新，减少日志量
    auto_start=True,
    enable_alerts=True
)
```

---

## 性能优化

### 1. 查询缓存

监控系统内置5秒缓存，减少数据库查询：

```python
# 使用缓存（默认）
stats = monitor.get_real_time_stats(use_cache=True)

# 强制刷新
stats = monitor.get_real_time_stats(use_cache=False)
```

### 2. 轻量级查询

所有统计查询都经过优化：
- 使用聚合函数（COUNT, AVG, SUM）
- 利用数据库索引
- 单次查询获取多个指标
- 避免全表扫描

### 3. 资源控制

- 独立后台线程运行
- 自动错误恢复
- 连接池复用
- 超时保护

---

## 错误处理

### 连接异常处理

```python
# 监控服务会自动处理连接异常
# 连续失败3次会记录错误日志
⚠️ 统计数据获取失败 (错误次数: 1/3)
⚠️ 统计数据获取失败 (错误次数: 2/3)
❌ 监控服务连续失败 3 次
```

### 降级显示

数据库不可用时，显示空统计：
```
📈 交易记录:
   • 总交易数: 0
   • 今日新增: 0
   ...
⚡ 性能指标:
   • 数据库状态: ❌ 异常
```

### 线程安全

监控服务是线程安全的：
- 独立daemon线程运行
- 不阻塞主业务
- 自动资源清理

---

## 使用示例

### 示例1: 启动时显示一次统计

```python
from src.database import DatabaseManager, DatabaseMonitor

db_manager = DatabaseManager()
monitor = DatabaseMonitor(db_manager)

# 启动时显示一次
monitor.get_summary()

# 继续运行交易逻辑...
```

### 示例2: 定期后台监控

```python
# 每1分钟自动刷新统计
monitor = DatabaseMonitor(
    db_manager=db_manager,
    refresh_interval=60,
    auto_start=True
)

# 监控会在后台持续运行，定期在日志中输出统计
```

### 示例3: 手动控制

```python
monitor = DatabaseMonitor(db_manager, auto_start=False)

# 手动启动
monitor.start_monitoring()

# ... 运行一段时间 ...

# 手动停止
monitor.stop_monitoring()
```

### 示例4: 自定义阈值

```python
monitor = DatabaseMonitor(db_manager)

# 修改阈值
monitor.thresholds['max_open_positions'] = 3
monitor.thresholds['max_response_time_ms'] = 200

# 手动检查警告
stats = monitor.get_real_time_stats()
monitor.check_alerts(stats)
```

---

## 故障排查

### 问题1: 统计数据为0

**原因**: 数据表为空

**解决**: 等待交易机器人产生数据，或使用测试数据

### 问题2: 监控服务无法启动

**症状**: `start_monitoring()` 返回 False

**排查**:
1. 检查数据库连接: `db_manager.check_health()`
2. 查看日志中的错误信息
3. 确认环境变量已设置

### 问题3: 响应时间过长

**原因**: 数据表过大或索引缺失

**解决**:
1. 确认索引已创建（`initialize_database()` 会自动创建）
2. 增加刷新间隔: `refresh_interval=300`
3. 清理旧数据

### 问题4: 日志输出过多

**解决**: 增加刷新间隔
```python
# 从60秒改为5分钟
monitor = DatabaseMonitor(
    db_manager=db_manager,
    refresh_interval=300
)
```

---

## 最佳实践

### 1. Railway生产环境

```python
# 较长的刷新间隔，减少日志量
monitor = DatabaseMonitor(
    db_manager=db_manager,
    refresh_interval=300,  # 5分钟
    auto_start=True,
    enable_alerts=True
)
```

### 2. 本地开发环境

```python
# 较短的刷新间隔，快速调试
monitor = DatabaseMonitor(
    db_manager=db_manager,
    refresh_interval=30,  # 30秒
    auto_start=True,
    enable_alerts=True
)
```

### 3. 资源清理

```python
# 确保在退出时停止监控
try:
    await run_trading_bot()
finally:
    if monitor:
        monitor.stop_monitoring()
    if db_manager:
        db_manager.close_all_connections()
```

### 4. 日志级别控制

```python
# 只在INFO级别显示统计
logging.basicConfig(level=logging.INFO)

# 禁用DEBUG日志减少输出
logging.getLogger('src.database.monitor').setLevel(logging.INFO)
```

---

## 完整示例代码

查看 `examples/database_monitor_usage.py` 获取6个完整使用示例：

1. 一次性显示统计摘要
2. 后台监控模式
3. 自定义警告阈值
4. 与交易机器人整合
5. 手动控制监控
6. 缓存使用优化

---

## 技术规格

- **线程安全**: ✅ 使用daemon线程
- **资源开销**: 极低（缓存+优化查询）
- **错误恢复**: 自动重试机制
- **内存占用**: < 1MB
- **CPU占用**: < 0.1%（后台模式）

---

## 更新日志

### v1.0.0 (2025-01-15)
- ✅ 初始版本发布
- ✅ 实时统计功能
- ✅ 后台监控模式
- ✅ 智能警告系统
- ✅ 性能优化（缓存）
- ✅ 生产级错误处理

---

## 相关文档

- **数据库设置**: `docs/DATABASE_SETUP.md`
- **使用示例**: `examples/database_monitor_usage.py`
- **数据库测试**: `tests/test_database.py`

---

**准备好了吗？**

立即启用数据库监控，实时掌握您的交易系统状态！🚀
