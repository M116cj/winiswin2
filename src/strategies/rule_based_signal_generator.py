"""
規則驅動信號生成器（v3.17+ SelfLearningTrader 架構）
職責：整合 ICT 策略邏輯，生成標準化交易信號
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
import logging

from src.utils.indicators import (
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_adx,
    identify_order_blocks,
    determine_market_structure
)
from src.config import Config
from src.utils.signal_details_logger import get_signal_details_logger

logger = logging.getLogger(__name__)


class RuleBasedSignalGenerator:
    """
    規則驅動信號生成器（v3.17+）
    
    職責：
    1. 整合 ICT/SMC 策略邏輯
    2. 生成標準化信號格式（供 SelfLearningTrader 使用）
    3. 計算基礎信心度（不含槓桿決策）
    """
    
    def __init__(self, config=None):
        """初始化信號生成器"""
        self.config = config or Config
        self._debug_stats = {
            'total_scanned': 0,
            'h1_bullish': 0, 'h1_bearish': 0, 'h1_neutral': 0,
            'm15_bullish': 0, 'm15_bearish': 0, 'm15_neutral': 0,
            'm5_bullish': 0, 'm5_bearish': 0, 'm5_neutral': 0,
            'structure_bullish': 0, 'structure_bearish': 0, 'structure_neutral': 0,
            'last_print_count': 0,
            'signals_generated': 0,
            'signals_passed_confidence': 0
        }
        
        self._pipeline_stats = {
            'stage0_total_symbols': 0,
            'stage1_valid_data': 0,
            'stage1_rejected_data': 0,
            'stage2_trend_ok': 0,
            'stage3_signal_direction': 0,
            'stage3_no_direction': 0,
            'stage3_priority1': 0,
            'stage3_priority2': 0,
            'stage3_priority3': 0,
            'stage3_priority4_relaxed': 0,
            'stage3_priority5_relaxed': 0,
            'stage4_adx_rejected_lt15': 0,
            'stage4_adx_penalty_15_20': 0,
            'stage4_adx_ok_gte20': 0,
            'stage5_confidence_calculated': 0,
            'stage6_win_prob_calculated': 0,
            'stage7_passed_double_gate': 0,
            'stage7_rejected_win_prob': 0,
            'stage7_rejected_confidence': 0,
            'stage7_rejected_rr': 0,
            'stage8_passed_quality': 0,
            'stage8_rejected_quality': 0,
            'stage9_ranked_signals': 0,
            'stage9_executed_signals': 0,
            'adx_distribution_lt15': 0,
            'adx_distribution_15_20': 0,
            'adx_distribution_20_25': 0,
            'adx_distribution_gte25': 0
        }
        
        logger.info("✅ RuleBasedSignalGenerator 初始化完成")
        logger.info(f"   🎚️ 信號模式: {'寬鬆模式' if self.config.RELAXED_SIGNAL_MODE else '嚴格模式'}")
        logger.info(f"   📊 10階段Pipeline診斷: 已啟用（每100個符號輸出統計）")
    
    def get_debug_stats(self) -> dict:
        """獲取調試統計數據"""
        return self._debug_stats.copy()
    
    def reset_debug_stats(self):
        """重置調試統計（每個週期開始時調用）"""
        self._debug_stats = {
            'total_scanned': 0,
            'h1_bullish': 0, 'h1_bearish': 0, 'h1_neutral': 0,
            'm15_bullish': 0, 'm15_bearish': 0, 'm15_neutral': 0,
            'm5_bullish': 0, 'm5_bearish': 0, 'm5_neutral': 0,
            'structure_bullish': 0, 'structure_bearish': 0, 'structure_neutral': 0,
            'last_print_count': 0,
            'signals_generated': 0,
            'signals_passed_confidence': 0
        }
        
        self._pipeline_stats = {
            'stage0_total_symbols': 0,
            'stage1_valid_data': 0,
            'stage1_rejected_data': 0,
            'stage2_trend_ok': 0,
            'stage3_signal_direction': 0,
            'stage3_no_direction': 0,
            'stage3_priority1': 0,
            'stage3_priority2': 0,
            'stage3_priority3': 0,
            'stage3_priority4_relaxed': 0,
            'stage3_priority5_relaxed': 0,
            'stage4_adx_rejected_lt15': 0,
            'stage4_adx_penalty_15_20': 0,
            'stage4_adx_ok_gte20': 0,
            'stage5_confidence_calculated': 0,
            'stage6_win_prob_calculated': 0,
            'stage7_passed_double_gate': 0,
            'stage7_rejected_win_prob': 0,
            'stage7_rejected_confidence': 0,
            'stage7_rejected_rr': 0,
            'stage8_passed_quality': 0,
            'stage8_rejected_quality': 0,
            'stage9_ranked_signals': 0,
            'stage9_executed_signals': 0,
            'adx_distribution_lt15': 0,
            'adx_distribution_15_20': 0,
            'adx_distribution_20_25': 0,
            'adx_distribution_gte25': 0
        }
    
    def get_pipeline_stats(self) -> dict:
        """獲取Pipeline統計數據"""
        return self._pipeline_stats.copy()
    
    def _print_pipeline_stats(self):
        """打印Pipeline統計數據（每100個符號）"""
        stats = self._pipeline_stats
        logger.info("=" * 80)
        logger.info(f"📊 Pipeline診斷報告（已掃描{stats['stage0_total_symbols']}個交易對）")
        logger.info("=" * 80)
        
        logger.info(f"Stage0 - 總掃描數: {stats['stage0_total_symbols']}")
        logger.info(f"Stage1 - 數據驗證: 有效={stats['stage1_valid_data']}, 拒絕={stats['stage1_rejected_data']}")
        if stats['stage1_valid_data'] > 0:
            reject_rate = stats['stage1_rejected_data'] / (stats['stage1_valid_data'] + stats['stage1_rejected_data']) * 100
            logger.info(f"         拒絕率: {reject_rate:.1f}%")
        
        logger.info(f"Stage2 - 趨勢判斷: 成功={stats['stage2_trend_ok']}")
        
        logger.info(f"Stage3 - 信號方向:")
        logger.info(f"         有方向={stats['stage3_signal_direction']}, 無方向={stats['stage3_no_direction']}")
        logger.info(f"         優先級1(完美對齊)={stats['stage3_priority1']}")
        logger.info(f"         優先級2(H1+M15)={stats['stage3_priority2']}")
        logger.info(f"         優先級3(趨勢初期)={stats['stage3_priority3']}")
        if self.config.RELAXED_SIGNAL_MODE:
            logger.info(f"         優先級4(H1主導-寬鬆)={stats['stage3_priority4_relaxed']}")
            logger.info(f"         優先級5(M15+M5-寬鬆)={stats['stage3_priority5_relaxed']}")
        
        logger.info(f"Stage4 - ADX過濾:")
        logger.info(f"         ADX<15(拒絕)={stats['stage4_adx_rejected_lt15']}")
        logger.info(f"         ADX 15-20(懲罰×0.8)={stats['stage4_adx_penalty_15_20']}")
        logger.info(f"         ADX≥20(通過)={stats['stage4_adx_ok_gte20']}")
        
        logger.info(f"ADX分布:")
        logger.info(f"         <15: {stats['adx_distribution_lt15']}")
        logger.info(f"         15-20: {stats['adx_distribution_15_20']}")
        logger.info(f"         20-25: {stats['adx_distribution_20_25']}")
        logger.info(f"         ≥25: {stats['adx_distribution_gte25']}")
        
        if stats['adx_distribution_lt15'] + stats['adx_distribution_15_20'] + stats['adx_distribution_20_25'] + stats['adx_distribution_gte25'] > 0:
            total_adx = stats['adx_distribution_lt15'] + stats['adx_distribution_15_20'] + stats['adx_distribution_20_25'] + stats['adx_distribution_gte25']
            lt15_pct = stats['adx_distribution_lt15'] / total_adx * 100
            logger.info(f"         🔥 ADX<15占比: {lt15_pct:.1f}% ← 主要過濾原因！" if lt15_pct > 50 else f"         ADX<15占比: {lt15_pct:.1f}%")
        
        logger.info(f"Stage5 - 信心度計算: {stats['stage5_confidence_calculated']}")
        logger.info(f"Stage6 - 勝率計算: {stats['stage6_win_prob_calculated']}")
        
        logger.info(f"Stage7 - 雙門檻驗證:")
        logger.info(f"         通過={stats['stage7_passed_double_gate']}")
        logger.info(f"         拒絕(勝率不足)={stats['stage7_rejected_win_prob']}")
        logger.info(f"         拒絕(信心不足)={stats['stage7_rejected_confidence']}")
        logger.info(f"         拒絕(R:R超範圍)={stats['stage7_rejected_rr']}")
        
        logger.info(f"Stage8 - 質量評分:")
        logger.info(f"         通過(quality≥門檻)={stats['stage8_passed_quality']}")
        logger.info(f"         拒絕(quality<門檻)={stats['stage8_rejected_quality']}")
        
        logger.info(f"Stage9 - 排序&執行:")
        logger.info(f"         排序候選={stats['stage9_ranked_signals']}")
        logger.info(f"         最終執行={stats['stage9_executed_signals']}")
        
        if stats['stage0_total_symbols'] > 0:
            funnel_rate = stats['stage9_executed_signals'] / stats['stage0_total_symbols'] * 100
            logger.info(f"")
            logger.info(f"🎯 Pipeline完整漏斗轉化率: {funnel_rate:.2f}% ({stats['stage9_executed_signals']}/{stats['stage0_total_symbols']})")
        logger.info("=" * 80)
    
    def generate_signal(
        self,
        symbol: str,
        multi_tf_data: Dict[str, pd.DataFrame]
    ) -> Optional[Dict]:
        """
        生成交易信號
        
        Args:
            symbol: 交易對
            multi_tf_data: 多時間框架數據
        
        Returns:
            標準化信號字典，包含：
            - symbol: 交易對
            - direction: 'LONG' 或 'SHORT'
            - entry_price: 入場價格
            - stop_loss: 止損價格
            - take_profit: 止盈價格
            - confidence: 基礎信心度（0-1）
            - win_probability: 預估勝率（0-1）
            - rr_ratio: 風報比
            - indicators: 所有技術指標
            - reasoning: 信號原因
        """
        try:
            self._pipeline_stats['stage0_total_symbols'] += 1
            
            # 驗證數據
            if not self._validate_data(multi_tf_data):
                self._pipeline_stats['stage1_rejected_data'] += 1
                return None
            
            # 🔥 添加類型安全檢查 - 確保數據不為None
            h1_data = multi_tf_data.get('1h')
            m15_data = multi_tf_data.get('15m')
            m5_data = multi_tf_data.get('5m')
            
            if h1_data is None or m15_data is None or m5_data is None:
                logger.warning(f"{symbol} 數據不完整，跳過信號生成")
                self._pipeline_stats['stage1_rejected_data'] += 1
                return None
            
            self._pipeline_stats['stage1_valid_data'] += 1
            
            # 計算所有指標
            indicators = self._calculate_all_indicators(h1_data, m15_data, m5_data)
            
            # 確定趨勢
            h1_trend = self._determine_trend(h1_data)
            m15_trend = self._determine_trend(m15_data)
            m5_trend = self._determine_trend(m5_data)
            
            self._pipeline_stats['stage2_trend_ok'] += 1
            
            # 市場結構
            market_structure = determine_market_structure(m15_data)
            
            # Order Blocks
            order_blocks = identify_order_blocks(
                m15_data,
                lookback=self.config.OB_LOOKBACK
            )
            
            # 流動性區域
            liquidity_zones = self._identify_liquidity_zones(m15_data)
            
            current_price = float(m5_data['close'].iloc[-1])
            
            # 確定信號方向
            signal_direction, priority_level = self._determine_signal_direction(
                h1_trend,
                m15_trend,
                m5_trend,
                market_structure,
                order_blocks,
                liquidity_zones,
                current_price
            )
            
            # 🔥 v3.18.7+ Debug: 記錄無信號原因（每50個交易對打印一次統計）
            if not signal_direction:
                self._pipeline_stats['stage3_no_direction'] += 1
                if not hasattr(self, '_debug_stats'):
                    self._debug_stats = {
                        'total_scanned': 0,
                        'h1_bullish': 0, 'h1_bearish': 0, 'h1_neutral': 0,
                        'm15_bullish': 0, 'm15_bearish': 0, 'm15_neutral': 0,
                        'm5_bullish': 0, 'm5_bearish': 0, 'm5_neutral': 0,
                        'structure_bullish': 0, 'structure_bearish': 0, 'structure_neutral': 0,
                        'last_print_count': 0  # 追蹤上次打印時的計數
                    }
                
                self._debug_stats['total_scanned'] += 1
                self._debug_stats[f'h1_{h1_trend}'] += 1
                self._debug_stats[f'm15_{m15_trend}'] += 1
                self._debug_stats[f'm5_{m5_trend}'] += 1
                self._debug_stats[f'structure_{market_structure}'] += 1
                
                # 每50個交易對打印一次統計（強制輸出）
                if self._debug_stats['total_scanned'] % 50 == 0:
                    logger.info(f"🔍 信號生成統計（已掃描{self._debug_stats['total_scanned']}個，0信號）：")
                    logger.info(f"   H1趨勢: bullish={self._debug_stats['h1_bullish']}, bearish={self._debug_stats['h1_bearish']}, neutral={self._debug_stats['h1_neutral']}")
                    logger.info(f"   M15趨勢: bullish={self._debug_stats['m15_bullish']}, bearish={self._debug_stats['m15_bearish']}, neutral={self._debug_stats['m15_neutral']}")
                    logger.info(f"   M5趨勢: bullish={self._debug_stats['m5_bullish']}, bearish={self._debug_stats['m5_bearish']}, neutral={self._debug_stats['m5_neutral']}")
                    logger.info(f"   市場結構: bullish={self._debug_stats['structure_bullish']}, bearish={self._debug_stats['structure_bearish']}, neutral={self._debug_stats['structure_neutral']}")
                    logger.info(f"   ⚠️ 建議啟用RELAXED_SIGNAL_MODE=true增加信號數量")
                    self._debug_stats['last_print_count'] = self._debug_stats['total_scanned']
                
                return None
            
            self._pipeline_stats['stage3_signal_direction'] += 1
            
            # 🔥 v3.18.9+ 修復：ADX 過濾條件（放寬以適應高波動市場）
            # 修復前：ADX < 20 → 直接拒絕（過於嚴格）
            # 修復後：ADX < 15 → 拒絕；15-20 → 降低信心度但不拒絕
            adx_value = indicators.get('adx', 25.0)
            adx_penalty = 1.0  # 默認無懲罰
            
            if adx_value < 15:
                self._pipeline_stats['adx_distribution_lt15'] += 1
                self._pipeline_stats['stage4_adx_rejected_lt15'] += 1
                logger.info(f"❌ {symbol} ADX過濾: ADX={adx_value:.1f}<15，純震盪市，拒絕信號（優先級{priority_level}）")
                return None
            elif adx_value < 20:
                self._pipeline_stats['adx_distribution_15_20'] += 1
                self._pipeline_stats['stage4_adx_penalty_15_20'] += 1
                adx_penalty = 0.8  # 信心度×0.8
                logger.debug(f"{symbol} ADX={adx_value:.1f}<20，低趨勢強度，信心度×0.8")
            elif adx_value < 25:
                self._pipeline_stats['adx_distribution_20_25'] += 1
                self._pipeline_stats['stage4_adx_ok_gte20'] += 1
            else:
                self._pipeline_stats['adx_distribution_gte25'] += 1
                self._pipeline_stats['stage4_adx_ok_gte20'] += 1
            
            # 🔥 v3.18.8+ 計算EMA偏差值指標
            deviation_metrics = self._calculate_ema_deviation_metrics(
                current_price=current_price,
                h1_data=h1_data,
                m15_data=m15_data,
                m5_data=m5_data,
                direction=signal_direction
            )
            
            # 計算基礎信心度（五維 ICT 評分，其中趨勢對齊40%替換為EMA偏差評分）
            confidence_score, sub_scores = self._calculate_confidence(
                h1_trend=h1_trend,
                m15_trend=m15_trend,
                m5_trend=m5_trend,
                market_structure=market_structure,
                order_blocks=order_blocks,
                liquidity_zones=liquidity_zones,
                current_price=current_price,
                h1_data=h1_data,
                m15_data=m15_data,
                m5_data=m5_data,
                direction=signal_direction,
                indicators=indicators,
                deviation_metrics=deviation_metrics  # 🔥 v3.18.8+ 新增EMA偏差指標
            )
            
            self._pipeline_stats['stage5_confidence_calculated'] += 1
            
            # 計算 SL/TP
            atr = indicators['atr']
            stop_loss, take_profit = self._calculate_sl_tp(
                current_price,
                signal_direction,
                atr,
                order_blocks
            )
            
            # 計算風報比
            risk = abs(current_price - stop_loss)
            reward = abs(take_profit - current_price)
            rr_ratio = reward / risk if risk > 0 else 1.5
            
            # 🔥 v3.18.9+ 應用ADX懲罰（如果適用）
            final_confidence_score = confidence_score * adx_penalty
            
            # 🔥 v3.18.8+ 預估勝率（基於EMA偏差值 + 歷史統計）
            win_probability = self._calculate_ema_based_win_probability(
                deviation_metrics=deviation_metrics,
                confidence_score=final_confidence_score,
                rr_ratio=rr_ratio,
                direction=signal_direction,
                market_structure=market_structure
            )
            
            self._pipeline_stats['stage6_win_prob_calculated'] += 1
            
            if self._pipeline_stats['stage0_total_symbols'] % 100 == 0:
                self._print_pipeline_stats()
            
            # 構建標準化信號
            signal = {
                'symbol': symbol,
                'direction': signal_direction,
                'entry_price': current_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': final_confidence_score / 100.0,  # 轉換為 0-1（已應用ADX懲罰）
                'win_probability': win_probability,
                'rr_ratio': rr_ratio,
                'indicators': indicators,
                'sub_scores': sub_scores,
                'reasoning': self._generate_reasoning(
                    signal_direction,
                    sub_scores,
                    market_structure,
                    h1_trend,
                    m15_trend,
                    m5_trend
                ),
                'timestamp': pd.Timestamp.now(),
                # 🔥 v3.18.4+ Critical: 完整特徵記錄（確保TradeRecorder可以捕獲所有ML特徵）
                'market_structure': market_structure,
                'order_blocks': len(order_blocks),
                'liquidity_zones': len(liquidity_zones),
                'timeframes': {
                    '1h_trend': h1_trend,
                    '15m_trend': m15_trend,
                    '5m_trend': m5_trend
                },
                # 🔥 v3.18.8+ EMA偏差指標（用於ML訓練和日誌）
                'ema_deviation': {
                    'h1_ema20_dev': deviation_metrics['h1_ema20_dev'],
                    'h1_ema50_dev': deviation_metrics['h1_ema50_dev'],
                    'm15_ema20_dev': deviation_metrics['m15_ema20_dev'],
                    'm15_ema50_dev': deviation_metrics['m15_ema50_dev'],
                    'm5_ema20_dev': deviation_metrics['m5_ema20_dev'],
                    'm5_ema50_dev': deviation_metrics['m5_ema50_dev'],
                    'avg_ema20_dev': deviation_metrics['avg_ema20_dev'],
                    'avg_ema50_dev': deviation_metrics['avg_ema50_dev'],
                    'deviation_score': deviation_metrics['deviation_score'],
                    'deviation_quality': deviation_metrics['deviation_quality']
                }
            }
            
            # 🔥 記錄到專屬日誌文件（不在Railway主日誌中顯示）
            signal_logger = get_signal_details_logger()
            signal_logger.log_signal_generated(
                symbol=symbol,
                direction=signal_direction,
                confidence=confidence_score / 100.0,
                win_rate=win_probability,
                rr_ratio=rr_ratio
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ {symbol} 信號生成失敗: {e}", exc_info=True)
            return None
    
    def _validate_data(self, multi_tf_data: Dict[str, pd.DataFrame]) -> bool:
        """驗證數據完整性"""
        required_tfs = ['1h', '15m', '5m']
        for tf in required_tfs:
            if tf not in multi_tf_data:
                return False
            df = multi_tf_data[tf]
            if df is None or len(df) < 50:
                return False
        return True
    
    def _calculate_all_indicators(self, h1_data, m15_data, m5_data) -> Dict:
        """計算所有技術指標"""
        indicators = {}
        
        # ATR（用於 SL/TP）
        indicators['atr'] = calculate_atr(m5_data, period=14).iloc[-1]
        
        # RSI
        indicators['rsi'] = calculate_rsi(m5_data, period=14).iloc[-1]
        
        # MACD
        macd_data = calculate_macd(m5_data)
        indicators['macd'] = macd_data['macd'].iloc[-1]
        indicators['macd_signal'] = macd_data['signal'].iloc[-1]
        indicators['macd_hist'] = macd_data['histogram'].iloc[-1]
        
        # 布林帶
        bb_data = calculate_bollinger_bands(m5_data)
        indicators['bb_upper'] = bb_data['upper'].iloc[-1]
        indicators['bb_middle'] = bb_data['middle'].iloc[-1]
        indicators['bb_lower'] = bb_data['lower'].iloc[-1]
        indicators['bb_width'] = bb_data['width'].iloc[-1]
        
        # ADX（趨勢強度）
        adx_data = calculate_adx(m5_data)
        indicators['adx'] = adx_data['adx'].iloc[-1]
        indicators['di_plus'] = adx_data['di_plus'].iloc[-1]
        indicators['di_minus'] = adx_data['di_minus'].iloc[-1]
        
        return indicators
    
    def _determine_trend(self, df: pd.DataFrame) -> str:
        """
        確定趨勢方向（v3.18.8+ 優化版）
        
        🔥 修復：簡化EMA排列要求，從4個嚴格不等號降至2個
        - 舊邏輯：價格 > EMA20 > EMA50 > EMA100（完美排列，極罕見）
        - 新邏輯：價格 > EMA20 AND EMA20 > EMA50（常見趨勢）
        
        預估改善：
        - Bullish: 1.6% → 25-35%
        - Bearish: 1.6% → 25-35%
        - Neutral: 96.8% → 30-50%
        """
        ema_20 = calculate_ema(df, period=20)
        ema_50 = calculate_ema(df, period=50)
        
        current_price = float(df['close'].iloc[-1])
        ema_20_val = float(ema_20.iloc[-1])
        ema_50_val = float(ema_50.iloc[-1])
        
        # 🔥 v3.18.8+ 簡化邏輯：只看價格與EMA20/50的關係
        # Bullish: 價格 > EMA20 AND EMA20 > EMA50
        if current_price > ema_20_val and ema_20_val > ema_50_val:
            return 'bullish'
        # Bearish: 價格 < EMA20 AND EMA20 < EMA50
        elif current_price < ema_20_val and ema_20_val < ema_50_val:
            return 'bearish'
        else:
            return 'neutral'
    
    def _identify_liquidity_zones(self, df: pd.DataFrame) -> list:
        """識別流動性區域"""
        # 🔥 轉換為numpy array確保類型安全
        highs = np.asarray(df['high'].values)
        lows = np.asarray(df['low'].values)
        
        zones = []
        window = 20
        
        for i in range(len(df) - window, len(df)):
            if i < window:
                continue
            
            # 識別高點聚集
            recent_highs = highs[i-window:i]
            max_high = float(np.max(recent_highs))
            high_cluster = int(np.sum(np.abs(recent_highs - max_high) / max_high < 0.002))
            
            if high_cluster >= 3:
                zones.append({
                    'type': 'resistance',
                    'price': max_high,
                    'strength': high_cluster
                })
            
            # 識別低點聚集
            recent_lows = lows[i-window:i]
            min_low = float(np.min(recent_lows))
            low_cluster = int(np.sum(np.abs(recent_lows - min_low) / min_low < 0.002))
            
            if low_cluster >= 3:
                zones.append({
                    'type': 'support',
                    'price': min_low,
                    'strength': low_cluster
                })
        
        return zones
    
    def _determine_signal_direction(
        self,
        h1_trend: str,
        m15_trend: str,
        m5_trend: str,
        market_structure: str,
        order_blocks: list,
        liquidity_zones: list,
        current_price: float
    ) -> tuple:
        """
        🔥 v3.18.7+: 確定信號方向（支持嚴格/寬松兩種模式）
        
        嚴格模式策略分層：
        1. 完美對齊：h1+m15+m5+market_structure完全一致（最高置信度）
        2. 強趨勢信號：h1+m15一致，market_structure支持（neutral可接受）
        3. 趨勢初期：h1明確，m15 neutral，m5確認，structure支持
        
        寬松模式策略分層（RELAXED_SIGNAL_MODE=true）：
        4. 單時間框架主導：H1明確趨勢，其他框架neutral可接受
        5. M15+M5對齊：短期趨勢，H1可以neutral
        
        Returns:
            (signal_direction, priority_level) or (None, None)
        """
        # ============ 嚴格模式（默認） ============
        # 優先級1: 四者完全一致（完美信號，最高置信度）
        if (h1_trend == 'bullish' and m15_trend == 'bullish' and 
            m5_trend == 'bullish' and market_structure == 'bullish'):
            self._pipeline_stats['stage3_priority1'] += 1
            return 'LONG', 1
        if (h1_trend == 'bearish' and m15_trend == 'bearish' and 
            m5_trend == 'bearish' and market_structure == 'bearish'):
            self._pipeline_stats['stage3_priority1'] += 1
            return 'SHORT', 1
        
        # 優先級2: h1+m15強趨勢，market_structure不對立（允許neutral和m5分歧）
        if (h1_trend == 'bullish' and m15_trend == 'bullish'):
            if market_structure in ['bullish', 'neutral']:
                self._pipeline_stats['stage3_priority2'] += 1
                return 'LONG', 2
        if (h1_trend == 'bearish' and m15_trend == 'bearish'):
            if market_structure in ['bearish', 'neutral']:
                self._pipeline_stats['stage3_priority2'] += 1
                return 'SHORT', 2
        
        # 優先級3: 趨勢初期場景（h1明確，m15 neutral，m5確認，structure支持）
        if (h1_trend == 'bullish' and m15_trend == 'neutral' and m5_trend == 'bullish'):
            if market_structure in ['bullish', 'neutral']:
                self._pipeline_stats['stage3_priority3'] += 1
                return 'LONG', 3
        if (h1_trend == 'bearish' and m15_trend == 'neutral' and m5_trend == 'bearish'):
            if market_structure in ['bearish', 'neutral']:
                self._pipeline_stats['stage3_priority3'] += 1
                return 'SHORT', 3
        
        # ============ 寬松模式（可選）============
        if self.config.RELAXED_SIGNAL_MODE:
            # 優先級4: H1主導（H1明確，其他可neutral，structure不對立）
            if h1_trend == 'bullish' and m15_trend != 'bearish' and market_structure != 'bearish':
                self._pipeline_stats['stage3_priority4_relaxed'] += 1
                return 'LONG', 4
            if h1_trend == 'bearish' and m15_trend != 'bullish' and market_structure != 'bullish':
                self._pipeline_stats['stage3_priority4_relaxed'] += 1
                return 'SHORT', 4
            
            # 優先級5: M15+M5短期對齊（H1可neutral，structure支持）
            if (m15_trend == 'bullish' and m5_trend == 'bullish' and 
                h1_trend != 'bearish' and market_structure in ['bullish', 'neutral']):
                self._pipeline_stats['stage3_priority5_relaxed'] += 1
                return 'LONG', 5
            if (m15_trend == 'bearish' and m5_trend == 'bearish' and 
                h1_trend != 'bullish' and market_structure in ['bearish', 'neutral']):
                self._pipeline_stats['stage3_priority5_relaxed'] += 1
                return 'SHORT', 5
        
        # 無法確定方向（拒絕對立信號）
        return None, None
    
    def _calculate_alignment_score(
        self,
        timeframes: dict,
        direction: str
    ) -> tuple:
        """
        📊 v3.19+ 修正1：時間框架對齊度評分（統一評分標準與生成條件）
        
        對齊度分數 = f(1h, 15m, 5m 趨勢一致性)
        
        核心原則：「評分標準 = 生成條件 = 執行依據 = 學習標籤」
        
        Args:
            timeframes: {'1h': trend, '15m': trend, '5m': trend}
            direction: 'LONG' or 'SHORT'
        
        Returns:
            (分數0-40, 等級字符串)
        """
        h1 = timeframes['1h']
        m15 = timeframes['15m']
        m5 = timeframes['5m']
        
        # 根據信號方向確定目標趨勢
        target_trend = 'bullish' if direction == 'LONG' else 'bearish'
        opposite_trend = 'bearish' if direction == 'LONG' else 'bullish'
        
        # 嚴格模式（RELAXED_SIGNAL_MODE=false）
        if not self.config.RELAXED_SIGNAL_MODE:
            # 完美對齊：三框架全部一致
            if h1 == target_trend and m15 == target_trend and m5 == target_trend:
                return 40.0, "Excellent"
            # 強對齊：1h+15m對齊，5m不對立
            elif h1 == target_trend and m15 == target_trend and m5 != opposite_trend:
                return 32.0, "Good"
            # 弱對齊：1h+5m對齊，15m中性
            elif h1 == target_trend and m15 == "neutral" and m5 == target_trend:
                return 24.0, "Fair"
            else:
                return 0.0, "Rejected"
        
        # 寬鬆模式（RELAXED_SIGNAL_MODE=true）
        else:
            # 計算1h+15m對齊度（主要決策框架）
            aligned_count = sum(1 for t in [h1, m15] if t == target_trend)
            
            if aligned_count == 2:
                # 1h+15m完美對齊
                return 32.0, "Good"
            elif aligned_count == 1 and m5 != opposite_trend:
                # 部分對齊且5m不對立
                return 24.0, "Fair"
            else:
                # 對齊度不足但仍可交易
                return 16.0, "Poor"
    
    def _classify_signal(
        self,
        signal: Dict,
        is_bootstrap: bool
    ) -> str:
        """
        📊 v3.19+ 修正4：信號分級（豁免期動態調整門檻）
        
        核心原則：「評分標準 = 生成條件 = 執行依據 = 學習標籤」
        
        Args:
            signal: 信號字典（包含confidence和win_probability）
            is_bootstrap: 是否處於豁免期
        
        Returns:
            信號等級: "Excellent"/"Good"/"Fair"/"Poor"/"Rejected"
        """
        confidence = signal.get('confidence', 0.0)
        win_probability = signal.get('win_probability', 0.0)
        
        if is_bootstrap:
            # 豁免期（前100筆交易）：僅拒絕極低質量
            # 目標：快速採集數據，接受Poor/Fair級別信號
            if confidence < 0.3 or win_probability < 0.3:
                return "Rejected"  # 極低質量，拒絕
            elif confidence >= 0.6:
                return "Excellent"  # 高質量
            elif confidence >= 0.5:
                return "Good"  # 中高質量
            else:
                return "Fair"  # Poor也接受（0.4-0.5範圍）
        else:
            # 正常期（100筆交易後）：嚴格分級
            # 目標：只接受高質量信號
            if confidence < 0.6:
                return "Rejected"  # 不符合最低標準
            elif confidence >= 0.8:
                return "Excellent"  # 卓越質量
            else:
                return "Good"  # 良好質量（0.6-0.8範圍）
    
    def _calculate_ob_score_with_decay(
        self,
        ob: Dict,
        current_time: pd.Timestamp
    ) -> float:
        """
        📊 v3.19+ 修正5：Order Block 時效衰減邏輯
        
        核心原則：「評分標準 = 生成條件 = 執行依據 = 學習標籤」
        
        明確衰減公式：
        - <48小時：全效（base_score × 1.0）
        - 48-72小時：線性衰減（base_score × decay_factor）
        - >72小時：失效（0.0）
        
        Args:
            ob: Order Block字典（包含created_at和quality_score）
            current_time: 當前時間戳
        
        Returns:
            調整後的OB分數（0-1）
        """
        # 提取創建時間
        ob_created = ob.get('created_at', ob.get('timestamp'))
        if ob_created is None:
            # 無時間信息，使用基礎分數
            return ob.get('quality_score', 0.5)
        
        # 確保時間戳格式一致
        if not isinstance(ob_created, pd.Timestamp):
            try:
                ob_created = pd.Timestamp(ob_created)
            except:
                return ob.get('quality_score', 0.5)
        
        # 計算年齡（小時）
        age_hours = (current_time - ob_created).total_seconds() / 3600
        
        # 基礎分數
        base_score = ob.get('quality_score', 0.5)
        
        # 應用時效衰減
        if age_hours > 72:
            # 72小時後失效
            return 0.0
        elif age_hours > 48:
            # 48-72小時線性衰減
            decay_factor = 1 - (age_hours - 48) / 24  # 線性從1.0衰減到0.0
            return base_score * decay_factor
        else:
            # 48小時內全效
            return base_score
    
    def _predict_signal_distribution(self, mode: str) -> Dict[str, float]:
        """
        📊 v3.19+ 修正6：動態預測信號分佈（嚴格/寬鬆模式）
        
        核心原則：「評分標準 = 生成條件 = 執行依據 = 學習標籤」
        
        Args:
            mode: "strict"（嚴格模式）或 "relaxed"（寬鬆模式）
        
        Returns:
            預期信號分佈字典 {等級: 占比}
        """
        if mode == "strict":
            # 嚴格模式：高質量信號占主導
            return {
                "Excellent": 0.30,  # 30% 卓越
                "Good": 0.40,       # 40% 良好
                "Fair": 0.30,       # 30% 中等
                "Poor": 0.00,       # 0% 低質（拒絕）
                "Rejected": 0.00    # 0% 拒絕
            }
        else:  # relaxed
            # 寬鬆模式：接受更多中低質量信號
            return {
                "Excellent": 0.15,  # 15% 卓越
                "Good": 0.25,       # 25% 良好
                "Fair": 0.35,       # 35% 中等
                "Poor": 0.25,       # 25% 低質（豁免期接受）
                "Rejected": 0.00    # 0% 拒絕
            }
    
    def _calculate_confidence(
        self,
        h1_trend: str,
        m15_trend: str,
        m5_trend: str,
        market_structure: str,
        order_blocks: list,
        liquidity_zones: list,
        current_price: float,
        h1_data: pd.DataFrame,
        m15_data: pd.DataFrame,
        m5_data: pd.DataFrame,
        direction: str,
        indicators: Dict,
        deviation_metrics: Optional[Dict] = None  # 🔥 v3.18.8+ 新增EMA偏差指標
    ) -> tuple:
        """
        計算五維 ICT 信心度評分
        
        🔥 v3.19+ 修正1：統一評分標準
        - 1️⃣ 時間框架對齊度 (40%) ← 統一「評分標準 = 生成條件」
        - 2️⃣ 市場結構 (20%)
        - 3️⃣ Order Block質量 (20%)
        - 4️⃣ 動量指標 (10%)
        - 5️⃣ 波動率 (10%)
        
        Returns:
            (總分, 子分數字典)
        """
        sub_scores = {}
        
        # 1️⃣ v3.19+ 修正1：時間框架對齊度評分 (40%)
        # 統一「評分標準 = 生成條件 = 執行依據 = 學習標籤」
        timeframes = {'1h': h1_trend, '15m': m15_trend, '5m': m5_trend}
        alignment_score, alignment_grade = self._calculate_alignment_score(timeframes, direction)
        sub_scores['timeframe_alignment'] = alignment_score
        sub_scores['alignment_grade'] = alignment_grade
        
        # 保留EMA偏差數據供參考（但不計入主評分）
        if deviation_metrics:
            sub_scores['ema_deviation_reference'] = deviation_metrics['deviation_score']
            sub_scores['deviation_quality_reference'] = deviation_metrics['deviation_quality']
        
        # 2️⃣ 市場結構 (20%)
        structure_score = 0.0
        if (direction == 'LONG' and market_structure == 'bullish') or \
           (direction == 'SHORT' and market_structure == 'bearish'):
            structure_score = 20.0
        
        sub_scores['market_structure'] = structure_score
        
        # 3️⃣ v3.19+ 修正5：Order Block 質量（含時效衰減）(20%)
        ob_score = 0.0
        current_time = pd.Timestamp.now()
        
        if order_blocks:
            relevant_obs = [
                ob for ob in order_blocks
                if (direction == 'LONG' and ob['type'] == 'bullish') or
                   (direction == 'SHORT' and ob['type'] == 'bearish')
            ]
            if relevant_obs:
                # 取最近的 OB（使用 zone 中點：(zone_low + zone_high) / 2）
                def get_ob_price(ob):
                    if 'price' in ob:
                        return ob['price']
                    elif 'zone_low' in ob and 'zone_high' in ob:
                        return (ob['zone_low'] + ob['zone_high']) / 2
                    else:
                        return current_price
                
                nearest_ob = min(relevant_obs, key=lambda x: abs(get_ob_price(x) - current_price))
                ob_price = get_ob_price(nearest_ob)
                ob_distance = abs(ob_price - current_price) / current_price
                
                # 距離分數（基礎分數）
                if ob_distance < 0.005:  # <0.5%
                    base_ob_score = 20.0
                elif ob_distance < 0.01:  # <1%
                    base_ob_score = 15.0
                elif ob_distance < 0.02:  # <2%
                    base_ob_score = 10.0
                else:
                    base_ob_score = 5.0
                
                # 🔥 v3.19+ 修正5：應用時效衰減
                # 原則：「評分標準 = 生成條件 = 執行依據 = 學習標籤」
                ob_quality_decayed = self._calculate_ob_score_with_decay(nearest_ob, current_time)
                decay_multiplier = ob_quality_decayed / max(nearest_ob.get('quality_score', 0.5), 0.01)
                
                # 最終分數 = 距離分數 × 時效衰減係數
                ob_score = base_ob_score * decay_multiplier
        
        sub_scores['order_block'] = ob_score
        
        # 4️⃣ 動量指標 (10%)
        momentum_score = 0.0
        rsi = indicators['rsi']
        macd_hist = indicators['macd_hist']
        
        if direction == 'LONG':
            if 50 <= rsi <= 70:
                momentum_score += 5.0
            if macd_hist > 0:
                momentum_score += 5.0
        elif direction == 'SHORT':
            if 30 <= rsi <= 50:
                momentum_score += 5.0
            if macd_hist < 0:
                momentum_score += 5.0
        
        sub_scores['momentum'] = momentum_score
        
        # 5️⃣ 波動率 (10%)
        volatility_score = 0.0
        bb_width = indicators['bb_width']
        
        # 計算波動率分位數
        bb_width_series = calculate_bollinger_bands(m5_data)['width']
        bb_percentile = (bb_width_series <= bb_width).sum() / len(bb_width_series)
        
        # 中等波動率最佳
        if 0.3 <= bb_percentile <= 0.7:
            volatility_score = 10.0
        elif 0.2 <= bb_percentile <= 0.8:
            volatility_score = 7.0
        else:
            volatility_score = 4.0
        
        sub_scores['volatility'] = volatility_score
        
        # 總分
        total_score = sum(sub_scores.values())
        
        return total_score, sub_scores
    
    def _calculate_sl_tp(
        self,
        entry_price: float,
        direction: str,
        atr: float,
        order_blocks: list
    ) -> tuple:
        """計算基礎 SL/TP（不含槓桿調整）"""
        # 基礎止損：2 ATR
        base_sl_distance = atr * 2.0
        
        if direction == 'LONG':
            stop_loss = entry_price - base_sl_distance
            take_profit = entry_price + (base_sl_distance * 1.5)
        else:  # SHORT
            stop_loss = entry_price + base_sl_distance
            take_profit = entry_price - (base_sl_distance * 1.5)
        
        return stop_loss, take_profit
    
    def _calculate_ema_deviation_metrics(
        self,
        current_price: float,
        h1_data: pd.DataFrame,
        m15_data: pd.DataFrame,
        m5_data: pd.DataFrame,
        direction: str
    ) -> Dict:
        """
        計算EMA偏差值指標（v3.18.8+）
        
        核心邏輯：
        - 價格越接近EMA（偏差小）→ 趨勢確認度高 → 信心值和勝率提升
        - 價格遠離EMA（偏差大）→ 可能是極端回撤或假突破 → 信心值和勝率降低
        
        Returns:
            {
                'h1_ema20_dev': 偏差百分比,
                'h1_ema50_dev': 偏差百分比,
                'm15_ema20_dev': 偏差百分比,
                'm15_ema50_dev': 偏差百分比,
                'm5_ema20_dev': 偏差百分比,
                'm5_ema50_dev': 偏差百分比,
                'avg_ema20_dev': 平均EMA20偏差,
                'avg_ema50_dev': 平均EMA50偏差,
                'deviation_score': 偏差評分 (0-100),
                'deviation_quality': 偏差質量等級 ('excellent'/'good'/'fair'/'poor')
            }
        """
        deviations = {}
        
        # 🔥 v3.18.9+ 修復：計算各時間框架的EMA偏差（僅計算同方向偏差）
        for timeframe, df in [('h1', h1_data), ('m15', m15_data), ('m5', m5_data)]:
            ema_20 = calculate_ema(df, period=20)
            ema_50 = calculate_ema(df, period=50)
            
            ema_20_val = float(ema_20.iloc[-1])
            ema_50_val = float(ema_50.iloc[-1])
            
            # 🔥 修復：僅計算同方向偏差（負值視為0）
            if direction == 'LONG':
                # LONG: 僅計算價格高於EMA的正偏差
                dev_20 = max(0.0, ((current_price - ema_20_val) / ema_20_val) * 100)
                dev_50 = max(0.0, ((current_price - ema_50_val) / ema_50_val) * 100)
            else:  # SHORT
                # SHORT: 僅計算價格低於EMA的正偏差（取反後為正）
                dev_20 = max(0.0, ((ema_20_val - current_price) / ema_20_val) * 100)
                dev_50 = max(0.0, ((ema_50_val - current_price) / ema_50_val) * 100)
            
            deviations[f'{timeframe}_ema20_dev'] = dev_20
            deviations[f'{timeframe}_ema50_dev'] = dev_50
        
        # 🔥 v3.18.9+ 修復：計算平均偏差（僅使用1h+15m，與信號決策邏輯對齊）
        # 修復前：使用1h+15m+5m → 5m可能與信號方向衝突，拉低評分
        # 修復後：僅使用1h+15m → 與_determine_signal_direction邏輯一致
        avg_ema20_dev = (deviations['h1_ema20_dev'] + deviations['m15_ema20_dev']) / 2
        avg_ema50_dev = (deviations['h1_ema50_dev'] + deviations['m15_ema50_dev']) / 2
        
        deviations['avg_ema20_dev'] = avg_ema20_dev
        deviations['avg_ema50_dev'] = avg_ema50_dev
        
        # 保留5m數據供調試（但不計入平均值）
        deviations['m5_ema20_dev_excluded'] = deviations['m5_ema20_dev']
        deviations['m5_ema50_dev_excluded'] = deviations['m5_ema50_dev']
        
        # 🔥 偏差評分邏輯（基於趨勢方向）
        deviation_score = 0.0
        
        if direction == 'LONG':
            # LONG：期待價格在EMA上方但不過遠（理想偏差：+0.5% ~ +3%）
            for dev in [deviations['h1_ema20_dev'], deviations['m15_ema20_dev'], deviations['m5_ema20_dev']]:
                if 0.5 <= dev <= 3.0:
                    deviation_score += 12.0  # 理想區間
                elif 0 <= dev < 0.5:
                    deviation_score += 8.0   # 接近EMA（稍弱）
                elif 3.0 < dev <= 5.0:
                    deviation_score += 6.0   # 偏離稍大（風險增加）
                elif dev < 0:
                    deviation_score += 2.0   # 價格低於EMA（逆勢）
                else:  # dev > 5.0
                    deviation_score += 1.0   # 極端偏離（假突破風險）
            
            # EMA50額外確認（權重較低）
            avg_ema50 = avg_ema50_dev
            if 1.0 <= avg_ema50 <= 5.0:
                deviation_score += 4.0
            elif avg_ema50 > 5.0:
                deviation_score -= 2.0  # 過度偏離扣分
        
        elif direction == 'SHORT':
            # SHORT：期待價格在EMA下方但不過遠（理想偏差：-3% ~ -0.5%）
            for dev in [deviations['h1_ema20_dev'], deviations['m15_ema20_dev'], deviations['m5_ema20_dev']]:
                if -3.0 <= dev <= -0.5:
                    deviation_score += 12.0  # 理想區間
                elif -0.5 < dev <= 0:
                    deviation_score += 8.0   # 接近EMA（稍弱）
                elif -5.0 <= dev < -3.0:
                    deviation_score += 6.0   # 偏離稍大（風險增加）
                elif dev > 0:
                    deviation_score += 2.0   # 價格高於EMA（逆勢）
                else:  # dev < -5.0
                    deviation_score += 1.0   # 極端偏離（假突破風險）
            
            # EMA50額外確認（權重較低）
            avg_ema50 = avg_ema50_dev
            if -5.0 <= avg_ema50 <= -1.0:
                deviation_score += 4.0
            elif avg_ema50 < -5.0:
                deviation_score -= 2.0  # 過度偏離扣分
        
        # 限制分數範圍 (0-40，對應40%權重)
        deviation_score = max(0.0, min(40.0, deviation_score))
        
        deviations['deviation_score'] = deviation_score
        
        # 偏差質量等級
        if deviation_score >= 35:
            deviations['deviation_quality'] = 'excellent'  # 理想偏差
        elif deviation_score >= 28:
            deviations['deviation_quality'] = 'good'       # 良好偏差
        elif deviation_score >= 20:
            deviations['deviation_quality'] = 'fair'       # 中等偏差
        else:
            deviations['deviation_quality'] = 'poor'       # 偏差過大或逆勢
        
        return deviations
    
    def _calculate_ema_based_win_probability(
        self,
        deviation_metrics: Dict,
        confidence_score: float,
        rr_ratio: float,
        direction: str,
        market_structure: str
    ) -> float:
        """
        基於EMA偏差值計算勝率（v3.18.8+）
        
        核心邏輯：
        - 偏差質量優秀（excellent）→ 基礎勝率65-70%
        - 偏差質量良好（good）→ 基礎勝率60-65%
        - 偏差質量中等（fair）→ 基礎勝率55-60%
        - 偏差質量差（poor）→ 基礎勝率50-55%
        
        Returns:
            勝率 (0.50-0.75)
        """
        # 🔥 基礎勝率（基於偏差質量）
        quality = deviation_metrics['deviation_quality']
        
        if quality == 'excellent':
            base_win_rate = 0.675  # 67.5%
        elif quality == 'good':
            base_win_rate = 0.625  # 62.5%
        elif quality == 'fair':
            base_win_rate = 0.575  # 57.5%
        else:  # poor
            base_win_rate = 0.525  # 52.5%
        
        # 🔥 v3.18.9+ 修復：R:R 調整（改為獎勵合理風報比）
        # 修復前：R:R > 2.5 → 懲罰（-2%/單位）→ 高風報比被低估
        # 修復後：1.5-2.5最佳區間 → 獎勵（+5%）→ 鼓勵合理風報比
        if 1.5 <= rr_ratio <= 2.5:
            rr_adjustment = 0.05  # 最佳區間，獎勵+5%
        elif rr_ratio > 2.5:
            rr_adjustment = 0.02  # 高風報比仍獎勵+2%
        else:  # rr_ratio < 1.5
            rr_adjustment = -0.05  # 低風報比懲罰-5%
        
        # 市場結構調整
        structure_bonus = 0.02 if (
            (direction == 'LONG' and market_structure == 'bullish') or
            (direction == 'SHORT' and market_structure == 'bearish')
        ) else 0.0
        
        # 精細化偏差調整（額外加成）
        avg_ema20_dev = abs(deviation_metrics['avg_ema20_dev'])
        if direction == 'LONG':
            # LONG最佳偏差：+0.5% ~ +3%
            if 0.5 <= deviation_metrics['avg_ema20_dev'] <= 3.0:
                deviation_bonus = 0.03  # 額外+3%勝率
            else:
                deviation_bonus = 0.0
        else:  # SHORT
            # SHORT最佳偏差：-3% ~ -0.5%
            if -3.0 <= deviation_metrics['avg_ema20_dev'] <= -0.5:
                deviation_bonus = 0.03  # 額外+3%勝率
            else:
                deviation_bonus = 0.0
        
        win_probability = base_win_rate + rr_adjustment + structure_bonus + deviation_bonus
        
        # 限制範圍
        return max(0.50, min(0.75, win_probability))
    
    def _generate_reasoning(
        self,
        direction: str,
        sub_scores: Dict,
        market_structure: str,
        h1_trend: str,
        m15_trend: str,
        m5_trend: str
    ) -> str:
        """生成信號推理說明"""
        reasons = []
        
        # 趨勢對齊
        if sub_scores['trend_alignment'] >= 35:
            reasons.append(f"三時間框架趨勢強勁對齊({h1_trend}/{m15_trend}/{m5_trend})")
        
        # 市場結構
        if sub_scores['market_structure'] >= 15:
            reasons.append(f"市場結構支持{direction}({market_structure})")
        
        # OB 質量
        if sub_scores['order_block'] >= 15:
            reasons.append("Order Block 距離理想")
        
        # 動量
        if sub_scores['momentum'] >= 8:
            reasons.append("動量指標確認")
        
        # 波動率
        if sub_scores['volatility'] >= 8:
            reasons.append("波動率適中")
        
        return " | ".join(reasons)
