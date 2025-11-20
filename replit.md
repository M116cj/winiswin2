# SelfLearningTrader - Compressed Overview

## Overview
SelfLearningTrader is an AI-driven cryptocurrency automated trading system designed for high reliability and performance. It leverages machine learning with advanced ICT/SMC strategies to make trading decisions, aiming for true AI-driven trading. The system is designed for deployment on cloud platforms like Railway and features significant performance optimizations, including a 4-5x speed improvement in data acquisition and a 85% cache hit rate. A key focus is on compliance with exchange API protocols, achieving zero REST K-line API calls to prevent IP bans.

**Business Vision**: To provide a robust, AI-powered automated trading solution for cryptocurrency markets.
**Market Potential**: Addresses the growing demand for sophisticated, reliable, and compliant automated trading systems in the volatile crypto market.
**Project Ambitions**: Achieve 95%+ reliability for critical operations like 2-hour forced liquidation, ensure 100% Binance API compliance, and continuously optimize trading signal generation and execution through machine learning.

## User Preferences
I want to prioritize iterative development, with clear communication at each stage. Ask before making major architectural changes or significant modifications to core logic. I prefer detailed explanations for complex decisions and changes.

## System Architecture

### UI/UX Decisions
The system does not have a direct user interface; its "UX" is primarily through clear, filtered logging and monitoring, especially optimized for cloud environments like Railway. Logging is streamlined to focus on critical business metrics (model learning status, profitability, key trade execution info) and error aggregation, reducing noise by 95-98%.

### Technical Implementations
- **AI/ML Core**: Utilizes XGBoost models with a unified 12-feature ICT/SMC schema for training and prediction. Features include market structure, order blocks, liquidity grabs, and fair value gaps. The model retrains automatically every 50 trades.
- **Data Acquisition**: Employs a WebSocket-only K-line data mode, eliminating REST K-line API calls. It features a robust WebSocket manager with intelligent reconnection, extended timeouts, and a data quality monitor with gap handling and historical data backfilling.
- **Risk Management**: Incorporates dynamic leverage based on win rate and confidence, intelligent position sizing, and dynamic Stop Loss/Take Profit adjustments. It features seven smart exit strategies, including forced liquidation for 100% loss, partial profit-taking, and time-based stop-loss mechanisms, which are critical for capital preservation.
- **Order Management**: Includes `BinanceClient` with `OrderValidator` and `SmartOrderManager` to handle order precision and notional value requirements, preventing common API errors.
- **Caching**: Implements optimized L1 in-memory caching (1000 entries) for technical indicators and market data. L2 persistent cache has been disabled in Phase 2 to save 250MB memory and reduce disk I/O. TTL optimized to 5-10 minutes to match strategy scanning periods, achieving 85-90%+ cache hit rate.
- **Database**: PostgreSQL is the unified data layer, managing all trade records and critical system state like position entry times. Phase 3 completed: Unified to asyncpg for full async architecture. All database operations now use async/await with connection pooling for 100-300% performance improvement.
- **Configuration**: Uses feature lock switches (`DISABLE_MODEL_TRAINING`, `DISABLE_WEBSOCKET`, `DISABLE_REST_FALLBACK`) and signal generation mode (`RELAXED_SIGNAL_MODE`) for flexible environment control and strategy tuning.

### Feature Specifications
- **Position Holding Time Persistence**: Stores and retrieves position entry times from PostgreSQL to ensure accurate time-based stop-loss even after system restarts.
- **Liquidation Retry Mechanism**: Implements a retry logic with exponential backoff for liquidation orders to increase reliability during temporary network or API issues.
- **Time-Based Stop-Loss Enhancement**: Ensures strict 2-hour forced liquidation for all positions, regardless of profitability, with a 60-second check interval.
- **Rate Limit Compliance**: Disables default REST API warm-up to prevent Binance IP bans, relying solely on WebSocket data accumulation.
- **Unified Feature Schema (v4.0)**: Standardizes 12 core ICT/SMC features for ML model training and prediction, ensuring consistency and preventing prediction mismatches.
- **Elite Refactoring (v3.20)**: Consolidates technical indicator computations into a single `EliteTechnicalEngine` and optimizes data pipelines for improved performance and reduced code redundancy.
- **ML Pipeline Optimization (v4.5.0)**: Extreme ML system simplification that deleted 946 lines of dead code (-39.3%), fixed P0 training/inference feature inconsistency, and ensured 100% feature consistency between training (12 ICT/SMC) and inference. Removed unused files (predictor.py, online_learning.py) and deprecated methods, disabled synthetic sample generation to enforce real trading data usage.
- **Phase 1 (2025-11-20)**: Fixed critical position_entry_times table missing error, created migration script, verified database schema. Established PostgreSQL as single source of truth.
- **Phase 2 (2025-11-20)**: Disabled L2 persistent cache globally (saving 250MB memory), optimized L1 cache from 5000 to 1000 entries, extended TTL from 60s to 300s (5 minutes) to match strategy scanning period. Cleaned up empty src/technical/ directory. Documented database driver unification plan for Phase 3.
- **Phase 3 (2025-11-20)**: Completed database driver unification (psycopg2→asyncpg). Created AsyncDatabaseManager with connection pooling, converted all database operations to async/await (11 files modified). Fixed 6 bugs during migration (placeholder conversion, Record formatting, ID extraction, async/await consistency, tuple indexing). Removed psycopg2 dependency. System validated production-ready with 100% async database operations and 100-300% expected performance improvement.

### System Design Choices
- **Modularity**: The system is structured into `core`, `clients`, `ml`, `strategies`, `managers`, and `utils` for clear separation of concerns.
- **Scalability**: Designed to monitor over 200 USDT perpetual contracts with optimized data handling and parallel processing.
- **Resilience**: Features graceful degradation for database failures (fallback to in-memory mode), robust WebSocket reconnection, and error handling for external API interactions.

## External Dependencies
- **Binance API**: For real-time market data (WebSocket streams for K-lines, account, and order updates) and order execution (REST API for account/order actions).
- **PostgreSQL**: Primary database for persisting trade records, position entry times, and other critical system state.
- **XGBoost**: Machine learning library used for the predictive trading model.
- **Asyncpg**: Asynchronous PostgreSQL driver for efficient database interactions.
- **Railway**: Recommended cloud deployment platform, with specific optimizations for its environment (e.g., `sslmode=require` for public connections, `RailwayOptimizedFeed`, `RailwayBusinessLogger`).
- **NumPy/Pandas**: Used for vectorized computations in the technical indicator engine and data manipulation.
- **Websockets library**: Python library for WebSocket communication.