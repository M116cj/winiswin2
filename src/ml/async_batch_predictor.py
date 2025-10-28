"""
异步批量预测器
优化3：异步模型推理 + 批量处理
"""
import asyncio
import logging
import time
import numpy as np
from typing import Any, Tuple

logger = logging.getLogger(__name__)


class AsyncBatchPredictor:
    """异步批量预测器"""
    
    def __init__(self, model, batch_size: int = 32, max_delay: float = 0.1):
        """
        初始化异步批量预测器
        
        Args:
            model: 预测模型
            batch_size: 批次大小
            max_delay: 最大延迟（秒）
        """
        self.model = model
        self.batch_size = batch_size
        self.max_delay = max_delay
        self.prediction_queue = asyncio.Queue()
        self.results = {}
        self.batch_task = None
        self._running = False
        
        logger.info(f"✅ 异步批量预测器初始化 (batch_size={batch_size}, max_delay={max_delay}s)")
    
    async def start_batch_processing(self):
        """启动批量处理任务"""
        if self._running:
            logger.warning("⚠️ 批量处理任务已在运行")
            return
        
        self._running = True
        self.batch_task = asyncio.create_task(self._process_batches())
        logger.info("🚀 批量处理任务已启动")
    
    async def stop_batch_processing(self):
        """停止批量处理任务"""
        self._running = False
        if self.batch_task:
            self.batch_task.cancel()
            try:
                await self.batch_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 批量处理任务已停止")
    
    async def predict_async(self, position_id: str, features):
        """
        异步预测
        
        Args:
            position_id: 仓位ID
            features: 特征向量
        
        Returns:
            预测结果
        """
        future = asyncio.Future()
        await self.prediction_queue.put((position_id, features, future))
        return await future
    
    async def _process_batches(self):
        """批量处理预测请求"""
        logger.info("🔄 批量处理循环开始")
        
        while self._running:
            try:
                batch = []
                start_time = time.time()
                
                # 收集批次
                while len(batch) < self.batch_size and (time.time() - start_time) < self.max_delay:
                    try:
                        item = await asyncio.wait_for(
                            self.prediction_queue.get(), 
                            timeout=self.max_delay
                        )
                        batch.append(item)
                    except asyncio.TimeoutError:
                        break
                
                if batch:
                    # 批量推理
                    position_ids = [item[0] for item in batch]
                    features_batch = np.array([item[1] for item in batch])
                    
                    logger.debug(f"🔮 批量预测 {len(batch)} 个仓位...")
                    
                    try:
                        # 执行批量预测
                        predictions = self.model.predict(features_batch)
                        
                        # 返回结果
                        for i, (position_id, _, future) in enumerate(batch):
                            if not future.done():
                                future.set_result(predictions[i])
                        
                        logger.debug(f"✅ 批量预测完成 ({len(batch)} 个)")
                    
                    except Exception as e:
                        logger.error(f"❌ 批量预测失败: {e}")
                        # 返回错误给所有等待的future
                        for _, _, future in batch:
                            if not future.done():
                                future.set_exception(e)
                
                else:
                    # 没有待处理的请求，短暂休眠
                    await asyncio.sleep(0.01)
            
            except asyncio.CancelledError:
                logger.info("批量处理任务被取消")
                break
            except Exception as e:
                logger.error(f"批量处理错误: {e}", exc_info=True)
                await asyncio.sleep(0.1)
        
        logger.info("🛑 批量处理循环结束")
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        return self.prediction_queue.qsize()
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "queue_size": self.prediction_queue.qsize(),
            "batch_size": self.batch_size,
            "max_delay": self.max_delay,
            "running": self._running
        }
