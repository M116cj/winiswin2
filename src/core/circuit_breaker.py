"""
熔斷器
職責：失敗檢測、自動熔斷、自動恢復
"""

import time
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """熔斷器狀態"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """API 調用熔斷器"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        """
        初始化熔斷器
        
        Args:
            failure_threshold: 觸發熔斷的失敗次數
            timeout: 熔斷超時時間（秒）
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: float = 0
        self.state = CircuitState.CLOSED
    
    def call(self, func, *args, **kwargs):
        """
        通過熔斷器調用函數
        
        Args:
            func: 要調用的函數
            *args, **kwargs: 函數參數
        
        Returns:
            函數返回值
        
        Raises:
            Exception: 當熔斷器開啟時拋出異常
        """
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.timeout:
                logger.info("熔斷器進入半開狀態，嘗試恢復")
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"熔斷器開啟，請 {self.timeout - (time.time() - self.last_failure_time):.0f} 秒後重試")
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def on_success(self):
        """處理成功調用"""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("熔斷器恢復正常")
            self.reset()
        
        # 逐漸降低失敗計數
        if self.failure_count > 0:
            self.failure_count -= 1
    
    def on_failure(self):
        """處理失敗調用"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(f"熔斷器開啟：連續失敗 {self.failure_count} 次")
    
    def reset(self):
        """重置熔斷器"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = 0
    
    def get_stats(self) -> dict:
        """獲取熔斷器統計"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "timeout": self.timeout,
            "time_since_last_failure": int(time.time() - self.last_failure_time) if self.last_failure_time > 0 else None
        }
