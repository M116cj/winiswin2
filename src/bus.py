"""
📡 EventBus - Central Nervous System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Global event-driven communication backbone. All components talk ONLY through this bus.
Zero direct imports between components = Zero coupling.
"""

import asyncio
from typing import Callable, Dict, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Topic(str, Enum):
    """Event topics - components publish and subscribe to these"""
    TICK_UPDATE = "tick_update"                # Feed → Brain
    SIGNAL_GENERATED = "signal_generated"      # Brain → Gatekeeper
    ORDER_REQUEST = "order_request"            # Gatekeeper → Hand
    ORDER_FILLED = "order_filled"              # Hand → Memory
    SYSTEM_SHUTDOWN = "system_shutdown"        # System → All


class EventBus:
    """
    Lightweight async EventBus - Singleton pattern
    
    No classes, no state - just pure event routing.
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._subscribers: Dict[Topic, List[Callable]] = {topic: [] for topic in Topic}
        self._initialized = True
        logger.info("✅ EventBus initialized")
    
    def subscribe(self, topic: Topic, callback: Callable) -> None:
        """
        Subscribe a callback to a topic
        
        Args:
            topic: Event topic (from Topic enum)
            callback: async function(data) to call when event is published
        """
        self._subscribers[topic].append(callback)
        logger.debug(f"📡 Subscribed to {topic.value}")
    
    async def publish(self, topic: Topic, data: dict) -> None:
        """
        Publish event to all subscribers
        
        Args:
            topic: Event topic
            data: Event data (dict)
        """
        logger.debug(f"📡 Publishing {topic.value}: {data.get('symbol', 'N/A')}")
        
        tasks = []
        for callback in self._subscribers[topic]:
            if asyncio.iscoroutinefunction(callback):
                tasks.append(callback(data))
            else:
                callback(data)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Global singleton instance
bus = EventBus()
