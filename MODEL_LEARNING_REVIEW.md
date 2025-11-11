# 模型學習渠道與功能設定審查報告
## SelfLearningTrader ML System Review v4.0

生成時間：2025-11-11  
系統版本：v4.0 (Feature Unification)

---

## 📊 執行摘要

### ⚠️ 關鍵發現

1. **🔒 模型訓練已鎖定**  
   - `DISABLE_MODEL_TRAINING=true`（預設啟用）
   - **初始訓練和重訓練均已禁用**
   - 系統將使用預訓練模型（若存在），否則回退至純規則引擎

2. **🔥 Architect識別的5大致命缺陷**（進度跟蹤）  
   - ❌ XGBoost過度複雜（100樹/深度6 vs 200樣本）→ **待修復**
   - ❌ 78%特徵浪費（12/56使用）→ **v4.0已修復**（統一12特徵）
   - ❌ Bootstrap接受20%勝率 → **待修復**
   - ❌ 信號質量公式RR主導 → **待修復**
   - ❌ 默認禁用訓練 → **待評估**（需確認是否適合生產）

---

## 🎯 一、模型學習渠道架構

### 1.1 初始訓練流程（ModelInitializer）

```
啟動檢查
   ↓
檢測 initialized.flag
   ↓ (不存在)
收集訓練數據 (200+樣本)
   ├─ PostgreSQL 真實交易數據（優先）
   ├─ trades.jsonl 歷史數據（備援）
   └─ 市場數據合成樣本（補足）
   ↓
訓練 XGBoost 模型
   ├─ 12個ICT/SMC特徵 (v4.0統一)
   ├─ 生產級參數（見下文）
   └─ 保存至 models/xgboost_model.json
   ↓
創建 initialized.flag
   ↓
✅ 系統就緒
```

**📁 關鍵文件**：
- `src/core/model_initializer.py` - 初始訓練邏輯
- `models/xgboost_model.json` - 訓練好的模型
- `models/initialized.flag` - 初始化標記

**🔒 當前狀態**：
```python
DISABLE_MODEL_TRAINING = true  # 初始訓練已禁用
```

---

### 1.2 在線重訓練流程（OnlineLearningManager）

```
定期檢查（每24小時）
   ↓
觸發條件檢測
   ├─ 定期重訓練（24小時）
   ├─ 模型漂移（性能下降>15%）
   └─ 市場狀態劇變（regime shift）
   ↓
收集最新交易數據
   ↓
重新訓練模型
   ↓
更新 baseline_performance
   ↓
reload MLModelWrapper
```

**📁 關鍵文件**：
- `src/ml/online_learning.py` - 在線學習管理器
- `src/core/model_initializer.py` - `retrain()` 方法

**🔒 當前狀態**：
```python
DISABLE_MODEL_TRAINING = true  # 重訓練已禁用
```

**⚠️ 重要**：即使 `OnlineLearningManager` 正常運行，由於 `DISABLE_MODEL_TRAINING=true`，所有重訓練請求將被拒絕。

---

### 1.3 預測推理流程（MLModelWrapper）

```
信號生成（RuleBasedSignalGenerator）
   ↓
提取12個ICT/SMC特徵
   ├─ market_structure
   ├─ order_blocks_count
   ├─ institutional_candle
   ├─ liquidity_grab
   ├─ order_flow
   ├─ fvg_count
   ├─ trend_alignment_enhanced
   ├─ swing_high_distance
   ├─ structure_integrity
   ├─ institutional_participation
   ├─ timeframe_convergence
   └─ liquidity_context
   ↓
MLModelWrapper.predict_from_signal()
   ↓
XGBoost 預測勝率（0-1）
   ↓
與規則引擎信心值混合
   ↓
最終交易決策
```

**📁 關鍵文件**：
- `src/ml/model_wrapper.py` - 預測包裝器
- `src/ml/feature_schema.py` - 統一特徵定義

**✅ 當前狀態**：**正常運行**（不受 `DISABLE_MODEL_TRAINING` 影響）

---

## 🧠 二、ML模型配置

