"""
🔥 v3.19 ML模型包装器
职责：加载XGBoost模型并提供预测接口
v3.19更新：支持56个特征（44→56，新增12个ICT/SMC特征）
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict
import numpy as np

logger = logging.getLogger(__name__)


class MLModelWrapper:
    """
    ML模型包装器（v3.19）
    
    职责：
    1. 加载训练好的XGBoost模型
    2. 提供56个特征的预测接口（v3.19：44→56）
    3. 处理模型不存在的fallback
    4. 向后兼容44特征模型
    """
    
    def __init__(self, model_path: str = "models/xgboost_model.json"):
        """
        初始化ML模型包装器
        
        Args:
            model_path: 模型文件路径
        """
        self.model_path = Path(model_path)
        self.model = None
        self.is_loaded = False
        
        # 尝试加载模型
        self._load_model()
    
    def _load_model(self) -> bool:
        """
        加载XGBoost模型
        
        Returns:
            是否成功加载
        """
        if not self.model_path.exists():
            logger.warning(f"⚠️ ML模型不存在: {self.model_path}")
            logger.info("   将使用规则引擎作为fallback")
            return False
        
        try:
            import xgboost as xgb
            
            # 加载模型
            self.model = xgb.Booster()
            self.model.load_model(str(self.model_path))
            
            self.is_loaded = True
            
            model_size = os.path.getsize(self.model_path) / 1024
            logger.info("=" * 60)
            logger.info(f"✅ ML模型已加载: {self.model_path}")
            logger.info(f"   模型大小: {model_size:.2f} KB")
            logger.info(f"   🔥 v3.19：使用56个特征进行预测（44→56）")
            logger.info("=" * 60)
            
            return True
            
        except ImportError:
            logger.error("❌ XGBoost未安装，无法加载模型")
            logger.info("   请运行: pip install xgboost")
            return False
        except Exception as e:
            logger.error(f"❌ 加载模型失败: {e}")
            return False
    
    def predict(self, features: List[float]) -> Optional[float]:
        """
        预测获胜概率
        
        Args:
            features: 56个特征的数值列表（v3.19）
        
        Returns:
            获胜概率（0-1），或None（如果模型未加载）
        """
        if not self.is_loaded or self.model is None:
            return None
        
        try:
            import xgboost as xgb
            
            # 验证特征数量（支持44或56）
            if len(features) not in [44, 56]:
                logger.warning(f"⚠️ 特征数量错误: {len(features)} != 56（或44向后兼容）")
                return None
            
            # 如果是44特征，补齐到56特征（向后兼容）
            if len(features) == 44:
                logger.debug("向后兼容：补齐44→56特征")
                features = features + [0.0] * 12  # 补齐12个ICT/SMC特征为默认值
            
            # 创建DMatrix
            dmatrix = xgb.DMatrix([features])
            
            # 预测
            prediction = self.model.predict(dmatrix)[0]
            
            return float(prediction)
            
        except Exception as e:
            logger.error(f"❌ 预测失败: {e}")
            return None
    
    def predict_from_signal(self, signal: Dict) -> Optional[float]:
        """
        从信号字典预测获胜概率
        
        Args:
            signal: 包含所有56个特征字段的信号字典（v3.19）
        
        Returns:
            获胜概率（0-1），或None（如果模型未加载或特征不完整）
        """
        if not self.is_loaded:
            return None
        
        try:
            # 按照FeatureEngine顺序提取44个特征
            features = self._extract_features_from_signal(signal)
            
            if features is None:
                return None
            
            # 预测
            return self.predict(features)
            
        except Exception as e:
            logger.error(f"❌ 从信号预测失败: {e}")
            return None
    
    def _extract_features_from_signal(self, signal: Dict) -> Optional[List[float]]:
        """
        🔥 v3.19: 从信号字典提取56个特征（容错处理）
        
        与FeatureEngine.get_feature_names()保持一致的容错逻辑
        
        Args:
            signal: 信号字典（可能缺少部分字段）
        
        Returns:
            56个特征的数值列表（v3.19：44→56）
        """
        try:
            # 🔥 优先使用FeatureEngine已生成的特征（如果存在）
            indicators = signal.get('indicators', {})
            timeframes = signal.get('timeframes', {})
            
            # 🔥 v3.18.6+ Critical Fix: 所有字段都使用默认值
            features = [
                # 基本特徵 (8) - 核心字段优先从signal读取
                float(signal.get('confidence', 0.5)),
                float(signal.get('leverage', 1.0)),
                float(signal.get('position_value', 0.0)),
                float(signal.get('rr_ratio', 1.5)),
                float(signal.get('order_blocks', 0)),
                float(signal.get('liquidity_zones', 0)),
                float(signal.get('entry_price', 0.0)),
                float(signal.get('win_probability', 0.5)),
                
                # 技術指標 (10) - 从indicators字典或直接从signal读取
                float(indicators.get('rsi', signal.get('rsi', 50.0))),
                float(indicators.get('macd', signal.get('macd', 0.0))),
                float(indicators.get('macd_signal', signal.get('macd_signal', 0.0))),
                float(indicators.get('macd_histogram', signal.get('macd_histogram', 0.0))),
                float(indicators.get('atr', signal.get('atr', 0.0))),
                float(indicators.get('bb_width', signal.get('bb_width', 0.0))),
                float(indicators.get('volume_sma_ratio', signal.get('volume_sma_ratio', 1.0))),
                float(indicators.get('ema50', signal.get('ema50', 0.0))),
                float(indicators.get('ema200', signal.get('ema200', 0.0))),
                float(indicators.get('volatility_24h', signal.get('volatility_24h', 0.0))),
                
                # 趨勢特徵 (6) - 需要编码
                self._encode_trend(timeframes.get('1h', signal.get('trend_1h', 'neutral'))),
                self._encode_trend(timeframes.get('15m', signal.get('trend_15m', 'neutral'))),
                self._encode_trend(timeframes.get('5m', signal.get('trend_5m', 'neutral'))),
                self._encode_structure(signal.get('market_structure', 'neutral')),
                1.0 if signal.get('direction') == 'LONG' else -1.0,
                self._calculate_trend_alignment(timeframes) if timeframes else float(signal.get('trend_alignment', 0.0)),
                
                # 其他特徵 (14) - 使用默认值
                float(signal.get('ema50_slope', 0.0)),
                float(signal.get('ema200_slope', 0.0)),
                float(signal.get('higher_highs', 0)),
                float(signal.get('lower_lows', 0)),
                float(signal.get('support_strength', 0.5)),
                float(signal.get('resistance_strength', 0.5)),
                float(signal.get('fvg_count', 0)),
                float(signal.get('swing_high_distance', 0.0)),
                float(signal.get('swing_low_distance', 0.0)),
                float(signal.get('volume_profile', 0.5)),
                float(signal.get('price_momentum', 0.0)),
                float(signal.get('order_flow', 0.0)),
                float(signal.get('liquidity_grab', 0)),
                float(signal.get('institutional_candle', 0)),
                
                # 競價上下文特徵 (3)
                float(signal.get('competition_rank', 1)),
                float(signal.get('score_gap_to_best', 0.0)),
                float(signal.get('num_competing_signals', 1)),
                
                # WebSocket專屬特徵 (3)
                float(signal.get('latency_zscore', 0.0)),
                float(signal.get('shard_load', 0.0)),
                float(signal.get('timestamp_consistency', 1)),
                
                # 🔥 v3.19 ICT/SMC高級特徵 - 基礎特徵 (8)
                float(signal.get('market_structure', 0)),
                float(signal.get('order_blocks_count', 0)),
                float(signal.get('institutional_candle', 0)),
                float(signal.get('liquidity_grab', 0)),
                float(signal.get('order_flow', 0.0)),
                float(signal.get('fvg_count', 0)),
                float(signal.get('trend_alignment_enhanced', 0.0)),
                float(signal.get('swing_high_distance', 0.0)),
                
                # 🔥 v3.19 ICT/SMC高級特徵 - 合成特徵 (4)
                float(signal.get('structure_integrity', 0.0)),
                float(signal.get('institutional_participation', 0.0)),
                float(signal.get('timeframe_convergence', 0.0)),
                float(signal.get('liquidity_context', 0.0))
            ]
            
            # 验证长度（支持44或56）
            if len(features) not in [44, 56]:
                logger.error(f"特徵數量錯誤: {len(features)} != 56（或44向后兼容）")
                return None
            
            return features
            
        except (ValueError, TypeError) as e:
            logger.warning(f"特徵提取失敗（數據類型錯誤）: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ 提取特征异常: {e}")
            return None
    
    def _encode_trend(self, trend: str) -> float:
        """编码趋势"""
        if trend == 'bullish':
            return 1.0
        elif trend == 'bearish':
            return -1.0
        else:
            return 0.0
    
    def _encode_structure(self, structure: str) -> float:
        """编码市场结构"""
        return self._encode_trend(structure)
    
    def _calculate_trend_alignment(self, timeframes: Dict) -> float:
        """计算趋势对齐度"""
        trends = [
            self._encode_trend(timeframes.get('1h', 'neutral')),
            self._encode_trend(timeframes.get('15m', 'neutral')),
            self._encode_trend(timeframes.get('5m', 'neutral'))
        ]
        
        alignment = abs(sum(trends)) / 3.0
        return alignment
    
    def reload(self) -> bool:
        """
        重新加载模型（用于模型更新后）
        
        Returns:
            是否成功重新加载
        """
        logger.info("🔄 重新加载ML模型...")
        self.model = None
        self.is_loaded = False
        return self._load_model()
