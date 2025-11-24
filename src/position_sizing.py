"""
💰 Position Sizing Layer - Convert ML % Return Prediction to Order Amount
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Model Prediction Architecture:
  ML Model → Predicted % Return (e.g., +5%) → Position Sizing → Order Amount

The model predicts EXPECTED % RETURN (無論賺或虧), not aware of capital.
This layer calculates ACTUAL ORDER AMOUNT using Risk Management formulas.

Two versions provided:
  Version A (Basic): Fixed Risk % per trade
  Version B (Advanced): Kelly Criterion or ATR-weighted dynamic sizing
"""

import logging
import math
from typing import Dict, Optional, Tuple
from src.binance_constraints import get_binance_constraints

logger = logging.getLogger(__name__)


class PositionSizingV1:
    """
    版本 A: 固定風險比例 (Fixed Risk %)
    
    每次交易固定風險為總資金的 N%
    公式: Order Amount = (Total Capital × Risk %) / Stop Loss %
    
    例子：
      - 資金: $10,000
      - 風險: 2% ($200)
      - 停損: 2%
      - 下單金額 = $200 / 0.02 = $10,000 (保證金 + 槓桿計算後的實際金額)
    """
    
    # 配置
    RISK_PER_TRADE = 0.02  # 每次交易風險 2% 的總資金
    DEFAULT_SL_PERCENT = 0.02  # 預設停損 2%
    
    @staticmethod
    def calculate_order_amount(
        total_capital: float,
        predicted_return_pct: float,
        stop_loss_pct: float = DEFAULT_SL_PERCENT,
        symbol: str = "BTCUSDT",
        current_price: float = 0.0,
        leverage: int = 1
    ) -> Dict:
        """
        計算下單金額 (基礎版本)
        
        Args:
            total_capital: 帳戶總權益 (USD)
            predicted_return_pct: 模型預測的 % 收益 (例: 0.05 表示 +5%)
            stop_loss_pct: 停損百分比 (例: 0.02 表示 2%)
            symbol: 交易對
            current_price: 當前價格
            leverage: 槓桿倍數
        
        Returns:
            {
                'order_amount': 下單金額 (USD),
                'quantity': 下單數量 (token),
                'risk_amount': 單筆風險 (USD),
                'tp_pct': 止盈百分比,
                'sl_pct': 止損百分比,
                'recommended': 是否推薦下單,
                'version': 'A'
            }
        """
        
        try:
            # ❌ 風險驗證
            if total_capital <= 0:
                return {'recommended': False, 'reason': 'Invalid capital', 'version': 'A'}
            
            # 風險金額 (固定)
            risk_amount = total_capital * PositionSizingV1.RISK_PER_TRADE
            
            # 下單金額 = 風險金額 / 停損百分比
            # 邏輯: 如果停損 2%，我想冒 2% 風險，我需要投入 100% 的風險金額
            order_amount = risk_amount / stop_loss_pct
            
            # ✅ 驗證不超過帳戶規模
            max_order_amount = total_capital * 2  # 最多下單帳戶的 2 倍（考慮槓桿）
            if order_amount > max_order_amount:
                order_amount = max_order_amount
            
            # 計算下單數量
            quantity = 0.0
            if current_price > 0:
                quantity = order_amount / current_price
            
            # 止盈距離 (簡單規則: TP = SL + Predicted Return)
            # 例: SL = 2%, Prediction = +5% → TP 可能在 +7% (SL + prediction)
            tp_pct = stop_loss_pct + abs(predicted_return_pct)
            
            return {
                'order_amount': order_amount,
                'quantity': quantity,
                'risk_amount': risk_amount,
                'tp_pct': tp_pct,
                'sl_pct': stop_loss_pct,
                'recommended': True,
                'version': 'A',
                'reason': f'Risk ${risk_amount:.2f}, Order ${order_amount:.2f}'
            }
        
        except Exception as e:
            logger.error(f"V1 Position Sizing Error: {e}")
            return {'recommended': False, 'reason': f'Error: {e}', 'version': 'A'}


