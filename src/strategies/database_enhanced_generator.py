from src.utils.logger_factory import get_logger
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = get_logger(__name__)

class DatabaseEnhancedGenerator:
    """数据库增强的信号生成器（v3.20+ 包装类）"""
    
    def __init__(self, config=None, use_pure_ict: bool = True, enable_database: bool = False):
        self.use_pure_ict = use_pure_ict
        self.database_enabled = enable_database
        
        from src.strategies.rule_based_signal_generator import RuleBasedSignalGenerator
        self.base_generator = RuleBasedSignalGenerator(config, use_pure_ict)
        
        if enable_database:
            from src.core.trading_database import TradingDatabase
            self.db = TradingDatabase(enabled=True)
            logger.info("✅ 数据库增强系统已启用")
        else:
            self.db = None
            logger.info("📦 使用基础信号生成器（数据库增强未启用）")
    
    def generate_signal(self, symbol: str, klines_data: Dict, market_structure: str = "NEUTRAL"):
        """生成信号（带可选数据库增强）"""
        try:
            signal, confidence, win_prob = self.base_generator.generate_signal(
                symbol, klines_data, market_structure
            )
            
            if self.database_enabled and self.db:
                try:
                    features = self._extract_features_from_signal(signal, confidence, win_prob)
                    
                    self.db.record_feature_analysis(
                        symbol=symbol,
                        features=features,
                        confidence=confidence,
                        win_probability=win_prob / 100 if win_prob > 1 else win_prob,
                        has_signal=signal is not None,
                        signal_direction=signal.get('direction') if signal else None
                    )
                    
                    if signal:
                        enhanced_confidence, enhanced_win_prob = self._apply_database_enhancement(
                            symbol, confidence, win_prob, features
                        )
                        
                        logger.debug(f"📊 {symbol}: 增强前={confidence:.1f}/{win_prob:.1f}% → "
                                   f"增强后={enhanced_confidence:.1f}/{enhanced_win_prob:.1f}%")
                        
                        return signal, enhanced_confidence, enhanced_win_prob
                        
                except Exception as e:
                    logger.warning(f"⚠️ 数据库增强失败 {symbol}: {e}，使用基础值")
            
            return signal, confidence, win_prob
            
        except Exception as e:
            logger.error(f"❌ 信号生成失败 {symbol}: {e}")
            return None, 0.0, 0.0
    
    def _extract_features_from_signal(self, signal: Optional[Dict], confidence: float, 
                                     win_prob: float) -> Dict:
        """从信号提取特征"""
        if not signal:
            return {
                'confidence_score': confidence,
                'win_probability': win_prob,
                'market_structure': 0.0,
                'order_blocks_count': 0
            }
        
        return {
            'market_structure': signal.get('market_structure_score', 0.0),
            'order_blocks_count': len(signal.get('order_blocks', [])),
            'structure_integrity': signal.get('structure_integrity', 0.0),
            'liquidity_context': signal.get('liquidity_context', 0.0),
            'institutional_participation': signal.get('institutional_participation', 0.0),
            'timeframe_convergence': signal.get('timeframe_convergence', 0.0),
            'institutional_candle': 1 if signal.get('institutional_candle') else 0,
            'liquidity_grab': 1 if signal.get('liquidity_grab') else 0,
            'order_flow': signal.get('order_flow', 0.0),
            'fvg_count': len(signal.get('fvg', [])) if signal.get('fvg') else 0,
            'trend_alignment_enhanced': signal.get('trend_alignment', 0.0),
            'swing_high_distance': signal.get('swing_high_distance', 0.0),
            'confidence_score': confidence,
            'win_probability': win_prob
        }
    
    def _apply_database_enhancement(self, symbol: str, confidence: float, 
                                   win_prob: float, features: Dict) -> Tuple[float, float]:
        """应用数据库增强"""
        try:
            performance = self.db.get_symbol_performance(symbol, lookback_hours=24)
            
            if not performance:
                return confidence, win_prob
            
            success_rate = performance.get('success_rate', 0.5)
            
            historical_adjustment = (success_rate - 0.5) * 0.3
            enhanced_confidence = confidence * (1 + historical_adjustment)
            
            win_prob_decimal = win_prob / 100 if win_prob > 1 else win_prob
            enhanced_win_prob_decimal = win_prob_decimal + (success_rate - 0.5) * 0.2
            enhanced_win_prob_decimal = max(0.3, min(0.8, enhanced_win_prob_decimal))
            
            enhanced_confidence = max(0, min(100, enhanced_confidence))
            enhanced_win_prob = enhanced_win_prob_decimal * 100 if win_prob > 1 else enhanced_win_prob_decimal
            
            return enhanced_confidence, enhanced_win_prob
            
        except Exception as e:
            logger.warning(f"⚠️ 增强计算失败 {symbol}: {e}")
            return confidence, win_prob
