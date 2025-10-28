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


# 🔥 v3.16.2 修復：模塊級別工作函數（避免序列化類時包含 thread.lock）
def _analyze_single_symbol_worker(symbol_data: Dict, model_path: Optional[str], config_dict: Dict) -> Optional[Dict]:
    """
    單個交易對分析（工作進程函數）
    
    🔥 v3.16.2 關鍵修復：
    - 必須是模塊級別函數（不能是類方法）
    - 避免序列化類時包含模塊級 logger（含 thread.lock）
    - 輸入數據已轉換為純 Python 字典（無 DataFrame）
    
    Args:
        symbol_data: {'symbol': str, 'data': Dict[str, Dict]}
        model_path: ML 模型路徑（可選）
        config_dict: 配置字典（純數據）
    
    Returns:
        Optional[Dict]: 交易信號
    """
    # 🔥 子進程內部創建獨立 logger
    import logging
    import pandas as pd
    proc_logger = logging.getLogger(f"{__name__}.subprocess")
    
    try:
        # 🔥 步驟1：重建 DataFrame（從純字典恢復）
        reconstructed_data = {}
        for tf_key, tf_dict in symbol_data['data'].items():
            if tf_dict is not None and 'data' in tf_dict:
                # 從字典重建 DataFrame
                df = pd.DataFrame(tf_dict['data'])
                if 'index' in tf_dict:
                    df.index = tf_dict['index']
                reconstructed_data[tf_key] = df
            else:
                reconstructed_data[tf_key] = None
        
        # 🔥 步驟2：添加記憶體監控
        process = None
        try:
            import psutil
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            initial_memory = None
        
        # 🔥 步驟3：重建配置
        from src.config import Config
        config = Config()
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        # 🔥 步驟4：嘗試使用自我學習交易員
        try:
            from src.strategies.self_learning_trader import SelfLearningTrader
            
            trader = SelfLearningTrader(config=config)
            result = trader.analyze(symbol_data['symbol'], reconstructed_data)
            
        except Exception as e:
            # 🔥 降級到 ICT 策略
            proc_logger.warning(f"⚠️ 自我學習交易員不可用 ({e})，使用降級策略")
            from src.strategies.ict_strategy import ICTStrategy
            trader = ICTStrategy()
            result = trader.analyze(symbol_data['symbol'], reconstructed_data)
        
        # 🔥 記憶體監控
        if initial_memory is not None and process is not None:
            try:
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory
                
                if memory_increase > 500:  # 記憶體增加超過 500MB
                    proc_logger.warning(
                        f"⚠️ 記憶體洩漏警告 {symbol_data['symbol']}: +{memory_increase:.1f}MB"
                    )
            except Exception:
                pass
        
        return result
        
    except MemoryError:
        proc_logger.error(f"❌ 記憶體不足 {symbol_data.get('symbol', 'UNKNOWN')}")
        return None
    except Exception as e:
        proc_logger.error(f"❌ 分析失敗 {symbol_data.get('symbol', 'UNKNOWN')}: {e}")
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
            
            # 🔥 步驟2：提交所有分析任務（使用安全提交）
            for i, multi_tf_data in enumerate(multi_tf_data_list):
                # 檢查數據有效性
                if isinstance(multi_tf_data, Exception) or multi_tf_data is None:
                    continue
                
                # 確保是字典類型
                if not isinstance(multi_tf_data, dict):
                    continue
                
                symbol = symbols_data[i]['symbol']
                
                # 🔥 v3.16.2 關鍵修復：將 DataFrame 轉換為純字典（避免序列化問題）
                # DataFrame 在某些環境下序列化可能失敗，轉換為純 Python 類型最安全
                serializable_data = {}
                for tf_key, df in multi_tf_data.items():
                    if df is not None and hasattr(df, 'to_dict'):
                        # 轉換為純字典格式
                        serializable_data[tf_key] = {
                            'data': df.to_dict('list'),  # 轉換為列表字典
                            'index': df.index.tolist() if hasattr(df.index, 'tolist') else list(df.index)
                        }
                    else:
                        serializable_data[tf_key] = None
                
                symbol_data = {
                    'symbol': symbol,
                    'data': serializable_data  # 純 Python 字典
                }
                
                # 🔥 創建可序列化的配置字典（只包含基本類型）
                config_dict = {
                    'MIN_CONFIDENCE': self.config.MIN_CONFIDENCE,
                    'MAX_LEVERAGE': self.config.MAX_LEVERAGE,
                    'MIN_LEVERAGE': self.config.MIN_LEVERAGE,
                    'BASE_MARGIN_PCT': self.config.BASE_MARGIN_PCT,
                    'MIN_MARGIN_PCT': self.config.MIN_MARGIN_PCT,
                    'MAX_MARGIN_PCT': self.config.MAX_MARGIN_PCT,
                    'RISK_REWARD_RATIO': self.config.RISK_REWARD_RATIO,
                    'TRADING_ENABLED': self.config.TRADING_ENABLED
                }
                
                # 🔥 v3.16.2: 使用模塊級函數（避免序列化類）
                future = self.global_pool.submit_safe(
                    _analyze_single_symbol_worker,
                    symbol_data,
                    self._model_path,
                    config_dict
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
