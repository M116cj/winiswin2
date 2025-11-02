# 📊 XGBoost 訓練數據格式說明

## 概述

本文檔說明 v3.0 系統生成的 XGBoost 訓練數據格式。系統通過 `DataArchiver` 模組自動記錄所有交易信號和倉位，為機器學習模型提供完整的訓練數據。

---

## 📁 數據文件

系統生成 2 個主要的 CSV 文件：

### 1. `ml_data/signals.csv` - 交易信號記錄
記錄所有生成的交易信號，包括被接受和被拒絕的信號。

### 2. `ml_data/positions.csv` - 倉位生命週期
記錄所有倉位（實際 + 虛擬）的完整生命週期，從開倉到平倉。

---

## 📋 Signals.csv 數據格式

### 欄位說明

#### 基本信息
- `timestamp`: 信號生成時間
- `symbol`: 交易對（如 BTCUSDT）
- `direction`: 方向（LONG/SHORT）
- `confidence`: 總信心度（0-1）
- `accepted`: 是否被接受（True/False）
- `rejection_reason`: 拒絕原因（如果被拒絕）

#### 五維評分 (核心特徵)
- `trend_alignment_score`: 趨勢對齊分數（0-1，權重 40%）
- `market_structure_score`: 市場結構分數（0-1，權重 20%）
- `price_position_score`: 價格位置分數（0-1，權重 20%）
- `momentum_score`: 動量分數（0-1，權重 10%）
- `volatility_score`: 波動率分數（0-1，權重 10%）

#### 時間框架趨勢
- `h1_trend`: 1 小時趨勢（BULLISH/BEARISH/NEUTRAL）
- `m15_trend`: 15 分鐘趨勢
- `m5_trend`: 5 分鐘趨勢

#### 價格信息
- `current_price`: 當前價格
- `entry_price`: 建議入場價
- `stop_loss`: 止損價
- `take_profit`: 止盈價

#### 技術指標
- `rsi`: RSI 指標值
- `macd`: MACD 值
- `macd_signal`: MACD 信號線
- `atr`: ATR（平均真實波幅）
- `bb_width_pct`: 布林帶寬度百分位

#### Order Block 信息
- `order_blocks_count`: 檢測到的 Order Block 數量
- `liquidity_zones_count`: 流動性區域數量

### 示例數據

```csv
timestamp,symbol,direction,confidence,accepted,rejection_reason,trend_alignment_score,...
2025-10-18 16:38:34,SOLUSDT,LONG,0.6863,True,,0.5622,0.9754,0.7856,0.5987,0.4936,...
2025-10-18 17:38:34,BNBUSDT,LONG,0.5794,True,,0.6024,0.6456,0.6895,0.1395,0.5753,...
2025-10-18 18:38:34,BNBUSDT,LONG,0.5116,False,信心度不足,0.5698,0.508,0.3847,0.241,0.81,...
```

### 數據統計
- 總信號數: 100+
- 被接受率: 約 70-85%（取決於 `MIN_CONFIDENCE` 設置）
- 被拒絕原因: 信心度不足、期望值為負、風險管理限制等

---

## 📈 Positions.csv 數據格式

### 欄位說明

#### 基本信息
- `event`: 事件類型（OPEN/CLOSE）
- `timestamp`: 事件時間
- `position_id`: 倉位唯一 ID
- `is_virtual`: 是否為虛擬倉位（True/False）
- `symbol`: 交易對
- `direction`: 方向（LONG/SHORT）

#### 價格信息
- `entry_price`: 入場價
- `exit_price`: 出場價（僅平倉記錄）
- `stop_loss`: 止損價
- `take_profit`: 止盈價

#### 交易信息
- `quantity`: 數量
- `leverage`: 槓桿倍數
- `confidence`: 開倉時的信心度

#### 盈虧信息（僅平倉記錄）
- `pnl`: 盈虧金額
- `pnl_pct`: 盈虧百分比
- `close_reason`: 平倉原因（TAKE_PROFIT/STOP_LOSS/MANUAL）
- `won`: 是否盈利（True/False）

#### 五維評分（與信號相同）
- `trend_alignment_score`
- `market_structure_score`
- `price_position_score`
- `momentum_score`
- `volatility_score`

#### 技術指標（開倉時的快照）
- `rsi`
- `macd`
- `atr`
- `bb_width_pct`

#### Order Block 信息
- `order_blocks_count`
- `liquidity_zones_count`

#### 其他
- `holding_duration_minutes`: 持倉時長（分鐘，僅平倉記錄）

