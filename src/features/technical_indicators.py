"""
安全的技術指標計算器
職責：處理數據不足情況的技術指標計算
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class TechnicalIndicatorCalculator:
    """安全的技術指標計算器（針對數據不足情況優化）"""
    
    @staticmethod
    def safe_ema(close_prices: pd.Series, period: int) -> Optional[pd.Series]:
        """
        安全的EMA計算 - 處理數據不足情況
        
        Args:
            close_prices: 收盤價序列
            period: EMA週期
            
        Returns:
            EMA序列，如果數據不足則返回None
        """
        try:
            if close_prices is None or len(close_prices) == 0:
                logger.warning(f"EMA{period}計算失敗: 數據為空")
                return None
                
            if len(close_prices) < period:
                available_period = min(period, len(close_prices))
                if available_period >= 5:
                    logger.debug(f"EMA{period}數據不足，使用EMA{available_period}")
                    return close_prices.ewm(span=available_period, adjust=False).mean()
                else:
                    logger.warning(f"EMA{period}數據嚴重不足: {len(close_prices)}行")
                    return None
                    
            return close_prices.ewm(span=period, adjust=False).mean()
        except Exception as e:
            logger.error(f"EMA{period}計算錯誤: {e}")
            return None
    
    @staticmethod
    def safe_rsi(close_prices: pd.Series, period: int = 14) -> Optional[pd.Series]:
        """
        安全的RSI計算
        
        Args:
            close_prices: 收盤價序列
            period: RSI週期
            
        Returns:
            RSI序列，如果數據不足則返回None
        """
        try:
            if close_prices is None or len(close_prices) < period + 1:
                logger.warning(f"RSI{period}數據不足: {len(close_prices) if close_prices is not None else 0} < {period + 1}")
                return None
                
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except Exception as e:
            logger.error(f"RSI{period}計算錯誤: {e}")
            return None
    
    @staticmethod
    def safe_bollinger_bands(close_prices: pd.Series, period: int = 20, nbdev: float = 2.0) -> Optional[Tuple]:
        """
        安全的布林帶計算
        
        Args:
            close_prices: 收盤價序列
            period: 移動平均週期
            nbdev: 標準差倍數
            
        Returns:
            (上軌, 中軌, 下軌) 元組，如果數據不足則返回None
        """
        try:
            if close_prices is None or len(close_prices) < period:
                logger.warning(f"布林帶數據不足: {len(close_prices) if close_prices is not None else 0} < {period}")
                return None
                
            middle = close_prices.rolling(window=period).mean()
            std = close_prices.rolling(window=period).std()
            upper = middle + (std * nbdev)
            lower = middle - (std * nbdev)
            
            return upper, middle, lower
        except Exception as e:
            logger.error(f"布林帶計算錯誤: {e}")
            return None
    
    @staticmethod
    def calculate_basic_indicators(close_prices: pd.Series, min_data: int = 5) -> Dict:
        """
        計算基本技術指標（適應數據不足情況）
        
        Args:
            close_prices: 收盤價序列
            min_data: 最小數據要求
            
        Returns:
            指標字典
        """
        indicators = {}
        
        if close_prices is None or len(close_prices) < min_data:
            logger.warning(f"技術指標計算跳過: 數據不足 {len(close_prices) if close_prices is not None else 0} < {min_data}")
            return indicators
        
        indicators['ema_20'] = TechnicalIndicatorCalculator.safe_ema(close_prices, 20)
        indicators['ema_50'] = TechnicalIndicatorCalculator.safe_ema(close_prices, 50)
        
        if len(close_prices) >= 15:
            indicators['rsi_14'] = TechnicalIndicatorCalculator.safe_rsi(close_prices, 14)
        
        if len(close_prices) >= 20:
            bb_result = TechnicalIndicatorCalculator.safe_bollinger_bands(close_prices, 20)
            if bb_result:
                indicators['bb_upper'], indicators['bb_middle'], indicators['bb_lower'] = bb_result
        
        try:
            if len(close_prices) >= 5:
                sma_period = min(10, len(close_prices))
                indicators['sma_10'] = close_prices.rolling(window=sma_period).mean()
        except Exception as e:
            logger.error(f"SMA計算錯誤: {e}")
        
        return indicators
