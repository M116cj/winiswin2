"""
🔌 EventBus - Zero-Coupling Event Communication
Minimal version for inter-module messaging
"""

import asyncio
from enum import Enum
from typing import Dict, Callable, List, Any


class Topic(Enum):
    """Event topics"""
    TICK_UPDATE = "tick_update"
    SIGNAL_GENERATED = "signal_generated"
    ORDER_REQUEST = "order_request"
    ORDER_FILLED = "order_filled"


class EventBus:
    """Simple EventBus for publishing/subscribing to topics"""
    
    def __init__(self):
        self.subscribers: Dict[Topic, List[Callable]] = {}
    
    async def publish(self, topic: Topic, data: Any):
        """Publish event to topic"""
        if topic in self.subscribers:
            for callback in self.subscribers[topic]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    pass
    
    def subscribe(self, topic: Topic, callback: Callable):
        """Subscribe to topic"""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)


# Global bus instance
bus = EventBus()
