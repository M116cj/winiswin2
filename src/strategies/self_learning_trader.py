"""
SelfLearningTrader v3.17+ - 智能決策核心
職責：槓桿計算、倉位計算、動態 SL/TP、倉位評估、多信號競價
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime
from src.utils.logger_factory import get_logger
import json
import time
import random

from src.strategies.rule_based_signal_generator import RuleBasedSignalGenerator
from src.core.leverage_engine import LeverageEngine
from src.core.position_sizer import PositionSizer
from src.core.sltp_adjuster import SLTPAdjuster
from src.config import Config
from src.utils.signal_details_logger import get_signal_details_logger

logger = get_logger(__name__)


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
        🔥 v4.0+ 初始化 SelfLearningTrader（整合ML模型 + UnifiedTradeRecorder）
        
        Args:
            config: 配置對象
            binance_client: Binance 客戶端（用於獲取交易規格）
            trade_recorder: UnifiedTradeRecorder實例（由main.py傳入，PostgreSQL數據源）
            virtual_position_manager: 虛擬倉位管理器（用於創建虛擬倉位）
            websocket_monitor: WebSocket監控器（v3.17.11，用於獲取即時市場數據）
        """
        self.config = config or Config
        self.binance_client = binance_client
        self.virtual_position_manager = virtual_position_manager
        self.websocket_monitor = websocket_monitor  # 🔥 v3.17.11
        
        # 🔥 v4.0+ UnifiedTradeRecorder（PostgreSQL唯一數據源）
        self.trade_recorder = trade_recorder
        if self.trade_recorder:
            logger.debug("使用UnifiedTradeRecorder（PostgreSQL）")
        else:
            logger.warning("⚠️ TradeRecorder未提供，部分功能將受限")
        
        # 初始化信號生成器（🔥 v3.19+：強制啟用純ICT/SMC模式）
        self.signal_generator = RuleBasedSignalGenerator(config, use_pure_ict=True)
        
        # 添加对signal_generator的pipeline统计访问
        self._pipeline_stats = self.signal_generator._pipeline_stats
        
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
        
        # 🚀 v4.6.0: 批量ML推理支持（Phase 1A3）
        self.batch_ml_enabled = (
            self.ml_enabled and 
            hasattr(self.config, 'BATCH_ML_INFERENCE_ENABLED') and 
            self.config.BATCH_ML_INFERENCE_ENABLED
        )
        
        # 🔥 v3.18.7+ 模型啟動豁免機制（v4.6.0: PostgreSQL緩存版）
        self.bootstrap_enabled = self.config.BOOTSTRAP_TRADE_LIMIT > 0
        self._completed_trades_cache = 0  # 緩存交易計數（從PostgreSQL更新）
        self._bootstrap_ended_logged = False  # 標記豁免期結束日誌是否已輸出
        self._cache_last_updated = 0.0  # 緩存上次更新時間
        
        logger.debug("SelfLearningTrader 初始化完成")
        logger.debug(f"   ML狀態: {'已加載' if self.ml_enabled else '未加載'}")
        logger.debug(f"   WebSocket: {'已啟用' if websocket_monitor else '未啟用'}")
    
    def analyze(
        self,
        symbol: str,
        multi_tf_data: Dict[str, pd.DataFrame]
    ) -> tuple[Optional[Dict], float, float]:
        """
        🔥 v3.19+ 分析並生成交易信號（ML預測 + 規則混合）+ 診斷信息
        
        Args:
            symbol: 交易對
            multi_tf_data: 多時間框架數據
        
        Returns:
            三元組 (signal, confidence, win_probability):
            - signal: 完整的交易信號（可直接執行），或 None
            - confidence: 信心值（0-100）
            - win_probability: 勝率（0-100）
        """
        try:
            # 步驟 1：生成基礎信號（規則引擎）- 返回三元組
            base_signal, base_confidence, base_win_prob = self.signal_generator.generate_signal(symbol, multi_tf_data)
            
            if base_signal is None:
                return None, base_confidence, base_win_prob
            
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
                    return None, confidence * 100, win_probability * 100
                
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
                    logger.info(f"❌ {symbol} 拒絕開倉: {reject_reason} | 勝率={win_probability:.1%} 信心={confidence:.1%} R:R={rr_ratio:.2f}")
                    return None, confidence * 100, win_probability * 100
            
            # 🔥 v4.1+ 步驟 4：獲取豁免期狀態和階段性槓桿上限
            is_bootstrap = thresholds.get('is_bootstrap', False)
            max_leverage = thresholds.get('max_leverage', None)  # v4.1+
            phase = thresholds.get('phase', 'normal')  # v4.1+
            
            if is_bootstrap:
                logger.info(
                    f"🎓 {symbol} 豁免期({phase}): 已完成 {thresholds['completed_trades']}/{self.config.BOOTSTRAP_TRADE_LIMIT} 筆 | "
                    f"門檻 勝率≥{thresholds['min_win_probability']:.0%} 信心≥{thresholds['min_confidence']:.0%} | "
                    f"槓桿限制: 1-{max_leverage:.0f}x"
                )
            
            # 步驟 5：計算槓桿（v4.1+：漸進式豁免期，正常期無上限）
            leverage = self.calculate_leverage(
                win_probability,
                confidence,
                is_bootstrap_period=is_bootstrap,
                max_leverage=max_leverage,
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
            
            # 🔥 v3.19+：返回增強信號 + 診斷信息（confidence/win_probability）
            return final_signal, confidence * 100, win_probability * 100
            
        except Exception as e:
            logger.error(f"❌ {symbol} 分析失敗: {e}", exc_info=True)
            return None, 0.0, 0.0
    
    def calculate_leverage(
        self,
        win_probability: float,
        confidence: float,
        is_bootstrap_period: bool = False,
        max_leverage: Optional[float] = None,
        verbose: bool = False
    ) -> float:
        """
        計算槓桿（v4.1+ 漸進式豁免期）
        
        漸進式策略：
        - 階段1 (1-15筆)：槓桿≤2x
        - 階段2 (16-35筆)：槓桿≤3x
        - 階段3 (36-50筆)：槓桿≤4x
        - 正常期（51+筆）：無上限（模型自行判定）
        
        Args:
            win_probability: 勝率（0-1）
            confidence: 信心度（0-1）
            is_bootstrap_period: 是否在豁免期
            max_leverage: 階段性槓桿上限（v4.1+）
            verbose: 是否輸出詳細日誌
        
        Returns:
            槓桿倍數
        """
        # 🔥 v4.1+ 委托给 LeverageEngine 处理（含漸進式逻辑）
        return self.leverage_engine.calculate_leverage(
            win_probability, confidence, is_bootstrap_period, max_leverage, verbose
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
    ) -> tuple[float, float]:
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
            
            # 🔥 v3.31+ 滑點保護：使用限價單替代市價單
            from src.config import Config
            side = 'BUY' if signal['direction'] == 'LONG' else 'SELL'
            
            if Config.USE_LIMIT_ORDER_FOR_ENTRY:
                # 獲取最新價格
                current_price = await self.binance_client.get_ticker_price(signal['symbol'])
                
                # 計算帶滑點保護的限價
                if signal['direction'] == 'LONG':
                    # 做多：允許以高於當前價的價格買入（最多滑點容忍度）
                    limit_price = current_price * (1 + Config.SLIPPAGE_TOLERANCE)
                else:
                    # 做空：允許以低於當前價的價格賣出（最多滑點容忍度）
                    limit_price = current_price * (1 - Config.SLIPPAGE_TOLERANCE)
                
                # 🔥 v3.33+ 精度格式化：避免 "Precision is over the maximum" 錯誤
                formatted_price = await self.binance_client.format_price(signal['symbol'], limit_price)
                formatted_size = await self.binance_client.format_quantity(signal['symbol'], size)
                
                logger.info(
                    f"📊 滑點保護: {signal['symbol']} {signal['direction']} | "
                    f"當前價={current_price:.6f}, 限價={limit_price:.6f}→{formatted_price}, "
                    f"數量={size:.2f}→{formatted_size}, 容忍度={Config.SLIPPAGE_TOLERANCE:.2%}"
                )
                
                order_result = await self.binance_client.place_order(
                    symbol=signal['symbol'],
                    side=side,
                    order_type='LIMIT',  # 使用限價單
                    quantity=formatted_size,
                    price=formatted_price
                )
            else:
                # 降級方案：使用市價單（不推薦，有滑點風險）
                # 🔥 v3.33+ 精度格式化：市價單也需要格式化數量
                formatted_size = await self.binance_client.format_quantity(signal['symbol'], size)
                
                logger.warning(
                    f"⚠️ 使用市價單開倉（無滑點保護）| "
                    f"{signal['symbol']} {signal['direction']} 數量={size:.2f}→{formatted_size}"
                )
                order_result = await self.binance_client.place_order(
                    symbol=signal['symbol'],
                    side=side,
                    order_type='MARKET',
                    quantity=formatted_size
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
                    websocket_metadata = {}
                    if self.websocket_monitor:
                        kline = self.websocket_monitor.get_kline(signal['symbol'])
                        if kline:
                            websocket_metadata = {
                                'latency_ms': kline.get('latency_ms', 0),
                                'server_timestamp': kline.get('server_timestamp', 0),
                                'local_timestamp': kline.get('local_timestamp', 0),
                                'shard_id': kline.get('shard_id', 0)
                            }
                    
                    # 🔥 v4.0: 使用UnifiedTradeRecorder API（PostgreSQL）
                    trade_data = {
                        'symbol': signal['symbol'],
                        'direction': signal['direction'],
                        'entry_price': signal['entry_price'],
                        'position_size': size,
                        'confidence': signal.get('confidence', 0),
                        'win_probability': signal.get('win_probability', 0),
                        'risk_reward_ratio': signal.get('rr_ratio', 1.5),
                        'leverage': signal['leverage'],
                        'margin_used': position_value / signal['leverage'],
                        'entry_time': datetime.now(),
                        'stop_loss_price': signal.get('adjusted_stop_loss'),
                        'take_profit_price': signal.get('adjusted_take_profit'),
                        'strategy_version': 'v3.23',
                        'market_conditions': {
                            'websocket_metadata': websocket_metadata,
                            'competition_context': competition_context
                        }
                    }
                    
                    logger.info(f"🔍 [DIAG] SelfLearningTrader - 準備調用record_entry: {signal['symbol']}")
                    await self.trade_recorder.record_entry(trade_data)
                    logger.info(f"🔍 [DIAG] SelfLearningTrader - record_entry完成: {signal['symbol']}")
                    logger.debug(f"📝 記錄開倉信號: {signal['symbol']}")
                except Exception as e:
                    logger.error(f"❌ 記錄開倉信號失敗: {e}", exc_info=True)
                    logger.error(f"🔍 [DIAG] SelfLearningTrader - 異常堆棧已記錄")
            
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
        # 確保使用Config實例（self.config可能是類或實例）
        config_instance = self.config if not isinstance(self.config, type) else self.config()
        
        # 🔥 v3.18.7+ 獲取已完成交易數（用於豁免期判斷）
        # 防御性檢查：如果trade_recorder未初始化，默認total_trades=0
        if self.trade_recorder:
            total_trades = await self.trade_recorder.get_trade_count('all')  # 🔧 v3.23+ 修復：統計所有歷史交易
            logger.info(
                f"📊 豁免期檢查 | "
                f"已完成交易: {total_trades} 筆 | "
                f"豁免期門檻: {config_instance.BOOTSTRAP_TRADE_LIMIT} 筆 | "
                f"狀態: {'🎓 豁免期' if total_trades < config_instance.BOOTSTRAP_TRADE_LIMIT else '📊 正常期'}"
            )
        else:
            total_trades = 0
            logger.warning("⚠️ TradeRecorder未初始化，使用total_trades=0（豁免期模式）")
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
            
            # 🔥 v3.21+ 智能汰換系統：當保證金不足時，嘗試用高品質新信號替換低品質舊持倉
            logger.info("🔄 檢查智能汰換機會...")
            
            # 找到最高品質的新信號
            high_quality_signals = [
                s for s in signals 
                if self._evaluate_signal_quality(s) >= 80
            ]
            
            if high_quality_signals:
                # 按品質排序，取最好的
                best_new_signal = max(
                    high_quality_signals, 
                    key=lambda x: self._evaluate_signal_quality(x)
                )
                
                logger.info(
                    f"🎯 發現高品質信號: {best_new_signal['symbol']} | "
                    f"品質: {self._evaluate_signal_quality(best_new_signal):.1f}"
                )
                
                # 嘗試智能汰換
                replacement_success = await self.execute_smart_replacement(best_new_signal)
                
                if replacement_success:
                    logger.info("✅ 智能汰換成功，已優化持倉組合")
                    # 返回空列表（因為是汰換而非新增）
                    return []
                else:
                    logger.info("⚠️ 智能汰換未執行（品質提升不足或無可替換持倉）")
            else:
                logger.info("⚠️ 無高品質信號（≥80）可用於汰換")
            
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
    
    async def _count_completed_trades(self, use_cache: bool = True) -> int:
        """
        🔥 v4.6.0 Phase 2: 統計已完成的交易數（PostgreSQL唯一數據源）
        
        Args:
            use_cache: 是否使用緩存（默認True，避免重複查詢）
        
        Returns:
            已完成交易的總數量（從PostgreSQL計算）
        """
        # 🔥 使用緩存避免重複查詢（性能優化）
        import time
        if use_cache and self._cache_last_updated > 0:
            # Cache valid if updated within last 60 seconds
            if time.time() - self._cache_last_updated < 60:
                return self._completed_trades_cache
        
        # 🔥 v4.6.0 Phase 2: 從 PostgreSQL 讀取總交易數（已移除trades.jsonl fallback）
        if self.trade_recorder and hasattr(self.trade_recorder, 'data_service'):
            try:
                count = await self.trade_recorder.data_service.get_trade_count('closed')
                
                # 更新緩存
                self._completed_trades_cache = count
                logger.debug(f"📊 已完成交易數（PostgreSQL）: {count}")
                return count
                
            except Exception as e:
                logger.warning(f"⚠️ 從PostgreSQL讀取交易數失敗: {e}")
                self._completed_trades_cache = 0
                return 0
        else:
            logger.warning("⚠️ TradeRecorder或DataService未配置，無法統計交易數")
            self._completed_trades_cache = 0
            return 0
    
    async def update_trade_count_cache(self):
        """
        🔥 v4.6.0 Phase 2: 更新交易計數緩存（async方法，從scheduler調用）
        
        這個方法應該：
        1. 在系統啟動時調用一次
        2. 在每個trading cycle開始時調用（可選）
        3. 在交易完成後調用（自動更新）
        """
        import time
        count = await self._count_completed_trades(use_cache=False)
        self._cache_last_updated = time.time()
        logger.debug(f"✅ 交易計數緩存已更新: {count}")
        return count
    
    def _get_progressive_bootstrap_thresholds(self, trade_count: int) -> Dict:
        """
        🔥 v4.1+ 漸進式Bootstrap門檻（修復20%勝率過低問題）
        
        階段策略：
        - 階段1 (交易1-15):   勝率35%, 信心30%, 槓桿≤2x
        - 階段2 (交易16-35):  勝率40%, 信心35%, 槓桿≤3x
        - 階段3 (交易36-50):  勝率43%, 信心38%, 槓桿≤4x
        - 正常期 (交易51+):   勝率45%, 信心40%, 槓桿動態
        
        Args:
            trade_count: 已完成交易數
            
        Returns:
            階段配置字典
        """
        if trade_count <= 15:
            return {
                'phase': 'phase_1',
                'min_win_probability': 0.35,
                'min_confidence': 0.30,
                'max_leverage': 2.0,
                'trade_range': (1, 15)
            }
        elif trade_count <= 35:
            return {
                'phase': 'phase_2',
                'min_win_probability': 0.40,
                'min_confidence': 0.35,
                'max_leverage': 3.0,
                'trade_range': (16, 35)
            }
        elif trade_count <= 50:
            return {
                'phase': 'phase_3',
                'min_win_probability': 0.43,
                'min_confidence': 0.38,
                'max_leverage': 4.0,
                'trade_range': (36, 50)
            }
        else:
            return {
                'phase': 'normal',
                'min_win_probability': 0.45,
                'min_confidence': 0.40,
                'max_leverage': None,  # 動態槓桿
                'trade_range': (51, float('inf'))
            }
    
    def _get_current_thresholds(self) -> Dict:
        """
        🔥 v4.6.0 Phase 2: 獲取當前應使用的門檻值（v4.1+ 漸進式豁免機制）
        
        ✅ FIXED: 使用緩存值避免在同步方法中調用async方法（event loop問題）
        緩存由 update_trade_count_cache() 更新（從 UnifiedScheduler 調用）
        
        Returns:
            包含當前門檻的字典 {
                'min_win_probability': float,
                'min_confidence': float,
                'is_bootstrap': bool,
                'completed_trades': int,
                'remaining': int (僅豁免期),
                'phase': str (僅豁免期)
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
        
        # 🔥 v4.6.0 Phase 2: 使用緩存計數（避免 asyncio.run() 在 event loop 中崩潰）
        completed_trades = self._completed_trades_cache
        
        # 🔥 v4.1+ 使用漸進式門檻
        if completed_trades < self.config.BOOTSTRAP_TRADE_LIMIT:
            progressive = self._get_progressive_bootstrap_thresholds(completed_trades)
            return {
                'min_win_probability': progressive['min_win_probability'],
                'min_confidence': progressive['min_confidence'],
                'is_bootstrap': True,
                'completed_trades': completed_trades,
                'remaining': self.config.BOOTSTRAP_TRADE_LIMIT - completed_trades,
                'phase': progressive['phase'],
                'max_leverage': progressive['max_leverage']
            }
        else:
            # 已完成豁免期，使用正常門檻
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
    
    # ========== 智能汰換系統 (Smart Replacement System) ==========
    
    async def execute_smart_replacement(self, new_signal: Dict) -> bool:
        """
        🔄 智能汰換：用高品質新信號替換最低品質舊持倉
        
        策略：
        1. 評估新信號質量（必須 ≥80 才考慮汰換）
        2. 獲取當前所有持倉
        3. 找到品質最差的持倉
        4. 比較品質差異（新信號必須明顯優於舊持倉，至少+15點）
        5. 執行汰換（關閉舊倉 + 開啟新倉）
        
        Args:
            new_signal: 新的交易信號
            
        Returns:
            True表示汰換成功，False表示無法汰換
        """
        try:
            logger.info("🔄 啟動智能汰換系統")
            
            # 1. 評估新信號質量
            new_quality = self._evaluate_signal_quality(new_signal)
            if new_quality < 80:  # 高品質門檻
                logger.info(f"⚠️ 新信號質量 {new_quality:.1f} 未達汰換標準（需≥80）")
                return False
            
            logger.info(f"✅ 新信號 {new_signal['symbol']} 質量: {new_quality:.1f}（達標）")
            
            # 2. 獲取當前持倉
            current_positions = await self._get_current_positions_from_api()
            if not current_positions:
                logger.info("✅ 無當前持倉，無需汰換（可直接執行新信號）")
                return False  # 返回False讓調用者知道應該直接執行新信號
            
            # 3. 找到品質最差的持倉
            worst_position = self._find_lowest_quality_position(current_positions)
            if not worst_position:
                logger.warning("⚠️ 找不到可替換的持倉")
                return False
            
            # 4. 比較品質差異（新信號必須明顯優於舊持倉）
            worst_quality = self._calculate_position_quality(worst_position)
            quality_improvement = new_quality - worst_quality
            
            if quality_improvement < 15:  # 至少提升15點品質
                logger.info(
                    f"⚠️ 品質提升不足: {quality_improvement:.1f}點 (<15) | "
                    f"新:{new_quality:.1f} vs 舊:{worst_quality:.1f}"
                )
                return False
            
            # 5. 執行汰換
            return await self._execute_quality_replacement(
                worst_position, 
                new_signal, 
                quality_improvement
            )
            
        except Exception as e:
            logger.error(f"❌ 智能汰換失敗: {e}", exc_info=True)
            return False
    
    def _evaluate_signal_quality(self, signal: Dict) -> float:
        """
        🔥 v4.1+ 評估信號品質分數（重新平衡權重）
        
        FIXED計算公式：
        - 預測能力 = 信心值 × 勝率 (0-1)
        - 標準化RR = min(RR/2.5, 1.0) (上限2.5避免過度影響)
        - 最終品質 = 預測能力×70% + 標準化RR×30%
        - 轉換為0-100範圍
        
        修復說明：
        - 舊版本：40% confidence + 40% win_prob + 20% RR（RR主導問題）
        - 新版本：70% prediction_power + 30% RR（平衡）
        
        Args:
            signal: 交易信號
            
        Returns:
            品質分數（0-100）
        """
        try:
            # 輸入驗證與正規化（0-100 → 0-1）
            confidence = max(0.0, min(1.0, signal.get('confidence', 0) / 100.0))
            win_probability = max(0.0, min(1.0, signal.get('win_probability', 0) / 100.0))
            rr_ratio = max(0.0, signal.get('rr_ratio', signal.get('risk_reward_ratio', 1.0)))
            
            # 計算預測能力（信心 × 勝率）
            prediction_power = confidence * win_probability
            
            # 標準化RR（上限2.5，防止極端值主導）
            normalized_rr = min(rr_ratio / 2.5, 1.0)
            
            # 🔥 FIXED: 平衡加權（70%預測 + 30%RR）
            signal_quality = (prediction_power * 0.70) + (normalized_rr * 0.30)
            
            # 轉換為0-100範圍
            final_quality = signal_quality * 100.0
            
            return max(0.0, min(100.0, final_quality))
            
        except Exception as e:
            logger.error(f"❌ 信號品質評估失敗: {e}")
            return 0.0
    
    def _find_lowest_quality_position(self, positions: List[Dict]) -> Optional[Dict]:
        """
        找到品質最低的持倉（基於信心值、勝率、時間衰減、浮虧）
        
        Args:
            positions: 持倉列表
            
        Returns:
            品質最低的持倉，或None
        """
        try:
            if not positions:
                return None
            
            # 為每個持倉計算當前品質分數
            quality_scores = []
            for position in positions:
                quality = self._calculate_position_quality(position)
                quality_scores.append((quality, position))
                
                logger.debug(
                    f"📊 持倉品質評估: {position.get('symbol')} | "
                    f"方向: {position.get('side')} | "
                    f"品質分數: {quality:.1f}"
                )
            
            # 按品質分數排序（升序），取最低的
            quality_scores.sort(key=lambda x: x[0])
            lowest_quality, worst_position = quality_scores[0]
            
            logger.info(
                f"📉 找到最低品質持倉: {worst_position.get('symbol')} | "
                f"品質分數: {lowest_quality:.1f} | "
                f"方向: {worst_position.get('side')}"
            )
            
            return worst_position
            
        except Exception as e:
            logger.error(f"❌ 尋找最低品質持倉失敗: {e}")
            return None
    
    def _calculate_position_quality(self, position: Dict) -> float:
        """
        計算持倉當前品質分數（0-100）
        
        考慮因素：
        1. 基礎品質：原始信心值和勝率（如果有記錄）
        2. 時間衰減：持倉越久，品質衰減越多（72小時線性衰減到0.5）
        3. 浮虧懲罰：虧損超過2%則扣分
        
        Args:
            position: 持倉信息
            
        Returns:
            品質分數（0-100）
        """
        try:
            from datetime import datetime, timezone, timedelta
            
            # 基礎品質：如果有原始信號數據則使用，否則使用保守估計50分
            original_confidence = position.get('confidence', position.get('original_confidence', 50))
            original_win_rate = position.get('win_probability', position.get('original_win_rate', 50))
            base_quality = (original_confidence + original_win_rate) / 2
            
            # 時間衰減懲罰（持倉越久，品質衰減越多）
            entry_time = position.get('entry_time')
            if entry_time:
                if isinstance(entry_time, str):
                    try:
                        entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                    except:
                        entry_time = datetime.now(timezone.utc)
                
                hours_held = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600
                time_decay = max(0.5, 1.0 - (hours_held / 72))  # 72小時線性衰減到0.5
            else:
                time_decay = 0.8  # 無時間數據時使用保守衰減
            
            # 浮虧懲罰（基於PnL百分比）
            pnl_penalty = 0
            pnl_pct = position.get('pnl_pct', 0)
            
            if pnl_pct < -0.02:  # 虧損超過2%
                pnl_penalty = abs(pnl_pct) * 100  # 虧損懲罰（-10% → -10分）
            
            # 最終品質分數
            final_quality = (base_quality * time_decay) - pnl_penalty
            
            return max(0, min(100, final_quality))  # 限制在0-100範圍
            
        except Exception as e:
            logger.error(f"❌ 持倉品質計算失敗: {e}")
            return 0
    
    async def _get_current_positions_from_api(self) -> List[Dict]:
        """
        從Binance API獲取當前持倉列表
        
        Returns:
            持倉列表，每個持倉包含：
            - symbol: 交易對
            - side: 方向（'LONG' 或 'SHORT'）
            - size: 數量
            - entry_price: 入場價格
            - current_price: 當前價格（通過markPrice獲取）
            - pnl: 盈虧（USDT）
            - pnl_pct: 盈虧百分比
            - leverage: 槓桿
        """
        try:
            if not self.binance_client:
                logger.error("❌ Binance客戶端未初始化")
                return []
            
            # 獲取持倉信息
            raw_positions = await self.binance_client.get_position_info_async()
            
            positions = []
            for raw_pos in raw_positions:
                position_amt = float(raw_pos.get('positionAmt', 0))
                
                # 跳過空倉位
                if abs(position_amt) < 1e-8:
                    continue
                
                symbol = raw_pos.get('symbol')
                entry_price = float(raw_pos.get('entryPrice', 0))
                unrealized_pnl = float(raw_pos.get('unRealizedProfit', 0))
                leverage = int(raw_pos.get('leverage', 1))
                
                # 計算當前價格（通過markPrice）
                mark_price = float(raw_pos.get('markPrice', entry_price))
                
                # 計算PnL百分比
                if entry_price > 0:
                    if position_amt > 0:  # LONG
                        pnl_pct = (mark_price - entry_price) / entry_price
                    else:  # SHORT
                        pnl_pct = (entry_price - mark_price) / entry_price
                else:
                    pnl_pct = 0
                
                positions.append({
                    'symbol': symbol,
                    'side': 'LONG' if position_amt > 0 else 'SHORT',
                    'size': abs(position_amt),
                    'entry_price': entry_price,
                    'current_price': mark_price,
                    'pnl': unrealized_pnl,
                    'pnl_pct': pnl_pct,
                    'leverage': leverage,
                    'raw_position': raw_pos  # 保留原始數據以備後用
                })
            
            logger.debug(f"📊 獲取到 {len(positions)} 個持倉")
            return positions
            
        except Exception as e:
            logger.error(f"❌ 獲取持倉失敗: {e}")
            return []
    
    async def _close_position_for_replacement(self, position: Dict) -> Optional[float]:
        """
        關閉持倉（用於汰換）
        
        Args:
            position: 要關閉的持倉
            
        Returns:
            釋放的保證金金額，失敗則返回None
        """
        try:
            if not self.binance_client:
                logger.error("❌ Binance 客戶端未初始化")
                return None
            
            symbol = position.get('symbol')
            side = position.get('side')
            size = position.get('size')
            
            logger.info(f"🗑️ 關閉持倉: {symbol} {side} {size}")
            
            # 平倉方向：多頭平倉用SELL，空頭平倉用BUY
            close_side = 'SELL' if side == 'LONG' else 'BUY'
            
            # 🔥 v3.33+ 精度格式化：平倉數量也需要格式化
            formatted_size = await self.binance_client.format_quantity(symbol, size)
            
            # 市價平倉（依照Binance API協議自動適配Position Mode）
            # place_order 會自動判斷 Hedge/One-Way Mode 並添加正確參數
            order_result = await self.binance_client.place_order(
                symbol=symbol,
                side=close_side,
                order_type='MARKET',
                quantity=formatted_size,
                reduceOnly="true"  # 🔥 Critical: 字符串"true"，符合Binance API協議
            )
            
            if not order_result:
                logger.error(f"❌ 平倉失敗: {symbol}")
                return None
            
            # 計算釋放的保證金（入場價 × 數量 / 槓桿）
            entry_price = position.get('entry_price', 0)
            leverage = position.get('leverage', 1)
            released_margin = (entry_price * size) / leverage
            
            logger.info(f"💰 釋放保證金: ${released_margin:.2f}")
            
            return released_margin
            
        except Exception as e:
            logger.error(f"❌ 關閉持倉失敗 {position.get('symbol')}: {e}")
            return None
    
    async def _execute_quality_replacement(
        self,
        old_position: Dict,
        new_signal: Dict,
        quality_improvement: float
    ) -> bool:
        """
        執行品質汰換（關閉舊倉 + 開啟新倉）
        
        Args:
            old_position: 要關閉的舊持倉
            new_signal: 要執行的新信號
            quality_improvement: 品質提升幅度
            
        Returns:
            True表示汰換成功，False表示失敗
        """
        try:
            old_symbol = old_position.get('symbol')
            new_symbol = new_signal.get('symbol')
            
            logger.info(
                f"🔄 執行品質汰換: {old_symbol} → {new_symbol} | "
                f"品質提升: +{quality_improvement:.1f}點"
            )
            
            # 1. 關閉舊持倉
            released_margin = await self._close_position_for_replacement(old_position)
            if released_margin is None:
                logger.error(f"❌ 關閉舊持倉失敗: {old_symbol}")
                return False
            
            # 2. 等待訂單結算（給交易所一點時間更新帳戶狀態）
            import asyncio
            await asyncio.sleep(0.5)
            
            # 3. 獲取最新帳戶狀態
            if not self.binance_client:
                logger.error("❌ Binance 客戶端未初始化")
                return False
            
            account_balance = await self.binance_client.get_account_balance()
            available_margin = account_balance['available_balance']
            
            # 4. 計算新頭寸（使用可用保證金的一部分，基於信號品質）
            new_quality = self._evaluate_signal_quality(new_signal)
            position_percentage = self._calculate_aggressive_position_percentage(new_quality)
            max_position_value = available_margin * position_percentage
            
            # 5. 計算實際倉位大小
            if not new_symbol:
                logger.error("❌ 新信號缺少交易對符號")
                return False
            
            position_size = await self.calculate_position_size(
                account_equity=available_margin,
                entry_price=new_signal['entry_price'],
                stop_loss=new_signal['adjusted_stop_loss'],
                leverage=new_signal['leverage'],
                symbol=new_symbol,
                verbose=False
            )
            
            # 限制倉位大小不超過最大值
            position_notional = position_size * new_signal['entry_price']
            if position_notional > max_position_value:
                position_size = max_position_value / new_signal['entry_price']
            
            # 6. 執行新交易
            logger.info(
                f"📝 執行新交易: {new_symbol} | "
                f"倉位: {position_size:.4f} | "
                f"保證金使用率: {position_percentage:.0%}"
            )
            
            # 調用原有的下單方法（修正參數名稱）
            order_result = await self._place_order_and_monitor(
                signal=new_signal,
                size=position_size,
                available_balance=available_margin
            )
            
            if order_result:
                logger.info(
                    f"✅ 品質汰換成功: {old_symbol} → {new_symbol} | "
                    f"釋放保證金: ${released_margin:.2f} | "
                    f"新頭寸名義價值: ${position_notional:.2f} | "
                    f"品質提升: +{quality_improvement:.1f}點"
                )
                return True
            else:
                logger.error(f"❌ 新交易執行失敗: {new_symbol}")
                return False
            
        except Exception as e:
            logger.error(f"❌ 品質汰換執行失敗: {e}", exc_info=True)
            return False
    
    def _calculate_aggressive_position_percentage(self, quality: float) -> float:
        """
        根據信號品質計算激進倉位百分比
        
        高品質信號使用更高比例的保證金
        
        Args:
            quality: 信號品質分數（0-100）
            
        Returns:
            保證金使用百分比（0-1）
        """
        if quality >= 90:
            return 0.35  # 35%保證金
        elif quality >= 85:
            return 0.30  # 30%保證金
        elif quality >= 80:
            return 0.25  # 25%保證金
        else:
            return 0.20  # 20%保證金
