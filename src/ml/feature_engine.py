"""
特徵工程引擎 v4.0 (Pure ICT/SMC + Unified Schema)
職責：純ICT/SMC高級特徵（移除傳統技術指標）

v4.0 特徵構成（统一schema）：
- 8個基礎特徵：market_structure, order_blocks_count, institutional_candle, 
                liquidity_grab, order_flow, fvg_count, trend_alignment_enhanced, swing_high_distance
- 4個合成特徵：structure_integrity, institutional_participation, 
                timeframe_convergence, liquidity_context

總特徵數：12個（與訓練一致）
"""

import logging
import numpy as np
from typing import Dict, Optional, Deque, List
from collections import deque
from src.utils.ict_tools import ICTTools
from src.ml.feature_schema import CANONICAL_FEATURE_NAMES, FEATURE_DEFAULTS

logger = logging.getLogger(__name__)


class FeatureEngine:
    """
    特徵工程引擎 v3.19 (Pure ICT/SMC)
    
    核心功能：
    1. 🔥 純ICT/SMC高級特徵（12個）
       - 基礎特徵（8個）
       - 合成特徵（4個）
    2. 移除傳統技術指標（簡化為純機構交易邏輯）
    """
    
    def __init__(self):
        """初始化特徵工程引擎"""
        # 🔥 v3.19：訂單流緩衝（用於計算實時訂單流）
        self.trade_buffer: Deque[Dict] = deque(maxlen=1000)
        
        # v3.17.2+: WebSocket特徵追蹤
        self.latency_history: Deque[float] = deque(maxlen=100)
        self.shard_load_counter: Dict[int, int] = {}
        
        logger.info("=" * 60)
        logger.info("✅ 特徵工程引擎已創建 v4.0 (Pure ICT/SMC + Unified Schema)")
        logger.info("   🎯 功能：純ICT/SMC機構交易特徵")
        logger.info("   📊 總特徵數：12個（與訓練一致）")
        logger.info("=" * 60)
    
    def build_enhanced_features(
        self, 
        signal: Dict, 
        competition_context: Optional[Dict] = None,
        websocket_metadata: Optional[Dict] = None,
        klines_data: Optional[Dict] = None,
        trade_data: Optional[List[Dict]] = None,
        depth_data: Optional[Dict] = None
    ) -> Dict:
        """
        構建純ICT/SMC特徵（12個）
        
        Args:
            signal: 交易信號
            klines_data: K線數據（用於ICT/SMC特徵）
            trade_data: 交易流數據（用於訂單流特徵）
            depth_data: 深度數據（用於流動性特徵）
        
        Returns:
            純ICT/SMC特徵字典（12個特徵）
        """
        # 🔥 v3.19：只構建ICT/SMC特徵（12個）
        ict_smc_features = self._build_ict_smc_features(
            signal, 
            klines_data=klines_data,
            trade_data=trade_data,
            depth_data=depth_data
        )
        
        logger.debug(
            f"✅ 構建12個ICT/SMC特徵: {signal.get('symbol', 'UNKNOWN')} "
            f"MarketStructure={ict_smc_features.get('market_structure', 0)} "
            f"OrderBlocks={ict_smc_features.get('order_blocks_count', 0)} "
            f"StructureIntegrity={ict_smc_features.get('structure_integrity', 0):.2f}"
        )
        
        return ict_smc_features
    
    def _build_base_features(self, signal: Dict) -> Dict:
        """
        構建基礎特徵（38個原有特徵）
        
        Args:
            signal: 交易信號
            
        Returns:
            基礎特徵字典
        """
        try:
            # 基本特徵 (8個)
            basic_features = {
                'confidence': signal.get('confidence', 0.5),
                'leverage': signal.get('leverage', 1.0),
                'position_value': signal.get('position_value', 0.0),
                'risk_reward_ratio': signal.get('rr_ratio', 1.5),
                'order_blocks_count_legacy': signal.get('order_blocks', 0),
                'liquidity_zones_count': signal.get('liquidity_zones', 0),
                'entry_price': signal.get('entry_price', 0.0),
                'win_probability': signal.get('win_probability', 0.5)
            }
            
            # 技術指標 (10個)
            indicators = signal.get('indicators', {})
            technical_features = {
                'rsi': indicators.get('rsi', 50.0),
                'macd': indicators.get('macd', 0.0),
                'macd_signal': indicators.get('macd_signal', 0.0),
                'macd_histogram': indicators.get('macd_histogram', 0.0),
                'atr': indicators.get('atr', 0.0),
                'bb_width': indicators.get('bb_width', 0.0),
                'volume_sma_ratio': indicators.get('volume_sma_ratio', 1.0),
                'ema50': indicators.get('ema50', 0.0),
                'ema200': indicators.get('ema200', 0.0),
                'volatility_24h': indicators.get('volatility_24h', 0.0)
            }
            
            # 趨勢特徵 (6個)
            timeframes = signal.get('timeframes', {})
            trend_features = {
                'trend_1h': self._encode_trend(timeframes.get('1h', 'neutral')),
                'trend_15m': self._encode_trend(timeframes.get('15m', 'neutral')),
                'trend_5m': self._encode_trend(timeframes.get('5m', 'neutral')),
                'market_structure_legacy': self._encode_structure(signal.get('market_structure', 'neutral')),
                'direction': 1 if signal.get('direction') == 'LONG' else -1,
                'trend_alignment': self._calculate_trend_alignment(timeframes)
            }
            
            # 其他特徵 (14個) - 使用默認值
            other_features = {
                'ema50_slope': 0.0,
                'ema200_slope': 0.0,
                'higher_highs': 0,
                'lower_lows': 0,
                'support_strength': 0.5,
                'resistance_strength': 0.5,
                'fvg_count_legacy': 0,
                'swing_high_distance_legacy': 0.0,
                'swing_low_distance': 0.0,
                'volume_profile': 0.5,
                'price_momentum': 0.0,
                'order_flow_legacy': 0.0,
                'liquidity_grab_legacy': 0,
                'institutional_candle_legacy': 0
            }
            
            # 合併所有基礎特徵
            return {
                **basic_features,
                **technical_features,
                **trend_features,
                **other_features
            }
            
        except Exception as e:
            logger.error(f"構建基礎特徵失敗: {e}", exc_info=True)
            # 返回最小特徵集
            return {
                'confidence': signal.get('confidence', 0.5),
                'leverage': signal.get('leverage', 1.0),
                'win_probability': signal.get('win_probability', 0.5)
            }
    
    def _encode_trend(self, trend: str) -> int:
        """
        編碼趨勢
        
        Args:
            trend: 'bullish', 'bearish', 'neutral'
            
        Returns:
            1 (bullish), -1 (bearish), 0 (neutral)
        """
        if trend == 'bullish':
            return 1
        elif trend == 'bearish':
            return -1
        else:
            return 0
    
    def _encode_structure(self, structure: str) -> int:
        """
        編碼市場結構
        
        Args:
            structure: 'bullish', 'bearish', 'neutral'
            
        Returns:
            1 (bullish), -1 (bearish), 0 (neutral)
        """
        return self._encode_trend(structure)
    
    def _calculate_trend_alignment(self, timeframes: Dict) -> float:
        """
        計算趨勢對齊度
        
        Args:
            timeframes: {'1h': 'bullish', '15m': 'bullish', '5m': 'neutral'}
            
        Returns:
            對齊度 (0~1)
        """
        trends = [
            self._encode_trend(timeframes.get('1h', 'neutral')),
            self._encode_trend(timeframes.get('15m', 'neutral')),
            self._encode_trend(timeframes.get('5m', 'neutral'))
        ]
        
        # 計算絕對值總和 / 3
        # 完全對齊（都是1或都是-1）= 1.0
        # 完全不對齊（混合）= 0~0.67
        alignment = abs(sum(trends)) / 3.0
        
        return alignment
    
    def get_feature_names(self) -> list:
        """
        獲取所有特徵名稱（12個純ICT/SMC特徵）
        
        v4.0: 使用统一的CANONICAL_FEATURE_NAMES（与训练一致）
        
        Returns:
            特徵名稱列表（v4.0：統一schema的12個ICT/SMC特徵）
        """
        return CANONICAL_FEATURE_NAMES
    
    # ==================== v3.17.2+ WebSocket專屬特徵方法 ====================
    
    def _build_websocket_features(self, websocket_metadata: Optional[Dict]) -> Dict:
        """
        構建WebSocket專屬特徵（v3.17.2+）
        
        Args:
            websocket_metadata: WebSocket元數據
        
        Returns:
            WebSocket特徵字典
        """
        if websocket_metadata is None:
            # 默認值（向後兼容）
            return {
                'latency_zscore': 0.0,
                'shard_load': 0.0,
                'timestamp_consistency': 1
            }
        
        latency_ms = websocket_metadata.get('latency_ms', 0)
        server_ts = websocket_metadata.get('server_timestamp', 0)
        local_ts = websocket_metadata.get('local_timestamp', 0)
        shard_id = websocket_metadata.get('shard_id', 0)
        
        return {
            'latency_zscore': self._calculate_latency_zscore(latency_ms),
            'shard_load': self._get_shard_load(shard_id),
            'timestamp_consistency': self._calculate_timestamp_consistency(server_ts, local_ts)
        }
    
    def _calculate_latency_zscore(self, latency_ms: float) -> float:
        """
        計算延遲Z-score（標準化延遲）
        
        Args:
            latency_ms: 網路延遲（毫秒）
        
        Returns:
            延遲Z-score（標準差數）
        """
        # 更新延遲歷史
        self.latency_history.append(latency_ms)
        
        # 至少需要10個樣本才能計算Z-score
        if len(self.latency_history) < 10:
            return 0.0
        
        # 計算均值和標準差
        mean_latency = sum(self.latency_history) / len(self.latency_history)
        variance = sum((x - mean_latency) ** 2 for x in self.latency_history) / len(self.latency_history)
        std_latency = variance ** 0.5
        
        # 避免除以零
        if std_latency == 0:
            return 0.0
        
        # 計算Z-score
        z_score = (latency_ms - mean_latency) / std_latency
        
        return z_score
    
    def _get_shard_load(self, shard_id: int) -> float:
        """
        獲取分片負載（歸一化）
        
        Args:
            shard_id: WebSocket分片ID
        
        Returns:
            分片負載（0-1範圍）
        """
        # 更新分片請求計數
        self.shard_load_counter[shard_id] = self.shard_load_counter.get(shard_id, 0) + 1
        
        # 計算總請求數
        total_requests = sum(self.shard_load_counter.values())
        
        # 避免除以零
        if total_requests == 0:
            return 0.0
        
        # 計算該分片的負載百分比
        shard_load = self.shard_load_counter[shard_id] / total_requests
        
        return shard_load
    
    def _calculate_timestamp_consistency(self, server_ts: int, local_ts: int) -> int:
        """
        計算時間戳一致性
        
        Args:
            server_ts: 伺服器時間戳（毫秒）
            local_ts: 本地時間戳（毫秒）
        
        Returns:
            1=一致（差異<1秒），0=不一致（差異≥1秒）
        """
        if server_ts == 0 or local_ts == 0:
            return 1  # 默認一致（向後兼容）
        
        timestamp_diff = abs(local_ts - server_ts)
        
        # 差異小於1秒視為一致
        return 1 if timestamp_diff < 1000 else 0
    
    # ==================== v3.19 ICT/SMC高級特徵方法 ====================
    
    @staticmethod
    def _is_valid_data(data) -> bool:
        """
        檢查數據是否有效（不為None且不為空）
        
        Args:
            data: 數據對象（可能是DataFrame、List或None）
        
        Returns:
            True if data is valid and non-empty, False otherwise
        """
        if data is None:
            return False
        # DataFrame检查
        if hasattr(data, 'empty'):
            return not data.empty
        # List/Tuple检查
        if isinstance(data, (list, tuple)):
            return len(data) > 0
        # 其他类型默认为有效
        return True
    
    @staticmethod
    def _convert_to_dict_list(data):
        """
        將DataFrame轉換為字典列表（ICTTools需要此格式）
        
        Args:
            data: DataFrame或List[Dict]
        
        Returns:
            List[Dict] or original data if not DataFrame
        """
        if data is None:
            return []
        # 如果是DataFrame，轉換為字典列表
        if hasattr(data, 'to_dict'):
            return data.to_dict('records')
        # 如果已經是列表，直接返回
        return data
    
    def _build_ict_smc_features(
        self,
        signal: Dict,
        klines_data: Optional[Dict] = None,
        trade_data: Optional[List[Dict]] = None,
        depth_data: Optional[Dict] = None
    ) -> Dict:
        """
        構建ICT/SMC高級特徵（12個）
        
        Args:
            signal: 交易信號
            klines_data: K線數據 {'1h': [...], '15m': [...], '5m': [...]}
            trade_data: 交易流數據
            depth_data: 深度數據
        
        Returns:
            ICT/SMC特徵字典（12個）
        """
        # 獲取K線數據
        if klines_data is None:
            klines_data = {
                '1h': signal.get('klines_1h', []),
                '15m': signal.get('klines_15m', []),
                '5m': signal.get('klines_5m', [])
            }
        
        klines_1h = klines_data.get('1h', [])
        klines_15m = klines_data.get('15m', [])
        klines_5m = klines_data.get('5m', [])
        
        # 轉換DataFrame為字典列表（ICTTools需要此格式）
        klines_1h_list = self._convert_to_dict_list(klines_1h)
        klines_15m_list = self._convert_to_dict_list(klines_15m)
        klines_5m_list = self._convert_to_dict_list(klines_5m)
        
        # 獲取當前價格和ATR
        current_price = signal.get('entry_price', 0)
        atr = signal.get('indicators', {}).get('atr', 0)
        
        # === 8個基礎特徵 ===
        
        # 1. market_structure（市場結構）
        market_structure = ICTTools.calculate_market_structure(klines_1h_list) if self._is_valid_data(klines_1h) else 0
        
        # 2. order_blocks_count（訂單塊數量）
        order_blocks_count = ICTTools.detect_order_blocks(klines_15m_list) if self._is_valid_data(klines_15m) else 0
        
        # 3. institutional_candle（機構K線）
        institutional_candle = 0
        if self._is_valid_data(klines_5m) and len(klines_5m) > 20:
            institutional_candle = ICTTools.detect_institutional_candle(
                klines_5m_list[-1], 
                klines_5m_list
            )
        
        # 4. liquidity_grab（流動性抓取）
        liquidity_grab = 0
        if self._is_valid_data(klines_5m) and atr > 0:
            liquidity_grab = ICTTools.detect_liquidity_grab(klines_5m_list, atr)
        
        # 5. order_flow（訂單流）
        order_flow = self._calculate_order_flow(trade_data) if trade_data else 0.0
        
        # 6. fvg_count（FVG數量）
        fvg_count = ICTTools.detect_fvg(klines_5m_list) if self._is_valid_data(klines_5m) else 0
        
        # 7. trend_alignment_enhanced（趨勢對齊度增強版）
        trend_alignment_enhanced = self._calculate_trend_alignment_enhanced(
            klines_1h, klines_15m, klines_5m
        )
        
        # 8. swing_high_distance（擺動高點距離）
        swing_high_distance = 0.0
        if self._is_valid_data(klines_15m) and current_price > 0 and atr > 0:
            swing_high_distance = ICTTools.calculate_swing_distance(
                klines_15m_list, current_price, atr, 'high'
            )
        
        # === 4個合成特徵 ===
        
        # 1. structure_integrity（結構完整性）
        structure_integrity = self._calculate_structure_integrity(
            market_structure, fvg_count, order_blocks_count
        )
        
        # 2. institutional_participation（機構參與度）
        institutional_participation = self._calculate_institutional_participation(
            institutional_candle, order_flow, liquidity_grab
        )
        
        # 3. timeframe_convergence（時間框架收斂度）
        timeframe_convergence = self._calculate_timeframe_convergence(
            klines_1h, klines_15m, klines_5m
        )
        
        # 4. liquidity_context（流動性情境）
        liquidity_context = self._calculate_liquidity_context(
            depth_data, liquidity_grab
        )
        
        return {
            # 基礎特徵（8個）
            'market_structure': market_structure,
            'order_blocks_count': order_blocks_count,
            'institutional_candle': institutional_candle,
            'liquidity_grab': liquidity_grab,
            'order_flow': order_flow,
            'fvg_count': fvg_count,
            'trend_alignment_enhanced': trend_alignment_enhanced,
            'swing_high_distance': swing_high_distance,
            
            # 合成特徵（4個）
            'structure_integrity': structure_integrity,
            'institutional_participation': institutional_participation,
            'timeframe_convergence': timeframe_convergence,
            'liquidity_context': liquidity_context
        }
    
    def _calculate_order_flow(self, trade_data: Optional[List[Dict]]) -> float:
        """
        計算訂單流（買賣壓力平衡）
        
        Returns:
            訂單流值（-1到1）
        """
        if not trade_data:
            return 0.0
        
        buy_volume = sum(t.get('q', 0) for t in trade_data if not t.get('m', True))
        sell_volume = sum(t.get('q', 0) for t in trade_data if t.get('m', True))
        total_volume = buy_volume + sell_volume
        
        if total_volume > 0:
            order_flow = (buy_volume - sell_volume) / total_volume
        else:
            order_flow = 0.0
        
        return order_flow
    
    def _calculate_trend_alignment_enhanced(
        self,
        klines_1h: List[Dict],
        klines_15m: List[Dict],
        klines_5m: List[Dict]
    ) -> float:
        """
        計算趨勢對齊度（增強版）
        
        Returns:
            對齊度（0到1）
        """
        # 轉換為字典列表
        klines_1h_list = self._convert_to_dict_list(klines_1h)
        klines_15m_list = self._convert_to_dict_list(klines_15m)
        klines_5m_list = self._convert_to_dict_list(klines_5m)
        
        trend_1h = ICTTools.calculate_market_structure(klines_1h_list) if self._is_valid_data(klines_1h) else 0
        trend_15m = ICTTools.calculate_market_structure(klines_15m_list) if self._is_valid_data(klines_15m) else 0
        trend_5m = ICTTools.calculate_market_structure(klines_5m_list) if self._is_valid_data(klines_5m) else 0
        
        trends = [trend_1h, trend_15m, trend_5m]
        
        # 計算對齊度
        if len(set(trends)) == 1 and trends[0] != 0:
            return 1.0  # 完全對齊
        elif len([t for t in trends if t == trends[0]]) == 2:
            return 0.5  # 部分對齊
        else:
            return 0.0  # 不對齊
    
    def _calculate_structure_integrity(
        self,
        market_structure: int,
        fvg_count: int,
        order_blocks_count: int
    ) -> float:
        """
        計算結構完整性
        
        公式: 0.4 * I(結構明確) + 0.3 * (1 - FVG懲罰) + 0.3 * tanh(訂單塊/3)
        
        Returns:
            結構完整性（0到1）
        """
        structure_clear = 1 if market_structure != 0 else 0
        fvg_penalty = 1 - min(1, fvg_count / 5)
        ob_score = np.tanh(order_blocks_count / 3) if order_blocks_count > 0 else 0
        
        integrity = 0.4 * structure_clear + 0.3 * fvg_penalty + 0.3 * ob_score
        
        return integrity
    
    def _calculate_institutional_participation(
        self,
        institutional_candle: int,
        order_flow: float,
        liquidity_grab: int
    ) -> float:
        """
        計算機構參與度
        
        公式: 0.5 * 機構K線 + 0.3 * |訂單流| + 0.2 * 流動性抓取
        
        Returns:
            機構參與度（0到1）
        """
        participation = (
            0.5 * institutional_candle +
            0.3 * abs(order_flow) +
            0.2 * liquidity_grab
        )
        
        return participation
    
    def _calculate_timeframe_convergence(
        self,
        klines_1h: List[Dict],
        klines_15m: List[Dict],
        klines_5m: List[Dict]
    ) -> float:
        """
        計算時間框架收斂度
        
        公式: 1 - (std(趨勢向量) / 2)
        
        Returns:
            收斂度（0到1）
        """
        # 轉換為字典列表
        klines_1h_list = self._convert_to_dict_list(klines_1h)
        klines_15m_list = self._convert_to_dict_list(klines_15m)
        klines_5m_list = self._convert_to_dict_list(klines_5m)
        
        trend_1h = ICTTools.calculate_market_structure(klines_1h_list) if self._is_valid_data(klines_1h) else 0
        trend_15m = ICTTools.calculate_market_structure(klines_15m_list) if self._is_valid_data(klines_15m) else 0
        trend_5m = ICTTools.calculate_market_structure(klines_5m_list) if self._is_valid_data(klines_5m) else 0
        
        trends = np.array([trend_1h, trend_15m, trend_5m])
        std = np.std(trends)
        convergence = 1 - (std / 2)
        
        return max(0.0, min(1.0, convergence))
    
    def _calculate_liquidity_context(
        self,
        depth_data: Optional[Dict],
        liquidity_grab: int
    ) -> float:
        """
        計算流動性情境
        
        公式: 0.7 * 流動性得分 + 0.3 * 流動性抓取
        
        Returns:
            流動性情境（0到1）
        """
        if not depth_data:
            # 無深度數據時，僅基於流動性抓取
            return 0.3 * liquidity_grab
        
        try:
            best_bid_qty = depth_data.get('bids', [[0, 0]])[0][1]
            best_ask_qty = depth_data.get('asks', [[0, 0]])[0][1]
            depth = (best_bid_qty + best_ask_qty) / 2
            
            best_bid_price = depth_data.get('bids', [[0, 0]])[0][0]
            best_ask_price = depth_data.get('asks', [[1, 1]])[0][0]
            spread = (best_ask_price - best_bid_price) / best_bid_price if best_bid_price > 0 else 0
            
            liquidity_score = (
                0.6 * np.tanh(depth / 100) +
                0.4 * (1 - min(1, spread / 0.001))
            )
            
            context = 0.7 * liquidity_score + 0.3 * liquidity_grab
            
            return context
        except (IndexError, KeyError, TypeError):
            # 深度數據格式錯誤時的fallback
            return 0.3 * liquidity_grab
