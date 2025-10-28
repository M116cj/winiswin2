# 🚂 Railway 環境變數配置指南（v3.17+）

**更新日期**: 2025-10-28  
**系統版本**: v3.17+ Production Ready

---

## ✅ 已配置的變數（檢測到）

以下變數已在 Railway 上配置：

```env
# ===== 核心配置 =====
BINANCE_API_KEY=****
BINANCE_API_SECRET=****
BINANCE_TESTNET=****
TRADING_ENABLED=****

# ===== 交易設置 =====
CYCLE_INTERVAL=****
MAX_POSITIONS=****
MIN_CONFIDENCE=****
SCAN_INTERVAL=****
TOP_VOLATILITY_SYMBOLS=****

# ===== Discord 通知 =====
DISCORD_TOKEN=****
DISCORD_CHANNEL_ID=****

# ===== 系統配置 =====
LOG_LEVEL=****
PYTHONUNBUFFERED=****
DATA_FILE_PATH=****

# ===== 符號掃描 =====
ANALYZE_ALL_SYMBOLS=****
MAX_ANALYZE_SYMBOLS=****

# ===== v3.16 高級功能 =====
ENABLE_MARKET_REGIME_PREDICTION=****
ENABLE_DYNAMIC_FEATURES=****
ENABLE_LIQUIDITY_HUNTING=****
DYNAMIC_FEATURE_MAX_COUNT=****
DYNAMIC_FEATURE_MIN_SHARPE=****
LIQUIDITY_HUNT_CONFIDENCE_THRESHOLD=****
LIQUIDITY_SLIPPAGE_TOLERANCE=****
REGIME_PREDICTION_LOOKBACK=****
REGIME_PREDICTION_THRESHOLD=****

# ===== 策略模式 =====
TRATEGY_MODE=****  # ⚠️ 拼字錯誤，應為 STRATEGY_MODE
```

---

## 🆕 需要添加的 v3.17+ 變數

### 方式 1: 在 Railway Dashboard 手動添加

前往 Railway → 你的專案 → Variables → Raw Editor，添加以下變數：

```env
# ===== v3.17+ 生產級優化 =====

# 模型自動初始化（零配置部署）
INITIAL_TRAINING_ENABLED=true
INITIAL_TRAINING_SAMPLES=200
INITIAL_TRAINING_LOOKBACK_DAYS=30

# XGBoost 中性參數（零偏見啟動）
XGBOOST_N_ESTIMATORS=50
XGBOOST_MAX_DEPTH=4
XGBOOST_LEARNING_RATE=0.1
XGBOOST_SUBSAMPLE=0.8
XGBOOST_COLSAMPLE=0.8
XGBOOST_MIN_CHILD_WEIGHT=1
XGBOOST_GAMMA=0

# 高速監控優化
POSITION_MONITOR_INTERVAL=1
TREND_MONITOR_INTERVAL=30
TREND_MONITOR_ENABLED=true

# 即時學習配置
REALTIME_TRAINING_ENABLED=true
TRAINING_MIN_SAMPLES=30
TRAINING_UPDATE_INTERVAL=3600

# v3.17+ 核心策略配置
STRATEGY_MODE=self_learning
POSITION_CONTROL_MODE=self_learning
ENABLE_SELF_LEARNING=true

# v3.17+ 開倉條件
MIN_WIN_PROBABILITY=0.55
MIN_RR_RATIO=1.0
MAX_RR_RATIO=2.0

# v3.17+ 倉位監控
POSITION_MONITOR_ENABLED=true
RISK_KILL_THRESHOLD=0.99

# v3.17+ 模型評級
MODEL_RATING_ENABLED=true
ENABLE_DAILY_REPORT=true
REPORTS_DIR=reports/daily
```

---

### 方式 2: 一鍵複製（推薦）

**完整變數列表**（包含現有 + 新增）：

