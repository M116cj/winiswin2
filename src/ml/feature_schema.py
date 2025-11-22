"""
📊 Feature Schema - The 12 ATR-Normalized Features
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Strict specification of the 12 ML features used by the A.E.G.I.S. system.
"""

from typing import Dict, List

# The 12 ATR-Normalized Features
FEATURE_SCHEMA = [
    {
        'index': 0,
        'name': 'market_structure',
        'description': 'Break of Structure direction (BOS/CHoCh)',
        'range': (-1, 0, 1),
        'type': 'discrete',
        'priority': 'HIGH'
    },
    {
        'index': 1,
        'name': 'order_blocks_count',
        'description': 'Order Block presence indicator',
        'range': (0, 1),
        'type': 'binary',
        'priority': 'HIGH'
    },
    {
        'index': 2,
        'name': 'institutional_candle',
        'description': 'Candle body × volume strength',
        'range': (0, 1),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 3,
        'name': 'liquidity_grab',
        'description': 'Liquidity Sweep detection ⭐ CRITICAL',
        'range': (0, 1),
        'type': 'binary',
        'priority': 'CRITICAL'
    },
    {
        'index': 4,
        'name': 'fvg_size_atr',
        'description': 'Fair Value Gap size normalized by ATR',
        'range': (0, float('inf')),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 5,
        'name': 'fvg_proximity',
        'description': 'Distance to FVG normalized by ATR',
        'range': (-1, 1),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 6,
        'name': 'ob_proximity',
        'description': 'Distance to Order Block normalized by ATR',
        'range': (0, 1),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 7,
        'name': 'atr_normalized_volume',
        'description': 'Current volume / Average volume',
        'range': (0, float('inf')),
        'type': 'continuous',
        'priority': 'LOW'
    },
    {
        'index': 8,
        'name': 'rsi_14',
        'description': 'Relative Strength Index (14 period)',
        'range': (0, 1),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 9,
        'name': 'momentum_atr',
        'description': 'Price momentum normalized by ATR',
        'range': (-1, 1),
        'type': 'continuous',
        'priority': 'MEDIUM'
    },
    {
        'index': 10,
        'name': 'time_to_next_level',
        'description': 'Distance to support/resistance level',
        'range': (0, 1),
        'type': 'continuous',
        'priority': 'LOW'
    },
    {
        'index': 11,
        'name': 'confidence_ensemble',
        'description': 'ML model confidence score',
        'range': (0, 1),
        'type': 'continuous',
        'priority': 'HIGH'
    },
]

# Convenience lookup
FEATURE_NAMES = [f['name'] for f in FEATURE_SCHEMA]
FEATURE_INDICES = {f['name']: f['index'] for f in FEATURE_SCHEMA}
CRITICAL_FEATURES = [f['name'] for f in FEATURE_SCHEMA if f['priority'] in ('CRITICAL', 'HIGH')]


def get_feature_names() -> List[str]:
    """Get list of all 12 feature names"""
    return FEATURE_NAMES


def get_feature_index(name: str) -> int:
    """Get index of a feature by name"""
    return FEATURE_INDICES.get(name, -1)


def validate_feature_vector(vector: Dict) -> bool:
    """Validate that a feature vector has all required fields"""
    return all(name in vector for name in FEATURE_NAMES)
