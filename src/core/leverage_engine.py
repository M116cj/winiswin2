"""
v3.18.7+ 槓桿引擎（豁免期策略）
基於「勝率 × 信心度」計算動態槓桿
豁免期（0-100筆）：強制壓制至 1-3x
正常期（101+筆）：無限制（模型自行判定）
"""

from src.utils.logger_factory import get_logger
from typing import Optional

logger = get_logger(__name__)


class LeverageEngine:
    """
    槓桿計算引擎（v3.18.7+ 豁免期策略）
    
    基礎公式：
    base = 1.0
    win_factor = max(0, (win_prob - 0.55) / 0.15)
    win_leverage = 1 + win_factor * 11  # 勝率 70% → 12x
    conf_factor = max(1.0, confidence / 0.5)
    leverage = base * win_leverage * conf_factor
    
    豁免期壓制（v3.18.7+）：
    - 前100筆交易：強制限制 1-3x（風險控制）
    - 101+筆交易：無上限（模型自行判定）
    
    最小值：0.5x
    最大值：豁免期3x / 正常期無上限
    """
    
    def __init__(self, config_profile):
        """
        初始化槓桿引擎（v3.18.7+ 豁免期策略）
        
        Args:
            config_profile: config manager instance
        """
        self.config = config_profile
        logger.info("=" * 80)
        logger.info("✅ 槓桿引擎初始化完成（v4.1+ 漸進式豁免期）")
        logger.info(f"   📊 正常期: 勝率≥{self.config.MIN_WIN_PROBABILITY:.0%}, 信心≥{self.config.MIN_CONFIDENCE:.0%}, 槓桿動態（0.5x ~ ∞）")
        logger.info(f"   🎓 豁免期（前{self.config.BOOTSTRAP_TRADE_LIMIT}筆）漸進式策略:")
        logger.info(f"      階段1 (1-15筆): 勝率≥35%, 信心≥30%, 槓桿≤2x")
        logger.info(f"      階段2 (16-35筆): 勝率≥40%, 信心≥35%, 槓桿≤3x")
        logger.info(f"      階段3 (36-50筆): 勝率≥43%, 信心≥38%, 槓桿≤4x")
        logger.info("=" * 80)
    
    def calculate_leverage(
        self, 
        win_probability: float, 
        confidence: float,
        is_bootstrap_period: bool = False,
        max_leverage: Optional[float] = None,
        verbose: bool = False
    ) -> float:
        """
        計算槓桿倍數（v4.1+：漸進式豁免期槓桿上限）
        
        Args:
            win_probability: 勝率預測（0-1）
            confidence: 信心度（0-1）
            is_bootstrap_period: 是否在豁免期
            max_leverage: 階段性槓桿上限（v4.1+漸進式）
                - 階段1: 2x
                - 階段2: 3x
                - 階段3: 4x
                - 正常期: None（無上限）
            verbose: 是否輸出詳細計算過程
            
        Returns:
            槓桿倍數
            - 豁免期：根據階段上限（2x/3x/4x）
            - 正常期：0.5x ~ ∞（模型自行判定）
        """
        # 基礎槓桿
        base = self.config.leverage_base
        
        # 勝率因子：勝率超過 55% 後線性增長
        win_factor = max(0, (win_probability - self.config.leverage_win_threshold) / self.config.leverage_win_scale)
        win_leverage = 1 + win_factor * self.config.leverage_win_multiplier
        
        # 信心度因子：信心度越高，槓桿放大越多
        conf_factor = max(1.0, confidence / self.config.leverage_conf_scale)
        
        # 綜合槓桿（原始計算）
        leverage = base * win_leverage * conf_factor
        
        # 🔥 v4.1+ 漸進式豁免期槓桿控制
        if is_bootstrap_period and max_leverage is not None:
            # 豁免期：強制限制在階段性上限
            # 計算壓制後的槓桿：基於信心度線性映射到 1-max_leverage
            # confidence < 0.3 → 1x（最小值）
            # confidence 線性增長到 max_leverage
            leverage_range = max_leverage - 1.0
            bootstrap_leverage = 1.0 + max(0, min((confidence - 0.3) / 0.3, 1.0)) * leverage_range
            
            if verbose:
                logger.debug(f"🎓 漸進式豁免期槓桿:")
                logger.debug(f"  原始計算槓桿: {leverage:.2f}x")
                logger.debug(f"  勝率: {win_probability:.1%} → win_leverage: {win_leverage:.2f}x")
                logger.debug(f"  信心度: {confidence:.1%} → conf_factor: {conf_factor:.2f}x")
                logger.debug(f"  階段上限: {max_leverage:.1f}x")
                logger.debug(f"  壓制後槓桿: {bootstrap_leverage:.2f}x（範圍：1-{max_leverage:.0f}x）")
            
            return round(bootstrap_leverage, 2)
        elif is_bootstrap_period:
            # 向後兼容：如果沒有提供 max_leverage，使用舊的 3x 上限
            bootstrap_leverage = 1.0 + max(0, min((confidence - 0.4) / 0.1, 2.0))
            
            if verbose:
                logger.debug(f"🎓 豁免期槓桿壓制（舊模式）:")
                logger.debug(f"  壓制後槓桿: {bootstrap_leverage:.2f}x（範圍：1-3x）")
            
            return round(bootstrap_leverage, 2)
        
        # 正常期：應用最小槓桿限制
        if leverage < self.config.min_leverage:
            if verbose:
                logger.debug(f"  ⚠️ 槓桿過低 ({leverage:.2f}x)，調整至最小值 {self.config.min_leverage}x")
            leverage = self.config.min_leverage
        
        if verbose:
            logger.debug(f"📊 正常期槓桿計算:")
            logger.debug(f"  勝率: {win_probability:.1%} → win_factor: {win_factor:.2f} → win_leverage: {win_leverage:.2f}x")
            logger.debug(f"  信心度: {confidence:.1%} → conf_factor: {conf_factor:.2f}x")
            logger.debug(f"  最終槓桿: {leverage:.2f}x（範圍：0.5x ~ ∞）")
        
        return leverage
    
    def validate_signal_conditions(
        self, 
        win_probability: float, 
        confidence: float,
        rr_ratio: float,
        min_win_probability: Optional[float] = None,
        min_confidence: Optional[float] = None
    ) -> tuple[bool, Optional[str]]:
        """
        驗證信號是否滿足開倉條件（v3.18.7+ 支持動態門檻）
        
        Args:
            win_probability: 勝率預測
            confidence: 信心度
            rr_ratio: 風險回報比
            min_win_probability: 可選的動態勝率門檻（用於啟動豁免）
            min_confidence: 可選的動態信心度門檻（用於啟動豁免）
            
        Returns:
            (is_valid, reject_reason)
        """
        # 🔥 v3.18.7+ 使用動態門檻（如果提供）
        actual_min_win_prob = min_win_probability if min_win_probability is not None else self.config.min_win_probability
        actual_min_confidence = min_confidence if min_confidence is not None else self.config.min_confidence
        
        # 檢查勝率
        if win_probability < actual_min_win_prob:
            return False, f"勝率不足: {win_probability:.1%} < {actual_min_win_prob:.1%}"
        
        # 檢查信心度
        if confidence < actual_min_confidence:
            return False, f"信心度不足: {confidence:.1%} < {actual_min_confidence:.1%}"
        
        # 檢查風險回報比（固定門檻）
        if rr_ratio < self.config.min_rr_ratio:
            return False, f"R:R 過低: {rr_ratio:.2f} < {self.config.min_rr_ratio:.2f}"
        
        if rr_ratio > self.config.max_rr_ratio:
            return False, f"R:R 過高: {rr_ratio:.2f} > {self.config.max_rr_ratio:.2f}"
        
        return True, None
    
    def get_leverage_summary(self) -> dict:
        """
        獲取槓桿引擎配置摘要（v4.1+ 漸進式豁免期）
        
        Returns:
            配置字典
        """
        return {
            "leverage_type": "progressive_bootstrap",
            "formula": "base × (1 + (winrate-0.55)/0.15 × 11) × (confidence/0.5)",
            "bootstrap_strategy": "4-phase progressive (2x→3x→4x→dynamic)",
            "phase_1": "trades 1-15: winrate≥35%, conf≥30%, leverage≤2x",
            "phase_2": "trades 16-35: winrate≥40%, conf≥35%, leverage≤3x",
            "phase_3": "trades 36-50: winrate≥43%, conf≥38%, leverage≤4x",
            "normal_period": "trades 51+: winrate≥45%, conf≥40%, leverage dynamic",
            "leverage_range_normal": "0.5x ~ ∞ (unlimited)",
            "min_rr_ratio": f"{self.config.MIN_RR_RATIO:.1f}",
            "max_rr_ratio": f"{self.config.MAX_RR_RATIO:.1f}",
        }