```env
# ===== Binance API 配置 =====
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
BINANCE_TESTNET=false

# ===== 核心策略配置 (v3.17+) =====
STRATEGY_MODE=self_learning
POSITION_CONTROL_MODE=self_learning
ENABLE_SELF_LEARNING=true

# ===== 開倉條件 (v3.17+) =====
MIN_WIN_PROBABILITY=0.55
MIN_CONFIDENCE=0.50
MIN_RR_RATIO=1.0
MAX_RR_RATIO=2.0

# ===== 倉位監控 (v3.17+) =====
POSITION_MONITOR_ENABLED=true
POSITION_MONITOR_INTERVAL=1
RISK_KILL_THRESHOLD=0.99

# ===== 模型評級 (v3.17+) =====
MODEL_RATING_ENABLED=true
ENABLE_DAILY_REPORT=true
REPORTS_DIR=reports/daily

# ===== 交易設置 =====
TRADING_ENABLED=false
MAX_POSITIONS=999
CYCLE_INTERVAL=60

# ===== 掃描配置 =====
SCAN_INTERVAL=60
TOP_VOLATILITY_SYMBOLS=200
ANALYZE_ALL_SYMBOLS=false
MAX_ANALYZE_SYMBOLS=500

# ===== 系統配置 =====
LOG_LEVEL=INFO
MAX_WORKERS=4
PYTHONUNBUFFERED=1

# ===== Discord 通知 =====
DISCORD_TOKEN=your_discord_token
DISCORD_CHANNEL_ID=your_channel_id

# ===== v3.17+ 生產級優化 =====

# 模型自動初始化
INITIAL_TRAINING_ENABLED=true
INITIAL_TRAINING_SAMPLES=200
INITIAL_TRAINING_LOOKBACK_DAYS=30

# XGBoost 中性參數
XGBOOST_N_ESTIMATORS=50
XGBOOST_MAX_DEPTH=4
XGBOOST_LEARNING_RATE=0.1
XGBOOST_SUBSAMPLE=0.8
XGBOOST_COLSAMPLE=0.8
XGBOOST_MIN_CHILD_WEIGHT=1
XGBOOST_GAMMA=0

# 高速監控
TREND_MONITOR_INTERVAL=30
TREND_MONITOR_ENABLED=true

# 即時學習
REALTIME_TRAINING_ENABLED=true
TRAINING_MIN_SAMPLES=30
TRAINING_UPDATE_INTERVAL=3600

# ===== v3.16 高級功能（可選）=====
ENABLE_MARKET_REGIME_PREDICTION=false
ENABLE_DYNAMIC_FEATURES=false
ENABLE_LIQUIDITY_HUNTING=false
DYNAMIC_FEATURE_MAX_COUNT=10
DYNAMIC_FEATURE_MIN_SHARPE=1.5
LIQUIDITY_HUNT_CONFIDENCE_THRESHOLD=0.75
LIQUIDITY_SLIPPAGE_TOLERANCE=0.002
REGIME_PREDICTION_LOOKBACK=100
REGIME_PREDICTION_THRESHOLD=0.6
```

---

## ⚠️ 需要修正的問題

### 拼字錯誤
```
TRATEGY_MODE → STRATEGY_MODE
```

請在 Railway 上：
1. 刪除 `TRATEGY_MODE`
2. 添加 `STRATEGY_MODE=self_learning`

---

## 🚀 部署檢查清單

### 步驟 1: 更新現有變數
- [ ] 修正 `TRATEGY_MODE` → `STRATEGY_MODE`
- [ ] 確認 `TRADING_ENABLED=false`（首次部署建議禁用）
- [ ] 確認 `BINANCE_API_KEY` 和 `SECRET` 正確

### 步驟 2: 添加 v3.17+ 新變數
- [ ] 複製上面的「完整變數列表」
- [ ] 貼上到 Railway → Variables → Raw Editor
- [ ] 點擊 Save

### 步驟 3: 部署並驗證
- [ ] 推送代碼到 Railway
- [ ] 查看日誌確認系統啟動
- [ ] 驗證自動訓練是否執行

---

## 📋 關鍵變數說明

### 必須配置
| 變數 | 說明 | 推薦值 |
|------|------|--------|
| `BINANCE_API_KEY` | Binance API 密鑰 | 你的密鑰 |
| `BINANCE_API_SECRET` | Binance API 密碼 | 你的密碼 |
| `TRADING_ENABLED` | 是否啟用實盤交易 | `false`（測試階段） |

### v3.17+ 核心配置
| 變數 | 說明 | 推薦值 |
|------|------|--------|
| `STRATEGY_MODE` | 策略模式 | `self_learning` |
| `MIN_WIN_PROBABILITY` | 最低勝率要求 | `0.55` (55%) |
| `POSITION_MONITOR_INTERVAL` | 倉位檢查間隔（秒） | `1` |
| `INITIAL_TRAINING_ENABLED` | 自動訓練 | `true` |

### 可選配置
| 變數 | 說明 | 推薦值 |
|------|------|--------|
| `ENABLE_MARKET_REGIME_PREDICTION` | 市場狀態預測 | `false` |
| `ENABLE_DYNAMIC_FEATURES` | 動態特徵生成 | `false` |
| `ENABLE_LIQUIDITY_HUNTING` | 流動性狩獵 | `false` |

---

## 🎯 快速啟動（最小配置）

如果只想快速測試，至少需要這些變數：

```env
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
BINANCE_TESTNET=false
TRADING_ENABLED=false
STRATEGY_MODE=self_learning
INITIAL_TRAINING_ENABLED=true
LOG_LEVEL=INFO
```

---

## 📊 驗證部署成功

部署後，檢查 Railway 日誌應該看到：

```
✅ 模型自動初始化器已創建（v3.17+）
✅ 實時趨勢監控器初始化完成（v3.17+）
🚀 檢查模型初始化狀態...
✅ 模型已就緒
🚀 啟動實時趨勢監控器...
✅ 趨勢監控器已啟動
```

---

**配置完成後，系統將自動：**
1. ✅ 檢測模型是否存在
2. ✅ 若無模型，自動收集數據並訓練
3. ✅ 啟動倉位監控（1 秒檢查）
4. ✅ 啟動趨勢監控（30 秒更新）
5. ✅ 開始高強度交易

**下一步**: 推送代碼到 Railway 並觀察日誌 🚀
