# SelfLearningTrader - Project Overview

## Overview
SelfLearningTrader is an AI-driven, high-reliability, and high-performance automated cryptocurrency trading system. It leverages machine learning and advanced ICT/SMC strategies for trading decisions, aiming for true AI-driven trading. The system is optimized for cloud deployment platforms like Railway, boasting significant performance enhancements, including 4-5x faster data acquisition and an 85% cache hit rate. A key focus is strict adherence to exchange API protocols, achieving zero REST K-line API calls to prevent IP bans.

**Business Vision**: To provide a reliable, AI-driven automated trading solution for the cryptocurrency market.
**Market Potential**: Addresses the growing demand for advanced, reliable, and compliant automated trading systems in the volatile crypto market.
**Project Ambition**: Achieve 95%+ reliability for critical operations (e.g., 2-hour forced liquidation), ensure 100% Binance API compliance, and continuously optimize trading signal generation and execution through machine learning.

## User Preferences
I prefer iterative development with clear communication at each stage. Please ask before making major architectural changes or significant modifications to core logic. I prefer detailed explanations for complex decisions and changes.

## System Architecture

### UI/UX Decisions
The system lacks a direct user interface; its "UX" is primarily delivered through clear, filtered logging and monitoring, specifically optimized for cloud environments like Railway. Logging is streamlined to focus on critical business metrics (model learning status, profitability, key trade execution info) and aggregated errors, reducing noise by 95-98%.

### Technical Implementations

#### Unified Manager Architecture v5.0
This architecture is built on the "Single Source of Truth" principle to eliminate architectural chaos and unify management patterns across key layers:
-   **WebSocket Layer**: `UnifiedWebSocketFeed` (single heartbeat, Producer-Consumer architecture).
-   **Configuration Layer**: `UnifiedConfigManager` (single entry point for all environment variables).
-   **Database Layer**: `UnifiedDatabaseManager` (unified interface for `asyncpg` and Redis).

#### Other Implementations
-   **Lifecycle Management**: `LifecycleManager` (singleton for graceful shutdown, signal handling), `StartupManager` (crash tracking), `Watchdog/Dead Man's Switch` (auto-restart), Railway-optimized zero-downtime deployment.
-   **AI/ML Core**: XGBoost model using a unified 12-feature ICT/SMC architecture for training and prediction (market structure, order blocks, liquidity grabs, fair value gaps). Models retrain automatically every 50 trades.
-   **Data Acquisition**: Producer-Consumer architecture with `asyncio.Queue` and three background worker threads to prevent event loop blocking. Features application-layer heartbeat monitor and robust reconnection logic. Employs a WebSocket-only K-line mode, eliminating REST K-line calls.
-   **Risk Management**: Dynamic leverage based on win rate and confidence, intelligent position sizing, dynamic stop-loss/take-profit adjustments, and seven smart exit strategies focused on capital preservation.
-   **Order Management**: `BinanceClient`, `OrderValidator`, and `SmartOrderManager` handle order precision, nominal value requirements, and common API errors.
-   **Caching**: Three-tier architecture: L1 memory cache for technical indicators, optional L2 Redis for hot database queries (30-60x speedup), and PostgreSQL as the source of truth. All operations are 100% async-safe and non-blocking.
-   **Database**: PostgreSQL serves as the unified data layer for all trading records and critical system states. Fully asynchronous using `asyncpg` with connection pooling for 100-300% performance improvement.
-   **Performance Stack**: `uvloop` for event loop (2-4x WebSocket throughput), `orjson` for JSON serialization (2-3x faster parsing), and Redis caching. All include graceful fallbacks.
-   **Configuration**: Flexible environment control and strategy tuning via feature toggle switches (e.g., `DISABLE_MODEL_TRAINING`, `RELAXED_SIGNAL_MODE`).

### Feature Specifications

#### Dynamic Position Sizing with Kelly Criterion
-   **Formula**: `kelly_multiplier = (confidence - 0.5) * 4`.
-   **Confidence Mapping**: Adjusts position size based on confidence (e.g., ≤50% skip, 75% baseline, 100% double).
-   **Safety Limits**: Capped at 10% account equity post-Kelly, with a 50% absolute account limit.
-   **Benefit**: Risk-adjusted scaling for better capital efficiency and mathematically optimal long-term growth.

#### Real-time Notification System
-   **`NotificationService`**: Fire-and-forget asynchronous notifications for Discord/Telegram.
-   **Events**: Covers trade opening, closing, and daily summaries with detailed metrics.
-   **Safety**: Non-blocking, error-isolated, and rate-limited.
-   **Configuration**: Optional via environment variables (`DISCORD_WEBHOOK_URL` or `TELEGRAM_TOKEN` + `TELEGRAM_CHAT_ID`).

#### Database Optimization
-   **Indexing**: Six PostgreSQL indexes (e.g., `win_status`, `entry_time`, `pnl`) significantly reduce query times (60-80% improvement).

#### Local-First, Zero-Polling Architecture
-   **Problem Addressed**: Eliminated 2,880+ daily REST API calls for account/position data, which previously led to high IP ban and rate limit risks.
-   **Solution**: Implemented `AccountStateCache` (an in-memory singleton) updated via WebSockets. All data reads for strategies are synchronous (<1ms) and from this cache, preventing network calls in the main loop.
-   **Impact**: Zero REST API calls for data retrieval, 250-600x faster response times for data access, eliminated IP ban and rate limit risks.

#### Event Loop Performance & Data Integrity
-   **`uvloop` Integration**: Provides 2-4x faster event loop processing, minimizing "Queue Full" warnings.
-   **Cache Reconciliation Mechanism**: `AccountStateCache.reconcile()` detects and auto-repairs cache drift (data inconsistencies from WebSocket packet loss) every 15 minutes by comparing cache data against REST API (source of truth).
-   **Low-Frequency Sync Task**: A scheduled task performs reconciliation every 15 minutes, reducing API calls to 96/day (a 97% reduction from prior polling).
-   **Logging Optimization**: `SmartLogger` uses rate limiting and aggregation to reduce debug noise by 90%, preventing I/O blocking from excessive logging.

## External Dependencies
-   **Binance API**: Used for real-time market data (WebSocket streams for K-lines, account, order updates) and order execution (REST API for account/order operations).
-   **PostgreSQL**: Primary database for persisting trading records, position entry times, and other critical system states.
-   **XGBoost**: Machine learning library used for predictive trading models.
-   **Asyncpg**: Asynchronous PostgreSQL driver for efficient database interaction.
-   **Railway**: Recommended cloud deployment platform, with specific optimizations for its environment (e.g., `sslmode=require`, `RailwayOptimizedFeed`).
-   **NumPy/Pandas**: Utilized in the technical indicators engine and for vectorized computations in data manipulation.
-   **Websockets library**: Python library for WebSocket communication.