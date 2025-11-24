# SelfLearningTrader - A.E.G.I.S. v8.0 - Percentage Return Architecture

## Overview
SelfLearningTrader A.E.G.I.S. v8.0 is a **kernel-level high-frequency trading engine** with a **Percentage-Based Return Prediction Architecture**. The project's core purpose is to predict percentage-based returns without capital awareness, manage position sizing independently using various strategies (fixed risk, Kelly/ATR), and dynamically adjust trade sizes based on total account equity. All stop-loss and take-profit mechanisms are percentage-based relative to entry price.

## User Preferences
I prefer detailed explanations.
I want iterative development.
Ask before making major changes.
I prefer simple language.
I like functional programming.
Do not make changes to the folder `Z`.
Do not make changes to the file `Y`.

## System Architecture

The system employs a **hardened kernel-level multiprocess architecture** with an ultra-flat structure, comprising only 12 core files.

**Core Architectural Decisions:**
- **Hardened Triple-Process Architecture**: Pure Python multiprocessing with signal handling, auto-restart, and graceful shutdown, consisting of an **Orchestrator**, **Feed**, and **Brain** process.
- **Keep-Alive Watchdog Loop**: Main process monitors core processes, triggering container restarts on failure.
- **Shared Memory Ring Buffer**: Implements the LMAX Disruptor pattern for zero-lock, single-writer/single-reader IPC with microsecond latency, including overrun protection and data sanitization.
- **Monolith-Lite Design**: Maintains a lean codebase for simplicity.
- **Event-Driven**: Utilizes an `EventBus` for zero-coupling communication.
- **High-Performance Components**: Integrates `uvloop`, `Numba JIT`, object pooling, a conflation buffer, and a priority dispatcher.
- **Multi-Timeframe Trading System**: Implements multi-timeframe analysis (1D → 1H → 15m → 5m/1m) for trend confirmation, precise entries, confidence-weighted signals, and dynamic position sizing.
- **ML Integration**: Includes a module for training ML models with virtual data, comprehensive validation, and bias detection.
- **Percentage Return + Position Sizing Architecture**:
    1.  **ML Model Output**: Predicts percentage return (e.g., +5%) without capital awareness.
    2.  **Position Sizing Layer**: Independently calculates order amounts using either fixed risk percentage or an advanced Kelly/ATR/Confidence formula.
    3.  **Capital Awareness**: Tracks total equity (Available Balance + Open Positions Value + Unrealized PnL) to automatically adjust order amounts.
    4.  **Percentage-Based SL/TP**: Stop-loss and take-profit are defined as percentages relative to the entry price.
- **Data Format Unification**: Standardized timestamp (BIGINT milliseconds), signal structure (full features), ML feature vectors, experience buffer, PostgreSQL table structures, and Redis formats.
- **Complete Data Persistence System**: Implements data collection, storage, and persistence for market data, ML models, experience buffer, and trading signals across PostgreSQL and Redis.
- **Binance Protocol Integration**: Full implementation of Binance constraints including minimum notional values, leverage limits (tiered based on notional value), and quantity step sizes. Includes a comprehensive order validation system with tolerance.

**UI/UX Decisions:**
- The architecture prioritizes backend performance and a lean, functional core, without an explicit UI/UX.

**Feature Specifications:**
- **Multi-Symbol Support**: Dynamic discovery of active Binance Futures pairs, scalable to 300+ symbols.
- **Risk Management**: Integrated risk validation, order execution, thread-safe state management, and an "Elite 3-Position Portfolio Rotation" feature.
- **Production-Grade Logging**: Implemented with a `WARNING` level root logger, contextual error wrappers, and a system heartbeat.
- **Data Firewall**: Comprehensive validation functions in the `Feed` process to ensure data integrity and prevent "poison pills" with dual-layer validation.

## External Dependencies

- **Binance API**: Used for live trading, order execution, and market data.
- **WebSockets**: Utilized for real-time tick ingestion from exchanges (e.g., Binance combined streams).
- **PostgreSQL**: Used for persistent storage of market data, ML models, experience buffer, and signals.
- **Redis**: Used for fast caching of market data (1hr TTL) and storing the latest OHLCV.