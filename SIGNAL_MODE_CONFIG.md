# 🎯 信號生成模式配置指南

## ⚠️ 診斷結果

**問題**：530個交易對掃描但0信號產生  
**根本原因**：嚴格模式（RELAXED_SIGNAL_MODE=false）過於苛刻

---

## 🚀 立即解決方案

### Railway環境變量設置

在Railway Dashboard → Variables中添加：

```env
RELAXED_SIGNAL_MODE=true
```

**預期效果**：
- ✅ 信號數量從0個提升到50-100個（530個交易對中）
- ✅ 允許H1主導策略（H1明確，M15可neutral）
- ✅ 允許M15+M5短期對齊（H1可neutral）

---

## 📊 完整推薦配置（按階段）

### 階段1：數據採集期（當前 - 前100筆交易）

```env
# 信號生成模式
RELAXED_SIGNAL_MODE=true

# 豁免期門檻（前100筆）
BOOTSTRAP_TRADE_LIMIT=100
BOOTSTRAP_MIN_WIN_PROBABILITY=0.40
BOOTSTRAP_MIN_CONFIDENCE=0.40

# 功能鎖定
DISABLE_MODEL_TRAINING=true
DISABLE_REST_FALLBACK=false
```

### 階段2：正常運行期（100筆交易後）

```env
# 保持寬鬆模式
RELAXED_SIGNAL_MODE=true

# 正常門檻
MIN_WIN_PROBABILITY=0.60
MIN_CONFIDENCE=0.50
```

### 階段3：高質量期（有足夠歷史數據後，可選）

```env
# 可切換回嚴格模式
RELAXED_SIGNAL_MODE=false

# 提高門檻
MIN_WIN_PROBABILITY=0.65
MIN_CONFIDENCE=0.60
```

---

## 🔍 嚴格模式 vs 寬鬆模式對比

| 項目 | 嚴格模式 | 寬鬆模式 |
|------|----------|----------|
| **H1+M15對齊要求** | 必須完全同向 | H1主導或M15主導 |
| **預期信號數量** | 5-10個/530對 | 50-100個/530對 |
| **勝率預期** | 較高（>65%） | 中等（55-65%） |
| **適用階段** | 數據充足期 | 初期啟動期 |
| **風險** | 信號過少，錯失機會 | 信號質量略低 |

---

## ⚡ 即時檢查命令

### 檢查當前配置
```bash
echo $RELAXED_SIGNAL_MODE
```

### 查看信號統計（每50個交易對輸出）
檢查日誌中是否出現：
```
🔍 信號生成統計（已掃描50個）：
   H1趨勢: bullish=X, bearish=Y, neutral=Z
   M15趨勢: bullish=X, bearish=Y, neutral=Z
```

---

## ✅ 預期結果

啟用RELAXED_SIGNAL_MODE=true後：

1. **第1個周期**（60秒內）：
   - 掃描530個交易對
   - 預期生成50-100個候選信號
   - 經過ML模型預測後，產生5-20個最終信號
   - 執行top 5信號（根據加權評分）

2. **後續周期**：
   - 持續生成信號
   - 開始積累交易數據
   - 每50筆觸發模型重訓練

---

## 🛠️ 故障排除

### 如果啟用後仍無信號：

1. **檢查豁免期門檻**：
   ```env
   BOOTSTRAP_MIN_WIN_PROBABILITY=0.40
   BOOTSTRAP_MIN_CONFIDENCE=0.40
   ```

2. **檢查日誌級別**：
   確保INFO日誌正常輸出

3. **檢查WebSocket數據**：
   ```
   📊 DataService WebSocket統計：
      WebSocket命中: 100.0%
   ```

4. **檢查市場條件**：
   可能所有交易對都處於極度震盪期

---

## 📌 結論

**立即行動**：在Railway添加環境變量
```env
RELAXED_SIGNAL_MODE=true
```

**預期時間**：5分鐘內看到第一批信號  
**建議監控**：前1小時觀察信號質量和執行情況

