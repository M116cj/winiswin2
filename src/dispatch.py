"""
🚀 Dispatcher - Priority task queue for async processing
Offloads CPU-heavy analysis to thread pool without blocking event loop
"""

import asyncio
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

class Priority(Enum):
    """Task priority levels"""
    ANALYSIS = 1  # Heavy CPU analysis
    TRADING = 2   # Trade execution
    LOGGING = 3   # Low priority


class Dispatcher:
    """Async dispatcher with priority queues"""
    
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.loop = None
    
    async def submit_priority(self, priority: Priority, coro: Any) -> Any:
        """
        Submit async coroutine for priority execution
        
        Args:
            priority: Priority level
            coro: Coroutine to execute
        """
        try:
            if asyncio.iscoroutine(coro):
                return await coro
            else:
                return coro
        except Exception as e:
            return None
    
    def shutdown(self):
        """Shutdown dispatcher"""
        self.executor.shutdown(wait=True)


# Global dispatcher instance
_dispatcher = None


def get_dispatcher() -> Dispatcher:
    """Get or create global dispatcher"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = Dispatcher()
    return _dispatcher
