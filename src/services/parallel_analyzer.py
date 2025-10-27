"""
並行分析器（v3.3.7性能優化版）
職責：利用 32 核心並行處理大量交易對分析、自適應批次大小、性能追蹤
"""

import asyncio
from typing import List, Dict, Optional
import logging
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing as mp
import psutil
import time

from src.strategies.ict_strategy import ICTStrategy
from src.config import Config

logger = logging.getLogger(__name__)


class ParallelAnalyzer:
    """並行分析器 - 充分利用 32vCPU 資源（v3.3.7性能優化版）"""
    
    def __init__(self, max_workers: Optional[int] = None, perf_monitor=None):
        """
        初始化並行分析器
        
        Args:
            max_workers: 最大工作線程數（None 表示從配置讀取）
            perf_monitor: 性能監控器（v3.3.7新增）
        """
        self.config = Config
        
        # 從配置獲取默認值
        default_workers = self.config.MAX_WORKERS
        
        # 自動檢測 CPU 核心數
        cpu_count = mp.cpu_count()
        
        # 如果未指定，使用配置值；否則取指定值
        if max_workers is None:
            self.max_workers = min(default_workers, cpu_count)
        else:
            self.max_workers = min(max_workers, cpu_count)
        
        self.strategy = ICTStrategy()
        
        # 使用線程池處理 I/O 密集型任務
        self.thread_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # ✨ v3.3.7新增：性能監控
        self.perf_monitor = perf_monitor
        
        logger.info(
            f"並行分析器初始化: {self.max_workers} 個工作線程 "
            f"(CPU 核心: {cpu_count})"
        )
    
    def _calculate_optimal_batch_size(self, total_symbols: int) -> int:
        """
        計算最優批次大小（v3.3.7新增 - 自適應批次大小）
        
        Args:
            total_symbols: 總交易對數量
        
        Returns:
            int: 最優批次大小
        """
        try:
            # 獲取當前系統負載
            cpu_usage = psutil.cpu_percent(interval=0.1)
            mem_usage = psutil.virtual_memory().percent
            
            # 基礎批次大小
            base_batch = self.max_workers * 2
            
            # 根據系統負載動態調整（内存优化：降低批次大小阈值）
            if cpu_usage < 40 and mem_usage < 50:
                # 系統空閒，增大批次
                multiplier = 2  # 降低從3到2
                logger.debug(f"系統負載低 (CPU: {cpu_usage:.1f}%, MEM: {mem_usage:.1f}%)，使用大批次")
            elif cpu_usage < 60 and mem_usage < 65:
                # 正常負載
                multiplier = 1.5  # 降低從2到1.5
                logger.debug(f"系統負載正常 (CPU: {cpu_usage:.1f}%, MEM: {mem_usage:.1f}%)，使用標準批次")
            else:
                # 高負載，減小批次
                multiplier = 1
                logger.warning(f"系統負載高 (CPU: {cpu_usage:.1f}%, MEM: {mem_usage:.1f}%)，使用小批次")
            
            batch_size = int(base_batch * multiplier)
            
            # 針對大量交易對優化（避免過大批次）
            if total_symbols > 500:
                batch_size = min(batch_size, 150)
            
            return int(batch_size)
            
        except Exception as e:
            logger.warning(f"計算最優批次大小失敗，使用默認值: {e}")
            return self.max_workers * 2
    
    async def analyze_batch(
        self,
        symbols_data: List[Dict],
        data_manager
    ) -> List[Dict]:
        """
        批量並行分析多個交易對（v3.3.7優化版 - 自適應批次大小）
        
        Args:
            symbols_data: 交易對列表
            data_manager: 數據管理器實例（DataService 或 SmartDataManager）
        
        Returns:
            List[Dict]: 生成的交易信號列表
        """
        try:
            # ✨ v3.3.7：性能追蹤
            start_time = time.time()
            
            total_symbols = len(symbols_data)
            logger.info(f"開始批量分析 {total_symbols} 個交易對")
            
            # ✨ v3.3.7：自適應批次大小
            batch_size = self._calculate_optimal_batch_size(total_symbols)
            
            signals = []
            total_batches = (total_symbols + batch_size - 1) // batch_size
            
            logger.info(
                f"⚡ 批次配置: {batch_size} 個/批次, 共 {total_batches} 批次 "
                f"(工作線程: {self.max_workers})"
            )
            
            for batch_idx in range(total_batches):
                i = batch_idx * batch_size
                batch = symbols_data[i:i + batch_size]
                
                logger.info(f"處理批次 {batch_idx + 1}/{total_batches} ({len(batch)} 個交易對)")
                
                # 並行獲取多時間框架數據（智能調度）
                tasks = [
                    data_manager.get_multi_timeframe_data(item['symbol'])
                    for item in batch
                ]
                
                multi_tf_data_list = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 並行分析信號
                analysis_tasks = []
                for j, multi_tf_data in enumerate(multi_tf_data_list):
                    # 明確檢查類型，確保是有效字典
                    if isinstance(multi_tf_data, Exception):
                        logger.debug(f"跳過 {batch[j]['symbol']}: 數據獲取異常 - {multi_tf_data}")
                        continue
                    
                    if multi_tf_data is None or not isinstance(multi_tf_data, dict):
                        logger.debug(f"跳過 {batch[j]['symbol']}: 數據無效")
                        continue
                    
                    symbol = batch[j]['symbol']
                    analysis_tasks.append(
                        self._analyze_symbol(symbol, multi_tf_data)
                    )
                
                batch_signals = await asyncio.gather(*analysis_tasks, return_exceptions=True)
                
                # 收集有效信號
                batch_signal_count = 0
                for signal in batch_signals:
                    if signal and not isinstance(signal, Exception):
                        signals.append(signal)
                        batch_signal_count += 1
                
                batch_time = time.time() - start_time
                logger.info(
                    f"批次 {batch_idx + 1}/{total_batches} 完成: "
                    f"生成 {batch_signal_count} 個信號, "
                    f"累計 {len(signals)} 個 "
                    f"⚡ 批次耗時: {batch_time:.2f}s"
                )
                
                # 🎯 v3.9.2.7性能优化：简化内存管理
                # 删除批量信号引用，让Python自动垃圾回收
                del batch_signals
                # 移除频繁手动gc.collect()，避免性能损耗
                
                # 🎯 v3.9.2.7优化：仅在极大量交易对且高负载时才延迟
                if total_symbols > 500 and batch_idx < total_batches - 1:
                    # 检查系统负载，仅在高负载时延迟
                    cpu_usage = psutil.cpu_percent(interval=0)
                    if cpu_usage > 80:
                        await asyncio.sleep(0.05)  # 减少延迟时间从0.1到0.05
            
            # ✨ v3.3.7：性能統計
            total_duration = time.time() - start_time
            avg_per_symbol = total_duration / max(total_symbols, 1)
            
            logger.info(
                f"✅ 批量分析完成: 分析 {total_symbols} 個交易對, "
                f"生成 {len(signals)} 個信號 "
                f"⚡ 總耗時: {total_duration:.2f}s "
                f"(平均 {avg_per_symbol*1000:.1f}ms/交易對)"
            )
            
            # ✨ v3.3.7：記錄性能
            if self.perf_monitor:
                self.perf_monitor.record_operation("analyze_batch", total_duration)
            
            return signals
            
        except Exception as e:
            logger.error(f"批量分析失敗: {e}", exc_info=True)
            return []
    
    async def _analyze_symbol(self, symbol: str, multi_tf_data: Dict) -> Optional[Dict]:
        """
        在線程池中分析單個交易對
        
        Args:
            symbol: 交易對
            multi_tf_data: 多時間框架數據
        
        Returns:
            Optional[Dict]: 交易信號（可能為 None）
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