### 2.1 XGBoost 超參數（v3.18.6+生產級）

```python
# 🌱 樹結構（控制複雜度）
n_estimators: 100          # 樹數量
max_depth: 6               # 樹深度
min_child_weight: 10       # 葉節點最小樣本權重

# ⚖️ 正則化（提升泛化）
gamma: 0.1                 # 分裂最小損失減少
subsample: 0.8             # 訓練樣本採樣率（80%）
colsample_bytree: 0.8      # 特徵採樣率（80%）

# 🚀 學習率
learning_rate: 0.1         # 學習步長

# 🎯 目標函數
objective: 'binary:logistic'  # 邏輯迴歸損失
eval_metric: 'logloss'        # 評估指標

# 🧠 其他
random_state: 42           # 可重現性
n_jobs: -1                 # 多核心加速
verbosity: 0               # 靜默模式
```

**📊 環境變量覆蓋**（可選）：
```bash
XGBOOST_N_ESTIMATORS=100
XGBOOST_MAX_DEPTH=6
XGBOOST_MIN_CHILD_WEIGHT=10
XGBOOST_GAMMA=0.1
XGBOOST_SUBSAMPLE=0.8
XGBOOST_COLSAMPLE=0.8
XGBOOST_LEARNING_RATE=0.1
```

---

### 2.2 訓練數據要求

```python
# 最小訓練樣本數
min_samples: 200                      # 預設200筆
lookback_days: 30                     # 回溯30天

# 環境變量覆蓋
INITIAL_TRAINING_SAMPLES=200
INITIAL_TRAINING_LOOKBACK_DAYS=30
```

**📊 數據來源優先級**：
1. **PostgreSQL** - `trades` 表（12個ICT/SMC特徵 + outcome）
2. **trades.jsonl** - 歷史交易記錄（向後兼容）
3. **市場數據合成** - 實時K線 + 簡單規則標註

---

### 2.3 特徵Schema（v4.0統一）

**12個標準特徵**（`CANONICAL_FEATURE_NAMES`）：

| 特徵名稱 | 類型 | 說明 | 預設值 |
|---------|------|------|--------|
| `market_structure` | float | 市場結構（1=看漲/-1=看跌/0=中性） | 0.0 |
| `order_blocks_count` | int | 訂單塊數量 | 0.0 |
| `institutional_candle` | int | 機構蠟燭（0/1） | 0.0 |
| `liquidity_grab` | int | 流動性掃單（0/1） | 0.0 |
| `order_flow` | float | 訂單流強度 | 0.0 |
| `fvg_count` | int | 公平價值缺口數量 | 0.0 |
| `trend_alignment_enhanced` | float | 趨勢對齊度（0-1） | 0.0 |
| `swing_high_distance` | float | 距離擺動高點 | 0.0 |
| `structure_integrity` | float | 結構完整性（0-1） | 0.5 |
| `institutional_participation` | float | 機構參與度（0-1） | 0.0 |
| `timeframe_convergence` | float | 時間框架收斂（0-1） | 0.5 |
| `liquidity_context` | float | 流動性上下文（0-1） | 0.5 |

**✅ v4.0修復**：
- 訓練和預測使用**完全相同**的12個特徵
- 解決了v3.x的特徵不一致問題（訓練44個 vs 預測12個）

---

## 🎓 三、Bootstrap豁免期機制

### 3.1 豁免期設定

```python
# 豁免期交易數
BOOTSTRAP_TRADE_LIMIT: 50             # 前50筆交易（v3.19縮短）

# 豁免期門檻（降低要求）
BOOTSTRAP_MIN_WIN_PROBABILITY: 0.20   # 勝率 20%（正常期45%）
BOOTSTRAP_MIN_CONFIDENCE: 0.25        # 信心 25%（正常期40%）
BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD: 0.25  # 質量 25%（正常期40%）

# 豁免期槓桿限制
槓桿範圍: 1-3x（強制壓制）           # 正常期無上限
```

