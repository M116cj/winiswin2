"""🔥 Binance API Error Handling"""

class BinanceRequestError(Exception):
    """Base exception for Binance API errors"""
    pass

class BinanceAPIError(BinanceRequestError):
    """Binance API error"""
    pass

class BinanceOrderException(BinanceRequestError):
    """Binance order error"""
    pass
