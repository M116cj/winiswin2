"""
🛡️ AEGIS Drift Detector - Model Stability Monitoring
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Detect model drift and feature importance changes
Design: Monitors feature importance after each training interval
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Monitors LightGBM model for concept drift and feature importance changes
    
    Alerts on:
    - liquidity_grab dropping out of Top 5 features (CRITICAL)
    - Significant changes in feature importance distribution
    - Model performance degradation indicators
    """
    
    def __init__(self, check_interval: int = 50):
        """
        Args:
            check_interval: Check drift every N trades (default: 50)
        """
        self.check_interval = check_interval
        self.last_feature_importance = {}
        self.drift_alerts = []
        self.last_check_trade = 0
        
        # Priority features that MUST stay in top 5
        self.critical_features = ['liquidity_grab', 'confidence_ensemble']
        
        # Expected feature importance ranking (baseline)
        self.expected_ranking = {
            'liquidity_grab': 1,           # Highest priority
            'confidence_ensemble': 2,
            'market_structure': 3,
            'fvg_size_atr': 4,
            'momentum_atr': 5,
            'rsi_14': 6,
            'ob_proximity': 7,
            'fvg_proximity': 8,
            'order_blocks_count': 9,
            'institutional_candle': 10,
            'atr_normalized_volume': 11,
            'time_to_next_level': 12,
        }
        
        logger.info(f"✅ DriftDetector initialized (check every {check_interval} trades)")
    
    def check_drift(
        self,
        current_trade_count: int,
        model_feature_importance: Optional[Dict] = None
    ) -> Dict:
        """
        Check for model drift
        
        Args:
            current_trade_count: Total completed trades
            model_feature_importance: Feature importance dict from LightGBM
        
        Returns: {
            'has_drift': bool,
            'severity': 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE',
            'alerts': [str],
            'feature_ranking': Dict
        }
        """
        result = {
            'has_drift': False,
            'severity': 'NONE',
            'alerts': [],
            'feature_ranking': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Check if it's time to inspect
        if current_trade_count - self.last_check_trade < self.check_interval:
            return result
        
        self.last_check_trade = current_trade_count
        
        # If no feature importance data, can't detect drift
        if not model_feature_importance:
            logger.warning("⚠️ No feature importance data available for drift detection")
            return result
        
        # Rank features by importance
        ranked = self._rank_features(model_feature_importance)
        result['feature_ranking'] = ranked
        
        # Check critical features
        critical_alerts = self._check_critical_features(ranked)
        if critical_alerts:
            result['alerts'].extend(critical_alerts)
            result['has_drift'] = True
            result['severity'] = 'CRITICAL'
        
        # Check for significant importance changes
        change_alerts = self._check_importance_changes(model_feature_importance)
        if change_alerts:
            result['alerts'].extend(change_alerts)
            if result['severity'] != 'CRITICAL':
                result['severity'] = 'HIGH'
                result['has_drift'] = True
        
        # Log results
        if result['has_drift']:
            logger.warning(f"⚠️ DRIFT DETECTED ({result['severity']}): {result['alerts']}")
            self.drift_alerts.append({
                'trade_count': current_trade_count,
                'severity': result['severity'],
                'alerts': result['alerts']
            })
        else:
            logger.info(f"✅ Model drift check passed (trade #{current_trade_count})")
        
        # Store for next comparison
        self.last_feature_importance = model_feature_importance.copy()
        
        return result
    
    def _rank_features(self, importance: Dict) -> Dict:
        """
        Rank features by importance
        
        Returns: {feature_name: rank (1=highest)}
        """
        sorted_features = sorted(
            importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            feature: rank + 1
            for rank, (feature, _) in enumerate(sorted_features)
        }
    
    def _check_critical_features(self, ranking: Dict) -> List[str]:
        """Check if critical features are still in Top 5"""
        alerts = []
        
        for critical_feat in self.critical_features:
            rank = ranking.get(critical_feat, 99)
            
            if rank > 5:
                alert = f"🔴 CRITICAL: '{critical_feat}' dropped out of Top 5 (rank: {rank})"
                logger.error(alert)
                alerts.append(alert)
            elif rank > 3:
                alert = f"⚠️ WARNING: '{critical_feat}' slipped in ranking (rank: {rank})"
                logger.warning(alert)
                alerts.append(alert)
        
        return alerts
    
    def _check_importance_changes(self, current_importance: Dict) -> List[str]:
        """Check for significant changes in feature importance"""
        alerts = []
        
        if not self.last_feature_importance:
            # First check, no previous data
            return alerts
        
        # Calculate importance change for each feature
        for feature, current_val in current_importance.items():
            last_val = self.last_feature_importance.get(feature, 0)
            
            if last_val == 0:
                continue
            
            # Calculate percentage change
            pct_change = abs((current_val - last_val) / last_val) * 100
            
            # Alert on >30% change
            if pct_change > 30:
                alert = f"🟡 Feature '{feature}' importance changed {pct_change:.1f}% " \
                       f"({last_val:.4f} → {current_val:.4f})"
                logger.warning(alert)
                alerts.append(alert)
        
        return alerts
    
    def get_drift_history(self, limit: int = 10) -> List[Dict]:
        """Get recent drift alerts"""
        return self.drift_alerts[-limit:]
    
    def __repr__(self) -> str:
        severity = "NONE"
        if self.drift_alerts:
            severity = self.drift_alerts[-1]['severity']
        return f"DriftDetector(severity={severity} | {len(self.drift_alerts)} alerts)"


# Global singleton
_drift_detector: Optional[DriftDetector] = None


def get_drift_detector(check_interval: int = 50) -> DriftDetector:
    """Get or create global drift detector"""
    global _drift_detector
    if _drift_detector is None:
        _drift_detector = DriftDetector(check_interval)
    return _drift_detector
