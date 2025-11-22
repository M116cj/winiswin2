# ConcurrentDictManager 集成指南

## 概述

`ConcurrentDictManager` 提供线程安全的字典操作，适用于WebSocket组件中的缓存和状态管理。

## 集成示例：KlineFeed

### 步骤1：导入并初始化

```python
from src.core.concurrent_dict_manager import ConcurrentDictManager

class KlineFeed(BaseFeed):
    def __init__(self, symbols: List[str], interval: str = "1m", shard_id: int = 0, max_history: int = 100):
        super().__init__(name=f"KlineFeed-Shard{shard_id}")
        
        self.symbols = [s.lower() for s in symbols if s]
        self.interval = interval
        self.shard_id = shard_id
        self.max_history = max_history
        
        # 🔥 使用ConcurrentDictManager替代原生dict
        self.kline_cache = ConcurrentDictManager[str, List[Dict]](
            name=f"KlineCache-Shard{shard_id}",
            enable_auto_cleanup=True,
            cleanup_interval=300,  # 每5分钟清理一次
            max_size=1000  # 最多缓存1000个交易对
        )
        
        self.ws_task: Optional[asyncio.Task] = None
```

### 步骤2：修改读写操作

```python
# 原代码：
def _update_kline(self, kline_data: Dict):
    symbol = kline_data.get('s', '').lower()
    if symbol not in self.kline_cache:
        self.kline_cache[symbol] = []
    self.kline_cache[symbol].append(kline_data)

# 修改后：
def _update_kline(self, kline_data: Dict):
    symbol = kline_data.get('s', '').lower()
    
    # 获取现有缓存
    existing = self.kline_cache.get(symbol, default=[])
    
    # 追加新数据
    existing.append(kline_data)
    
    # 限制最大长度
    if len(existing) > self.max_history:
        existing = existing[-self.max_history:]
    
    # 更新缓存
    self.kline_cache.set(symbol, existing)
```

```python
# 原代码：
def get_latest_kline(self, symbol: str) -> Optional[Dict]:
    klines = self.kline_cache.get(symbol.lower())
    return klines[-1] if klines else None

# 修改后：
def get_latest_kline(self, symbol: str) -> Optional[Dict]:
    klines = self.kline_cache.get(symbol.lower(), default=[])
    return klines[-1] if klines else None
```

### 步骤3：生命周期管理

```python
class KlineFeed(BaseFeed):
    async def start(self):
        """启动Feed"""
        if not self.symbols:
            logger.warning(f"⚠️ {self.name}: 无幣種，未啟動")
            return
        
        self.running = True
        logger.info(f"🚀 {self.name} 啟動中... ({len(self.symbols)} 個幣種)")
        
        # 🔥 启动自动清理任务
        await self.kline_cache.start_auto_cleanup()
        
        # 启动心跳监控
        await self._start_heartbeat_monitor()
        
        # 启动WebSocket监听
        self.ws_task = asyncio.create_task(self._listen_klines())
        
        logger.info(f"✅ {self.name} 已啟動")
    
    async def stop(self):
        """停止Feed"""
        logger.info(f"🛑 正在停止 {self.name}...")
        self.running = False
        
        # 停止WebSocket任务
        if self.ws_task:
            self.ws_task.cancel()
            try:
                await self.ws_task
            except asyncio.CancelledError:
                pass
        
        # 🔥 停止自动清理任务
        await self.kline_cache.stop_auto_cleanup()
        
        # 停止心跳监控
        await self._stop_heartbeat_monitor()
        
        logger.info(f"✅ {self.name} 已停止")
```

### 步骤4：统计信息集成

```python
def get_stats(self) -> Dict:
    """获取Feed统计信息"""
    base_stats = super().get_stats()
    
    # 🔥 集成ConcurrentDictManager统计
    cache_stats = self.kline_cache.get_stats()
    
    return {
        **base_stats,
        'cache': cache_stats,
        'cached_symbols': cache_stats['size'],
        'cache_hit_rate': cache_stats['hit_rate']
    }
```

## 其他组件集成

### PriceFeed

```python
class PriceFeed(BaseFeed):
    def __init__(self, symbols: List[str], shard_id: int = 0):
        super().__init__(name=f"PriceFeed-Shard{shard_id}")
        
        # 使用ConcurrentDictManager
        self.price_cache = ConcurrentDictManager[str, Dict](
            name=f"PriceCache-Shard{shard_id}",
            enable_auto_cleanup=True,
            cleanup_interval=60,
            max_size=500
        )
```

### AccountFeed

```python
class AccountFeed(BaseFeed):
    def __init__(self, binance_client: Any, recv_timeout: int = 120):
        super().__init__(name="AccountFeed")
        
        # 使用ConcurrentDictManager
        self.position_cache = ConcurrentDictManager[str, Dict](
            name="PositionCache",
            enable_auto_cleanup=False,  # 持仓数据不需要自动过期
            max_size=100
        )
        
        self.account_data = ConcurrentDictManager[str, Any](
            name="AccountData",
            enable_auto_cleanup=False
        )
```

## TTL使用示例

```python
# 设置带TTL的缓存（60秒后自动过期）
self.cache.set("BTCUSDT", price_data, ttl=60)

# 批量设置带TTL
self.cache.update_many({
    "BTCUSDT": btc_data,
    "ETHUSDT": eth_data
}, ttl=60)
```

## 异步操作示例

```python
async def update_price_async(self, symbol: str, price_data: Dict):
    """异步更新价格"""
    await self.price_cache.set_async(symbol, price_data, ttl=60)

async def get_price_async(self, symbol: str) -> Optional[Dict]:
    """异步获取价格"""
    return await self.price_cache.get_async(symbol)
```

## 性能优化建议

1. **合理设置max_size**：根据实际使用情况设置最大条目数，避免内存溢出
2. **选择性启用自动清理**：只对需要TTL的缓存启用自动清理
3. **调整cleanup_interval**：根据过期频率调整清理间隔
4. **批量操作**：使用`update_many`和`get_many`减少锁竞争

## 迁移检查清单

- [ ] 导入ConcurrentDictManager
- [ ] 替换原生dict初始化
- [ ] 修改所有读操作（使用`.get(key, default=...)`）
- [ ] 修改所有写操作（使用`.set(key, value, ttl=...)`）
- [ ] 在`start()`中启动自动清理
- [ ] 在`stop()`中停止自动清理
- [ ] 集成统计信息到`get_stats()`
- [ ] 测试并发访问场景
