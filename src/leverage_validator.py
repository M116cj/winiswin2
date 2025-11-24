"""
✅ 槓桿驗證器 - 確保所有槓桿操作都使用整數
"""

import logging
from src.binance_constraints import get_binance_constraints

logger = logging.getLogger(__name__)


def validate_and_clamp_leverage(
    calculated_leverage: float,
    symbol: str,
    position_notional: float
) -> int:
    """
    驗證和限制槓桿到 Binance 允許的範圍
    
    流程：
    1. 計算的槓桿轉換為整數
    2. 檢查不超過該符號的最大槓桿
    3. 返回最終的整數槓桿
    
    Args:
        calculated_leverage: 計算的槓桿（浮點數）
        symbol: 交易對
        position_notional: 持倉名義價值（USDT）
        
    Returns:
        最終的整數槓桿
    """
    constraints = get_binance_constraints()
    
    # ✅ 轉換為整數
    leverage_int = constraints.clamp_leverage(calculated_leverage)
    
    # 獲得該符號和持倉大小的最大允許槓桿
    max_allowed = constraints.get_max_leverage(symbol, position_notional)
    
    # 確保不超過 Binance 限制
    final_leverage = min(leverage_int, max_allowed)
    
    # 記錄如果有調整
    if final_leverage < leverage_int:
        logger.warning(
            f"⚠️ Leverage clamped for {symbol}: "
            f"{leverage_int}x → {final_leverage}x (max allowed at ${position_notional:.2f})"
        )
    
    return final_leverage
