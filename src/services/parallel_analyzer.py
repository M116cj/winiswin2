"""
並行分析器（v3.17+ ThreadPool 版本）
職責：批量處理大量交易對分析

v3.17+ 優化：
- 使用內建 ThreadPoolExecutor（無外部依賴）
- 移除所有 ProcessPool 遺留代碼
- 確保與 ICT 策略兼容
"""

import asyncio
from typing import List, Dict, Optional
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from src.config import Config

logger = logging.getLogger(__name__)


# 🔥 v3.16.2 修復：工作函數（線程池版本，無序列化問題）
def _analyze_single_symbol_worker(symbol: str, market_data: dict, config_dict: dict) -> Optional[Dict]:
    """
    單個交易對分析（線程池工作函數）
    
    v3.16.2 ThreadPool 版本：
    - 使用線程池，共享內存，無序列化需求
    - 可以直接使用模塊級 logger（無 thread.lock 問題）
    - 參數保持扁平化以便調用
    
    Args:
        symbol: 交易對名稱（str）
        market_data: 市場數據（Dict[str, Dict[str, Any]]），已轉換為純字典
        config_dict: 配置參數（Dict[str, Union[int, float, str, bool]]），只包含基本類型
    
    Returns:
        Optional[Dict]: 交易信號
    """
    # 🔥 線程池可以直接使用 logger（無序列化問題）
    import logging
    import pandas as pd
    
    try:
        # 🔥 步驟1：重建 DataFrame（從純字典恢復）
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
        
        # 🔥 步驟2：在線程內重建 Config 對象
        from src.config import Config
        config = Config()
        # 應用傳入的配置參數
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        # 🔥 步驟3：使用 ICT 策略執行分析
        result = None
        try:
            from src.strategies.ict_strategy import ICTStrategy
            trader = ICTStrategy()
            result = trader.analyze(symbol, reconstructed_data)
        except Exception as e:
            logger.error(f"❌ {symbol} ICT 策略分析失敗: {e}")
            result = None
        
        return result
        
    except MemoryError:
        logger.error(f"❌ {symbol} 記憶體不足")
        return None
    except Exception as e:
        logger.error(f"❌ {symbol} 分析失敗: {e}")
        return None


class ParallelAnalyzer:
    """並行分析器 - v3.17+ ThreadPool 版本"""
    
    def __init__(self, max_workers: Optional[int] = None, perf_monitor=None):
        """
        初始化並行分析器
        
        Args:
            max_workers: 線程池工作線程數（預設使用 Config.MAX_WORKERS）
            perf_monitor: 性能監控器
        """
        self.config = Config()
        self.max_workers = max_workers or Config.MAX_WORKERS
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # ✨ 性能監控
        self.perf_monitor = perf_monitor
        
        logger.info("✅ 並行分析器初始化（v3.17+ ThreadPool）")
        logger.info(f"   線程池工作線程: {self.max_workers}")
    
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
                
                # 🔥 v3.17+: 使用標準線程池提交任務
                future = self.executor.submit(
                    _analyze_single_symbol_worker,
                    symbol,
                    market_data,
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
            
        except Exception as e:
            logger.error(f"❌ 批量分析失敗: {e}", exc_info=True)
            return []
    
    async def close(self):
        """關閉執行器（v3.17+）"""
        if self.executor:
            self.executor.shutdown(wait=True)
            logger.info("✅ 並行分析器線程池已關閉")
