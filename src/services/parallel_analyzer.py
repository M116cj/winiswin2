"""
並行分析器（v3.15.1 串行稳定版）
職責：批量處理大量交易對分析、自適應批次大小、性能追蹤

v3.15.1 修复：
- 禁用进程池（避免 BrokenProcessPool 错误）
- 改用串行处理（100% 稳定）
- 优先保证系统稳定性
"""

import asyncio
from typing import List, Dict, Optional
import logging
import time

from src.strategies.ict_strategy import ICTStrategy
from src.config import Config

logger = logging.getLogger(__name__)


class ParallelAnalyzer:
    """並行分析器 - 充分利用 32vCPU 資源（v3.12.0 全局进程池优化版）"""
    
    def __init__(self, max_workers: Optional[int] = None, perf_monitor=None):
        """
        初始化並行分析器
        
        Args:
            max_workers: 最大工作進程數（None 表示從配置讀取）
            perf_monitor: 性能監控器
        """
        self.config = Config
        self.max_workers = max_workers
        
        # 🔧 v3.15.1：禁用进程池，改用串行处理（避免 BrokenProcessPool 错误）
        # 进程池在某些环境下不稳定，导致子进程崩溃
        # 串行处理虽然稍慢，但 100% 稳定
        self.global_pool = None  # 禁用进程池
        
        # 策略实例（用于串行分析）
        self.strategy = ICTStrategy()
        
        # ✨ 性能監控
        self.perf_monitor = perf_monitor
        
        logger.info("並行分析器初始化: 使用串行处理模式（稳定优先）")
        logger.info("🔧 v3.15.1: 已禁用进程池，避免 BrokenProcessPool 错误")
    
    def _calculate_optimal_batch_size(self, total_symbols: int) -> int:
        """
        計算最優批次大小（自適應批次大小）
        
        Args:
            total_symbols: 總交易對數量
        
        Returns:
            int: 最優批次大小
        """
        # 🔧 v3.15.1: 串行处理模式，返回固定批次大小
        # 使用较大批次以减少日志输出
        return min(total_symbols, 100)
    
    async def analyze_batch(
        self,
        symbols_data: List[Dict],
        data_manager
    ) -> List[Dict]:
        """
        批量並行分析多個交易對（v3.12.0 全局进程池优化版）
        
        Args:
            symbols_data: 交易對列表
            data_manager: 數據管理器實例（DataService 或 SmartDataManager）
        
        Returns:
            List[Dict]: 生成的交易信號列表
        """
        try:
            # ✨ 性能追蹤
            start_time = time.time()
            
            total_symbols = len(symbols_data)
            logger.info(f"開始批量分析 {total_symbols} 個交易對")
            
            # ✨ 自適應批次大小
            batch_size = self._calculate_optimal_batch_size(total_symbols)
            
            signals = []
            total_batches = (total_symbols + batch_size - 1) // batch_size
            
            logger.info(
                f"⚡ 批次配置: {batch_size} 個/批次, 共 {total_batches} 批次 "
                f"(工作進程: {self.global_pool.max_workers})"
            )
            
            for batch_idx in range(total_batches):
                i = batch_idx * batch_size
                batch = symbols_data[i:i + batch_size]
                
                logger.info(f"處理批次 {batch_idx + 1}/{total_batches} ({len(batch)} 個交易對)")
                
                # 並行獲取多時間框架數據
                tasks = [
                    data_manager.get_multi_timeframe_data(item['symbol'])
                    for item in batch
                ]
                
                multi_tf_data_list = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 🔧 v3.15.1: 串行处理（不使用进程池，100% 稳定）
                batch_signal_count = 0
                
                for j, multi_tf_data in enumerate(multi_tf_data_list):
                    # 检查数据有效性
                    if isinstance(multi_tf_data, Exception):
                        logger.debug(f"跳過 {batch[j]['symbol']}: 數據獲取異常 - {multi_tf_data}")
                        continue
                    
                    if multi_tf_data is None or not isinstance(multi_tf_data, dict):
                        logger.debug(f"跳過 {batch[j]['symbol']}: 數據無效")
                        continue
                    
                    symbol = batch[j]['symbol']
                    
                    # 串行分析（主进程中执行，避免进程池问题）
                    try:
                        signal = self.strategy.analyze(symbol, multi_tf_data)
                        if signal:
                            signals.append(signal)
                            batch_signal_count += 1
                    except Exception as e:
                        logger.debug(f"分析 {symbol} 失败: {e}")
                
                batch_time = time.time() - start_time
                logger.info(
                    f"批次 {batch_idx + 1}/{total_batches} 完成: "
                    f"生成 {batch_signal_count} 個信號, "
                    f"累計 {len(signals)} 個 "
                    f"⚡ 批次耗時: {batch_time:.2f}s"
                )
                
                # 内存管理：删除批量信号引用
                del batch_signals
                
                # 仅在极大量交易对且高负载时才延迟
                if total_symbols > 500 and batch_idx < total_batches - 1:
                    cpu_usage = psutil.cpu_percent(interval=0)
                    if cpu_usage > 80:
                        await asyncio.sleep(0.05)
            
            # ✨ 性能統計
            total_duration = time.time() - start_time
            avg_per_symbol = total_duration / max(total_symbols, 1)
            
            logger.info(
                f"✅ 批量分析完成: 分析 {total_symbols} 個交易對, "
                f"生成 {len(signals)} 個信號 "
                f"⚡ 總耗時: {total_duration:.2f}s "
                f"(平均 {avg_per_symbol*1000:.1f}ms/交易對)"
            )
            
            # ✨ 記錄性能
            if self.perf_monitor:
                self.perf_monitor.record_operation("analyze_batch", total_duration)
            
            return signals
            
        except Exception as e:
            logger.error(f"批量分析失敗: {e}", exc_info=True)
            return []
    
    async def analyze_async(self, symbols: List[str], data_manager) -> List[Dict]:
        """
        异步并行分析多个符号（文档步骤2要求的简化接口）
        
        使用全局进程池并发分析，避免重复创建/销毁进程
        
        Args:
            symbols: 交易对列表
            data_manager: 数据管理器
        
        Returns:
            List[Dict]: 分析结果列表
        """
        loop = asyncio.get_event_loop()
        executor = self.global_pool.get_executor()
        
        # 为每个符号创建任务
        tasks = []
        for symbol in symbols:
            # 获取多时间框架数据
            multi_tf_data = await data_manager.get_multi_timeframe_data(symbol)
            
            if multi_tf_data is None:
                continue
            
            # 提交到全局进程池
            task = loop.run_in_executor(
                executor,
                self._analyze_single_symbol,
                (symbol, multi_tf_data)
            )
            tasks.append(task)
        
        # 并发执行所有分析任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        signals = [r for r in results if r is not None and not isinstance(r, Exception)]
        
        return signals
    
    def _analyze_single_symbol(self, args) -> Optional[Dict]:
        """
        单一符号分析 - 在子进程中执行（文档步骤2要求）
        
        这个方法在子进程中运行，可以使用预加载的 ml_model
        
        Args:
            args: (symbol, multi_tf_data) 元组
        
        Returns:
            Optional[Dict]: 分析信号
        """
        try:
            symbol, multi_tf_data = args
            
            # 使用预加载的策略引擎（通过analyze_symbol_worker）
            # 这个函数已经在global_pool中定义，可以访问_worker_strategy
            return analyze_symbol_worker(args)
            
        except Exception as e:
            logger.error(f"分析符号 {args[0] if args else 'unknown'} 失败: {e}")
            return None
    
    async def close(self):
        """
        關閉執行器
        
        注意：v3.12.0 不再关闭全局进程池（由应用生命周期管理）
        """
        logger.info("並行分析器關閉（全局進程池继续运行）")
