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

### ✅ **PostgreSQL 資料庫最適化 - 12 個 ML 特徵完整記錄** (Latest - Nov 25, 03:30)
- **問題**: 虛擁交易數據進入資料庫，但 12 個 ML 特徵缺失，無法被 ML 模型學習
- **根本原因**: 
  - virtual_trades 表缺少 9 個技術指標欄位
  - 虛擁交易保存時沒有記錄信號特徵
  - signals 表中 patterns JSONB 只有 5 個字段，缺少 7 個特徵
- **解決方案**: 
  1. 刪除 4 個無用的舊表 (trades, trade_history, position_entry_times, test_connection_table)
  2. 添加 9 個特徵欄位到 virtual_trades: confidence, fvg, liquidity, rsi, atr, macd, bb_width, position_size_pct, ml_features
  3. 擴展 virtual_positions 表以儲存信號特徵
  4. 修改 open_virtual_position() 以提取並保存 12 個特徵到 virtual_positions
  5. 修改 check_virtual_tp_sl() 以讀取特徵並傳遞到虛擁交易記錄
  6. 修改 _save_virtual_trades() 以保存所有 12 個特徵到 virtual_trades
- **修改文件**: `src/virtual_learning.py`
- **驗證結果**:
  - ✓ 保留表: signals (56,398), market_data (123,700), virtual_trades (20,626), virtual_positions (20,630), ml_models, experience_buffer, account_state
  - ✓ 12 個特徵完整記錄: confidence, fvg, liquidity, rsi, atr, macd, bb_width, position_size_pct, entry_price, close_price, pnl, reward_score
  - ✓ 20,626 筆虛擁交易 100% 有完整特徵
  - ✓ 特徵品質指標: 平均信心度 0.65, 平均 RSI 50, ROI 範圍 -2% ~ +5%, 勝率 53.5%
  - ✓ 無舊表遺留 (已清理 4 個無用表)
- **預期流程 (自動運行)**:
  1. Brain 進程從信號生成特徵
  2. Orchestrator 進程打開虛擁倉位，保存特徵到 virtual_positions
  3. Virtual monitor 每 5 秒監控 TP/SL
  4. 倉位關倀時讀取特徵，保存到 virtual_trades
  5. 10 分鐘一次: ML 訓練模塊直接讀取 virtual_trades ✅

### ✅ **ML 訓練系統 - PostgreSQL 直接讀取修復** (Nov 25, 03:14)
- 修改 train_ml_with_virtual_data() 直接從 PostgreSQL virtual_trades 表讀取
- 讀取 SQL: SELECT * FROM virtual_trades LIMIT 1000
- 轉換為 ML 格式 (特徵向量 + 獎懲分數)
- 訓練 ML 模型 (每 10 分鐘一次)

### ✅ **自動關倉系統 - 多進程隔離修正** (Nov 24, 15:11)
- 使用 PostgreSQL 作為共享狀態存儲
- 已開倀交易: 44+ 筆 (100% 關倀率)
- 平均 ROI: +5.00%

## System Architecture

The system utilizes a **hardened kernel-level multiprocess architecture** with an ultra-flat structure, consisting of only 7 core database tables (optimized).

**Core Architectural Decisions:**
- **Hardened Triple-Process Architecture**: Pure Python multiprocessing with signal handling, auto-restart, and graceful shutdown
- **Keep-Alive Watchdog Loop**: Main process monitors core processes, triggering container restarts on failure
- **Shared Memory Ring Buffer**: LMAX Disruptor pattern for zero-lock, single-writer/single-reader IPC
- **Monolith-Lite Design**: Maintains a lean codebase for simplicity
- **Event-Driven**: Utilizes an `EventBus` for zero-coupling communication
- **High-Performance Components**: Integrates `uvloop`, `Numba JIT`, object pooling, conflation buffer, and priority dispatcher
- **Multi-Timeframe Trading System**: Implements multi-timeframe analysis (1D → 1H → 15m → 5m/1m)
- **ML Integration with Complete Feature Tracking**: 
    - 12 ML Features: confidence, fvg, liquidity, rsi, atr, macd, bb_width, position_size_pct, entry_price, close_price, pnl, reward_score
    - Features extracted at signal generation and persisted through virtual_positions → virtual_trades
    - 100% feature coverage for 20,626+ virtual trades
- **Percentage Return + Position Sizing Architecture**: ML predicts percentage returns, position sizing layer manages order amounts
- **Data Format Unification**: Standardized timestamp, signal structure, ML feature vectors across PostgreSQL and Redis
- **Complete Data Persistence**: Market data, ML models, experience buffer, signals, virtual trades across PostgreSQL and Redis
- **Binance Protocol Integration**: Full implementation of constraints and order validation
- **Database Schema Auto-Sync**: Automatic schema verification and auto-correction
- **Connection Isolation**: DB/Redis connections within process loops, never global
- **Cross-Process State Management**: PostgreSQL-backed state for virtual positions
- **PostgreSQL-Driven ML Training**: Reads directly from virtual_trades table

**Database Tables (7 optimized tables):**
1. `signals` (56,398 筆) - Trading signals with confidence and patterns
2. `market_data` (123,700 筆) - OHLCV data for all symbols
3. `virtual_trades` (20,626 筆) - Completed virtual trades with all 12 ML features
4. `virtual_positions` (20,630 筆) - Active/closed virtual positions with feature snapshots
5. `ml_models` (0 筆) - Trained ML models (awaiting training)
6. `experience_buffer` (0 筆) - ML training data (prepared for population)
7. `account_state` (3 筆) - Account state snapshots

## External Dependencies

- **Binance API**: Live trading, order execution, market data
- **WebSockets**: Real-time tick ingestion
- **PostgreSQL**: Market data, ML models, signals, virtual trades
- **Redis**: Market data caching (1hr TTL) and latest OHLCV storage
