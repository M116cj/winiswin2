# 🔍 v3.1.6: 改進錯誤診斷

**日期**: 2025-10-26  
**狀態**: 🔍 診斷中  
**問題**: 持續的400 Bad Request錯誤，缺乏詳細錯誤信息  
**修復**: 改進錯誤處理以捕獲Binance具體錯誤代碼

---

## 📊 當前狀態分析

### Railway 日誌（最新）

#### ✅ 部分成功

```
🎯 生成 54 個交易信號
已归档 7 条仓位记录到 ml_data/positions.csv  # ✅ 7個訂單成功！
```

**成功率**: 7/54 = 13% （太低）

#### ❌ 重複失敗的交易對

```
1. AIXBTUSDT
   - 限價單失敗: quantity=8856.0, price=0.09051
   - 錯誤: 400 Bad Request

2. NEARUSDT
   - 市價單失敗: quantity=349.0
   - 錯誤: 400 Bad Request

3. DOTUSDT
   - 市價單失敗: quantity=259.2
   - 錯誤: 400 Bad Request

4. BLUAIUSDT
   - 限價單失敗: quantity=22353.0, price=0.03586
   - 錯誤: 400 Bad Request
```

### 問題診斷

**當前問題**：錯誤日誌不夠詳細，只顯示"400 Bad Request"，無法確定具體原因

**可能原因**：
1. **數量精度問題** - stepSize不匹配（259.2可能應該是259）
2. **價格精度問題** - tickSize不匹配
3. **MIN_NOTIONAL** - 訂單價值低於最小要求
4. **市場狀態** - 交易對暫停交易或限制
5. **杠桿設置** - 杠桿不符合交易所要求
6. **持倉限制** - 超過最大持倉限制

---

## 🛠️ v3.1.6 修復內容

### 改進錯誤處理

**問題**：舊代碼只記錄HTTP狀態碼和URL，不記錄Binance返回的具體錯誤代碼

**舊代碼** (`src/clients/binance_client.py`):
```python
except Exception as e:
    logger.error(f"API 請求失敗: {endpoint} - {str(e)}")
    raise
```

**新代碼** (`src/clients/binance_client.py`):
```python
async with session.request(...) as response:
    if response.status != 200:
        # 獲取錯誤響應體
        error_text = await response.text()
        try:
            error_json = await response.json()
            error_msg = error_json.get('msg', error_text)
            error_code = error_json.get('code', 'N/A')
            logger.error(
                f"Binance API 錯誤 {response.status}: "
                f"code={error_code}, msg={error_msg}, "
                f"endpoint={endpoint}, params={_params}"
            )
        except:
            logger.error(f"Binance API 錯誤 {response.status}: {error_text}")
        response.raise_for_status()
    return await response.json()
```

### 新增詳細錯誤信息

**修復後的日誌輸出**：
```
舊版本:
  API 請求失敗: /fapi/v1/order - 400, message='Bad Request'

新版本:
  Binance API 錯誤 400: code=-1111, msg=Precision is over the maximum defined for this asset., 
  endpoint=/fapi/v1/order, params={'symbol': 'DOTUSDT', 'quantity': 259.2}
```

**常見Binance錯誤代碼**：
```
-1111: Precision is over the maximum defined
       → 數量或價格精度錯誤

-1013: Filter failure: LOT_SIZE
       → 數量不符合LOT_SIZE規則

-1116: Invalid orderType
       → 訂單類型錯誤

-2010: NEW_ORDER_REJECTED
       → 訂單被拒絕（可能是notional太小）

-4164: Order's notional must be no smaller than X
       → 訂單價值太小
```

---

## 🚀 部署與診斷步驟

### 步驟 1: 推送v3.1.6代碼

```bash
git add .
git commit -m "🔍 v3.1.6: 改進錯誤診斷（捕獲Binance錯誤代碼）"
git push railway main
```

### 步驟 2: 監控詳細錯誤

```bash
railway logs --follow | grep "Binance API 錯誤"
```

**預期輸出**：
```
Binance API 錯誤 400: code=-1111, msg=Precision is over the maximum defined, params={...}
Binance API 錯誤 400: code=-2010, msg=NEW_ORDER_REJECTED, params={...}
Binance API 錯誤 400: code=-4164, msg=Order's notional must be no smaller than 5.0, params={...}
```

### 步驟 3: 根據錯誤代碼修復

基於具體錯誤代碼，我們可以：

#### 如果是 -1111 (精度錯誤)
→ 修復數量/價格的小數位數

#### 如果是 -1013 (LOT_SIZE錯誤)
→ 確保數量是stepSize的整數倍

#### 如果是 -4164 (notional太小)
→ 增加訂單最小價值檢查

#### 如果是 -2010 (訂單被拒絕)
→ 檢查市場狀態和杠桿設置

---

## 🎯 下一步行動計畫

1. **立即**推送v3.1.6到Railway
2. 監控新的詳細錯誤日誌
3. 根據具體錯誤代碼（-1111, -1013, -4164等）製定修復方案
4. 實施針對性修復（v3.1.7）
5. 驗證100%成功率

---

## 📋 已知問題總結

| 版本 | 問題 | 狀態 |
|------|------|------|
| v3.1.2 | 智能訂單系統 | ✅ 已修復 |
| v3.1.3 | 冷啟動問題 | ✅ 已修復 |
| v3.1.4 | 數量精度 | ✅ 已修復 |
| v3.1.5 | 價格精度 | ✅ 已修復 |
| v3.1.6 | 錯誤診斷 | 🔍 診斷中 |
| **待修復** | **400錯誤（需詳細診斷）** | ⏳ **等待錯誤代碼** |

---

## 💡 為什麼需要v3.1.6？

**問題**：
- 我們修復了數量精度（v3.1.4）和價格精度（v3.1.5）
- 但仍有13%失敗率（47/54訂單失敗）
- **缺少具體錯誤信息**無法診斷根本原因

**解決方案**：
- v3.1.6捕獲Binance返回的**錯誤代碼和消息**
- 這樣我們就能知道：
  - 是精度問題嗎？（-1111）
  - 是訂單價值太小嗎？（-4164）
  - 是市場限制嗎？（-2010）
  - 是其他問題嗎？

**下一版本（v3.1.7）**：
- 基於v3.1.6的詳細錯誤信息
- 實施針對性修復
- 目標：**100%成功率**

---

## 🔄 修復流程

```
v3.1.3: 學習模式（冷啟動）     ✅
   ↓
v3.1.4: 數量精度修復           ✅
   ↓
v3.1.5: 價格精度修復           ✅
   ↓
v3.1.6: 錯誤診斷增強           🔍 ← 當前位置
   ↓
v3.1.7: 針對性修復             ⏳ 等待診斷結果
   ↓
✅ 100%成功率                  🎯 最終目標
```

---

## 📞 立即行動

**推送v3.1.6並監控詳細錯誤**：

```bash
git add .
git commit -m "🔍 v3.1.6: 詳細錯誤診斷"
git push railway main

# 然後監控
railway logs --follow | grep -E "Binance API 錯誤|code=|msg="
```

**等待詳細錯誤信息後，我們就能準確修復！** 🔍
