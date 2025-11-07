# 🚀 系统优化实施计划

## 📋 概述

本文档提供**分步骤的代码优化方案**，确保安全、高效地完成系统重构。

---

## 🎯 阶段1：数据层统一（最高优先级）

### Step 1.1: 启用PostgreSQL作为唯一数据源

#### 修改`src/main.py`

**当前代码（第177-182行）：**
```python
# 🔥 v3.29+ 增强版交易記錄器（三层锁保护）
self.trade_recorder = EnhancedTradeRecorder(
    trades_file="data/trades.jsonl",  # ← 使用JSONL
    pending_file="data/pending_entries.json",
    buffer_size=10
)
logger.info("✅ 增强版交易記錄器初始化完成（v3.29+，三层锁保护）")
```

**优化后代码：**
```python
# 🔥 v4.0+ 统一PostgreSQL交易记录器
from src.database import DatabaseManager, TradingDataService, initialize_database

# 初始化数据库
if DatabaseConfig.is_database_configured():
    self.db_manager = DatabaseManager(
        min_connections=2,
        max_connections=10
    )
    
    # 初始化表结构
    initialize_database(self.db_manager)
    
    # 创建数据服务
    self.db_service = TradingDataService(self.db_manager)
    
    # 创建PostgreSQL版TradeRecorder
    self.trade_recorder = UnifiedTradeRecorder(
        db_service=self.db_service,
        model_scorer=self.model_scorer,
        model_initializer=self.model_initializer
    )
    logger.info("✅ 统一PostgreSQL交易記錄器初始化完成（v4.0+）")
else:
    logger.warning("⚠️ 数据库未配置，使用降级模式")
    self.trade_recorder = None
```

---

### Step 1.2: 创建UnifiedTradeRecorder

**新建文件：`src/managers/unified_trade_recorder.py`**

```python
"""
UnifiedTradeRecorder v4.0 - 统一PostgreSQL交易记录器

职责：
1. 所有交易数据存储到PostgreSQL
2. ML特征收集和管理
3. 模型重训练触发
4. 性能指标追踪

替代：
- src/managers/trade_recorder.py (JSONL版)
- src/managers/optimized_trade_recorder.py (异步I/O版)
- src/core/trade_recorder.py (SQLite版)
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from src.database.service import TradingDataService
from src.ml.feature_engine import FeatureEngine

logger = logging.getLogger(__name__)


class UnifiedTradeRecorder:
    """
    统一交易记录器（PostgreSQL版本）
    
    特性：
    - 单一数据源（PostgreSQL）
    - 异步批量操作
    - 自动ML特征收集
    - 模型重训练管理
    """
    
    def __init__(
        self,
        db_service: TradingDataService,
        model_scorer=None,
        model_initializer=None
    ):
        """
        初始化统一交易记录器
        
        Args:
            db_service: PostgreSQL数据服务
            model_scorer: 模型评分器（可选）
            model_initializer: 模型初始化器（可选）
        """
        self.db_service = db_service
        self.model_scorer = model_scorer
        self.model_initializer = model_initializer
        
        # ML特征引擎
        self.feature_engine = FeatureEngine()
        
        # 模型重训练计数器
        self.trades_since_last_retrain = 0
        self.retrain_interval = 50
        
        # 统计信息
        self.stats = {
            'total_entries': 0,
            'total_exits': 0,
            'total_features_collected': 0,
            'total_retrains_triggered': 0
        }
        
        logger.info("✅ UnifiedTradeRecorder初始化完成（PostgreSQL）")
    
    def record_entry(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        leverage: int,
        signal_data: Dict,
        klines_data: Dict
    ) -> Optional[int]:
        """
        记录开仓
        
        Args:
            symbol: 交易对
            direction: 方向（LONG/SHORT）
            entry_price: 入场价
            quantity: 数量
            leverage: 杠杆
            signal_data: 信号数据
            klines_data: K线数据
            
        Returns:
            交易ID（PostgreSQL主键）
        """
        try:
            # 提取ML特征
            ml_features = self.feature_engine.build_full_features(
                signal_data,
                klines_data
            )
            
            # 构建交易记录
            trade_data = {
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'quantity': quantity,
                'leverage': leverage,
                'entry_timestamp': datetime.utcnow().isoformat() + 'Z',
                'status': 'OPEN',
                
                # 策略信息
                'strategy': signal_data.get('strategy', 'ICT_SMC'),
                'confidence': signal_data.get('confidence'),
                'win_probability': signal_data.get('win_probability'),
                
                # ML特征（44个）
                **ml_features,
                
                # 元数据
                'metadata': {
                    'signal': signal_data,
                    'collected_at': datetime.utcnow().isoformat()
                }
            }
            
            # 保存到PostgreSQL
            trade_id = self.db_service.save_trade(trade_data)
            
            if trade_id:
                self.stats['total_entries'] += 1
                self.stats['total_features_collected'] += 1
                logger.info(f"✅ 开仓记录已保存到PostgreSQL，ID: {trade_id}")
                return trade_id
            else:
                logger.error("❌ 保存开仓记录失败")
                return None
                
        except Exception as e:
            logger.error(f"❌ 记录开仓失败: {e}")
            logger.exception("详细错误:")
            return None
    
    def record_exit(
        self,
        trade_id: int,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str
    ) -> bool:
        """
        记录平仓
        
        Args:
            trade_id: 交易ID（PostgreSQL主键）
            exit_price: 出场价
            pnl: 盈亏金额
            pnl_pct: 盈亏百分比
            reason: 平仓原因
            
        Returns:
            是否成功
        """
        try:
            # 更新交易状态
            success = self.db_service.update_trade_status(
                trade_id=trade_id,
                status='CLOSED',
                exit_price=exit_price,
                pnl=pnl,
                pnl_pct=pnl_pct
            )
            
            if success:
                self.stats['total_exits'] += 1
                self.trades_since_last_retrain += 1
                
                logger.info(f"✅ 平仓记录已更新，ID: {trade_id}, PnL: {pnl_pct:.2f}%")
                
                # 检查是否需要重训练
                self._check_retrain()
                
                return True
            else:
                logger.error(f"❌ 更新平仓记录失败，ID: {trade_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 记录平仓失败: {e}")
            return False
    
    def _check_retrain(self):
        """检查是否需要触发模型重训练"""
        if self.trades_since_last_retrain >= self.retrain_interval:
            if self.model_initializer:
                logger.info(f"🔄 触发模型重训练（{self.trades_since_last_retrain}笔交易）")
                
                # 异步触发重训练
                try:
                    import asyncio
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.model_initializer.retrain_if_needed())
                    
                    self.trades_since_last_retrain = 0
                    self.stats['total_retrains_triggered'] += 1
                except Exception as e:
                    logger.error(f"❌ 触发重训练失败: {e}")
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            'db_stats': self.db_service.get_statistics()
        }
```

