"""
📊 多時間框架分析 - 正確的高頻交易架構
分層分析：1D 趨勢 → 1H 確認 → 15m 機會 → 5m/1m 進場
"""

import logging
from typing import Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


class TimeframeAnalyzer:
    """多時間框架市場分析"""
    
    def __init__(self):
        self.timeframes = {
            '1d': {'data': [], 'trend': None, 'strength': 0},
            '1h': {'data': [], 'trend': None, 'strength': 0},
            '15m': {'data': [], 'trend': None, 'strength': 0},
            '5m': {'data': [], 'trend': None, 'strength': 0},
            '1m': {'data': [], 'trend': None, 'strength': 0},
        }
        
        # 信心度和勝率閾值
        self.MIN_CONFIDENCE = 0.60
        self.MIN_WINRATE = 0.60
    
    def analyze_trend(self, timeframe: str, candles: list) -> Dict:
        """
        分析單個時間框架的趨勢
        
        Returns:
            {
                'trend': 'UP' | 'DOWN' | 'RANGING',
                'strength': 0-1 (趨勢強度),
                'confidence': 0-1
            }
        """
        if len(candles) < 3:
            return {'trend': 'RANGING', 'strength': 0, 'confidence': 0}
        
        recent = candles[-3:]  # 最後3根 K 線
        closes = [c[4] for c in recent]  # close
        
        # 簡單趨勢檢測
        if closes[-1] > closes[-2] > closes[-3]:
            trend = 'UP'
            strength = min(1.0, (closes[-1] - closes[-3]) / closes[-3])
        elif closes[-1] < closes[-2] < closes[-3]:
            trend = 'DOWN'
            strength = min(1.0, (closes[-3] - closes[-1]) / closes[-3])
        else:
            trend = 'RANGING'
            strength = 0.3
        
        # 勢能強度基於價格動量
        momentum = abs(closes[-1] - closes[-2]) / closes[-2]
        confidence = min(1.0, strength + momentum * 0.5)
        
        return {
            'trend': trend,
            'strength': strength,
            'confidence': confidence
        }
    
    def validate_setup(self, symbol: str, candles_by_tf: Dict) -> Optional[Dict]:
        """
        驗證多時間框架設置
        
        規則：
        1. 1D 確認主趨勢
        2. 1H 確認中期趨勢（與 1D 一致）
        3. 15m 確認機會（與 1D/1H 一致）
        4. 5m/1m 確認進場點
        
        Returns:
            信號對象或 None（不符合條件）
        """
        try:
            # 第 1 層：1D 趨勢確認
            d1_analysis = self.analyze_trend('1d', candles_by_tf.get('1d', []))
            if d1_analysis['confidence'] < self.MIN_CONFIDENCE:
                logger.debug(f"❌ {symbol} 1D 信心不足: {d1_analysis['confidence']:.2f}")
                return None
            
            # 第 2 層：1H 與 1D 一致
            h1_analysis = self.analyze_trend('1h', candles_by_tf.get('1h', []))
            if h1_analysis['trend'] != d1_analysis['trend']:
                logger.debug(f"❌ {symbol} 1H 與 1D 不一致")
                return None
            
            # 第 3 層：15m 機會確認
            m15_analysis = self.analyze_trend('15m', candles_by_tf.get('15m', []))
            if m15_analysis['trend'] != d1_analysis['trend']:
                logger.debug(f"❌ {symbol} 15m 與 1D 不一致")
                return None
            
            # 第 4 層：5m/1m 進場確認
            m5_analysis = self.analyze_trend('5m', candles_by_tf.get('5m', []))
            m1_analysis = self.analyze_trend('1m', candles_by_tf.get('1m', []))
            
            # 進場方向必須與主趨勢一致
            entry_trend = m1_analysis['trend']
            if entry_trend != d1_analysis['trend']:
                logger.debug(f"❌ {symbol} 進場方向與主趨勢不一致")
                return None
            
            # 綜合信心度計算
            # 1D: 40% 權重 (主趨勢)
            # 1H: 30% 權重 (確認)
            # 15m: 20% 權重 (機會)
            # 5m+1m: 10% 權重 (進場)
            
            composite_confidence = (
                d1_analysis['confidence'] * 0.40 +
                h1_analysis['confidence'] * 0.30 +
                m15_analysis['confidence'] * 0.20 +
                m5_analysis['confidence'] * 0.05 +
                m1_analysis['confidence'] * 0.05
            )
            
            if composite_confidence < self.MIN_CONFIDENCE:
                logger.debug(f"❌ {symbol} 綜合信心不足: {composite_confidence:.2f}")
                return None
            
            # ✅ 設置通過所有驗證
            signal = {
                'symbol': symbol,
                'direction': d1_analysis['trend'],
                'confidence': composite_confidence,
                'strength': d1_analysis['strength'],
                'timeframe_analysis': {
                    '1d': d1_analysis,
                    '1h': h1_analysis,
                    '15m': m15_analysis,
                    '5m': m5_analysis,
                    '1m': m1_analysis
                }
            }
            
            logger.warning(
                f"🎯 Signal Generated: {symbol} {signal['direction']} "
                f"@ {composite_confidence:.2%} confidence"
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error in validate_setup: {e}", exc_info=True)
            return None


def get_timeframe_analyzer():
    """全局時間框架分析器"""
    global _analyzer
    if '_analyzer' not in globals():
        _analyzer = TimeframeAnalyzer()
    return _analyzer
