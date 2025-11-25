"""
🚀 Railway Logger - 日誌過濾器
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Railway 日誌過濾器：
只顯示：
1. 模型累積分數 (Model cumulative score)
2. 模型學習數量 (Model learning count/samples)
3. Binance 倉位狀態 (Binance position status)
4. 所有 ERROR 級別的日誌

其餘日誌被抑制
"""

import logging
import os

class RailwayLogFilter(logging.Filter):
    """只允許關鍵日誌通過"""
    
    # 允許的關鍵詞
    ALLOWED_KEYWORDS = {
        # 模型累積分數
        'model cumulative',
        'model score',
        'cumulative score',
        '累積分數',
        '模型分數',
        '使用虛擁',
        '訓練 ml',
        
        # 模型學習數量
        'model learning',
        'samples absorbed',
        'learning count',
        'learning samples',
        '學習數量',
        '吸收樣本',
        '虛擁樣本',
        '虛擁交易',
        
        # Binance 倉位狀態
        'binance',
        'position',
        '倉位',
        'order',
        '訂單',
        'execution',
        '執行',
        'state persisted',
        
        # 虛擁交易
        'virtual',
        '虛擁',
        '開倉',
        '平倉',
        
        # 系統狀態
        'account',
        '帳户',
    }
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        過濾日誌：
        - ERROR、CRITICAL 級別：總是允許
        - 其他級別：只有包含特定關鍵詞才允許
        """
        
        # 1️⃣ 始終允許 ERROR 和 CRITICAL
        if record.levelno >= logging.ERROR:
            return True
        
        # 2️⃣ 其他級別檢查關鍵詞
        message = record.getMessage().lower()
        
        for keyword in self.ALLOWED_KEYWORDS:
            if keyword in message:
                return True
        
        # 3️⃣ 都不匹配，就過濾掉
        return False


def setup_railway_logger(logger_instance: logging.Logger) -> None:
    """
    設置 Railway 日誌過濾
    
    使用方式：
    ```python
    logger = logging.getLogger(__name__)
    setup_railway_logger(logger)
    ```
    """
    filter_obj = RailwayLogFilter()
    
    # 應用過濾器到所有處理器
    for handler in logger_instance.handlers:
        handler.addFilter(filter_obj)
    
    # 如果沒有處理器，添加一個
    if not logger_instance.handlers:
        handler = logging.StreamHandler()
        handler.addFilter(filter_obj)
        logger_instance.addHandler(handler)


def get_logger_with_railway_filter(name: str) -> logging.Logger:
    """
    獲取配置好的 Railway 日誌記錄器
    
    使用方式：
    ```python
    logger = get_logger_with_railway_filter(__name__)
    ```
    """
    logger = logging.getLogger(name)
    setup_railway_logger(logger)
    return logger


# ✅ Railway 環境判斷
IS_RAILWAY = os.getenv('RAILWAY_ENVIRONMENT') is not None
