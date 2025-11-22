"""
🌐 Cluster Manager - Consolidated Market Discovery, Data Management, Orchestration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Consolidated responsibilities:
- Market Universe Discovery (BinanceUniverse)
- Historical Data Management (Cold Start + Gap Filling)
- 300+ Pair Orchestration
- Signal Generation & Aggregation
"""

import asyncio
import os
from typing import Dict, List, Optional, Callable, Any, Set
from datetime import datetime, timedelta
import logging

try:
    import polars as pl
except ImportError:
    pl = None

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# MARKET UNIVERSE - Dynamic Pair Discovery
# ════════════════════════════════════════════════════════════════════════════

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
        """Initialize BinanceUniverse"""
        self.client = binance_client
        self._pairs: Set[str] = set()
        self._last_update: Optional[datetime] = None
        self._cache_ttl = 3600  # 1 hour in seconds
        self._lock = asyncio.Lock()
    
    async def get_all_active_pairs(self) -> List[str]:
        """Fetch all active Binance Futures USDT pairs"""
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
        """Get pairs without waiting - use cached data"""
        return sorted(list(self._pairs))
    
    def get_pair_count(self) -> int:
        """Get number of pairs in universe"""
        return len(self._pairs)


# ════════════════════════════════════════════════════════════════════════════
# HISTORICAL DATA MANAGER - Cold Start Support
# ════════════════════════════════════════════════════════════════════════════

class HistoricalDataManager:
    """
    Manages historical OHLCV data for cold start
    
    Flow:
    1. Check if local cache exists
    2. If fresh (< 1 min old), load from cache
    3. If not fresh, fetch from Binance REST API
    4. Save to parquet for next startup
    5. Return Polars DataFrame
    """
    
    def __init__(self, binance_client, data_dir: str = "data"):
        """Initialize data manager"""
        self.client = binance_client
        self.data_dir = data_dir
        
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
        
        mod_time = os.path.getmtime(cache_path)
        file_age = (datetime.now() - datetime.fromtimestamp(mod_time)).total_seconds() / 60
        
        return file_age < max_age_minutes
    
    def _load_cache(self, symbol: str, interval: str = "1m"):
        """Load cached parquet file"""
        cache_path = self._get_cache_path(symbol, interval)
        
        try:
            if pl:
                df = pl.read_parquet(cache_path)
                logger.info(f"✅ Loaded cache for {symbol}: {len(df)} candles")
                return df
            return None
        except Exception as e:
            logger.warning(f"⚠️ Failed to load cache for {symbol}: {e}")
            return None
    
    def _save_cache(self, symbol: str, df, interval: str = "1m") -> bool:
        """Save dataframe to parquet cache"""
        cache_path = self._get_cache_path(symbol, interval)
        
        try:
            if pl:
                df.write_parquet(cache_path)
                logger.info(f"💾 Cached {symbol}: {len(df)} candles")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to cache {symbol}: {e}")
            return False
    
    async def ensure_history(self, symbols: List[str], interval: str = "1m", limit: int = 1000) -> Dict:
        """Ensure historical data is available for all symbols"""
        results = {}
        
        logger.info(f"❄️ Cold Start: Ensuring history for {len(symbols)} symbols...")
        
        for symbol in symbols:
            try:
                if self._is_cache_fresh(symbol, interval):
                    df = self._load_cache(symbol, interval)
                    if df is not None and len(df) > 1:
                        df = await self._fill_gaps(symbol, df, interval)
                    results[symbol] = df
                    continue
                
                logger.info(f"📥 Fetching history for {symbol}...")
                klines = await self.client.get_klines(symbol, interval, limit)
                
                if not klines:
                    logger.warning(f"⚠️ No klines for {symbol}")
                    results[symbol] = None
                    continue
                
                if pl:
                    df = pl.DataFrame({
                        'timestamp': [k[0] for k in klines],
                        'open': [float(k[1]) for k in klines],
                        'high': [float(k[2]) for k in klines],
                        'low': [float(k[3]) for k in klines],
                        'close': [float(k[4]) for k in klines],
                        'volume': [float(k[7]) for k in klines],
                    })
                    
                    df = await self._fill_gaps(symbol, df, interval)
                    self._save_cache(symbol, df, interval)
                    results[symbol] = df
                    logger.info(f"✅ {symbol}: {len(df)} candles loaded and cached")
                else:
                    results[symbol] = None
            
            except Exception as e:
                logger.error(f"❌ Failed to load history for {symbol}: {e}")
                results[symbol] = None
        
        logger.info(f"✅ Cold start complete: {len([r for r in results.values() if r is not None])}/{len(symbols)} symbols")
        return results
    
    async def _fill_gaps(self, symbol: str, df, interval: str = "1m"):
        """Auto-Gap Filling - Detect and fill missing candles"""
        if not pl or len(df) < 2:
            return df
        
        try:
            interval_ms = self._get_interval_ms(interval)
            timestamps = df['timestamp'].to_list()
            gaps_found = []
            
            for i in range(1, len(timestamps)):
                expected_gap = interval_ms
                actual_gap = timestamps[i] - timestamps[i-1]
                
                if actual_gap > expected_gap + 1000:
                    gaps_found.append((timestamps[i-1], timestamps[i]))
            
            if not gaps_found:
                return df
            
            logger.warning(f"⚠️ {symbol}: Found {len(gaps_found)} gaps in data, filling...")
            
            for gap_start, gap_end in gaps_found:
                try:
                    missing_count = (gap_end - gap_start) // interval_ms
                    
                    if missing_count > 100:
                        logger.warning(f"⚠️ Gap too large for {symbol}, skipping ({missing_count} candles)")
                        continue
                    
                    logger.info(f"📥 Fetching {missing_count} missing candles for {symbol}...")
                    missing_klines = await self.client.get_klines(symbol, interval, missing_count + 2)
                    
                    if missing_klines:
                        missing_df = pl.DataFrame({
                            'timestamp': [k[0] for k in missing_klines],
                            'open': [float(k[1]) for k in missing_klines],
                            'high': [float(k[2]) for k in missing_klines],
                            'low': [float(k[3]) for k in missing_klines],
                            'close': [float(k[4]) for k in missing_klines],
                            'volume': [float(k[7]) for k in missing_klines],
                        })
                        
                        df = pl.concat([df, missing_df]).unique(subset=['timestamp'])
                        df = df.sort('timestamp')
                        logger.info(f"✅ Gap filled for {symbol}: {len(missing_klines)} candles added")
                
                except Exception as e:
                    logger.warning(f"⚠️ Failed to fill gap for {symbol}: {e}")
            
            return df
        
        except Exception as e:
            logger.error(f"❌ Gap filling failed for {symbol}: {e}")
            return df
    
    @staticmethod
    def _get_interval_ms(interval: str) -> int:
        """Convert interval string to milliseconds"""
        mapping = {
            '1m': 60_000,
            '5m': 300_000,
            '15m': 900_000,
            '1h': 3_600_000,
            '4h': 14_400_000,
            '1d': 86_400_000,
        }
        return mapping.get(interval, 60_000)