**📊 設計目的**：
1. **加速冷啟動** - 允許模型在數據不足時也能開始交易
2. **風險控制** - 低槓桿限制（1-3x）防止初期虧損過大
3. **數據累積** - 快速收集真實交易數據用於後續訓練

**⚠️ Architect警告**：
- **20%勝率過低**：接受"10次交易失敗8次"的策略
- **建議**：將豁免期勝率提升至 30-45%，逐步過渡

---

### 3.2 正常期門檻

```python
# 正常期門檻（第51筆交易開始）
MIN_WIN_PROBABILITY: 0.45             # 勝率 45%（v3.20.7修復）
MIN_CONFIDENCE: 0.40                  # 信心 40%（v3.20.7修復）
SIGNAL_QUALITY_THRESHOLD: 0.40        # 質量 40%（v3.20.7修復）

# 槓桿控制
槓桿範圍: 無上限（由模型動態決定）
最大槓桿: 基於 勝率 × 信心度 計算
```

---

## 🔄 四、重訓練機制

### 4.1 觸發條件

#### 定期重訓練
```python
retrain_interval_hours: 24  # 每24小時自動重訓練
```

#### 模型漂移檢測
```python
drift_threshold: 0.15  # 性能下降15%觸發重訓練

# 計算公式
performance_drop = (baseline - current) / baseline

if performance_drop > 0.15:
    trigger_retrain()
```

#### 市場狀態劇變（Regime Shift）
```python
# 檢測市場狀態變化
current_regime = detect_market_regime()  # trending/choppy/volatile
last_regime = load_last_regime()

if current_regime != last_regime:
    trigger_retrain()
```

**🔒 當前狀態**：
```python
DISABLE_MODEL_TRAINING = true
# 所有重訓練觸發器已禁用
```

---

### 4.2 重訓練流程

```python
async def retrain_model():
    """
    重訓練模型（OnlineLearningManager）
    """
    # 1. 收集最新交易數據（PostgreSQL優先）
    trades = await load_recent_trades(days=30)
    
    # 2. 提取12個ICT/SMC特徵 + 標籤
    X, y = extract_features_and_labels(trades)
    
    # 3. 訓練新模型（XGBoost）
    model = train_xgboost(X, y, params=PRODUCTION_PARAMS)
    
    # 4. 保存模型
    model.save('models/xgboost_model.json')
    
    # 5. 重載預測器
    ml_wrapper.reload()
    
    # 6. 更新基準性能
    baseline_performance = evaluate_model()
```

---

## 🎯 五、信號質量評分

### 5.1 質量計算公式

```python
# 🔥 v3.19+ 加權評分
signal_quality = (
    confidence * 0.40 +       # 信心值權重 40%
    win_probability * 0.40 +  # 勝率權重 40%
    (rr_ratio / 3.0) * 0.20   # R:R權重 20%（正規化到3.0）
)
```

**⚠️ Architect警告**：
- **RR主導問題**：當前公式導致高RR信號被過度選擇
- **建議**：調整為 `60% prediction + 40% RR`，更平衡

---

### 5.2 信號競價機制

```
多時間框架掃描（1h/15m/5m）
   ↓
生成候選信號（多個交易對）
   ↓
計算質量評分（每個信號）
   ↓
排序（按quality降序）
   ↓
選擇Top 1信號
   ↓
執行交易
```

**📊 競價上下文特徵**（已棄用v4.0）：
- `competition_rank` - 競價排名
- `score_gap_to_best` - 與最佳信號差距
- `num_competing_signals` - 競爭信號數量

---

## 📁 六、關鍵文件與職責

### 6.1 核心文件

| 文件路徑 | 職責 | 狀態 |
|---------|------|------|
| `src/ml/model_wrapper.py` | 加載模型並提供預測接口 | ✅ 運行中 |
| `src/ml/feature_schema.py` | 統一12個ICT/SMC特徵定義 | ✅ v4.0 |
| `src/core/model_initializer.py` | 初始訓練 + 強制重訓練 | 🔒 鎖定 |
| `src/ml/online_learning.py` | 在線重訓練管理器 | 🔒 鎖定 |
| `src/strategies/self_learning_trader.py` | ML預測 + 規則混合決策 | ✅ 運行中 |

