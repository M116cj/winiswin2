"""
並行分析器（v3.16.2 序列化修復版）
職責：批量處理大量交易對分析、自動重建損壞進程池、內存監控

v3.16.2 修復（2025-10-28）：
- 修復子進程 logger 序列化問題（thread.lock 錯誤）
- 在子進程內部創建獨立 logger（避免序列化模塊級別 logger）

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
from concurrent.futures import TimeoutError
from concurrent.futures.process import BrokenProcessPool

from src.core.global_pool import GlobalProcessPool
from src.config import Config

logger = logging.getLogger(__name__)


# 🔥 v3.16.2 修復：模塊級別工作函數（完全無閉包設計）
def _analyze_single_symbol_worker(symbol: str, market_data: dict, config_dict: dict) -> Optional[Dict]:
    """
    單個交易對分析（獨立工作函數，無任何外部依賴）
    
    🔥 v3.16.2 嚴格修復（GlobalProcessPool 方案）：
    - 完全獨立的模塊級函數（不依賴任何類或模塊狀態）
    - 參數完全扁平化（symbol, market_data, config_dict）
    - 所有參數都是基本類型（str, dict）
    - 在子進程內部重建所有複雜對象（logger, DataFrame, Config, Strategy）
    
    Args:
        symbol: 交易對名稱（str）
        market_data: 市場數據（Dict[str, Dict[str, Any]]），已轉換為純字典
        config_dict: 配置參數（Dict[str, Union[int, float, str, bool]]），只包含基本類型
    
    Returns:
        Optional[Dict]: 交易信號
    """
    # 🔥 步驟1：在子進程內部創建獨立 logger（避免序列化主進程 logger）
    import logging
    import pandas as pd
    proc_logger = logging.getLogger(f"worker.{symbol}")
    
    try:
        # 🔥 步驟2：重建 DataFrame（從純字典恢復）
        reconstructed_data = {}
        for tf_key, tf_dict in market_data.items():
            if tf_dict is not None and isinstance(tf_dict, dict) and 'data' in tf_dict:
                # 從純字典重建 DataFrame
                df = pd.DataFrame(tf_dict['data'])
                if 'index' in tf_dict:
                    df.index = tf_dict['index']
                reconstructed_data[tf_key] = df
            else:
                reconstructed_data[tf_key] = None
        
        # 🔥 步驟3：添加記憶體監控
        process = None
        initial_memory = None
        try:
            import psutil
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            pass
        
        # 🔥 步驟4：在子進程內重建 Config 對象
        from src.config import Config
        config = Config()
        # 只應用傳入的配置參數
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        # 🔥 步驟5：在子進程內創建策略實例並執行分析
        result = None
        try:
            from src.strategies.self_learning_trader import SelfLearningTrader
            trader = SelfLearningTrader(config=config)
            result = trader.analyze(symbol, reconstructed_data)
            
        except Exception as e:
            # 🔥 降級到 ICT 策略
            proc_logger.warning(f"⚠️ 自我學習交易員不可用 ({e})，使用降級策略")
            try:
                from src.strategies.ict_strategy import ICTStrategy
                trader = ICTStrategy()
                result = trader.analyze(symbol, reconstructed_data)
            except Exception as fallback_error:
                proc_logger.error(f"❌ 降級策略也失敗: {fallback_error}")
                result = None
        
        # 🔥 步驟6：記憶體監控
        if initial_memory is not None and process is not None:
            try:
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory
                
                if memory_increase > 500:  # 記憶體增加超過 500MB
                    proc_logger.warning(
                        f"⚠️ 記憶體洩漏警告 {symbol}: +{memory_increase:.1f}MB"
                    )
            except Exception:
                pass
        
        return result
        
    except MemoryError:
        proc_logger.error(f"❌ 記憶體不足 {symbol}")
        return None
    except Exception as e:
        proc_logger.error(f"❌ 分析失敗 {symbol}: {e}")
        return None


class ParallelAnalyzer:
    """並行分析器 - v3.16.1 BrokenProcessPool 修復版"""
    
    def __init__(self, max_workers: Optional[int] = None, perf_monitor=None):
        """
        初始化並行分析器
        
        Args:
            max_workers: 最大工作進程數（未使用，由 GlobalProcessPool 管理）
            perf_monitor: 性能監控器
        """
        self.config = Config()  # 🔥 修复：实例化 Config 对象
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
            
            # 🔥 步驟2：提交所有分析任務（使用完全無閉包設計）
            for i, multi_tf_data in enumerate(multi_tf_data_list):
                # 檢查數據有效性
                if isinstance(multi_tf_data, Exception) or multi_tf_data is None:
                    continue
                
                # 確保是字典類型
                if not isinstance(multi_tf_data, dict):
                    continue
                
                symbol = symbols_data[i]['symbol']
                
                # 🔥 轉換 DataFrame 為純字典（100% 可序列化）
                market_data = {}
                for tf_key, df in multi_tf_data.items():
                    if df is not None and hasattr(df, 'to_dict'):
                        # 轉換為純 Python 基本類型
                        market_data[tf_key] = {
                            'data': df.to_dict('list'),  # list of lists/dicts
                            'index': df.index.tolist() if hasattr(df.index, 'tolist') else list(df.index)
                        }
                    else:
                        market_data[tf_key] = None
                
                # 🔥 創建配置字典（只包含基本類型：int, float, str, bool）
                config_dict = {
                    'MIN_CONFIDENCE': float(self.config.MIN_CONFIDENCE),
                    'MAX_LEVERAGE': int(self.config.MAX_LEVERAGE),
                    'MIN_LEVERAGE': int(self.config.MIN_LEVERAGE),
                    'BASE_MARGIN_PCT': float(self.config.BASE_MARGIN_PCT),
                    'MIN_MARGIN_PCT': float(self.config.MIN_MARGIN_PCT),
                    'MAX_MARGIN_PCT': float(self.config.MAX_MARGIN_PCT),
                    'RISK_REWARD_RATIO': float(self.config.RISK_REWARD_RATIO),
                    'TRADING_ENABLED': bool(self.config.TRADING_ENABLED)
                }
                
                # 🔥 v3.16.2 嚴格驗證：提交前檢查所有參數可序列化
                try:
                    import pickle
                    # 驗證函數本身
                    pickle.dumps(_analyze_single_symbol_worker)
                    # 驗證所有參數
                    pickle.dumps(symbol)  # str
                    pickle.dumps(market_data)  # dict
                    pickle.dumps(config_dict)  # dict
                except Exception as pickle_error:
                    logger.error(f"❌ 序列化驗證失敗 {symbol}: {pickle_error}")
                    logger.error(f"   函數: _analyze_single_symbol_worker")
                    logger.error(f"   symbol 類型: {type(symbol)}")
                    logger.error(f"   market_data 類型: {type(market_data)}")
                    logger.error(f"   config_dict 類型: {type(config_dict)}")
                    continue  # 跳過無法序列化的任務
                
                # 🔥 使用完全扁平化的參數（無嵌套，無閉包）
                future = self.global_pool.submit_safe(
                    _analyze_single_symbol_worker,  # 模塊級函數
                    symbol,                         # str (扁平參數1)
                    market_data,                    # dict (扁平參數2)
                    config_dict                     # dict (扁平參數3)
                )
                tasks.append((symbol, future))
            
            # 🔥 步驟3：收集結果（帶超時機制）
            timeout_seconds = self.config.PROCESS_TIMEOUT_SECONDS
            for symbol, future in tasks:
                try:
                    # 使用配置的超時時間
                    result = await loop.run_in_executor(None, future.result, timeout_seconds)
                    if result:
                        signals.append(result)
                except TimeoutError:
                    logger.warning(f"⚠️ 分析 {symbol} 超時（{timeout_seconds}秒）")
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
    
    async def close(self):
        """
        關閉執行器
        
        注意：v3.16.1 不關閉全局進程池（由應用生命週期管理）
        """
        logger.info("並行分析器關閉（全局進程池繼續運行）")
