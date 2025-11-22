"""
v3.17+ 動態 SL/TP 調整器
高槓桿 → 寬止損/止盈，避免過早觸發
"""

from src.utils.logger_factory import get_logger
from typing import Tuple

logger = get_logger(__name__)


class SLTPAdjuster:
    """
    動態 SL/TP 調整器（v3.17+）
    
    邏輯：
    - 槓桿越高，止損/止盈範圍越寬
    - 放大因子：f = min(3.0, 1 + (leverage - 1) × 0.05)
    - SL/TP 距離 × f
    """
    
    def __init__(self, config_profile):
        """
        初始化 SL/TP 調整器
        
        Args:
            config_profile: config manager instance
        """
        self.config = config_profile
        logger.info("✅ SL/TP 調整器初始化完成（v3.17+）")
        logger.info(f"   📊 放大因子: 1 + (leverage-1) × {self.config.sltp_scale_factor}")
        logger.info(f"   📊 最大放大倍數: {self.config.sltp_max_scale:.1f}x")
    
    def adjust_sl_tp_for_leverage(
        self,
        entry_price: float,
        side: str,
        base_sl_pct: float,
        leverage: float,
        verbose: bool = False
    ) -> Tuple[float, float]:
        """
        根據槓桿調整 SL/TP
        
        Args:
            entry_price: 入場價格
            side: 方向（"LONG" 或 "SHORT"）
            base_sl_pct: 基礎止損百分比（例如 0.02 = 2%）
            leverage: 槓桿倍數
            verbose: 是否輸出詳細計算過程
            
        Returns:
            (stop_loss, take_profit)
        """
        # 計算放大因子
        scale_factor = self._calculate_scale_factor(leverage)
        
        # 調整後的 SL/TP 百分比
        adjusted_sl_pct = base_sl_pct * scale_factor
        adjusted_tp_pct = adjusted_sl_pct * self.config.sltp_tp_to_sl_ratio  # TP = SL × ratio
        
        # 計算實際價格
        if side == "LONG":
            stop_loss = entry_price * (1 - adjusted_sl_pct)
            take_profit = entry_price * (1 + adjusted_tp_pct)
        elif side == "SHORT":
            stop_loss = entry_price * (1 + adjusted_sl_pct)
            take_profit = entry_price * (1 - adjusted_tp_pct)
        else:
            raise ValueError(f"無效的方向: {side}")
        
        if verbose:
            logger.debug(f"SL/TP 調整詳情:")
            logger.debug(f"  槓桿: {leverage:.2f}x → 放大因子: {scale_factor:.2f}x")
            logger.debug(f"  基礎 SL: {base_sl_pct:.2%} → 調整後: {adjusted_sl_pct:.2%}")
            logger.debug(f"  調整後 TP: {adjusted_tp_pct:.2%}")
            logger.debug(f"  入場: ${entry_price:.2f} | SL: ${stop_loss:.2f} | TP: ${take_profit:.2f}")
        
        return stop_loss, take_profit
    
    def _calculate_scale_factor(self, leverage: float) -> float:
        """
        計算放大因子
        
        Args:
            leverage: 槓桿倍數
            
        Returns:
            放大因子（1.0 - 3.0）
        """
        scale = 1.0 + (leverage - 1) * self.config.sltp_scale_factor
        return min(scale, self.config.sltp_max_scale)
    
    def get_recommended_base_sl(
        self,
        entry_price: float,
        atr: float,
        atr_multiplier: float = 2.0
    ) -> float:
        """
        獲取推薦的基礎止損百分比（基於 ATR）
        
        Args:
            entry_price: 入場價格
            atr: 平均真實波動範圍
            atr_multiplier: ATR 倍數
            
        Returns:
            基礎止損百分比
        """
        sl_distance = atr * atr_multiplier
        base_sl_pct = sl_distance / entry_price
        
        # 確保 ≥ 最小止損距離
        return max(base_sl_pct, self.config.min_stop_distance_pct)
    
    def validate_sltp_levels(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        side: str
    ) -> Tuple[bool, str]:
        """
        驗證 SL/TP 是否有效
        
        Args:
            entry_price: 入場價格
            stop_loss: 止損價格
            take_profit: 止盈價格
            side: 方向（"LONG" 或 "SHORT"）
            
        Returns:
            (is_valid, error_message)
        """
        # 檢查止損距離
        sl_distance_pct = abs(entry_price - stop_loss) / entry_price
        if sl_distance_pct < self.config.min_stop_distance_pct:
            return False, f"止損距離過小: {sl_distance_pct:.2%} < {self.config.min_stop_distance_pct:.2%}"
        
        # 檢查方向邏輯
        if side == "LONG":
            if stop_loss >= entry_price:
                return False, f"LONG 止損必須 < 入場價: {stop_loss:.2f} >= {entry_price:.2f}"
            if take_profit <= entry_price:
                return False, f"LONG 止盈必須 > 入場價: {take_profit:.2f} <= {entry_price:.2f}"
        elif side == "SHORT":
            if stop_loss <= entry_price:
                return False, f"SHORT 止損必須 > 入場價: {stop_loss:.2f} <= {entry_price:.2f}"
            if take_profit >= entry_price:
                return False, f"SHORT 止盈必須 < 入場價: {take_profit:.2f} >= {entry_price:.2f}"
        
        return True, ""
    
    def get_sltp_summary(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        leverage: float
    ) -> dict:
        """
        獲取 SL/TP 摘要信息
        
        Args:
            entry_price: 入場價格
            stop_loss: 止損價格
            take_profit: 止盈價格
            leverage: 槓桿倍數
            
        Returns:
            SL/TP 摘要字典
        """
        sl_distance_pct = abs(entry_price - stop_loss) / entry_price
        tp_distance_pct = abs(take_profit - entry_price) / entry_price
        rr_ratio = tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0
        
        scale_factor = self._calculate_scale_factor(leverage)
        
        return {
            "entry_price": f"${entry_price:.2f}",
            "stop_loss": f"${stop_loss:.2f} ({sl_distance_pct:.2%})",
            "take_profit": f"${take_profit:.2f} ({tp_distance_pct:.2%})",
            "rr_ratio": f"{rr_ratio:.2f}",
            "leverage": f"{leverage:.2f}x",
            "scale_factor": f"{scale_factor:.2f}x",
        }
