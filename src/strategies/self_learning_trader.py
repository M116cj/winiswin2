"""
SelfLearningTrader v3.17+ - 智能決策核心
職責：槓桿計算、倉位計算、動態 SL/TP、倉位評估、多信號競價
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
import logging
import json
import time
import random

from src.strategies.rule_based_signal_generator import RuleBasedSignalGenerator
from src.core.leverage_engine import LeverageEngine
from src.core.position_sizer import PositionSizer
from src.core.sltp_adjuster import SLTPAdjuster
from src.config import Config
from src.utils.signal_details_logger import get_signal_details_logger

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
    
    def __init__(self, config=None, binance_client=None, trade_recorder=None, virtual_position_manager=None, websocket_monitor=None):
        """
        🔥 v3.18.6+ 初始化 SelfLearningTrader（整合ML模型）
        
        Args:
            config: 配置對象
            binance_client: Binance 客戶端（用於獲取交易規格）
            trade_recorder: 交易記錄器（用於記錄競價結果）
            virtual_position_manager: 虛擬倉位管理器（用於創建虛擬倉位）
            websocket_monitor: WebSocket監控器（v3.17.11，用於獲取即時市場數據）
        """
        self.config = config or Config
        self.binance_client = binance_client
        self.trade_recorder = trade_recorder
        self.virtual_position_manager = virtual_position_manager
        self.websocket_monitor = websocket_monitor  # 🔥 v3.17.11
        
        # 初始化信號生成器
        self.signal_generator = RuleBasedSignalGenerator(config)
        
        # 初始化三大引擎
        self.leverage_engine = LeverageEngine(config)
        self.position_sizer = PositionSizer(config, binance_client)
        self.sltp_adjuster = SLTPAdjuster(config)
        
        # 🔥 v3.18.6+ 初始化ML模型包装器
        try:
            from src.ml.model_wrapper import MLModelWrapper
            self.ml_model = MLModelWrapper()
            self.ml_enabled = self.ml_model.is_loaded
        except Exception as e:
            logger.warning(f"⚠️ ML模型加载失败: {e}")
            self.ml_model = None
            self.ml_enabled = False
        
        # 🔥 v3.18.7+ 模型啟動豁免機制
        self.bootstrap_enabled = self.config.BOOTSTRAP_TRADE_LIMIT > 0
        self._completed_trades_cache = None  # 緩存交易計數（避免重複讀取文件）
        self._bootstrap_ended_logged = False  # 標記豁免期結束日誌是否已輸出
        
        logger.info("=" * 80)
        logger.info(f"✅ SelfLearningTrader v3.18.7+ 初始化完成（豁免期策略）")
        logger.info(f"   🧠 決策引擎: {'ML模型 + 規則混合' if self.ml_enabled else '純規則驅動'}")
        logger.info(f"   🤖 ML狀態: {'✅ 已加載（44個特徵）' if self.ml_enabled else '❌ 未加載（使用規則fallback）'}")
        logger.info("   📡 WebSocket: {}".format("已啟用（即時市場數據）" if websocket_monitor else "未啟用"))
        logger.info("   🛡️  風險控制: 6層防護（質量門檻+方向驗證+RR控制+倉位限制+動態槓桿+智能出場）")
        logger.info("   🏆 多信號競價: 加權評分（信心40% + 勝率40% + R:R 20%）")
        if self.bootstrap_enabled:
            logger.info("")
            logger.info("   🎓 豁免期策略（前100筆交易）:")
            logger.info(f"      ├─ 勝率門檻: {self.config.BOOTSTRAP_MIN_WIN_PROBABILITY:.0%} (正常期: {self.config.MIN_WIN_PROBABILITY:.0%})")
            logger.info(f"      ├─ 信心門檻: {self.config.BOOTSTRAP_MIN_CONFIDENCE:.0%} (正常期: {self.config.MIN_CONFIDENCE:.0%})")
            logger.info(f"      ├─ 質量門檻: {self.config.BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD:.0%} (正常期: {self.config.SIGNAL_QUALITY_THRESHOLD:.0%})")
            logger.info(f"      └─ 槓桿範圍: 1-3x（強制壓制）(正常期: 無上限)")
        logger.info("=" * 80)
    
    def analyze(
        self,
        symbol: str,
        multi_tf_data: Dict[str, pd.DataFrame]
    ) -> Optional[Dict]:
        """
        🔥 v3.18.6+ 分析並生成交易信號（ML預測 + 規則混合）
        
        Args:
            symbol: 交易對
            multi_tf_data: 多時間框架數據
        
        Returns:
            完整的交易信號（可直接執行），或 None
        """
        try:
            # 步驟 1：生成基礎信號（規則引擎）
            base_signal = self.signal_generator.generate_signal(symbol, multi_tf_data)
            
            if base_signal is None:
                return None
            
            # 🔥 v3.19+ 修正3：ML模型統一輸出（支持未來多輸出模型）
            win_probability = base_signal['win_probability']  # 規則引擎的默認值
            confidence = base_signal['confidence']  # 規則引擎的默認值
            ml_score = None  # 綜合分數（僅ML模型提供）
            
            if self.ml_enabled and self.ml_model:
                try:
                    # 使用ML模型預測（支持單輸出或多輸出）
                    ml_prediction = self.ml_model.predict_from_signal(base_signal)
                    
                    if ml_prediction is not None:
                        # 🔥 v3.19+ 修正3：支持多輸出模型
                        # 檢查返回值類型：單值（舊模型）或三元組（新模型）
                        if isinstance(ml_prediction, (tuple, list)) and len(ml_prediction) == 3:
                            # 新型多輸出模型：[綜合分數0-100, 勝率0-1, 信心度0-1]
                            ml_score, ml_win, ml_conf = ml_prediction
                            win_probability = float(ml_win)
                            confidence = float(ml_conf)
                            base_signal['ml_score'] = float(ml_score)
                            base_signal['win_probability'] = win_probability
                            base_signal['confidence'] = confidence
                            base_signal['prediction_source'] = 'ml_model_multi'
                            logger.debug(
                                f"🤖 {symbol} ML多輸出: 綜合={ml_score:.1f} "
                                f"勝率={ml_win:.3f} 信心={ml_conf:.3f}"
                            )
                        else:
                            # 舊型單輸出模型：僅返回勝率
                            win_probability = float(ml_prediction)
                            base_signal['win_probability'] = win_probability
                            base_signal['prediction_source'] = 'ml_model_single'
                            logger.debug(f"🤖 {symbol} ML單輸出勝率: {ml_prediction:.3f}")
                    else:
                        # ML預測失敗，使用規則引擎fallback
                        base_signal['prediction_source'] = 'rule_engine_fallback'
                        logger.debug(f"⚠️ {symbol} ML預測失敗，使用規則引擎: {win_probability:.3f}")
                        
                except Exception as e:
                    # ML預測異常，使用規則引擎fallback
                    base_signal['prediction_source'] = 'rule_engine_fallback'
                    logger.warning(f"⚠️ {symbol} ML預測異常: {e}，使用規則引擎")
            else:
                # ML未啟用，使用規則引擎
                base_signal['prediction_source'] = 'rule_engine'
            
            # 步驟 3：提取決策參數
            confidence = base_signal['confidence']
            rr_ratio = base_signal['rr_ratio']
            
            # 🔥 v3.18.7+ 步驟 3.5：獲取當前門檻（支持啟動豁免）
            thresholds = self._get_current_thresholds()
            
            # 🔥 v3.19+ 修正3：ML綜合分數篩選（優先於雙門檻）
            # 原則：「評分標準 = 生成條件 = 執行依據 = 學習標籤」
            if 'ml_score' in base_signal and base_signal['ml_score'] is not None:
                # ML多輸出模型模式：使用綜合分數篩選
                ml_score_value = base_signal['ml_score']
                ml_threshold = 60.0  # ML綜合分數門檻
                
                if ml_score_value < ml_threshold:
                    logger.debug(
                        f"❌ {symbol} ML綜合分數過低: {ml_score_value:.1f} < {ml_threshold}"
                    )
                    return None
                
                logger.debug(
                    f"✅ {symbol} ML綜合分數通過: {ml_score_value:.1f} >= {ml_threshold}"
                )
            else:
                # 規則模式或ML單輸出模式：使用雙門檻驗證
                is_valid, reject_reason = self.leverage_engine.validate_signal_conditions(
                    win_probability, 
                    confidence, 
                    rr_ratio,
                    min_win_probability=thresholds['min_win_probability'],
                    min_confidence=thresholds['min_confidence']
                )
                
                if not is_valid:
                    logger.debug(f"❌ {symbol} 拒絕開倉: {reject_reason}")
                    return None
            
            # 🔥 v3.18.7+ 步驟 4：獲取豁免期狀態並記錄
            is_bootstrap = thresholds.get('is_bootstrap', False)
            
            if is_bootstrap:
                logger.info(
                    f"🎓 {symbol} 豁免期: 已完成 {thresholds['completed_trades']}/{self.config.BOOTSTRAP_TRADE_LIMIT} 筆 | "
                    f"門檻 勝率≥{thresholds['min_win_probability']:.0%} 信心≥{thresholds['min_confidence']:.0%} | "
                    f"槓桿限制: 1-3x"
                )
            
            # 步驟 5：計算槓桿（豁免期壓制至1-3x，正常期無上限）
            leverage = self.calculate_leverage(
                win_probability,
                confidence,
                is_bootstrap_period=is_bootstrap,
                verbose=True
            )
            
            # 步驟 6：獲取入場價格和基礎 SL/TP
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
            
            # 🔥 v3.19+ 修正2：用調整後 SL/TP 重新計算 RR（統一評分與執行）
            # 原則：「評分標準 = 生成條件 = 執行依據 = 學習標籤」
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            adjusted_rr_ratio = reward / risk if risk > 0 else 1.5
            
            # 記錄基礎與調整後的 RR 比率供對比
            base_rr_ratio = base_signal.get('rr_ratio', 1.5)
            
            # 步驟 8：計算倉位數量（含 10 USDT 下限）
            # 注意：這裡需要賬戶權益，暫時返回信號，由 PositionController 調用
            
            # 構建完整信號
            final_signal = {
                **base_signal,  # 包含所有基礎信號數據
                'leverage': leverage,
                'adjusted_stop_loss': stop_loss,
                'adjusted_take_profit': take_profit,
                'rr_ratio': adjusted_rr_ratio,  # 🔥 v3.19+ 修正2：使用調整後RR
                'base_rr_ratio': base_rr_ratio,  # 保留基礎RR供對比
                'leverage_info': {
                    'win_probability': win_probability,
                    'confidence': confidence,
                    'calculated_leverage': leverage
                }
            }
            
            # 🔥 記錄到專屬日誌文件（不在Railway主日誌中顯示）
            signal_logger = get_signal_details_logger()
            signal_logger.log_complete_signal(
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                leverage=leverage,
                sl_price=stop_loss,
                tp_price=take_profit,
                win_rate=win_probability,
                confidence=confidence
            )
            
            return final_signal
            
        except Exception as e:
            logger.error(f"❌ {symbol} 分析失敗: {e}", exc_info=True)
            return None
    
    def calculate_leverage(
        self,
        win_probability: float,
        confidence: float,
        is_bootstrap_period: bool = False,
        verbose: bool = False
    ) -> float:
        """
        計算槓桿（v3.18.7+ 豁免期壓制）
        
        豁免期（0-100筆）：1-3x（強制壓制）
        正常期（101+筆）：無上限（模型自行判定）
        
        公式：
        1. win_factor = (win_prob - 0.55) / 0.15
           - win_prob = 0.55 → win_factor = 0 → 1x
           - win_prob = 0.70 → win_factor = 1 → 12x
        
        2. win_leverage = 1 + win_factor × 11
        
        3. conf_factor = confidence / 0.5
           - confidence = 0.50 → conf_factor = 1.0
           - confidence = 1.00 → conf_factor = 2.0
        
        4. leverage = base × win_leverage × conf_factor
        
        豁免期壓制：
        - 前100筆：強制限制 1-3x（基於信心度線性映射）
        - 101+筆：無上限（模型自行判定）
        
        Args:
            win_probability: 勝率（0-1）
            confidence: 信心度（0-1）
            is_bootstrap_period: 是否在豁免期（前100筆交易）
            verbose: 是否輸出詳細日誌
        
        Returns:
            槓桿倍數
            - 豁免期：1-3x（強制壓制）
            - 正常期：0.5x ~ ∞（模型自行判定）
        """
        # 🔥 v3.18.7+ 委托给 LeverageEngine 处理（包含豁免期逻辑）
        return self.leverage_engine.calculate_leverage(
            win_probability, confidence, is_bootstrap_period, verbose
        )
    
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
            # 🔥 記錄到專屬日誌文件（不在Railway主日誌中顯示）
            signal_logger = get_signal_details_logger()
            signal_logger.log_sltp_adjustment(
                symbol="UNKNOWN",  # 在analyze方法中會有完整信號記錄，這裡僅記錄調整細節
                leverage=leverage,
                scale=scale,
                base_sl_pct=base_sl_pct,
                adjusted_sl_pct=adjusted_sl_pct,
                sl_price=stop_loss,
                tp_price=take_profit
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
    
    async def execute_best_trade(self, signals: List[Dict]) -> Optional[Dict]:
        """
        從多個信號中選擇最優者執行（加權評分 + 完整記錄）
        
        Args:
            signals: 交易信號列表
            
        Returns:
            成功執行的倉位信息，或 None
        """
        if not signals:
            return None
        
        # 確保 Binance 客戶端已初始化
        if not self.binance_client:
            logger.error("❌ Binance 客戶端未初始化，無法執行交易")
            return None
        
        # === 1. 獲取帳戶狀態 ===
        account_balance = await self.binance_client.get_account_balance()
        available_balance = account_balance['available_balance']
        total_equity = account_balance['total_wallet_balance']
        
        # === 2. 過濾有效信號 + 計算加權評分 ===
        scored_signals = []
        for signal in signals:
            # 品質過濾（基本門檻）
            if not self._validate_signal_quality(signal):
                continue
            
            # 計算理論倉位
            theoretical_size = await self.calculate_position_size(
                account_equity=available_balance,
                entry_price=signal['entry_price'],
                stop_loss=signal['adjusted_stop_loss'],
                leverage=signal['leverage'],
                symbol=signal['symbol'],
                verbose=False
            )
            notional_value = theoretical_size * signal['entry_price']
            
            # 單倉上限：≤ 50% 總權益
            if notional_value > total_equity * 0.5:
                logger.debug(f"❌ {signal['symbol']} 倉位過大 ({notional_value:.2f} > {total_equity * 0.5:.2f})，跳過")
                continue
            
            # 🔢 計算加權評分（標準化至 0~1）
            norm_confidence = min(signal['confidence'] / 1.0, 1.0)                    # 信心值 (0~1)
            norm_win_rate = min(signal['win_probability'] / 1.0, 1.0)                # 勝率 (0~1)
            norm_rr = min(signal.get('rr_ratio', 1.5) / 3.0, 1.0)                    # R:R (0~3 → 0~1)
            
            weighted_score = (
                norm_confidence * 0.4 +   # 信心值 40%
                norm_win_rate * 0.4 +     # 勝率 40%
                norm_rr * 0.2             # 報酬率 20%
            )
            
            scored_signals.append({
                'signal': signal,
                'size': theoretical_size,
                'notional': notional_value,
                'score': weighted_score,
                'details': {
                    'confidence': signal['confidence'],
                    'win_rate': signal['win_probability'],
                    'rr_ratio': signal.get('rr_ratio', 1.5),
                    'norm_confidence': norm_confidence,
                    'norm_win_rate': norm_win_rate,
                    'norm_rr': norm_rr,
                    'weighted_score': weighted_score
                }
            })
        
        if not scored_signals:
            logger.info("❌ 無有效信號可執行")
            return None
        
        # === 3. 選擇最高分信號 ===
        best = max(scored_signals, key=lambda x: x['score'])
        
        # === 4. 記錄競價過程（供審計與訓練）===
        await self._log_competition_results(scored_signals, best)
        
        # === 5. 倉位補足至最小值 ===
        min_notional = getattr(self.config, 'MIN_NOTIONAL_VALUE', 10.0)
        if best['notional'] < min_notional:
            logger.info(
                f"🔧 {best['signal']['symbol']} 倉位補足至最小值 "
                f"({best['notional']:.2f} → {min_notional})"
            )
            best['size'] = min_notional / best['signal']['entry_price']
            best['notional'] = min_notional
        
        # === 6. 探索-利用平衡（v3.17.10+）===
        # 解決「局部最優」問題：5% 時間執行非最優信號
        # 持續收集「模型不喜歡但可能正確」的樣本
        if random.random() < 0.05 and len(scored_signals) > 1:
            # 從 Rank 2-N 中隨機選一個
            exploration_candidates = [s for s in scored_signals if s != best]
            if exploration_candidates:
                explore = random.choice(exploration_candidates)
                
                # 計算競價上下文（用於記錄）
                sorted_signals = sorted(scored_signals, key=lambda x: x['score'], reverse=True)
                explore_rank = sorted_signals.index(explore) + 1
                score_gap = best['score'] - explore['score']
                
                logger.info(
                    f"🔍 探索模式: 執行 {explore['signal']['symbol']}（非最優） | "
                    f"評分={explore['score']:.3f} vs 最優={best['score']:.3f}"
                )
                
                # 補足倉位至最小值
                if explore['notional'] < min_notional:
                    explore['size'] = min_notional / explore['signal']['entry_price']
                    explore['notional'] = min_notional
                
                # 🔥 v3.18+ Critical Fix: 確保signal包含original_signal用於智能出場
                if 'original_signal' not in explore['signal']:
                    import copy
                    explore['signal']['original_signal'] = copy.deepcopy(explore['signal'])
                    logger.debug(f"📋 {explore['signal']['symbol']} 已添加original_signal（探索模式）")
                
                # 執行探索性交易
                position = await self._place_order_and_monitor(
                    explore['signal'], 
                    explore['size'], 
                    available_balance,
                    competition_context={
                        'rank': explore_rank,
                        'score_gap': score_gap,
                        'num_signals': len(scored_signals)
                    }
                )
                
                # 創建虛擬倉位（包含 best 信號）
                await self._create_virtual_positions(scored_signals, explore['signal'], total_equity)
                
                return position
        
        # === 7. 執行最優信號（95% 情況）===
        # 🔥 v3.18+ Critical Fix: 確保signal包含original_signal用於智能出場
        if 'original_signal' not in best['signal']:
            import copy
            best['signal']['original_signal'] = copy.deepcopy(best['signal'])
            logger.debug(f"📋 {best['signal']['symbol']} 已添加original_signal（最優信號）")
        
        position = await self._place_order_and_monitor(
            best['signal'], 
            best['size'], 
            available_balance,
            competition_context={
                'rank': 1,  # 最優信號始終是 rank 1
                'score_gap': 0.0,  # 與自己的差距為0
                'num_signals': len(scored_signals)
            }
        )
        
        # === 8. 創建虛擬倉位（未執行信號）===
        await self._create_virtual_positions(scored_signals, best['signal'], total_equity)
        
        return position

    def _validate_signal_quality(self, signal: Dict) -> bool:
        """
        驗證信號品質（基本門檻）
        
        Args:
            signal: 交易信號
            
        Returns:
            是否通過品質檢查
        """
        try:
            # 檢查必要欄位
            required_fields = ['symbol', 'direction', 'entry_price', 'confidence', 
                             'win_probability', 'leverage', 'adjusted_stop_loss', 
                             'adjusted_take_profit']
            
            for field in required_fields:
                if field not in signal:
                    logger.debug(f"❌ {signal.get('symbol', 'UNKNOWN')} 缺少欄位: {field}")
                    return False
            
            # 基本數值檢查
            if signal['confidence'] < 0 or signal['confidence'] > 1:
                logger.debug(f"❌ {signal['symbol']} 信心度異常: {signal['confidence']}")
                return False
                
            if signal['win_probability'] < 0 or signal['win_probability'] > 1:
                logger.debug(f"❌ {signal['symbol']} 勝率異常: {signal['win_probability']}")
                return False
                
            if signal['leverage'] <= 0:
                logger.debug(f"❌ {signal['symbol']} 槓桿異常: {signal['leverage']}")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ 信號品質驗證失敗: {e}")
            return False

    async def _log_competition_results(self, all_signals: List[dict], best: dict):
        """
        記錄多信號競價結果（JSON 格式，供分析）
        
        Args:
            all_signals: 所有參與競價的信號
            best: 獲勝的信號
        """
        competition_log = {
            'timestamp': time.time(),
            'total_signals': len(all_signals),
            'best_signal': {
                'symbol': best['signal']['symbol'],
                'score': best['score'],
                'details': best['details']
            },
            'all_signals': [
                {
                    'symbol': s['signal']['symbol'],
                    'score': s['score'],
                    'confidence': s['details']['confidence'],
                    'win_rate': s['details']['win_rate'],
                    'rr_ratio': s['details']['rr_ratio']
                }
                for s in all_signals
            ]
        }
        
        # 輸出到 stdout（Railway Logs 可捕獲）
        print(f"[SIGNAL_COMPETITION] {json.dumps(competition_log)}")
        
        # 保存到訓練數據（用於模型改進）
        if self.trade_recorder:
            await self.trade_recorder.save_competition_log(competition_log)
        
        logger.info(
            f"🏆 信號競價選中: {best['signal']['symbol']} {best['signal']['direction']} | "
            f"綜合評分: {best['score']:.3f} | "
            f"信心: {best['details']['confidence']:.1%} (40%) | "
            f"勝率: {best['details']['win_rate']:.1%} (40%) | "
            f"R:R: {best['details']['rr_ratio']:.2f} (20%) | "
            f"槓桿: {best['signal']['leverage']:.1f}x"
        )

    async def _place_order_and_monitor(
        self, 
        signal: Dict, 
        size: float, 
        available_balance: float,
        competition_context: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        執行下單並監控倉位
        
        Args:
            signal: 交易信號
            size: 倉位數量
            available_balance: 可用保證金
            competition_context: 競價上下文（v3.17.10+）
            
        Returns:
            倉位信息或 None
        """
        try:
            # 確保 Binance 客戶端已初始化
            if not self.binance_client:
                logger.error("❌ Binance 客戶端未初始化")
                return None
            
            # 設置槓桿
            safe_leverage = min(int(signal['leverage']), 125)
            try:
                await self.binance_client.set_leverage(signal['symbol'], safe_leverage)
            except Exception as e:
                logger.warning(f"⚠️ 設置槓桿失敗 ({signal['symbol']} {safe_leverage}x): {e}")
            
            # 下單
            side = 'BUY' if signal['direction'] == 'LONG' else 'SELL'
            order_result = await self.binance_client.place_order(
                symbol=signal['symbol'],
                side=side,
                order_type='MARKET',
                quantity=size
            )
            
            # 計算倉位價值
            position_value = size * signal['entry_price']
            
            # 構建倉位信息
            position = {
                'symbol': signal['symbol'],
                'direction': signal['direction'],
                'entry_price': signal['entry_price'],
                'size': size,
                'leverage': signal['leverage'],
                'stop_loss': signal['adjusted_stop_loss'],
                'take_profit': signal['adjusted_take_profit'],
                'confidence': signal['confidence'],
                'win_probability': signal['win_probability'],
                'order_id': order_result.get('orderId'),
                'timestamp': time.time(),
                'position_value': position_value
            }
            
            # 記錄開倉信號（用於後續配對和 ML 訓練）
            if self.trade_recorder:
                try:
                    # 🔥 v3.17.2+：從WebSocketManager獲取元數據
                    websocket_metadata = None
                    if self.websocket_monitor:
                        kline = self.websocket_monitor.get_kline(signal['symbol'])
                        if kline:
                            websocket_metadata = {
                                'latency_ms': kline.get('latency_ms', 0),
                                'server_timestamp': kline.get('server_timestamp', 0),
                                'local_timestamp': kline.get('local_timestamp', 0),
                                'shard_id': kline.get('shard_id', 0)
                            }
                    
                    self.trade_recorder.record_entry(
                        signal=signal,
                        position_info={
                            'leverage': signal['leverage'],
                            'position_value': position_value,
                            'size': size
                        },
                        competition_context=competition_context,  # 🔥 v3.17.10+：競價上下文特徵
                        websocket_metadata=websocket_metadata  # 🔥 v3.17.2+：WebSocket元數據
                    )
                    logger.debug(f"📝 記錄開倉信號: {signal['symbol']}")
                except Exception as e:
                    logger.warning(f"⚠️ 記錄開倉信號失敗: {e}")
            
            logger.info(
                f"✅ 下單成功: {signal['symbol']} {signal['direction']} | "
                f"數量={size:.6f} | 槓桿={signal['leverage']:.1f}x | "
                f"價值=${position_value:.2f} | "
                f"信心值={signal.get('confidence', 0):.1%} 勝率={signal.get('win_probability', 0):.1%}"
            )
            
            return position
            
        except Exception as e:
            logger.error(f"❌ 下單失敗 {signal['symbol']}: {e}", exc_info=True)
            return None

    async def _create_virtual_positions(
        self, 
        scored_signals: List[dict], 
        executed_signal: Dict,
        total_equity: float
    ):
        """
        創建虛擬倉位（未執行的信號）
        
        Args:
            scored_signals: 所有評分後的信號
            executed_signal: 已執行的信號
            total_equity: 總權益
        """
        if not self.virtual_position_manager:
            logger.debug("⚠️ 未配置虛擬倉位管理器，跳過虛擬倉位創建")
            return
        
        try:
            executed_symbol = executed_signal['symbol']
            rank = 2  # 從第2名開始（第1名已執行）
            
            # 按評分排序
            sorted_signals = sorted(scored_signals, key=lambda x: x['score'], reverse=True)
            
            for item in sorted_signals:
                signal = item['signal']
                
                # 跳過已執行的信號
                if signal['symbol'] == executed_symbol:
                    continue
                
                # 創建虛擬倉位
                try:
                    self.virtual_position_manager.add_position(
                        signal=signal,
                        rank=rank,
                        expiry=96  # 96小時過期
                    )
                    logger.debug(f"📝 創建虛擬倉位: {signal['symbol']} (排名={rank}, 評分={item['score']:.3f})")
                    rank += 1
                    
                except Exception as e:
                    logger.warning(f"⚠️ 創建虛擬倉位失敗 {signal['symbol']}: {e}")
            
            logger.info(f"✅ 創建 {rank - 2} 個虛擬倉位")
            
        except Exception as e:
            logger.error(f"❌ 虛擬倉位批次創建失敗: {e}", exc_info=True)
    
    async def _get_market_context(self, symbol: str) -> Dict:
        """
        獲取即時市場上下文（WebSocket優先，REST備援）
        
        Args:
            symbol: 交易對
        
        Returns:
            市場上下文字典
        """
        context = {
            'current_price': None,
            'liquidity_score': 0.0,
            'spread_bps': None,
            'trend_direction': 'neutral',
            'data_source': 'unknown'
        }
        
        # 🔥 v3.17.2+：優先使用WebSocket K線數據
        if self.websocket_monitor:
            kline = self.websocket_monitor.get_kline(symbol)
            if kline:
                # 從K線提取市場上下文
                context['current_price'] = kline.get('close')
                context['data_source'] = 'websocket_kline'
                context['liquidity_score'] = self.websocket_monitor.get_liquidity_score(symbol)
                context['spread_bps'] = self.websocket_monitor.get_spread_bps(symbol)
                
                # 🔥 v3.17.2+：趨勢方向判斷（基於K線OHLC）
                open_price = kline.get('open', 0)
                close_price = kline.get('close', 0)
                if close_price > open_price:
                    context['trend_direction'] = 'bullish'
                elif close_price < open_price:
                    context['trend_direction'] = 'bearish'
                else:
                    context['trend_direction'] = 'neutral'
                
                logger.debug(
                    f"💡 {symbol} 市場上下文（K線）: "
                    f"價格=${close_price:.2f}, "
                    f"趨勢={context['trend_direction']}, "
                    f"流動性={context['liquidity_score']:.2f}"
                )
                return context
            
            # 備援：使用價格數據（向後兼容WebSocketMonitor）
            price = self.websocket_monitor.get_price(symbol)
            if price is not None:
                context['current_price'] = price
                context['data_source'] = 'websocket_price'
                context['liquidity_score'] = self.websocket_monitor.get_liquidity_score(symbol)
                context['spread_bps'] = self.websocket_monitor.get_spread_bps(symbol)
                logger.debug(f"💡 {symbol} 市場上下文（WebSocket價格）: 價格=${price:.2f}")
                return context
        
        # 🔥 v3.17.2+：REST API備援
        if self.binance_client:
            try:
                ticker = await self.binance_client.get_ticker(symbol)
                context['current_price'] = float(ticker.get('lastPrice', 0))
                context['data_source'] = 'rest_api'
                logger.debug(f"📡 {symbol} 市場上下文（REST API）: 價格=${context['current_price']}")
            except Exception as e:
                logger.warning(f"⚠️ {symbol} REST API備援失敗: {e}")
        
        return context
    
    async def execute_best_trades(
        self,
        signals: List[Dict],
        max_positions: Optional[int] = None
    ) -> List[Dict]:
        """
        執行多信號資金分配（v3.18+ 動態預算池版本）
        
        流程：
        1. 獲取帳戶狀態（可用保證金、總權益）
        2. 使用CapitalAllocator進行資金分配
        3. 對每個已分配信號計算倉位並下單
        4. 創建虛擬倉位（未分配到資金的信號）
        
        Args:
            signals: 交易信號列表（dict格式）
            max_positions: 最大同時開倉數（可選，默認使用Config.MAX_CONCURRENT_ORDERS）
        
        Returns:
            成功執行的倉位列表
        """
        from src.core.capital_allocator import CapitalAllocator
        
        if not signals:
            logger.debug("💰 無信號需要執行")
            return []
        
        # 確保Binance客戶端已初始化
        if not self.binance_client:
            logger.error("❌ Binance客戶端未初始化，無法執行交易")
            return []
        
        # ===== 步驟1：獲取帳戶狀態 =====
        try:
            account_balance = await self.binance_client.get_account_balance()
            available_margin = account_balance['available_balance']
            total_equity = account_balance['total_wallet_balance']
            total_balance = account_balance['total_balance']  # 帳戶總金額（不含浮盈浮虧）
            total_margin = account_balance['total_margin']    # 已佔用保證金
            
            logger.info(
                f"💰 帳戶狀態 | 總權益: ${total_equity:.2f} | "
                f"可用保證金: ${available_margin:.2f} | "
                f"已佔用保證金: ${total_margin:.2f}"
            )
        except Exception as e:
            logger.error(f"❌ 獲取帳戶信息失敗: {e}")
            return []
        
        # ===== 步驟2：動態分配資金（v3.18.7+ 含豁免期質量門檻）=====
        # 🔥 v3.18.7+ 獲取已完成交易數（用於豁免期判斷）
        # 防御性檢查：如果trade_recorder未初始化，默認total_trades=0
        if self.trade_recorder:
            total_trades = await self.trade_recorder.get_trade_count()
        else:
            total_trades = 0
            logger.warning("⚠️ TradeRecorder未初始化，使用total_trades=0（豁免期模式）")
        
        # 確保使用Config實例（self.config可能是類或實例）
        config_instance = self.config if not isinstance(self.config, type) else self.config()
        allocator = CapitalAllocator(
            config_instance,
            total_equity,
            total_balance=total_balance,
            total_margin=total_margin,
            total_trades=total_trades  # 🔥 v3.18.7+ 豁免期邏輯
        )
        allocated_signals = allocator.allocate_capital(signals, available_margin)
        
        if not allocated_signals:
            logger.info("💰 無信號獲得資金分配")
            # 創建虛擬倉位（所有信號都未執行）
            await self._create_virtual_positions_from_dict(signals, None, total_equity)
            return []
        
        # ===== 步驟3：應用最大開倉數限制 =====
        max_concurrent = max_positions or self.config.MAX_CONCURRENT_ORDERS
        if len(allocated_signals) > max_concurrent:
            logger.warning(
                f"💰 獲批信號 ({len(allocated_signals)}) 超過最大開倉數 ({max_concurrent})，"
                f"僅執行前 {max_concurrent} 個"
            )
            allocated_signals = allocated_signals[:max_concurrent]
        
        # ===== 步驟4：執行已分配信號 =====
        executed_positions = []
        
        for idx, alloc in enumerate(allocated_signals, 1):
            signal = alloc.signal
            symbol = signal.get('symbol', 'UNKNOWN')
            
            try:
                # 計算倉位大小（基於分配的保證金）
                position_size = self._calculate_position_size_from_budget(
                    allocated_budget=alloc.allocated_budget,
                    entry_price=signal['entry_price'],
                    stop_loss=signal.get('adjusted_stop_loss', signal.get('stop_loss')),
                    leverage=signal['leverage']
                )
                
                # 驗證倉位大小
                notional_value = position_size * signal['entry_price']
                min_notional = getattr(self.config, 'MIN_NOTIONAL_VALUE', 10.0)
                
                if notional_value < min_notional:
                    logger.warning(
                        f"💰 {symbol} 倉位過小 ({notional_value:.2f} < {min_notional})，"
                        f"調整至最小值"
                    )
                    position_size = min_notional / signal['entry_price']
                    notional_value = min_notional
                
                logger.info(
                    f"💰 執行 #{idx}/{len(allocated_signals)} | {symbol} | "
                    f"分配: ${alloc.allocated_budget:.2f} | "
                    f"槓桿: {signal['leverage']:.1f}x | "
                    f"倉位: {position_size:.6f} | "
                    f"名義價值: ${notional_value:.2f} | "
                    f"質量分數: {alloc.quality_score:.3f}"
                )
                
                # 🔥 v3.18+ Critical Fix: 確保signal包含original_signal用於智能出場
                # 問題：PositionMonitor需要original_signal來執行進場失效、逆勢平倉等高級出場邏輯
                # 解決：如果signal缺少original_signal，使用deep copy創建完整備份
                if 'original_signal' not in signal:
                    import copy
                    signal['original_signal'] = copy.deepcopy(signal)
                    logger.debug(f"📋 {symbol} 已添加original_signal（用於智能出場）")
                
                # 執行下單
                position = await self._place_order_and_monitor(
                    signal=signal,
                    size=position_size,
                    available_balance=available_margin,
                    competition_context={
                        'rank': idx,
                        'quality_score': alloc.quality_score,
                        'allocated_budget': alloc.allocated_budget,
                        'allocation_ratio': alloc.allocation_ratio,
                        'num_signals': len(allocated_signals)
                    }
                )
                
                if position:
                    executed_positions.append(position)
                    logger.info(
                        f"✅ {symbol} 開倉成功 | "
                        f"倉位ID: {position.get('id', 'UNKNOWN')}"
                    )
                else:
                    logger.warning(f"❌ {symbol} 開倉失敗")
                
            except Exception as e:
                logger.error(f"❌ {symbol} 執行失敗: {e}", exc_info=True)
                continue
        
        # ===== 步驟5：創建虛擬倉位（未獲分配的信號）=====
        executed_symbols = {p.get('symbol') for p in executed_positions if p}
        unexecuted_signals = [
            s for s in signals 
            if s.get('symbol') not in executed_symbols
        ]
        
        if unexecuted_signals:
            await self._create_virtual_positions_from_dict(
                unexecuted_signals,
                None,  # 無執行信號
                total_equity
            )
        
        # ===== 最終報告 =====
        logger.info("=" * 80)
        logger.info(f"✅ 多信號執行完成")
        logger.info(f"   成功開倉: {len(executed_positions)}/{len(allocated_signals)}")
        logger.info(f"   虛擬倉位: {len(unexecuted_signals)}")
        logger.info("=" * 80)
        
        return executed_positions
    
    def _calculate_position_size_from_budget(
        self,
        allocated_budget: float,
        entry_price: float,
        stop_loss: float,
        leverage: float
    ) -> float:
        """
        基於分配的保證金計算倉位大小（v3.18+）
        
        公式：
        1. 名義價值 = 分配保證金 × 槓桿
        2. 倉位大小 = 名義價值 / 入場價格
        
        Args:
            allocated_budget: 分配的保證金（USDT）
            entry_price: 入場價格
            stop_loss: 止損價格（用於驗證）
            leverage: 槓桿倍數
        
        Returns:
            倉位數量
        """
        # 計算名義價值
        notional_value = allocated_budget * leverage
        
        # 計算倉位大小
        position_size = notional_value / entry_price
        
        # 止損距離驗證（防禦性檢查）
        sl_distance_pct = abs(entry_price - stop_loss) / entry_price
        if sl_distance_pct < 0.003:  # 止損距離 < 0.3%
            logger.warning(
                f"   ⚠️ 止損距離過小 ({sl_distance_pct:.3%})，"
                f"可能導致過早觸發"
            )
        
        logger.debug(
            f"   💰 倉位計算: 保證金=${allocated_budget:.2f} × 槓桿={leverage:.1f}x "
            f"= 名義價值=${notional_value:.2f} → 數量={position_size:.6f}"
        )
        
        return position_size
    
    async def _create_virtual_positions_from_dict(
        self,
        signals: List[Dict],
        executed_signal: Optional[Dict],
        total_equity: float
    ) -> None:
        """
        從dict格式信號創建虛擬倉位（兼容性包裝）
        
        Args:
            signals: 信號列表（dict格式）
            executed_signal: 已執行的信號（dict格式，可選）
            total_equity: 總權益
        """
        # 過濾掉已執行的信號
        if executed_signal:
            executed_symbol = executed_signal.get('symbol')
            unexecuted_signals = [
                s for s in signals 
                if s.get('symbol') != executed_symbol
            ]
        else:
            unexecuted_signals = signals
        
        # 創建虛擬倉位
        if unexecuted_signals and self.virtual_position_manager:
            for signal in unexecuted_signals:
                try:
                    await self.virtual_position_manager.create_virtual_position(
                        signal=signal,
                        account_equity=total_equity
                    )
                except Exception as e:
                    logger.error(
                        f"❌ 創建虛擬倉位失敗 {signal.get('symbol', 'UNKNOWN')}: {e}"
                    )
    
    def _count_completed_trades(self, use_cache: bool = True) -> int:
        """
        統計已完成的交易數（v3.18.7+ 從持久化文件讀取，支持緩存）
        
        Args:
            use_cache: 是否使用緩存（默認True，避免重複讀取文件）
        
        Returns:
            已完成交易的總數量（從trades.jsonl計算）
        """
        # 🔥 使用緩存避免重複讀取文件（性能優化）
        if use_cache and self._completed_trades_cache is not None:
            return self._completed_trades_cache
        
        # 🔥 Critical Fix: 從 trades.jsonl 文件讀取總交易數
        # 因為 completed_trades 列表會在每次 flush 時被清空（ML_FLUSH_COUNT=1）
        from pathlib import Path
        
        trades_file = Path("data/trades.jsonl")
        
        if not trades_file.exists():
            self._completed_trades_cache = 0
            return 0
        
        try:
            count = 0
            with open(trades_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        count += 1
            
            # 更新緩存
            self._completed_trades_cache = count
            return count
            
        except Exception as e:
            logger.warning(f"⚠️ 讀取trades.jsonl失敗: {e}")
            # 容錯：如果有trade_recorder，使用內存計數
            if self.trade_recorder:
                fallback_count = len(self.trade_recorder.completed_trades)
                self._completed_trades_cache = fallback_count
                return fallback_count
            else:
                self._completed_trades_cache = 0
                return 0
    
    def invalidate_trades_cache(self):
        """
        使交易計數緩存失效（在交易完成後調用）
        
        這個方法應該在trade_recorder.record_exit()後調用
        """
        self._completed_trades_cache = None
    
    def _get_current_thresholds(self) -> Dict:
        """
        獲取當前應使用的門檻值（v3.18.7+ 啟動豁免機制）
        
        Returns:
            包含當前門檻的字典 {
                'min_win_probability': float,
                'min_confidence': float,
                'is_bootstrap': bool,
                'completed_trades': int,
                'remaining': int (僅豁免期)
            }
        """
        if not self.bootstrap_enabled or not self.trade_recorder:
            # 豁免未啟用或無記錄器，使用正常門檻
            return {
                'min_win_probability': self.config.MIN_WIN_PROBABILITY,
                'min_confidence': self.config.MIN_CONFIDENCE,
                'is_bootstrap': False,
                'completed_trades': 0
            }
        
        # 🔥 強制重新讀取交易數（use_cache=False）確保計數最新
        # 這個方法只在有新信號時才調用，不會造成性能問題
        completed_trades = self._count_completed_trades(use_cache=False)
        
        # 前N筆交易使用豁免門檻
        if completed_trades < self.config.BOOTSTRAP_TRADE_LIMIT:
            return {
                'min_win_probability': self.config.BOOTSTRAP_MIN_WIN_PROBABILITY,
                'min_confidence': self.config.BOOTSTRAP_MIN_CONFIDENCE,
                'is_bootstrap': True,
                'completed_trades': completed_trades,
                'remaining': self.config.BOOTSTRAP_TRADE_LIMIT - completed_trades
            }
        else:
            # 已完成豁免期，使用正常門檻
            # 🔥 在豁免期結束時記錄一次（避免重複輸出）
            if not self._bootstrap_ended_logged:
                self._bootstrap_ended_logged = True
                logger.info("=" * 80)
                logger.info(f"🎓 啟動豁免期已結束！已完成 {completed_trades} 筆交易")
                logger.info(f"   切換至正常門檻: 勝率≥{self.config.MIN_WIN_PROBABILITY:.0%} 信心≥{self.config.MIN_CONFIDENCE:.0%}")
                logger.info("=" * 80)
            
            return {
                'min_win_probability': self.config.MIN_WIN_PROBABILITY,
                'min_confidence': self.config.MIN_CONFIDENCE,
                'is_bootstrap': False,
                'completed_trades': completed_trades
            }
