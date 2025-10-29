"""
WebSocketMonitor v3.17.11 - 即時市場數據監控
職責：訂閱Binance WebSocket、緩存即時價格和深度、自動重連
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    import websockets  # type: ignore
except ImportError:
    websockets = None  # type: ignore

logger = logging.getLogger(__name__)


class WebSocketMonitor:
    """
    WebSocketMonitor - Binance WebSocket即時數據監控器
    
    職責：
    1. 訂閱bookTicker（最優買賣價）
    2. 緩存即時價格和深度數據
    3. 斷線自動重連（每5秒）
    4. 提供流動性評分計算
    
    優勢：
    - 避免REST API輪詢（減少API調用）
    - 即時價格更新（無延遲）
    - 深度數據（流動性評估）
    """
    
    def __init__(self, symbols: List[str]):
        """
        初始化WebSocketMonitor
        
        Args:
            symbols: 交易對列表（例如：['BTCUSDT', 'ETHUSDT']）
        """
        self.symbols = [s.lower() for s in symbols if s]  # 轉小寫並過濾空字符串
        self.price_cache: Dict[str, float] = {}  # 緩存最新價格
        self.depth_cache: Dict[str, Any] = {}  # 緩存深度數據（包含時間戳）
        self.running = False
        self.ws_tasks: List[asyncio.Task] = []
        
        # 統計數據
        self.stats = {
            'total_updates': 0,
            'reconnections': 0,
            'errors': 0,
            'active_symbols': 0
        }
        
        logger.info("=" * 80)
        logger.info("✅ WebSocketMonitor 初始化完成")
        logger.info(f"   📊 監控幣種數量: {len(self.symbols)}")
        logger.info(f"   🔌 WebSocket URL: wss://fstream.binance.com/ws/")
        logger.info(f"   📡 數據類型: bookTicker（最優買賣價+深度）")
        logger.info("=" * 80)
    
    async def start(self):
        """啟動所有WebSocket連線（非阻塞）"""
        if not self.symbols:
            logger.warning("⚠️ TRADING_SYMBOLS為空，WebSocket監控未啟動")
            return
        
        self.running = True
        logger.info(f"🚀 WebSocketMonitor 啟動中... ({len(self.symbols)} 個幣種)")
        
        # 為每個幣種創建WebSocket監聽任務
        self.ws_tasks = [
            asyncio.create_task(self._listen_symbol(symbol)) 
            for symbol in self.symbols
        ]
        
        # 非阻塞：讓任務在後台運行
        logger.info(f"✅ WebSocketMonitor 已啟動 {len(self.ws_tasks)} 個連接")
        
        # 更新活躍幣種數量
        self.stats['active_symbols'] = len(self.symbols)
    
    async def _listen_symbol(self, symbol: str):
        """
        監聽單個幣種的WebSocket流
        
        Args:
            symbol: 幣種（小寫，例如：btcusdt）
        """
        url = f"wss://fstream.binance.com/ws/{symbol}@bookTicker"
        reconnect_delay = 5  # 重連延遲（秒）
        
        while self.running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:  # type: ignore
                    logger.debug(f"✅ {symbol.upper()} WebSocket已連接")
                    
                    while self.running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30)
                            data = json.loads(msg)
                            self._update_cache(symbol, data)
                            
                        except asyncio.TimeoutError:
                            # 30秒無數據，檢查連接
                            try:
                                await ws.ping()
                            except Exception:
                                logger.warning(f"⚠️ {symbol.upper()} ping失敗，重連中...")
                                break
                        
                        except Exception as e:
                            logger.error(f"❌ {symbol.upper()} 接收數據失敗: {e}")
                            self.stats['errors'] += 1
                            break
            
            except websockets.exceptions.WebSocketException as e:  # type: ignore
                self.stats['reconnections'] += 1
                logger.warning(f"🔄 {symbol.upper()} WebSocket重連中... (錯誤: {e})")
                await asyncio.sleep(reconnect_delay)
            
            except Exception as e:
                self.stats['errors'] += 1
                logger.error(f"❌ {symbol.upper()} WebSocket異常: {e}")
                await asyncio.sleep(reconnect_delay)
    
    def _update_cache(self, symbol: str, data: dict):
        """
        更新緩存數據
        
        Args:
            symbol: 幣種（小寫）
            data: bookTicker數據
        
        數據格式：
        {
            "u": 更新ID,
            "s": "BTCUSDT",
            "b": "43250.00",    # 最優買價（bid）
            "B": "10.5",        # 最優買量
            "a": "43251.00",    # 最優賣價（ask）
            "A": "8.2"          # 最優賣量
        }
        """
        try:
            # 使用賣一價作為當前價格（更接近市價單成交價）
            self.price_cache[symbol] = float(data['a'])
            
            # 緩存深度數據
            self.depth_cache[symbol] = {
                'bid_price': float(data['b']),
                'bid_qty': float(data['B']),
                'ask_price': float(data['a']),
                'ask_qty': float(data['A']),
                'spread': float(data['a']) - float(data['b']),
                'last_update': datetime.now()
            }
            
            self.stats['total_updates'] += 1
            
            # 每1000次更新記錄一次（避免日誌過多）
            if self.stats['total_updates'] % 1000 == 0:
                logger.debug(
                    f"📊 WebSocket更新: {self.stats['total_updates']} 次 | "
                    f"活躍: {len(self.price_cache)} 幣種 | "
                    f"重連: {self.stats['reconnections']} 次"
                )
        
        except (KeyError, ValueError) as e:
            logger.error(f"❌ {symbol.upper()} 數據解析失敗: {e}")
            self.stats['errors'] += 1
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        獲取幣種的即時價格
        
        Args:
            symbol: 交易對（例如：BTCUSDT 或 btcusdt）
        
        Returns:
            即時價格，無數據時返回None
        """
        symbol_lower = symbol.lower()
        price = self.price_cache.get(symbol_lower)
        
        if price is None:
            logger.debug(f"⚠️ {symbol.upper()} WebSocket無價格數據，可能需要REST備援")
        
        return price
    
    def get_depth(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        獲取幣種的深度數據
        
        Args:
            symbol: 交易對（例如：BTCUSDT）
        
        Returns:
            深度數據字典，無數據時返回None
        """
        return self.depth_cache.get(symbol.lower())
    
    def get_liquidity_score(self, symbol: str) -> float:
        """
        計算流動性評分（0.0 - 1.0）
        
        Args:
            symbol: 交易對
        
        Returns:
            流動性評分：
            - 0.0: 無流動性或無數據
            - 1.0: 極高流動性（買賣量>=10）
        
        計算方式：
            score = min(1.0, (bid_qty + ask_qty) / 10.0)
        """
        depth = self.depth_cache.get(symbol.lower())
        
        if not depth:
            return 0.0
        
        total_qty = depth['bid_qty'] + depth['ask_qty']
        
        # 標準化到0-1範圍（10作為參考值）
        score = min(1.0, total_qty / 10.0)
        
        return score
    
    def get_spread_bps(self, symbol: str) -> Optional[float]:
        """
        計算買賣價差（基點，1 bps = 0.01%）
        
        Args:
            symbol: 交易對
        
        Returns:
            價差（基點），無數據時返回None
        """
        depth = self.depth_cache.get(symbol.lower())
        
        if not depth:
            return None
        
        mid_price = (depth['bid_price'] + depth['ask_price']) / 2
        spread_bps = (depth['spread'] / mid_price) * 10000
        
        return spread_bps
    
    async def stop(self):
        """停止所有WebSocket連線"""
        logger.info("⏸️  WebSocketMonitor 停止中...")
        self.running = False
        
        # 取消所有WebSocket任務
        for task in self.ws_tasks:
            task.cancel()
        
        # 等待所有任務完成
        await asyncio.gather(*self.ws_tasks, return_exceptions=True)
        
        logger.info("✅ WebSocketMonitor 已停止")
        logger.info(f"   📊 統計: 總更新={self.stats['total_updates']}, "
                   f"重連={self.stats['reconnections']}, "
                   f"錯誤={self.stats['errors']}")
    
    def get_stats(self) -> Dict[str, int]:
        """獲取統計數據"""
        return {
            **self.stats,
            'cached_symbols': len(self.price_cache),
            'monitored_symbols': len(self.symbols)
        }
    
    def is_ready(self, symbol: str) -> bool:
        """
        檢查幣種數據是否就緒
        
        Args:
            symbol: 交易對
        
        Returns:
            True表示有價格數據，False表示需要等待或使用REST備援
        """
        return symbol.lower() in self.price_cache