---

### Step 1.3: 删除旧版TradeRecorder

**需要删除的文件：**
```bash
rm src/managers/optimized_trade_recorder.py
rm src/core/trade_recorder.py
mv src/managers/trade_recorder.py src/managers/trade_recorder.py.backup
```

**清理导入：**
```bash
# 全局搜索并替换
find src -name "*.py" -exec sed -i 's/from src.managers.optimized_trade_recorder/# REMOVED/g' {} +
find src -name "*.py" -exec sed -i 's/from src.core.trade_recorder/# REMOVED/g' {} +
```

---

### Step 1.4: 合并技术指标引擎

**保留：** `src/core/elite/technical_indicator_engine.py`  
**删除：** `src/technical/elite_technical_engine.py`

**更新所有导入：**

```python
# 旧导入（需要全局替换）
from src.technical.elite_technical_engine import EliteTechnicalEngine

# 新导入
from src.core.elite.technical_indicator_engine import EliteTechnicalEngine
```

**全局替换命令：**
```bash
find src -name "*.py" -exec sed -i 's/from src.technical.elite_technical_engine/from src.core.elite.technical_indicator_engine/g' {} +
```

---

## 🎯 阶段2：WebSocket系统优化

### Step 2.1: 创建统一WebSocketOrchestrator

**新建文件：`src/core/websocket/orchestrator.py`**

```python
"""
WebSocketOrchestrator v4.0 - 统一WebSocket管理器

职责：
1. 统一管理所有WebSocket连接
2. 自动重连和心跳
3. 数据质量监控
4. Feed生命周期管理

替代：
- optimized_base_feed.py
- advanced_feed_manager.py
- 部分websocket_manager.py的功能
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class WebSocketOrchestrator:
    """
    统一WebSocket协调器
    
    特性：
    - 统一连接管理
    - 自动重连机制
    - 心跳监控
    - Feed动态注册
    """
    
    def __init__(self, max_reconnect_attempts: int = 5):
        """
        初始化WebSocket协调器
        
        Args:
            max_reconnect_attempts: 最大重连次数
        """
        self.feeds: Dict[str, 'BaseFeed'] = {}
        self.max_reconnect_attempts = max_reconnect_attempts
        
        # 统一监控
        self.stats = {
            'total_connections': 0,
            'total_reconnections': 0,
            'total_messages': 0,
            'active_feeds': 0
        }
        
        logger.info("✅ WebSocketOrchestrator初始化完成")
    
    def register_feed(self, name: str, feed: 'BaseFeed'):
        """注册Feed"""
        self.feeds[name] = feed
        self.stats['active_feeds'] += 1
        logger.info(f"📡 注册Feed: {name}")
    
    async def start_all(self):
        """启动所有Feeds"""
        tasks = [feed.start() for feed in self.feeds.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all(self):
        """停止所有Feeds"""
        tasks = [feed.stop() for feed in self.feeds.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
```

