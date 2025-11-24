"""
📊 多時間框架數據緩衝區 - 聚合多個時間框架的 K 線數據
用於信號生成的完整多時間框架分析
"""

import logging
from typing import Dict, List, Optional
from collections import defaultdict
import time

logger = logging.getLogger(__name__)


class TimeframeBuffer:
    """
    聚合多個時間框架的 K 線數據
    
    - 每個符號維護 5 個時間框架的歷史數據
    - 自動聚合原始 tick 數據到不同時間框架
    - 提供完整的 candles_by_tf 結構用於多時間框架分析
    """
    
    # 時間框架配置（秒）
    TIMEFRAMES = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '1h': 3600,
        '1d': 86400
    }
    
    def __init__(self, max_candles_per_tf: int = 500):
        """
        初始化多時間框架緩衝區
        
        Args:
            max_candles_per_tf: 每個時間框架最多保留的 K 線數量
        """
        self.max_candles_per_tf = max_candles_per_tf
        
        # 格式：{symbol: {timeframe: [candles...]}}
        self.data: Dict[str, Dict[str, List[tuple]]] = defaultdict(
            lambda: {tf: [] for tf in self.TIMEFRAMES.keys()}
        )
        
        # 追蹤每個時間框架的當前開倉時間
        # 格式：{symbol: {timeframe: open_time}}
        self.current_candle_time: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {tf: 0 for tf in self.TIMEFRAMES.keys()}
        )
    
    def add_tick(self, symbol: str, tick: tuple) -> None:
        """
        添加 tick 數據並聚合到所有時間框架
        
        Args:
            symbol: 交易對
            tick: (timestamp_ms, open, high, low, close, volume)
        """
        timestamp_ms, o, h, l, c, v = tick
        timestamp = timestamp_ms / 1000.0  # 轉換為秒
        
        # 為每個時間框架聚合 tick
        for tf_name, tf_seconds in self.TIMEFRAMES.items():
            # 計算該 tick 應該屬於哪個 K 線
            candle_open_time = int(timestamp / tf_seconds) * tf_seconds
            
            # 如果是新的 K 線，創建新的 candle
            if candle_open_time > self.current_candle_time[symbol][tf_name]:
                # 保存舊 K 線（如果存在）
                if self.data[symbol][tf_name]:
                    # 更新最後一根 K 線的收盤價（如果時間相同，更新；否則創建新的）
                    pass
                
                # 創建新 K 線
                self.current_candle_time[symbol][tf_name] = candle_open_time
                new_candle = (
                    candle_open_time * 1000,  # timestamp_ms
                    c,  # open (用 close 作為開倉價)
                    c,  # high
                    c,  # low
                    c,  # close
                    v  # volume
                )
                self.data[symbol][tf_name].append(new_candle)
            else:
                # 更新當前 K 線的 OHLCV
                if self.data[symbol][tf_name]:
                    last_candle = self.data[symbol][tf_name][-1]
                    updated_candle = (
                        last_candle[0],  # timestamp_ms（不變）
                        last_candle[1],  # open（不變）
                        max(last_candle[2], h),  # high
                        min(last_candle[3], l),  # low
                        c,  # close（更新為最新價）
                        last_candle[5] + v  # volume 累加
                    )
                    self.data[symbol][tf_name][-1] = updated_candle
            
            # 限制緩衝區大小
            if len(self.data[symbol][tf_name]) > self.max_candles_per_tf:
                self.data[symbol][tf_name] = self.data[symbol][tf_name][-self.max_candles_per_tf:]
    
    def get_candles_by_tf(self, symbol: str) -> Dict[str, List[tuple]]:
        """
        獲取符號的所有時間框架 K 線數據
        
        Returns:
            {
                '1d': [...],
                '1h': [...],
                '15m': [...],
                '5m': [...],
                '1m': [...]
            }
        """
        if symbol not in self.data:
            return {tf: [] for tf in self.TIMEFRAMES.keys()}
        
        return {
            tf: list(self.data[symbol].get(tf, []))
            for tf in self.TIMEFRAMES.keys()
        }
    
    def has_sufficient_data(self, symbol: str, min_candles_per_tf: int = 3) -> bool:
        """
        檢查符號是否有足夠的多時間框架數據用於分析
        
        🔍 OPTIMIZED: Only check recent timeframes (5m, 15m, 1h)
           Skip 1d because WebSocket takes too long to accumulate daily data
        
        Args:
            symbol: 交易對
            min_candles_per_tf: 每個時間框架最少需要的 K 線數
            
        Returns:
            True 如果所有檢查的時間框架都有足夠的數據
        """
        if symbol not in self.data:
            return False
        
        # 🔍 Check only recent timeframes for faster signal generation
        required_tfs = ['5m', '15m', '1h']  # Skip '1d' and '1m' for efficiency
        for tf_name in required_tfs:
            if len(self.data[symbol].get(tf_name, [])) < min_candles_per_tf:
                return False
        
        return True
    
    def get_stats(self, symbol: str) -> Dict:
        """獲取緩衝區統計信息"""
        stats = {}
        if symbol in self.data:
            for tf_name in self.TIMEFRAMES.keys():
                candles = self.data[symbol][tf_name]
                stats[tf_name] = len(candles)
        
        return stats or {tf: 0 for tf in self.TIMEFRAMES.keys()}


# 全局多時間框架緩衝區
_buffer: Optional[TimeframeBuffer] = None


def get_timeframe_buffer() -> TimeframeBuffer:
    """獲取全局多時間框架緩衝區"""
    global _buffer
    if _buffer is None:
        _buffer = TimeframeBuffer()
        logger.critical("📊 TimeframeBuffer initialized")
    return _buffer
