# SelfLearningTrader v3.18.7+ - 生產級自動交易系統

## 📌 項目概述

**版本**：v3.18.7+  
**狀態**：✅ 生產就緒  
**部署目標**：Railway（推薦）或其他雲平台

SelfLearningTrader 是一個基於機器學習的加密貨幣自動交易系統，實現真正的AI驅動交易決策。

---

## 🎯 核心特性

### 1. 🧠 機器學習驅動
- **XGBoost模型**：44個特徵完整記錄與預測
- **自動重訓練**：每50筆交易觸發模型更新
- **勝率預測**：基於歷史數據持續優化
- **特徵完整性**：100%驗證通過（447行測試套件）

### 2. 🎚️ 無限槓桿控制
- **動態槓桿**：基於勝率 × 信心度
- **智能倉位**：10 USDT最小倉位
- **動態SL/TP**：高槓桿 → 寬止損
- **多信號競價**：加權評分機制

### 3. 🛡️ 風險管理
- **7種智能出場**：
  1. 💯 100%虧損熔斷（PnL ≤ -99%）
  2. 💰 60%盈利自動平倉50%
  3. 🔴 強制止盈（信心/勝率降20%）
  4. 🟡 智能持倉（深度虧損+高信心）
  5. ⚠️ 進場理由失效（信心<70%）
  6. ⚪ 逆勢平倉（信心<80%）
  7. 🔵 追蹤止盈（盈利>20%）

### 4. 📡 實時數據（可選）
- **WebSocket監控**：200+個USDT永續合約
- **K線Feed**：@kline_1m實時更新
- **帳戶Feed**：listenKey即時倉位
- **REST備援**：WebSocket失敗自動切換

### 5. 📊 ICT/SMC策略
- **Order Blocks**：機構建倉區識別
- **Liquidity Zones**：流動性聚集區
- **Market Structure**：BOS/CHOCH檢測
- **Fair Value Gaps**：價格真空識別
- **Institutional Candles**：機構K線分析

---

## 🔒 功能鎖定開關 (v3.18.7+)

### 新增三大鎖定開關用於生產環境控制：

#### 1. `DISABLE_MODEL_TRAINING` (默認: `true`)
- **用途**：鎖定模型訓練（初始訓練 + 重訓練）
- **生產配置**：`true` - 使用預訓練模型
- **開發配置**：`false` - 允許動態學習

#### 2. `DISABLE_WEBSOCKET` (默認: `true`)
- **用途**：鎖定WebSocket，使用純REST模式
- **生產配置**：`true` - 純REST模式（穩定）
- **開發配置**：`false` - WebSocket實時數據

#### 3. `DISABLE_REST_FALLBACK` (默認: `false`)
- **用途**：禁用REST API備援
- **生產配置**：`false` - 保持備援（推薦）
- **極端場景**：`true` - 僅WebSocket（不推薦）

---

## 🎚️ 信號生成模式配置 (v3.18.7+)

### `RELAXED_SIGNAL_MODE` - ICT/SMC信號寬鬆度控制

#### ⚠️ **重要診斷結果（2025-11-01）**：

**問題**：530個交易對掃描但0信號產生  
**根本原因**：嚴格模式（RELAXED_SIGNAL_MODE=false）的ICT/SMC過濾器過於苛刻

**嚴格模式要求**：
- ✅ H1 + M15 **必須完全同向**（都bullish或都bearish）
- ✅ Market Structure不對立
- ✅ Order Blocks精確對齊
- ✅ 結果：530個交易對中可能只有5-10個符合條件

**寬鬆模式優勢**：
- ✅ 允許H1主導（H1明確，M15可neutral）
- ✅ 允許M15+M5短期對齊（H1可neutral）
- ✅ 預期信號數量提升10-20倍

#### 配置選項：

##### 嚴格模式（默認）
```env
RELAXED_SIGNAL_MODE=false
```
- **適用場景**：追求高質量、低頻率信號
- **信號數量**：極少（530個中可能5-10個）
- **勝率要求**：多時間框架完美對齊
- **推薦情況**：資金充足，追求高勝率

##### 寬鬆模式（推薦初期使用）
```env
RELAXED_SIGNAL_MODE=true
```
- **適用場景**：增加信號數量，加速模型訓練
- **信號數量**：中等（530個中可能50-100個）
- **勝率要求**：主導時間框架對齊即可
- **推薦情況**：初期啟動，數據採集階段

#### 建議配置（按階段）：

**階段1：數據採集期（前100筆交易）**
```env
RELAXED_SIGNAL_MODE=true
BOOTSTRAP_TRADE_LIMIT=100
BOOTSTRAP_MIN_WIN_PROBABILITY=0.40
BOOTSTRAP_MIN_CONFIDENCE=0.40
```

**階段2：正常運行期（100筆後）**
```env
RELAXED_SIGNAL_MODE=true  # 保持寬鬆模式
MIN_WIN_PROBABILITY=0.60
MIN_CONFIDENCE=0.50
```

**階段3：高質量期（有足夠歷史數據後）**
```env
RELAXED_SIGNAL_MODE=false  # 可切換回嚴格模式
MIN_WIN_PROBABILITY=0.65
MIN_CONFIDENCE=0.60
```

**詳細文檔**：[FEATURE_LOCKS.md](FEATURE_LOCKS.md)

---

## 🏗️ 項目架構

### 核心組件

