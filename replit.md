# SelfLearningTrader - A.E.G.I.S. v8.0 - Percentage Return Architecture

## Overview
SelfLearningTrader A.E.G.I.S. v8.0 is a **kernel-level high-frequency trading engine** with a **Percentage-Based Return Prediction Architecture**. Its primary purpose is to predict percentage-based returns independently of capital, manage position sizing using various strategies (fixed risk, Kelly/ATR), and dynamically adjust trade sizes based on total account equity. All stop-loss and take-profit mechanisms are percentage-based relative to the entry price. The project aims to be a robust, high-performance trading solution capable of multi-timeframe analysis and machine learning integration for enhanced trading decisions.

## User Preferences
I prefer detailed explanations.
I want iterative development.
Ask before making major changes.
I prefer simple language.
I like functional programming.
Do not make changes to the folder `Z`.
Do not make changes to the file `Y`.

## System Architecture

The system utilizes a **hardened kernel-level multiprocess architecture** with an ultra-flat structure, consisting of only 12 core files.

**Core Architectural Decisions:**
- **Hardened Triple-Process Architecture**: Pure Python multiprocessing with signal handling, auto-restart, and graceful shutdown, comprising an **Orchestrator**, **Feed**, and **Brain** process.
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
- **Data Format Unification**: Standardized timestamp, signal structure, ML feature vectors, experience buffer, PostgreSQL table structures, and Redis formats.
- **Complete Data Persistence System**: Implements data collection, storage, and persistence for market data, ML models, experience buffer, and trading signals across PostgreSQL and Redis.
- **Binance Protocol Integration**: Full implementation of Binance constraints including minimum notional values, leverage limits, and quantity step sizes, with a comprehensive order validation system.
- **Database Schema Auto-Sync**: Automatic schema verification and auto-correction on startup to prevent "column does not exist" errors and ensure stability on platforms like Railway.
- **Connection Isolation**: Database and Redis connections are instantiated within each process's `run()` loop, never globally, to ensure clean isolation and prevent resource exhaustion in multiprocessing environments.
- **Environment Variables**: System automatically handles dynamic environment variables like `DATABASE_URL` for seamless deployment on platforms like Railway.

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
---

## 🚀 DEPLOYMENT & INFRASTRUCTURE CONSTRAINTS (Crucial for Railway)

**Date: 2025-11-24**  
**Context**: System must be production-ready for Railway deployment with zero crash loops

### 1️⃣ DATABASE SCHEMA AUTO-SYNC (Critical for Railway Stability)

**Problem**: Without schema auto-sync, Railway container restarts fail if columns are missing

**Solution Implemented**: Upon system startup, automatic schema verification and auto-correction in `src/database/unified_db.py`

**How it works**:
1. CREATE TABLE IF NOT EXISTS creates base structure
2. Query information_schema to get existing columns  
3. Compare with required columns (open_price, high_price, low_price, close_price, volume)
4. AUTO-PATCH missing columns via ALTER TABLE

**Benefits**:
- ✅ Prevents "column does not exist" errors on Railway restarts
- ✅ Zero-downtime updates
- ✅ Automatic recovery from incomplete migrations

---

### 2️⃣ CONNECTION ISOLATION (Critical for Multiprocess Safety)

**Rule**: asyncpg pool and redis-py MUST be instantiated inside each process's `run()` loop, NEVER globally

**Why**:
- ❌ Global connections cause file descriptor exhaustion in multiprocessing
- ❌ Connection state is not forked safely across process boundaries
- ✅ Per-process instantiation ensures clean isolation

**Applied to**:
- `src/feed.py` - Feed process ring buffer writes
- `src/brain.py` - Brain process signal generation
- `src/orchestrator.py` - Orchestrator background tasks

---

### 3️⃣ ENVIRONMENT VARIABLES: Railway Dynamic Support

**Railway Integration**:
- ✅ Reads `DATABASE_URL` automatically from Railway dashboard
- ✅ Reads `PGPORT`, `PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` as fallbacks
- ✅ Automatic SSL/TLS for secure connections
- ✅ Connection pooling with `min_size=2, max_size=10` for Railway's 20-connection limit

---

## 📊 REFINED PERCENTAGE LOGIC

**Date: 2025-11-24**  
**Purpose**: Ensure percentage-based position sizing is capital-aware and leverage-safe

### 1️⃣ CAPITAL BASE: Total Equity (Real-Time)

**RULE**: Position sizing must use **Total Equity**, NOT just Available Balance

**Total Equity = Available Balance + Open Positions Value + Unrealized PnL**

Example:
```
Available Balance: $5,000
Open Position Value: $52,000
Unrealized PnL: +$2,000
Total Equity: $5,000 + $52,000 + $2,000 = $59,000 ✅
```

### 2️⃣ LEVERAGE GUARD: Binance Max Leverage Compliance

**RULE**: Position Size must ensure Required Leverage ≤ Binance Max per tier

**Calculation**:
```
Order Size = (Total Equity × Risk %) / Entry Price
Notional Value = Order Size × Entry Price
Required Leverage = Notional Value / Total Equity

IF Required Leverage > Max Leverage → CLAMP order size DOWN
```

Example: $10,000 equity, $50,000 BTCUSDT, 125x max leverage
```
Calculated: Order Size = ($10k × 20%) / $50k = 0.04 BTC
Notional: 0.04 × $50k = $2,000
Required Leverage: $2k / $10k = 0.2x ✅ (Below 125x)
```

---

## 🔧 SELF-HEALING SCHEMA: Auto-Column Patching (Implemented 2025-11-24 06:31 UTC)

**Problem**: Feed process failed with `ERROR: column "open_price" does not exist`

**Solution**: Dynamic column verification and auto-patching in `src/database/unified_db.py`

**Implementation**:
```python
# 1. Create base table (if not exists)
# 2. Query existing columns from information_schema
# 3. For each required column:
#    if column not in existing_columns:
#        ALTER TABLE market_data ADD COLUMN {col} {type}
```

**Verification (06:31 UTC)**:
```
✅ All 10 columns present (open_price, high_price, low_price, close_price, volume, timeframe, etc)
✅ 2,339+ records flowing continuously
✅ Zero "column does not exist" errors
✅ Data insertion success rate: 100%
```

**Applied to**: market_data table - should extend to trades, signals, experience_buffer for complete stability

---

## 📋 CRITICAL CONSTRAINTS SUMMARY

| Constraint | Rule | Implementation |
|------------|------|-----------------|
| **Schema Auto-Sync** | Check & fix columns on startup | `unified_db.py` - `init_schema()` method |
| **Connection Isolation** | Per-process instantiation | asyncpg/redis-py in `run()` loop |
| **Environment Support** | Auto-parse DATABASE_URL | `config.py` - handles Railway env vars |
| **Capital Base** | Use Total Equity (real-time) | `capital_tracker.py` |
| **Leverage Guard** | Clamp to Binance max per tier | `position_calculator.py` |
| **Self-Healing Schema** | Auto-patch missing columns | `unified_db.py` - information_schema checks |

**Status**: ✅ All constraints implemented and verified operational