### 示例數據

#### 開倉記錄
```csv
event,timestamp,position_id,is_virtual,symbol,direction,entry_price,...
OPEN,2025-10-18 16:38:34,POS_0000,True,SOLUSDT,LONG,47319.94,...
```

#### 平倉記錄
```csv
event,timestamp,position_id,is_virtual,symbol,direction,entry_price,exit_price,...,pnl,pnl_pct,close_reason,won,...
CLOSE,2025-10-19 07:38:34,POS_0000,True,SOLUSDT,LONG,47319.94,47887.78,...,9.31,1.2,TAKE_PROFIT,True,...
```

### 數據統計
- 開倉/平倉記錄數: 各 50+
- 勝率: 約 55-65%（取決於策略表現）
- 實際倉位: 約 20-30%
- 虛擬倉位: 約 70-80%

---

## 🤖 XGBoost 訓練數據準備

### 特徵選擇

從 `positions.csv` 的平倉記錄中提取以下特徵：

#### 核心特徵（14 個）

1. **五維評分** (5 個)
   - trend_alignment_score
   - market_structure_score
   - price_position_score
   - momentum_score
   - volatility_score

2. **信心度** (1 個)
   - confidence

3. **技術指標** (4 個)
   - rsi
   - macd
   - atr
   - bb_width_pct

4. **Order Block** (2 個)
   - order_blocks_count
   - liquidity_zones_count

5. **額外計算特徵** (2 個)
   - risk_reward_ratio: (TP - Entry) / (Entry - SL)
   - leverage: 槓桿倍數

### 目標變量

- **y (won)**: 是否盈利（1 = 盈利，0 = 虧損）

### 訓練數據示例

```csv
trend_alignment_score,market_structure_score,...,leverage,won
0.5714,0.8254,0.4338,0.8054,0.9693,0.6835,30.03,98.44,...,12,1
0.7962,0.5232,0.7645,0.4194,0.5325,0.7557,67.96,93.13,...,16,0
0.6559,0.7600,0.7280,0.4294,0.9848,0.8150,61.01,87.90,...,6,0
```

---

## 💻 使用示例

### 1. 讀取數據

```python
import pandas as pd

# 讀取信號數據
signals_df = pd.read_csv('ml_data/signals.csv')
print(f"總信號數: {len(signals_df)}")
print(f"被接受: {signals_df['accepted'].sum()}")

# 讀取倉位數據
positions_df = pd.read_csv('ml_data/positions.csv')

# 只取平倉記錄
closed_positions = positions_df[positions_df['event'] == 'CLOSE']
print(f"平倉記錄數: {len(closed_positions)}")
print(f"勝率: {closed_positions['won'].mean():.2%}")
```

### 2. 準備訓練數據

```python
# 特徵列
feature_columns = [
    'trend_alignment_score', 'market_structure_score',
    'price_position_score', 'momentum_score', 'volatility_score',
    'confidence', 'rsi', 'macd', 'atr', 'bb_width_pct',
    'order_blocks_count', 'liquidity_zones_count'
]

# 準備特徵矩陣
X = closed_positions[feature_columns].copy()

# 添加計算特徵
X['risk_reward_ratio'] = (
    (closed_positions['take_profit'] - closed_positions['entry_price']) / 
    (closed_positions['entry_price'] - closed_positions['stop_loss'])
).abs()
X['leverage'] = closed_positions['leverage']

# 目標變量
y = closed_positions['won'].astype(int)

print(f"樣本數: {len(X)}")
print(f"特徵數: {len(X.columns)}")
print(f"正樣本率: {y.mean():.2%}")
```

### 3. 訓練 XGBoost 模型

```python
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

# 分割數據
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# 創建 DMatrix
dtrain = xgb.DMatrix(X_train, label=y_train)
dtest = xgb.DMatrix(X_test, label=y_test)

# 設置參數
params = {
    'objective': 'binary:logistic',
    'max_depth': 6,
    'learning_rate': 0.1,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'eval_metric': 'logloss'
}

# 訓練
model = xgb.train(
    params, dtrain,
    num_boost_round=100,
    evals=[(dtrain, 'train'), (dtest, 'test')],
    early_stopping_rounds=10,
    verbose_eval=10
)

# 預測
y_pred_proba = model.predict(dtest)
y_pred = (y_pred_proba > 0.5).astype(int)

# 評估
print(f"準確率: {accuracy_score(y_test, y_pred):.4f}")
print(classification_report(y_test, y_pred))
```

### 4. 使用模型預測新信號

