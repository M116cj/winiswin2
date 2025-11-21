"""
KlineFeed v4.5+ - 即時K線數據流（重構版：職責分離架構）
職責：訂閱Binance @kline_1m WebSocket，專注消息處理
升級：連接管理由OptimizedWebSocketFeed負責，KlineFeed專注數據處理
🔥 v4.5+: 完整架構重構，使用父類連接管理
🔥 v3.23+: 集成ConcurrentDictManager實現線程安全緩存
🔥 v3.29+: 使用OptimizedWebSocketFeed（指数退避重连，健康檢查）
"""

import asyncio
# 🔥 Performance Upgrade: Use orjson for 2-3x faster JSON parsing
try:
    import orjson as json
    _ORJSON_ENABLED = True
except ImportError:
    import json
    _ORJSON_ENABLED = False
from src.utils.logger_factory import get_logger
import time
from typing import Dict, List, Optional

try:
    import websockets  # type: ignore
    from websockets.exceptions import ConnectionClosed, ConnectionClosedError  # type: ignore
except ImportError:
    websockets = None  # type: ignore
    ConnectionClosed = Exception  # type: ignore
    ConnectionClosedError = Exception  # type: ignore

from src.core.websocket.optimized_base_feed import OptimizedWebSocketFeed  # v3.29+
from src.core.websocket.heartbeat_monitor import ApplicationLevelHeartbeatMonitor  # 🔥 v1.0
from src.core.concurrent_dict_manager import ConcurrentDictManager

logger = get_logger(__name__)


