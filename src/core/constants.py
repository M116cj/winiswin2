"""
🎯 Constants & Configuration Enums
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Centralized configuration constants for the A.E.G.I.S. system.
"""

# Trading Configuration
KLINE_INTERVAL = "1m"
MAX_SYMBOLS = 300
SHARD_SIZE = 50  # Symbols per shard
MAX_LEVERAGE_TEACHER = 3.0
MAX_LEVERAGE_STUDENT = 10.0
TEACHER_PHASE_THRESHOLD = 50

# Feature Configuration
NUM_FEATURES = 12
ATR_PERIOD = 14
RSI_PERIOD = 14
MOMENTUM_PERIOD = 5

# Buffer & Performance
BATCH_FLUSH_INTERVAL = 0.1  # seconds
EXPERIENCE_REPLAY_SIZE = 5000
MICRO_BATCH_SIZE = 100

# WebSocket Configuration
WS_RECONNECT_DELAY_START = 5
WS_RECONNECT_DELAY_MAX = 300
WS_PING_INTERVAL = 20
WS_PING_TIMEOUT = 20

# Data Management
CACHE_MAX_AGE_MINUTES = 1
HISTORICAL_CANDLES_LIMIT = 1000
GAP_FILL_THRESHOLD_MS = 60000  # 1 minute

# Drift Detection
DRIFT_CHECK_INTERVAL = 50  # trades
IMPORTANCE_CHANGE_THRESHOLD = 0.30  # 30%
CRITICAL_FEATURES_MIN_RANK = 5

# Logger Configuration
LOG_LEVEL_PRODUCTION = "INFO"
LOG_LEVEL_DEVELOPMENT = "DEBUG"
