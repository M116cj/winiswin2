"""
💰 動態倉位和槓桿計算器
基於信心度、勝率、賬戶規模動態調整倉位大小和槓桿
遵守 Binance 約束：最低開倉限制、槓桿分檔、整數槓桿
"""

import logging
from typing import Dict, Tuple
from src.binance_constraints import get_binance_constraints

logger = logging.getLogger(__name__)


class PositionCalculator:
    """計算動態倉位大小和槓桿"""
    
    # 基準參數
    BASE_RISK_PER_TRADE = 0.02  # 單筆交易風險 2% 的賬戶
    MIN_CONFIDENCE_THRESHOLD = 0.60  # 信心度基準
    MIN_WINRATE_THRESHOLD = 0.60  # 勝率基準
    
    @staticmethod
    def calculate_position(
        balance: float,
        confidence: float,
        winrate: float,
        signal_direction: str = "UP",
        current_price: float = 0,
        symbol: str = ""
    ) -> Dict:
        """
        計算倉位大小和槓桿
        
        輸入：
        - balance: 賬戶餘額
        - confidence: 信號信心度 (0-1)
        - winrate: 模型勝率 (0-1)
        - signal_direction: 信號方向 (UP/DOWN)
        
        輸出：
        {
            'position_size': 基礎倉位（UST）,
            'leverage': 槓桿倍數 (1-10),
            'risk_amount': 單筆風險（USD）,
            'tp_distance': TP 距離（%）,
            'sl_distance': SL 距離（%）,
            'recommended': True/False (是否推薦開倉)
        }
        """
        
        # ❌ 不符合基準 → 拒絕
        if confidence < PositionCalculator.MIN_CONFIDENCE_THRESHOLD:
            return {'recommended': False, 'reason': f'Confidence too low: {confidence:.2f}'}
        
        if winrate < PositionCalculator.MIN_WINRATE_THRESHOLD:
            return {'recommended': False, 'reason': f'Winrate too low: {winrate:.2f}'}
        
        # ✅ 符合基準 → 計算倉位
        
        # 基礎風險金額
        base_risk = balance * PositionCalculator.BASE_RISK_PER_TRADE
        
        # 信心度倍數：0.60 → 1x，0.80 → 1.5x，1.00 → 2x
        confidence_multiplier = 1.0 + (confidence - 0.60) * 2.5
        confidence_multiplier = min(2.0, max(1.0, confidence_multiplier))
        
        # 勝率倍數：0.60 → 1x，0.70 → 1.4x，0.80+ → 2x
        winrate_multiplier = 1.0 + (winrate - 0.60) * 4.0
        winrate_multiplier = min(2.0, max(1.0, winrate_multiplier))
        
        # 綜合倍數（信心度 60%，勝率 40%）
        position_multiplier = (confidence_multiplier * 0.6) + (winrate_multiplier * 0.4)
        
        # 最終風險金額
        risk_amount = base_risk * position_multiplier
        
        # 倉位大小（假設 1% 的止損距離）
        position_size = risk_amount / 0.01  # 基礎計算，實際需要根據市場調整
        
        # ✅ 無限制槓桿計算（基於信心度和勝率）
        # 公式：base_leverage * (confidence_multiplier + winrate_multiplier)
        # 可以超過 125x，但 Binance API 會自動限制在符號的最大槓桿
        
        base_leverage = 2.0  # 基準 2x
        
        # 信心度槓桿倍數增加：0.60 → 1x, 1.00 → 7x
        confidence_leverage_boost = (confidence - 0.60) * 10.0  # 可高達 4x
        
        # 勝率槓桿倍數增加：0.60 → 1x, 0.80+ → 3x
        winrate_leverage_boost = (winrate - 0.60) * 10.0  # 可高達 2x
        
        # 綜合槓桿（信心度 70%，勝率 30%）
        # 無限制，由 Binance 的分檔系統自動限制
        leverage_raw = base_leverage * (1.0 + confidence_leverage_boost * 0.7 + winrate_leverage_boost * 0.3)
        
        # ✅ CRITICAL: 轉換為整數（Binance 只接受整數槓桿）
        leverage = get_binance_constraints().clamp_leverage(leverage_raw)
        
        # TP 和 SL 距離（基於信心度）
        # 高信心度 → 更緊的 SL，更遠的 TP
        # 低信心度 → 更寬的 SL，更近的 TP
        
        sl_distance = 0.015 / (confidence / 0.70)  # 反比例
        sl_distance = min(0.05, max(0.01, sl_distance))  # 1% - 5%
        
        tp_distance = 0.03 * (confidence / 0.70) * (leverage / 2)  # 正比例
        tp_distance = min(0.15, max(0.02, tp_distance))  # 2% - 15%
        
        # ✅ 如果提供了當前價格和符號，驗證 Binance 協議符合性
        binance_validation = None
        if current_price > 0 and symbol:
            is_valid, error_msg = get_binance_constraints().validate_order_size(
                symbol=symbol,
                quantity=position_size / leverage,  # 實際開倉量
                current_price=current_price,
                tolerance_percent=0.001  # 0.1% 容許誤差
            )
            binance_validation = {
                'valid': is_valid,
                'error': error_msg if not is_valid else "",
                'quantity': position_size / leverage,
                'notional_value': (position_size / leverage) * current_price
            }
        
        return {
            'recommended': True,
            'position_size': position_size,
            'leverage': leverage,  # ✅ 整數槓桿
            'leverage_raw': leverage_raw,  # 原始浮點槓桿（用於調試）
            'risk_amount': risk_amount,
            'multiplier': position_multiplier,
            'confidence_multiplier': confidence_multiplier,
            'winrate_multiplier': winrate_multiplier,
            'tp_distance': tp_distance,
            'sl_distance': sl_distance,
            'binance_validation': binance_validation,  # ✅ Binance 協議驗證
            'notes': (
                f"Confidence: {confidence:.0%} ({confidence_multiplier:.1f}x) | "
                f"Winrate: {winrate:.0%} ({winrate_multiplier:.1f}x) | "
                f"Leverage: {leverage}x (raw: {leverage_raw:.1f}x)"  # ✅ 顯示整數和原始值
            )
        }


def get_position_calculator():
    """全局倉位計算器"""
    return PositionCalculator()
