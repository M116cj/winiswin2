"""
⚡ Task Dispatcher - Priority-Based Offloading Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Prevents CPU-heavy math from blocking the WebSocket event loop.
Uses ThreadPoolExecutor for CPU-bound tasks and priority queue for scheduling.
"""

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from enum import IntEnum
from typing import Callable, Any, Coroutine, Optional

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Task priority levels (lower = higher priority)"""
    SYSTEM_CRITICAL = 0    # Error handling, reconnect
    EXECUTION = 1          # Order placement, cancellation
    ANALYSIS = 2           # SMC, ML prediction (CPU-bound, offloaded to thread)
    DATA_INGESTION = 3     # Saving to DB
    BACKGROUND = 4         # Logging, monitoring


class TaskDispatcher:
    """Priority-based task dispatcher with thread pool offloading"""
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize dispatcher
        
        Args:
            max_workers: Number of worker threads for CPU-bound tasks
        """
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.priority_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.worker_task: Optional[asyncio.Task] = None
        self.running = False
        
        logger.info(f"⚡ TaskDispatcher initialized (max_workers={max_workers})")
    
    async def init(self) -> None:
        """Initialize dispatcher and start worker loop"""
        self.loop = asyncio.get_event_loop()
        self.running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info("⚡ TaskDispatcher worker loop started")
    
    async def _worker_loop(self) -> None:
        """Main worker loop - process priority queue"""
        try:
            while self.running:
                try:
                    # Get next task (blocks if queue empty, with timeout to allow shutdown)
                    priority, coro = await asyncio.wait_for(
                        self.priority_queue.get(),
                        timeout=1.0
                    )
                    
                    # Execute coroutine
                    if asyncio.iscoroutine(coro):
                        await coro
                    else:
                        logger.warning(f"⚠️ Dispatcher: Expected coroutine, got {type(coro)}")
                
                except asyncio.TimeoutError:
                    # Queue empty, keep looping
                    pass
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"❌ Dispatcher worker error: {e}")
        
        finally:
            self.running = False
            logger.info("⚡ TaskDispatcher worker loop stopped")
    
    async def submit_priority(
        self,
        priority: Priority,
        coro: Coroutine
    ) -> None:
        """
        Submit a high-priority async task
        
        Args:
            priority: Priority level (lower = higher priority)
            coro: Coroutine to execute
        """
        await self.priority_queue.put((priority, coro))
        logger.debug(f"⚡ Task submitted (priority={priority.name})")
    
    async def submit_cpu_bound(
        self,
        func: Callable,
        *args,
        priority: Priority = Priority.ANALYSIS,
        **kwargs
    ) -> Any:
        """
        Submit CPU-bound function to thread pool, wrap in async
        
        This offloads heavy computation to separate threads, preventing
        event loop blocking.
        
        Args:
            func: CPU-bound function to execute
            *args: Positional arguments for function
            priority: Priority level for scheduling
            **kwargs: Keyword arguments for function
            
        Returns:
            Result from function
        """
        if not self.loop:
            raise RuntimeError("Dispatcher not initialized. Call await init() first.")
        
        # Execute in thread pool, wrap result in coroutine
        future = self.loop.run_in_executor(
            self.thread_pool,
            lambda: func(*args, **kwargs)
        )
        
        # Wait for result
        result = await future
        return result
    
    async def shutdown(self) -> None:
        """Shutdown dispatcher gracefully"""
        self.running = False
        
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)
        logger.info("⚡ TaskDispatcher shutdown complete")


# Global dispatcher instance
_dispatcher: Optional[TaskDispatcher] = None


def get_dispatcher() -> TaskDispatcher:
    """Get global dispatcher instance"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = TaskDispatcher(max_workers=4)
    return _dispatcher


async def init_dispatcher() -> TaskDispatcher:
    """Initialize and return global dispatcher"""
    global _dispatcher
    _dispatcher = TaskDispatcher(max_workers=4)
    await _dispatcher.init()
    return _dispatcher