class KlineFeed(OptimizedWebSocketFeed):
    """
    KlineFeed v4.5+ - Binance K線WebSocket監控器（重構版：職責分離）
    
    **架構設計（v4.5+）**：
    - 連接管理：由OptimizedWebSocketFeed父類負責（指數退避、健康檢查）
    - 消息處理：由KlineFeed專注處理（解析、緩存、統計）
    
    職責：
    1. ✅ 使用合併流訂閱多個幣種（單一連線）
    2. ✅ 緩存最新閉盤K線數據（ConcurrentDictManager）
    3. ✅ 提供即時K線數據查詢
    4. ✅ 時間戳標準化（server_timestamp + local_timestamp + latency_ms）
    
    **連接管理（由父類OptimizedWebSocketFeed負責）**：
    - 指數退避重連：1s → 300s（避免重連風暴）
    - 健康檢查：每60秒（主動檢測異常）
    - 心跳監控：Binance服務器每20秒ping，websockets庫自動pong
    - 連接狀態：完整追蹤（last_message_time, reconnect_count等）
    
    **合併流訂閱**：
    - URL格式：wss://fstream.binance.com/stream?streams=btcusdt@kline_1m/ethusdt@kline_1m/...
    - 單一WebSocket連線處理≤50個符號
    - 減少95%+ WebSocket連線數
    
    K線數據格式：
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
    
    def __init__(self, symbols: List[str], interval: str = "1m", shard_id: int = 0, max_history: int = 4000):
        """
        初始化KlineFeed
        
        Args:
            symbols: 交易對列表（例如：['BTCUSDT', 'ETHUSDT']）
            interval: K線週期（默認1m）
            shard_id: 分片ID（用於追蹤，默認0）
            max_history: 最大歷史K線數量（默認4000，支持1h聚合需≥3600根）
        
        Notes:
            v4.3.2+：max_history提升到4000以支持WebSocket-only模式
            - 1h聚合需要60根1m K線
            - 保留66.67小時历史（~3天）以应对网络中断
            - 内存占用：200符号 × 4000根 × 200bytes ≈ 160MB（可接受）
        """
        # v3.32+ 使用符合Binance规范的WebSocket参数
        super().__init__(
            name=f"KlineFeed-Shard{shard_id}",
            ping_interval=25,
            ping_timeout=60,  # 🔥 Stability Fix v2: Railway network optimization enhanced
            max_reconnect_delay=300,
            health_check_interval=60
        )
        
        self.symbols = [s.lower() for s in symbols if s]
        self.interval = interval
        self.shard_id = shard_id
        self.max_history = max_history
        
        # 🔥 v3.23+: 使用ConcurrentDictManager實現線程安全緩存
        self.kline_cache = ConcurrentDictManager[str, List[Dict]](
            name=f"KlineCache-Shard{shard_id}",
            enable_auto_cleanup=True,
            cleanup_interval=300,  # 每5分鐘清理一次
            max_size=1000  # 最多緩存1000個交易對
        )
        
        # 🔥 Application-Level Heartbeat Monitor v1.0
        self.heartbeat_monitor = ApplicationLevelHeartbeatMonitor(
            name=f"KlineHeartbeat-Shard{shard_id}",
            check_interval=10,  # 每10秒检查一次
            stale_threshold=60,  # 60秒无数据则强制重连
            on_stale_connection=self._on_stale_connection
        )
        
        self.ws_task: Optional[asyncio.Task] = None
        
        logger.info("=" * 80)
        logger.info(f"✅ KlineFeed Shard{shard_id} 初始化完成（v4.5 重構版）")
        logger.info(f"   📊 監控幣種數量: {len(self.symbols)}")
        logger.info(f"   ⏱️  K線週期: {interval}")
        logger.info(f"   📦 歷史緩存大小: {max_history}根K線")
        logger.info(f"   🔌 WebSocket模式: 合併流（單一連線）")
        logger.info(f"   ⚡ 架構模式: 職責分離（父類連接，子類處理）")
        logger.info(f"   💓 連接管理: OptimizedWebSocketFeed（指數退避+健康檢查）")
        logger.info(f"   🔄 心跳機制: 服務器ping（每20秒）+ websockets自動pong")
        logger.info("=" * 80)
    
    async def start(self):
        """啟動KlineFeed（v4.5+重構版：使用父類連接管理）"""
        if not self.symbols:
            logger.warning(f"⚠️ {self.name}: 無幣種，未啟動")
            return
        
        if not websockets:
            logger.error(f"❌ {self.name}: websockets模塊未安裝")
            return
        
        self.running = True
        logger.info(f"🚀 {self.name} 啟動中... ({len(self.symbols)} 個幣種)")
        
        # 啟動緩存自動清理任務
        await self.kline_cache.start_auto_cleanup()
        
        # ✅ v4.5+：使用父類connect()建立連接（指數退避重連）
        url = self._build_url()
        success = await self.connect(url)
        
        if not success:
            logger.error(f"❌ {self.name} 初始連接失敗（將在後台重試）")
            # 仍然啟動消息循環，父類會自動重連
        
        # ✅ v4.5+：啟動消息處理循環（不負責連接管理）
        self.ws_task = asyncio.create_task(self._message_loop())
        
        # 啟動健康檢查（父類功能）
        await self.start_health_check()
        
        # 🔥 Start application-level heartbeat monitor
        await self.heartbeat_monitor.start()
        
        logger.info(f"✅ {self.name} 已啟動（Producer-Consumer + AppLevel Heartbeat）")
    
    def _build_url(self) -> str:
        """
        構建WebSocket合併流URL
        
        Returns:
            WebSocket URL（合併流格式）
        """
        streams = "/".join([f"{symbol}@kline_{self.interval}" for symbol in self.symbols])
        url = f"wss://fstream.binance.com/stream?streams={streams}"
        
        logger.debug(f"📡 {self.name} WebSocket URL: {url[:100]}...")
        return url
    
    async def _message_loop(self):
        """
        消息處理循環（v4.5+：專注消息處理 + 主動重連）
        
        職責：
        - 接收WebSocket消息（使用父類receive_message()）
        - 解析K線數據
        - 更新緩存
        - 處理異常（區分可恢復 vs 致命錯誤）
        - ✅ 檢測斷線並主動觸發重連（調用父類connect()）
        
        重連機制：當檢測到連接斷開時，主動調用父類connect()重新建立連接。
        """
        logger.info(f"📨 {self.name} 消息處理循環已啟動")
        
        consecutive_errors = 0
        max_consecutive_errors = 20
        
        while self.running:
            try:
                # 檢查連接狀態，斷線則主動重連
                if not self.connected:
                    logger.warning(f"🔄 {self.name} 檢測到連接斷開，主動重連...")
                    url = self._build_url()
                    success = await self.connect(url)
                    
                    if not success:
                        logger.error(f"❌ {self.name} 重連失敗，5秒後重試...")
                        await asyncio.sleep(5)
                        continue
                    
                    logger.info(f"✅ {self.name} 重連成功")
                
                # ✅ 使用父類接收消息（帶超時和異常處理）
                msg = await self.receive_message()
                
                if not msg:
                    # 超時或連接問題
                    if not self.connected:
                        # 連接已斷開，下次循環會重連
                        continue
                    else:
                        # 超時但連接仍在，繼續
                        continue
                
                # ✅ 處理消息（專注業務邏輯）
                self._process_message(msg)
                
                # 重置錯誤計數器（成功處理消息）
                consecutive_errors = 0
            
            except ConnectionClosed:
                logger.warning(f"⚠️ {self.name} WebSocket連接關閉，將在下次循環重連")
                self.connected = False
                consecutive_errors = 0  # 連接關閉不算錯誤
                await asyncio.sleep(1)
            
            except asyncio.CancelledError:
                logger.info(f"⏸️ {self.name} 消息循環已取消")
                break
            
            except Exception as e:
                consecutive_errors += 1
                logger.error(
                    f"❌ {self.name} 消息循環異常 ({consecutive_errors}/{max_consecutive_errors}): {e}",
                    exc_info=True
                )
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(
                        f"🔴 {self.name} 連續錯誤{max_consecutive_errors}次，停止運行"
                    )
                    self.running = False
                    break
                
                await asyncio.sleep(1)
        
        logger.info(f"✅ {self.name} 消息處理循環已停止")
    
    async def _on_stale_connection(self) -> None:
        """
        🔥 Callback when application-level heartbeat detects stale connection
        Force reconnect by closing WebSocket
        """
        logger.warning(f"🔴 {self.name} 应用层心跳：检测到死连接，强制重连...")
        self.connected = False
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.warning(f"⚠️ {self.name} 关闭WebSocket失败: {e}")
    
    async def process_message(self, msg: str) -> None:
        """
        🔥 Producer-Consumer v1: Background worker processes K-line messages
        Override parent class method
        """
        self._process_message(msg)
        # 🔥 Record message receipt for application-level heartbeat
        self.heartbeat_monitor.record_message()
    
    def _process_message(self, msg: str):
        """
        處理單條WebSocket消息（v4.5+：專注數據解析）
        
        Args:
            msg: WebSocket消息（JSON字符串）
        
        不拋出異常，所有錯誤在內部處理。
        """
        try:
            # 🐛 Chain Reaction Fix: Check for None/invalid messages
            if not msg:
                logger.debug(f"⚠️ {self.name} 收到空消息，跳過")
                return
            
            data = json.loads(msg)
            
            # 🐛 Chain Reaction Fix: Defensive check for None after parsing
            if data is None:
                logger.debug(f"⚠️ {self.name} JSON解析結果為None（可能是心跳信號），跳過")
                return
            
            # 🐛 Chain Reaction Fix: Type check before subscripting
            if not isinstance(data, dict):
                logger.warning(f"⚠️ {self.name} 消息格式非字典: {type(data)}")
                return
            
            # 合併流數據格式: {"stream": "btcusdt@kline_1m", "data": {...}}
            if 'data' in data and data['data'] is not None and isinstance(data['data'], dict):
                if data['data'].get('e') == 'kline':
                    self._update_kline(data['data']['k'])
            else:
                # 非K線消息或格式不正確，跳過
                pass
        
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ {self.name} JSON解析失敗: {e}")
            if 'json_errors' not in self.stats:
                self.stats['json_errors'] = 0
            self.stats['json_errors'] += 1
        
        except TypeError as e:
            logger.warning(f"⚠️ {self.name} 消息格式錯誤（NoneType）: {e}")
            if 'format_errors' not in self.stats:
                self.stats['format_errors'] = 0
            self.stats['format_errors'] += 1
        
        except KeyError as e:
            logger.warning(f"⚠️ {self.name} 消息格式錯誤（缺少字段）: {e}")
            if 'format_errors' not in self.stats:
                self.stats['format_errors'] = 0
            self.stats['format_errors'] += 1
        
        except Exception as e:
            logger.error(f"❌ {self.name} 消息處理異常: {e}", exc_info=True)
            if 'processing_errors' not in self.stats:
                self.stats['processing_errors'] = 0
            self.stats['processing_errors'] += 1
    
    def _update_kline(self, kline: dict):
        """
        更新K線緩存（v4.5+：僅閉盤K線 + 時間戳標準化）
        
        Args:
            kline: K線數據（來自Binance WebSocket）
        """
        symbol = kline.get('s', '').lower()
        if not symbol or symbol not in self.symbols:
            return
        
        # 僅保存閉盤K線（is_final=True）
        if kline.get('x', False):  # x = is_final
            # ✅ v4.5+：使用事件時間計算延遲（已移除循環內import）
            event_ts = int(kline.get('E', 0))  # WebSocket事件時間（最準確）
            open_ts = int(kline['t'])  # K線開盤時間（用於時間對齊聚合）
            local_ts = int(time.time() * 1000)  # 本地時間（毫秒）
            latency_ms = local_ts - event_ts if event_ts > 0 else 0  # 真實網路延遲
            
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
        
        # 🔥 v3.23+: 停止緩存自動清理任務
        await self.kline_cache.stop_auto_cleanup()
        
        # v3.29+ OptimizedWebSocketFeed会自动停止心跳监控
        # await self._stop_heartbeat_monitor()  # 已删除，由父类处理
        
        # 取消WebSocket任務
        if self.ws_task:
            self.ws_task.cancel()
            try:
                await self.ws_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"✅ {self.name} 已停止")
