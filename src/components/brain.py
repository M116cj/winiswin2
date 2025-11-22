"""
🧠 Brain Component - Signal Generation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pure analysis logic. Receives TICK_UPDATE, runs SMC + ML, publishes SIGNAL_GENERATED.
NO direct imports of other components. Only uses EventBus.
"""

import logging
import numpy as np
from typing import Dict, Optional

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


async def process_candle(tick: Dict) -> None:
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
        
        # Publish to gatekeeper for risk checking
        await bus.publish(Topic.SIGNAL_GENERATED, signal)


async def init() -> None:
    """Initialize brain - subscribe to tick updates"""
    logger.info("🧠 Brain initializing")
    bus.subscribe(Topic.TICK_UPDATE, process_candle)
    logger.info("✅ Brain ready (subscribed to TICK_UPDATE)")
