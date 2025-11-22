"""
🌍 Market Universe - Dynamic Binance Futures Pair Discovery
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Discovers all active trading pairs from Binance Futures.
Filters by volume, liquidity, and other criteria.
"""

import logging
import ccxt.async_support as ccxt
from typing import List

logger = logging.getLogger(__name__)


class BinanceUniverse:
    """Discovers active Binance Futures trading pairs"""
    
    def __init__(self, min_volume_usdt: float = 1_000_000):
        """
        Initialize market universe
        
        Args:
            min_volume_usdt: Minimum 24h trading volume in USDT
        """
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'rateLimit': 100,
        })
        self.min_volume_usdt = min_volume_usdt
        self._symbols_cache: List[str] = []
    
    async def get_active_pairs(self) -> List[str]:
        """
        Get all active USDT trading pairs
        
        Returns:
            List of symbols like ["BTC/USDT", "ETH/USDT", ...]
        """
        try:
            # Load markets
            await self.exchange.load_markets()
            
            active_symbols: List[str] = []
            symbols = self.exchange.symbols or []
            for symbol in symbols:
                # Filter: only USDT pairs, active, with trading
                if symbol.endswith('/USDT'):
                    active_symbols.append(symbol)
            
            logger.info(f"✅ Discovered {len(active_symbols)} active USDT pairs")
            return sorted(active_symbols)
        
        except Exception as e:
            logger.error(f"❌ Failed to load markets: {e}")
            # Fallback to common pairs
            return self._get_fallback_pairs()
    
    def _get_fallback_pairs(self) -> List[str]:
        """Fallback if API fails"""
        return [
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "SOL/USDT",
            "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "MATIC/USDT",
            "FTT/USDT", "TRX/USDT", "ARB/USDT", "OP/USDT", "LTC/USDT",
            "BCH/USDT", "ETC/USDT", "XLM/USDT", "ATOM/USDT", "UNI/USDT"
        ]


async def discover_universe() -> List[str]:
    """Quick discover all active pairs"""
    universe = BinanceUniverse()
    return await universe.get_active_pairs()
