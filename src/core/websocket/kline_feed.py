"""
🔥 KlineFeed v5.0 - 即时K线数据流（统一架构版）
职责：订阅Binance @kline_1m WebSocket，专注消息处理

改进（v5.0）：
- 继承UnifiedWebSocketFeed - 单一心跳机制
- 完全删除ApplicationLevelHeartbeatMonitor
- 简化消息处理逻辑
"""

import asyncio
import time
try:
    import orjson as json
except ImportError:
    import json
from typing import Dict, List, Optional

try:
    import websockets  # type: ignore
except ImportError:
    websockets = None  # type: ignore

from src.utils.logger_factory import get_logger
from src.core.concurrent_dict_manager import ConcurrentDictManager
from .unified_feed import UnifiedWebSocketFeed

logger = get_logger(__name__)


class KlineFeed(UnifiedWebSocketFeed):
    """
    🔥 KlineFeed v5.0 - Binance K线WebSocket监控器（统一架构版）
    
    职责：
    1. 订阅@kline_1m（K线数据）
    2. 缓存最新闭盘K线数据（ConcurrentDictManager）
    3. 提供即时K线数据查询
    4. 时间戳标准化
    
    **连接管理（由父类UnifiedWebSocketFeed负责）**：
    - 单一心跳机制：Ping Interval=20s, Ping Timeout=20s
    - 自动重连：指数退避（5s → 300s）
    
    K线数据格式：
    {
        'symbol': 'BTCUSDT',
        'open': 67000.0,
        'high': 67500.0,
        'low': 66800.0,
        'close': 67200.0,
        'volume': 1234.56,
        'quote_volume': 82904800.0,
        'trades': 12345,
        'server_timestamp': 1730177520000,  # Binance服务器时间（毫秒）
        'local_timestamp': 1730177520023,   # 本地接收时间（毫秒）
        'latency_ms': 23,                   # 网络延迟（毫秒）
        'close_time': 1730177579999,        # K线闭盘时间
        'shard_id': 0                       # 分片ID
    }
    """
    
    def __init__(self, symbols: List[str], interval: str = "1m", shard_id: int = 0, max_history: int = 4000):
        """
        初始化KlineFeed
        
        Args:
            symbols: 交易对列表（例如：['BTCUSDT', 'ETHUSDT']）
            interval: K线周期（默认1m）
            shard_id: 分片ID（用于追踪，默认0）
            max_history: 最大历史K线数量（默认4000）
        """
        self.symbols = [s.lower() for s in symbols if s]
        self.interval = interval
        self.shard_id = shard_id
        self.max_history = max_history
        
        # K线缓存
        self.kline_cache = ConcurrentDictManager[str, List[Dict]](
            name=f"KlineCache-Shard{shard_id}",
            enable_auto_cleanup=True,
            cleanup_interval=300,  # 每5分钟清理一次
            max_size=1000  # 最多缓存1000个交易对
        )
        
        # 构建WebSocket URL
        streams = "/".join([f"{symbol}@kline_{interval}" for symbol in self.symbols])
        url = f"wss://fstream.binance.com/stream?streams={streams}"
        
        # 调用父类初始化
        super().__init__(url=url, feed_name=f"KlineFeed-Shard{shard_id}")
        
        logger.info("=" * 80)
        logger.info(f"✅ KlineFeed Shard{shard_id} 初始化完成（v5.0 统一架构版）")
        logger.info(f"   📊 监控币种数量: {len(self.symbols)}")
        logger.info(f"   ⏱️  K线周期: {interval}")
        logger.info(f"   📦 历史缓存大小: {max_history}根K线")
        logger.info(f"   🔌 WebSocket模式: 合并流（单一连线）")
        logger.info(f"   ⚡ 架构模式: 统一心跳 + Producer-Consumer")
        logger.info("=" * 80)
    
    async def on_connect(self, ws) -> None:
        """连接成功后的回调"""
        # 启动缓存自动清理
        await self.kline_cache.start_auto_cleanup()
        logger.debug(f"✅ {self.name} WebSocket已连接 ({len(self.symbols)}个币种)")
    
    async def process_message(self, raw_msg: str) -> None:
        """
        处理单条K线消息
        
        Args:
            raw_msg: 原始WebSocket消息（JSON字符串）
        """
        try:
            # 检查消息有效性
            if not raw_msg:
                logger.debug(f"⚠️ {self.name} 收到空消息，跳过")
                return
            
            data = json.loads(raw_msg)
            
            # 防御性检查
            if data is None:
                logger.debug(f"⚠️ {self.name} JSON解析结果为None，跳过")
                return
            
            if not isinstance(data, dict):
                logger.warning(f"⚠️ {self.name} 消息格式非字典: {type(data)}")
                return
            
            # 合并流数据格式: {"stream": "btcusdt@kline_1m", "data": {...}}
            if 'data' in data and data['data'] is not None and isinstance(data['data'], dict):
                if data['data'].get('e') == 'kline':
                    self._update_kline(data['data']['k'])
        
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ {self.name} JSON解析失败: {e}")
            if 'json_errors' not in self.stats:
                self.stats['json_errors'] = 0
            self.stats['json_errors'] += 1
        
        except TypeError as e:
            logger.warning(f"⚠️ {self.name} 消息格式错误（NoneType）: {e}")
            if 'format_errors' not in self.stats:
                self.stats['format_errors'] = 0
            self.stats['format_errors'] += 1
        
        except KeyError as e:
            logger.warning(f"⚠️ {self.name} 消息格式错误（缺少字段）: {e}")
            if 'format_errors' not in self.stats:
                self.stats['format_errors'] = 0
            self.stats['format_errors'] += 1
        
        except Exception as e:
            logger.error(f"❌ {self.name} 消息处理异常: {e}")
            if 'processing_errors' not in self.stats:
                self.stats['processing_errors'] = 0
            self.stats['processing_errors'] += 1
    
    def _update_kline(self, kline: dict):
        """
        更新K线缓存（仅闭盘K线）
        
        Args:
            kline: K线数据（来自Binance WebSocket）
        """
        symbol = kline.get('s', '').lower()
        if not symbol or symbol not in self.symbols:
            return
        
        # 仅保存闭盘K线（is_final=True）
        if kline.get('x', False):  # x = is_final
            # 使用事件时间计算延迟（最准确）
            event_ts = int(kline.get('E', 0))  # WebSocket事件时间
            open_ts = int(kline['t'])  # K线开盘时间（用于时间对齐聚合）
            local_ts = int(time.time() * 1000)  # 本地时间（毫秒）
            latency_ms = local_ts - event_ts if event_ts > 0 else 0  # 真实网络延迟
            
            kline_data = {
                'symbol': kline.get('s'),
                'timestamp': open_ts,                 # K线开盘时间（用于聚合时间对齐）
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v']),
                'quote_volume': float(kline['q']),
                'trades': int(kline['n']),
                'server_timestamp': event_ts,         # WebSocket事件时间（用于延迟计算）
                'local_timestamp': local_ts,          # 本地接收时间（毫秒）
                'latency_ms': latency_ms,             # 真实网络延迟
                'close_time': int(kline['T']),       # K线闭盘时间
                'shard_id': self.shard_id             # 分片ID
            }
            
            # 维护K线历史列表（保留最近max_history根）
            if symbol not in self.kline_cache:
                self.kline_cache[symbol] = []
            
            self.kline_cache[symbol].append(kline_data)
            
            # 保留最近max_history根K线
            if len(self.kline_cache[symbol]) > self.max_history:
                self.kline_cache[symbol] = self.kline_cache[symbol][-self.max_history:]
            
            logger.debug(
                f"📊 {symbol.upper()} K线更新: "
                f"O={kline['o']}, H={kline['h']}, L={kline['l']}, C={kline['c']}, "
                f"latency={latency_ms}ms, 历史={len(self.kline_cache[symbol])}根, shard={self.shard_id}"
            )
    
    # ==================== 数据查询接口 ====================
    
    def get_latest_kline(self, symbol: str) -> Optional[Dict]:
        """
        获取最新K线数据
        
        Args:
            symbol: 交易对
        
        Returns:
            最新K线数据，或None
        """
        klines = self.kline_cache.get(symbol.lower())
        if klines and len(klines) > 0:
            return klines[-1]
        return None
    
    def get_kline_history(self, symbol: str) -> List[Dict]:
        """
        获取K线历史数据
        
        Args:
            symbol: 交易对
        
        Returns:
            K线历史列表（按时间戳升序）
        """
        return self.kline_cache.get(symbol.lower(), []).copy()
    
    def get_all_klines(self) -> Dict[str, List[Dict]]:
        """
        获取所有币种的K线历史
        
        Returns:
            所有K线历史数据的字典
        """
        return {symbol: klines.copy() for symbol, klines in self.kline_cache.items()}
    
    def seed_history(self, symbol: str, klines: List[Dict]):
        """
        预填充K线历史（用于启动时预热缓存）
        
        Args:
            symbol: 交易对
            klines: K线历史列表（按时间戳升序）
        """
        symbol = symbol.lower()
        if symbol not in self.symbols:
            logger.warning(f"⚠️ {symbol} 不在监控列表中，跳过预填充")
            return
        
        # 保留最近max_history根K线
        self.kline_cache[symbol] = klines[-self.max_history:] if len(klines) > self.max_history else klines.copy()
        logger.info(f"✅ {symbol.upper()} 预填充 {len(self.kline_cache[symbol])} 根K线历史")
    
    def has_sufficient_history(self, symbol: str, min_count: int = 60) -> bool:
        """
        检查是否有足够的K线历史
        
        Args:
            symbol: 交易对
            min_count: 最小K线数量（默认60，用于聚合1h）
        
        Returns:
            True如果历史数据足够
        """
        klines = self.kline_cache.get(symbol.lower(), [])
        return len(klines) >= min_count
    
    def get_stats(self) -> Dict:
        """获取统计数据"""
        base_stats = super().get_stats()
        return {
            **base_stats,
            'cached_symbols': len(self.kline_cache),
            'total_symbols': len(self.symbols),
            'shard_id': self.shard_id,
            'connection_mode': 'combined_stream'
        }
    
    async def stop(self):
        """停止KlineFeed"""
        logger.info(f"⏸️  {self.name} 停止中...")
        
        # 停止缓存自动清理
        await self.kline_cache.stop_auto_cleanup()
        
        # 调用父类stop()
        await super().stop()
        
        logger.info(f"✅ {self.name} 已停止")
