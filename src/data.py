"""
📡 Data Module - Market Data + Signal Generation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Merged: Feed (ingestion) + Brain (SMC analysis & signal generation)
Receives ticks, detects patterns, publishes signals.
"""

import logging
import asyncio
import numpy as np
from typing import Dict, Optional, List

from src.bus import bus, Topic
from src.indicators import Indicators

logger = logging.getLogger(__name__)


def _detect_pattern(tick: Optional[Dict]) -> Dict:
    """Pure stateless SMC pattern detection"""
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
    
    Logic:
    1. Detect SMC patterns
    2. Calculate ML features
    3. If opportunity -> publish SIGNAL_GENERATED
    """
    if not tick:
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
        
        logger.info(f"🧠 Signal: {symbol} @ {confidence:.1%}")
        
        # Publish to risk manager for validation
        await bus.publish(Topic.SIGNAL_GENERATED, signal)


async def start(symbols: Optional[List[str]] = None) -> None:
    """
    Start data feed - connects to Binance, publishes market ticks
    
    In production: Connect to Binance WebSocket, parse messages,
    publish TICK_UPDATE events
    """
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT"]
    
    logger.info(f"📡 Data feed starting ({len(symbols)} symbols)")
    
    try:
        # Simulated: In production, this would be WebSocket connection
        # For now, just publish sample ticks
        while True:
            await asyncio.sleep(60)
            
            # Example tick data
            tick = {
                'symbol': 'BTCUSDT',
                'open': 42000,
                'high': 42500,
                'low': 41500,
                'close': 42200,
                'volume': 1000,
                'time': 0
            }
            
            await bus.publish(Topic.TICK_UPDATE, tick)
    except asyncio.CancelledError:
        logger.info("📡 Data feed cancelled")
    except Exception as e:
        logger.error(f"❌ Data feed error: {e}")


async def stop() -> None:
    """Stop data feed"""
    logger.info("📡 Data feed stopping")


async def init() -> None:
    """Initialize data module - connect feed to brain"""
    logger.info("📡 Data module initializing")
    bus.subscribe(Topic.TICK_UPDATE, _process_candle)
    logger.info("✅ Data module ready")
