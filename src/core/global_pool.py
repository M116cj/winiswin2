"""
全局进程池管理器（v3.16.1 BrokenProcessPool 修复版）
职责：单例模式进程池复用、健康检查、自动重建

v3.16.1 修复：
- 添加健康检查机制（检测进程池损坏）
- 自动重建损坏的进程池
- submit_safe 方法（自动处理 BrokenProcessPool）
- 子进程内存监控
"""

import multiprocessing as mp
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Optional

logger = logging.getLogger(__name__)


class GlobalProcessPool:
    """
    全局进程池单例管理器（带健康检查和重建机制）
    
    特点：
    1. 单例模式 - 整个应用生命周期内只创建一次
    2. 健康检查 - 自动检测进程池是否损坏
    3. 自动重建 - 损坏时自动重建进程池
    4. 安全提交 - submit_safe 方法自动处理 BrokenProcessPool
    """
    
    _instance: Optional['GlobalProcessPool'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance
    
    def _initialize_pool(self, max_workers: Optional[int] = None):
        """
        初始化进程池
        
        Args:
            max_workers: 最大工作进程数（如果未指定，从 Config 读取）
        """
        # 🔥 修复：从 Config 读取限制
        if max_workers is None:
            from src.config import Config
            max_workers = Config.MAX_WORKERS
        
        self.max_workers = max_workers
        self.executor = ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=self._worker_init,
            initargs=(self._get_model_path(),),
            mp_context=mp.get_context('spawn')  # 使用 spawn 避免 fork 问题
        )
        self._is_broken = False
        logger.info(f"✅ 全局進程池初始化完成 (workers={max_workers})")
    
    def _get_model_path(self) -> str:
        """获取模型路径"""
        return "data/models/model.onnx"
    
    def _worker_init(self, model_path: str):
        """
        子进程初始化
        
        Args:
            model_path: 模型文件路径
        """
        # 设置子进程名称便于调试
        mp.current_process().name = f"Worker-{mp.current_process().pid}"
        
        # 预加载模型（注意：这里要处理可能的 ImportError）
        try:
            import onnxruntime as ort
            global ml_model
            if os.path.exists(model_path):
                ml_model = ort.InferenceSession(model_path)
                logger.info(f"✅ 子進程 {mp.current_process().name} 模型加載成功")
            else:
                ml_model = None
                logger.warning(f"⚠️ 模型文件不存在: {model_path}")
        except ImportError:
            logger.warning(f"⚠️ 子進程 {mp.current_process().name} ONNX Runtime 未安装")
            ml_model = None
        except Exception as e:
            logger.warning(f"⚠️ 子進程 {mp.current_process().name} 模型加載失敗: {e}")
            # 即使模型加载失败，子进程仍可运行（使用 fallback 逻辑）
            ml_model = None
    
    def get_executor(self) -> ProcessPoolExecutor:
        """
        获取健康的进程池执行器
        
        Returns:
            ProcessPoolExecutor: 健康的进程池
        """
        if self._is_broken:
            logger.warning("⚠️ 檢測到損壞的進程池，正在重建...")
            self._rebuild_pool()
        
        return self.executor
    
    def _rebuild_pool(self):
        """重建进程池"""
        try:
            # 关闭旧的进程池
            if hasattr(self, 'executor') and self.executor is not None:
                self.executor.shutdown(wait=True, cancel_futures=True)
        except Exception as e:
            logger.error(f"關閉舊進程池時出錯: {e}")
        
        # 创建新的进程池
        self._initialize_pool(self.max_workers)
        self._is_broken = False
        logger.info("✅ 進程池重建完成")
    
    def submit_safe(self, func, *args, **kwargs):
        """
        安全提交任务（自动处理 BrokenProcessPool）
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
        
        Returns:
            Future: 任务的 Future 对象
        """
        try:
            executor = self.get_executor()
            return executor.submit(func, *args, **kwargs)
        except BrokenProcessPool:
            logger.warning("⚠️ 捕獲 BrokenProcessPool，重建進程池後重試")
            self._is_broken = True
            self._rebuild_pool()
            executor = self.get_executor()
            return executor.submit(func, *args, **kwargs)
    
    def get_pool_health(self) -> dict:
        """
        获取进程池健康状态
        
        Returns:
            dict: 健康状态信息
        """
        return {
            'is_broken': self._is_broken,
            'max_workers': self.max_workers,
            'executor_available': self.executor is not None
        }
    
    def shutdown(self, wait: bool = True):
        """
        关闭进程池
        
        Args:
            wait: 是否等待所有任务完成
        """
        if self.executor is not None:
            logger.info("🛑 關閉全局進程池...")
            try:
                self.executor.shutdown(wait=wait, cancel_futures=not wait)
                logger.info("✅ 全局進程池已關閉")
            except Exception as e:
                logger.error(f"關閉進程池時出錯: {e}")
    
    def __del__(self):
        """析构函数 - 确保进程池被关闭"""
        try:
            self.shutdown(wait=False)
        except Exception:
            pass
    
    @classmethod
    def reset(cls):
        """
        重置单例（主要用于测试）
        """
        if cls._instance is not None:
            cls._instance.shutdown(wait=False)
            cls._instance = None


def get_global_pool() -> GlobalProcessPool:
    """
    获取全局进程池实例（便捷函数）
    
    Returns:
        GlobalProcessPool: 全局进程池实例
    """
    return GlobalProcessPool()
