# 🚨 Railway環境問題診斷與解決方案

**日期**: 2025-11-05  
**環境**: Railway Production  
**狀態**: 🔴 兩個Critical問題待修復

---

## 📊 問題總覽

### 問題1: 豁免期配置錯誤 🔴 CRITICAL

**症狀**:
```
🎓 NTRNUSDT 豁免期: 已完成 0/100 筆 | 門檻 勝率≥40% 信心≥40%
                           ^^^      ^^         ^^
                          錯誤     錯誤       錯誤
```

**預期**:
```
🎓 NTRNUSDT 豁免期: 已完成 0/50 筆 | 門檻 勝率≥20% 信心≥25%
```

**影響**: 所有交易信號被拒絕（0筆交易執行）

### 問題2: validate_leverage 異常 🟡 MEDIUM

**症狀**:
```
2025-11-05 14:17:48,818 - src.core.exception_handler - ERROR - ❌ 異常發生在 validate_leverage
```

**可能原因**:
1. leverage 值為 None
2. leverage 值為 0
3. leverage 值為 NaN/Inf

---

## 🔍 問題1詳細診斷：豁免期配置錯誤

### 根本原因

Railway環境變量覆蓋了代碼默認值：

```bash
# Railway Dashboard → Environment Variables
BOOTSTRAP_TRADE_LIMIT=100          # ❌ 應該是 50
BOOTSTRAP_MIN_WIN_PROBABILITY=0.40 # ❌ 應該是 0.20
BOOTSTRAP_MIN_CONFIDENCE=0.40      # ❌ 應該是 0.25
```

### 代碼驗證（正確）

```python
# src/config.py Line 69-71
BOOTSTRAP_TRADE_LIMIT: int = int(os.getenv("BOOTSTRAP_TRADE_LIMIT", "50"))
BOOTSTRAP_MIN_WIN_PROBABILITY: float = float(os.getenv("BOOTSTRAP_MIN_WIN_PROBABILITY", "0.20"))
BOOTSTRAP_MIN_CONFIDENCE: float = float(os.getenv("BOOTSTRAP_MIN_CONFIDENCE", "0.25"))
```

✅ **代碼邏輯100%正確**

### 影響評估

| 指標 | 錯誤配置 | 正確配置 | 損失 |
|------|---------|---------|------|
| 信號通過率 | 0% (0/532) | ~15% (80/532) | 100% |
| 交易執行 | 0筆 | 3-10筆/週期 | 100% |
| ML學習 | 完全停止 | 正常累積 | 100% |
| 豁免期完成時間 | 無限期 | ~1週 | N/A |

### 解決方案

#### 方案A：刪除環境變量 ⭐ **推薦**

1. **登入 Railway Dashboard**
   ```
   https://railway.app
   ```

2. **進入項目的 Environment Variables**

3. **刪除以下3個變量**：
   ```
   BOOTSTRAP_TRADE_LIMIT
   BOOTSTRAP_MIN_WIN_PROBABILITY
   BOOTSTRAP_MIN_CONFIDENCE
   ```

4. **重新部署**
   - 點擊 "Redeploy" 按鈕
   - 系統將使用代碼中的正確默認值

#### 方案B：修正環境變量值

如果需要保留環境變量覆蓋能力：

```bash
BOOTSTRAP_TRADE_LIMIT=50
BOOTSTRAP_MIN_WIN_PROBABILITY=0.20
BOOTSTRAP_MIN_CONFIDENCE=0.25
```

### 驗證步驟

部署後檢查啟動日誌：

```bash
# 預期輸出
2025-11-05 XX:XX:XX - src.core.leverage_engine - INFO - 🎓 豁免期交易數: 前50筆
2025-11-05 XX:XX:XX - src.core.leverage_engine - INFO - 🎓 豁免期勝率閾值: 20%
2025-11-05 XX:XX:XX - src.core.leverage_engine - INFO - 🎓 豁免期信心度閾值: 25%
```

等待15分鐘（1個交易週期）後：

```bash
# 預期輸出
✅ 下單成功: BTCUSDT LONG | 數量=0.001 | 槓桿=3.0x | 價值=$60.00
```

---

## 🔍 問題2詳細診斷：validate_leverage 異常

### 錯誤來源

