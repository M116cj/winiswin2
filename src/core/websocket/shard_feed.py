"""
🔥 ShardFeed - Individual Shard Worker for Combined Streams
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Handle a chunk (50-100 symbols) via single WebSocket combined stream
Design: Concrete implementation inheriting from UnifiedWebSocketFeed
"""

import asyncio
import json
import logging
from typing import List, Optional, Callable

try:
    import websockets
except ImportError:
    websockets = None

logger = logging.getLogger(__name__)


class ShardFeed:
    """
    Individual shard worker handling a chunk of trading pairs
    
    Features:
    - Combined streams URL for efficient data transfer
    - K-line data parsing and routing
    - Auto-reconnect with exponential backoff
    - Callback routing to ClusterManager
    """
    
    def __init__(
        self,
        all_symbols: List[str],
        shard_id: int = 0,
        on_kline_callback: Optional[Callable] = None,
        kline_interval: str = "1m"
    ):
        """
        Initialize ShardFeed for a chunk of symbols
        
        Args:
            all_symbols: List of symbols for this shard
            shard_id: Shard identifier
            on_kline_callback: Callback when kline closes
            kline_interval: Kline interval (default 1m)
        """
        self.all_symbols = [s.lower() for s in all_symbols]
        self.shard_id = shard_id
        self.on_kline_callback = on_kline_callback
        self.kline_interval = kline_interval
        self.running = False
        
        # WebSocket management
        self._ws = None
        self._connection_task = None
        self._reconnect_delay = 5  # Start with 5s
        self._max_reconnect_delay = 300  # Cap at 5 minutes
        
        # Stats
        self.stats = {
            'messages_received': 0,
            'reconnections': 0,
            'errors': 0
        }
        
        logger.info(f"✅ ShardFeed {shard_id} initialized ({len(all_symbols)} symbols)")
    
    def _build_combined_stream_url(self) -> str:
        """
        Build Binance combined streams URL
        
        Format: wss://fstream.binance.com/stream?streams=btcusdt@kline_1m/ethusdt@kline_1m/...
        
        Returns: WebSocket URL
        """
        streams = []
        for symbol in self.all_symbols:
            stream_name = f"{symbol}@kline_{self.kline_interval}"
            streams.append(stream_name)
        
        combined = "/".join(streams)
        url = f"wss://fstream.binance.com/stream?streams={combined}"
        
        logger.debug(f"📡 Shard {self.shard_id} URL ({len(streams)} streams)")
        return url
    
    async def _connect_and_listen(self):
        """
        Connect to WebSocket and process messages
        """
        url = self._build_combined_stream_url()
        
        try:
            logger.info(f"🔌 Shard {self.shard_id} connecting ({len(self.all_symbols)} symbols)...")
            
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                max_size=None
            ) as ws:
                self._ws = ws
                self._reconnect_delay = 5  # Reset backoff on successful connection
                logger.info(f"✅ Shard {self.shard_id} connected")
                
                while self.running:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=30)
                        await self._process_message(message)
                    except asyncio.TimeoutError:
                        logger.warning(f"⚠️ Shard {self.shard_id} timeout")
                        break
        
        except Exception as e:
            logger.error(f"❌ Shard {self.shard_id} connection error: {e}")
            self.stats['errors'] += 1
    
    async def _process_message(self, message: str):
        """
        Parse combined stream message and route klines
        
        Combined stream format:
        {
            "stream": "btcusdt@kline_1m",
            "data": {
                "e": "kline",
                "E": 1234567890000,
                "s": "BTCUSDT",
                "k": {
                    "t": 1234567860000,
                    "T": 1234567919999,
                    "s": "BTCUSDT",
                    "i": "1m",
                    "f": 100,
                    "L": 200,
                    "o": "10000",
                    "c": "10100",
                    "h": "10200",
                    "l": "9900",
                    "v": "1000",
                    "n": 100,
                    "x": true,  # Is this candle closed?
                    "q": "10150000",
                    "V": "500",
                    "Q": "5075000",
                    "B": "0"
                }
            }
        }
        """
        try:
            payload = json.loads(message)
            
            if 'data' not in payload:
                return
            
            data = payload['data']
            
            # Check if it's a kline event
            if data.get('e') != 'kline':
                return
            
            # Extract kline info
            kline_data = data.get('k', {})
            is_closed = kline_data.get('x', False)
            
            # Only process closed klines
            if not is_closed:
                return
            
            # Parse kline
            symbol = kline_data.get('s', '').lower()
            kline = {
                'symbol': symbol,
                'open': float(kline_data.get('o', 0)),
                'high': float(kline_data.get('h', 0)),
                'low': float(kline_data.get('l', 0)),
                'close': float(kline_data.get('c', 0)),
                'volume': float(kline_data.get('v', 0)),
                'quote_volume': float(kline_data.get('q', 0)),
                'timestamp': int(kline_data.get('T', 0)),
                'interval': kline_data.get('i', '1m')
            }
            
            self.stats['messages_received'] += 1
            
            # Route to callback
            if self.on_kline_callback:
                await self.on_kline_callback(kline)
        
        except Exception as e:
            logger.error(f"❌ Shard {self.shard_id} parse error: {e}")
            self.stats['errors'] += 1
    
    async def start(self):
        """Start the shard feed"""
        if self.running:
            logger.warning(f"⚠️ Shard {self.shard_id} already running")
            return
        
        self.running = True
        self._connection_task = asyncio.create_task(self._reconnect_loop())
        logger.info(f"🚀 Shard {self.shard_id} started")
    
    async def _reconnect_loop(self):
        """
        Automatic reconnection with exponential backoff
        """
        while self.running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                logger.error(f"❌ Shard {self.shard_id} reconnect error: {e}")
            
            if self.running:
                wait_time = min(self._reconnect_delay, self._max_reconnect_delay)
                logger.info(f"⏳ Shard {self.shard_id} reconnecting in {wait_time}s...")
                await asyncio.sleep(wait_time)
                self._reconnect_delay = min(self._reconnect_delay * 1.5, self._max_reconnect_delay)
                self.stats['reconnections'] += 1
    
    async def stop(self):
        """Stop the shard feed"""
        self.running = False
        
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"✅ Shard {self.shard_id} stopped")
    
    def get_stats(self) -> dict:
        """Get shard statistics"""
        return {
            'shard_id': self.shard_id,
            'symbols': len(self.all_symbols),
            **self.stats
        }
