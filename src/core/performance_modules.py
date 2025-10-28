"""
性能模块统一管理器 (v3.16.0)
职责：统一管理所有性能优化模块，提供 fallback 机制
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# 尝试导入所有性能模块
try:
    from src.core.market_regime_predictor import MarketRegimePredictor
    MARKET_REGIME_PREDICTOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ MarketRegimePredictor 未可用: {e}")
    MARKET_REGIME_PREDICTOR_AVAILABLE = False

try:
    from src.core.dynamic_feature_generator import DynamicFeatureGenerator
    DYNAMIC_FEATURE_GENERATOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ DynamicFeatureGenerator 未可用: {e}")
    DYNAMIC_FEATURE_GENERATOR_AVAILABLE = False

try:
    from src.core.liquidity_hunter import LiquidityHunter
    LIQUIDITY_HUNTER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ LiquidityHunter 未可用: {e}")
    LIQUIDITY_HUNTER_AVAILABLE = False


class PerformanceModules:
    """性能模块统一管理器"""
    
    def __init__(self, config):
        """
        初始化性能模块管理器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self._init_modules()
    
    def _init_modules(self):
        """初始化所有可用模块"""
        self.market_regime_predictor = None
        self.dynamic_feature_generator = None
        self.liquidity_hunter = None
        
        # 🔥 v3.16.0: 市场状态转换预测器
        if self.config.ENABLE_MARKET_REGIME_PREDICTION and MARKET_REGIME_PREDICTOR_AVAILABLE:
            try:
                self.market_regime_predictor = MarketRegimePredictor(self.config)
                logger.info("✅ 市场状态转换预测器已启用")
            except Exception as e:
                logger.error(f"❌ 市场状态预测器初始化失败: {e}")
        else:
            if self.config.ENABLE_MARKET_REGIME_PREDICTION:
                logger.warning("⚠️ 市场状态预测器被禁用（配置或依赖不可用）")
        
        # 🔥 v3.16.0: 动态特征生成器
        if self.config.ENABLE_DYNAMIC_FEATURES and DYNAMIC_FEATURE_GENERATOR_AVAILABLE:
            try:
                self.dynamic_feature_generator = DynamicFeatureGenerator(self.config)
                logger.info("✅ 动态特征生成器已启用")
            except Exception as e:
                logger.error(f"❌ 动态特征生成器初始化失败: {e}")
        else:
            if self.config.ENABLE_DYNAMIC_FEATURES:
                logger.warning("⚠️ 动态特征生成器被禁用（配置或依赖不可用）")
        
        # 🔥 v3.16.0: 主动流动性狩猎器
        if self.config.ENABLE_LIQUIDITY_HUNTING and LIQUIDITY_HUNTER_AVAILABLE:
            try:
                self.liquidity_hunter = LiquidityHunter(self.config)
                logger.info("✅ 主动流动性狩猎器已启用")
            except Exception as e:
                logger.error(f"❌ 流动性狩猎器初始化失败: {e}")
        else:
            if self.config.ENABLE_LIQUIDITY_HUNTING:
                logger.warning("⚠️ 流动性狩猎器被禁用（配置或依赖不可用）")
    
    def predict_market_regime(self, current_data: Dict) -> Optional[Dict]:
        """
        预测市场状态转换
        
        Args:
            current_data: 当前市场数据
        
        Returns:
            Optional[Dict]: 预测结果，如果功能未启用则返回 None
        """
        if self.market_regime_predictor:
            try:
                return self.market_regime_predictor.predict(current_data)
            except Exception as e:
                logger.warning(f"市场状态预测失败: {e}")
        return None
    
    def generate_dynamic_features(self, market_regime: str, recent_data: Any) -> Optional[Dict]:
        """
        生成动态特征
        
        Args:
            market_regime: 市场状态
            recent_data: 最近的市场数据
        
        Returns:
            Optional[Dict]: 动态特征，如果功能未启用则返回 None
        """
        if self.dynamic_feature_generator:
            try:
                return self.dynamic_feature_generator.generate(market_regime, recent_data)
            except Exception as e:
                logger.warning(f"动态特征生成失败: {e}")
        return None
    
    def hunt_liquidity(self, symbol: str, current_price: float) -> Optional[Dict]:
        """
        狩猎流动性
        
        Args:
            symbol: 交易对符号
            current_price: 当前价格
        
        Returns:
            Optional[Dict]: 流动性目标，如果功能未启用则返回 None
        """
        if self.liquidity_hunter:
            try:
                return self.liquidity_hunter.hunt(symbol, current_price)
            except Exception as e:
                logger.warning(f"流动性狩猎失败: {e}")
        return None
