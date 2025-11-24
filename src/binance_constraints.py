"""
Binance 協議限制查詢和驗證
包括最低開倉限制、槓桿限制等
"""

import logging
from typing import Dict, Optional
import aiohttp

logger = logging.getLogger(__name__)

# Binance 最低名義價值（USDT）
MINIMUM_NOTIONAL_VALUES = {
    'BTCUSDT': 50.0,      # BTC: 50 USDT
    'ETHUSDT': 20.0,      # ETH: 20 USDT
    # 其他所有對：5 USDT（默認）
    'DEFAULT': 5.0
}

# Binance 槓桿限制（按持倉大小分檔）
LEVERAGE_BRACKETS = {
    'BTCUSDT': [
        {'notional_bracket': 50000, 'initial_margin': 0.1, 'max_leverage': 125},
        {'notional_bracket': 100000, 'initial_margin': 0.125, 'max_leverage': 100},
        {'notional_bracket': 500000, 'initial_margin': 0.25, 'max_leverage': 50},
        {'notional_bracket': 1000000, 'initial_margin': 0.5, 'max_leverage': 25},
        {'notional_bracket': 5000000, 'initial_margin': 1.0, 'max_leverage': 10},
        {'notional_bracket': 8000000, 'initial_margin': 2.0, 'max_leverage': 5},
        {'notional_bracket': 10000000, 'initial_margin': 5.0, 'max_leverage': 2},
    ],
    'ETHUSDT': [
        {'notional_bracket': 20000, 'initial_margin': 0.1, 'max_leverage': 125},
        {'notional_bracket': 50000, 'initial_margin': 0.125, 'max_leverage': 100},
        {'notional_bracket': 100000, 'initial_margin': 0.25, 'max_leverage': 50},
        {'notional_bracket': 500000, 'initial_margin': 0.5, 'max_leverage': 25},
        {'notional_bracket': 1000000, 'initial_margin': 1.0, 'max_leverage': 10},
        {'notional_bracket': 2000000, 'initial_margin': 2.0, 'max_leverage': 5},
        {'notional_bracket': 5000000, 'initial_margin': 5.0, 'max_leverage': 2},
    ]
}


class BinanceConstraints:
    """Binance 交易限制管理"""
    
    @staticmethod
    def get_min_notional(symbol: str) -> float:
        """
        獲得符號的最低名義價值
        
        Args:
            symbol: 交易對 (如 BTCUSDT)
            
        Returns:
            最低名義價值（USDT）
        """
        return MINIMUM_NOTIONAL_VALUES.get(symbol, MINIMUM_NOTIONAL_VALUES['DEFAULT'])
    
    @staticmethod
    def calculate_min_quantity(
        symbol: str,
        current_price: float,
        lot_size_step: float = 0.001
    ) -> float:
        """
        計算符號的最低開倉數量
        
        公式：
        minimum_qty = MAX(
            lot_size.minQty,
            min_notional / current_price
        )
        
        然後四捨五入到 stepSize 精度
        
        Args:
            symbol: 交易對
            current_price: 當前價格
            lot_size_step: LOT_SIZE stepSize（默認 0.001）
            
        Returns:
            最低開倉數量
        """
        min_notional = BinanceConstraints.get_min_notional(symbol)
        min_qty_from_notional = min_notional / current_price
        
        # 四捨五入到 stepSize
        import math
        min_qty = math.ceil(min_qty_from_notional / lot_size_step) * lot_size_step
        
        return min_qty
    
    @staticmethod
    def validate_order_size(
        symbol: str,
        quantity: float,
        current_price: float,
        lot_size_step: float = 0.001,
        tolerance_percent: float = 0.001  # 0.1% 容許誤差
    ) -> tuple[bool, str]:
        """
        驗證訂單大小是否符合 Binance 限制（含容許誤差）
        
        容許誤差用於處理浮點精度問題
        
        Args:
            symbol: 交易對
            quantity: 開倉數量
            current_price: 當前價格
            lot_size_step: LOT_SIZE stepSize
            tolerance_percent: 容許誤差百分比（默認 0.1%）
            
        Returns:
            (is_valid, error_message)
        """
        min_qty = BinanceConstraints.calculate_min_quantity(
            symbol,
            current_price,
            lot_size_step
        )
        
        notional_value = quantity * current_price
        min_notional = BinanceConstraints.get_min_notional(symbol)
        
        # 應用容許誤差
        tolerance = min_notional * tolerance_percent
        min_notional_with_tolerance = min_notional - tolerance
        
        if notional_value < min_notional_with_tolerance:
            return False, (
                f"Order notional {notional_value:.2f} USDT < "
                f"minimum {min_notional:.2f} USDT "
                f"(tolerance: {tolerance:.2f} USDT)"
            )
        
        # 數量容許誤差
        quantity_tolerance = min_qty * tolerance_percent
        min_qty_with_tolerance = min_qty - quantity_tolerance
        
        if quantity < min_qty_with_tolerance:
            return False, (
                f"Order quantity {quantity} < minimum {min_qty} "
                f"(tolerance: {quantity_tolerance})"
            )
        
        return True, ""
    
    @staticmethod
    def get_max_leverage(symbol: str, notional_value: float) -> int:
        """
        根據持倉名義價值和符號獲得最大槓桿
        
        Binance 使用分檔制：持倉越大，最大槓桿越低
        
        Args:
            symbol: 交易對
            notional_value: 持倉名義價值（USDT）
            
        Returns:
            最大槓桿倍數（整數）
        """
        # 從 LEVERAGE_BRACKETS 獲得符號的分檔信息
        brackets = LEVERAGE_BRACKETS.get(symbol)
        if not brackets:
            # 默認分檔：最多 20x（新用戶默認）
            return 20
        
        # 找到適用的分檔
        for bracket in brackets:
            if notional_value <= bracket['notional_bracket']:
                return int(bracket['max_leverage'])
        
        # 如果超出最大分檔，返回最小槓桿
        return int(brackets[-1]['max_leverage'])
    
    @staticmethod
    def clamp_leverage(leverage: float) -> int:
        """
        將槓桿倍數限制為整數並確保有效
        
        重要：Binance 只接受整數槓桿
        
        Args:
            leverage: 計算的槓桿倍數
            
        Returns:
            有效的整數槓桿（確保 >= 1）
        """
        # 將浮點數轉換為整數（向下取整）
        # 不向上取整，因為超過 Binance 限制會被拒絕
        leverage_int = int(leverage)
        
        # 確保至少 1x
        return max(1, leverage_int)


def get_binance_constraints():
    """全局 Binance 限制管理器"""
    return BinanceConstraints()
