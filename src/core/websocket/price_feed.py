"""
🔥 PriceFeed v5.0 - bookTicker即时价格流（统一架构版）
职责：订阅Binance @bookTicker WebSocket，提供零延迟最优买卖价

改进（v5.0）：
- 继承UnifiedWebSocketFeed - 单一心跳机制
- 删除PriceFeed自有的message_queue bug
- 简化消息处理逻辑
"""

import asyncio
try:
    import orjson as json
except ImportError:
    import json
from typing import Dict, List, Optional, Any

try:
    import websockets  # type: ignore
except ImportError:
    websockets = None  # type: ignore

from src.utils.logger_factory import get_logger
from .unified_feed import UnifiedWebSocketFeed

logger = get_logger(__name__)


class PriceFeed(UnifiedWebSocketFeed):
    """
    🔥 PriceFeed v5.0 - Binance bookTicker WebSocket监控器（统一架构版）
    
    职责：
    1. 订阅@bookTicker（即时最优买卖价）
    2. 缓存即时价格数据（bid/ask/spread）
    3. 心跳监控 + 自动重连（由父类负责）
    4. 计算流动性指标
    
    优势：
    - 零延迟价格更新（vs REST 100-200ms）
    - 提供买卖价差数据（spread_bps）
    - 减少REST ticker API调用
    
    数据格式：
    {
        'symbol': 'BTCUSDT',
        'bid': 67000.0,          # 最优买价
        'ask': 67001.0,          # 最优卖价
        'bid_qty': 1.234,        # 买价数量
        'ask_qty': 0.567,        # 卖价数量
        'spread_bps': 1.49,      # 价差（基点）
        'mid_price': 67000.5,    # 中间价
        'server_timestamp': 1730177520000,  # 服务器时间
        'local_timestamp': 1730177520023,   # 本地接收时间
        'latency_ms': 23         # 网络延迟
    }
    """
    
    def __init__(self, symbols: List[str], shard_id: int = 0):
        """
        初始化PriceFeed
        
        Args:
            symbols: 交易对列表
            shard_id: 分片ID（用于追踪）
        """
        self.symbols = [s.lower() for s in symbols if s]
        self.shard_id = shard_id
        self.price_cache: Dict[str, Dict] = {}  # {symbol: price_data}
        
        # 构建WebSocket URL
        streams = "/".join([f"{symbol}@bookTicker" for symbol in self.symbols])
        url = f"wss://fstream.binance.com/stream?streams={streams}"
        
        # 调用父类初始化
        super().__init__(url=url, feed_name=f"PriceFeed-Shard{shard_id}")
        
        logger.info("=" * 80)
        logger.info(f"✅ PriceFeed Shard{shard_id} 初始化完成（v5.0 统一架构版）")
        logger.info(f"   📊 监控币种数量: {len(self.symbols)}")
        logger.info(f"   📡 数据源: bookTicker（即时买卖价）")
        logger.info(f"   🔄 架构: Producer-Consumer + 统一心跳")
        logger.info("=" * 80)
    
    async def on_connect(self, ws) -> None:
        """连接成功后的回调"""
        logger.debug(f"✅ {self.name} WebSocket已连接 ({len(self.symbols)}个币种)")
    
    async def process_message(self, raw_msg: str) -> None:
        """
        处理单条bookTicker消息
        
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
            
            # 合并流数据格式: {"stream": "btcusdt@bookTicker", "data": {...}}
            if 'data' in data and data['data'] is not None:
                self._update_price(data['data'])
        
        except json.JSONDecodeError:
            logger.warning(f"⚠️ {self.name} JSON解析失败")
        
        except TypeError as e:
            logger.warning(f"⚠️ {self.name} 消息格式错误（NoneType）: {e}")
        
        except KeyError as e:
            logger.warning(f"⚠️ {self.name} 消息格式错误（缺少字段）: {e}")
        
        except Exception as e:
            logger.error(f"❌ {self.name} 消息处理异常: {e}")
    
    def _update_price(self, data: dict):
        """
        更新价格缓存（bookTicker数据）
        
        Args:
            data: bookTicker数据
        """
        try:
            symbol = data.get('s', '').lower()
            if not symbol or symbol not in self.symbols:
                return
            
            # 获取时间戳
            server_ts = self.get_server_timestamp_ms(data, 'T')  # 交易时间
            local_ts = self.get_local_timestamp_ms()
            latency_ms = self.calculate_latency_ms(server_ts, local_ts)
            
            # 解析价格数据
            bid = float(data['b'])
            ask = float(data['a'])
            bid_qty = float(data['B'])
            ask_qty = float(data['A'])
            
            # 计算中间价和价差
            mid_price = (bid + ask) / 2
            spread = ask - bid
            spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0
            
            # 更新缓存
            self.price_cache[symbol] = {
                'symbol': data.get('s'),
                'bid': bid,
                'ask': ask,
                'bid_qty': bid_qty,
                'ask_qty': ask_qty,
                'spread_bps': spread_bps,
                'mid_price': mid_price,
                'server_timestamp': server_ts,
                'local_timestamp': local_ts,
                'latency_ms': latency_ms,
                'shard_id': self.shard_id
            }
            
            logger.debug(
                f"💰 {symbol.upper()} 价格更新: "
                f"bid={bid}, ask={ask}, spread={spread_bps:.2f}bps, "
                f"latency={latency_ms}ms"
            )
        
        except Exception as e:
            logger.error(f"❌ {self.name} 解析price失败: {e}")
    
    # ==================== 数据查询接口 ====================
    
    def get_price(self, symbol: str) -> Optional[Dict]:
        """
        获取即时价格数据
        
        Args:
            symbol: 交易对
        
        Returns:
            价格数据，或None
        """
        return self.price_cache.get(symbol.lower())
    
    def get_mid_price(self, symbol: str) -> Optional[float]:
        """
        获取中间价
        
        Args:
            symbol: 交易对
        
        Returns:
            中间价，或None
        """
        price_data = self.get_price(symbol)
        return price_data['mid_price'] if price_data else None
    
    def get_spread_bps(self, symbol: str) -> Optional[float]:
        """
        获取买卖价差（基点）
        
        Args:
            symbol: 交易对
        
        Returns:
            价差（基点），或None
        """
        price_data = self.get_price(symbol)
        return price_data['spread_bps'] if price_data else None
    
    def get_all_prices(self) -> Dict[str, Dict]:
        """
        获取所有币种的价格数据
        
        Returns:
            所有价格数据的字典
        """
        return self.price_cache.copy()
    
    def get_stats(self) -> Dict:
        """
        获取统计数据
        
        Returns:
            统计数据字典
        """
        base_stats = super().get_stats()
        return {
            **base_stats,
            'cached_symbols': len(self.price_cache),
            'shard_id': self.shard_id
        }
