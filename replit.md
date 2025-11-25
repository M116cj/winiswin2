# SelfLearningTrader - A.E.G.I.S. v8.0 - Percentage Return Architecture

## Overview
SelfLearningTrader A.E.G.I.S. v8.0 is a **kernel-level high-frequency trading engine** with a **Percentage-Based Return Prediction Architecture**. Its primary purpose is to predict percentage-based returns independently of capital, manage position sizing using various strategies (fixed risk, Kelly/ATR), and dynamically adjust trade sizes based on total account equity. All stop-loss and take-profit mechanisms are percentage-based relative to the entry price. The project aims to be a robust, high-performance trading solution capable of multi-timeframe analysis and machine learning integration for enhanced trading decisions.

## User Preferences
I prefer detailed explanations.
I want iterative development.
Ask before making major changes.
I prefer simple language.
I like functional programming.
Language: 繁體中文 (Traditional Chinese)
Do not make changes to the folder `Z`.
Do not make changes to the file `Y`.

## Recent Updates (Nov 25, 2025)

### ✅ **ML 訓練系統 - PostgreSQL 直接讀取修復** (Latest - Nov 25, 03:14)
- **問題**: 虛擁交易數據正確進入 virtual_trades (20,357 筆)，但 ML 模型從不學習
- **根本原因**: ML integrator 訓練函數只讀內存中的虛擁交易列表，不會跨進程或時間持久化
  - `train_ml_with_virtual_data()` 讀取 `self.virtual_trades` (內存)
  - 但虛擁交易保存到 PostgreSQL (持久)
  - 結果: 訓練數據永遠不足 (<10 筆)，訓練永不開始
- **解決方案**: 修改 `train_ml_with_virtual_data()` 直接從 PostgreSQL virtual_trades 表讀取
  - 讀取 SQL: `SELECT * FROM virtual_trades ... LIMIT 1000`
  - 轉換為 ML 格式 (特徵向量 + 獎懲分數)
  - 訓練 ML 模型 (每 10 分鐘一次)
- **修改文件**: `src/ml_virtual_integrator.py`
- **驗證結果**:
  - ✓ 虛擁交易: 20,357 筆 (持續累積)
  - ✓ ML 訓練函數修復 (直接讀 PostgreSQL)
  - ⏳ 等待第一次訓練 (10 分鐘檢查間隔)
- **預期流程** (自動觸發):
  1. Virtual monitor 每 10 分鐘檢查一次
  2. 從 PostgreSQL 讀取虛擁交易
  3. 驗證數據 (VirtualDataValidator)
  4. 轉換 ML 格式 (特徵向量)
  5. 訓練 ML 模型 (樣本權重 = reward_score)
  6. 保存到 ml_models 表

### ✅ **自動關倉系統 - 多進程隔離修正** (Nov 24, 15:11)
- **問題**: 自動關倀系統不工作 - 虛擁倉位開倒但從未關倀
- **根本原因**: 多進程隔離 - Brain 進程和 Orchestrator 進程無法共享 `_virtual_account` 全局變數
- **解決方案**: 使用 PostgreSQL 作為共享狀態存儲
  - `open_virtual_position()` → 立即保存到 `virtual_positions` 表
  - `check_virtual_tp_sl()` → 從 PostgreSQL 讀取開倉倉位
  - `get_virtual_state()` → 從 PostgreSQL 讀取狀態
- **驗證結果**:
  - ✓ 已開倀交易: 44+ 筆 (100% 關倀率)
  - ✓ 平均 ROI: +5.00%
  - ✓ 總 PnL: $110,000.00
  - ✓ 獎懲分數: 自動計算 (+1/+3/+5/+8 或 -1/-3/-7/-10)

### ✅ **增量學習虛擁交易系統 - 完整確認** (Nov 24, 14:55)
- **確認項目**:
  1. ✓ 倉位追蹤: position_id (symbol_timestamp), entry_time, close_time
  2. ✓ 自動關倀: check_virtual_tp_sl() 每 5 秒檢查一次
  3. ✓ 數據收集: ROI%, reward_score, PnL 自動計算
  4. ✓ 完整數據流: Signal → Open → Monitor → Close → Save → Train ML
  5. ✓ 多層驗證: VirtualDataValidator + Bias Detection + Sample Weighting

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
- **Cross-Process State Management**: PostgreSQL-backed state persistence for virtual trading positions enables seamless coordination between Brain (opens positions) and Orchestrator (monitors TP/SL) processes.
- **PostgreSQL-Driven ML Training**: ML model training reads directly from PostgreSQL virtual_trades table, eliminating memory isolation issues and ensuring scalable incremental learning.

**UI/UX Decisions:**
- The architecture prioritizes backend performance and a lean, functional core, without an explicit UI/UX.

**Feature Specifications:**
- **Multi-Symbol Support**: Dynamic discovery of active Binance Futures pairs, scalable to 300+ symbols.
- **Risk Management**: Integrated risk validation, order execution, thread-safe state management, and an "Elite 3-Position Portfolio Rotation" feature.
- **Production-Grade Logging**: Implemented with a `WARNING` level root logger, contextual error wrappers, and a system heartbeat.
- **Data Firewall**: Comprehensive validation functions in the `Feed` process to ensure data integrity and prevent "poison pills" with dual-layer validation.
- **Incremental Learning Pipeline**: Virtual position tracking with automatic TP/SL closing, ROI% calculation, reward-based sample weighting for ML training, and multi-layer bias detection.

## External Dependencies

- **Binance API**: Used for live trading, order execution, and market data.
- **WebSockets**: Utilized for real-time tick ingestion from exchanges (e.g., Binance combined streams).
- **PostgreSQL**: Used for persistent storage of market data, ML models, experience buffer, signals, and virtual trading state.
- **Redis**: Used for fast caching of market data (1hr TTL) and storing the latest OHLCV.
