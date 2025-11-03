"""
PriceFeed v3.17.2+ - bookTicker即時價格流
職責：訂閱Binance @bookTicker WebSocket，提供零延遲最優買賣價
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
import time

try:
    import websockets  # type: ignore
except ImportError:
    websockets = None  # type: ignore

from src.core.websocket.base_feed import BaseFeed

logger = logging.getLogger(__name__)


class PriceFeed(BaseFeed):
    """
    PriceFeed - Binance bookTicker WebSocket監控器
    
    職責：
    1. 訂閱@bookTicker（即時最優買賣價）
    2. 緩存即時價格數據（bid/ask/spread）
    3. 心跳監控 + 自動重連
    4. 計算流動性指標
    
    優勢：
    - 零延遲價格更新（vs REST 100-200ms）
    - 提供買賣價差數據（spread_bps）
    - 減少REST ticker API調用
    
    數據格式：
    {
        'symbol': 'BTCUSDT',
        'bid': 67000.0,          # 最優買價
        'ask': 67001.0,          # 最優賣價
        'bid_qty': 1.234,        # 買價數量
        'ask_qty': 0.567,        # 賣價數量
        'spread_bps': 1.49,      # 價差（基點）
        'mid_price': 67000.5,    # 中間價
        'server_timestamp': 1730177520000,  # 伺服器時間
        'local_timestamp': 1730177520023,   # 本地接收時間
        'latency_ms': 23         # 網路延遲
    }
    """
    
    def __init__(self, symbols: List[str], shard_id: int = 0):
        """
        初始化PriceFeed
        
        Args:
            symbols: 交易對列表
            shard_id: 分片ID（用於追蹤）
        """
        super().__init__(name=f"PriceFeed-Shard{shard_id}")
        
        self.symbols = [s.lower() for s in symbols if s]
        self.shard_id = shard_id
        self.price_cache: Dict[str, Dict] = {}  # {symbol: price_data}
        self.ws_task: Optional[asyncio.Task] = None
        
        logger.info("=" * 80)
        logger.info(f"✅ PriceFeed Shard{shard_id} 初始化完成")
        logger.info(f"   📊 監控幣種數量: {len(self.symbols)}")
        logger.info(f"   📡 數據源: bookTicker（即時買賣價）")
        logger.info("=" * 80)
    
    async def start(self):
        """啟動bookTicker WebSocket監聽"""
        if not self.symbols:
            logger.warning(f"⚠️ {self.name}: 無幣種，未啟動")
            return
        
        if not websockets:
            logger.error(f"❌ {self.name}: websockets模塊未安裝")
            return
        
        self.running = True
        logger.info(f"🚀 {self.name} 啟動中... ({len(self.symbols)} 個幣種)")
        
        # 啟動心跳監控
        await self._start_heartbeat_monitor()
        
        # 啟動WebSocket監聽
        self.ws_task = asyncio.create_task(self._listen_prices())
        
        logger.info(f"✅ {self.name} 已啟動")
    
    async def _listen_prices(self):
        """
        監聽bookTicker WebSocket流（合併訂閱）
        
        使用合併流（Combined Streams）訂閱多個幣種：
        wss://fstream.binance.com/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker/...
        """
        # 構建合併流URL
        streams = "/".join([f"{symbol}@bookTicker" for symbol in self.symbols])
        url = f"wss://fstream.binance.com/stream?streams={streams}"
        
        reconnect_delay = 5
        
        while self.running:
            try:
                # v3.20.6 穩定性優化：更頻繁的keepalive檢測（15秒）
                async with websockets.connect(
                    url, 
                    ping_interval=15,      # 每15秒發送ping（從20秒縮短，提升穩定性）
                    ping_timeout=10,       # 10秒等待pong回應
                    close_timeout=10,      # 10秒關閉超時
                    max_size=2**20,        # 1MB消息緩衝區
                    read_limit=2**18,      # 256KB讀取限制
                    write_limit=2**18      # 256KB寫入限制
                ) as ws:  # type: ignore
                    logger.debug(f"✅ {self.name} WebSocket已連接 ({len(self.symbols)}個幣種)")
                    
                    while self.running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30)
                            data = json.loads(msg)
                            
                            # 合併流數據格式: {"stream": "btcusdt@bookTicker", "data": {...}}
                            if 'data' in data:
                                self._update_price(data['data'])
                            
                            # 更新心跳
                            self._update_heartbeat()
                        
                        except asyncio.TimeoutError:
                            try:
                                await ws.ping()
                            except Exception:
                                logger.warning(f"⚠️ {self.name} ping失敗，重連中...")
                                break
                        
                        except Exception as e:
                            logger.error(f"❌ {self.name} 接收失敗: {e}")
                            self.stats['errors'] += 1
                            break
            
            except Exception as e:
                self.stats['reconnections'] += 1
                logger.warning(f"🔄 {self.name} 重連中... (錯誤: {e})")
                await asyncio.sleep(reconnect_delay)
    
    def _update_price(self, data: dict):
        """
        更新價格緩存（bookTicker數據）
        
        Args:
            data: bookTicker數據
        """
        try:
            symbol = data.get('s', '').lower()
            if not symbol or symbol not in self.symbols:
                return
            
            # 獲取時間戳
            server_ts = self.get_server_timestamp_ms(data, 'T')  # 交易時間
            local_ts = self.get_local_timestamp_ms()
            latency_ms = self.calculate_latency_ms(server_ts, local_ts)
            
            # 解析價格數據
            bid = float(data['b'])
            ask = float(data['a'])
            bid_qty = float(data['B'])
            ask_qty = float(data['A'])
            
            # 計算中間價和價差
            mid_price = (bid + ask) / 2
            spread = ask - bid
            spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0
            
            # 更新緩存
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
                f"💰 {symbol.upper()} 價格更新: "
                f"bid={bid}, ask={ask}, spread={spread_bps:.2f}bps, "
                f"latency={latency_ms}ms"
            )
        
        except Exception as e:
            logger.error(f"❌ {self.name} 解析price失敗: {e}")
    
    async def _on_heartbeat_timeout(self):
        """心跳超時處理（觸發重連）"""
        logger.warning(f"⚠️ {self.name} 心跳超時，正在等待自動重連...")
        # WebSocket會自動重連（_listen_prices的while循環）
    
    # ==================== 數據查詢接口 ====================
    
    def get_price(self, symbol: str) -> Optional[Dict]:
        """
        獲取即時價格數據
        
        Args:
            symbol: 交易對
        
        Returns:
            價格數據，或None
        """
        return self.price_cache.get(symbol.lower())
    
    def get_mid_price(self, symbol: str) -> Optional[float]:
        """
        獲取中間價
        
        Args:
            symbol: 交易對
        
        Returns:
            中間價，或None
        """
        price_data = self.get_price(symbol)
        return price_data['mid_price'] if price_data else None
    
    def get_spread_bps(self, symbol: str) -> Optional[float]:
        """
        獲取買賣價差（基點）
        
        Args:
            symbol: 交易對
        
        Returns:
            價差（基點），或None
        """
        price_data = self.get_price(symbol)
        return price_data['spread_bps'] if price_data else None
    
    def get_all_prices(self) -> Dict[str, Dict]:
        """
        獲取所有幣種的價格數據
        
        Returns:
            所有價格數據的字典
        """
        return self.price_cache.copy()
    
    def get_stats(self) -> Dict:
        """
        獲取統計數據
        
        Returns:
            統計數據字典
        """
        base_stats = super().get_stats()
        return {
            **base_stats,
            'cached_symbols': len(self.price_cache),
            'shard_id': self.shard_id
        }
    
    async def stop(self):
        """停止PriceFeed"""
        logger.info(f"⏸️  {self.name} 停止中...")
        self.running = False
        
        # 停止心跳監控
        await self._stop_heartbeat_monitor()
        
        # 取消WebSocket任務
        if self.ws_task:
            self.ws_task.cancel()
            try:
                await self.ws_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"✅ {self.name} 已停止")
