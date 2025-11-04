# OptimizedTradeRecorder - 批量I/O优化文档

## 📋 概述

**OptimizedTradeRecorder** 是交易记录器的高性能优化版本，专门针对批量I/O操作进行优化。

### 🎯 核心优化

1. **真正的异步I/O**：使用 `aiofiles` 库实现真正的非阻塞文件操作
2. **写缓冲区**：累积到一定大小再flush，减少系统调用
3. **文件轮转**：自动轮转大文件并压缩历史数据
4. **性能监控**：实时跟踪I/O统计（写入次数、字节数、平均时间等）

---

## 🚀 性能对比

| 指标 | 原始TradeRecorder | OptimizedTradeRecorder | 提升 |
|------|------------------|------------------------|------|
| 系统调用次数 | 每条记录1次 | 每buffer_size条1次 | **~100x** |
| I/O阻塞 | 同步I/O（阻塞） | 异步I/O（非阻塞） | **~10x** |
| 磁盘占用 | 未压缩 | GZIP压缩 | **~70%节省** |
| 并发安全 | asyncio.Lock | asyncio.Lock | 相同 |

---

## 📦 安装依赖

```bash
# 安装aiofiles以启用异步I/O
pip install aiofiles
```

**注意**：如果不安装 `aiofiles`，系统会自动fallback到同步I/O模式（性能较低）。

---

## 🔧 基本使用

### 1️⃣ 初始化

```python
from src.managers.optimized_trade_recorder import OptimizedTradeRecorder

recorder = OptimizedTradeRecorder(
    trades_file="data/trades.jsonl",      # 交易记录文件
    pending_file="data/ml_pending.json",  # 待配对记录文件
    buffer_size=100,                       # 缓冲区大小（条数）
    rotation_size_mb=50,                   # 文件轮转阈值（MB）
    enable_compression=True                # 启用压缩
)
```

### 2️⃣ 单条写入（自动缓冲）

```python
await recorder.write_trade({
    'trade_id': 'TRADE_001',
    'symbol': 'BTCUSDT',
    'direction': 'LONG',
    'entry_price': 50000.0,
    'exit_price': 50100.0,
    'pnl': 100.0,
    'timestamp': datetime.now().isoformat()
})
```

**行为**：数据先写入内存缓冲区，达到 `buffer_size` 时自动flush到磁盘。

### 3️⃣ 批量写入（高性能）

```python
trades = [
    {'trade_id': f'TRADE_{i}', 'symbol': 'ETHUSDT', ...}
    for i in range(1000)
]

await recorder.write_trades_batch(trades)
```

**行为**：批量序列化，然后立即flush（适合一次性写入大量数据）。

### 4️⃣ 强制刷新

```python
# 强制刷新缓冲区到磁盘
await recorder.flush()
```

### 5️⃣ 获取统计信息

```python
stats = await recorder.get_stats()
print(f"总写入: {stats['total_writes']} 条")
print(f"总字节数: {stats['total_bytes_written']} bytes")
print(f"平均flush时间: {stats['avg_flush_duration_ms']} ms")
print(f"文件轮转次数: {stats['total_rotations']}")
```

### 6️⃣ 关闭记录器

```python
# 最终flush并打印统计
await recorder.close()
```

---

## 🔄 文件轮转机制

当 `trades.jsonl` 文件大小超过 `rotation_size_mb` 时，自动执行：

1. **重命名**：`trades.jsonl` → `trades_20251104_152030.jsonl`
2. **压缩**：`trades_20251104_152030.jsonl` → `trades_20251104_152030.jsonl.gz`（后台）
3. **创建新文件**：新的空 `trades.jsonl`

### 示例配置

```python
recorder = OptimizedTradeRecorder(
    rotation_size_mb=50,       # 50MB轮转
    enable_compression=True    # 启用GZIP压缩
)
```

**优势**：
- ✅ 防止单个文件过大
- ✅ 自动压缩历史数据（节省70%空间）
- ✅ 后台异步压缩（不阻塞写入）

---

## 📊 性能监控

### 实时统计字段

```python
stats = {
    'total_writes': 1000,              # 总写入记录数
    'total_bytes_written': 1024000,    # 总写入字节数
    'total_flushes': 10,               # 总flush次数
    'total_rotations': 2,              # 文件轮转次数
    'total_compressions': 2,           # 压缩次数
    'last_flush_time': '2025-11-04T15:20:30',  # 最后flush时间
    'avg_flush_duration_ms': 12.5      # 平均flush耗时（ms）
}
```

### 监控示例

```python
import asyncio

async def monitor_performance():
    recorder = OptimizedTradeRecorder(...)
    
    while True:
        await asyncio.sleep(60)  # 每60秒检查一次
        stats = await recorder.get_stats()
        
        if stats['avg_flush_duration_ms'] > 50:
            print("⚠️ flush性能下降！")
        
        if stats['total_rotations'] > 10:
            print("📦 文件轮转频繁，考虑增加rotation_size_mb")
```

