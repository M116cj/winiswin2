"""
🌐 Cluster Manager - Orchestrate 300+ Pairs Across Multiple Shards
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Manage market universe discovery, shard orchestration, and signal aggregation
Design: Central hub coordinating all shards
"""

import asyncio
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import logging

from src.core.market_universe import get_universe
from src.core.data_manager import get_data_manager
from src.core.websocket.shard_feed import ShardFeed
from src.core.smc_engine import SMCEngine
from src.ml.feature_engineer import get_feature_engineer
from src.ml.predictor import get_predictor
from src.core.risk_manager import get_risk_manager

logger = logging.getLogger(__name__)


class ClusterManager:
    """
    Manages the entire SMC-Quant Sharded Engine
    
    Responsibilities:
    1. Discover all 300+ trading pairs via BinanceUniverse
    2. Start ShardFeed workers for each chunk
    3. On each M1 candle close:
       - Detect SMC patterns
       - Compute ML features
       - Get confidence score
       - Calculate position size
       - Signal PositionController
    4. Monitor all active trades
    5. Handle forced exits (time + stagnation)
    """
    
    def __init__(
        self,
        binance_client: Any,
        on_signal_callback: Optional[Callable] = None
    ):
        """
        Initialize ClusterManager
        
        Args:
            binance_client: Binance API client
            on_signal_callback: Callback for trading signals
        """
        self.client = binance_client
        self.on_signal_callback = on_signal_callback
        
        # Components
        self.universe = get_universe(binance_client)
        self.data_manager = get_data_manager(binance_client)  # ❄️ Cold start
        self.smc_engine = SMCEngine()
        self.feature_engineer = get_feature_engineer()
        self.predictor = get_predictor()
        self.risk_manager = get_risk_manager()
        
        # State
        self.running = False
        self.pairs: List[str] = []
        self.kline_buffers: Dict[str, List] = {}  # {symbol: klines}
        self.warmup_complete = False  # 🔥 Cold start flag
        
        # Statistics
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
            
            # 1. Discover pairs
            logger.info("📍 Discovering market universe...")
            self.pairs = await self.universe.get_all_active_pairs()
            logger.info(f"✅ Found {len(self.pairs)} pairs")
            
            # 2. Initialize kline buffers
            for pair in self.pairs:
                self.kline_buffers[pair] = []
            
            # 3. ❄️ COLD START: Fetch historical data to warm up indicators
            logger.info("❄️ Cold Start: Fetching historical data...")
            historical_data = await self.data_manager.ensure_history(self.pairs, interval='1m', limit=1000)
            
            # Pre-populate buffers with historical data
            for symbol, df in historical_data.items():
                if df is not None:
                    try:
                        # Convert Polars DataFrame to dict list
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
            
            # 4. Start processing (actual shard workers are managed by WebSocketManager)
            logger.info("🔄 Cluster ready to receive market data")
        
        except Exception as e:
            logger.error(f"❌ Cluster start failed: {e}")
            self.running = False
    
    async def on_kline_close(self, kline: Dict):
        """
        Process closed M1 candle
        
        Called by ShardFeed on each M1 close
        
        Args:
            kline: Kline data {symbol, open, high, low, close, volume, ...}
        """
        if not self.running:
            return
        
        try:
            symbol = kline.get('symbol', '').lower()
            
            # Update buffer
            if symbol not in self.kline_buffers:
                self.kline_buffers[symbol] = []
            
            self.kline_buffers[symbol].append(kline)
            
            # Keep only last 100 candles
            if len(self.kline_buffers[symbol]) > 100:
                self.kline_buffers[symbol] = self.kline_buffers[symbol][-100:]
            
            # 🔥 COLD START MITIGATION:
            # - Need ≥20 candles for reliable indicators (RSI, ATR)
            # - Use ≥5 for early testing but with caution
            MIN_BUFFER_SIZE = 20  # Production: wait for full history
            MIN_BUFFER_WARMUP = 5   # During warmup: accept earlier signals
            
            min_required = MIN_BUFFER_WARMUP if not self.warmup_complete else MIN_BUFFER_SIZE
            
            if len(self.kline_buffers[symbol]) < min_required:
                return
            
            self.stats['klines_processed'] += 1
            
            # Process signal
            await self._process_signal(symbol)
        
        except Exception as e:
            logger.error(f"❌ Kline processing error: {e}")
    
    async def _process_signal(self, symbol: str):
        """
        Process a single symbol for trading signal (CONCURRENT)
        
        Args:
            symbol: Trading symbol
        """
        klines = self.kline_buffers.get(symbol, [])
        if not klines or len(klines) < 5:
            return
        
        try:
            # 1. Detect SMC patterns (vectorized, fast)
            smc_results = {
                'fvg': self.smc_engine.detect_fvg(klines[-5:]),
                'order_block': self.smc_engine.detect_order_block(klines),
                'liquidity_sweep': self.smc_engine.detect_liquidity_sweep(klines),
                'structure': self.smc_engine.detect_structure(klines)
            }
            
            # 2. Compute ML features (polars-optimized)
            features = self.feature_engineer.compute_features(klines, smc_results)
            
            # 3. Get confidence from ML (LightGBM inference)
            confidence = self.predictor.predict_confidence(features)
            
            # Only process if high enough confidence
            if confidence < 0.60:
                return
            
            # 4. Get account balance (simplified, would come from AccountStateCache)
            balance = 10000.0  # Default, would get from real account
            
            # 5. Calculate position size
            position_size = self.risk_manager.calculate_size(confidence, balance)
            
            if position_size == 0:
                return
            
            # 6. Create signal
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
            
            # 7. Call callback
            if self.on_signal_callback:
                try:
                    await self.on_signal_callback(signal)
                    self.stats['trades_executed'] += 1
                except Exception as e:
                    logger.error(f"❌ Signal callback error: {e}")
        
        except Exception as e:
            logger.error(f"❌ Signal processing error for {symbol}: {e}")
    
    async def process_batch_signals(self, symbols: List[str]):
        """
        🔥 Process multiple symbols in parallel using asyncio.gather
        
        This enables concurrent processing of 300+ pairs across shards
        
        Args:
            symbols: List of trading symbols to process in parallel
        """
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
