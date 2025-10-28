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
    
    def __init__(self, config=None, binance_client=None, trade_recorder=None, virtual_position_manager=None):
        """
        初始化 SelfLearningTrader
        
        Args:
            config: 配置對象
            binance_client: Binance 客戶端（用於獲取交易規格）
            trade_recorder: 交易記錄器（用於記錄競價結果）
            virtual_position_manager: 虛擬倉位管理器（用於創建虛擬倉位）
        """
        self.config = config or Config
        self.binance_client = binance_client
        self.trade_recorder = trade_recorder
        self.virtual_position_manager = virtual_position_manager
        
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
        logger.info("   🏆 多信號競價: 加權評分（信心40% + 勝率40% + R:R 20%）")
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
        account_info = await self.binance_client.get_account_info()
        available_balance = float(account_info.get('availableBalance', 0))
        total_equity = float(account_info.get('totalWalletBalance', 0))
        
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
        
        # === 6. 執行下單 ===
        position = await self._place_order_and_monitor(
            best['signal'], best['size'], available_balance
        )
        
        # === 7. 創建虛擬倉位（未執行信號）===
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
            f"🏆 選中 {best['signal']['symbol']} | "
            f"評分: {best['score']:.3f} | "
            f"信心: {best['details']['confidence']:.1%} | "
            f"勝率: {best['details']['win_rate']:.1%} | "
            f"R:R: {best['details']['rr_ratio']:.2f}"
        )

    async def _place_order_and_monitor(
        self, 
        signal: Dict, 
        size: float, 
        available_balance: float
    ) -> Optional[Dict]:
        """
        執行下單並監控倉位
        
        Args:
            signal: 交易信號
            size: 倉位數量
            available_balance: 可用保證金
            
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
                    self.trade_recorder.record_entry(
                        signal=signal,
                        position_info={
                            'leverage': signal['leverage'],
                            'position_value': position_value,
                            'size': size
                        }
                    )
                    logger.debug(f"📝 記錄開倉信號: {signal['symbol']}")
                except Exception as e:
                    logger.warning(f"⚠️ 記錄開倉信號失敗: {e}")
            
            logger.info(
                f"✅ 下單成功: {signal['symbol']} {signal['direction']} | "
                f"數量={size:.6f} | 槓桿={signal['leverage']:.1f}x | "
                f"價值=${position_value:.2f}"
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