```python
# src/core/safety_validator.py
@ExceptionHandler.log_exceptions
def validate_leverage(leverage: float, symbol: str = "unknown") -> float:
    if leverage is None:
        raise ValidationError(f"槓桿值不能為None: {symbol}")
    
    if math.isnan(leverage) or math.isinf(leverage):
        raise ValidationError(f"無效槓桿值(NaN/Inf): {leverage} - {symbol}")
    
    if leverage <= 0:
        raise ValidationError(f"槓桿值必須大於0: {leverage} - {symbol}")
```

### 可能觸發點

1. **信號生成時leverage為None**
   ```python
   # src/strategies/self_learning_trader.py
   signal['leverage'] = None  # ❌ 不應該發生
   ```

2. **槓桿計算返回0**
   ```python
   # 某處計算邏輯錯誤
   leverage = 0  # ❌ 觸發 leverage <= 0 檢查
   ```

3. **數學計算錯誤產生NaN**
   ```python
   # 除零或其他數學錯誤
   leverage = 0.0 / 0.0  # ❌ NaN
   ```

### 診斷方法

#### Step 1: 獲取完整錯誤堆棧

從 Railway 日誌查找完整錯誤信息：

```bash
# 在 Railway Dashboard → Logs 搜索
❌ 異常發生在 validate_leverage
```

查看上下文日誌：
- 錯誤類型 (ValidationError)
- 錯誤信息 (具體原因)
- 堆棧追蹤 (調用路徑)

#### Step 2: 檢查信號數據

查找觸發錯誤時的信號：

```bash
# 在錯誤發生前的日誌中查找
🎯 最佳信號 XXXUSDT: leverage=?
```

#### Step 3: 檢查槓桿計算邏輯

```python
# src/strategies/self_learning_trader.py Line 230
leverage = self.calculate_leverage(
    win_probability,
    confidence,
    rr_ratio,
    is_bootstrap=thresholds['is_bootstrap'],
    verbose=True  # 啟用詳細日誌
)
```

### 可能的解決方案

#### 方案A：添加防護性默認值

```python
# 在調用 validate_leverage 之前
leverage = signal.get('leverage', 1.0)  # 默認1.0倍
if leverage is None or leverage <= 0:
    leverage = 1.0
    
# 然後再驗證
validated_leverage = SafetyValidator.validate_leverage(leverage, symbol)
```

#### 方案B：修復槓桿計算邏輯

如果問題在 `calculate_leverage` 方法：

```python
# src/core/leverage_engine.py
def calculate_leverage(...):
    # 確保所有返回路徑都返回有效值
    leverage = max(0.5, min(100.0, calculated_leverage))  # 限制範圍
    return leverage
```

#### 方案C：改進錯誤處理

```python
# src/strategies/self_learning_trader.py
try:
    leverage = self.calculate_leverage(...)
    validated_leverage = SafetyValidator.validate_leverage(leverage, symbol)
except ValidationError as e:
    logger.error(f"槓桿驗證失敗: {e}，使用默認值1.0x")
    validated_leverage = 1.0
```

### 臨時緩解措施

如果無法立即修復，可以在 `SafetyValidator.validate_leverage` 中添加兜底邏輯：

```python
@staticmethod
@ExceptionHandler.log_exceptions
def validate_leverage(leverage: float, symbol: str = "unknown") -> float:
    # 新增：兜底處理
    if leverage is None or (isinstance(leverage, float) and (math.isnan(leverage) or math.isinf(leverage))):
        logger.warning(f"⚠️ 無效槓桿值 {leverage}（{symbol}），使用默認值1.0x")
        return 1.0
    
    if leverage <= 0:
        logger.warning(f"⚠️ 槓桿值非正數 {leverage}（{symbol}），使用默認值1.0x")
        return 1.0
    
    # 原有邏輯...
    if leverage < SafetyValidator.MIN_LEVERAGE:
        return SafetyValidator.MIN_LEVERAGE
    
    return float(leverage)
```

**注意**：這是臨時方案，應該找到並修復根本原因。

---

## 📋 修復檢查清單

### Priority 0 - 立即執行

