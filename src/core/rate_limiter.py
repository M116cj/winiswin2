"""
限流器
職責：1200 請求/分鐘限制、智能配額管理、請求排隊
"""

import time
import asyncio
from collections import deque
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """API 請求限流器"""
    
    def __init__(self, max_requests: int = 1200, time_window: int = 60):
        """
        初始化限流器
        
        Args:
            max_requests: 時間窗口內最大請求數
            time_window: 時間窗口（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: deque = deque()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """
        獲取請求許可（阻塞直到獲得許可）
        """
        async with self._lock:
            current_time = time.time()
            
            # 清理過期請求記錄
            while self.requests and self.requests[0] < current_time - self.time_window:
                self.requests.popleft()
            
            # 檢查是否超過限制
            if len(self.requests) >= self.max_requests:
                # 計算需要等待的時間
                oldest_request = self.requests[0]
                wait_time = self.time_window - (current_time - oldest_request)
                
                if wait_time > 0:
                    logger.warning(f"達到速率限制，等待 {wait_time:.2f} 秒")
                    await asyncio.sleep(wait_time)
                    # 遞歸重試
                    return await self.acquire()
            
            # 記錄此次請求
            self.requests.append(current_time)
    
    def get_remaining_quota(self) -> int:
        """獲取剩餘配額"""
        current_time = time.time()
        
        # 清理過期請求
        while self.requests and self.requests[0] < current_time - self.time_window:
            self.requests.popleft()
        
        return max(0, self.max_requests - len(self.requests))
    
    def get_stats(self) -> dict:
        """獲取限流統計"""
        return {
            "max_requests": self.max_requests,
            "time_window": self.time_window,
            "current_usage": len(self.requests),
            "remaining_quota": self.get_remaining_quota(),
            "usage_rate": f"{(len(self.requests) / self.max_requests * 100):.2f}%"
        }
