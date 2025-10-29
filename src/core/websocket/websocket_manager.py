"""
WebSocketManager v3.17.2+ - 統一WebSocket管理器
職責：統一管理KlineFeed、AccountFeed等多種WebSocket連線
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any

from src.core.websocket.kline_feed import KlineFeed
from src.core.websocket.account_feed import AccountFeed

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    WebSocketManager - 統一WebSocket管理器
    
    職責：
    1. 管理多種WebSocket連線（K線、帳戶等）
    2. 提供統一的數據查詢接口
    3. 協調生命週期管理（start/stop）
    4. 預留多交易所擴展點
    
    架構（v3.17.2+）：
    ┌──────────────────────────────────┐
    │      WebSocketManager            │
    ├──────────────────────────────────┤
    │ • KlineFeed (即時K線)            │
    │ • AccountFeed (即時倉位)         │
    │ • [預留] PriceFeed (即時價格)    │
    └──────────────────────────────────┘
    """
    
    def __init__(
        self,
        symbols: List[str],
        binance_client: Any,
        kline_interval: str = "1m",
        enable_kline_feed: bool = True,
        enable_account_feed: bool = True
    ):
        """
        初始化WebSocketManager
        
        Args:
            symbols: 交易對列表
            binance_client: Binance客戶端
            kline_interval: K線週期（默認1m）
            enable_kline_feed: 是否啟用K線Feed
            enable_account_feed: 是否啟用帳戶Feed
        """
        self.symbols = symbols
        self.binance_client = binance_client
        self.running = False
        
        # 初始化各種Feed
        self.kline_feed: Optional[KlineFeed] = None
        self.account_feed: Optional[AccountFeed] = None
        
        if enable_kline_feed:
            self.kline_feed = KlineFeed(
                symbols=symbols,
                interval=kline_interval
            )
        
        if enable_account_feed:
            self.account_feed = AccountFeed(
                binance_client=binance_client
            )
        
        logger.info("=" * 80)
        logger.info("✅ WebSocketManager v3.17.2+ 初始化完成")
        logger.info(f"   📊 監控幣種數量: {len(symbols)}")
        logger.info(f"   📡 K線Feed: {'啟用' if enable_kline_feed else '停用'}")
        logger.info(f"   📡 帳戶Feed: {'啟用' if enable_account_feed else '停用'}")
        logger.info("=" * 80)
    
    async def start(self):
        """啟動所有WebSocket Feed（非阻塞）"""
        if self.running:
            logger.warning("⚠️ WebSocketManager 已在運行中")
            return
        
        self.running = True
        logger.info("🚀 WebSocketManager 啟動中...")
        
        tasks = []
        
        # 啟動K線Feed
        if self.kline_feed:
            tasks.append(self.kline_feed.start())
        
        # 啟動帳戶Feed
        if self.account_feed:
            tasks.append(self.account_feed.start())
        
        # 並行啟動所有Feed
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("✅ WebSocketManager 已啟動")
    
    # ==================== K線數據接口 ====================
    
    def get_kline(self, symbol: str) -> Optional[Dict]:
        """
        獲取最新K線數據
        
        Args:
            symbol: 交易對
        
        Returns:
            最新K線數據，或None（如果無數據）
        """
        if not self.kline_feed:
            return None
        return self.kline_feed.get_latest_kline(symbol)
    
    def get_all_klines(self) -> Dict[str, Dict]:
        """
        獲取所有幣種的最新K線
        
        Returns:
            所有K線數據的字典
        """
        if not self.kline_feed:
            return {}
        return self.kline_feed.get_all_klines()
    
    # ==================== 帳戶/倉位數據接口 ====================
    
    def get_account_position(self, symbol: str) -> Optional[Dict]:
        """
        獲取即時倉位數據
        
        Args:
            symbol: 交易對
        
        Returns:
            倉位數據，或None（如果無倉位）
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
    
    # ==================== 價格數據接口（向後兼容）====================
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        獲取最新價格（向後兼容WebSocketMonitor接口）
        
        Args:
            symbol: 交易對
        
        Returns:
            最新價格，或None
        """
        # 優先使用K線的收盤價
        if self.kline_feed:
            kline = self.kline_feed.get_latest_kline(symbol)
            if kline:
                return kline.get('close')
        
        # 備援：使用帳戶Feed的倉位數據（如果有）
        if self.account_feed:
            position = self.account_feed.get_position(symbol)
            if position:
                return position.get('entry_price')
        
        return None
    
    def get_liquidity_score(self, symbol: str) -> float:
        """
        計算流動性評分（基於K線成交量）
        
        Args:
            symbol: 交易對
        
        Returns:
            流動性評分（0-100）
        """
        kline = self.get_kline(symbol)
        if not kline:
            return 0.0
        
        # 基於成交量計算流動性評分
        volume = kline.get('volume', 0)
        quote_volume = kline.get('quote_volume', 0)
        trades = kline.get('trades', 0)
        
        # 簡單評分邏輯（可以後續優化）
        score = 0.0
        if quote_volume > 1000000:  # >100萬USDT成交量
            score += 50
        if trades > 1000:  # >1000筆交易
            score += 30
        if volume > 0:
            score += 20
        
        return min(score, 100.0)
    
    def get_spread_bps(self, symbol: str) -> Optional[float]:
        """
        獲取買賣價差（基點）
        
        注意：目前K線數據不包含買賣價差，返回None
        後續可以通過bookTicker Feed實現
        
        Args:
            symbol: 交易對
        
        Returns:
            買賣價差（基點），或None
        """
        # 🔥 v3.17.2+：K線Feed不提供買賣價差
        # 如需此功能，可添加PriceFeed（bookTicker）
        return None
    
    # ==================== 統計數據接口 ====================
    
    def get_stats(self) -> Dict:
        """
        獲取所有Feed的統計數據
        
        Returns:
            統計數據字典
        """
        stats = {
            'running': self.running,
            'symbols_count': len(self.symbols)
        }
        
        if self.kline_feed:
            stats['kline_feed'] = self.kline_feed.get_stats()
        
        if self.account_feed:
            stats['account_feed'] = self.account_feed.get_stats()
        
        return stats
    
    # ==================== 生命週期管理 ====================
    
    async def stop(self):
        """停止所有WebSocket Feed"""
        logger.info("⏸️  WebSocketManager 停止中...")
        self.running = False
        
        tasks = []
        
        # 停止K線Feed
        if self.kline_feed:
            tasks.append(self.kline_feed.stop())
        
        # 停止帳戶Feed
        if self.account_feed:
            tasks.append(self.account_feed.stop())
        
        # 並行停止所有Feed
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("✅ WebSocketManager 已停止")
