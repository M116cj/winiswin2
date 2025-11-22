# SelfLearningTrader - Project Overview

## Overview
SelfLearningTrader is an AI-driven, high-reliability, and high-performance automated cryptocurrency trading system. It utilizes machine learning and advanced ICT/SMC strategies to make trading decisions, aiming for true AI-driven trading. The system is optimized for cloud deployment and features efficient data acquisition and cache utilization. A core principle is strict adherence to exchange API protocols to prevent issues like IP bans.

**Business Vision**: To provide a reliable, AI-driven automated trading solution for the cryptocurrency market.
**Market Potential**: Addresses the growing demand for advanced, reliable, and compliant automated trading systems in the volatile crypto market.
**Project Ambition**: Achieve 95%+ reliability for critical operations, ensure 100% Binance API compliance, and continuously optimize trading signal generation and execution through machine learning.

## User Preferences
I prefer iterative development with clear communication at each stage. Please ask before making major architectural changes or significant modifications to core logic. I prefer detailed explanations for complex decisions and changes.

## System Architecture

### UI/UX Decisions
The system primarily relies on clear, filtered logging and monitoring, optimized for cloud environments. Logging is streamlined to focus on critical business metrics and aggregated errors, significantly reducing noise.

### Technical Implementations

#### Unified Manager Architecture v5.0
This architecture follows the "Single Source of Truth" principle, unifying management across key layers:
-   **WebSocket Layer**: `UnifiedWebSocketFeed` (single heartbeat, Producer-Consumer).
-   **Configuration Layer**: `UnifiedConfigManager` (single entry point for environment variables).
-   **Database Layer**: `UnifiedDatabaseManager` (unified interface for `asyncpg` and Redis).

#### Other Implementations
-   **Lifecycle Management**: Includes `LifecycleManager` for graceful shutdown, `StartupManager` for crash tracking, and `Watchdog/Dead Man's Switch` for auto-restart, with Railway-optimized zero-downtime deployment.
-   **AI/ML Core**: Uses XGBoost and LightGBM models with a 12-feature ICT/SMC architecture (market structure, order blocks, liquidity grabs, fair value gaps). Models retrain automatically.
-   **Data Acquisition**: Employs a Producer-Consumer architecture with `asyncio.Queue` and background workers, featuring a WebSocket-only K-line mode to eliminate REST K-line calls and robust reconnection logic.
-   **Risk Management**: Implements dynamic leverage, intelligent position sizing via Kelly Criterion, dynamic stop-loss/take-profit, and smart exit strategies.
-   **Order Management**: `BinanceClient`, `OrderValidator`, and `SmartOrderManager` handle order precision, nominal values, and API error handling.
-   **Caching**: A three-tier architecture comprising L1 memory cache, optional L2 Redis for hot queries, and PostgreSQL as the source of truth, all asynchronously safe.
-   **Database**: PostgreSQL serves as the unified data layer, utilizing `asyncpg` for asynchronous operations and connection pooling.
-   **Performance Stack**: Integrates `uvloop` for event loop acceleration, `orjson` for faster JSON serialization, and Redis caching.
-   **Configuration**: Flexible environment control and strategy tuning are managed via feature toggle switches.

### Feature Specifications

#### Dynamic Position Sizing with Kelly Criterion
Position sizing is dynamically adjusted based on trade confidence using a Kelly multiplier, with safety limits applied to account equity.

#### Real-time Notification System
A `NotificationService` provides fire-and-forget asynchronous notifications for trade events and daily summaries via Discord/Telegram, ensuring non-blocking, error-isolated, and rate-limited operation.

#### Database Optimization
Extensive PostgreSQL indexing significantly reduces query times.

#### Local-First, Zero-Polling Architecture
The `AccountStateCache` (in-memory singleton) is updated via WebSockets, eliminating periodic REST API calls for account data. This design reduces API calls, speeds up data access, and mitigates IP ban risks. Cache reconciliation mechanisms periodically verify data consistency against the REST API.

#### Event Loop Performance & Data Integrity
`uvloop` integration enhances event loop processing. A cache reconciliation mechanism detects and repairs data inconsistencies by comparing cache data with the REST API. Optimized logging via `SmartLogger` reduces debug noise and I/O blocking.

### System Design Choices

#### SMC-QUANT Sharded Engine
Transforms the system into a specialized M1/M5 SMC Scalper for 300+ pairs by implementing:
-   **Sharded Infrastructure**: `BinanceUniverse` discovers and caches trading pairs, `ShardFeed` combines streams, and `ClusterManager` orchestrates shards, buffers klines, and routes signals.
-   **Intelligence Layer**: `SMCEngine` detects SMC patterns (FVG, OB, LS, BOS) and calculates ATR. `FeatureEngineer` converts patterns and OHLCV into 12 numerical features for ML. `MLPredictor` uses LightGBM to predict trade confidence.
-   **Strategy & Risk Management**: `RiskManager` implements dynamic position sizing based on prediction confidence and enforces forced exits. `ICTScalper` routes signals and coordinates with `RiskManager` for order execution.

## External Dependencies
-   **Binance API**: For real-time market data (WebSocket streams) and order execution (REST API).
-   **PostgreSQL**: Primary database for all trading records and system states.
-   **XGBoost**: Machine learning library for predictive models.
-   **LightGBM**: Machine learning library for predictive models.
-   **Asyncpg**: Asynchronous PostgreSQL driver.
-   **Railway**: Recommended cloud deployment platform.
-   **NumPy/Pandas**: Used in the technical indicators engine and for vectorized data computations.
-   **Polars**: Used for high-speed data operations in feature engineering.
-   **Websockets library**: Python library for WebSocket communication.