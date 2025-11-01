"""
KlineFeed v3.17.2+ - 即時K線數據流（升級版+合併流訂閱）
職責：訂閱Binance @kline_1m WebSocket，取代REST K線輪詢
升級：時間戳標準化、心跳監控、shard_id支持、合併流訂閱
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional

try:
    import websockets  # type: ignore
except ImportError:
    websockets = None  # type: ignore

from src.core.websocket.base_feed import BaseFeed

logger = logging.getLogger(__name__)


class KlineFeed(BaseFeed):
    """
    KlineFeed - Binance K線WebSocket監控器（v3.17.2+升級版+合併流）
    
    職責：
    1. 使用合併流訂閱多個幣種（單一連線）
    2. 緩存最新閉盤K線數據
    3. 斷線自動重連（每5秒）
    4. 提供即時K線數據查詢
    5. 時間戳標準化（server_timestamp + local_timestamp + latency_ms）
    6. 心跳監控（30秒無訊息→重連）
    
    **關鍵升級（v3.17.2+）**：
    - 使用合併流（Combined Streams）：單一WebSocket訂閱多個符號
    - URL格式：wss://fstream.binance.com/stream?streams=btcusdt@kline_1m/ethusdt@kline_1m/...
    - 符合分片目標：每個KlineFeed實例管理≤50個符號在單一連線上
    
    優勢：
    - 減少90%+ REST API K線請求
    - 減少95%+ WebSocket連線數（50符號/連線 vs 1符號/連線）
    - 即時趨勢分析（無延遲）
    - 網路延遲追蹤（訓練特徵）
    
    K線數據格式（v3.17.2+）：
    {
        'symbol': 'BTCUSDT',
        'open': 67000.0,
        'high': 67500.0,
        'low': 66800.0,
        'close': 67200.0,
        'volume': 1234.56,
        'quote_volume': 82904800.0,
        'trades': 12345,
        'server_timestamp': 1730177520000,  # Binance伺服器時間（毫秒）
        'local_timestamp': 1730177520023,   # 本地接收時間（毫秒）
        'latency_ms': 23,                   # 網路延遲（毫秒）
        'close_time': 1730177579999,        # K線閉盤時間
        'shard_id': 0                       # 分片ID
    }
    """
    
    def __init__(self, symbols: List[str], interval: str = "1m", shard_id: int = 0, max_history: int = 100):
        """
        初始化KlineFeed
        
        Args:
            symbols: 交易對列表（例如：['BTCUSDT', 'ETHUSDT']）
            interval: K線週期（默認1m）
            shard_id: 分片ID（用於追蹤，默認0）
            max_history: 最大歷史K線數量（默認100，用於聚合5m/15m/1h）
        """
        super().__init__(name=f"KlineFeed-Shard{shard_id}")
        
        self.symbols = [s.lower() for s in symbols if s]
        self.interval = interval
        self.shard_id = shard_id
        self.max_history = max_history
        self.kline_cache: Dict[str, List[Dict]] = {}  # {symbol: [kline1, kline2, ...]}（保留最近max_history根）
        self.ws_task: Optional[asyncio.Task] = None
        
        logger.info("=" * 80)
        logger.info(f"✅ KlineFeed Shard{shard_id} 初始化完成")
        logger.info(f"   📊 監控幣種數量: {len(self.symbols)}")
        logger.info(f"   ⏱️  K線週期: {interval}")
        logger.info(f"   📦 歷史緩存大小: {max_history}根K線")
        logger.info(f"   🔌 WebSocket模式: 合併流（單一連線）")
        logger.info(f"   ⚡ 時間戳標準化: server_ts + local_ts + latency_ms")
        logger.info(f"   💓 心跳監控: 30秒無訊息→重連")
        logger.info("=" * 80)
    
    async def start(self):
        """啟動合併流WebSocket監聽（非阻塞）"""
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
        
        # 啟動合併流WebSocket監聽（單一連線）
        self.ws_task = asyncio.create_task(self._listen_klines_combined())
        
        logger.info(f"✅ {self.name} 已啟動（合併流單一連線）")
    
    async def _listen_klines_combined(self):
        """
        監聽多個幣種的K線WebSocket流（合併流訂閱）
        
        使用合併流（Combined Streams）訂閱多個符號：
        wss://fstream.binance.com/stream?streams=btcusdt@kline_1m/ethusdt@kline_1m/...
        
        關鍵優勢：
        - 單一WebSocket連線處理多個符號
        - 符合Binance最佳實務（≤100 streams/連線）
        - 減少連線開銷，提升穩定性
        """
        # 構建合併流URL
        streams = "/".join([f"{symbol}@kline_{self.interval}" for symbol in self.symbols])
        url = f"wss://fstream.binance.com/stream?streams={streams}"
        
        reconnect_delay = 5
        
        while self.running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:  # type: ignore
                    logger.debug(f"✅ {self.name} WebSocket已連接 ({len(self.symbols)}個幣種)")
                    
                    while self.running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30)
                            data = json.loads(msg)
                            
                            # 合併流數據格式: {"stream": "btcusdt@kline_1m", "data": {...}}
                            if 'data' in data and data['data'].get('e') == 'kline':
                                self._update_kline(data['data']['k'])
                            
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
    
    def _update_kline(self, kline: dict):
        """
        更新K線緩存（僅閉盤K線）+ 時間戳標準化
        
        Args:
            kline: K線數據
        """
        symbol = kline.get('s', '').lower()
        if not symbol or symbol not in self.symbols:
            return
        
        # 🔥 v3.17.2+：僅保存閉盤K線（is_final=True）
        if kline.get('x', False):  # x = is_final
            # 🔥 v3.18.8+ Critical Fix: 使用事件時間計算延遲，而非開盤時間
            # 修復前：server_ts = kline['t']（開盤時間，60秒前）→ 延遲顯示60,000ms ❌
            # 修復後：server_ts = kline['E']（事件時間，當前）→ 延遲顯示100-500ms ✅
            event_ts = self.get_server_timestamp_ms(kline, 'E')  # WebSocket事件時間（最準確）
            open_ts = int(kline['t'])  # K線開盤時間（用於時間對齊聚合）
            local_ts = self.get_local_timestamp_ms()
            latency_ms = self.calculate_latency_ms(event_ts, local_ts)  # 真實網路延遲
            
            kline_data = {
                'symbol': kline.get('s'),
                'timestamp': open_ts,                 # ✅ K線開盤時間（用於聚合時間對齊）
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v']),
                'quote_volume': float(kline['q']),
                'trades': int(kline['n']),
                'server_timestamp': event_ts,         # ✅ WebSocket事件時間（用於延遲計算）
                'local_timestamp': local_ts,          # 本地接收時間（毫秒）
                'latency_ms': latency_ms,             # ✅ 真實網路延遲（100-500ms）
                'close_time': int(kline['T']),       # K線閉盤時間
                'shard_id': self.shard_id             # 分片ID
            }
            
            # 🔥 v3.17.3+：維護K線歷史列表（保留最近max_history根）
            if symbol not in self.kline_cache:
                self.kline_cache[symbol] = []
            
            self.kline_cache[symbol].append(kline_data)
            
            # 保留最近max_history根K線
            if len(self.kline_cache[symbol]) > self.max_history:
                self.kline_cache[symbol] = self.kline_cache[symbol][-self.max_history:]
            
            logger.debug(
                f"📊 {symbol.upper()} K線更新: "
                f"O={kline['o']}, H={kline['h']}, L={kline['l']}, C={kline['c']}, "
                f"latency={latency_ms}ms, 歷史={len(self.kline_cache[symbol])}根, shard={self.shard_id}"
            )
    
    async def _on_heartbeat_timeout(self):
        """心跳超時處理（觸發重連）"""
        logger.warning(f"⚠️ {self.name} 心跳超時，正在等待自動重連...")
        # WebSocket會自動重連（_listen_klines_combined的while循環）
    
    # ==================== 數據查詢接口 ====================
    
    def get_latest_kline(self, symbol: str) -> Optional[Dict]:
        """
        獲取最新K線數據
        
        Args:
            symbol: 交易對
        
        Returns:
            最新K線數據，或None（如果無數據）
        """
        klines = self.kline_cache.get(symbol.lower())
        if klines and len(klines) > 0:
            return klines[-1]
        return None
    
    def get_kline_history(self, symbol: str) -> List[Dict]:
        """
        獲取K線歷史數據（用於聚合5m/15m/1h）
        
        Args:
            symbol: 交易對
        
        Returns:
            K線歷史列表（按時間戳升序），如果無數據則返回空列表
        """
        return self.kline_cache.get(symbol.lower(), []).copy()
    
    def get_all_klines(self) -> Dict[str, List[Dict]]:
        """
        獲取所有幣種的K線歷史
        
        Returns:
            所有K線歷史數據的字典 {symbol: [kline1, kline2, ...]}
        """
        return {symbol: klines.copy() for symbol, klines in self.kline_cache.items()}
    
    def seed_history(self, symbol: str, klines: List[Dict]):
        """
        預填充K線歷史（用於啟動時預熱緩存）
        
        Args:
            symbol: 交易對
            klines: K線歷史列表（按時間戳升序）
        """
        symbol = symbol.lower()
        if symbol not in self.symbols:
            logger.warning(f"⚠️ {symbol} 不在監控列表中，跳過預填充")
            return
        
        # 保留最近max_history根K線
        self.kline_cache[symbol] = klines[-self.max_history:] if len(klines) > self.max_history else klines.copy()
        
        logger.info(f"✅ {symbol.upper()} 預填充 {len(self.kline_cache[symbol])} 根K線歷史")
    
    def has_sufficient_history(self, symbol: str, min_count: int = 60) -> bool:
        """
        檢查是否有足夠的K線歷史（用於預熱檢查）
        
        Args:
            symbol: 交易對
            min_count: 最小K線數量（默認60，用於聚合1h）
        
        Returns:
            True如果歷史數據足夠，否則False
        """
        klines = self.kline_cache.get(symbol.lower(), [])
        return len(klines) >= min_count
    
    def get_stats(self) -> Dict:
        """
        獲取統計數據
        
        Returns:
            統計數據字典
        """
        base_stats = super().get_stats()
        return {
            **base_stats,
            'cached_symbols': len(self.kline_cache),
            'total_symbols': len(self.symbols),
            'shard_id': self.shard_id,
            'connection_mode': 'combined_stream'
        }
    
    async def stop(self):
        """停止合併流WebSocket連線"""
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
