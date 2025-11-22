"""Rate limiter stub for BinanceClient"""
import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter"""
    def __init__(self, max_requests: int = 1200, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    async def wait_if_needed(self):
        """Wait if rate limit exceeded"""
        now = time.time()
        self.requests = [r for r in self.requests if now - r < self.time_window]
        
        if len(self.requests) >= self.max_requests:
            wait_time = self.time_window - (now - self.requests[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        self.requests.append(now)
