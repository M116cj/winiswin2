"""
熔斷器（v3.9.2.2增強版）
職責：失敗檢測、自動熔斷、自動恢復、狀態查詢
"""

import time
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """熔斷器狀態"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """API 調用熔斷器（v3.9.2.2增強版：支持狀態查詢和手動控制）"""
    
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
        self.manual_open_reason: Optional[str] = None
    
    async def call_async(self, func, *args, **kwargs):
        """
        通過熔斷器調用異步函數
        
        Args:
            func: 要調用的異步函數
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
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def call(self, func, *args, **kwargs):
        """
        通過熔斷器調用同步函數
        
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
            "time_since_last_failure": int(time.time() - self.last_failure_time) if self.last_failure_time > 0 else None,
            "manual_open_reason": self.manual_open_reason
        }
    
    def is_open(self) -> bool:
        """
        檢查熔斷器是否開啟（v3.9.2.2新增）
        
        Returns:
            bool: True表示熔斷器開啟，不應發送新請求
        """
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.timeout:
                return False
            return True
        return False
    
    def get_retry_after(self) -> float:
        """
        獲取剩餘等待時間（v3.9.2.2新增）
        
        Returns:
            float: 剩餘秒數，0表示可以重試
        """
        if self.state != CircuitState.OPEN:
            return 0.0
        
        elapsed = time.time() - self.last_failure_time
        remaining = max(0, self.timeout - elapsed)
        return remaining
    
    def manual_open(self, reason: str, cooldown: Optional[int] = None):
        """
        手動開啟熔斷器（v3.9.2.2新增）
        
        用於在檢測到系統級問題時主動暫停API調用
        
        Args:
            reason: 開啟原因
            cooldown: 冷卻時間（秒），None使用默認timeout
        """
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        self.manual_open_reason = reason
        
        if cooldown is not None:
            original_timeout = self.timeout
            self.timeout = cooldown
            logger.warning(
                f"⚠️  熔斷器已手動開啟: {reason} "
                f"(冷卻{cooldown}秒)"
            )
            self.timeout = original_timeout
        else:
            logger.warning(
                f"⚠️  熔斷器已手動開啟: {reason} "
                f"(冷卻{self.timeout}秒)"
            )
    
    def can_proceed(self) -> tuple[bool, Optional[str]]:
        """
        檢查是否可以繼續執行（v3.9.2.2新增）
        
        Returns:
            tuple[bool, Optional[str]]: (是否可執行, 阻止原因)
        """
        if not self.is_open():
            return True, None
        
        retry_after = self.get_retry_after()
        reason = self.manual_open_reason or "連續失敗觸發"
        
        return False, f"熔斷器開啟({reason})，請{retry_after:.0f}秒後重試"
