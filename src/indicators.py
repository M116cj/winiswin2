"""
📊 Technical Indicators - SMC Pattern Recognition
Minimal version for signal generation
"""

class Indicators:
    """Technical indicators for market analysis"""
    
    @staticmethod
    def rsi(prices, period=14):
        """Relative Strength Index"""
        if len(prices) < period:
            return 50
        gains = sum(max(0, prices[i] - prices[i-1]) for i in range(-period, 0))
        losses = sum(max(0, prices[i-1] - prices[i]) for i in range(-period, 0))
        rs = gains / (losses + 0.0001)
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def atr(highs, lows, closes, period=14):
        """Average True Range"""
        if len(highs) < period:
            return 0
        trs = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            trs.append(tr)
        return sum(trs[-period:]) / period if trs else 0
