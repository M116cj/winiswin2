"""Binance API error handling"""


class BinanceRequestError(Exception):
    """Binance API request error"""
    def __init__(self, code: int = None, message: str = None, http_status: int = None):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message or "Binance API error")