---

## 🎯 阶段3：配置和日志统一

### Step 3.1: 合并DatabaseConfig到Config

**修改`src/config.py`：**

```python
class Config:
    """统一配置类"""
    
    # ==================== Binance配置 ====================
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
    
    # ==================== 数据库配置 ====================
    # 🔥 v4.0+ 合并DatabaseConfig
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    DATABASE_PUBLIC_URL = os.getenv("DATABASE_PUBLIC_URL", "")
    
    # 连接池配置
    DB_MIN_CONNECTIONS = int(os.getenv("DB_MIN_CONNECTIONS", "2"))
    DB_MAX_CONNECTIONS = int(os.getenv("DB_MAX_CONNECTIONS", "10"))
    DB_CONNECTION_TIMEOUT = int(os.getenv("DB_CONNECTION_TIMEOUT", "30"))
    
    # 查询配置
    DB_QUERY_TIMEOUT = int(os.getenv("DB_QUERY_TIMEOUT", "30"))
    DB_BATCH_SIZE = int(os.getenv("DB_BATCH_SIZE", "1000"))
    
    # ==================== 其他配置 ====================
    # ... 现有配置保持不变 ...
    
    @staticmethod
    def get_database_url() -> Optional[str]:
        """获取数据库URL（优先使用内部URL）"""
        return Config.DATABASE_URL or Config.DATABASE_PUBLIC_URL
    
    @staticmethod
    def is_database_configured() -> bool:
        """检查数据库是否已配置"""
        return bool(Config.get_database_url())
```

**删除文件：**
```bash
rm src/database/config.py
```

**更新导入：**
```python
# 旧导入
from src.database.config import DatabaseConfig

# 新导入
from src.config import Config
```

---

### Step 3.2: 全面使用SmartLogger

**创建统一日志工厂：**

**新建文件：`src/utils/logger_factory.py`**

```python
"""
Logger Factory v4.0 - 统一日志创建

确保所有模块都使用SmartLogger
"""

from src.utils.smart_logger import create_smart_logger


def get_logger(name: str, **kwargs):
    """
    获取统一配置的logger
    
    Args:
        name: logger名称（通常使用__name__）
        **kwargs: SmartLogger额外参数
        
    Returns:
        配置好的SmartLogger实例
    """
    # 默认配置
    default_config = {
        'rate_limit_window': 2.0,
        'enable_aggregation': True,
        'enable_structured': False
    }
    
    # 合并用户配置
    config = {**default_config, **kwargs}
    
    return create_smart_logger(name, **config)
```

**全局替换：**
```bash
# 替换所有标准logging为SmartLogger
find src -name "*.py" -exec sed -i 's/import logging$/from src.utils.logger_factory import get_logger/g' {} +
find src -name "*.py" -exec sed -i 's/logger = logging.getLogger(__name__)/logger = get_logger(__name__)/g' {} +
```

---

## 📊 验证清单

### 阶段1验证
- [ ] PostgreSQL连接正常
- [ ] 交易记录成功保存到数据库
- [ ] ML特征正确提取
- [ ] 旧版recorder已删除
- [ ] 所有导入已更新
- [ ] 单元测试通过

### 阶段2验证
- [ ] WebSocket连接稳定
- [ ] 实时数据正常接收
- [ ] 重连机制工作正常
- [ ] Feed数量减少

### 阶段3验证
- [ ] 配置加载正常
- [ ] 日志输出一致
- [ ] 性能监控正常

---

## 🎯 回退计划

### 如果出现问题

1. **立即回退：**
```bash
git checkout HEAD~1
```

2. **恢复备份：**
```bash
cp src/managers/trade_recorder.py.backup src/managers/trade_recorder.py
```

3. **重启workflow：**
```bash
# Railway会自动重新部署
```

---

## 📈 预期改进

| 指标 | 改进 |
|------|------|
| 代码行数 | ↓ 14,752行 (34%) |
| 文件数 | ↓ 38个 (33%) |
| 类数量 | ↓ 46个 (33%) |
| 启动时间 | ↓ 30% |
| 内存使用 | ↓ 25% |
| 数据一致性 | ↑ 100% |

---

**准备好开始优化了吗？**

建议从阶段1开始，完成后再进行阶段2和3。每个阶段完成后都要进行充分测试。
