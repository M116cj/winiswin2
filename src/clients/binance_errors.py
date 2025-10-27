"""
Binance API 錯誤類型（v3.9.2.2新增）
職責：結構化錯誤、重試元數據解析
"""

import re
from typing import Optional


class BinanceRequestError(Exception):
    """
    Binance API請求錯誤
    
    包含重試延遲等結構化元數據，用於智能重試
    """
    
    def __init__(
        self,
        message: str,
        endpoint: str = "",
        retry_after_seconds: Optional[float] = None,
        is_circuit_breaker_error: bool = False,
        original_error: Optional[Exception] = None
    ):
        """
        初始化錯誤
        
        Args:
            message: 錯誤消息
            endpoint: API端點
            retry_after_seconds: 建議重試延遲（秒）
            is_circuit_breaker_error: 是否為熔斷器觸發
            original_error: 原始異常
        """
        super().__init__(message)
        self.endpoint = endpoint
        self.retry_after_seconds = retry_after_seconds
        self.is_circuit_breaker_error = is_circuit_breaker_error
        self.original_error = original_error
    
    @staticmethod
    def parse_retry_after(error_message: str) -> Optional[float]:
        """
        從錯誤消息中解析重試延遲
        
        支持格式：
        - "請 58 秒後重試"
        - "請58秒後重試" 
        - "wait 60 seconds"
        - "retry after 30"
        
        Args:
            error_message: 錯誤消息
        
        Returns:
            Optional[float]: 秒數，無法解析返回None
        """
        if not error_message:
            return None
        
        patterns = [
            r'請\s*(\d+)\s*秒後重試',
            r'wait\s+(\d+)\s+seconds?',
            r'retry\s+after\s+(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                return float(match.group(1))
        
        return None
