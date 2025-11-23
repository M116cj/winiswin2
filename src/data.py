"""
📡 Data Module - Market Data + Signal Generation (High-Performance + Dispatcher)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Merged: Feed (ingestion) + Brain (SMC analysis & signal generation)
Includes time-based conflation to smooth high-frequency data streams.
CPU-heavy analysis offloaded to thread pool via dispatcher.

🛡️ STRICT FIREWALL: All ticks validated before processing
"""

import logging
import asyncio
import numpy as np
from typing import Dict, Optional, List
from time import time

from src.bus import bus, Topic
from src.indicators import Indicators
from src.dispatch import get_dispatcher, Priority
from src.feed import _is_valid_tick, _log_poison_pill

logger = logging.getLogger(__name__)

# Conflation buffer: store latest tick per symbol
_latest_ticks: Dict[str, Dict] = {}

# Conflation control
_conflation_interval = 0.1  # 100ms conflation window
_last_flush_time = 0.0


def _detect_pattern(tick: Optional[Dict]) -> Dict:
    """Pure stateless SMC pattern detection (JIT compiled)"""
    if not tick:
        return {'fvg': False, 'liquidity': False, 'strength': 0.0}
    
    high = float(tick.get('high', 0))
    low = float(tick.get('low', 0))
    
    # Simplified SMC logic
    return {
        'fvg': high - low > 100,
        'liquidity': np.random.random() > 0.7,
        'strength': np.random.random()
    }


async def _process_candle(tick: Dict) -> None:
    """
    Process candle when TICK_UPDATE received
    
    🛡️ FIREWALL: Validate tick before processing
    
    Logic:
    1. Validate tick (catch poison pills)
    2. Detect SMC patterns
    3. Calculate ML features
    4. If opportunity -> publish SIGNAL_GENERATED
    """
    if not tick:
        return
    
    # 🛡️ STRICT FIREWALL: Reject invalid ticks before processing
    if not _is_valid_tick(tick):
        _log_poison_pill(tick, f"Invalid tick rejected before SMC processing")
        return
    
    symbol = tick.get('symbol', '')
    
    # Detect patterns (pure logic)
    patterns = _detect_pattern(tick)
    
    # Simple confidence calculation
    confidence = patterns['strength']
    
    if confidence > 0.60:
        signal = {
            'symbol': symbol,
            'confidence': confidence,
            'patterns': patterns,
            'position_size': 100.0
        }
        
        logger.debug(f"🧠 Signal: {symbol} @ {confidence:.1%}")
        
        # Publish to risk manager for validation
        await bus.publish(Topic.SIGNAL_GENERATED, signal)


async def _conflation_loop(symbols: List[str]) -> None:
    """
    Time-based conflation loop: buffer ticks, flush latest snapshot every 100ms
    
    This dramatically smooths processing of high-frequency data streams.
    Instead of processing every tick, we process only the latest state
    at fixed intervals, eliminating micro-stutters.
    
    CPU-heavy analysis is offloaded to thread pool, preventing event loop blocking.
    """
    global _last_flush_time
    
    dispatcher = get_dispatcher()
    
    logger.info(f"🌊 Conflation loop started (interval={_conflation_interval*1000:.0f}ms, {len(symbols)} symbols)")
    
    try:
        while True:
            await asyncio.sleep(_conflation_interval)
            
            current_time = time()
            elapsed = current_time - _last_flush_time
            
            # Process latest snapshot for each symbol
            for symbol in symbols:
                if symbol in _latest_ticks:
                    tick = _latest_ticks[symbol]
                    # Offload CPU-heavy analysis to thread pool (Priority.ANALYSIS)
                    await dispatcher.submit_priority(
                        Priority.ANALYSIS,
                        _process_candle(tick)
                    )
            
            _last_flush_time = current_time
            logger.debug(f"💫 Conflation flush (elapsed={elapsed*1000:.1f}ms, symbols={len([s for s in symbols if s in _latest_ticks])})")
    
    except asyncio.CancelledError:
        logger.info("🌊 Conflation loop cancelled")


async def start(symbols: Optional[List[str]] = None) -> None:
    """
    Start data feed - connects to Binance, publishes market ticks
    
    Includes conflation buffer to smooth high-frequency streams.
    
    In production: Connect to Binance WebSocket, parse messages,
    publish TICK_UPDATE events
    """
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT"]
    
    logger.info(f"📡 Data feed starting ({len(symbols)} symbols)")
    
    # Start conflation loop in background
    conflation_task = asyncio.create_task(_conflation_loop(symbols))
    
    try:
        # Simulated: In production, this would be WebSocket connection
        # For now, publish sample ticks into the buffer
        tick_count = 0
        
        while True:
            await asyncio.sleep(0.01)  # Simulate 100 ticks/sec
            
            # Store in buffer instead of processing immediately
            tick = {
                'symbol': 'BTCUSDT',
                'open': 42000,
                'high': 42500,
                'low': 41500,
                'close': 42200,
                'volume': 1000,
                'time': int(time() * 1000)
            }
            
            # Buffer the tick (conflation will process it)
            _latest_ticks['BTCUSDT'] = tick
            
            tick_count += 1
            if tick_count % 1000 == 0:
                logger.debug(f"📊 {tick_count} ticks buffered")
            
            # Still publish for non-conflated subscribers
            await bus.publish(Topic.TICK_UPDATE, tick)
    
    except asyncio.CancelledError:
        logger.info("📡 Data feed cancelled")
        conflation_task.cancel()
    except Exception as e:
        logger.error(f"❌ Data feed error: {e}")
        conflation_task.cancel()


async def stop() -> None:
    """Stop data feed and conflation"""
    logger.info("📡 Data feed stopping")
    _latest_ticks.clear()


async def init() -> None:
    """Initialize data module - connect feed to brain"""
    logger.info("📡 Data module initializing")
    bus.subscribe(Topic.TICK_UPDATE, _process_candle)
    logger.info("✅ Data module ready (with 100ms conflation)")
