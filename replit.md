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
- **Caching**: Implements a three-tier caching architecture (L1 in-memory, L2 persistent, L3 API fallback) for technical indicators and market data, significantly boosting performance.
- **Database**: PostgreSQL is the unified data layer, managing all trade records and critical system state like position entry times. It features `asyncpg` for efficient asynchronous database operations.
- **Configuration**: Uses feature lock switches (`DISABLE_MODEL_TRAINING`, `DISABLE_WEBSOCKET`, `DISABLE_REST_FALLBACK`) and signal generation mode (`RELAXED_SIGNAL_MODE`) for flexible environment control and strategy tuning.

### Feature Specifications
- **Position Holding Time Persistence**: Stores and retrieves position entry times from PostgreSQL to ensure accurate time-based stop-loss even after system restarts.
- **Liquidation Retry Mechanism**: Implements a retry logic with exponential backoff for liquidation orders to increase reliability during temporary network or API issues.
- **Time-Based Stop-Loss Enhancement**: Ensures strict 2-hour forced liquidation for all positions, regardless of profitability, with a 60-second check interval.
- **Rate Limit Compliance**: Disables default REST API warm-up to prevent Binance IP bans, relying solely on WebSocket data accumulation.
- **Unified Feature Schema (v4.0)**: Standardizes 12 core ICT/SMC features for ML model training and prediction, ensuring consistency and preventing prediction mismatches.
- **Elite Refactoring (v3.20)**: Consolidates technical indicator computations into a single `EliteTechnicalEngine` and optimizes data pipelines for improved performance and reduced code redundancy.
- **ML Pipeline Optimization (v4.5.0)**: Extreme ML system simplification that deleted 946 lines of dead code (-39.3%), fixed P0 training/inference feature inconsistency, and ensured 100% feature consistency between training (12 ICT/SMC) and inference. Removed unused files (predictor.py, online_learning.py) and deprecated methods, disabled synthetic sample generation to enforce real trading data usage.

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