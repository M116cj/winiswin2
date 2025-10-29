"""
特徵工程引擎 v3.17.2+
職責：加入競價上下文特徵 + WebSocket專屬特徵

解決「數據浪費」問題：
- signal_competitions.jsonl 僅用於審計，未用於改進模型
- 競價上下文包含重要信息（排名、分數差距、競爭強度）
- WebSocket元數據包含網路品質資訊（延遲、時間戳一致性、分片負載）
"""

import logging
from typing import Dict, Optional, Deque
from collections import deque

logger = logging.getLogger(__name__)


class FeatureEngine:
    """
    特徵工程引擎
    
    核心功能：
    1. 構建基礎特徵（38個原有特徵）
    2. 加入競價上下文特徵（3個新特徵）
    3. 加入WebSocket專屬特徵（3個新特徵）
    4. 總計 44 個特徵
    """
    
    def __init__(self):
        """初始化特徵工程引擎"""
        # 🔥 v3.17.2+：追蹤延遲統計（用於計算Z-score）
        self.latency_history: Deque[float] = deque(maxlen=1000)  # 保留最近1000次延遲
        self.shard_load_counter: Dict[int, int] = {}  # {shard_id: request_count}
        
        logger.info("=" * 60)
        logger.info("✅ 特徵工程引擎已創建 v3.17.2+")
        logger.info("   🎯 功能：基礎特徵 + 競價上下文特徵 + WebSocket特徵")
        logger.info("=" * 60)
    
    def build_enhanced_features(
        self, 
        signal: Dict, 
        competition_context: Optional[Dict] = None,
        websocket_metadata: Optional[Dict] = None
    ) -> Dict:
        """
        加入競價上下文特徵 + WebSocket專屬特徵
        
        Args:
            signal: 交易信號（包含所有基礎特徵）
            competition_context: 競價上下文
                {
                    'rank': 1,              # 信號排名
                    'my_score': 0.782,      # 該信號評分
                    'best_score': 0.782,    # 最高評分
                    'total_signals': 5      # 總信號數
                }
            websocket_metadata: WebSocket元數據（v3.17.2+）
                {
                    'latency_ms': 23,         # 網路延遲（毫秒）
                    'server_timestamp': 1730177520000,  # 伺服器時間
                    'local_timestamp': 1730177520023,   # 本地時間
                    'shard_id': 0             # 分片ID
                }
        
        Returns:
            增強的特徵字典（44個特徵）
        """
        # 構建基礎特徵
        base_features = self._build_base_features(signal)
        
        # 如果沒有競價上下文，使用默認值
        if competition_context is None:
            competition_context = {
                'rank': 1,
                'my_score': signal.get('confidence', 0.5),
                'best_score': signal.get('confidence', 0.5),
                'total_signals': 1
            }
        
        # 新增特徵：信號在競價中的相對排名
        rank_features = {
            'competition_rank': competition_context['rank'],  # 1, 2, 3...
            'score_gap_to_best': competition_context['best_score'] - competition_context['my_score'],
            'num_competing_signals': competition_context['total_signals']
        }
        
        # 🔥 v3.17.2+：新增WebSocket專屬特徵
        websocket_features = self._build_websocket_features(websocket_metadata)
        
        # 合併特徵
        enhanced_features = {**base_features, **rank_features, **websocket_features}
        
        logger.debug(
            f"✅ 構建增強特徵: {signal['symbol']} "
            f"Rank={rank_features['competition_rank']} "
            f"Gap={rank_features['score_gap_to_best']:.4f} "
            f"Total={rank_features['num_competing_signals']} "
            f"Latency={websocket_features.get('latency_zscore', 0):.2f}σ"
        )
        
        return enhanced_features
    
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
                'order_blocks_count': signal.get('order_blocks', 0),
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
                'market_structure': self._encode_structure(signal.get('market_structure', 'neutral')),
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
                'fvg_count': 0,
                'swing_high_distance': 0.0,
                'swing_low_distance': 0.0,
                'volume_profile': 0.5,
                'price_momentum': 0.0,
                'order_flow': 0.0,
                'liquidity_grab': 0,
                'institutional_candle': 0
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
        獲取所有特徵名稱（44個）
        
        Returns:
            特徵名稱列表
        """
        return [
            # 基本特徵 (8)
            'confidence', 'leverage', 'position_value', 'risk_reward_ratio',
            'order_blocks_count', 'liquidity_zones_count', 'entry_price', 'win_probability',
            
            # 技術指標 (10)
            'rsi', 'macd', 'macd_signal', 'macd_histogram', 'atr', 'bb_width',
            'volume_sma_ratio', 'ema50', 'ema200', 'volatility_24h',
            
            # 趨勢特徵 (6)
            'trend_1h', 'trend_15m', 'trend_5m', 'market_structure', 'direction', 'trend_alignment',
            
            # 其他特徵 (14)
            'ema50_slope', 'ema200_slope', 'higher_highs', 'lower_lows',
            'support_strength', 'resistance_strength', 'fvg_count',
            'swing_high_distance', 'swing_low_distance', 'volume_profile',
            'price_momentum', 'order_flow', 'liquidity_grab', 'institutional_candle',
            
            # 競價上下文特徵 (3) - v3.17.10+
            'competition_rank', 'score_gap_to_best', 'num_competing_signals',
            
            # 🔥 WebSocket專屬特徵 (3) - v3.17.2+
            'latency_zscore', 'shard_load', 'timestamp_consistency'
        ]
    
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
