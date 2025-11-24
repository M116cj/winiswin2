"""
📊 Percentage Return Model Wrapper - ML Output to % Return Prediction
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

轉換 ML 模型輸出為百分比收益率預測

新架構:
  1. ML Model → 預測信心度 (Confidence) + 歷史勝率 (Win Rate)
  2. Percentage Return Wrapper → 轉換為 % 收益率預測
  3. Position Sizing → 計算實際下單金額
  4. Trade Execution → 下單

例子:
  Confidence: 0.80 (80%)
  Win Rate: 0.70 (70%)
  ATR: 1.2%
  
  → Predicted Return: +5% (表示預測這次交易有 +5% 的潛在收益)
  → Position Sizing 計算下單金額
  → 執行下單
"""

import logging
from typing import Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


class PercentageReturnModel:
    """
    將 ML 模型的信心度/勝率轉換為 % 收益率預測
    
    邏輯:
      基礎回報率 = 2% (最低預測)
      信心度倍數: (conf - 0.60) * 10 (0.60 → 0%, 0.80 → 2%, 1.00 → 4%)
      勝率倍數: (wr - 0.60) * 5 (0.60 → 0%, 0.70 → 0.5%, 0.80 → 1%)
      
      Final Return = Base + Confidence Boost + WinRate Boost
    """
    
    BASE_RETURN_PCT = 0.02  # 基礎 2% 預測
    
    @staticmethod
    def calculate_predicted_return(
        confidence: float,
        win_rate: float,
        atr_pct: float = 0.02,
        market_volatility: float = 1.0,
        direction: str = "UP"
    ) -> float:
        """
        計算預測收益率 (%)
        
        Args:
            confidence: 模型信心度 (0-1)
            win_rate: 歷史勝率 (0-1)
            atr_pct: 市場 ATR % (用於波動率調整)
            market_volatility: 市場波動率倍數 (1.0 = normal)
            direction: 方向 (UP/DOWN)
        
        Returns:
            float: 預測收益率 (例: 0.05 = +5%)
        """
        
        try:
            # 驗證輸入
            confidence = max(0.0, min(1.0, confidence))
            win_rate = max(0.0, min(1.0, win_rate))
            
            # ===== 基礎計算 =====
            base_return = PercentageReturnModel.BASE_RETURN_PCT
            
            # 信心度倍數 (0.60 → 0, 0.80 → 2%, 1.00 → 4%)
            confidence_boost = max(0, (confidence - 0.60) * 10.0) / 100.0
            
            # 勝率倍數 (0.60 → 0, 0.70 → 0.5%, 0.80+ → 1%)
            winrate_boost = max(0, (win_rate - 0.60) * 5.0) / 100.0
            
            # 基礎預測 = 基礎 + 信心倍數(70%) + 勝率倍數(30%)
            predicted_return = base_return + (confidence_boost * 0.7) + (winrate_boost * 0.3)
            
            # ===== 波動率調整 =====
            # 高波動 → 降低預測 (風險更大)
            # 低波動 → 提高預測 (風險更小)
            volatility_adjustment = market_volatility  # 1.0 = no adjustment
            predicted_return = predicted_return * volatility_adjustment
            
            # 範圍限制 (0.5% - 15%)
            predicted_return = max(0.005, min(0.15, predicted_return))
            
            logger.debug(
                f"📊 Predicted Return: {predicted_return:.2%} "
                f"(Conf={confidence:.0%}, WR={win_rate:.0%}, ATR={atr_pct:.2%})"
            )
            
            return predicted_return
        
        except Exception as e:
            logger.error(f"Error calculating predicted return: {e}")
            return PercentageReturnModel.BASE_RETURN_PCT
    
    @staticmethod
    def predict_signal(
        signal_data: Dict,
        historical_stats: Optional[Dict] = None
    ) -> Dict:
        """
        基於信號資料預測收益率
        
        Args:
            signal_data: {
                'confidence': float,
                'direction': str,
                'strength': float,
                'features': {...},
                'symbol': str
            }
            historical_stats: {
                'win_rate': float,
                'avg_return': float,
                'atr': float
            }
        
        Returns:
            {
                'predicted_return_pct': 預測收益率 (例: 0.05),
                'confidence': 信心度,
                'direction': 方向,
                'explanation': 解釋文字
            }
        """
        
        try:
            confidence = signal_data.get('confidence', 0.65)
            direction = signal_data.get('direction', 'UP')
            symbol = signal_data.get('symbol', 'UNKNOWN')
            
            # 默認歷史統計
            if historical_stats is None:
                historical_stats = {
                    'win_rate': 0.65,
                    'atr': 0.02,
                    'market_volatility': 1.0
                }
            
            win_rate = historical_stats.get('win_rate', 0.65)
            atr_pct = historical_stats.get('atr', 0.02)
            market_volatility = historical_stats.get('market_volatility', 1.0)
            
            # 計算預測收益率
            predicted_return = PercentageReturnModel.calculate_predicted_return(
                confidence=confidence,
                win_rate=win_rate,
                atr_pct=atr_pct,
                market_volatility=market_volatility,
                direction=direction
            )
            
            # 生成解釋
            explanation = (
                f"{symbol} {direction}: "
                f"Predicted return +{predicted_return:.2%}, "
                f"Confidence {confidence:.0%}, "
                f"Historical WR {win_rate:.0%}"
            )
            
            return {
                'predicted_return_pct': predicted_return,
                'confidence': confidence,
                'direction': direction,
                'symbol': symbol,
                'explanation': explanation,
                'calculation': {
                    'base_return': PercentageReturnModel.BASE_RETURN_PCT,
                    'confidence_factor': max(0, (confidence - 0.60) * 10.0) / 100.0,
                    'winrate_factor': max(0, (win_rate - 0.60) * 5.0) / 100.0,
                    'atr': atr_pct,
                    'market_volatility': market_volatility
                }
            }
        
        except Exception as e:
            logger.error(f"Error predicting signal: {e}")
            return {
                'predicted_return_pct': PercentageReturnModel.BASE_RETURN_PCT,
                'confidence': 0.6,
                'direction': 'UNKNOWN',
                'explanation': f'Error: {e}'
            }


def get_percentage_return_model() -> PercentageReturnModel:
    """獲取百分比收益率模型實例"""
    return PercentageReturnModel()
