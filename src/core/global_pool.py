"""
全局線程池管理器（v3.16.2 ThreadPool 修復版）
職責：單例模式線程池復用、健康檢查

v3.16.2 重大修復：
- 改用 ThreadPoolExecutor（避免序列化問題）
- 移除所有 pickle 相關代碼
- 簡化實現（線程共享內存，無序列化需求）
- ML 模型（ONNX/TensorRT）會釋放 GIL，線程池可並行
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

logger = logging.getLogger(__name__)


class GlobalThreadPool:
    """
    全局線程池單例管理器（v3.16.2 徹底解決序列化問題）
    
    關鍵改進：
    1. 使用 ThreadPoolExecutor 替代 ProcessPoolExecutor
    2. 線程共享內存，無需序列化
    3. ML 模型（ONNX）會釋放 GIL，線程池可並行
    4. 完全避免 'cannot pickle _thread.lock' 錯誤
    """
    
    _instance: Optional['GlobalThreadPool'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance
    
    def _initialize_pool(self, max_workers: Optional[int] = None):
        """
        初始化線程池
        
        Args:
            max_workers: 最大工作線程數（如果未指定，從 Config 讀取）
        """
        # 從 Config 讀取配置
        if max_workers is None:
            from src.config import Config
            max_workers = Config.MAX_WORKERS
        
        self.max_workers = max_workers
        
        # 🔥 v3.16.2 關鍵修復：使用 ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="MLWorker"
        )
        
        logger.info(f"✅ 全局線程池初始化完成 (workers={max_workers})")
        logger.info(f"   使用 ThreadPoolExecutor（無序列化問題）")
    
    def get_executor(self) -> ThreadPoolExecutor:
        """
        獲取線程池執行器
        
        Returns:
            ThreadPoolExecutor: 線程池執行器
        """
        return self.executor
    
    def submit_safe(self, func, *args, **kwargs):
        """
        安全提交任務
        
        Args:
            func: 要執行的函數
            *args: 位置參數
            **kwargs: 關鍵字參數
        
        Returns:
            Future: 任務的 Future 對象
        """
        executor = self.get_executor()
        return executor.submit(func, *args, **kwargs)
    
    def get_pool_health(self) -> dict:
        """
        獲取線程池健康狀態
        
        Returns:
            dict: 健康狀態信息
        """
        return {
            'max_workers': self.max_workers,
            'executor_available': self.executor is not None,
            'executor_type': 'ThreadPoolExecutor'
        }
    
    def shutdown(self, wait: bool = True):
        """
        關閉線程池
        
        Args:
            wait: 是否等待所有任務完成
        """
        if self.executor is not None:
            logger.info("🛑 關閉全局線程池...")
            try:
                self.executor.shutdown(wait=wait, cancel_futures=not wait)
                logger.info("✅ 全局線程池已關閉")
            except Exception as e:
                logger.error(f"關閉線程池時出錯: {e}")
    
    def __del__(self):
        """析構函數 - 確保線程池被關閉"""
        try:
            self.shutdown(wait=False)
        except Exception:
            pass
    
    @classmethod
    def reset(cls):
        """
        重置單例（主要用於測試）
        """
        if cls._instance is not None:
            cls._instance.shutdown(wait=False)
            cls._instance = None


# 向後兼容別名
GlobalProcessPool = GlobalThreadPool


def get_global_pool() -> GlobalThreadPool:
    """
    獲取全局線程池實例（便捷函數）
    
    Returns:
        GlobalThreadPool: 全局線程池實例
    """
    return GlobalThreadPool()
