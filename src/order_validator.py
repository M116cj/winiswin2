"""
✅ 訂單驗證系統 - 確保所有下單完整符合 Binance 協議
包括容許誤差、精度、名義價值等完整驗證
"""

import logging
from typing import Dict, Tuple
from src.binance_constraints import get_binance_constraints
import math

logger = logging.getLogger(__name__)


class OrderValidator:
    """訂單驗證 - 完整 Binance 協議符合性檢查"""
    
    # 容許誤差參數
    TOLERANCE_NOTIONAL_USD = 0.01  # 1 cents 的容許誤差
    TOLERANCE_NOTIONAL_PERCENT = 0.001  # 0.1% 的容許誤差
    TOLERANCE_QUANTITY_PERCENT = 0.0001  # 0.01% 的數量容許誤差
    
    # 精度設置（根據 Binance 標準）
    PRICE_PRECISION_DECIMAL = 2  # 價格通常精度到小數點後 2-8 位
    QUANTITY_PRECISION_DECIMAL = 4  # 數量通常精度到小數點後 1-8 位
    
    @staticmethod
    def validate_order_with_tolerance(
        symbol: str,
        quantity: float,
        current_price: float,
        lot_size_step: float = 0.001,
        price_precision: int = 8,
        quantity_precision: int = 8
    ) -> Tuple[bool, str, Dict]:
        """
        完整驗證訂單，包含容許誤差
        
        驗證項目：
        1. 最低名義價值（含容許誤差）
        2. 最低數量
        3. 精度符合性
        4. 浮點精度問題
        
        Returns:
            (is_valid, error_message, validation_details)
        """
        constraints = get_binance_constraints()
        validation_details = {}
        
        # ========== 1. 精度處理 ==========
        # 根據 Binance 精度要求四捨五入
        quantity_rounded = OrderValidator._round_to_precision(
            quantity, 
            quantity_precision
        )
        price_rounded = OrderValidator._round_to_precision(
            current_price,
            price_precision
        )
        
        validation_details['quantity_original'] = quantity
        validation_details['quantity_rounded'] = quantity_rounded
        validation_details['price_original'] = current_price
        validation_details['price_rounded'] = price_rounded
        validation_details['quantity_adjusted'] = quantity != quantity_rounded
        validation_details['price_adjusted'] = current_price != price_rounded
        
        # 計算名義價值（使用四捨五入後的值）
        notional_value = quantity_rounded * price_rounded
        
        # ========== 2. 最低名義價值檢查 (含容許誤差) ==========
        min_notional = constraints.get_min_notional(symbol)
        
        # 計算容許誤差範圍
        tolerance_usd = OrderValidator.TOLERANCE_NOTIONAL_USD
        tolerance_percent = OrderValidator.TOLERANCE_NOTIONAL_PERCENT * min_notional
        tolerance = max(tolerance_usd, tolerance_percent)
        
        min_notional_with_tolerance = min_notional - tolerance
        
        validation_details['min_notional'] = min_notional
        validation_details['notional_value'] = notional_value
        validation_details['tolerance'] = tolerance
        validation_details['min_notional_with_tolerance'] = min_notional_with_tolerance
        
        if notional_value < min_notional_with_tolerance:
            error_msg = (
                f"❌ 訂單名義價值過低：{notional_value:.2f} USDT "
                f"< {min_notional:.2f} USDT (容許誤差: {tolerance:.2f} USDT)"
            )
            logger.warning(f"🛡️ {symbol}: {error_msg}")
            return False, error_msg, validation_details
        
        # ========== 3. 最低數量檢查 ==========
        min_qty = constraints.calculate_min_quantity(
            symbol,
            price_rounded,
            lot_size_step
        )
        
        # 考慮浮點誤差
        min_qty_with_tolerance = min_qty * (1 - OrderValidator.TOLERANCE_QUANTITY_PERCENT)
        
        validation_details['min_quantity'] = min_qty
        validation_details['min_quantity_with_tolerance'] = min_qty_with_tolerance
        
        if quantity_rounded < min_qty_with_tolerance:
            error_msg = (
                f"❌ 數量過小：{quantity_rounded} "
                f"< {min_qty} (容許誤差: {OrderValidator.TOLERANCE_QUANTITY_PERCENT*100:.2f}%)"
            )
            logger.warning(f"🛡️ {symbol}: {error_msg}")
            return False, error_msg, validation_details
        
        # ========== 4. 精度符合性 ==========
        # 檢查數量是否符合 stepSize
        quantity_step_check = (quantity_rounded / lot_size_step) % 1
        if quantity_step_check > OrderValidator.TOLERANCE_QUANTITY_PERCENT:
            # 調整到最近的有效 stepSize
            quantity_adjusted = math.ceil(quantity_rounded / lot_size_step) * lot_size_step
            validation_details['quantity_step_adjusted'] = quantity_adjusted
            validation_details['quantity_step_adjustment_needed'] = True
            quantity_rounded = quantity_adjusted
        else:
            validation_details['quantity_step_adjustment_needed'] = False
        
        # ========== 5. 重新計算名義價值 ==========
        notional_value_final = quantity_rounded * price_rounded
        
        # 確保調整後仍符合最低名義價值
        if notional_value_final < min_notional_with_tolerance:
            # 計算所需最小數量
            min_qty_final = min_notional / price_rounded
            min_qty_final_adjusted = math.ceil(min_qty_final / lot_size_step) * lot_size_step
            
            validation_details['quantity_final_adjusted'] = min_qty_final_adjusted
            quantity_rounded = min_qty_final_adjusted
            notional_value_final = quantity_rounded * price_rounded
        
        validation_details['notional_value_final'] = notional_value_final
        validation_details['quantity_final'] = quantity_rounded
        
        # ========== 6. 最終檢查 ==========
        if notional_value_final < min_notional:
            error_msg = f"❌ 最終名義價值 {notional_value_final:.2f} < {min_notional:.2f}"
            return False, error_msg, validation_details
        
        # ✅ 驗證通過
        logger.critical(
            f"✅ Order Validation PASSED: {symbol} | "
            f"Qty: {quantity_rounded} | Notional: ${notional_value_final:.2f} | "
            f"(Original: Qty {quantity}, Price ${current_price})"
        )
        
        return True, "", validation_details
    
    @staticmethod
    def _round_to_precision(value: float, decimal_places: int) -> float:
        """根據精度四捨五入"""
        if decimal_places < 0:
            return value
        
        factor = 10 ** decimal_places
        return round(value * factor) / factor
    
    @staticmethod
    def normalize_for_binance(
        symbol: str,
        quantity: float,
        current_price: float,
        lot_size_step: float = 0.001
    ) -> Tuple[float, float, bool]:
        """
        正規化訂單參數使其符合 Binance 要求
        
        Returns:
            (final_quantity, final_price, was_adjusted)
        """
        constraints = get_binance_constraints()
        
        # 計算最低數量
        min_qty = constraints.calculate_min_quantity(
            symbol,
            current_price,
            lot_size_step
        )
        
        # 確保數量至少是最低數量
        quantity_final = max(quantity, min_qty)
        
        # 調整到 stepSize 的倍數
        quantity_final = math.ceil(quantity_final / lot_size_step) * lot_size_step
        
        # 確保名義價值符合最低要求
        min_notional = constraints.get_min_notional(symbol)
        notional = quantity_final * current_price
        
        if notional < min_notional:
            # 重新計算所需的最小數量
            quantity_final = math.ceil((min_notional / current_price) / lot_size_step) * lot_size_step
        
        was_adjusted = (quantity != quantity_final)
        
        if was_adjusted:
            logger.debug(
                f"📊 Order normalized for {symbol}: "
                f"{quantity} → {quantity_final} "
                f"(notional: ${quantity_final * current_price:.2f})"
            )
        
        return quantity_final, current_price, was_adjusted


def get_order_validator():
    """全局訂單驗證器"""
    return OrderValidator()
