# 🔒 功能鎖定開關指南 (v3.18.7+)

## 📌 概述

SelfLearningTrader v3.18.7+ 新增三個功能鎖定開關，允許生產環境靈活控制系統行為。

## 🎯 三大鎖定開關

### 1. `DISABLE_MODEL_TRAINING` - 模型訓練鎖定

**用途**：鎖定模型訓練功能（初始訓練 + 重訓練）

**默認值**：`true` (生產環境建議)

**行為**：
- ✅ **啟用 (true)**：系統使用現有模型，不進行任何訓練
  - 跳過初始訓練（首次啟動）
  - 跳過自動重訓練（每50筆交易觸發）
  - 要求預先存在模型文件 (`models/xgboost_model.json`)
  
- ❌ **停用 (false)**：允許模型訓練
  - 首次啟動自動訓練初始模型
  - 每50筆交易自動重訓練

**使用場景**：
```bash
# 生產環境（推薦）- 使用預訓練模型
DISABLE_MODEL_TRAINING=true

# 開發環境 - 允許動態學習
DISABLE_MODEL_TRAINING=false
```

**注意事項**：
- ⚠️ 啟用時必須確保已有預訓練模型
- 🔥 生產環境建議鎖定，避免模型不穩定

---

### 2. `DISABLE_WEBSOCKET` - WebSocket鎖定

**用途**：鎖定WebSocket連接，使用純REST API模式

**默認值**：`true` (生產環境建議)

**行為**：
- ✅ **啟用 (true)**：純REST模式
  - 不啟動WebSocket連接
  - 所有數據透過REST API獲取
  - 降低連接複雜度
  - 適合不穩定網絡環境
  
- ❌ **停用 (false)**：WebSocket + REST混合模式
  - 啟動WebSocket監控200+交易對
  - K線Feed：@kline_1m (實時K線)
  - 帳戶Feed：listenKey (實時倉位)
  - REST作為備援

**使用場景**：
```bash
# 生產環境（推薦）- 純REST模式
DISABLE_WEBSOCKET=true

# 開發環境 - 實時數據優先
DISABLE_WEBSOCKET=false
```

**注意事項**：
- 🌐 純REST模式穩定性更高
- 📡 WebSocket模式數據更新更快（1秒 vs 60秒）
- 🔄 系統已優化REST API頻率限制

---

### 3. `DISABLE_REST_FALLBACK` - REST備援鎖定

**用途**：禁用REST API備援機制（僅在WebSocket極度穩定時使用）

**默認值**：`false` (建議保持備援)

**行為**：
- ✅ **啟用 (true)**：禁用REST備援
  - WebSocket失敗時不切換到REST
  - 完全依賴WebSocket數據
  - ⚠️ 高風險配置
  
- ❌ **停用 (false)**：啟用REST備援（推薦）
  - WebSocket失敗時自動切換REST
  - 確保數據持續可用

**使用場景**：
```bash
# 標準配置（推薦）- 保持備援
DISABLE_REST_FALLBACK=false

# 極端場景 - 僅WebSocket（不推薦）
DISABLE_REST_FALLBACK=true
```

**注意事項**：
- ⚠️ 啟用後失去容錯能力
- 🚫 生產環境**不建議**啟用

---

## 🔧 配置方法

### Railway部署

在Railway環境變量中設置：

```env
# 生產環境推薦配置
DISABLE_MODEL_TRAINING=true
DISABLE_WEBSOCKET=true
DISABLE_REST_FALLBACK=false
```

### 本地開發

在 `.env` 或環境變量中設置：

```bash
export DISABLE_MODEL_TRAINING=false
export DISABLE_WEBSOCKET=false
export DISABLE_REST_FALLBACK=false
```

---

## 📊 推薦配置組合

### 🟢 生產環境（穩定優先）

```env
DISABLE_MODEL_TRAINING=true   # 使用預訓練模型
DISABLE_WEBSOCKET=true        # 純REST模式
DISABLE_REST_FALLBACK=false   # 保持備援
```

**優勢**：
- ✅ 最高穩定性
- ✅ 可預測性
- ✅ 低複雜度

---

### 🟡 開發環境（學習優先）

```env
DISABLE_MODEL_TRAINING=false  # 允許動態學習
DISABLE_WEBSOCKET=false       # WebSocket實時數據
DISABLE_REST_FALLBACK=false   # 保持備援
```

**優勢**：
- ✅ 模型持續優化
- ✅ 實時數據更新
- ✅ 完整功能測試

---

### 🔴 極端場景（純WebSocket）

```env
DISABLE_MODEL_TRAINING=true   # 使用預訓練模型
DISABLE_WEBSOCKET=false       # WebSocket模式
DISABLE_REST_FALLBACK=true    # 禁用REST備援
```

**注意**：
- ⚠️ 僅在WebSocket極度穩定時使用
- ⚠️ 失去容錯能力
- ⚠️ 不建議生產環境

---

## 🧪 驗證配置

啟動系統後，檢查日誌輸出：

### ✅ 模型訓練已鎖定
```
🔒 模型訓練已鎖定（DISABLE_MODEL_TRAINING=True）
   ✅ 系統將使用現有模型，不進行初始訓練或重訓練
   ✅ 檢測到現有模型: models/xgboost_model.json
```

### ✅ WebSocket已鎖定
```
🔒 WebSocket已鎖定（DISABLE_WEBSOCKET=True）
   ✅ 系統將使用REST API獲取數據（純REST模式）
📡 步驟1-2：跳過WebSocket（已鎖定，使用純REST API模式）
```

### ✅ 模型重訓練已跳過
```
# 完成50筆交易後，不會看到重訓練日誌
```

---

## 🎯 故障排除

### 問題1：模型訓練鎖定但無模型文件

**症狀**：
```
⚠️ 未檢測到模型文件: models/xgboost_model.json
⚠️ 請確保已有預訓練模型，或臨時關閉DISABLE_MODEL_TRAINING
```

**解決方案**：
1. 臨時設置 `DISABLE_MODEL_TRAINING=false` 訓練初始模型
2. 或上傳預訓練模型到 `models/` 目錄

---

### 問題2：WebSocket鎖定後REST請求過多

**症狀**：
- REST API頻率限制警告
- 熔斷器觸發

**解決方案**：
- ✅ 這是正常的，系統已優化REST請求頻率
- 📊 熔斷器自動保護，60秒後重試

---

### 問題3：同時鎖定WebSocket和REST備援

**症狀**：
```
# 無法獲取任何數據
```

**解決方案**：
- ⚠️ **不要**同時設置：
  - `DISABLE_WEBSOCKET=true`
  - `DISABLE_REST_FALLBACK=true`
- 這會導致無數據源可用

---

## 📝 版本歷史

### v3.18.7 (2025-11-01)
- ✨ 新增三大功能鎖定開關
- 🔒 支援生產環境靈活控制
- 🛡️ 提升系統穩定性與可預測性
- 📚 完整文檔與配置指南

---

## 🔗 相關文件

- [交易策略報告](TRADING_STRATEGY_REPORT.md) - 詳細策略邏輯
- [特徵完整性測試](tests/test_feature_integrity.py) - 44特徵驗證
- [主配置文件](src/config.py) - 鎖定開關定義
- [模型初始化器](src/core/model_initializer.py) - 訓練鎖定實現
- [統一調度器](src/core/unified_scheduler.py) - WebSocket鎖定實現
- [交易記錄器](src/managers/trade_recorder.py) - 重訓練鎖定實現

---

**🎉 系統現已支援生產級功能鎖定，可安全部署到Railway！**