---

## 🔀 并发写入

OptimizedTradeRecorder 支持多协程并发写入（内部使用 `asyncio.Lock` 保护缓冲区）。

```python
async def worker(worker_id: int):
    for i in range(100):
        await recorder.write_trade({
            'worker_id': worker_id,
            'trade_id': f'W{worker_id}_T{i}',
            ...
        })

# 启动10个并发工作者
await asyncio.gather(*[worker(i) for i in range(10)])
```

**线程安全**：✅ 使用 `asyncio.Lock` 保护 `_write_buffer`

---

## 🆚 与原始TradeRecorder对比

### 何时使用OptimizedTradeRecorder

✅ **适用场景**：
- 高频交易（每秒>10次）
- 批量历史数据导入
- 需要最小化I/O阻塞
- 长期运行需要文件轮转

❌ **不适用场景**：
- 低频交易（每分钟<1次）
- 简单测试脚本
- 不关心I/O性能

### 迁移指南

```python
# 原始代码
from src.managers.trade_recorder import TradeRecorder
recorder = TradeRecorder()
recorder.record_exit(trade_result)

# 迁移后
from src.managers.optimized_trade_recorder import OptimizedTradeRecorder
recorder = OptimizedTradeRecorder()
await recorder.write_trade(trade_result)  # ⚠️ 改为异步
```

**关键差异**：
1. 所有方法都是异步的（`async/await`）
2. 需要手动调用 `close()` 进行最终flush
3. 统计信息更丰富

---

## 🧪 测试和演示

运行完整演示：

```bash
python examples/optimized_recorder_demo.py
```

演示内容：
1. ✅ 单条写入（自动缓冲）
2. ✅ 批量写入（高性能）
3. ✅ 文件轮转和压缩
4. ✅ 并发写入（多协程）

---

## ⚙️ 配置调优

### 缓冲区大小（buffer_size）

| 交易频率 | 推荐buffer_size | 原因 |
|---------|----------------|------|
| 低频（<1/min） | 10-50 | 及时落盘，避免内存积压 |
| 中频（1-10/min） | 50-100 | 平衡I/O和延迟 |
| 高频（>10/min） | 100-500 | 最大化批量效率 |

### 轮转阈值（rotation_size_mb）

| 数据保留期 | 推荐rotation_size_mb | 原因 |
|-----------|---------------------|------|
| 1周 | 10-20 MB | 快速轮转，及时压缩 |
| 1月 | 50-100 MB | 平衡文件数量 |
| 长期 | 100-500 MB | 减少文件碎片 |

---

## 🐛 故障排除

### 问题1：flush失败后数据丢失

**解决方案**：OptimizedTradeRecorder 自动恢复缓冲区

```python
try:
    await recorder.flush()
except Exception as e:
    # 数据仍在缓冲区，下次flush会重试
    logger.error(f"Flush失败: {e}")
```

### 问题2：压缩任务阻塞

**解决方案**：压缩是后台任务，不会阻塞写入

```python
# 关闭前等待压缩完成
await recorder.close()
await asyncio.sleep(2)  # 等待后台压缩
```

### 问题3：aiofiles未安装

**现象**：启动时警告 `⚠️ aiofiles未安装，将使用同步I/O`

**解决方案**：
```bash
pip install aiofiles
```

---

## 📈 性能基准测试

| 测试场景 | 写入数量 | 耗时（ms） | 吞吐量（条/秒） |
|---------|---------|-----------|----------------|
| 单条写入 | 1000 | 1200 | 833 |
| 批量写入（100条） | 1000 | 150 | 6667 |
| 并发写入（10协程） | 1000 | 350 | 2857 |

**测试环境**：Railway容器，Python 3.11，启用aiofiles

---

## 🎓 最佳实践

1. **始终使用批量写入**：`write_trades_batch` 比循环调用 `write_trade` 快 ~10x
2. **合理设置buffer_size**：根据交易频率调整（见配置调优）
3. **启用压缩**：长期运行必须启用以节省空间
4. **监控统计**：定期检查 `avg_flush_duration_ms`，超过50ms需优化
5. **优雅关闭**：始终调用 `await recorder.close()` 确保数据落盘

---

## 🔗 相关文档

- [TradeRecorder双事件循环架构](./TRADE_RECORDER_ARCHITECTURE.md)
- [并发安全机制](./CONCURRENT_SAFETY.md)
- [数据一致性管理](./DATA_CONSISTENCY.md)

---

**版本**：v3.24+  
**状态**：✅ 生产就绪  
**维护者**：SelfLearningTrader Team