- [ ] **修復問題1：豁免期配置**
  - [ ] 登入 Railway Dashboard
  - [ ] 刪除 3 個 BOOTSTRAP_* 環境變量
  - [ ] 重新部署
  - [ ] 驗證啟動日誌顯示 "50筆/25%/20%"
  - [ ] 等待15分鐘驗證交易執行

### Priority 1 - 24小時內

- [ ] **診斷問題2：validate_leverage 錯誤**
  - [ ] 從 Railway 日誌獲取完整堆棧追蹤
  - [ ] 識別觸發錯誤的具體信號
  - [ ] 檢查槓桿計算邏輯
  - [ ] 確定根本原因

- [ ] **修復問題2**
  - [ ] 實施適當的解決方案（A/B/C）
  - [ ] 添加單元測試
  - [ ] 部署修復
  - [ ] 驗證錯誤不再發生

### Priority 2 - 1週內

- [ ] **改進監控**
  - [ ] 添加槓桿值範圍監控
  - [ ] 添加異常率監控
  - [ ] 設置警報閾值

- [ ] **改進文檔**
  - [ ] 更新環境變量文檔
  - [ ] 記錄配置最佳實踐
  - [ ] 創建故障排除指南

---

## 🔍 調試命令

### Railway Dashboard 操作

```bash
# 1. 查看環境變量
Settings → Variables → 查找 BOOTSTRAP_*

# 2. 查看實時日誌
Deployments → Latest → Logs

# 3. 搜索錯誤
Logs 搜索框 → "validate_leverage"
Logs 搜索框 → "ValidationError"

# 4. 查看啟動配置
Logs 搜索框 → "豁免期交易數"
Logs 搜索框 → "豁免期閾值"
```

### 本地測試（Replit）

```bash
# 模擬環境變量
export BOOTSTRAP_TRADE_LIMIT=100
export BOOTSTRAP_MIN_CONFIDENCE=0.40
export BOOTSTRAP_MIN_WIN_PROBABILITY=0.40

# 運行並觀察日誌
python -m src.main
```

### 驗證修復

```bash
# 檢查配置加載
grep "豁免期" logs/*.log | head -5

# 檢查信號通過率
grep "最佳信號" logs/*.log | wc -l

# 檢查交易執行
grep "下單成功" logs/*.log | wc -l
```

---

## 📊 預期修復效果

### 修復前（當前狀態）

```
環境變量: BOOTSTRAP_TRADE_LIMIT=100, MIN_CONFIDENCE=40%
信號掃描: 532個
信號通過: 0個
交易執行: 0筆
錯誤: validate_leverage 異常
```

### 修復後（目標狀態）

```
環境變量: 使用代碼默認值（50, 25%, 20%）
信號掃描: 532個
信號通過: ~80個 (15%)
交易執行: 3-10筆/週期
錯誤: 0個
```

---

## ⏱️ 預計修復時間

| 任務 | 時間 | 備註 |
|------|------|------|
| 修復問題1（環境變量） | 5分鐘 | 刪除變量 + 重新部署 |
| 驗證問題1 | 15-30分鐘 | 等待交易週期 |
| 診斷問題2 | 10-30分鐘 | 查看日誌 + 分析 |
| 修復問題2 | 30-60分鐘 | 取決於根本原因 |
| **總計** | **1-2小時** | 包括驗證時間 |

---

## 📞 下一步行動

1. **立即**：修復豁免期配置（問題1）
   - 這是最Critical的問題，導致系統完全無法交易
   - 修復簡單（刪除3個環境變量）
   - 預計5分鐘完成

2. **等待驗證**：觀察15-30分鐘
   - 確認信號開始通過
   - 確認交易開始執行

3. **診斷問題2**：如果仍出現 validate_leverage 錯誤
   - 獲取完整堆棧追蹤
   - 提供詳細日誌供分析

4. **報告結果**：修復完成後提供：
   - 修復前後對比截圖
   - 第一筆交易執行日誌
   - 信號通過率數據

---

## ✅ 成功標準

修復成功的判斷標準：

1. ✅ 啟動日誌顯示正確配置 (50/25%/20%)
2. ✅ 15分鐘內至少有1個信號通過
3. ✅ 1小時內至少執行1筆交易
4. ✅ 無 validate_leverage 錯誤
5. ✅ trades.jsonl 文件大小 > 0

---

修復完成後，系統應該能夠正常運作！🚀