```python
def predict_signal_win_probability(signal_features, model):
    """
    預測信號的獲勝概率
    
    Args:
        signal_features: dict，包含所有特徵
        model: 訓練好的 XGBoost 模型
    
    Returns:
        float: 獲勝概率 (0-1)
    """
    # 轉換為 DataFrame
    X_new = pd.DataFrame([signal_features])
    
    # 創建 DMatrix
    dnew = xgb.DMatrix(X_new)
    
    # 預測
    win_prob = model.predict(dnew)[0]
    
    return win_prob

# 示例
new_signal = {
    'trend_alignment_score': 0.85,
    'market_structure_score': 0.90,
    'price_position_score': 0.75,
    'momentum_score': 0.70,
    'volatility_score': 0.80,
    'confidence': 0.82,
    'rsi': 55.0,
    'macd': 50.0,
    'atr': 800.0,
    'bb_width_pct': 45.0,
    'order_blocks_count': 3,
    'liquidity_zones_count': 2,
    'risk_reward_ratio': 2.5,
    'leverage': 10
}

win_prob = predict_signal_win_probability(new_signal, model)
print(f"獲勝概率: {win_prob:.2%}")

if win_prob > 0.65:
    print("✅ 建議接受此信號")
elif win_prob > 0.50:
    print("⚠️  信號質量中等")
else:
    print("❌ 建議拒絕此信號")
```

---

## 📊 特徵重要性分析

訓練後，可以查看特徵重要性：

```python
# 獲取特徵重要性
importance = model.get_score(importance_type='weight')

# 排序並打印
for feature, score in sorted(importance.items(), key=lambda x: x[1], reverse=True):
    print(f"{feature}: {score}")
```

預期重要性排序（根據策略設計）：
1. `trend_alignment_score` (40% 權重)
2. `confidence` (總體信心度)
3. `market_structure_score` (20% 權重)
4. `price_position_score` (20% 權重)
5. `risk_reward_ratio` (計算特徵)
6. 其他技術指標...

---

## 🔄 實時訓練流程

### v3.0 當前狀態
- ✅ 數據歸檔已完全自動化
- ✅ 所有特徵已記錄
- ✅ 實際 + 虛擬倉位都被追蹤
- ⏳ XGBoost 自動訓練（計劃在 v3.1 實現）

### v3.1 計劃
1. **自動觸發訓練**
   - 每累計 100 筆新交易後重新訓練
   - 每週定期重新訓練

2. **模型版本管理**
   - 保存多個模型版本
   - A/B 測試比較性能

3. **實時預測集成**
   - 在信號生成時調用模型
   - 將 ML 預測作為額外的評分維度

4. **反饋循環**
   - 根據實際交易結果調整模型
   - 動態調整特徵權重

---

## 📂 文件位置

### 實際數據（生產環境）
- `ml_data/signals.csv`
- `ml_data/positions.csv`

### 示例數據（學習參考）
- `examples/example_signals.csv`
- `examples/example_positions.csv`
- `examples/example_xgboost_training.csv`

### 代碼
- `examples/xgboost_data_example.py` - 完整示例代碼
- `src/ml/data_archiver.py` - 數據歸檔器源碼

---

## ⚠️ 注意事項

1. **數據累積**
   - 建議至少累積 100 筆交易後再訓練模型
   - 更多數據 = 更好的模型性能

2. **特徵工程**
   - 可以根據需要添加更多計算特徵
   - 例如：時間特徵、市場狀態、相關性等

3. **過擬合防範**
   - 使用交叉驗證
   - 設置 early_stopping
   - 調整 subsample 和 colsample_bytree

4. **數據平衡**
   - 注意正負樣本比例
   - 如果不平衡，考慮使用 `scale_pos_weight` 參數

5. **實時性**
   - 訓練可能需要幾分鐘
   - 考慮在低流量時段進行

---

## 🎯 總結

v3.0 系統已經為 XGBoost 機器學習做好了充分準備：

✅ **完整的數據記錄**
- 所有信號（接受 + 拒絕）
- 所有倉位（實際 + 虛擬）
- 完整的市場狀態快照

✅ **高質量的特徵**
- 五維評分系統
- 豐富的技術指標
- Order Block 信息

✅ **清晰的目標變量**
- 是否盈利（won）
- 盈虧百分比（pnl_pct）

✅ **易於使用**
- 標準 CSV 格式
- 清晰的數據結構
- 完整的示例代碼

**下一步**: 開始累積交易數據，待數據充足後即可訓練第一個 XGBoost 模型！
