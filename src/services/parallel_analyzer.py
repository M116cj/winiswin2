"""
並行分析器（v3.16.1 BrokenProcessPool 修复版）
職責：批量處理大量交易對分析、自動重建損壞進程池、內存監控

v3.16.1 修復：
- 重新啟用進程池（使用安全提交機制）
- 添加 BrokenProcessPool 自動恢復
- 添加子進程內存監控
- 添加 fallback 降級策略
- 添加超時機制（30秒/任務）
"""

import asyncio
from typing import List, Dict, Optional
import logging
import time
from concurrent.futures import BrokenProcessPool, TimeoutError

from src.core.global_pool import GlobalProcessPool
from src.config import Config

logger = logging.getLogger(__name__)


class ParallelAnalyzer:
    """並行分析器 - v3.16.1 BrokenProcessPool 修復版"""
    
    def __init__(self, max_workers: Optional[int] = None, perf_monitor=None):
        """
        初始化並行分析器
        
        Args:
            max_workers: 最大工作進程數（未使用，由 GlobalProcessPool 管理）
            perf_monitor: 性能監控器
        """
        self.config = Config
        self.global_pool = GlobalProcessPool()
        self._model_path = "data/models/model.onnx"
        
        # ✨ 性能監控
        self.perf_monitor = perf_monitor
        
        logger.info("✅ 並行分析器初始化: 使用全局進程池（v3.16.1 安全版本）")
        logger.info(f"   進程池狀態: {self.global_pool.get_pool_health()}")
    
    async def analyze_batch(
        self,
        symbols_data: List[Dict],
        data_manager
    ) -> List[Dict]:
        """
        批量並行分析多個交易對（v3.16.1 安全版本）
        
        Args:
            symbols_data: 交易對列表
            data_manager: 數據管理器實例
        
        Returns:
            List[Dict]: 生成的交易信號列表
        """
        try:
            start_time = time.time()
            total_symbols = len(symbols_data)
            
            logger.info(f"開始批量分析 {total_symbols} 個交易對")
            
            signals = []
            loop = asyncio.get_event_loop()
            tasks = []
            
            # 🔥 步驟1：並行獲取所有數據
            data_tasks = [
                data_manager.get_multi_timeframe_data(item['symbol'])
                for item in symbols_data
            ]
            
            multi_tf_data_list = await asyncio.gather(*data_tasks, return_exceptions=True)
            
            # 🔥 步驟2：提交所有分析任務（使用安全提交）
            for i, multi_tf_data in enumerate(multi_tf_data_list):
                # 檢查數據有效性
                if isinstance(multi_tf_data, Exception) or multi_tf_data is None:
                    continue
                
                symbol = symbols_data[i]['symbol']
                symbol_data = {
                    'symbol': symbol,
                    'data': multi_tf_data
                }
                
                # 🔥 使用安全提交（自動處理 BrokenProcessPool）
                future = self.global_pool.submit_safe(
                    self._analyze_single_symbol,
                    symbol_data,
                    self._model_path,
                    self.config.__dict__
                )
                tasks.append((symbol, future))
            
            # 🔥 步驟3：收集結果（帶超時機制）
            for symbol, future in tasks:
                try:
                    # 30秒超時
                    result = await loop.run_in_executor(None, future.result, 30)
                    if result:
                        signals.append(result)
                except TimeoutError:
                    logger.warning(f"⚠️ 分析 {symbol} 超時（30秒）")
                except BrokenProcessPool:
                    logger.error(f"❌ 進程池損壞（分析 {symbol}），跳過剩餘任務")
                    break
                except Exception as e:
                    logger.error(f"❌ 分析 {symbol} 失敗: {e}")
            
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
            
        except BrokenProcessPool:
            logger.error("❌ 進程池損壞，跳過本次分析")
            return []
        except Exception as e:
            logger.error(f"❌ 批量分析失敗: {e}", exc_info=True)
            return []
    
    @staticmethod
    def _analyze_single_symbol(symbol_data: Dict, model_path: str, config_dict: Dict) -> Optional[Dict]:
        """
        單符號分析 - 子進程執行（v3.16.1 內存監控版本）
        
        Args:
            symbol_data: 符號數據 {'symbol': str, 'data': dict}
            model_path: 模型路徑
            config_dict: 配置字典
        
        Returns:
            Optional[Dict]: 交易信號
        """
        try:
            # 🔥 添加記憶體監控
            try:
                import psutil
                process = psutil.Process()
                initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            except ImportError:
                initial_memory = None
            
            # 重建配置
            from src.config import Config
            config = Config()
            for key, value in config_dict.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            # 🔥 嘗試使用自我學習交易員
            try:
                from src.strategies.self_learning_trader import SelfLearningTrader
                trader = SelfLearningTrader(config)
                result = trader.analyze(symbol_data['symbol'], symbol_data['data'])
                
            except (ImportError, MemoryError) as e:
                # 🔥 降級到 ICT 策略
                logger.warning(f"⚠️ 自我學習交易員不可用 ({e})，使用降級策略")
                result = ParallelAnalyzer._fallback_analysis(symbol_data, config)
            
            # 🔥 記憶體監控
            if initial_memory is not None:
                try:
                    final_memory = process.memory_info().rss / 1024 / 1024  # MB
                    memory_increase = final_memory - initial_memory
                    
                    if memory_increase > 500:  # 記憶體增加超過 500MB
                        logger.warning(
                            f"⚠️ 記憶體洩漏警告 {symbol_data['symbol']}: +{memory_increase:.1f}MB"
                        )
                except Exception:
                    pass
            
            return result
            
        except MemoryError:
            logger.error(f"❌ 記憶體不足: {symbol_data['symbol']}")
            return None
        except ImportError as e:
            logger.warning(f"⚠️ 模組導入錯誤: {e}")
            # 使用 fallback 策略
            try:
                return ParallelAnalyzer._fallback_analysis(symbol_data, config_dict)
            except Exception:
                return None
        except Exception as e:
            logger.error(f"❌ 分析錯誤 {symbol_data['symbol']}: {e}")
            return None
    
    @staticmethod
    def _fallback_analysis(symbol_data: Dict, config_or_dict) -> Optional[Dict]:
        """
        降級分析策略（當深度學習不可用時）
        
        Args:
            symbol_data: 符號數據
            config_or_dict: 配置對象或字典
        
        Returns:
            Optional[Dict]: 交易信號
        """
        try:
            from src.strategies.ict_strategy import ICTStrategy
            from src.config import Config
            
            # 處理配置
            if isinstance(config_or_dict, dict):
                config = Config()
                for key, value in config_or_dict.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            else:
                config = config_or_dict
            
            trader = ICTStrategy(config)
            result = trader.analyze(symbol_data['symbol'], symbol_data['data'])
            return result
            
        except Exception as e:
            logger.error(f"❌ 降級分析失敗: {e}")
            return None
    
    async def close(self):
        """
        關閉執行器
        
        注意：v3.16.1 不關閉全局進程池（由應用生命週期管理）
        """
        logger.info("並行分析器關閉（全局進程池繼續運行）")
