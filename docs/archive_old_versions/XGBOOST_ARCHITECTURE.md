# 🤖 XGBoost ML 系統全方位架構文檔

**版本**: v3.4.0  
**更新日期**: 2025-10-27  
**系統狀態**: ✅ 生產就緒

---

## 📋 目錄

1. [系統概述](#系統概述)
2. [特徵工程體系](#特徵工程體系)
3. [模型學習路徑](#模型學習路徑)
4. [訓練方式](#訓練方式)
5. [參數配置](#參數配置)
6. [自動化機制](#自動化機制)
7. [高級功能](#高級功能)
8. [性能優化](#性能優化)

---

## 🎯 系統概述

### **核心職責**
```
ICT信號 → 特徵提取 → XGBoost預測 → 信心度校準 → 交易決策
    ↓                                              ↓
 歷史交易 ← 數據收集 ← 執行結果 ← 風險管理 ← 信號過濾
```

### **ML增強效果**
| 指標 | 傳統策略 | ML增強後 |
|------|---------|---------|
| **信號準確率** | 僅ICT分析 | ICT + ML預測 |
| **信心度校準** | 固定權重 | 60% ICT + 40% ML |
| **勝率優化** | 靜態閾值 | 動態學習歷史 |
| **適應能力** | 固定策略 | 自動重訓練 |

---

## 📊 特徵工程體系

### **總覽**
```
總特徵數: 29個
├── 基礎特徵: 21個 (ICT + 技術指標)
└── 增強特徵: 8個 (時間 + 交互)
```

---

### **1️⃣ 基礎特徵 (21個)**

#### **A. ICT核心特徵 (7個)**

| 特徵名稱 | 類型 | 取值範圍 | 說明 |
|---------|------|---------|------|
| `confidence_score` | float | 0.0 - 1.0 | ICT信號信心指數 |
| `leverage` | int | 3 - 20 | 動態槓桿倍數 |
| `position_value` | float | > 0 | 倉位價值 (USDT) |
| `hold_duration_hours` | float | > 0 | 持倉時長（小時） |
| `risk_reward_ratio` | float | 0.5 - 10.0 | 風險回報比 |
| `order_blocks_count` | int | 0 - 10 | 訂單塊數量 |
| `liquidity_zones_count` | int | 0 - 10 | 流動性區域數量 |

**用途**: 評估ICT策略核心要素的質量

---

#### **B. 技術指標特徵 (9個)**

| 特徵名稱 | 類型 | 取值範圍 | 指標說明 |
|---------|------|---------|---------|
| `rsi_entry` | float | 0 - 100 | RSI相對強弱指數 |
| `macd_entry` | float | 任意 | MACD快線值 |
| `macd_signal_entry` | float | 任意 | MACD慢線值 |
| `macd_histogram_entry` | float | 任意 | MACD柱狀圖 |
| `atr_entry` | float | > 0 | ATR平均真實波幅 |
| `bb_width_pct` | float | 0 - 1.0 | 布林帶寬度百分比 |
| `volume_sma_ratio` | float | > 0 | 成交量/均量比 |
| `price_vs_ema50` | float | -1.0 - 1.0 | 價格vs EMA50偏離度 |
| `price_vs_ema200` | float | -1.0 - 1.0 | 價格vs EMA200偏離度 |

**用途**: 捕捉市場技術面動量和趨勢強度

---

#### **C. 趨勢結構特徵 (5個)**

| 特徵名稱 | 編碼方式 | 取值 | 說明 |
|---------|---------|------|------|
| `trend_1h_encoded` | 序數編碼 | 1=bullish, 0=neutral, -1=bearish | 1小時趨勢 |
| `trend_15m_encoded` | 序數編碼 | 1=bullish, 0=neutral, -1=bearish | 15分鐘趨勢 |
| `trend_5m_encoded` | 序數編碼 | 1=bullish, 0=neutral, -1=bearish | 5分鐘趨勢 |
| `market_structure_encoded` | 序數編碼 | 1=bullish, 0=neutral, -1=bearish | 市場結構 |
| `direction_encoded` | 二元編碼 | 1=LONG, -1=SHORT | **倉位方向** ✅ |

**用途**: 多時間框架趨勢共振分析

---

### **2️⃣ 增強特徵 (8個)**

#### **A. 時間特徵 (3個)**

| 特徵名稱 | 類型 | 取值範圍 | 說明 |
|---------|------|---------|------|
| `hour_of_day` | int | 0 - 23 | 開倉小時 |
| `day_of_week` | int | 0 - 6 | 星期幾 (0=週一) |
| `is_weekend` | binary | 0/1 | 是否週末 |

**用途**: 捕捉時間規律（如亞洲盤vs歐美盤）

---

#### **B. 價格波動特徵 (2個)**

| 特徵名稱 | 計算公式 | 說明 |
|---------|---------|------|
| `stop_distance_pct` | `|stop_loss - entry_price| / entry_price` | 止損距離% |
| `tp_distance_pct` | `|take_profit - entry_price| / entry_price` | 止盈距離% |

**用途**: 衡量風險/回報設置的合理性

---

#### **C. 交互特徵 (3個)**

| 特徵名稱 | 計算公式 | 用途 |
|---------|---------|------|
| `confidence_x_leverage` | `confidence_score × leverage` | 信心與槓桿的複合效應 |
| `rsi_x_trend` | `rsi_entry × trend_15m_encoded` | RSI與趨勢的共振 |
| `atr_x_bb_width` | `atr_entry × bb_width_pct` | 波動率複合指標 |

**用途**: 捕捉特徵間的非線性關係

---

### **3️⃣ 目標變量**

| 變量名 | 類型 | 取值 | 說明 |
|-------|------|------|------|
| `is_winner` | binary | 0/1 | 交易是否盈利 (1=盈利, 0=虧損) |

**分類任務**: 二元分類（預測交易成功概率）

---

## 🔄 模型學習路徑

### **完整數據流**

```
┌─────────────────────────────────────────────────────────────┐
│  1. 信號生成階段                                             │
│  ICT策略分析 (1h, 15m, 5m) → 產生交易信號                    │
│  ├── 市場結構分析                                            │
│  ├── 訂單塊/流動性區域識別                                    │
│  └── 技術指標計算 (RSI, MACD, ATR, BB, EMA)                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  2. ML預測階段                                               │
│  MLPredictor.predict(signal) → 預測勝率                      │
│  ├── 特徵準備: _prepare_signal_features() (29個特徵)        │
│  ├── XGBoost預測: model.predict_proba()                     │
│  └── 輸出: {win_probability, loss_probability, ml_confidence}│
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 信心度校準階段                                            │
│  calibrate_confidence() → 最終信心度                         │
│  ├── ICT信心: 60%權重                                        │
│  ├── ML預測: 40%權重                                         │
│  └── 公式: 0.6×ICT + 0.4×ML                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  4. 交易執行階段                                              │
│  RiskManager → 計算倉位 → BinanceClient → 執行開倉           │
│  └── TradeRecorder.record_entry() → 記錄開倉數據             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  5. 平倉結果階段                                              │
│  止盈/止損觸發 → 平倉執行                                     │
│  └── TradeRecorder.record_exit() → 配對開倉，生成ML記錄      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  6. 數據持久化階段                                            │
│  完成交易 → 寫入 data/trades.json (每10筆Flush)              │
│  格式: 每行一個JSON對象 (JSONL格式)                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  7. 自動重訓練階段                                            │
│  MLPredictor.check_and_retrain_if_needed()                  │
│  觸發條件:                                                   │
│  ├── 數量觸發: 新增 ≥50筆交易                                │
│  ├── 時間觸發: 距上次訓練 ≥24小時 且 新增≥10筆                │
│  └── 性能觸發: 準確率下降 >5% 且 新增≥20筆                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  8. 模型訓練階段                                              │
│  XGBoostTrainer.train() → 生成新模型                         │
│  ├── 數據加載: load_training_data()                         │
│  ├── 特徵工程: prepare_features() (29個特徵)                │
│  ├── 訓練/測試分割: 80/20                                    │
│  ├── 模型訓練: XGBClassifier.fit()                          │
│  ├── 評估指標: Accuracy, Precision, Recall, F1, ROC-AUC    │
│  └── 保存模型: xgboost_model.pkl + model_metrics.json      │
└─────────────────────────────────────────────────────────────┘
                          ↓
                   循環回 步驟1
```

---

### **數據處理管道**

```python
# 階段1: 原始數據 → 清洗數據
MLDataProcessor.load_training_data(validate=True)
  ├── 讀取 JSONL 格式交易記錄
  ├── 移除缺失必需字段的記錄
  ├── 使用 IQR 方法移除異常值（3倍IQR）
  └── 檢查類別平衡（贏/輸比例）

# 階段2: 清洗數據 → 特徵矩陣
MLDataProcessor.prepare_features(df)
  ├── 類別編碼: trend, market_structure, direction
  ├── 增強特徵: _add_enhanced_features()
  │   ├── 時間特徵提取
  │   ├── 價格波動計算
  │   └── 交互特徵生成
  ├── 缺失值填充: fillna(0)
  └── 特徵提取: X (29個特徵), y (is_winner)

# 階段3: 特徵矩陣 → 訓練/測試集
MLDataProcessor.split_data(X, y, test_size=0.2)
  ├── 隨機分割 80/20
  ├── 分層抽樣（保持類別比例）
  └── random_state=42 (可重現)
```

---

## 🎓 訓練方式

### **1️⃣ 完整訓練 (Full Training)**

**觸發時機**:
- 首次訓練（無模型文件）
- 手動觸發完整重訓練
- 數據格式變更

**流程**:
```python
XGBoostTrainer.train(incremental=False)
  ├── 加載全部歷史數據
  ├── 從零開始訓練新模型
  ├── 耗時: 較長（數據量×計算複雜度）
  └── 輸出: 全新模型
```

**參數配置**:
```python
params = {
    'max_depth': 6,              # 樹深度
    'learning_rate': 0.1,        # 學習率
    'n_estimators': 200,         # 樹數量
    'objective': 'binary:logistic',
    'eval_metric': 'auc',
    'subsample': 0.8,            # 樣本抽樣比例
    'colsample_bytree': 0.8,     # 特徵抽樣比例
    'min_child_weight': 1,
    'gamma': 0.1,                # 分裂最小增益
    'reg_alpha': 0.1,            # L1正則化
    'reg_lambda': 1.0,           # L2正則化
    'random_state': 42,
    'n_jobs': 32,                # 並行核心數
    'tree_method': 'gpu_hist',   # GPU加速
    'predictor': 'gpu_predictor'
}
```

---

### **2️⃣ 增量學習 (Incremental Learning)**

**觸發時機**:
- 自動重訓練（有舊模型）
- 快速更新模型知識

**流程**:
```python
XGBoostTrainer.train(incremental=True)
  ├── 加載舊模型 (pickle → JSON)
  ├── 基於舊模型繼續訓練 (xgb_model參數)
  ├── 僅學習新增數據的模式
  ├── 耗時: 較短（約為完整訓練的30-50%）
  └── 輸出: 更新後的模型
```

**優勢**:
- ✅ 訓練速度快 2-3倍
- ✅ 保留歷史知識
- ✅ 適合生產環境持續學習

**關鍵代碼**:
```python
# 保存舊模型為JSON格式
old_model.save_model('temp_xgb_model.json')

# 增量訓練
model.fit(
    X_train, y_train,
    eval_set=[(X_train, y_train), (X_test, y_test)],
    early_stopping_rounds=20,
    verbose=False,
    xgb_model='temp_xgb_model.json'  # 🔑 增量學習關鍵
)
```

---

### **3️⃣ 超參數調優 (Hyperparameter Tuning)**

**觸發方式**:
```python
trainer = XGBoostTrainer(use_tuning=True)  # 啟用調優
model, metrics = trainer.train()
```

**調優策略**: RandomizedSearchCV

**搜索空間**:
```python
param_dist = {
    'max_depth': randint(4, 11),          # 4-10
    'learning_rate': uniform(0.01, 0.19), # 0.01-0.2
    'n_estimators': randint(100, 401),    # 100-400
    'subsample': uniform(0.6, 0.3),       # 0.6-0.9
    'colsample_bytree': uniform(0.6, 0.3),# 0.6-0.9
    'min_child_weight': randint(1, 8),    # 1-7
    'gamma': uniform(0, 0.3),             # 0-0.3
    'reg_alpha': uniform(0, 1.0),         # 0-1.0
    'reg_lambda': uniform(0.5, 1.5)       # 0.5-2.0
}
```

**調優配置**:
```python
RandomizedSearchCV(
    estimator=base_model,
    param_distributions=param_dist,
    n_iter=10,              # 快速調優10次
    scoring='roc_auc',      # 優化目標: ROC-AUC
    cv=3,                   # 3折交叉驗證
    n_jobs=32,              # 32核並行
    random_state=42
)
```

**耗時**: 約為普通訓練的 3-5倍

---

### **4️⃣ 模型集成 (Ensemble Learning)** 🚀

**觸發方式**:
```python
trainer = XGBoostTrainer(use_ensemble=True)
ensemble, metrics = trainer.train_with_ensemble()
```

**集成策略**: 加權平均（基於ROC-AUC）

**支持的模型**:
1. **XGBoost** (主力模型)
2. **LightGBM** (速度優化)
3. **CatBoost** (類別特徵優化)

**權重計算**:
```python
# 基於驗證集ROC-AUC分配權重
weights = {
    'xgboost': 0.45,   # AUC=0.85
    'lightgbm': 0.30,  # AUC=0.82
    'catboost': 0.25   # AUC=0.80
}

# 集成預測
ensemble_proba = (
    0.45 × xgb_proba +
    0.30 × lgb_proba +
    0.25 × cat_proba
)
```

**性能提升**: 集成模型通常比單一模型準確率提升 2-5%

---

## ⚙️ 參數配置詳解

### **1️⃣ 默認參數 (Default Params)**

```python
{
    # === 樹結構參數 ===
    'max_depth': 6,
    # 說明: 樹的最大深度，控制模型複雜度
    # 範圍: 3-10（典型值）
    # 調優: 數據量大可增加，過擬合風險高則降低
    
    'min_child_weight': 1,
    # 說明: 葉節點最小樣本權重和
    # 範圍: 1-7
    # 調優: 增加以防止過擬合
    
    'gamma': 0.1,
    # 說明: 節點分裂所需最小損失減少
    # 範圍: 0-0.3
    # 調優: 增加使模型更保守
    
    # === 學習參數 ===
    'learning_rate': 0.1,
    # 說明: 每棵樹的貢獻權重（收縮率）
    # 範圍: 0.01-0.3
    # 調優: 較小值需增加n_estimators
    
    'n_estimators': 200,
    # 說明: 提升樹的數量
    # 範圍: 100-400
    # 調優: 配合learning_rate調整
    
    # === 抽樣參數 ===
    'subsample': 0.8,
    # 說明: 訓練每棵樹時的樣本抽樣比例
    # 範圍: 0.6-1.0
    # 用途: 防止過擬合，增加泛化能力
    
    'colsample_bytree': 0.8,
    # 說明: 訓練每棵樹時的特徵抽樣比例
    # 範圍: 0.6-1.0
    # 用途: 減少特徵間相關性影響
    
    # === 正則化參數 ===
    'reg_alpha': 0.1,
    # 說明: L1正則化係數（Lasso）
    # 範圍: 0-1.0
    # 用途: 特徵選擇，稀疏解
    
    'reg_lambda': 1.0,
    # 說明: L2正則化係數（Ridge）
    # 範圍: 0.5-2.0
    # 用途: 權重平滑，防止過擬合
    
    # === 任務參數 ===
    'objective': 'binary:logistic',
    # 說明: 學習目標函數
    # 選項: binary:logistic (二元分類)
    
    'eval_metric': 'auc',
    # 說明: 驗證集評估指標
    # 選項: auc, logloss, error
    
    # === 系統參數 ===
    'random_state': 42,
    # 說明: 隨機種子，保證可重現性
    
    'n_jobs': 32,
    # 說明: 並行線程數
    # 設置: CPU核心數
    
    'tree_method': 'gpu_hist',
    # 說明: 樹構建算法
    # 選項: gpu_hist (GPU), hist (CPU), exact
    
    'predictor': 'gpu_predictor'
    # 說明: 預測器類型
    # 選項: gpu_predictor (GPU), cpu_predictor
}
```

---

### **2️⃣ 訓練控制參數**

```python
model.fit(
    X_train, y_train,
    eval_set=[(X_train, y_train), (X_test, y_test)],
    early_stopping_rounds=20,
    # 說明: 若20輪驗證集無改善則提前停止
    # 用途: 防止過擬合，節省時間
    
    verbose=False
    # 說明: 不輸出訓練過程日誌
)
```

---

### **3️⃣ 自適應參數 (AdaptiveLearner)**

**動態學習率調整**:
```python
# 性能持續提升 → 增加學習率（探索）
if consecutive_improvements >= 2:
    new_lr = min(current_lr × 1.2, max_lr)  # 最高0.3
    
# 性能持續下降 → 降低學習率（保守）
if consecutive_degradations >= 2:
    new_lr = max(current_lr × 0.7, min_lr)  # 最低0.01
```

**動態樹數量調整**:
```python
# 訓練時間過長（>60秒）→ 減少樹數量
if training_time > 60:
    new_n = max(current_n - 50, 100)
    
# 性能優秀且訓練快速 → 增加樹數量
if accuracy > 0.80 and training_time < 30:
    new_n = min(current_n + 50, 400)
```

---

## 🤖 自動化機制

### **1️⃣ 自動重訓練 (Auto Retraining)**

**檢查邏輯**:
```python
MLPredictor.check_and_retrain_if_needed()
  ├── 加載當前數據量
  ├── 計算新增樣本數
  └── 檢查觸發條件:
      ├── 數量觸發: new_samples >= 50
      ├── 時間觸發: hours >= 24 AND new_samples >= 10
      └── 性能觸發: accuracy_drop > 5% AND new_samples >= 20
```

**執行頻率**: 每次主循環迭代（約每1-5分鐘）

**重訓練流程**:
```
檢測到觸發條件
  ↓
記錄日誌: "🔄 觸發重訓練 (原因: ...)"
  ↓
執行訓練: trainer.train(incremental=True)
  ↓
保存模型: save_model(model, metrics)
  ↓
更新計數器: last_training_samples, last_training_time
  ↓
記錄日誌: "✅ 模型重訓練完成！準確率: XX%"
```

---

### **2️⃣ 冷啟動處理 (Cold Start)**

**場景**: 首次運行，無歷史數據

**處理邏輯**:
```python
MLPredictor.initialize()
  ├── 嘗試加載模型: load_model()
  │   └── 模型不存在
  ├── 檢查數據量: len(df) < 100
  │   └── 數據不足，跳過訓練
  └── 返回狀態: is_ready = False

# 主循環行為
if not ml_predictor.is_ready:
    # 使用純ICT策略，不進行ML預測
    confidence = ict_confidence  # 無ML校準
```

**數據累積**:
```
0-100筆交易: 純ICT模式，收集數據
  ↓
達到100筆: 自動觸發首次訓練
  ↓
訓練完成: 啟用ML增強模式
```

---

### **3️⃣ 數據持久化 (Data Persistence)**

**Flush策略**: 智能批量寫入

```python
TradeRecorder._check_and_flush()
  ├── 檢查內存記錄數: len(completed_trades)
  ├── 達到閾值（10筆）→ 觸發Flush
  └── _flush_to_disk()
      ├── 追加寫入: data/trades.json
      ├── 格式: JSONL (每行一個JSON)
      └── 清空內存: completed_trades = []
```

**文件格式**:
```json
{"symbol": "BTCUSDT", "direction": "LONG", "pnl_pct": 0.015, "is_winner": true, ...}
{"symbol": "ETHUSDT", "direction": "SHORT", "pnl_pct": -0.008, "is_winner": false, ...}
```

**優勢**:
- ✅ 減少磁盤I/O（批量寫入）
- ✅ 防止數據丟失（定期Flush）
- ✅ 易於增量讀取（JSONL格式）

---

## 🚀 高級功能

### **1️⃣ 超參數調優器 (HyperparameterTuner)**

**快速調優模式**:
```python
HyperparameterTuner.quick_tune(X_train, y_train, use_gpu=True)
  ├── 迭代次數: 10
  ├── 交叉驗證: 3-fold
  ├── 並行任務: 32核
  └── 優化目標: ROC-AUC
```

**完整調優模式**:
```python
HyperparameterTuner.tune(
    X_train, y_train,
    n_iter=20,      # 20次迭代
    cv=5,           # 5折交叉驗證
    n_jobs=32,
    use_gpu=True
)
```

**輸出示例**:
```
============================================================
✅ 超參數調優完成
   調優耗時: 45.23秒
   最佳ROC-AUC: 0.8765
   最佳參數:
     max_depth: 7
     learning_rate: 0.085
     n_estimators: 285
     subsample: 0.75
     colsample_bytree: 0.82
     min_child_weight: 3
     gamma: 0.15
     reg_alpha: 0.42
     reg_lambda: 1.23
============================================================
```

---

### **2️⃣ 自適應學習器 (AdaptiveLearner)**

**性能追蹤**:
```python
AdaptiveLearner.update_performance(accuracy, timestamp)
  ├── 記錄到歷史: performance_history (最近10次)
  ├── 檢測趨勢: 持續提升 / 持續下降 / 穩定
  └── 調整參數: learning_rate, n_estimators
```

**智能觸發**:
```python
AdaptiveLearner.should_retrain(new_samples, hours_since_training)
  ├── 基礎規則:
  │   ├── new_samples >= 50 → True
  │   └── hours >= 24 AND new_samples >= 10 → True
  └── 自適應規則:
      └── accuracy < avg - 5% AND new_samples >= 20 → True
```

**統計信息**:
```python
stats = AdaptiveLearner.get_stats()
# {
#   'history_size': 8,
#   'avg_accuracy': 0.7825,
#   'best_accuracy': 0.8156,
#   'worst_accuracy': 0.7421,
#   'current_lr': 0.12,
#   'current_n_estimators': 250,
#   'consecutive_improvements': 2,
#   'consecutive_degradations': 0
# }
```

---

### **3️⃣ 模型集成 (EnsembleModel)**

**訓練流程**:
```python
EnsembleModel.train_ensemble(X_train, y_train, X_test, y_test)
  ├── 訓練 XGBoost
  │   ├── 參數: max_depth=6, lr=0.1, n_est=200
  │   └── 性能: Accuracy=0.82, AUC=0.85
  ├── 訓練 LightGBM
  │   ├── 參數: max_depth=6, lr=0.1, n_est=200
  │   └── 性能: Accuracy=0.80, AUC=0.82
  ├── 訓練 CatBoost
  │   ├── 參數: depth=6, lr=0.1, iter=200
  │   └── 性能: Accuracy=0.79, AUC=0.80
  ├── 計算權重: 基於AUC歸一化
  │   ├── XGBoost: 0.85/(0.85+0.82+0.80) = 0.344
  │   ├── LightGBM: 0.82/2.47 = 0.332
  │   └── CatBoost: 0.80/2.47 = 0.324
  └── 集成評估: Accuracy=0.84, AUC=0.87 ✅
```

**預測方式**:
```python
ensemble_proba = EnsembleModel.predict_proba(X)
  ├── 各模型獨立預測
  ├── 加權平均: np.average(predictions, weights=weights)
  └── 返回集成概率
```

**保存/加載**:
```python
# 保存
ensemble.save('ensemble_model.pkl')  # 包含所有模型+權重

# 加載
ensemble.load('ensemble_model.pkl')
```

---

## ⚡ 性能優化

### **1️⃣ GPU加速**

**自動檢測**:
```python
def _detect_gpu():
    try:
        subprocess.check_output(['nvidia-smi'])
        return True
    except:
        return False
```

**GPU配置**:
```python
if use_gpu and _detect_gpu():
    params['tree_method'] = 'gpu_hist'      # 快10-100倍
    params['predictor'] = 'gpu_predictor'   # GPU預測
else:
    params['tree_method'] = 'hist'          # CPU優化版
```

**性能對比**:
| 環境 | 訓練時間 (200樣本) | 加速比 |
|------|------------------|--------|
| CPU (32核) | ~15秒 | 1x |
| GPU (NVIDIA) | ~1.5秒 | 10x |

---

### **2️⃣ 增量學習加速**

**對比**:
| 訓練方式 | 耗時 | 適用場景 |
|---------|------|---------|
| 完整訓練 | 100% | 首次訓練、數據格式變更 |
| 增量學習 | 30-50% | 自動重訓練、持續學習 |

**實現**:
```python
# 加載舊模型
old_model.save_model('temp.json')

# 繼續訓練（不是從零開始）
model.fit(..., xgb_model='temp.json')
```

---

### **3️⃣ 並行計算**

**多核並行**:
```python
params['n_jobs'] = 32  # 使用32個CPU核心
```

**交叉驗證並行**:
```python
RandomizedSearchCV(..., n_jobs=32)  # 32倍加速
```

---

### **4️⃣ Early Stopping**

**防止過度訓練**:
```python
model.fit(
    ...,
    early_stopping_rounds=20
    # 驗證集20輪無改善 → 自動停止
)
```

**效果**:
- ✅ 節省訓練時間 20-40%
- ✅ 防止過擬合
- ✅ 自動找到最佳迭代次數

---

## 📈 評估指標

### **訓練時輸出**

```python
metrics = {
    'training_samples': 450,       # 總訓練樣本數
    'accuracy': 0.8156,            # 準確率
    'precision': 0.7892,           # 精確率
    'recall': 0.8421,              # 召回率
    'f1_score': 0.8147,            # F1分數
    'roc_auc': 0.8534,             # ROC-AUC
    'train_set_size': 360,         # 訓練集大小
    'test_set_size': 90,           # 測試集大小
    'confusion_matrix': [          # 混淆矩陣
        [38, 12],  # TN=38, FP=12
        [7, 33]    # FN=7,  TP=33
    ],
    'feature_importance': {        # 特徵重要性
        'confidence_score': 0.145,
        'rsi_entry': 0.098,
        'trend_15m_encoded': 0.087,
        ...
    },
    'training_time_seconds': 8.52, # 訓練耗時
    'incremental': True,           # 是否增量訓練
    'trained_at': '2025-10-27T10:30:00'  # 訓練時間
}
```

---

## 📂 文件結構

```
data/
├── trades.json                # 歷史交易數據 (JSONL格式)
├── ml_pending.json            # 待配對的開倉記錄
└── models/
    ├── xgboost_model.pkl      # 主模型
    ├── model_metrics.json     # 模型評估指標
    ├── ensemble_model.pkl     # 集成模型（可選）
    └── temp_xgb_model.json    # 增量學習臨時文件

src/ml/
├── model_trainer.py           # 模型訓練器
├── data_processor.py          # 數據處理器
├── predictor.py               # ML預測服務
├── hyperparameter_tuner.py    # 超參數調優器
├── adaptive_learner.py        # 自適應學習器
└── ensemble_model.py          # 模型集成系統
```

---

## 🔧 使用示例

### **1. 啟用ML預測**
```python
# 初始化
ml_predictor = MLPredictor()
ml_predictor.initialize()

# 預測信號
ml_result = ml_predictor.predict(signal)
# {
#   'predicted_class': 1,
#   'win_probability': 0.78,
#   'loss_probability': 0.22,
#   'ml_confidence': 0.78
# }

# 校準信心度
final_confidence = ml_predictor.calibrate_confidence(
    traditional_confidence=0.85,
    ml_prediction=ml_result
)
# 0.85×0.6 + 0.78×0.4 = 0.822
```

---

### **2. 手動訓練模型**
```python
trainer = XGBoostTrainer()

# 默認訓練
model, metrics = trainer.train()

# 啟用GPU + 增量學習
model, metrics = trainer.train(use_gpu=True, incremental=True)

# 啟用超參數調優
trainer = XGBoostTrainer(use_tuning=True)
model, metrics = trainer.train()

# 啟用模型集成
trainer = XGBoostTrainer(use_ensemble=True)
ensemble, metrics = trainer.train_with_ensemble()
```

---

### **3. 自動重訓練**
```python
# 主循環中自動檢查
if ml_predictor.is_ready:
    success = ml_predictor.check_and_retrain_if_needed()
    if success:
        logger.info("模型已自動更新")
```

---

## ✅ 最佳實踐

### **數據質量**
- ✅ 至少100筆交易後再啟用ML
- ✅ 保持類別平衡（勝率30-70%）
- ✅ 定期檢查異常值

### **訓練策略**
- ✅ 生產環境使用增量學習
- ✅ 每週執行一次完整訓練
- ✅ 性能下降時觸發調優

### **監控指標**
- ✅ 關注ROC-AUC（>0.75為良好）
- ✅ 監控準確率趨勢
- ✅ 檢查特徵重要性變化

---

**文檔版本**: v3.4.0  
**最後更新**: 2025-10-27  
**維護者**: Trading Bot Team