### 6.2 數據文件

| 文件路徑 | 內容 | 狀態 |
|---------|------|------|
| `models/xgboost_model.json` | 訓練好的XGBoost模型 | 📦 預訓練 |
| `models/initialized.flag` | 初始化標記（含訓練參數） | 📝 存在 |
| `models/feature_weights.json` | 特徵權重（無先驗偏好） | 📝 1.0均值 |
| PostgreSQL `trades` 表 | 真實交易數據（訓練源） | 📊 累積中 |
| `data/trades.jsonl` | JSONL備援數據 | 📂 備用 |

---

## 🚨 七、關鍵問題與建議

### 7.1 當前配置問題

#### ❌ 問題1：XGBoost過度複雜
```python
# 當前配置
n_estimators = 100      # 樹數量
max_depth = 6           # 樹深度
min_child_weight = 10   # 葉節點最小樣本

# 問題分析
訓練樣本 ≈ 200 筆
模型複雜度 = 100樹 × 2^6葉節點 = 6400 參數
過擬合風險 = 極高（32倍於數據量）
```

**🔧 建議修復**：
```python
n_estimators = 30           # 降低至30樹
max_depth = 3               # 降低至深度3
min_child_weight = 1000     # 提升至1000樣本（確保統計顯著性）
```

---

#### ❌ 問題2：Bootstrap勝率過低（20%）
```python
# 當前設定
BOOTSTRAP_MIN_WIN_PROBABILITY = 0.20  # 接受80%失敗率

# 風險
- 豁免期累積大量虧損交易
- 模型學到錯誤模式
- 信心受挫（用戶/系統）
```

**🔧 建議修復**：
```python
# 漸進式提升策略
交易 1-25:   勝率門檻 30%
交易 26-50:  勝率門檻 37.5%
交易 51+:    勝率門檻 45%（正常期）
```

---

#### ❌ 問題3：信號質量公式RR主導
```python
# 當前公式
quality = confidence*0.4 + win_prob*0.4 + (rr/3.0)*0.2

# 問題
- RR容易被誇大（虛假高RR）
- 忽略預測準確性
```

**🔧 建議修復**：
```python
# 重新平衡
quality = (confidence * win_prob)*0.6 + normalized_rr*0.4
```

---

#### ⚠️ 問題4：訓練默認禁用
```python
DISABLE_MODEL_TRAINING = true
```

**問題分析**：
- **初始訓練禁用** → 依賴預訓練模型
- **重訓練禁用** → 無法適應市場變化
- **風險**：模型逐漸過時，性能下降

**🔧 建議修復**：
```python
# 生產環境建議
DISABLE_MODEL_TRAINING = false  # 啟用訓練

# 安全啟動策略
1. 確保 PostgreSQL 中有足夠數據（>200筆）
2. 設置重訓練間隔（24-72小時）
3. 啟用模型漂移檢測（drift_threshold=0.15）
4. 監控訓練日誌（確保無錯誤）
```

---

### 7.2 功能改進建議

#### 🔧 改進1：自適應重訓練頻率
```python
# 當前：固定24小時
retrain_interval_hours = 24

# 建議：根據交易頻率動態調整
if trades_per_day > 10:
    retrain_every = 25  # 每25筆交易
elif trades_per_day > 5:
    retrain_every = 50  # 每50筆交易
else:
    retrain_every = 100 # 每100筆交易
```

---

#### 🔧 改進2：特徵擴展（12 → 25）
```python
# 當前：12個ICT/SMC特徵
CANONICAL_FEATURE_NAMES = [...]  # 12個

# 建議：添加宏觀特徵
新增特徵（13個）：
- 市場波動率（VIX類似）
- 交易量分佈
- 訂單簿不平衡
- 資金費率
- 持倉興趣變化
- ...
```

---