```
src/
├── clients/              # Binance API客戶端
│   ├── binance_client.py
│   └── binance_errors.py
├── core/                 # 核心引擎
│   ├── model_initializer.py    # 模型自動初始化
│   ├── unified_scheduler.py    # 統一調度器
│   ├── leverage_engine.py      # 槓桿控制
│   ├── position_sizer.py       # 倉位計算
│   ├── sltp_adjuster.py        # SL/TP調整
│   └── websocket.py            # WebSocket管理
├── ml/                   # 機器學習
│   ├── model_wrapper.py        # XGBoost封裝
│   └── feature_engine.py       # 特徵工程
├── strategies/           # 交易策略
│   ├── self_learning_trader.py # 主策略
│   └── rule_based_signal_generator.py # ICT/SMC信號
├── managers/             # 數據管理
│   └── trade_recorder.py       # 交易記錄
└── main.py               # 程序入口
```

---

## 🚀 部署指南

### Railway部署（推薦）

1. **環境變量設置**：
```env
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
DISABLE_MODEL_TRAINING=true
DISABLE_WEBSOCKET=true
DISABLE_REST_FALLBACK=false
```

2. **預訓練模型**：
- 上傳 `models/xgboost_model.json` 到部署環境
- 或首次部署時臨時設置 `DISABLE_MODEL_TRAINING=false`

3. **啟動命令**：
```bash
python -m src.main
```

---

## 📊 數據流程

### 1. 信號生成
```
RuleBasedSignalGenerator
  ├─ Order Block檢測
  ├─ Liquidity Zone識別
  ├─ Market Structure分析
  └─ 44個特徵字段生成
```

### 2. 特徵提取
```
FeatureEngine
  ├─ 基礎特徵（價格、成交量）
  ├─ 競價上下文（勝率、信心度）
  └─ WebSocket特徵（實時數據）
```

### 3. ML預測
```
MLModelWrapper
  ├─ XGBoost模型加載
  ├─ 44特徵輸入
  └─ 勝率預測輸出
```

### 4. 決策執行
```
SelfLearningTrader
  ├─ 槓桿計算（勝率 × 信心度）
  ├─ 倉位計算（最小10 USDT）
  ├─ SL/TP調整（動態放大）
  └─ 訂單執行
```

### 5. 交易記錄
```
TradeRecorder
  ├─ 44特徵完整記錄
  ├─ trades.jsonl持久化
  └─ 每50筆觸發重訓練
```

---

## 🧪 測試與驗證

### 特徵完整性測試
```bash
python -m pytest tests/test_feature_integrity.py -v
```

**測試覆蓋**：
- ✅ 特徵名稱一致性（44個）
- ✅ 提取管道完整性
- ✅ 模型兼容性
- ✅ 特徵順序一致性
- ✅ 歷史數據兼容性

---

## 📈 性能指標

### 模型評級系統（100分制）
- **基礎分**：60分
- **勝率加分**：最高+20分
- **盈虧比加分**：最高+15分
- **交易頻率加分**：最高+10分
- **最大回撤扣分**：最高-15分
- **100%虧損懲罰**：-40分/次

### 交易統計
- **最小倉位**：10 USDT
- **槓桿範圍**：無限制（基於勝率）
- **監控週期**：60秒
- **重訓練間隔**：50筆交易

---

## 🔧 配置文件

### src/config.py
```python
# 功能鎖定開關
DISABLE_MODEL_TRAINING: bool = True
DISABLE_WEBSOCKET: bool = True
DISABLE_REST_FALLBACK: bool = False

# 交易參數
TRADING_ENABLED: bool = True
MIN_CONFIDENCE: float = 0.50
CYCLE_INTERVAL: int = 60
```

---

## 📚 文檔索引

1. **[FEATURE_LOCKS.md](FEATURE_LOCKS.md)** - 功能鎖定開關詳細指南
2. **[TRADING_STRATEGY_REPORT.md](TRADING_STRATEGY_REPORT.md)** - 交易策略完整文檔
3. **[tests/test_feature_integrity.py](tests/test_feature_integrity.py)** - 特徵完整性測試

---

## 🛠️ 故障排除

### Binance API 451錯誤
**症狀**：地理位置限制  
**解決**：部署到Railway或其他雲平台

### 模型文件缺失
**症狀**：`DISABLE_MODEL_TRAINING=true` 但無模型  
**解決**：臨時設置 `DISABLE_MODEL_TRAINING=false` 訓練初始模型

### WebSocket連接失敗
**症狀**：WebSocket無法建立  
**解決**：設置 `DISABLE_WEBSOCKET=true` 使用純REST模式

---

## 🎉 最新更新

### v3.18.7+ (2025-11-01) - 重大BUG修復
- 🐛 **修復0信號BUG**：SIGNAL_QUALITY_THRESHOLD動態門檻（豁免期0.4，正常期0.6）
- 🎯 **預期效果**：信號數量從0提升到30-50個/周期（530個交易對中）
- 📊 **數學證明**：40%/40%門檻質量分數=0.480，原門檻0.6全部拒絕
- ✅ **完整修復**：Config + CapitalAllocator + SelfLearningTrader
- 📚 **詳細文檔**：BUG_FIX_SIGNAL_QUALITY_THRESHOLD.md

### v3.18.7 (2025-11-01)
- ✨ 新增功能鎖定開關（3個）
- 🔒 生產環境靈活控制
- 📚 完整文檔（FEATURE_LOCKS.md）
- ✅ 100% LSP診斷清零

### v3.18.6
- ✅ 44特徵完整性100%驗證
- 📊 交易策略完整文檔化
- 🧪 447行測試套件
- 🎯 生產就緒確認

---

## 📞 支援

**問題反饋**：GitHub Issues  
**文檔更新**：定期維護  
**部署協助**：參考Railway文檔

---

**🚀 系統已就緒，可安全部署到生產環境！**