# ════════════════════════════════════════════════════════════════════════════
# CLUSTER MANAGER - Central Orchestrator
# ════════════════════════════════════════════════════════════════════════════

class ClusterManager:
    """
    Manages the entire SMC-Quant Sharded Engine
    
    Responsibilities:
    1. Discover all 300+ trading pairs via BinanceUniverse
    2. Manage historical data via HistoricalDataManager
    3. Process M1 candles through the analysis pipeline
    4. Generate trading signals
    5. Monitor system health
    """
    
    def __init__(self, binance_client: Any, on_signal_callback: Optional[Callable] = None):
        """Initialize ClusterManager"""
        self.client = binance_client
        self.on_signal_callback = on_signal_callback
        
        # Components
        self.universe = BinanceUniverse(binance_client)
        self.data_manager = HistoricalDataManager(binance_client)
        
        # Try to import dependencies
        try:
            from src.core.smc_engine import SMCEngine
            self.smc_engine = SMCEngine()
        except Exception:
            logger.warning("⚠️ SMCEngine not available")
            self.smc_engine = None
        
        try:
            from src.ml.feature_engineer import get_feature_engineer
            self.feature_engineer = get_feature_engineer()
        except Exception:
            logger.warning("⚠️ FeatureEngineer not available")
            self.feature_engineer = None
        
        try:
            from src.ml.hybrid_learner import get_predictor
            self.predictor = get_predictor()
        except Exception:
            logger.warning("⚠️ Predictor not available")
            self.predictor = None
        
        try:
            from src.core.risk_manager import get_risk_manager
            self.risk_manager = get_risk_manager()
        except Exception:
            logger.warning("⚠️ RiskManager not available")
            self.risk_manager = None
        
        # State
        self.running = False
        self.pairs: List[str] = []
        self.kline_buffers: Dict[str, List] = {}
        self.warmup_complete = False
        
        self.stats = {
            'klines_processed': 0,
            'signals_generated': 0,
            'trades_executed': 0,
            'start_time': None
        }
        
        logger.info("✅ ClusterManager initialized")
    
    async def start(self):
        """Start the cluster"""
        try:
            self.running = True
            self.stats['start_time'] = datetime.utcnow()
            
            logger.info("🚀 Cluster starting...")
            
            logger.info("📍 Discovering market universe...")
            self.pairs = await self.universe.get_all_active_pairs()
            logger.info(f"✅ Found {len(self.pairs)} pairs")
            
            for pair in self.pairs:
                self.kline_buffers[pair] = []
            
            logger.info("❄️ Cold Start: Fetching historical data...")
            historical_data = await self.data_manager.ensure_history(self.pairs, interval='1m', limit=1000)
            
            for symbol, df in historical_data.items():
                if df is not None:
                    try:
                        klines = []
                        for row in df.iter_rows(named=True):
                            klines.append({
                                'symbol': symbol,
                                'open': row['open'],
                                'high': row['high'],
                                'low': row['low'],
                                'close': row['close'],
                                'volume': row['volume'],
                                'time': row['timestamp']
                            })
                        self.kline_buffers[symbol] = klines
                    except Exception as e:
                        logger.warning(f"⚠️ Could not pre-populate {symbol}: {e}")
            
            self.warmup_complete = True
            logger.info("✅ Cold start complete")
            logger.info("🔄 Cluster ready to receive market data")
        
        except Exception as e:
            logger.error(f"❌ Cluster start failed: {e}")
            self.running = False
    
    async def on_kline_close(self, kline: Dict):
        """Process closed M1 candle"""
        if not self.running:
            return
        
        try:
            symbol = kline.get('symbol', '').lower()
            
            if symbol not in self.kline_buffers:
                self.kline_buffers[symbol] = []
            
            self.kline_buffers[symbol].append(kline)
            
            if len(self.kline_buffers[symbol]) > 100:
                self.kline_buffers[symbol] = self.kline_buffers[symbol][-100:]
            
            MIN_BUFFER_SIZE = 20
            MIN_BUFFER_WARMUP = 5
            
            min_required = MIN_BUFFER_WARMUP if not self.warmup_complete else MIN_BUFFER_SIZE
            
            if len(self.kline_buffers[symbol]) < min_required:
                return
            
            self.stats['klines_processed'] += 1
            
            await self._process_signal(symbol)
        
        except Exception as e:
            logger.error(f"❌ Kline processing error: {e}")
    
    async def _process_signal(self, symbol: str):
        """Process a single symbol for trading signal"""
        klines = self.kline_buffers.get(symbol, [])
        if not klines or len(klines) < 5:
            return
        
        try:
            if not self.smc_engine or not self.feature_engineer or not self.predictor:
                return
            
            smc_results = {
                'fvg': self.smc_engine.detect_fvg(klines[-5:]),
                'order_block': self.smc_engine.detect_order_block(klines),
                'liquidity_sweep': self.smc_engine.detect_liquidity_sweep(klines),
                'structure': self.smc_engine.detect_structure(klines)
            }
            
            features = self.feature_engineer.compute_features(klines, smc_results)
            
            confidence = self.predictor.predict_confidence(features)
            
            if confidence < 0.60:
                return
            
            balance = 10000.0
            
            if self.risk_manager:
                position_size = self.risk_manager.calculate_size(confidence, balance)
            else:
                position_size = 100.0
            
            if position_size == 0:
                return
            
            signal = {
                'symbol': symbol,
                'confidence': confidence,
                'position_size': position_size,
                'smc_patterns': smc_results,
                'features': features,
                'timestamp': datetime.utcnow()
            }
            
            self.stats['signals_generated'] += 1
            
            logger.info(
                f"📊 Signal: {symbol} @ {confidence:.2%} confidence, "
                f"Size: {position_size:.2f} USDT"
            )
            
            if self.on_signal_callback:
                try:
                    await self.on_signal_callback(signal)
                    self.stats['trades_executed'] += 1
                except Exception as e:
                    logger.error(f"❌ Signal callback error: {e}")
        
        except Exception as e:
            logger.error(f"❌ Signal processing error for {symbol}: {e}")
    
    async def process_batch_signals(self, symbols: List[str]):
        """Process multiple symbols in parallel"""
        tasks = []
        for symbol in symbols:
            if symbol in self.kline_buffers and len(self.kline_buffers[symbol]) > 0:
                tasks.append(self._process_signal(symbol))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop(self):
        """Stop the cluster"""
        logger.info("⏸️ Cluster stopping...")
        self.running = False
        logger.info("✅ Cluster stopped")
    
    def get_stats(self) -> Dict:
        """Get cluster statistics"""
        uptime = (datetime.utcnow() - self.stats['start_time']).total_seconds() if self.stats['start_time'] else 0
        
        return {
            'running': self.running,
            'pairs': len(self.pairs),
            'uptime_seconds': uptime,
            'klines_processed': self.stats['klines_processed'],
            'signals_generated': self.stats['signals_generated'],
            'trades_executed': self.stats['trades_executed']
        }


# Global singletons
_universe: Optional[BinanceUniverse] = None
_data_manager: Optional[HistoricalDataManager] = None


def get_universe(binance_client) -> BinanceUniverse:
    """Get or create the global universe instance"""
    global _universe
    if _universe is None:
        _universe = BinanceUniverse(binance_client)
    return _universe


def get_data_manager(binance_client, data_dir: str = "data") -> HistoricalDataManager:
    """Get or create global data manager"""
    global _data_manager
    if _data_manager is None:
        _data_manager = HistoricalDataManager(binance_client, data_dir)
    return _data_manager
