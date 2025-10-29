"""
ShardFeed v3.17.2+ - WebSocket分片管理器
職責：管理多個WebSocket分片，避免單一連線過載
"""

import asyncio
import logging
from typing import Dict, List, Optional

from src.core.websocket.kline_feed import KlineFeed
from src.core.websocket.price_feed import PriceFeed

logger = logging.getLogger(__name__)


class ShardFeed:
    """
    ShardFeed - WebSocket分片管理器
    
    職責：
    1. 將大量交易對分片（每片≤50個符號）
    2. 為每個分片創建獨立的WebSocket連線
    3. 統一管理所有分片的生命週期
    4. 提供統一的數據查詢接口
    
    設計原則：
    - 符合Binance最佳實務（建議≤100 streams/連線）
    - 避免單一連線處理200+訊息的CPU瓶頸
    - 提供高可用性（單一分片失敗不影響其他分片）
    
    架構：
    ┌─────────────────────────────────┐
    │       ShardFeed (Manager)       │
    ├─────────────────────────────────┤
    │ • Shard 0: 50 symbols           │
    │ • Shard 1: 50 symbols           │
    │ • Shard 2: 50 symbols           │
    │ • Shard N: remaining symbols    │
    └─────────────────────────────────┘
    """
    
    def __init__(
        self,
        all_symbols: List[str],
        shard_size: int = 50,
        enable_kline: bool = True,
        enable_price: bool = True,
        kline_interval: str = "1m"
    ):
        """
        初始化ShardFeed
        
        Args:
            all_symbols: 所有交易對列表
            shard_size: 每個分片的符號數量（默認50）
            enable_kline: 是否啟用K線Feed
            enable_price: 是否啟用價格Feed
            kline_interval: K線週期（默認1m）
        """
        self.all_symbols = all_symbols
        self.shard_size = shard_size
        self.enable_kline = enable_kline
        self.enable_price = enable_price
        self.kline_interval = kline_interval
        self.running = False
        
        # 分片列表
        self.shards = self._create_shards()
        
        # Feed列表
        self.kline_shards: List[KlineFeed] = []
        self.price_shards: List[PriceFeed] = []
        
        logger.info("=" * 80)
        logger.info("✅ ShardFeed 初始化完成")
        logger.info(f"   📊 總幣種數量: {len(all_symbols)}")
        logger.info(f"   🔀 分片數量: {len(self.shards)}")
        logger.info(f"   📦 分片大小: {shard_size}")
        logger.info(f"   📡 K線Feed: {'啟用' if enable_kline else '停用'}")
        logger.info(f"   💰 價格Feed: {'啟用' if enable_price else '停用'}")
        logger.info("=" * 80)
    
    def _create_shards(self) -> List[List[str]]:
        """
        將交易對分片
        
        Returns:
            分片列表，每個分片包含≤shard_size個符號
        """
        shards = []
        for i in range(0, len(self.all_symbols), self.shard_size):
            shard = self.all_symbols[i:i + self.shard_size]
            shards.append(shard)
            logger.debug(
                f"🔀 Shard {len(shards) - 1}: "
                f"{len(shard)} symbols ({shard[0]} ... {shard[-1]})"
            )
        return shards
    
    async def start(self):
        """啟動所有分片（並行）"""
        if self.running:
            logger.warning("⚠️ ShardFeed 已在運行中")
            return
        
        self.running = True
        logger.info(f"🚀 ShardFeed 啟動中... ({len(self.shards)} 個分片)")
        
        tasks = []
        
        # 為每個分片創建K線Feed
        if self.enable_kline:
            for shard_id, symbols in enumerate(self.shards):
                kline_feed = KlineFeed(
                    symbols=symbols,
                    interval=self.kline_interval,
                    shard_id=shard_id  # 🔥 修復：正確傳遞shard_id
                )
                self.kline_shards.append(kline_feed)
                tasks.append(kline_feed.start())
        
        # 為每個分片創建價格Feed
        if self.enable_price:
            for shard_id, symbols in enumerate(self.shards):
                price_feed = PriceFeed(
                    symbols=symbols,
                    shard_id=shard_id
                )
                self.price_shards.append(price_feed)
                tasks.append(price_feed.start())
        
        # 並行啟動所有Feed
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(
            f"✅ ShardFeed 已啟動 "
            f"(K線分片:{len(self.kline_shards)}, "
            f"價格分片:{len(self.price_shards)})"
        )
    
    # ==================== 統一數據查詢接口 ====================
    
    def get_kline(self, symbol: str) -> Optional[Dict]:
        """
        獲取K線數據（跨所有分片查詢）
        
        Args:
            symbol: 交易對
        
        Returns:
            K線數據，或None
        """
        for kline_feed in self.kline_shards:
            kline = kline_feed.get_latest_kline(symbol)
            if kline:
                return kline
        return None
    
    def get_price(self, symbol: str) -> Optional[Dict]:
        """
        獲取價格數據（跨所有分片查詢）
        
        Args:
            symbol: 交易對
        
        Returns:
            價格數據，或None
        """
        for price_feed in self.price_shards:
            price = price_feed.get_price(symbol)
            if price:
                return price
        return None
    
    def get_mid_price(self, symbol: str) -> Optional[float]:
        """
        獲取中間價
        
        Args:
            symbol: 交易對
        
        Returns:
            中間價，或None
        """
        for price_feed in self.price_shards:
            mid_price = price_feed.get_mid_price(symbol)
            if mid_price is not None:
                return mid_price
        return None
    
    def get_spread_bps(self, symbol: str) -> Optional[float]:
        """
        獲取買賣價差
        
        Args:
            symbol: 交易對
        
        Returns:
            價差（基點），或None
        """
        for price_feed in self.price_shards:
            spread = price_feed.get_spread_bps(symbol)
            if spread is not None:
                return spread
        return None
    
    def get_all_klines(self) -> Dict[str, Dict]:
        """
        獲取所有K線數據（合併所有分片）
        
        Returns:
            所有K線數據的字典
        """
        all_klines = {}
        for kline_feed in self.kline_shards:
            all_klines.update(kline_feed.get_all_klines())
        return all_klines
    
    def get_all_prices(self) -> Dict[str, Dict]:
        """
        獲取所有價格數據（合併所有分片）
        
        Returns:
            所有價格數據的字典
        """
        all_prices = {}
        for price_feed in self.price_shards:
            all_prices.update(price_feed.get_all_prices())
        return all_prices
    
    # ==================== 統計與生命週期 ====================
    
    def get_stats(self) -> Dict:
        """
        獲取所有分片的統計數據
        
        Returns:
            統計數據字典
        """
        stats = {
            'running': self.running,
            'total_symbols': len(self.all_symbols),
            'total_shards': len(self.shards),
            'shard_size': self.shard_size,
            'kline_shards': [],
            'price_shards': []
        }
        
        # K線分片統計
        for kline_feed in self.kline_shards:
            stats['kline_shards'].append(kline_feed.get_stats())
        
        # 價格分片統計
        for price_feed in self.price_shards:
            stats['price_shards'].append(price_feed.get_stats())
        
        return stats
    
    async def stop(self):
        """停止所有分片"""
        logger.info("⏸️  ShardFeed 停止中...")
        self.running = False
        
        tasks = []
        
        # 停止所有K線Feed
        for kline_feed in self.kline_shards:
            tasks.append(kline_feed.stop())
        
        # 停止所有價格Feed
        for price_feed in self.price_shards:
            tasks.append(price_feed.stop())
        
        # 並行停止所有Feed
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self.kline_shards.clear()
        self.price_shards.clear()
        
        logger.info("✅ ShardFeed 已停止")
