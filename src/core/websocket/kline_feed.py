"""
KlineFeed v3.17.2+ - 即時K線數據流
職責：訂閱Binance @kline_1m WebSocket，取代REST K線輪詢
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

try:
    import websockets  # type: ignore
except ImportError:
    websockets = None  # type: ignore

logger = logging.getLogger(__name__)


class KlineFeed:
    """
    KlineFeed - Binance K線WebSocket監控器
    
    職責：
    1. 訂閱@kline_1m（1分鐘K線）
    2. 緩存最新閉盤K線數據
    3. 斷線自動重連（每5秒）
    4. 提供即時K線數據查詢
    
    優勢：
    - 減少90%+ REST API K線請求
    - 即時趨勢分析（無延遲）
    - 自動數據更新（無需輪詢）
    """
    
    def __init__(self, symbols: List[str], interval: str = "1m"):
        """
        初始化KlineFeed
        
        Args:
            symbols: 交易對列表（例如：['BTCUSDT', 'ETHUSDT']）
            interval: K線週期（默認1m）
        """
        self.symbols = [s.lower() for s in symbols if s]
        self.interval = interval
        self.kline_cache: Dict[str, Dict] = {}  # {symbol: latest_kline}
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
        logger.info("✅ KlineFeed 初始化完成")
        logger.info(f"   📊 監控幣種數量: {len(self.symbols)}")
        logger.info(f"   ⏱️  K線週期: {interval}")
        logger.info(f"   🔌 WebSocket URL: wss://fstream.binance.com/ws/")
        logger.info("=" * 80)
    
    async def start(self):
        """啟動所有WebSocket連線（非阻塞）"""
        if not self.symbols:
            logger.warning("⚠️ KlineFeed: 無幣種，未啟動")
            return
        
        if not websockets:
            logger.error("❌ KlineFeed: websockets模塊未安裝")
            return
        
        self.running = True
        logger.info(f"🚀 KlineFeed 啟動中... ({len(self.symbols)} 個幣種)")
        
        # 為每個幣種創建WebSocket監聽任務
        self.ws_tasks = [
            asyncio.create_task(self._listen_kline(symbol)) 
            for symbol in self.symbols
        ]
        
        logger.info(f"✅ KlineFeed 已啟動 {len(self.ws_tasks)} 個連接")
        self.stats['active_symbols'] = len(self.symbols)
    
    async def _listen_kline(self, symbol: str):
        """
        監聽單個幣種的K線WebSocket流
        
        Args:
            symbol: 幣種（小寫，例如：btcusdt）
        """
        stream = f"{symbol}@kline_{self.interval}"
        url = f"wss://fstream.binance.com/ws/{stream}"
        reconnect_delay = 5
        
        while self.running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:  # type: ignore
                    logger.debug(f"✅ {symbol.upper()} K線WebSocket已連接")
                    
                    while self.running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30)
                            data = json.loads(msg)
                            
                            if data.get('e') == 'kline':
                                self._update_kline(symbol, data['k'])
                            
                        except asyncio.TimeoutError:
                            try:
                                await ws.ping()
                            except Exception:
                                logger.warning(f"⚠️ {symbol.upper()} K線 ping失敗，重連中...")
                                break
                        
                        except Exception as e:
                            logger.error(f"❌ {symbol.upper()} K線接收失敗: {e}")
                            self.stats['errors'] += 1
                            break
            
            except Exception as e:
                self.stats['reconnections'] += 1
                logger.warning(f"🔄 {symbol.upper()} K線重連中... (錯誤: {e})")
                await asyncio.sleep(reconnect_delay)
    
    def _update_kline(self, symbol: str, kline: dict):
        """
        更新K線緩存（僅閉盤K線）
        
        Args:
            symbol: 幣種
            kline: K線數據
        """
        # 🔥 v3.17.2+：僅保存閉盤K線（is_final=True）
        if kline.get('x', False):  # x = is_final
            self.kline_cache[symbol] = {
                'symbol': symbol.upper(),
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v']),
                'timestamp': int(kline['t']),
                'close_time': int(kline['T']),
                'quote_volume': float(kline['q']),
                'trades': int(kline['n'])
            }
            self.stats['total_updates'] += 1
            logger.debug(
                f"📊 {symbol.upper()} K線更新: "
                f"O={kline['o']}, H={kline['h']}, L={kline['l']}, C={kline['c']}"
            )
    
    def get_latest_kline(self, symbol: str) -> Optional[Dict]:
        """
        獲取最新K線數據
        
        Args:
            symbol: 交易對
        
        Returns:
            最新K線數據，或None（如果無數據）
        """
        return self.kline_cache.get(symbol.lower())
    
    def get_all_klines(self) -> Dict[str, Dict]:
        """
        獲取所有幣種的最新K線
        
        Returns:
            所有K線數據的字典
        """
        return self.kline_cache.copy()
    
    def get_stats(self) -> Dict:
        """
        獲取統計數據
        
        Returns:
            統計數據字典
        """
        return {
            **self.stats,
            'cached_symbols': len(self.kline_cache),
            'running': self.running
        }
    
    async def stop(self):
        """停止所有WebSocket連線"""
        logger.info("⏸️  KlineFeed 停止中...")
        self.running = False
        
        # 取消所有WebSocket任務
        for task in self.ws_tasks:
            task.cancel()
        
        # 等待所有任務完成
        if self.ws_tasks:
            await asyncio.gather(*self.ws_tasks, return_exceptions=True)
        
        self.ws_tasks.clear()
        logger.info("✅ KlineFeed 已停止")
