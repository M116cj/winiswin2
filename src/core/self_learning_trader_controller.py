"""
v3.17+ 自我學習交易員控制器
核心編排器，擁有倉位的絕對控制權
"""

import logging
from typing import Optional, Dict, Any
import pandas as pd

from src.core.leverage_engine import LeverageEngine
from src.core.position_sizer import PositionSizer
from src.core.sltp_adjuster import SLTPAdjuster

logger = logging.getLogger(__name__)


class SelfLearningTraderController:
    """
    自我學習交易員控制器（v3.17+）
    
    職責：
    1. 接收 SelfLearningTrader 的信號
    2. 計算槓桿（基於勝率×信心度）
    3. 計算倉位數量（含 Binance 規格檢查）
    4. 調整 SL/TP（高槓桿→寬止損）
    5. 返回可執行的訂單包
    
    這是 v3.17+ 的核心決策者
    """
    
    def __init__(
        self,
        config_profile,
        self_learning_trader,
        binance_client=None
    ):
        """
        初始化控制器
        
        Args:
            config_profile: ConfigProfile 實例
            self_learning_trader: SelfLearningTrader 實例
            binance_client: BinanceClient 實例（可選）
        """
        self.config = config_profile
        self.trader = self_learning_trader
        self.binance_client = binance_client
        
        # 初始化三大引擎
        self.leverage_engine = LeverageEngine(config_profile)
        self.position_sizer = PositionSizer(config_profile, binance_client)
        self.sltp_adjuster = SLTPAdjuster(config_profile)
        
        logger.info("=" * 60)
        logger.info("✅ SelfLearningTraderController 初始化完成（v3.17+）")
        logger.info("   🎯 模式: 絕對控制權（無限制槓桿）")
        logger.info("   🧠 決策依據: 勝率 × 信心度")
        logger.info("=" * 60)
    
    async def analyze_and_execute(
        self,
        symbol: str,
        multi_tf_data: Dict[str, pd.DataFrame],
        account_equity: float
    ) -> Optional[Dict[str, Any]]:
        """
        分析並生成可執行訂單
        
        Args:
            symbol: 交易對符號
            multi_tf_data: 多時間框架數據
            account_equity: 賬戶權益（USDT）
            
        Returns:
            可執行訂單包，或 None（無信號/拒絕）
        """
        # 1. 調用 SelfLearningTrader 生成原始信號
        raw_signal = self.trader.analyze(symbol, multi_tf_data)
        
        if raw_signal is None:
            return None
        
        # 2. 提取關鍵決策參數
        win_probability = raw_signal.get('win_probability', 0.5)
        confidence = raw_signal.get('confidence', 0.5)
        rr_ratio = raw_signal.get('rr_ratio', 1.5)
        
        # 3. 驗證開倉條件
        is_valid, reject_reason = self.leverage_engine.validate_signal_conditions(
            win_probability, confidence, rr_ratio
        )
        
        if not is_valid:
            logger.debug(f"❌ {symbol} 拒絕開倉: {reject_reason}")
            return None
        
        # 4. 計算槓桿（無上限）
        leverage = self.leverage_engine.calculate_leverage(
            win_probability, confidence, verbose=True
        )
        
        # 5. 獲取入場價格和原始 SL/TP
        entry_price = raw_signal.get('entry_price', raw_signal.get('current_price'))
        base_sl = raw_signal.get('stop_loss')
        side = raw_signal.get('direction')
        
        # 6. 動態調整 SL/TP（高槓桿→寬止損）
        if base_sl:
            base_sl_pct = abs(entry_price - base_sl) / entry_price
            stop_loss, take_profit = self.sltp_adjuster.adjust_sl_tp_for_leverage(
                entry_price, side, base_sl_pct, leverage, verbose=True
            )
        else:
            # 如果沒有原始 SL，使用 ATR 計算
            atr = raw_signal.get('indicators', {}).get('atr', entry_price * 0.02)
            base_sl_pct = self.sltp_adjuster.get_recommended_base_sl(
                entry_price, atr, atr_multiplier=2.0
            )
            stop_loss, take_profit = self.sltp_adjuster.adjust_sl_tp_for_leverage(
                entry_price, side, base_sl_pct, leverage, verbose=True
            )
        
        # 7. 驗證 SL/TP 有效性
        is_valid_sltp, sltp_error = self.sltp_adjuster.validate_sltp_levels(
            entry_price, stop_loss, take_profit, side
        )
        
        if not is_valid_sltp:
            logger.warning(f"⚠️ {symbol} SL/TP 無效: {sltp_error}")
            return None
        
        # 8. 計算倉位數量（含 Binance 規格檢查）
        position_size, adjusted_sl = await self.position_sizer.calculate_position_size_async(
            account_equity, entry_price, stop_loss, leverage, symbol, verbose=True
        )
        
        # 9. 構建可執行訂單包
        executable_order = {
            # 原始信號信息
            **raw_signal,
            
            # v3.17+ 增強信息
            'win_probability': win_probability,
            'rr_ratio': rr_ratio,
            
            # 槓桿與倉位
            'leverage': leverage,
            'position_size': position_size,
            
            # 價格水平
            'entry_price': entry_price,
            'stop_loss': adjusted_sl,
            'take_profit': take_profit,
            
            # 風險計算
            'risk_amount': abs(entry_price - adjusted_sl) * position_size,
            'reward_amount': abs(take_profit - entry_price) * position_size,
            
            # 元數據
            'controller_version': 'v3.17+',
            'control_mode': 'self_learning_absolute',
        }
        
        # 10. 記錄決策日誌
        logger.info(
            f"✅ {symbol} {side} | "
            f"勝率:{win_probability:.1%} 信心:{confidence:.1%} → 槓桿:{leverage:.2f}x | "
            f"數量:{position_size:.6f} 入場:${entry_price:.2f} "
            f"SL:${adjusted_sl:.2f} TP:${take_profit:.2f}"
        )
        
        return executable_order
    
    def get_controller_status(self) -> Dict[str, Any]:
        """
        獲取控制器狀態摘要
        
        Returns:
            狀態字典
        """
        return {
            "version": "v3.17+",
            "mode": "self_learning_absolute_control",
            "leverage_engine": self.leverage_engine.get_leverage_summary(),
            "position_sizer": {
                "equity_usage": f"{self.config.equity_usage_ratio:.1%}",
                "min_notional": f"${self.config.min_notional_value:.2f}",
            },
            "sltp_adjuster": {
                "scale_factor": self.config.sltp_scale_factor,
                "max_scale": self.config.sltp_max_scale,
            },
        }
