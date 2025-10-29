"""
🔥 v3.18+ 自我學習交易員控制器
核心編排器，擁有倉位的絕對控制權

v3.18+ 新特性:
- 集成EvaluationEngine進行統一信號評估
- 40/40/20競價評分系統（信心值40% + 勝率40% + 報酬率20%）
- 智能訂單類型選擇（限價/市價）
- 50%帳戶權益上限保護
- 完整original_signal存儲
"""

import logging
from typing import Optional, Dict, Any
import pandas as pd

from src.core.leverage_engine import LeverageEngine
from src.core.position_sizer import PositionSizer
from src.core.sltp_adjuster import SLTPAdjuster
from src.core.evaluation_engine import EvaluationEngine, MarketContext

logger = logging.getLogger(__name__)


class SelfLearningTraderController:
    """
    🔥 v3.18+ 自我學習交易員控制器
    
    職責：
    1. 接收 SelfLearningTrader 的信號
    2. 使用EvaluationEngine統一評估（信心值/勝率）
    3. 40/40/20競價評分系統
    4. 計算槓桿（基於勝率×信心度，0.5x~∞）
    5. 計算倉位數量（≤50%帳戶權益，≥Binance最小值）
    6. 調整 SL/TP（高槓桿→寬止損）
    7. 智能訂單類型選擇
    8. 返回可執行的訂單包（含original_signal）
    
    這是 v3.18+ 的核心決策者
    """
    
    def __init__(
        self,
        config_profile,
        self_learning_trader,
        binance_client=None,
        evaluation_engine: Optional[EvaluationEngine] = None
    ):
        """
        初始化控制器（v3.18+）
        
        Args:
            config_profile: ConfigProfile 實例
            self_learning_trader: SelfLearningTrader 實例
            binance_client: BinanceClient 實例（可選）
            evaluation_engine: EvaluationEngine 實例（v3.18+，可選）
        """
        self.config = config_profile
        self.trader = self_learning_trader
        self.binance_client = binance_client
        
        # 🔥 v3.18+ 新增：統一評估引擎
        self.evaluation_engine = evaluation_engine or EvaluationEngine(model=None)
        
        # 初始化三大引擎
        self.leverage_engine = LeverageEngine(config_profile)
        self.position_sizer = PositionSizer(config_profile, binance_client)
        self.sltp_adjuster = SLTPAdjuster(config_profile)
        
        logger.info("=" * 60)
        logger.info("✅ SelfLearningTraderController 初始化完成（v3.18+）")
        logger.info("   🎯 模式: 絕對控制權（無限制槓桿，0.5x~∞）")
        logger.info("   🧠 決策依據: 勝率 × 信心度 + 40/40/20競價")
        logger.info("   🛡️ 保護: 50%帳戶權益上限 + Binance最小值檢查")
        logger.info(f"   🤖 評估引擎: {self.evaluation_engine.get_engine_info()['engine_type']}")
        logger.info("=" * 60)
    
    async def analyze_and_execute(
        self,
        symbol: str,
        multi_tf_data: Dict[str, pd.DataFrame],
        account_equity: float
    ) -> Optional[Dict[str, Any]]:
        """
        🔥 v3.18+ 分析並生成可執行訂單（完整重構版）
        
        新特性:
        - 使用EvaluationEngine統一評估
        - 40/40/20競價評分系統
        - 50%帳戶權益上限保護
        - 智能訂單類型選擇
        - original_signal完整存儲
        
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
        
        # 🔥 v3.18+ Step 2: 使用EvaluationEngine即時計算信心值和勝率
        entry_price = raw_signal.get('entry_price', raw_signal.get('current_price'))
        
        # 構建當前市場上下文（從multi_tf_data提取）
        market_context = self._build_market_context(multi_tf_data, raw_signal)
        
        # 即時計算信心值和勝率（統一評估）
        confidence = self.evaluation_engine.calculate_current_confidence(
            raw_signal, entry_price, market_context
        )
        win_probability = self.evaluation_engine.calculate_current_win_probability(
            raw_signal, entry_price, market_context
        )
        reward_ratio = self.evaluation_engine.calculate_reward_ratio(
            raw_signal, entry_price
        )
        
        # 更新raw_signal（確保一致性）
        raw_signal['confidence'] = confidence
        raw_signal['win_probability'] = win_probability
        raw_signal['rr_ratio'] = reward_ratio
        
        # 🔥 v3.18+ Step 3: 40/40/20競價評分系統
        entry_score = self._calculate_entry_score(confidence, win_probability, reward_ratio)
        
        logger.debug(
            f"📊 {symbol} 競價評分: {entry_score:.2%} "
            f"(信心:{confidence:.1%}×40% + 勝率:{win_probability:.1%}×40% + 報酬:{reward_ratio:.2f}×20%)"
        )
        
        # 3. 驗證開倉條件
        is_valid, reject_reason = self.leverage_engine.validate_signal_conditions(
            win_probability, confidence, reward_ratio
        )
        
        if not is_valid:
            logger.debug(f"❌ {symbol} 拒絕開倉: {reject_reason}")
            return None
        
        # 4. 計算槓桿（0.5x~∞無上限）
        leverage = self.leverage_engine.calculate_leverage(
            win_probability, confidence, verbose=True
        )
        
        # 5. 獲取入場價格和原始 SL/TP
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
        
        # 🔥 v3.18+ Step 8: 計算倉位數量（含50%上限+Binance最小值檢查）
        position_size, adjusted_sl = await self.position_sizer.calculate_position_size_async(
            account_equity, entry_price, stop_loss, leverage, symbol, verbose=True
        )
        
        # 關鍵檢查：如果position_size=0，表示50%上限與Binance最小值衝突
        if position_size <= 0:
            logger.warning(
                f"⚠️ {symbol} 跳過開倉: 帳戶權益${account_equity:.2f}過低，"
                f"50%上限無法滿足Binance最小倉位要求"
            )
            return None
        
        # 🔥 v3.18+ Step 9: 智能訂單類型選擇
        order_type = self._determine_order_type(symbol, raw_signal, market_context)
        
        # 🔥 v3.18+ Step 10: 構建可執行訂單包（含original_signal）
        executable_order = {
            # 原始信號信息
            **raw_signal,
            
            # v3.18+ 增強信息
            'win_probability': win_probability,
            'confidence': confidence,  # 使用EvaluationEngine計算的值
            'rr_ratio': reward_ratio,
            'entry_score': entry_score,  # 40/40/20競價分數
            
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
            
            # 訂單類型
            'order_type': order_type,  # "LIMIT" or "MARKET"
            
            # 🔥 v3.18+ 關鍵：存儲完整原始信號（用於PositionMonitor即時評估）
            'original_signal': raw_signal.copy(),
            
            # 元數據
            'controller_version': 'v3.18+',
            'control_mode': 'self_learning_absolute_with_evaluation_engine',
        }
        
        # 11. 記錄決策日誌
        logger.info(
            f"✅ {symbol} {side} [{order_type}] | "
            f"勝率:{win_probability:.1%} 信心:{confidence:.1%} 評分:{entry_score:.1%} → 槓桿:{leverage:.2f}x | "
            f"數量:{position_size:.6f} 入場:${entry_price:.2f} "
            f"SL:${adjusted_sl:.2f} TP:${take_profit:.2f}"
        )
        
        return executable_order
    
    def get_controller_status(self) -> Dict[str, Any]:
        """
        獲取控制器狀態摘要（v3.18+）
        
        Returns:
            狀態字典
        """
        return {
            "version": "v3.18+",
            "mode": "self_learning_absolute_control_with_evaluation_engine",
            "evaluation_engine": self.evaluation_engine.get_engine_info(),
            "leverage_engine": self.leverage_engine.get_leverage_summary(),
            "position_sizer": {
                "equity_usage": f"{self.config.equity_usage_ratio:.1%}",
                "min_notional": f"${self.config.min_notional_value:.2f}",
                "max_account_usage": "50%",
            },
            "sltp_adjuster": {
                "scale_factor": self.config.sltp_scale_factor,
                "max_scale": self.config.sltp_max_scale,
            },
        }
    
    # ========== v3.18+ 輔助方法 ==========
    
    def _build_market_context(
        self,
        multi_tf_data: Dict[str, pd.DataFrame],
        raw_signal: Dict[str, Any]
    ) -> MarketContext:
        """
        從多時間框架數據構建市場上下文
        
        Args:
            multi_tf_data: 多時間框架數據（包含 '1h', '15m', '5m'）
            raw_signal: 原始信號數據
        
        Returns:
            MarketContext: 市場上下文對象
        """
        # 1. 提取趨勢方向（優先使用1h趨勢）
        trends = raw_signal.get('trends', {})
        h1_trend = trends.get('h1', 'neutral').upper()
        
        if 'BULLISH' in h1_trend or 'UP' in h1_trend:
            trend_direction = "BULLISH"
        elif 'BEARISH' in h1_trend or 'DOWN' in h1_trend:
            trend_direction = "BEARISH"
        else:
            trend_direction = "NEUTRAL"
        
        # 2. 計算流動性分數（基於成交量）
        try:
            m15_data = multi_tf_data.get('15m')
            if m15_data is not None and len(m15_data) > 20:
                recent_volume = m15_data['volume'].iloc[-10:].mean()
                avg_volume = m15_data['volume'].iloc[-100:].mean()
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
                liquidity_score = min(volume_ratio, 1.5) / 1.5  # 歸一化到0-1
            else:
                liquidity_score = 0.5
                volume_ratio = 1.0
        except:
            liquidity_score = 0.5
            volume_ratio = 1.0
        
        # 3. 計算波動率（ATR/價格）
        atr = raw_signal.get('indicators', {}).get('atr')
        current_price = raw_signal.get('current_price', raw_signal.get('entry_price'))
        
        if atr and current_price:
            volatility = atr / current_price
        else:
            volatility = 0.02  # 默認2%波動率
        
        # 4. 提取技術指標
        indicators = raw_signal.get('indicators', {})
        rsi = indicators.get('rsi')
        macd = indicators.get('macd')
        
        return MarketContext(
            trend_direction=trend_direction,
            liquidity_score=liquidity_score,
            volatility=volatility,
            rsi=rsi,
            macd=macd,
            volume_ratio=volume_ratio
        )
    
    def _calculate_entry_score(
        self,
        confidence: float,
        win_probability: float,
        reward_ratio: float
    ) -> float:
        """
        計算40/40/20競價評分系統
        
        評分公式：
        entry_score = confidence * 40% + win_probability * 40% + (reward_ratio/3) * 20%
        
        Args:
            confidence: 信心值 (0-1)
            win_probability: 勝率 (0-1)
            reward_ratio: 報酬率 (通常1-3)
        
        Returns:
            float: 競價評分 (0-1)
        """
        # 將reward_ratio歸一化到0-1（假設最大值為3）
        normalized_rr = min(reward_ratio / 3.0, 1.0)
        
        # 40/40/20加權
        entry_score = (
            confidence * 0.40 +
            win_probability * 0.40 +
            normalized_rr * 0.20
        )
        
        return entry_score
    
    def _determine_order_type(
        self,
        symbol: str,
        raw_signal: Dict[str, Any],
        market_context: MarketContext
    ) -> str:
        """
        智能訂單類型選擇（v3.18+）
        
        決策邏輯:
        - 高流動性（>0.6）+ 低波動（<3%） → LIMIT（減少滑點）
        - 突破信號 + 高波動（>3%） → MARKET（確保成交）
        - 默認 → LIMIT（減少成本）
        
        Args:
            symbol: 交易對
            raw_signal: 原始信號
            market_context: 市場上下文
        
        Returns:
            str: "LIMIT" 或 "MARKET"
        """
        # 1. 檢查流動性和波動率
        high_liquidity = market_context.liquidity_score > 0.6
        high_volatility = market_context.volatility > 0.03  # 3%
        
        # 2. 檢查是否為突破信號
        signal_type = raw_signal.get('signal_type', '')
        is_breakout = 'breakout' in signal_type.lower() or 'break' in signal_type.lower()
        
        # 3. 決策
        if is_breakout and high_volatility:
            # 突破 + 高波動 → 市價單確保成交
            logger.debug(f"{symbol}: 選擇MARKET（突破信號 + 高波動{market_context.volatility:.2%}）")
            return "MARKET"
        elif high_liquidity and not high_volatility:
            # 高流動性 + 低波動 → 限價單減少成本
            logger.debug(f"{symbol}: 選擇LIMIT（高流動性{market_context.liquidity_score:.2f} + 低波動）")
            return "LIMIT"
        else:
            # 默認限價單
            logger.debug(f"{symbol}: 選擇LIMIT（默認）")
            return "LIMIT"
