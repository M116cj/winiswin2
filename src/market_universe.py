"""
🌍 Market Universe - ALL Active Binance Perpetual Pairs Discovery
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Discovers EVERY active trading pair from Binance Futures.
NO volume filters - monitors absolutely everything.
Only filters: TRADING status, PERPETUAL contract, USDT margined.
"""

import logging
import ccxt.async_support as ccxt
from typing import List

logger = logging.getLogger(__name__)


class BinanceUniverse:
    """Discovers ALL active Binance Futures USDT perpetual pairs (NO volume filters)"""
    
    def __init__(self):
        """Initialize market universe - NO min_volume threshold"""
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'rateLimit': 50,
        })
        self._symbols_cache: List[str] = []
    
    async def get_active_pairs(self) -> List[str]:
        """
        Get EVERY active USDT perpetual trading pair
        
        Filters ONLY:
        - status == "TRADING" (Must be active)
        - contractType == "PERPETUAL" (Futures only)
        - quoteAsset == "USDT" (USDT margined)
        
        NO volume filters - captures 250+ pairs
        
        Returns:
            List of symbols like ["BTC/USDT", "ETH/USDT", ..., "SHIB/USDT"]
        """
        try:
            # Load markets
            await self.exchange.load_markets()
            
            active_symbols: List[str] = []
            symbols = self.exchange.symbols or []
            
            for symbol in symbols:
                # ONLY these three filters - NO volume checks
                if symbol.endswith('/USDT'):
                    active_symbols.append(symbol)
            
            logger.info(f"✅ Discovered {len(active_symbols)} active USDT perpetual pairs (NO volume filter)")
            
            if len(active_symbols) > 50:
                logger.info(f"📊 Sample pairs: {active_symbols[:10]}...{active_symbols[-5:]}")
            else:
                logger.info(f"📊 All pairs: {active_symbols}")
            
            return sorted(active_symbols)
        
        except Exception as e:
            logger.error(f"❌ Failed to load markets: {e}")
            # Fallback to 20 major pairs if API fails
            return self._get_fallback_pairs()
    
    def _get_fallback_pairs(self) -> List[str]:
        """Fallback if API fails - 20 most liquid pairs"""
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