class PositionSizingV2:
    """
    版本 B: 動態部位規模 (Dynamic - Kelly Criterion or ATR-weighted)
    
    根據以下因素動態調整下單金額:
    1. 模型信心度 (Confidence)
    2. 模型勝率 (Win Rate)
    3. 市場波動率 (ATR - Average True Range)
    4. 預測收益率 (Predicted Return %)
    
    凱利公式應用:
      Kelly % = (Win% * Avg Win - Loss% * Avg Loss) / Avg Win
      Position Size = Kelly % * Capital
    
    例子:
      - Confidence: 0.80 (80%)
      - Winrate: 0.70 (70%)
      - Predicted Return: +5%
      - ATR: 1.2% → 更高風險 → 縮小部位
      - 計算: Position = Capital × Kelly % × Confidence × (1 / ATR 倍數)
    """
    
    BASE_RISK_PER_TRADE = 0.02  # 基準風險
    
    @staticmethod
    def calculate_kelly_criterion(
        win_rate: float,
        avg_win_pct: float,
        avg_loss_pct: float
    ) -> float:
        """
        計算凱利百分比
        
        Kelly % = (p * b - q) / b
        where:
          p = 勝率
          q = 1 - p (敗率)
          b = 勝時的倍數 (Avg Win / Avg Loss)
        
        Args:
            win_rate: 勝率 (0-1)
            avg_win_pct: 平均贏時的 % (例: 0.05 = 5%)
            avg_loss_pct: 平均虧時的 % (例: 0.02 = 2%)
        
        Returns:
            Kelly percentage (需要限制在 0-0.25 以避免過度槓桿)
        """
        try:
            if avg_loss_pct <= 0 or win_rate <= 0:
                return 0.02  # 回到預設 2%
            
            loss_rate = 1 - win_rate
            b = avg_win_pct / avg_loss_pct
            
            kelly = (win_rate * b - loss_rate) / b
            
            # 限制凱利比例在合理範圍 (0.5% - 25%)
            kelly = max(0.005, min(0.25, kelly))
            
            logger.debug(f"🎯 Kelly Criterion: {kelly:.2%} (WR={win_rate:.1%}, b={b:.2f})")
            return kelly
        
        except Exception as e:
            logger.debug(f"Kelly calculation error: {e}")
            return 0.02
    
    @staticmethod
    def calculate_atr_weight(atr_pct: float, reference_atr_pct: float = 0.02) -> float:
        """
        基於 ATR 的波動率加權
        
        邏輯: 波動率越高，風險越大 → 縮小部位
             波動率越低，風險越小 → 擴大部位
        
        Weight = Reference ATR / Current ATR
        
        例子:
          - Reference: 2%, Current: 1% → Weight = 2.0 (擴大部位 2倍)
          - Reference: 2%, Current: 4% → Weight = 0.5 (縮小部位 50%)
        
        Args:
            atr_pct: 當前 ATR % (例: 0.015 = 1.5%)
            reference_atr_pct: 參考 ATR % (預設 2%)
        
        Returns:
            ATR 權重倍數 (限制在 0.3 - 3.0)
        """
        try:
            if atr_pct <= 0:
                return 1.0
            
            weight = reference_atr_pct / atr_pct
            weight = max(0.3, min(3.0, weight))  # 限制倍數
            
            logger.debug(f"📊 ATR Weight: {weight:.2f}x (ATR={atr_pct:.2%})")
            return weight
        
        except Exception as e:
            logger.debug(f"ATR weight calculation error: {e}")
            return 1.0
    
    @staticmethod
    def calculate_order_amount(
        total_capital: float,
        predicted_return_pct: float,
        confidence: float = 0.70,
        win_rate: float = 0.60,
        atr_pct: float = 0.02,
        current_price: float = 0.0,
        symbol: str = "BTCUSDT",
        leverage: int = 1,
        use_kelly: bool = True
    ) -> Dict:
        """
        計算下單金額 (進階版本 - 動態凱利或波動率加權)
        
        Args:
            total_capital: 帳戶總權益 (USD)
            predicted_return_pct: 模型預測的 % 收益
            confidence: 模型信心度 (0-1)
            win_rate: 歷史勝率 (0-1)
            atr_pct: 市場 ATR % (用於波動率調整)
            current_price: 當前價格
            symbol: 交易對
            leverage: 槓桿倍數
            use_kelly: 是否使用凱利公式 (True) 或純 ATR 加權 (False)
        
        Returns:
            {
                'order_amount': 下單金額 (USD),
                'quantity': 下單數量,
                'risk_amount': 單筆風險,
                'tp_pct': 止盈百分比,
                'sl_pct': 止損百分比,
                'kelly_pct': 凱利百分比 (如果使用),
                'atr_weight': ATR 加權倍數,
                'confidence_factor': 信心度因子,
                'recommended': 是否推薦下單,
                'version': 'B'
            }
        """
        
        try:
            if total_capital <= 0:
                return {'recommended': False, 'reason': 'Invalid capital', 'version': 'B'}
            
            # ===== 第一步: 計算基礎風險 =====
            base_risk_pct = PositionSizingV2.BASE_RISK_PER_TRADE
            
            # ===== 第二步: 凱利公式 =====
            kelly_pct = base_risk_pct
            if use_kelly:
                # 使用歷史勝率計算凱利
                avg_win = abs(predicted_return_pct)  # 平均贏的金額
                avg_loss = 0.01  # 假設平均虧 1%
                kelly_pct = PositionSizingV2.calculate_kelly_criterion(win_rate, avg_win, avg_loss)
            
            # ===== 第三步: ATR 波動率調整 =====
            atr_weight = PositionSizingV2.calculate_atr_weight(atr_pct)
            
            # ===== 第四步: 信心度調整 =====
            # Confidence: 0.60 → 1.0x, 0.80 → 1.4x, 1.00 → 2.0x
            confidence_factor = 1.0 + (confidence - 0.60) * 2.5
            confidence_factor = max(1.0, min(2.0, confidence_factor))
            
            # ===== 第五步: 綜合計算下單金額 =====
            # Risk Amount = Capital × Kelly% × ATR Weight × Confidence Factor
            risk_amount = total_capital * kelly_pct * atr_weight * confidence_factor
            
            # ✅ 驗證不超過帳戶規模
            max_risk = total_capital * 0.10  # 最多冒 10% 帳戶
            risk_amount = min(risk_amount, max_risk)
            
            # 停損百分比 (基於 ATR，範圍 1%-5%)
            sl_pct = atr_pct * 0.5 + 0.01  # ATR的一半 + 基礎 1%
            sl_pct = max(0.01, min(0.05, sl_pct))
            
            # 下單金額 = 風險 / 停損
            order_amount = risk_amount / sl_pct if sl_pct > 0 else risk_amount
            
            # 計算數量
            quantity = 0.0
            if current_price > 0:
                quantity = order_amount / current_price
            
            # 止盈距離
            tp_pct = sl_pct + abs(predicted_return_pct)
            
            return {
                'order_amount': order_amount,
                'quantity': quantity,
                'risk_amount': risk_amount,
                'tp_pct': tp_pct,
                'sl_pct': sl_pct,
                'kelly_pct': kelly_pct,
                'atr_weight': atr_weight,
                'confidence_factor': confidence_factor,
                'recommended': True,
                'version': 'B',
                'calculation': {
                    'base_risk_pct': base_risk_pct,
                    'kelly_pct': kelly_pct,
                    'atr_weight': atr_weight,
                    'confidence_factor': confidence_factor,
                    'final_risk_pct': kelly_pct * atr_weight * confidence_factor
                }
            }
        
        except Exception as e:
            logger.error(f"V2 Position Sizing Error: {e}")
            return {'recommended': False, 'reason': f'Error: {e}', 'version': 'B'}


