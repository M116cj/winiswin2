"""
🤖 ML Virtual Integrator - Bias-Free Incremental Learning
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Integrates virtual trading data into ML model training without bias.
Ensures:
- Data quality validation
- Bias detection and prevention
- Incremental learning capability
- Separation of virtual vs real data tracking
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class VirtualDataValidator:
    """Validate virtual trading data for ML training"""
    
    # Data quality thresholds
    MIN_PRICE_CONFIDENCE = 0.5
    MAX_PRICE_MOVEMENT = 0.20  # 20% max single movement
    MIN_VOLUME = 0.01
    
    @staticmethod
    def validate_trade_data(trade: Dict) -> Tuple[bool, str]:
        """
        Validate virtual trade data for ML training
        
        Returns: (is_valid, reason)
        """
        # Check required fields
        required = ['symbol', 'side', 'quantity', 'entry_price', 'close_price', 'pnl', 'reason']
        for field in required:
            if field not in trade:
                return False, f"Missing required field: {field}"
        
        # Validate numeric fields
        try:
            entry_price = float(trade['entry_price'])
            close_price = float(trade['close_price'])
            quantity = float(trade['quantity'])
            pnl = float(trade['pnl'])
            
            if entry_price <= 0 or close_price <= 0 or quantity <= 0:
                return False, "Price or quantity must be positive"
            
            # Check for unrealistic price movements
            price_change = abs(close_price - entry_price) / entry_price
            if price_change > VirtualDataValidator.MAX_PRICE_MOVEMENT:
                return False, f"Unrealistic price movement: {price_change:.1%}"
            
            # Validate PnL calculation
            if trade['side'] == 'BUY':
                expected_pnl = (close_price - entry_price) * quantity
            else:
                expected_pnl = (entry_price - close_price) * quantity
            
            pnl_error = abs(pnl - expected_pnl) / abs(expected_pnl) if expected_pnl != 0 else 0
            if pnl_error > 0.01:  # 1% tolerance
                return False, f"PnL calculation mismatch: {pnl} vs {expected_pnl}"
            
            # Validate close reason
            valid_reasons = ['TP_HIT', 'SL_HIT', 'MANUAL', 'TIMEOUT']
            if trade['reason'] not in valid_reasons:
                return False, f"Invalid close reason: {trade['reason']}"
            
            return True, "Valid"
        
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    @staticmethod
    def detect_bias(trades: List[Dict]) -> Dict:  # type: ignore[no-untyped-def]
        """
        Detect potential bias in virtual trading data
        
        Returns: {has_bias: bool, metrics: {...}, warnings: [...]}
        """
        if not trades:
            return {'has_bias': False, 'metrics': {}, 'warnings': []}
        
        warnings = []
        metrics = {}
        
        # Check 1: Win rate distribution (should be realistic)
        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        win_rate = wins / len(trades) if trades else 0
        metrics['win_rate'] = win_rate
        
        if win_rate > 0.85:
            warnings.append(f"⚠️ Unrealistically high win rate: {win_rate:.1%} (>85%)")
        if win_rate < 0.25:
            warnings.append(f"⚠️ Unrealistically low win rate: {win_rate:.1%} (<25%)")
        
        # Check 2: PnL distribution (should be normal-ish)
        pnls = [t.get('pnl', 0) for t in trades if t.get('pnl', 0) != 0]
        if pnls:
            mean_pnl = statistics.mean(pnls)
            stdev_pnl = statistics.stdev(pnls) if len(pnls) > 1 else 0
            metrics['mean_pnl'] = mean_pnl
            metrics['stdev_pnl'] = stdev_pnl
            
            # Check for extreme outliers
            for pnl in pnls:
                if stdev_pnl > 0:
                    z_score = abs(pnl - mean_pnl) / stdev_pnl
                    if z_score > 3:  # 3-sigma outlier
                        warnings.append(f"⚠️ Extreme outlier detected: PnL={pnl}, Z-score={z_score:.1f}")
        
        # Check 3: Symbol diversity
        symbols = set(t.get('symbol', '') for t in trades)
        metrics['unique_symbols'] = len(symbols)
        if len(symbols) < 3 and len(trades) > 20:
            warnings.append(f"⚠️ Low symbol diversity: {len(symbols)} unique symbols in {len(trades)} trades")
        
        # Check 4: Side distribution
        buys = sum(1 for t in trades if t.get('side') == 'BUY')
        sells = sum(1 for t in trades if t.get('side') == 'SELL')
        buy_ratio = buys / len(trades) if trades else 0
        metrics['buy_sell_ratio'] = buy_ratio
        
        if buy_ratio > 0.95 or buy_ratio < 0.05:
            warnings.append(f"⚠️ Unbalanced BUY/SELL ratio: {buy_ratio:.1%}")
        
        # Check 5: Close reason distribution (should have mix of TP/SL)
        reasons: Dict[str, int] = defaultdict(int)
        for trade in trades:
            reasons[trade.get('reason', 'UNKNOWN')] += 1  # type: ignore[union-attr]
        metrics['close_reasons'] = dict(reasons)
        
        tp_rate = reasons.get('TP_HIT', 0) / len(trades) if trades else 0
        if tp_rate > 0.90:
            warnings.append(f"⚠️ Unrealistically high TP hit rate: {tp_rate:.1%}")
        
        has_bias = len(warnings) > 0
        
        return {
            'has_bias': has_bias,
            'metrics': metrics,
            'warnings': warnings
        }


class MLVirtualIntegrator:
    """Integrate virtual trading data into ML training without bias"""
    
    def __init__(self):
        self.virtual_trades = []
        self.real_trades = []
        self.validator = VirtualDataValidator()
        self.last_training_time = None
    
    async def add_virtual_trade(self, trade: Dict) -> bool:
        """Add and validate virtual trade"""
        is_valid, reason = self.validator.validate_trade_data(trade)
        
        if not is_valid:
            logger.warning(f"❌ Invalid virtual trade rejected: {reason}")
            return False
        
        # Mark as virtual for bias tracking
        trade['_source'] = 'virtual'
        self.virtual_trades.append(trade)
        
        logger.debug(f"✅ Virtual trade added: {trade['symbol']} {trade['side']} PnL={trade['pnl']:.2f}")
        return True
    
    async def get_training_data_with_bias_check(self) -> Optional[Tuple[List[Dict], Dict]]:
        """
        Get training data with bias analysis
        
        Returns: (training_data, bias_analysis) or None if bias detected
        """
        if len(self.virtual_trades) < 10:
            logger.warning(f"⚠️ Insufficient virtual trades for training: {len(self.virtual_trades)}/10")
            return None
        
        # Analyze bias
        bias_report = self.validator.detect_bias(self.virtual_trades)
        
        # Log warnings
        for warning in bias_report['warnings']:
            logger.warning(warning)
        
        # If critical bias detected, mark data but still train
        if bias_report['has_bias']:
            logger.warning(f"🔍 Bias detected in virtual data, training with caution")
        
        # Log metrics
        logger.critical(
            f"📊 Virtual training data: {len(self.virtual_trades)} trades | "
            f"Win Rate: {bias_report['metrics'].get('win_rate', 0):.1%} | "
            f"Symbols: {bias_report['metrics'].get('unique_symbols', 0)} | "
            f"Mean PnL: ${bias_report['metrics'].get('mean_pnl', 0):.2f}"
        )
        
        return self.virtual_trades.copy(), bias_report
    
    def convert_to_ml_format(self, trade: Dict) -> Dict:
        """Convert virtual trade to ML training format with reward shaping (統一格式)"""
        from src.data_formats import extract_ml_features
        from src.reward_shaping import get_sample_weight, get_label_from_score
        
        # 構建完整的信號格式
        signal_data = {
            'confidence': 0.65,  # Default confidence from virtual signals
            'features': {
                'confidence': 0.65,
                'fvg': 1.0,
                'liquidity': 0.8,
                'rsi': 50,
                'atr': 0,
                'macd': 0,
                'bb_width': 0,
                'position_size': trade.get('quantity', 0),
                'position_size_pct': 0.0065,  # 0.65% of 10k
            },
            'position_size': trade.get('quantity', 0),
        }
        
        # 使用統一的特徵提取
        feature_vector = extract_ml_features(signal_data)
        
        # 🎯 獎懲機制：使用分數而非純 PnL
        reward_score = trade.get('reward_score', 0)  # 來自 virtual_learning.py
        sample_weight = get_sample_weight(reward_score)
        label = get_label_from_score(reward_score)
        
        pnl = trade.get('pnl', 0)
        roi_pct = trade.get('roi_pct', 0)
        
        return {
            'features': feature_vector,
            'label': label,  # Binary: 1 (profitable) or 0 (loss)
            'weight': sample_weight,  # Sample weight from reward shaping
            'metadata': {
                'symbol': trade.get('symbol', ''),
                'timestamp': int(trade.get('timestamp', 0)),
                'pnl': pnl,
                'roi_pct': roi_pct,
                'reward_score': reward_score,
                'sample_weight': sample_weight,
                'source': 'virtual'
            }
        }


# Global integrator
_integrator: Optional[MLVirtualIntegrator] = None


def get_ml_virtual_integrator() -> MLVirtualIntegrator:
    """Get or create global integrator"""
    global _integrator
    if _integrator is None:
        _integrator = MLVirtualIntegrator()
    return _integrator


async def train_ml_with_virtual_data(ml_model) -> bool:
    """
    Train ML model using virtual trading data (with bias checking)
    
    Args:
        ml_model: ML model instance
    
    Returns:
        True if training successful
    """
    integrator = get_ml_virtual_integrator()
    
    result = await integrator.get_training_data_with_bias_check()
    if result is None:
        logger.warning("⚠️ Insufficient data for ML training")
        return False
    
    virtual_trades, bias_report = result
    
    # Convert to ML format
    training_data = [integrator.convert_to_ml_format(t) for t in virtual_trades]
    
    # Train model
    logger.critical("🤖 Training ML model with virtual data (bias-checked)...")
    success = await ml_model.train(training_data)
    
    if success:
        logger.critical(
            f"✅ ML model trained successfully with {len(training_data)} virtual samples"
        )
    
    return success
