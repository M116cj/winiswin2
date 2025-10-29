"""
v3.17+ 槓桿引擎
基於「勝率 × 信心度」計算無限制槓桿
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LeverageEngine:
    """
    槓桿計算引擎（v3.17+）
    
    公式：
    base = 1.0
    win_factor = max(0, (win_prob - 0.55) / 0.15)
    win_leverage = 1 + win_factor * 11  # 勝率 70% → 12x
    conf_factor = max(1.0, confidence / 0.5)
    leverage = base * win_leverage * conf_factor
    
    最小值：0.5x
    最大值：無上限
    """
    
    def __init__(self, config_profile):
        """
        初始化槓桿引擎
        
        Args:
            config_profile: ConfigProfile 實例
        """
        self.config = config_profile
        logger.info("✅ 槓桿引擎初始化完成（v3.17+ 無限制槓桿）")
        logger.info(f"   📊 勝率閾值: {self.config.min_win_probability:.1%}")
        logger.info(f"   📊 信心度閾值: {self.config.min_confidence:.1%}")
        logger.info(f"   📊 槓桿範圍: 無限制（0x ~ ∞）")
    
    def calculate_leverage(
        self, 
        win_probability: float, 
        confidence: float,
        verbose: bool = False
    ) -> float:
        """
        計算槓桿倍數（v3.18+：無上限，最小0.5x）
        
        Args:
            win_probability: 勝率預測（0-1）
            confidence: 信心度（0-1）
            verbose: 是否輸出詳細計算過程
            
        Returns:
            槓桿倍數（0.5x ~ ∞）
        """
        # 基礎槓桿
        base = self.config.leverage_base
        
        # 勝率因子：勝率超過 55% 後線性增長
        win_factor = max(0, (win_probability - self.config.leverage_win_threshold) / self.config.leverage_win_scale)
        win_leverage = 1 + win_factor * self.config.leverage_win_multiplier
        
        # 信心度因子：信心度越高，槓桿放大越多
        conf_factor = max(1.0, confidence / self.config.leverage_conf_scale)
        
        # 綜合槓桿
        leverage = base * win_leverage * conf_factor
        
        # 🔥 v3.18+ 新增：最小槓桿0.5x（防止過低導致倉位無意義）
        MIN_LEVERAGE = 0.5
        if leverage < MIN_LEVERAGE:
            if verbose:
                logger.debug(f"  ⚠️ 槓桿過低 ({leverage:.2f}x)，調整至最小值 {MIN_LEVERAGE}x")
            leverage = MIN_LEVERAGE
        
        if verbose:
            logger.debug(f"槓桿計算詳情:")
            logger.debug(f"  勝率: {win_probability:.1%} → win_factor: {win_factor:.2f} → win_leverage: {win_leverage:.2f}x")
            logger.debug(f"  信心度: {confidence:.1%} → conf_factor: {conf_factor:.2f}x")
            logger.debug(f"  最終槓桿: {leverage:.2f}x（範圍：0.5x ~ ∞）")
        
        return leverage
    
    def validate_signal_conditions(
        self, 
        win_probability: float, 
        confidence: float,
        rr_ratio: float
    ) -> tuple[bool, Optional[str]]:
        """
        驗證信號是否滿足開倉條件
        
        Args:
            win_probability: 勝率預測
            confidence: 信心度
            rr_ratio: 風險回報比
            
        Returns:
            (is_valid, reject_reason)
        """
        # 檢查勝率
        if win_probability < self.config.min_win_probability:
            return False, f"勝率不足: {win_probability:.1%} < {self.config.min_win_probability:.1%}"
        
        # 檢查信心度
        if confidence < self.config.min_confidence:
            return False, f"信心度不足: {confidence:.1%} < {self.config.min_confidence:.1%}"
        
        # 檢查風險回報比
        if rr_ratio < self.config.min_rr_ratio:
            return False, f"R:R 過低: {rr_ratio:.2f} < {self.config.min_rr_ratio:.2f}"
        
        if rr_ratio > self.config.max_rr_ratio:
            return False, f"R:R 過高: {rr_ratio:.2f} > {self.config.max_rr_ratio:.2f}"
        
        return True, None
    
    def get_leverage_summary(self) -> dict:
        """
        獲取槓桿引擎配置摘要
        
        Returns:
            配置字典
        """
        return {
            "leverage_type": "unlimited",
            "formula": "base × (1 + (winrate-0.55)/0.15 × 11) × (confidence/0.5)",
            "leverage_range": "unlimited (0x ~ ∞)",
            "min_win_probability": f"{self.config.min_win_probability:.1%}",
            "min_confidence": f"{self.config.min_confidence:.1%}",
            "min_rr_ratio": f"{self.config.min_rr_ratio:.1f}",
            "max_rr_ratio": f"{self.config.max_rr_ratio:.1f}",
        }
