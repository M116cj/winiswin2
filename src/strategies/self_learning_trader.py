"""
SelfLearningTrader v3.17+ - 智能決策核心
職責：槓桿計算、倉位計算、動態 SL/TP、倉位評估
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
import logging

from src.strategies.rule_based_signal_generator import RuleBasedSignalGenerator
from src.core.leverage_engine import LeverageEngine
from src.core.position_sizer import PositionSizer
from src.core.sltp_adjuster import SLTPAdjuster
from src.config import Config

logger = logging.getLogger(__name__)


class SelfLearningTrader:
    """
    SelfLearningTrader v3.17+ - 智能決策核心
    
    核心理念：
    「模型擁有無限制槓桿控制權，唯一準則是勝率 × 信心度」
    
    職責：
    1. 槓桿計算（無上限）：基於勝率 × 信心度
    2. 倉位計算（含 10 USDT 下限）：符合 Binance 規格
    3. 動態 SL/TP（高槓桿 → 寬止損）：防止過早觸發
    4. 倉位評估：24/7 監控並決定平倉時機
    """
    
    def __init__(self, config=None, binance_client=None):
        """
        初始化 SelfLearningTrader
        
        Args:
            config: 配置對象
            binance_client: Binance 客戶端（用於獲取交易規格）
        """
        self.config = config or Config
        self.binance_client = binance_client
        
        # 初始化信號生成器
        self.signal_generator = RuleBasedSignalGenerator(config)
        
        # 初始化三大引擎
        self.leverage_engine = LeverageEngine(config)
        self.position_sizer = PositionSizer(config, binance_client)
        self.sltp_adjuster = SLTPAdjuster(config)
        
        logger.info("=" * 80)
        logger.info("✅ SelfLearningTrader v3.17+ 初始化完成")
        logger.info("   🎯 模式: 無限制槓桿（基於勝率 × 信心度）")
        logger.info("   🧠 決策依據: win_probability × confidence")
        logger.info("   🛡️  風險控制: 動態 SL/TP + 10 USDT 最小倉位")
        logger.info("=" * 80)
    
    def analyze(
        self,
        symbol: str,
        multi_tf_data: Dict[str, pd.DataFrame]
    ) -> Optional[Dict]:
        """
        分析並生成交易信號（含槓桿、倉位、SL/TP 計算）
        
        Args:
            symbol: 交易對
            multi_tf_data: 多時間框架數據
        
        Returns:
            完整的交易信號（可直接執行），或 None
        """
        try:
            # 步驟 1：生成基礎信號
            base_signal = self.signal_generator.generate_signal(symbol, multi_tf_data)
            
            if base_signal is None:
                return None
            
            # 步驟 2：提取決策參數
            win_probability = base_signal['win_probability']
            confidence = base_signal['confidence']
            rr_ratio = base_signal['rr_ratio']
            
            # 步驟 3：驗證開倉條件
            is_valid, reject_reason = self.leverage_engine.validate_signal_conditions(
                win_probability, confidence, rr_ratio
            )
            
            if not is_valid:
                logger.debug(f"❌ {symbol} 拒絕開倉: {reject_reason}")
                return None
            
            # 步驟 4：計算槓桿（無上限）
            leverage = self.calculate_leverage(
                win_probability,
                confidence,
                verbose=True
            )
            
            # 步驟 5：獲取入場價格和基礎 SL/TP
            entry_price = base_signal['entry_price']
            base_sl = base_signal['stop_loss']
            base_tp = base_signal['take_profit']
            direction = base_signal['direction']
            
            # 步驟 6：動態調整 SL/TP（高槓桿 → 寬止損）
            base_sl_pct = abs(entry_price - base_sl) / entry_price
            stop_loss, take_profit = self.adjust_sl_tp_for_leverage(
                entry_price,
                direction,
                base_sl_pct,
                leverage,
                verbose=True
            )
            
            # 步驟 7：驗證 SL/TP 有效性
            is_valid_sltp, sltp_error = self.sltp_adjuster.validate_sltp_levels(
                entry_price, stop_loss, take_profit, direction
            )
            
            if not is_valid_sltp:
                logger.warning(f"⚠️ {symbol} SL/TP 無效: {sltp_error}，使用安全值")
                # 使用安全的 SL/TP
                safe_sl_pct = 0.01  # 1%
                stop_loss, take_profit = self.adjust_sl_tp_for_leverage(
                    entry_price, direction, safe_sl_pct, leverage, verbose=False
                )
            
            # 步驟 8：計算倉位數量（含 10 USDT 下限）
            # 注意：這裡需要賬戶權益，暫時返回信號，由 PositionController 調用
            
            # 構建完整信號
            final_signal = {
                **base_signal,  # 包含所有基礎信號數據
                'leverage': leverage,
                'adjusted_stop_loss': stop_loss,
                'adjusted_take_profit': take_profit,
                'leverage_info': {
                    'win_probability': win_probability,
                    'confidence': confidence,
                    'calculated_leverage': leverage
                }
            }
            
            logger.info(
                f"🎯 {symbol} 完整信號: {direction} @ {entry_price:.2f} | "
                f"槓桿={leverage:.1f}x | SL={stop_loss:.2f} | TP={take_profit:.2f} | "
                f"勝率={win_probability*100:.1f}% | 信心度={confidence*100:.1f}%"
            )
            
            return final_signal
            
        except Exception as e:
            logger.error(f"❌ {symbol} 分析失敗: {e}", exc_info=True)
            return None
    
    def calculate_leverage(
        self,
        win_probability: float,
        confidence: float,
        verbose: bool = False
    ) -> float:
        """
        計算槓桿（無上限）
        
        公式：
        1. win_factor = (win_prob - 0.55) / 0.15
           - win_prob = 0.55 → win_factor = 0 → 1x
           - win_prob = 0.70 → win_factor = 1 → 12x
        
        2. win_leverage = 1 + win_factor × 11
        
        3. conf_factor = confidence / 0.5
           - confidence = 0.50 → conf_factor = 1.0
           - confidence = 1.00 → conf_factor = 2.0
        
        4. leverage = base × win_leverage × conf_factor
        
        Args:
            win_probability: 勝率（0-1）
            confidence: 信心度（0-1）
            verbose: 是否輸出詳細日誌
        
        Returns:
            計算的槓桿倍數（無上限，最低 0.5x）
        """
        base = 1.0
        
        # 勝率因子
        win_factor = max(0, (win_probability - 0.55) / 0.15)
        win_leverage = 1 + win_factor * 11  # 最高 12x（當 win_prob = 0.70）
        
        # 信心度因子
        conf_factor = max(1.0, confidence / 0.5)  # 最低 1.0，最高 2.0
        
        # 最終槓桿
        leverage = base * win_leverage * conf_factor
        
        # 確保最低 0.5x
        leverage = max(0.5, leverage)
        
        if verbose:
            logger.info(
                f"   📊 槓桿計算: 勝率={win_probability:.2%} → win_leverage={win_leverage:.2f}x | "
                f"信心度={confidence:.2%} → conf_factor={conf_factor:.2f}x | "
                f"最終槓桿={leverage:.2f}x"
            )
        
        return leverage
    
    async def calculate_position_size(
        self,
        account_equity: float,
        entry_price: float,
        stop_loss: float,
        leverage: float,
        symbol: str,
        verbose: bool = False
    ) -> float:
        """
        計算倉位數量（含 10 USDT 下限 + Binance 規格檢查）
        
        邏輯：
        1. margin = equity × 0.8（80% 資金利用率）
        2. notional = leverage × margin
        3. size = notional / entry_price
        4. 確保 size × entry_price ≥ 10 USDT
        5. 確保符合 Binance 最小數量精度
        
        Args:
            account_equity: 賬戶權益（USDT）
            entry_price: 入場價格
            stop_loss: 止損價格
            leverage: 槓桿倍數
            symbol: 交易對
            verbose: 是否輸出詳細日誌
        
        Returns:
            倉位數量
        """
        # 止損安全檢查
        sl_distance_pct = abs(entry_price - stop_loss) / entry_price
        if sl_distance_pct < 0.003:  # 止損距離 < 0.3%
            if entry_price > stop_loss:
                stop_loss = entry_price * 0.997  # LONG
            else:
                stop_loss = entry_price * 1.003  # SHORT
            
            if verbose:
                logger.warning(
                    f"   ⚠️ 止損距離過小 ({sl_distance_pct:.3%})，調整為 0.3%"
                )
        
        # 計算名義價值
        margin = account_equity * 0.8  # 80% 資金利用率
        notional = leverage * margin
        size = notional / entry_price
        
        # ⭐ 確保最低 10 USDT 名義價值 ⭐
        min_notional = 10.0
        if size * entry_price < min_notional:
            size = min_notional / entry_price
            if verbose:
                logger.info(
                    f"   📏 調整倉位至最小值: {min_notional} USDT / {entry_price:.2f} = {size:.6f}"
                )
        
        # Binance 最小數量精度檢查
        if self.binance_client:
            try:
                min_qty = await self.binance_client.get_min_quantity(symbol)
                if size < min_qty:
                    size = min_qty
                    if verbose:
                        logger.info(
                            f"   📏 調整倉位至 Binance 最小數量: {min_qty}"
                        )
            except Exception as e:
                logger.warning(f"   ⚠️ 無法獲取 {symbol} 最小數量: {e}")
        
        if verbose:
            logger.info(
                f"   💰 倉位計算: 權益=${account_equity:.2f} | 槓桿={leverage:.1f}x | "
                f"名義價值=${notional:.2f} | 數量={size:.6f} | "
                f"實際價值=${size * entry_price:.2f}"
            )
        
        return size
    
    def adjust_sl_tp_for_leverage(
        self,
        entry_price: float,
        side: str,
        base_sl_pct: float,
        leverage: float,
        verbose: bool = False
    ) -> tuple:
        """
        動態調整 SL/TP（高槓桿 → 寬止損）
        
        邏輯：
        - scale = 1.0 + (leverage - 1) × 0.05
        - 槓桿 1x → scale = 1.0（不調整）
        - 槓桿 10x → scale = 1.45（擴大 45%）
        - 槓桿 20x → scale = 1.95（擴大 95%）
        - 最大 scale = 3.0（最多擴大 3 倍）
        
        Args:
            entry_price: 入場價格
            side: 方向（'LONG' 或 'SHORT'）
            base_sl_pct: 基礎止損百分比
            leverage: 槓桿倍數
            verbose: 是否輸出詳細日誌
        
        Returns:
            (stop_loss, take_profit)
        """
        # 計算調整比例
        scale = 1.0 + (leverage - 1) * 0.05
        scale = min(scale, 3.0)  # 最大 3 倍
        
        # 調整 SL/TP
        adjusted_sl_pct = base_sl_pct * scale
        adjusted_tp_pct = adjusted_sl_pct * 1.5  # TP = SL × 1.5
        
        # 計算實際價格
        if side == 'LONG':
            stop_loss = entry_price * (1 - adjusted_sl_pct)
            take_profit = entry_price * (1 + adjusted_tp_pct)
        else:  # SHORT
            stop_loss = entry_price * (1 + adjusted_sl_pct)
            take_profit = entry_price * (1 - adjusted_tp_pct)
        
        if verbose:
            logger.info(
                f"   🎯 SL/TP 調整: 槓桿={leverage:.1f}x → scale={scale:.2f}x | "
                f"基礎 SL={base_sl_pct:.2%} → 調整後={adjusted_sl_pct:.2%} | "
                f"SL=${stop_loss:.2f} | TP=${take_profit:.2f}"
            )
        
        return stop_loss, take_profit
    
    async def evaluate_positions(
        self,
        positions: List[Dict]
    ) -> Dict[str, str]:
        """
        評估所有持倉並決定是否平倉
        
        Args:
            positions: 持倉列表
        
        Returns:
            {position_id: decision} 字典
            decision 可以是：'HOLD', 'CLOSE', 'ADJUST_SL', 'ADJUST_TP'
        """
        decisions = {}
        
        for position in positions:
            position_id = None
            try:
                position_id = position.get('id') or position.get('symbol')
                pnl_pct = position.get('pnl_pct', 0.0)
                
                # 100% 虧損熔斷（PnL ≤ -99%）
                if pnl_pct <= -0.99:
                    decisions[position_id] = 'CLOSE'
                    logger.warning(
                        f"🚨 {position_id} 觸發 100% 虧損熔斷 (PnL={pnl_pct:.2%})，立即平倉"
                    )
                    continue
                
                # 其他評估邏輯（後續擴展）
                # 例如：移動止損、部分止盈等
                decisions[position_id] = 'HOLD'
                
            except Exception as e:
                if position_id:
                    logger.error(f"❌ 評估持倉 {position_id} 失敗: {e}")
                    decisions[position_id] = 'HOLD'
                else:
                    logger.error(f"❌ 評估持倉失敗（無法獲取 ID）: {e}")
        
        return decisions
