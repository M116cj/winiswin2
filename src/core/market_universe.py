"""
🌍 Market Universe - Dynamic Pair Discovery
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Discover and cache all active Binance Futures USDT perpetual pairs
Constraint: Cache for 1 hour to avoid API limits
"""

import asyncio
import time
from typing import List, Set, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class BinanceUniverse:
    """
    Manages the universe of tradable Binance Futures pairs (USDT perpetual)
    
    Features:
    - Fetches all active trading pairs from exchangeInfo
    - Filters for PERPETUAL contracts with USDT quote
    - Caches results for 1 hour
    - Thread-safe access
    """
    
    def __init__(self, binance_client):
        """
        Initialize BinanceUniverse
        
        Args:
            binance_client: BinanceClient instance for API calls
        """
        self.client = binance_client
        self._pairs: Set[str] = set()
        self._last_update: Optional[datetime] = None
        self._cache_ttl = 3600  # 1 hour in seconds
        self._lock = asyncio.Lock()
    
    async def get_all_active_pairs(self) -> List[str]:
        """
        Fetch all active Binance Futures USDT pairs
        
        Returns: List of symbols (e.g., ['BTCUSDT', 'ETHUSDT', ...])
        """
        async with self._lock:
            # Check if cache is still valid
            if self._pairs and self._last_update:
                elapsed = (datetime.utcnow() - self._last_update).total_seconds()
                if elapsed < self._cache_ttl:
                    logger.debug(f"📦 Using cached universe ({len(self._pairs)} pairs, {elapsed:.0f}s old)")
                    return sorted(list(self._pairs))
            
            # Fetch fresh data from exchange
            logger.info("🌍 Fetching Binance Futures universe...")
            try:
                exchange_info = await self.client.get_exchange_info()
                
                if not exchange_info or 'symbols' not in exchange_info:
                    logger.warning("⚠️ No exchange info returned, using cached pairs")
                    return sorted(list(self._pairs)) if self._pairs else []
                
                # Filter for PERPETUAL + USDT
                active_pairs = set()
                for symbol_info in exchange_info['symbols']:
                    if (symbol_info.get('status') == 'TRADING' and
                        symbol_info.get('contractType') == 'PERPETUAL' and
                        symbol_info.get('quoteAsset') == 'USDT'):
                        active_pairs.add(symbol_info['symbol'].lower())
                
                self._pairs = active_pairs
                self._last_update = datetime.utcnow()
                
                logger.info(f"✅ Universe updated: {len(self._pairs)} active pairs")
                logger.debug(f"   Sample: {sorted(list(self._pairs))[:10]}")
                
                return sorted(list(self._pairs))
            
            except Exception as e:
                logger.error(f"❌ Failed to fetch universe: {e}")
                return sorted(list(self._pairs)) if self._pairs else []
    
    async def refresh_universe(self):
        """Force refresh the universe (bypass cache)"""
        async with self._lock:
            self._last_update = None
            await self.get_all_active_pairs()
    
    def get_cached_pairs(self) -> List[str]:
        """Get pairs without waiting (blocking) - use cached data"""
        return sorted(list(self._pairs))
    
    def get_pair_count(self) -> int:
        """Get number of pairs in universe"""
        return len(self._pairs)


# Global singleton instance
_universe: Optional[BinanceUniverse] = None


def get_universe(binance_client) -> BinanceUniverse:
    """Get or create the global universe instance"""
    global _universe
    if _universe is None:
        _universe = BinanceUniverse(binance_client)
    return _universe
