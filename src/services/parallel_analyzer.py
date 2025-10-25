"""
並行分析器
職責：利用 32 核心並行處理大量交易對分析
"""

import asyncio
from typing import List, Dict
import logging
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing as mp

from src.strategies.ict_strategy import ICTStrategy
from src.config import Config

logger = logging.getLogger(__name__)


class ParallelAnalyzer:
    """並行分析器 - 充分利用 32vCPU 資源"""
    
    def __init__(self, max_workers: int = 32):
        """
        初始化並行分析器
        
        Args:
            max_workers: 最大工作線程數（默認 32 以充分利用 32 核心）
        """
        self.max_workers = max_workers
        self.strategy = ICTStrategy()
        self.config = Config
        
        # 使用線程池處理 I/O 密集型任務
        self.thread_executor = ThreadPoolExecutor(max_workers=max_workers)
        
        logger.info(f"並行分析器初始化: {max_workers} 個工作線程")
    
    async def analyze_batch(
        self,
        symbols_data: List[Dict],
        data_service
    ) -> List[Dict]:
        """
        批量並行分析多個交易對
        
        Args:
            symbols_data: 交易對列表
            data_service: 數據服務實例
        
        Returns:
            List[Dict]: 生成的交易信號列表
        """
        try:
            # 分批處理以優化內存使用
            batch_size = self.max_workers * 2  # 每批處理 64 個
            signals = []
            
            for i in range(0, len(symbols_data), batch_size):
                batch = symbols_data[i:i + batch_size]
                
                # 並行獲取多時間框架數據
                tasks = [
                    data_service.get_multi_timeframe_data(item['symbol'])
                    for item in batch
                ]
                
                multi_tf_data_list = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 並行分析信號
                analysis_tasks = []
                for j, multi_tf_data in enumerate(multi_tf_data_list):
                    if isinstance(multi_tf_data, Exception):
                        continue
                    
                    symbol = batch[j]['symbol']
                    analysis_tasks.append(
                        self._analyze_symbol(symbol, multi_tf_data)
                    )
                
                batch_signals = await asyncio.gather(*analysis_tasks, return_exceptions=True)
                
                # 收集有效信號
                for signal in batch_signals:
                    if signal and not isinstance(signal, Exception):
                        signals.append(signal)
                
                # 日志進度
                if (i + batch_size) % (batch_size * 5) == 0:
                    logger.info(f"分析進度: {min(i + batch_size, len(symbols_data))}/{len(symbols_data)}")
            
            logger.info(f"批量分析完成: {len(signals)} 個信號")
            return signals
            
        except Exception as e:
            logger.error(f"批量分析失敗: {e}")
            return []
    
    async def _analyze_symbol(self, symbol: str, multi_tf_data: Dict) -> Dict:
        """
        在線程池中分析單個交易對
        
        Args:
            symbol: 交易對
            multi_tf_data: 多時間框架數據
        
        Returns:
            Dict: 交易信號
        """
        try:
            loop = asyncio.get_event_loop()
            
            # 在線程池中執行 CPU 密集型分析
            signal = await loop.run_in_executor(
                self.thread_executor,
                self.strategy.analyze,
                symbol,
                multi_tf_data
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"分析 {symbol} 失敗: {e}")
            return None
    
    async def close(self):
        """關閉執行器"""
        try:
            self.thread_executor.shutdown(wait=True)
            logger.info("並行分析器已關閉")
        except Exception as e:
            logger.error(f"關閉並行分析器失敗: {e}")
