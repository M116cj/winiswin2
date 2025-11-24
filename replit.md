# SelfLearningTrader - A.E.G.I.S. v8.0

## Overview
SelfLearningTrader A.E.G.I.S. v8.0 is a **kernel-level high-frequency trading engine** designed for extreme performance, scalability, and microsecond latency in tick-to-trade execution. It features a dual-process architecture for true parallelism, capable of handling hundreds of trades per second across 300+ symbols at 100,000+ ticks/sec. The project aims to minimize latency and maximize throughput by eliminating common performance bottlenecks, focusing on a production-ready system for live trading.

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
- **Hardened Triple-Process Architecture**: Pure Python multiprocessing with signal handling (SIGTERM, SIGINT), auto-restart on failure, and graceful shutdown. Consists of:
    1. **Orchestrator**: Initializes database and ring buffer, runs reconciliation, system monitoring, and maintenance.
    2. **Feed**: WebSocket data ingestion to ring buffer.
    3. **Brain**: Ring buffer reader, SMC/ML analysis, trade execution.
- **Keep-Alive Watchdog Loop**: Main process monitors all three core processes, triggering a container restart on failure.
- **Shared Memory Ring Buffer**: Implements the LMAX Disruptor pattern for zero-lock, single-writer/single-reader IPC, using struct packing for microsecond latency. Includes overrun protection and data sanitization.
- **Monolith-Lite Design**: Maintains a lean codebase for simplicity.
- **Event-Driven**: Utilizes an `EventBus` for zero-coupling communication between modules.
- **High-Performance Components**: Integrates `uvloop` for faster event loops, `Numba JIT` for accelerated mathematical calculations, object pooling to reduce garbage collection pressure, a conflation buffer for high-frequency data, and a priority dispatcher for non-blocking, priority-scheduled task processing.
- **Multi-Timeframe Trading System**: Implements a multi-timeframe analysis (1D → 1H → 15m → 5m/1m) for trend confirmation and precise entry points, with confidence-weighted signal calculation and dynamic position sizing based on confidence and win rate.
- **ML Integration**: Features a module for training ML models with virtual data, including comprehensive validation and bias detection (e.g., win rate, PnL distribution, symbol diversity, BUY/SELL balance).

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

### 💰 NEW: Binance Protocol Integration & Unlimited Leverage System

**Date: 2025-11-24 - 完整的 Binance 約束集成 + 無限制槓桿**

**Binance 協議限制已實施：**

1. **最低開倉限制（最小名義價值）：**
   - BTCUSDT: 50 USDT
   - ETHUSDT: 20 USDT
   - 其他所有對: 5 USDT
   - 系統在下單前自動驗證

2. **槓桿限制（分檔制）：**
   - 最大槓桿：125x（主要對）
   - 根據持倉名義價值自動降級
   - 完整的 BTCUSDT 和 ETHUSDT 分檔配置

**New Components:**

1. **src/binance_constraints.py**
   - BinanceConstraints 類：管理所有 Binance 限制
   - get_min_notional(symbol): 最低名義價值
   - calculate_min_quantity(symbol, price): 計算最低數量
   - validate_order_size(symbol, qty, price): 訂單驗證
   - get_max_leverage(symbol, notional): 分檔槓桿查詢
   - clamp_leverage(leverage): ✅ 轉換為整數

2. **src/leverage_validator.py**
   - validate_and_clamp_leverage(): 完整槓桿驗證管道
   - 計算 → 轉換為整數 → 檢查分檔 → 返回最終值

**無限制槓桿實施（整數槓桿）：**

- 公式：`leverage_raw = 2.0 * (1.0 + conf_boost*0.7 + win_boost*0.3)`
- 信心度倍增：(confidence - 0.60) * 10.0
- 勝率倍增：(winrate - 0.60) * 10.0
- ✅ 轉換為整數：`int(leverage_raw)` 確保 >= 1
- Binance 分檔自動限制

示例計算：
- 信心度 0.60, 勝率 0.60 → leverage_raw ≈ 2.0 → 整數 2x
- 信心度 0.80, 勝率 0.70 → leverage_raw ≈ 5.2 → 整數 5x
- 信心度 0.90, 勝率 0.80 → leverage_raw ≈ 8.6 → 整數 8x
- 信心度 1.00, 勝率 0.90 → leverage_raw ≈ 12.0 → 整數 12x

**系統整合：**
- position_calculator.py: 無限制槓桿計算
- trade.py: Binance 約束驗證在下單前
- 所有槓桿值都是整數，符合 Binance API 要求
