"""
WebSocketManager v3.17.2+ - 統一WebSocket管理器（完整升級版）
職責：動態獲取全交易對、分片管理、統一數據接口
升級：自動獲取200+ USDT合約、ShardFeed整合、PriceFeed支持
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any

from src.core.websocket.shard_feed import ShardFeed
from src.core.websocket.account_feed import AccountFeed

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    WebSocketManager - 統一WebSocket管理器（v3.17.2+完整升級版）
    
    職責：
    1. 動態獲取所有Binance USDT永續合約（200+）
    2. 使用ShardFeed進行分片管理（每片50個符號）
    3. 管理AccountFeed（帳戶/倉位監控）
    4. 提供統一的數據查詢接口
    5. 協調生命週期管理（start/stop）
    
    架構（v3.17.2+）：
    ┌──────────────────────────────────────────┐
    │      WebSocketManager v3.17.2+           │
    ├──────────────────────────────────────────┤
    │ • ShardFeed (分片管理器)                 │
    │   ├─ Shard 0: K線Feed + 價格Feed (50)   │
    │   ├─ Shard 1: K線Feed + 價格Feed (50)   │
    │   ├─ Shard N: K線Feed + 價格Feed (N)    │
    │ • AccountFeed (即時倉位)                 │
    └──────────────────────────────────────────┘
    
    優勢：
    - 100% WebSocket驅動（API權重≈0）
    - 自動獲取全市場（無需手動配置）
    - 分片防止單連線過載
    - 心跳監控 + 自動重連
    """
    
    def __init__(
        self,
        binance_client: Any,
        symbols: Optional[List[str]] = None,
        kline_interval: str = "1m",
        shard_size: int = 50,
        enable_kline_feed: bool = True,
        enable_price_feed: bool = True,
        enable_account_feed: bool = True,
        auto_fetch_symbols: bool = True
    ):
        """
        初始化WebSocketManager
        
        Args:
            binance_client: Binance客戶端
            symbols: 交易對列表（可選，如為None則自動獲取）
            kline_interval: K線週期（默認1m）
            shard_size: 分片大小（默認50）
            enable_kline_feed: 是否啟用K線Feed
            enable_price_feed: 是否啟用價格Feed（bookTicker）
            enable_account_feed: 是否啟用帳戶Feed
            auto_fetch_symbols: 是否自動獲取全市場交易對
        """
        self.binance_client = binance_client
        self.symbols = symbols or []
        self.kline_interval = kline_interval
        self.shard_size = shard_size
        self.enable_kline_feed = enable_kline_feed
        self.enable_price_feed = enable_price_feed
        self.enable_account_feed = enable_account_feed
        self.auto_fetch_symbols = auto_fetch_symbols
        self.running = False
        
        # Feed組件
        self.shard_feed: Optional[ShardFeed] = None
        self.account_feed: Optional[AccountFeed] = None
        
        logger.info("=" * 80)
        logger.info("✅ WebSocketManager v3.17.2+ 初始化完成")
        logger.info(f"   📊 交易對模式: {'自動獲取全市場' if auto_fetch_symbols else f'{len(symbols)}個'}")
        logger.info(f"   🔀 分片大小: {shard_size}")
        logger.info(f"   📡 K線Feed: {'啟用' if enable_kline_feed else '停用'}")
        logger.info(f"   💰 價格Feed: {'啟用' if enable_price_feed else '停用'}")
        logger.info(f"   📡 帳戶Feed: {'啟用' if enable_account_feed else '停用'}")
        logger.info("=" * 80)
    
    async def _get_all_futures_symbols(self) -> List[str]:
        """
        動態獲取所有USDT永續交易對
        
        Returns:
            所有交易對列表
        """
        try:
            logger.info("🔍 正在獲取所有USDT永續合約...")
            info = await self.binance_client._request("GET", "/fapi/v1/exchangeInfo")
            
            symbols = [
                s['symbol'] for s in info['symbols']
                if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING'
            ]
            
            logger.info(f"✅ 獲取成功：{len(symbols)} 個USDT永續合約")
            return symbols
        
        except Exception as e:
            logger.error(f"❌ 獲取交易對失敗: {e}")
            return []
    
    async def start(self):
        """啟動所有WebSocket Feed（非阻塞）"""
        if self.running:
            logger.warning("⚠️ WebSocketManager 已在運行中")
            return
        
        self.running = True
        logger.info("🚀 WebSocketManager v3.17.2+ 啟動中...")
        
        # 1. 動態獲取交易對（如果需要）
        if self.auto_fetch_symbols and not self.symbols:
            self.symbols = await self._get_all_futures_symbols()
            if not self.symbols:
                logger.warning("⚠️ 未獲取到交易對，使用空列表")
                self.symbols = []
        
        tasks = []
        
        # 2. 啟動ShardFeed（K線+價格分片管理）
        if self.symbols and (self.enable_kline_feed or self.enable_price_feed):
            self.shard_feed = ShardFeed(
                all_symbols=self.symbols,
                shard_size=self.shard_size,
                enable_kline=self.enable_kline_feed,
                enable_price=self.enable_price_feed,
                kline_interval=self.kline_interval
            )
            tasks.append(self.shard_feed.start())
        else:
            logger.warning("⚠️ ShardFeed: 無幣種或未啟用，跳過")
        
        # 3. 啟動AccountFeed（帳戶/倉位監控）
        if self.enable_account_feed:
            self.account_feed = AccountFeed(binance_client=self.binance_client)
            tasks.append(self.account_feed.start())
        
        # 4. 並行啟動所有Feed
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("✅ WebSocketManager已啟動（K線Feed + 價格Feed + 帳戶Feed）")
    
    # ==================== K線數據接口 ====================
    
    def get_kline(self, symbol: str) -> Optional[Dict]:
        """
        獲取最新K線數據
        
        Args:
            symbol: 交易對
        
        Returns:
            K線數據（包含時間戳），或None
        """
        if not self.shard_feed:
            return None
        return self.shard_feed.get_kline(symbol)
    
    def get_all_klines(self) -> Dict[str, Dict]:
        """
        獲取所有幣種的最新K線
        
        Returns:
            所有K線數據的字典
        """
        if not self.shard_feed:
            return {}
        return self.shard_feed.get_all_klines()
    
    # ==================== 價格數據接口 ====================
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        獲取最新價格（中間價）
        
        Args:
            symbol: 交易對
        
        Returns:
            最新價格，或None
        """
        # 優先使用PriceFeed的中間價
        if self.shard_feed:
            mid_price = self.shard_feed.get_mid_price(symbol)
            if mid_price is not None:
                return mid_price
        
        # 備援：使用K線的收盤價
        kline = self.get_kline(symbol)
        if kline:
            return kline.get('close')
        
        # 備援：使用帳戶Feed的倉位價格
        if self.account_feed:
            position = self.account_feed.get_position(symbol)
            if position:
                return position.get('entry_price')
        
        return None
    
    def get_price_data(self, symbol: str) -> Optional[Dict]:
        """
        獲取完整價格數據（bid/ask/spread）
        
        Args:
            symbol: 交易對
        
        Returns:
            價格數據，或None
        """
        if not self.shard_feed:
            return None
        return self.shard_feed.get_price(symbol)
    
    def get_spread_bps(self, symbol: str) -> Optional[float]:
        """
        獲取買賣價差（基點）
        
        Args:
            symbol: 交易對
        
        Returns:
            價差（基點），或None
        """
        if not self.shard_feed:
            return None
        return self.shard_feed.get_spread_bps(symbol)
    
    def get_liquidity_score(self, symbol: str) -> float:
        """
        計算流動性評分（基於成交量+價差）
        
        Args:
            symbol: 交易對
        
        Returns:
            流動性評分（0-100）
        """
        score = 0.0
        
        # 1. 基於K線成交量
        kline = self.get_kline(symbol)
        if kline:
            quote_volume = kline.get('quote_volume', 0)
            trades = kline.get('trades', 0)
            
            if quote_volume > 1000000:  # >100萬USDT成交量
                score += 40
            elif quote_volume > 100000:  # >10萬USDT
                score += 20
            
            if trades > 1000:  # >1000筆交易
                score += 20
            elif trades > 100:  # >100筆
                score += 10
        
        # 2. 基於價差（越小越好）
        spread_bps = self.get_spread_bps(symbol)
        if spread_bps is not None:
            if spread_bps < 5:  # 價差<5bps（非常緊密）
                score += 40
            elif spread_bps < 10:  # 價差<10bps
                score += 20
            elif spread_bps < 20:  # 價差<20bps
                score += 10
        
        return min(score, 100.0)
    
    # ==================== 帳戶/倉位數據接口 ====================
    
    def get_account_position(self, symbol: str) -> Optional[Dict]:
        """
        獲取即時倉位數據
        
        Args:
            symbol: 交易對
        
        Returns:
            倉位數據，或None
        """
        if not self.account_feed:
            return None
        return self.account_feed.get_position(symbol)
    
    def get_all_positions(self) -> Dict[str, Dict]:
        """
        獲取所有倉位
        
        Returns:
            所有倉位數據的字典
        """
        if not self.account_feed:
            return {}
        return self.account_feed.get_all_positions()
    
    def get_account_balance(self, asset: str = 'USDT') -> Optional[Dict]:
        """
        獲取帳戶餘額
        
        Args:
            asset: 資產名稱
        
        Returns:
            餘額數據，或None
        """
        if not self.account_feed:
            return None
        return self.account_feed.get_account_balance(asset)
    
    # ==================== 統計數據接口 ====================
    
    def get_stats(self) -> Dict:
        """
        獲取所有Feed的統計數據
        
        Returns:
            統計數據字典
        """
        stats = {
            'running': self.running,
            'symbols_count': len(self.symbols),
            'shard_size': self.shard_size
        }
        
        if self.shard_feed:
            stats['shard_feed'] = self.shard_feed.get_stats()
        
        if self.account_feed:
            stats['account_feed'] = self.account_feed.get_stats()
        
        return stats
    
    # ==================== 生命週期管理 ====================
    
    async def stop(self):
        """停止所有WebSocket Feed"""
        logger.info("⏸️  WebSocketManager 停止中...")
        self.running = False
        
        tasks = []
        
        # 停止ShardFeed
        if self.shard_feed:
            tasks.append(self.shard_feed.stop())
        
        # 停止AccountFeed
        if self.account_feed:
            tasks.append(self.account_feed.stop())
        
        # 並行停止所有Feed
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("✅ WebSocketManager 已停止")