#### 🔧 改進3：集成學習（Ensemble）
```python
# 當前：單一XGBoost模型
model = XGBoost()

# 建議：多模型投票
models = [
    XGBoost(),           # 非線性特徵
    LightGBM(),          # 更快訓練
    LogisticRegression() # 線性基準
]

# 加權投票
prediction = weighted_vote(models, weights=[0.5, 0.3, 0.2])
```

---

## 📋 八、檢查清單

### 8.1 啟用訓練前檢查

- [ ] PostgreSQL 中至少200筆已結算交易
- [ ] `trades` 表包含12個ICT/SMC特徵欄位
- [ ] XGBoost已安裝（`pip install xgboost`）
- [ ] 足夠磁盤空間（至少100MB）
- [ ] 設置 `DISABLE_MODEL_TRAINING=false`

### 8.2 訓練成功驗證

- [ ] `models/xgboost_model.json` 已生成
- [ ] `models/initialized.flag` 已創建
- [ ] 模型大小合理（10-100KB）
- [ ] 日誌顯示訓練成功（無錯誤）
- [ ] `MLModelWrapper.is_loaded = true`

### 8.3 重訓練監控

- [ ] 每24小時觸發一次重訓練
- [ ] 模型漂移檢測正常運作
- [ ] 重訓練後性能提升或保持
- [ ] 日誌記錄重訓練事件

---

## 🎯 九、結論與行動計劃

### 9.1 當前狀態總結

| 功能模塊 | 狀態 | 風險等級 |
|---------|------|---------|
| 特徵Schema（12個ICT/SMC） | ✅ v4.0統一 | 🟢 低 |
| ML預測推理 | ✅ 正常運行 | 🟢 低 |
| 初始訓練 | 🔒 禁用 | 🟡 中 |
| 在線重訓練 | 🔒 禁用 | 🟡 中 |
| Bootstrap機制 | ⚠️ 20%勝率過低 | 🔴 高 |
| XGBoost參數 | ⚠️ 過度複雜 | 🔴 高 |
| 信號質量公式 | ⚠️ RR主導 | 🟡 中 |

---

### 9.2 優先級行動計劃

#### 🔴 優先級1（立即修復）
1. **降低XGBoost複雜度**  
   ```python
   n_estimators: 100 → 30
   max_depth: 6 → 3
   min_child_weight: 10 → 1000
   ```

2. **提升Bootstrap勝率門檻**  
   ```python
   BOOTSTRAP_MIN_WIN_PROBABILITY: 0.20 → 0.30（漸進至0.45）
   ```

---

#### 🟡 優先級2（短期優化）
3. **重新平衡信號質量公式**  
   ```python
   quality = (confidence × win_prob) × 0.6 + normalized_rr × 0.4
   ```

4. **評估啟用訓練**  
   - 確認數據充足（>200筆）
   - 設置 `DISABLE_MODEL_TRAINING=false`
   - 監控首次訓練

---

#### 🟢 優先級3（長期改進）
5. **實施自適應重訓練**  
   - 每25-100筆交易觸發（根據頻率）
   - 結合漂移檢測

6. **擴展特徵集**  
   - 從12個增至25個特徵
   - 添加宏觀市場指標

7. **引入集成學習**  
   - XGBoost + LightGBM + LogisticRegression
   - 加權投票機制

---

### 9.3 監控指標

部署後需持續監控：

```python
# 模型性能
- 預測準確率（>50%）
- 勝率（>45%）
- Sharpe比率（>1.0）

# 訓練健康
- 訓練頻率（24-72小時一次）
- 模型大小（<100KB）
- 訓練時間（<5分鐘）

# 數據質量
- 訓練樣本數（>200）
- 特徵完整性（12/12特徵）
- 標籤準確性（outcome=WIN/LOSS）
```

---

## 📚 十、參考文檔

- `src/ml/feature_schema.py` - 統一特徵定義
- `src/core/model_initializer.py` - 訓練邏輯
- `src/ml/online_learning.py` - 重訓練機制
- `RAILWAY_LOGS_SIMPLE.md` - 日誌簡化策略
- Architect Review - ML策略綜合審查

---

**報告生成時間**：2025-11-11  
**下次審查建議**：實施優先級1修復後
