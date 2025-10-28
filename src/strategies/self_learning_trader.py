"""
自我学习交易员（核心策略）
完全自主的信号生成，无需预定义规则
"""

import logging
import numpy as np
import pandas as pd
import time
from typing import Optional, Dict, Any

from src.ml.market_structure_autoencoder import MarketStructureAutoencoder
from src.ml.feature_discovery_network import FeatureDiscoveryNetwork
from src.ml.liquidity_prediction_model import LiquidityPredictionModel
from src.ml.model_quantizer import ModelQuantizer
from src.core.performance_modules import PerformanceModules

logger = logging.getLogger(__name__)


class SelfLearningTrader:
    """自我学习交易员策略"""
    
    def __init__(self, config):
        self.config = config
        
        # 🔥 v3.16.0: 性能模块管理器
        self.performance_modules = PerformanceModules(config)
        
        # 优化1：使用量化模型（如果启用）
        self.quantization_enabled = False
        if hasattr(config, 'ENABLE_QUANTIZATION') and config.ENABLE_QUANTIZATION:
            try:
                import os
                model_path = f"{config.QUANTIZED_MODEL_PATH}/structure_encoder_quant.tflite"
                if os.path.exists(model_path):
                    self.structure_model = ModelQuantizer.load_quantized_model(model_path)
                    self.quantization_enabled = True
                    logger.info("✅ 使用量化模型（TensorFlow Lite）")
                else:
                    logger.warning(f"⚠️ 量化模型文件不存在: {model_path}，使用原始模型")
                    self.structure_model = MarketStructureAutoencoder()
            except Exception as e:
                logger.warning(f"⚠️ 量化模型加载失败，使用原始模型: {e}")
                self.structure_model = MarketStructureAutoencoder()
        else:
            self.structure_model = MarketStructureAutoencoder()
        
        self.feature_model = FeatureDiscoveryNetwork()
        self.liquidity_model = LiquidityPredictionModel()
        
        self.min_confidence = config.MIN_CONFIDENCE
        
        logger.info("✅ 自我学习交易员初始化完成（v3.16.0 + 性能模块）")
    
    def analyze(self, symbol: str, multi_tf_data: Dict[str, pd.DataFrame]) -> Optional[Dict]:
        """
        完全自主的信号生成（v3.16.0 增强版）
        
        Args:
            symbol: 交易对符号
            multi_tf_data: 多时间框架数据
            
        Returns:
            交易信号或None
        """
        try:
            if '5m' not in multi_tf_data or len(multi_tf_data['5m']) < 50:
                return None
            
            # 🔥 v3.16.0 步骤1: 市场状态转换预测
            market_regime_prediction = None
            if self.config.ENABLE_MARKET_REGIME_PREDICTION:
                market_regime_prediction = self.performance_modules.predict_market_regime(
                    {'symbol': symbol, 'data': multi_tf_data['5m']}
                )
                
                # 只在高概率转换时交易
                if (market_regime_prediction and 
                    market_regime_prediction.get('confidence', 0) < self.config.REGIME_PREDICTION_THRESHOLD):
                    logger.debug(
                        f"{symbol}: 市场状态预测置信度不足 "
                        f"{market_regime_prediction.get('confidence', 0):.2%} < "
                        f"{self.config.REGIME_PREDICTION_THRESHOLD:.2%}"
                    )
                    return None
            
            # 🔥 v3.16.0 步骤2: 动态特征生成
            dynamic_features_v316 = None
            if self.config.ENABLE_DYNAMIC_FEATURES and market_regime_prediction:
                dynamic_features_v316 = self.performance_modules.generate_dynamic_features(
                    market_regime_prediction['predicted_regime'],
                    multi_tf_data['5m'].tail(50)
                )
            
            # 🔥 步骤3: 基础市场结构分析（原有功能）
            market_structure = self.structure_model.encode_structure(
                multi_tf_data['5m']['close'].values
            )
            
            # 基础特征发现（原有功能）
            dynamic_features = self.feature_model.discover_features(
                market_structure,
                multi_tf_data['5m'].tail(50)
            )
            
            # 基础流动性预测（原有功能）
            liquidity_prediction = self.liquidity_model.predict_liquidity(
                symbol,
                multi_tf_data['5m'].tail(20)
            )
            
            # 🔥 v3.16.0 步骤4: 主动流动性狩猎
            liquidity_target = None
            if self.config.ENABLE_LIQUIDITY_HUNTING:
                current_price = multi_tf_data['5m']['close'].iloc[-1]
                liquidity_target = self.performance_modules.hunt_liquidity(symbol, current_price)
            
            # 🔥 v3.16.0 步骤5: 生成交易信号（集成所有分析结果）
            signal = self._generate_signal_from_analysis(
                symbol=symbol,
                market_structure=market_structure,
                dynamic_features=dynamic_features,
                liquidity_prediction=liquidity_prediction,
                liquidity_target=liquidity_target,
                market_regime_prediction=market_regime_prediction,
                dynamic_features_v316=dynamic_features_v316,
                multi_tf_data=multi_tf_data
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"SelfLearningTrader 分析错误 {symbol}: {e}")
            return None
    
    def _generate_signal_from_analysis(self, **kwargs) -> Optional[Dict]:
        """
        从分析结果生成交易信号（v3.16.0 增强版）
        
        Args:
            symbol: 交易对符号
            market_structure: 市场结构编码
            dynamic_features: 动态特征
            liquidity_prediction: 流动性预测
            liquidity_target: 流动性目标（v3.16.0）
            market_regime_prediction: 市场状态预测（v3.16.0）
            dynamic_features_v316: v3.16.0 动态特征
            multi_tf_data: 多时间框架数据
        
        Returns:
            交易信号或None
        """
        symbol = kwargs['symbol']
        market_structure = kwargs['market_structure']
        dynamic_features = kwargs['dynamic_features']
        liquidity_target = kwargs.get('liquidity_target')
        multi_tf_data = kwargs['multi_tf_data']
        df_5m = multi_tf_data['5m']
        
        # 基础信号生成
        structure_signal = np.mean(market_structure[:8])
        feature_signal = np.mean(dynamic_features[:16])
        
        combined_signal = (structure_signal + feature_signal) / 2
        
        if abs(combined_signal) < 0.1:
            return None
        
        direction = 1 if combined_signal > 0 else -1
        confidence = min(abs(combined_signal), 1.0)
        
        if confidence < self.min_confidence:
            return None
        
        current_price = float(df_5m['close'].iloc[-1])
        
        # 🔥 v3.16.0: 流动性狩猎调整进场价格
        entry_price = current_price
        if liquidity_target and liquidity_target.get('confidence', 0) >= self.config.LIQUIDITY_HUNT_CONFIDENCE_THRESHOLD:
            if direction == 1:  # LONG
                # 在支撑位附近等待进场（稍低于当前价格）
                entry_price = liquidity_target.get('support_level', current_price) * 0.999
                logger.debug(f"{symbol}: 流动性狩猎 LONG - 目标进场价: {entry_price:.2f}")
            else:  # SHORT
                # 在阻力位附近等待进场（稍高于当前价格）
                entry_price = liquidity_target.get('resistance_level', current_price) * 1.001
                logger.debug(f"{symbol}: 流动性狩猎 SHORT - 目标进场价: {entry_price:.2f}")
        
        # 计算止损止盈
        atr = self._calculate_atr(df_5m)
        
        if direction == 1:
            stop_loss = entry_price - (atr * 1.5)
            take_profit = entry_price + (atr * 3.0)
        else:
            stop_loss = entry_price + (atr * 1.5)
            take_profit = entry_price - (atr * 3.0)
        
        leverage = self._calculate_leverage(confidence)
        
        # 生成信号
        signal = {
            'symbol': symbol,
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'confidence': confidence,
            'leverage': leverage,
            'timestamp': time.time(),
            'reasoning': f"自我学习信号 v3.16.0 (结构:{structure_signal:.3f}, 特征:{feature_signal:.3f})",
            'timeframe': '5m',
            'strategy_name': 'self_learning',
            'signal_type': 'self_learning',
            'market_state': kwargs.get('market_regime_prediction', {}).get('predicted_regime', 'unknown'),
            'scores': {
                'structure_signal': float(structure_signal),
                'feature_signal': float(feature_signal)
            },
            'liquidity_prediction': kwargs.get('liquidity_prediction'),
            'v316_features': {
                'liquidity_hunting_enabled': liquidity_target is not None,
                'regime_prediction_enabled': kwargs.get('market_regime_prediction') is not None,
                'dynamic_features_enabled': kwargs.get('dynamic_features_v316') is not None
            }
        }
        
        return signal
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算ATR"""
        if len(df) < period:
            high = df['high'].values if 'high' in df.columns else df['close'].values
            low = df['low'].values if 'low' in df.columns else df['close'].values
            return float(np.mean(high - low))
        
        high = df['high'].tail(period).values
        low = df['low'].tail(period).values
        close = df['close'].tail(period + 1).values
        
        tr = np.maximum(high - low, np.abs(high - close[:-1]))
        tr = np.maximum(tr, np.abs(low - close[:-1]))
        
        return float(np.mean(tr))
    
    def _calculate_leverage(self, confidence: float) -> int:
        """基于信心度计算杠杆"""
        base_leverage = self.config.BASE_LEVERAGE
        max_leverage = self.config.MAX_LEVERAGE
        
        leverage = int(base_leverage + (max_leverage - base_leverage) * confidence)
        return min(max(leverage, base_leverage), max_leverage)