class PositionSizingFactory:
    """Factory to choose between V1 and V2"""
    
    @staticmethod
    def calculate(
        version: str = 'A',
        **kwargs
    ) -> Dict:
        """
        選擇版本並計算下單金額
        
        Usage:
            V1: PositionSizingFactory.calculate(
                version='A',
                total_capital=10000,
                predicted_return_pct=0.05,
                stop_loss_pct=0.02
            )
            
            V2: PositionSizingFactory.calculate(
                version='B',
                total_capital=10000,
                predicted_return_pct=0.05,
                confidence=0.80,
                win_rate=0.70,
                atr_pct=0.015,
                current_price=42000
            )
        """
        
        if version.upper() == 'A':
            return PositionSizingV1.calculate_order_amount(**kwargs)
        elif version.upper() == 'B':
            return PositionSizingV2.calculate_order_amount(**kwargs)
        else:
            logger.warning(f"Unknown version: {version}, defaulting to V1")
            return PositionSizingV1.calculate_order_amount(**kwargs)


# Convenience functions
def calculate_position_size_v1(**kwargs) -> Dict:
    """快速計算 V1"""
    return PositionSizingV1.calculate_order_amount(**kwargs)


def calculate_position_size_v2(**kwargs) -> Dict:
    """快速計算 V2"""
    return PositionSizingV2.calculate_order_amount(**kwargs)


def calculate_position_size(version: str = 'A', **kwargs) -> Dict:
    """通用計算"""
    return PositionSizingFactory.calculate(version=version, **kwargs)
