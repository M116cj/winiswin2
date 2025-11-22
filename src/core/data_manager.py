"""
❄️ Historical Data Manager - Cold Start Support
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Auto-fetch and cache historical K-lines for cold start initialization
On startup, fetch 1000+ candles for all pairs to warm up SMCEngine
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import polars as pl

logger = logging.getLogger(__name__)


class HistoricalDataManager:
    """
    Manages historical OHLCV data for cold start
    
    Flow:
    1. Check if local cache exists (data/{symbol}_{interval}.parquet)
    2. If fresh (< 1 min old), load from cache
    3. If not fresh, fetch from Binance REST API
    4. Save to parquet for next startup
    5. Return Polars DataFrame
    """
    
    def __init__(self, binance_client, data_dir: str = "data"):
        """Initialize data manager"""
        self.client = binance_client
        self.data_dir = data_dir
        
        # Create data directory if needed
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"✅ HistoricalDataManager initialized (cache dir: {data_dir})")
    
    def _get_cache_path(self, symbol: str, interval: str = "1m") -> str:
        """Get cache file path"""
        return os.path.join(self.data_dir, f"{symbol}_{interval}.parquet")
    
    def _is_cache_fresh(self, symbol: str, interval: str = "1m", max_age_minutes: int = 1) -> bool:
        """Check if cache file exists and is fresh"""
        cache_path = self._get_cache_path(symbol, interval)
        
        if not os.path.exists(cache_path):
            return False
        
        # Check file age
        mod_time = os.path.getmtime(cache_path)
        file_age = (datetime.now() - datetime.fromtimestamp(mod_time)).total_seconds() / 60
        
        return file_age < max_age_minutes
    
    def _load_cache(self, symbol: str, interval: str = "1m") -> Optional[pl.DataFrame]:
        """Load cached parquet file"""
        cache_path = self._get_cache_path(symbol, interval)
        
        try:
            df = pl.read_parquet(cache_path)
            logger.info(f"✅ Loaded cache for {symbol}: {len(df)} candles")
            return df
        except Exception as e:
            logger.warning(f"⚠️ Failed to load cache for {symbol}: {e}")
            return None
    
    def _save_cache(self, symbol: str, df: pl.DataFrame, interval: str = "1m") -> bool:
        """Save dataframe to parquet cache"""
        cache_path = self._get_cache_path(symbol, interval)
        
        try:
            df.write_parquet(cache_path)
            logger.info(f"💾 Cached {symbol}: {len(df)} candles")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to cache {symbol}: {e}")
            return False
    
    async def ensure_history(
        self,
        symbols: List[str],
        interval: str = "1m",
        limit: int = 1000
    ) -> Dict[str, Optional[pl.DataFrame]]:
        """
        Ensure historical data is available for all symbols
        
        Args:
            symbols: List of trading symbols
            interval: Candle interval (1m, 5m, etc.)
            limit: Number of candles to fetch
        
        Returns:
            {symbol: DataFrame | None}
        """
        results = {}
        
        logger.info(f"❄️ Cold Start: Ensuring history for {len(symbols)} symbols...")
        
        for symbol in symbols:
            try:
                # Check cache first
                if self._is_cache_fresh(symbol, interval):
                    df = self._load_cache(symbol, interval)
                    results[symbol] = df
                    continue
                
                # Fetch from Binance
                logger.info(f"📥 Fetching history for {symbol}...")
                klines = await self.client.get_klines(symbol, interval, limit)
                
                if not klines:
                    logger.warning(f"⚠️ No klines for {symbol}")
                    results[symbol] = None
                    continue
                
                # Convert to Polars DataFrame
                df = pl.DataFrame({
                    'timestamp': [k[0] for k in klines],
                    'open': [float(k[1]) for k in klines],
                    'high': [float(k[2]) for k in klines],
                    'low': [float(k[3]) for k in klines],
                    'close': [float(k[4]) for k in klines],
                    'volume': [float(k[7]) for k in klines],
                })
                
                # Save to cache
                self._save_cache(symbol, df, interval)
                results[symbol] = df
                
                logger.info(f"✅ {symbol}: {len(df)} candles loaded and cached")
            
            except Exception as e:
                logger.error(f"❌ Failed to load history for {symbol}: {e}")
                results[symbol] = None
        
        logger.info(f"✅ Cold start complete: {len([r for r in results.values() if r is not None])}/{len(symbols)} symbols")
        return results
    
    def get_dataframe_for_smc(self, symbol: str, interval: str = "1m") -> Optional[pl.DataFrame]:
        """
        Get historical dataframe for SMC analysis
        (convenience method)
        """
        if self._is_cache_fresh(symbol, interval):
            return self._load_cache(symbol, interval)
        return None


# Global instance
_data_manager: Optional[HistoricalDataManager] = None


def get_data_manager(binance_client, data_dir: str = "data") -> HistoricalDataManager:
    """Get or create global data manager"""
    global _data_manager
    if _data_manager is None:
        _data_manager = HistoricalDataManager(binance_client, data_dir)
    return _data_manager
