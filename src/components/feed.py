"""
📡 Feed Component - Market Data Ingestion
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pure data ingestion. Connects to WebSocket and publishes TICK_UPDATE events.
NO business logic. NO imports of other components.
"""

import logging
import asyncio
from typing import List, Optional

from src.bus import bus, Topic

logger = logging.getLogger(__name__)


async def start(symbols: Optional[List[str]] = None) -> None:
    """
    Start feed component - simulated for now
    
    In production: Connect to Binance WebSocket, parse messages,
    publish TICK_UPDATE events
    """
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT"]
    
    logger.info(f"🔌 Feed starting ({len(symbols)} symbols)")
    
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


async def stop() -> None:
    """Stop feed"""
    logger.info("🔌 Feed stopping")
