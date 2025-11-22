"""
🔥 Startup Prewarmer - Cold Start Mitigation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Preload historical data and warm up ML models before live trading
Strategy: Fetch 1h of historical 1m klines to fill buffers
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class StartupPrewarmer:
    """
    Preloads historical data to warm up system
    
    Goals:
    1. Fill kline buffers with 60 historical M1 candles
    2. Warm up ML model inference (first LightGBM call)
    3. Validate all components work
    4. Ready to trade after ~30 seconds
    """
    
    def __init__(self, binance_client, cluster_manager):
        """
        Initialize prewarmer
        
        Args:
            binance_client: Binance API client
            cluster_manager: ClusterManager instance
        """
        self.client = binance_client
        self.cluster_manager = cluster_manager
        self.warmup_complete = False
        self.warmup_start_time: Optional[datetime] = None
    
    async def warmup(self, symbols: List[str], lookback_minutes: int = 60) -> bool:
        """
        Preload historical klines for startup
        
        Args:
            symbols: List of trading pairs (select top 50 for speed)
            lookback_minutes: How many minutes of history to load (default 60)
        
        Returns: True if successful, False if failed
        """
        try:
            self.warmup_start_time = datetime.utcnow()
            logger.info(
                f"🔥 Startup warmup starting...\n"
                f"   📊 Symbols: {len(symbols)}\n"
                f"   ⏱️ Lookback: {lookback_minutes} minutes"
            )
            
            # Select top symbols to speed up (don't load all 300+)
            warmup_symbols = symbols[:50] if len(symbols) > 50 else symbols
            
            # Batch fetch historical data
            klines_batch = await self._fetch_historical_batch(
                warmup_symbols,
                lookback_minutes
            )
            
            if not klines_batch:
                logger.warning("⚠️ Failed to fetch historical data")
                return False
            
            # Populate cluster buffers
            for symbol, klines in klines_batch.items():
                self.cluster_manager.kline_buffers[symbol] = klines
            
            # Warm up ML predictor (trigger one inference)
            await self._warmup_ml_predictor()
            
            # Calculate warmup time
            warmup_duration = (datetime.utcnow() - self.warmup_start_time).total_seconds()
            
            logger.info(
                f"✅ Warmup complete in {warmup_duration:.1f}s\n"
                f"   📊 Buffers: {len(klines_batch)} symbols loaded\n"
                f"   🤖 ML model: Ready\n"
                f"   🚀 System: Ready to trade"
            )
            
            self.warmup_complete = True
            return True
        
        except Exception as e:
            logger.error(f"❌ Warmup failed: {e}")
            return False
    
    async def _fetch_historical_batch(
        self,
        symbols: List[str],
        lookback_minutes: int
    ) -> Dict[str, List[Dict]]:
        """
        Fetch historical klines in parallel
        
        Args:
            symbols: Trading pairs
            lookback_minutes: History duration
        
        Returns: Dict[symbol, klines]
        """
        try:
            klines_batch = {}
            
            # Parallel fetch with batch size control
            batch_size = 10
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                tasks = [
                    self._fetch_symbol_history(symbol, lookback_minutes)
                    for symbol in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for symbol, klines in zip(batch, results):
                    if isinstance(klines, Exception):
                        logger.warning(f"⚠️ {symbol}: {klines}")
                        continue
                    if klines:
                        klines_batch[symbol] = klines
            
            logger.info(f"📊 Loaded history for {len(klines_batch)} symbols")
            return klines_batch
        
        except Exception as e:
            logger.error(f"❌ Batch fetch failed: {e}")
            return {}
    
    async def _fetch_symbol_history(
        self,
        symbol: str,
        lookback_minutes: int
    ) -> Optional[List[Dict]]:
        """
        Fetch M1 history for one symbol
        
        Args:
            symbol: Trading pair
            lookback_minutes: Duration
        
        Returns: List of klines or None
        """
        try:
            # REST API: klines endpoint
            end_time = int(datetime.utcnow().timestamp() * 1000)
            start_time = end_time - (lookback_minutes * 60 * 1000)
            
            klines = await self.client.get_klines(
                symbol=symbol.upper(),
                interval='1m',
                start_time=start_time,
                end_time=end_time,
                limit=1000  # Max limit per request
            )
            
            # Convert to dict format
            kline_dicts = []
            for kline in klines:
                kline_dict = {
                    'symbol': symbol.lower(),
                    'open': float(kline[1]),
                    'high': float(kline[2]),
                    'low': float(kline[3]),
                    'close': float(kline[4]),
                    'volume': float(kline[7]),
                    'time': int(kline[6])
                }
                kline_dicts.append(kline_dict)
            
            logger.debug(f"📊 {symbol}: Loaded {len(kline_dicts)} klines")
            return kline_dicts
        
        except Exception as e:
            logger.error(f"❌ {symbol} history fetch failed: {e}")
            return None
    
    async def _warmup_ml_predictor(self):
        """
        Trigger LightGBM model loading + one inference
        
        Purpose: Avoid first-inference latency (50-200ms) during live trading
        """
        try:
            predictor = self.cluster_manager.predictor
            
            # Dummy feature vector to warm up model
            dummy_features = {
                'market_structure': 0.0,
                'order_blocks_count': 0.0,
                'institutional_candle': 0.0,
                'liquidity_grab': 0.0,
                'fvg_size_atr': 0.0,
                'fvg_proximity': 0.0,
                'ob_proximity': 0.0,
                'atr_normalized_volume': 0.0,
                'rsi_14': 0.5,
                'momentum_atr': 0.0,
                'time_to_next_level': 0.0,
                'confidence_ensemble': 0.5,
            }
            
            # Trigger inference (loads model if not loaded)
            confidence = predictor.predict_confidence(dummy_features)
            
            logger.info(
                f"🤖 ML model warmed up\n"
                f"   Loaded: {predictor.loaded}\n"
                f"   First inference: {confidence:.3f}"
            )
        
        except Exception as e:
            logger.warning(f"⚠️ ML warmup failed: {e}")
    
    def get_warmup_status(self) -> Dict:
        """Get warmup status"""
        if not self.warmup_start_time:
            return {'warmup_complete': False, 'duration_seconds': None}
        
        duration = (datetime.utcnow() - self.warmup_start_time).total_seconds()
        
        return {
            'warmup_complete': self.warmup_complete,
            'duration_seconds': duration,
            'buffers_ready': len(self.cluster_manager.kline_buffers),
            'ml_model_ready': self.cluster_manager.predictor.loaded
        }


# Global singleton
_prewarmer: Optional[StartupPrewarmer] = None


def get_prewarmer(
    binance_client=None,
    cluster_manager=None
) -> Optional[StartupPrewarmer]:
    """Get or create global prewarmer"""
    global _prewarmer
    if _prewarmer is None:
        if binance_client and cluster_manager:
            _prewarmer = StartupPrewarmer(binance_client, cluster_manager)
    return _prewarmer
