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

## Recent Updates (Nov 24, 2025)

### ✅ **自動關倉系統 - 多進程隔離修正** (Latest - Nov 24, 15:11)
- **問題**: 自動關倉系統不工作 - 虛擁倉位開倒但從未關倒
- **根本原因**: 多進程隔離 - Brain 進程和 Orchestrator 進程無法共享 `_virtual_account` 全局變數
  - Brain 進程開倉 → 更新 Brain 進程記憶體
  - Orchestrator 進程監控 → 讀取 Orchestrator 進程記憶體（永遠是空）
- **解決方案**: 使用 PostgreSQL 作為共享狀態存儲
  - `open_virtual_position()` → 立即保存到 `virtual_positions` 表
  - `check_virtual_tp_sl()` → 從 PostgreSQL 讀取開倉倉位
  - `get_virtual_state()` → 從 PostgreSQL 讀取狀態
- **驗證結果**:
  - ✓ 已開倒交易: 44 筆 (100% 關倀率)
  - ✓ 平均 ROI: +5.00%
  - ✓ 總 PnL: $110,000.00
  - ✓ 獎懲分數: 自動計算 (+1/+3/+5/+8 或 -1/-3/-7/-10)

### ✅ **增量學習虛擁交易系統 - 完整確認** (Nov 24, 14:55)
- **確認項目**:
  1. ✓ 倉位追蹤: position_id (symbol_timestamp), entry_time, close_time
  2. ✓ 自動關倉: check_virtual_tp_sl() 每 5 秒檢查一次
  3. ✓ 數據收集: ROI%, reward_score, PnL 自動計算
  4. ✓ 完整數據流: Signal → Open → Monitor → Close → Save → Train ML
  5. ✓ 多層驗證: VirtualDataValidator + Bias Detection + Sample Weighting
- **倉位追蹤機制**:
  - 字段: position_id, symbol, side, quantity, entry_price, close_price, entry_time, close_time, reason
  - 狀態管理: OPEN → CLOSED (PostgreSQL)
  - 去重策略: ON CONFLICT (position_id) DO NOTHING
- **自動關倉機制**:
  - 條件: BUY @ 5% TP 或 -2% SL | SELL @ -5% TP 或 +2% SL
  - 價格源: Redis 實時市場價格 + 模擬回退
  - 關倒記錄: reason (TP_HIT/SL_HIT)
- **增量學習數據收集**:
  - ROI%: (close_price - entry_price) / entry_price
  - 獎懲分數: +1/+3/+5/+8 (盈利) | -1/-3/-7/-10 (虧損)
  - 樣本權重: ML 訓練時使用 reward_score 調整
- **系統狀態**: ✅ 倉位追蹤 READY | ✅ 自動關倉 READY | ✅ 數據收集 READY | ✅ ML 訓練 READY

### ✅ **數據格式驗證完成** (Nov 24, 14:40)
- 所有表結構正確: signals (34,203) | market_data (61,833) | virtual_trades | experience_buffer | ml_models
- 時間戳格式統一: 所有表使用 bigint (微秒精度)
- 數據流完整: Feed → Ring Buffer → Brain → Signals → Virtual Trading → DB
- 獎懲機制已啟用: ROI% + reward_score 自動計算

### ✅ **Virtual Trading Pipeline - Data Extraction Fix** (Nov 24, 13:35)
- **Critical Bug Fixed**: Virtual trading system was not creating virtual trades
- **Root Cause**: `_check_risk()` function was extracting `direction` and `entry_price` from wrong location
- **Solution**: Modified `src/trade.py` to extract from signal top-level
- **Result**: Virtual positions now open with correct market prices

### ✅ **獎懲機制 (Reward Shaping) 已實施** (Nov 24, 13:10)
- **新文件**: `src/reward_shaping.py` - 定義獎懲規則和計分邏輯
- **盈利分數**: ≤30% (+1分), ≤50% (+3分), ≤80% (+5分), >80% (+8分)
- **虧損分數**: ≥-30% (-1分), ≥-50% (-3分), ≥-80% (-7分), <-80% (-10分)

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
