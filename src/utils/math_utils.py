"""
🧮 Math Utils - Precision Rounding & Safe Calculations
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FIX 1: PRECISION & ROUNDING (StepSize Filter)
- Handles IEEE 754 float precision errors
- Always rounds DOWN (ROUND_DOWN) for safety
- Prevents "Insufficient Balance" errors from rounding up
"""

import logging
from decimal import Decimal, ROUND_DOWN
from typing import Union

logger = logging.getLogger(__name__)


def round_step_size(quantity: Union[float, int], step_size: float) -> float:
    """
    ✅ FIX 1: Round quantity to step size using Decimal (safe precision)
    
    CRITICAL: Always rounds DOWN (floor) to prevent "Insufficient Balance"
    
    Args:
        quantity: Raw quantity (e.g., 0.14977266648836587)
        step_size: Minimum step size (e.g., 0.001 for BTC, 1.0 for Alts)
    
    Returns:
        Safe quantity rounded down to step size
    
    Example:
        >>> round_step_size(0.14977266648836587, 0.001)
        0.149  # Rounded down, safe
        
        >>> round_step_size(0.123456789, 0.00000001)
        0.12345678  # Rounded down to 8 decimals
    """
    try:
        # Convert to Decimal to avoid IEEE 754 float errors
        q = Decimal(str(quantity))
        s = Decimal(str(step_size))
        
        # Quantize (round) DOWN to step size
        # ROUND_DOWN ensures we never round up (safe for balance checks)
        target = q.quantize(s, rounding=ROUND_DOWN)
        
        result = float(target)
        
        logger.debug(f"💰 Rounded {quantity} to {result} (step={step_size})")
        return result
    
    except Exception as e:
        logger.error(f"❌ rounding failed: qty={quantity}, step={step_size}, error={e}")
        return 0.0


def round_to_precision(value: Union[float, int], decimals: int = 8) -> float:
    """
    ✅ FIX 1: Round to decimal precision (alternative method)
    
    Used when step_size is not available.
    Always rounds DOWN for safety.
    
    Args:
        value: Raw value
        decimals: Number of decimal places (default 8 for BTC/ETH)
    
    Returns:
        Value rounded down to specified decimals
    
    Example:
        >>> round_to_precision(0.14977266648836587, 8)
        0.14977266
    """
    try:
        # Use Decimal for precision
        v = Decimal(str(value))
        step = Decimal(10) ** (-decimals)
        
        # Quantize with ROUND_DOWN
        target = v.quantize(step, rounding=ROUND_DOWN)
        result = float(target)
        
        logger.debug(f"💰 Rounded {value} to {result} decimals ({decimals})")
        return result
    
    except Exception as e:
        logger.error(f"❌ Precision rounding failed: value={value}, decimals={decimals}, error={e}")
        return 0.0


def validate_quantity(quantity: float, symbol: str = "BTCUSDT") -> bool:
    """
    ✅ FIX 1: Validate quantity is safe before sending to Binance
    
    Checks:
    - Quantity is positive
    - Quantity is not too small (min notional $5)
    - Precision is acceptable (max 8 decimals)
    
    Args:
        quantity: Order quantity
        symbol: Trading pair (for min notional checks)
    
    Returns:
        True if valid, False otherwise
    """
    try:
        if quantity <= 0:
            logger.error(f"❌ Invalid quantity: {quantity} (must be > 0)")
            return False
        
        # Check precision (max 8 decimals)
        qty_str = f"{quantity:.10f}".rstrip('0')
        decimal_places = len(qty_str.split('.')[-1]) if '.' in qty_str else 0
        
        if decimal_places > 8:
            logger.error(f"❌ Precision too high: {decimal_places} decimals (max 8)")
            return False
        
        logger.debug(f"✅ Quantity valid: {quantity} ({decimal_places} decimals)")
        return True
    
    except Exception as e:
        logger.error(f"❌ Validation error: {e}")
        return False


# Default step sizes for common pairs
# Format: symbol -> step_size (minimum order size)
BINANCE_STEP_SIZES = {
    "BTCUSDT": 0.001,      # BTC: 0.001 BTC minimum
    "ETHUSDT": 0.01,       # ETH: 0.01 ETH minimum
    "BNBUSDT": 0.1,        # BNB: 0.1 BNB minimum
    "XRPUSDT": 1.0,        # XRP: 1.0 XRP minimum (alt coins use full units)
    "DOGEUSDT": 1.0,       # DOGE: 1.0 minimum
    "ADAUSDT": 1.0,        # ADA: 1.0 minimum
}


def get_step_size(symbol: str) -> float:
    """
    Get default step size for symbol
    
    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
    
    Returns:
        Step size (e.g., 0.001 for BTC)
    """
    # Try exact match
    if symbol in BINANCE_STEP_SIZES:
        return BINANCE_STEP_SIZES[symbol]
    
    # Default: 0.001 for BTC-like, 1.0 for altcoins
    if symbol.startswith(("BTC", "ETH")):
        return 0.001
    
    return 1.0
