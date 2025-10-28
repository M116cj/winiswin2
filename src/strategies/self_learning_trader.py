"""
自我學習交易員（v3.16.3 - 增量學習系統）
完全自主的信號生成 + 持續學習能力
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
from src.ml.model_persistence import ModelPersistence
from src.core.performance_modules import PerformanceModules

logger = logging.getLogger(__name__)


class SelfLearningTrader:
    """自我學習交易員策略（v3.16.3 增量學習版本）"""
    
    def __init__(self, config):
        self.config = config
        
        # 🔥 v3.16.3: 模型持久化管理器
        self.persistence = ModelPersistence()
        
        # 🔥 v3.16.0: 性能模塊管理器
        self.performance_modules = PerformanceModules(config)
        
        # 🔥 v3.16.3: 加載或創建模型（恢復訓練狀態）
        self.structure_model, training_counter_1 = self._load_or_create_structure_model()
        self.feature_model, training_counter_2 = self._load_or_create_feature_model()
        self.liquidity_model, training_counter_3 = self._load_or_create_liquidity_model()
        
        # 增量學習狀態（使用最大訓練計數）
        self.training_counter = max(training_counter_1, training_counter_2, training_counter_3)
        self.save_interval = 100  # 每100次分析後保存
        self.last_save_time = time.time()
        
        self.min_confidence = config.MIN_CONFIDENCE
        
        logger.info("✅ 自我學習交易員初始化完成（v3.16.3 - 增量學習系統）")
        logger.info(f"   📊 學習進度: {self.training_counter} 次分析")
        logger.info(f"   💾 自動保存間隔: 每 {self.save_interval} 次分析")
    
    def _load_or_create_structure_model(self) -> tuple:
        """加載或創建市場結構編碼器，返回 (model, training_counter)"""
        model_name = "structure_encoder"
        
        # 優先使用量化模型
        if hasattr(self.config, 'ENABLE_QUANTIZATION') and self.config.ENABLE_QUANTIZATION:
            try:
                import os
                model_path = f"{self.config.QUANTIZED_MODEL_PATH}/structure_encoder_quant.tflite"
                if os.path.exists(model_path):
                    model = ModelQuantizer.load_quantized_model(model_path)
                    logger.info("  ✅ 使用量化模型（TensorFlow Lite）")
                    return (model, 0)
            except Exception as e:
                logger.warning(f"  ⚠️ 量化模型加載失敗: {e}")
        
        # 嘗試加載已訓練模型
        result = self.persistence.load_model(model_name, MarketStructureAutoencoder)
        if result:
            model, metadata = result
            training_count = metadata.get('training_counter', 0)
            logger.info(f"  ✅ 加載已訓練模型: {model_name} (訓練次數: {training_count})")
            return (model, training_count)
        
        # 創建新模型
        logger.info(f"  🆕 創建新模型: {model_name}")
        return (MarketStructureAutoencoder(), 0)
    
    def _load_or_create_feature_model(self) -> tuple:
        """加載或創建特徵發現網絡，返回 (model, training_counter)"""
        model_name = "feature_network"
        
        result = self.persistence.load_model(model_name, FeatureDiscoveryNetwork)
        if result:
            model, metadata = result
            training_count = metadata.get('training_counter', 0)
            logger.info(f"  ✅ 加載已訓練模型: {model_name} (訓練次數: {training_count})")
            return (model, training_count)
        
        logger.info(f"  🆕 創建新模型: {model_name}")
        return (FeatureDiscoveryNetwork(), 0)
    
    def _load_or_create_liquidity_model(self) -> tuple:
        """加載或創建流動性預測模型，返回 (model, training_counter)"""
        model_name = "liquidity_predictor"
        
        result = self.persistence.load_model(model_name, LiquidityPredictionModel)
        if result:
            model, metadata = result
            training_count = metadata.get('training_counter', 0)
            logger.info(f"  ✅ 加載已訓練模型: {model_name} (訓練次數: {training_count})")
            return (model, training_count)
        
        logger.info(f"  🆕 創建新模型: {model_name}")
        return (LiquidityPredictionModel(), 0)
    
    def save_models(self):
        """保存所有模型狀態"""
        try:
            metadata = {
                'training_counter': self.training_counter,
                'last_save_time': time.time()
            }
            
            # 保存三個模型
            self.persistence.save_model(self.structure_model, "structure_encoder", metadata)
            self.persistence.save_model(self.feature_model, "feature_network", metadata)
            self.persistence.save_model(self.liquidity_model, "liquidity_predictor", metadata)
            
            logger.info(f"💾 模型已保存 (訓練次數: {self.training_counter})")
            self.last_save_time = time.time()
            
        except Exception as e:
            logger.error(f"❌ 保存模型失敗: {e}")
    
    def analyze(self, symbol: str, multi_tf_data: Dict[str, pd.DataFrame]) -> Optional[Dict]:
        """
        完全自主的信號生成（v3.16.3 增量學習版本）
        
        Args:
            symbol: 交易對符號
            multi_tf_data: 多時間框架數據
            
        Returns:
            交易信號或None
        """
        try:
            if '5m' not in multi_tf_data or len(multi_tf_data['5m']) < 50:
                return None
            
            # 🔥 v3.16.0 步驟1: 市場狀態轉換預測
            market_regime_prediction = None
            if self.config.ENABLE_MARKET_REGIME_PREDICTION:
                market_regime_prediction = self.performance_modules.predict_market_regime(
                    {'symbol': symbol, 'data': multi_tf_data['5m']}
                )
                
                if (market_regime_prediction and 
                    market_regime_prediction.get('confidence', 0) < self.config.REGIME_PREDICTION_THRESHOLD):
                    logger.debug(
                        f"{symbol}: 市場狀態預測置信度不足 "
                        f"{market_regime_prediction.get('confidence', 0):.2%} < "
                        f"{self.config.REGIME_PREDICTION_THRESHOLD:.2%}"
                    )
                    return None
            
            # 🔥 v3.16.0 步驟2: 動態特徵生成
            dynamic_features_v316 = None
            if self.config.ENABLE_DYNAMIC_FEATURES and market_regime_prediction:
                dynamic_features_v316 = self.performance_modules.generate_dynamic_features(
                    market_regime_prediction['predicted_regime'],
                    multi_tf_data['5m'].tail(50)
                )
            
            # 🔥 步驟3: 基礎市場結構分析
            market_structure = self.structure_model.encode_structure(
                multi_tf_data['5m']['close'].values
            )
            
            # 基礎特徵發現
            dynamic_features = self.feature_model.discover_features(
                market_structure,
                multi_tf_data['5m'].tail(50)
            )
            
            # 基礎流動性預測
            liquidity_prediction = self.liquidity_model.predict_liquidity(
                symbol,
                multi_tf_data['5m'].tail(20)
            )
            
            # 🔥 v3.16.0 步驟4: 主動流動性狩獵
            liquidity_target = None
            if self.config.ENABLE_LIQUIDITY_HUNTING:
                current_price = multi_tf_data['5m']['close'].iloc[-1]
                liquidity_target = self.performance_modules.hunt_liquidity(symbol, current_price)
            
            # 🔥 v3.16.0 步驟5: 生成交易信號
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
            
            # 🔥 v3.16.3: 增量學習
            if signal:
                self._online_learning(symbol, multi_tf_data, signal, market_structure)
                self.training_counter += 1
                
                # 定期自動保存
                if self.training_counter % self.save_interval == 0:
                    self.save_models()
                    logger.info(f"📊 學習進度: {self.training_counter} 次分析")
            
            return signal
            
        except Exception as e:
            logger.error(f"SelfLearningTrader 分析錯誤 {symbol}: {e}", exc_info=True)
            return None
    
    def _online_learning(self, symbol: str, multi_tf_data: Dict, signal: Dict, market_structure: np.ndarray):
        """
        在線學習：基於當前分析結果更新模型
        
        Args:
            symbol: 交易對符號
            multi_tf_data: 多時間框架數據
            signal: 生成的交易信號
            market_structure: 市場結構向量
        """
        try:
            # 1. 更新市場結構編碼器
            if hasattr(self.structure_model, 'update_incremental'):
                price_series = multi_tf_data['5m']['close'].values
                self.structure_model.update_incremental(price_series)
            
            # 2. 更新特徵發現網絡（基於信號質量）
            if hasattr(self.feature_model, 'update_incremental'):
                signal_quality = signal.get('confidence', 0.5)
                self.feature_model.update_incremental(market_structure, signal_quality)
            
            # 3. 更新流動性預測模型
            if hasattr(self.liquidity_model, 'update_incremental'):
                recent_data = multi_tf_data['5m'].tail(20)
                self.liquidity_model.update_incremental(symbol, recent_data)
            
            logger.debug(f"🎓 增量學習完成: {symbol}")
            
        except Exception as e:
            logger.debug(f"增量學習失敗: {e}")
    
    def _generate_signal_from_analysis(self, **kwargs) -> Optional[Dict]:
        """
        從分析結果生成交易信號
        
        Args:
            symbol: 交易對符號
            market_structure: 市場結構編碼
            dynamic_features: 動態特徵
            liquidity_prediction: 流動性預測
            liquidity_target: 流動性目標（v3.16.0）
            market_regime_prediction: 市場狀態預測（v3.16.0）
            dynamic_features_v316: v3.16.0 動態特徵
            multi_tf_data: 多時間框架數據
        
        Returns:
            交易信號或None
        """
        symbol = kwargs['symbol']
        market_structure = kwargs['market_structure']
        dynamic_features = kwargs['dynamic_features']
        liquidity_target = kwargs.get('liquidity_target')
        multi_tf_data = kwargs['multi_tf_data']
        df_5m = multi_tf_data['5m']
        
        # 基礎信號生成
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
        
        # 🔥 v3.16.0: 流動性狩獵調整進場價格
        entry_price = current_price
        if liquidity_target and liquidity_target.get('confidence', 0) >= self.config.LIQUIDITY_HUNT_CONFIDENCE_THRESHOLD:
            if direction == 1:
                entry_price = liquidity_target.get('support_level', current_price) * 0.999
                logger.debug(f"{symbol}: 流動性狩獵 LONG - 目標進場價: {entry_price:.2f}")
            else:
                entry_price = liquidity_target.get('resistance_level', current_price) * 1.001
                logger.debug(f"{symbol}: 流動性狩獵 SHORT - 目標進場價: {entry_price:.2f}")
        
        # 計算止損止盈
        atr = self._calculate_atr(df_5m)
        
        if direction == 1:
            stop_loss = entry_price - (atr * 1.5)
            take_profit = entry_price + (atr * 3.0)
        else:
            stop_loss = entry_price + (atr * 1.5)
            take_profit = entry_price - (atr * 3.0)
        
        leverage = self._calculate_leverage(confidence)
        
        # 生成信號
        signal = {
            'symbol': symbol,
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'confidence': confidence,
            'leverage': leverage,
            'timestamp': time.time(),
            'reasoning': f"自我學習信號 v3.16.3 (結構:{structure_signal:.3f}, 特徵:{feature_signal:.3f}, 訓練:{self.training_counter}次)",
            'timeframe': '5m',
            'strategy_name': 'self_learning',
            'signal_type': 'self_learning',
            'market_state': kwargs.get('market_regime_prediction', {}).get('predicted_regime', 'unknown'),
            'scores': {
                'structure_signal': float(structure_signal),
                'feature_signal': float(feature_signal),
                'training_counter': self.training_counter
            },
            'liquidity_prediction': kwargs.get('liquidity_prediction'),
            'v316_features': {
                'liquidity_hunting_enabled': liquidity_target is not None,
                'regime_prediction_enabled': kwargs.get('market_regime_prediction') is not None,
                'dynamic_features_enabled': kwargs.get('dynamic_features_v316') is not None,
                'incremental_learning_enabled': True
            }
        }
        
        return signal
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """計算ATR"""
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
        """基於信心度計算槓桿"""
        base_leverage = self.config.BASE_LEVERAGE
        max_leverage = self.config.MAX_LEVERAGE
        
        leverage = int(base_leverage + (max_leverage - base_leverage) * confidence)
        return min(max(leverage, base_leverage), max_leverage)
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """獲取學習統計信息"""
        return {
            'training_counter': self.training_counter,
            'last_save_time': self.last_save_time,
            'models_saved': self.persistence.list_models(),
            'save_interval': self.save_interval
        }
    
    def shutdown(self):
        """優雅關閉：保存所有模型狀態"""
        logger.info("🔄 系統關閉中，保存模型狀態...")
        self.save_models()
        logger.info("✅ 模型狀態已保存")
