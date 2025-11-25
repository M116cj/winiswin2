# SelfLearningTrader - A.E.G.I.S. v8.0 - Percentage Return Architecture

## Overview
SelfLearningTrader A.E.G.I.S. v8.0 is a **kernel-level high-frequency trading engine** designed for **Percentage-Based Return Prediction**. Its core purpose is to predict percentage returns independently of capital, manage position sizing using various strategies (fixed risk, Kelly/ATR), and dynamically adjust trade sizes based on total account equity. All stop-loss and take-profit mechanisms are percentage-based relative to the entry price. The project aims to provide a robust, high-performance trading solution capable of multi-timeframe analysis and machine learning integration for enhanced trading decisions. This architecture accounts for trading costs (commissions) to prevent models from being misled by micro-profits.

## User Preferences
I prefer detailed explanations.
I want iterative development.
Ask before making major changes.
I prefer simple language.
I like functional programming.
Language: 繁體中文 (Traditional Chinese)
Do not make changes to the folder `Z`.
Do not make changes to the file `Y`.

## System Architecture

The system utilizes a **hardened kernel-level multiprocess architecture** with an ultra-flat structure and 10 optimized core database tables.

**Core Architectural Decisions:**
- **Hardened Triple-Process Architecture**: Pure Python multiprocessing with signal handling, auto-restart, and graceful shutdown.
- **Keep-Alive Watchdog Loop**: Main process monitors core processes, triggering container restarts on failure.
- **Shared Memory Ring Buffer**: LMAX Disruptor pattern for zero-lock, single-writer/single-reader IPC.
- **Monolith-Lite Design**: Maintains a lean codebase for simplicity.
- **Event-Driven**: Utilizes an `EventBus` for zero-coupling communication.
- **High-Performance Components**: Integrates `uvloop`, `Numba JIT`, object pooling, conflation buffer, and priority dispatcher.
- **Multi-Timeframe Trading System**: Implements multi-timeframe analysis (1D → 1H → 15m → 5m/1m).
- **ML Integration with Complete Feature Tracking**:
    - 12 ML Features: confidence, fvg, liquidity, rsi, atr, macd, bb_width, position_size_pct, entry_price, close_price, pnl, reward_score.
    - Features are extracted at signal generation and persisted through `virtual_positions` → `virtual_trades`.
- **Percentage Return + Position Sizing Architecture**: ML predicts percentage returns, with a dedicated position sizing layer managing order amounts.
- **Data Format Unification**: Standardized timestamp, signal structure, and ML feature vectors across PostgreSQL and Redis.
- **Complete Data Persistence**: Market data, ML models, experience buffer, signals, virtual trades persisted across PostgreSQL and Redis.
- **Binance Protocol Integration**: Full implementation of Binance constraints and order validation.
- **Database Schema Auto-Sync**: Automatic schema verification and auto-correction.
- **Connection Isolation**: DB/Redis connections are managed within process loops, never globally.
- **Cross-Process State Management**: PostgreSQL-backed state for virtual positions.
- **PostgreSQL-Driven ML Training**: ML models are trained directly from the `virtual_trades` table.
- **Commission Tracking**: All trades track Binance commission (0.2% round trip) for accurate ML training and net PnL calculation.
- **Time Precision**: `entry_at`/`exit_at` timestamps enable funding rate and duration calculations.

**Database Tables (10 optimized tables):**
1. `signals`: Trading signals with confidence and patterns, including 7 dedicated feature columns for fast queries.
2. `market_data`: OHLCV data with a composite index (`symbol`, `timeframe`, `timestamp`).
3. `virtual_trades`: Completed virtual trades with commission and time tracking (29 columns).
4. `virtual_positions`: Active/closed virtual positions with feature snapshots.
5. `trades`: Real Binance trades with commission tracking.
6. `ml_models`: Trained ML models.
7. `experience_buffer`: ML training data.
8. `account_state`: Account state snapshots.

## External Dependencies

- **Binance API**: Used for live trading, order execution, and market data retrieval.
- **WebSockets**: Provides real-time tick data ingestion.
- **PostgreSQL**: Serves as the primary database for market data, ML models, signals, and virtual trades, including commission tracking.
- **Redis**: Utilized for market data caching (1-hour TTL) and storage of the latest OHLCV data.