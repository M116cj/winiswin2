# Binance API 端点與權限檢查清單 v4.1

## 📊 系統使用的所有Binance API端點

### 1️⃣ 公開端點（無需簽名）

| 端點 | 方法 | 用途 | 簽名 |
|-----|------|------|------|
| `/fapi/v1/ping` | GET | 測試連接 | ❌ |
| `/fapi/v1/exchangeInfo` | GET | 獲取交易規則 | ❌ |
| `/fapi/v1/klines` | GET | 獲取K線數據 | ❌ |
| `/fapi/v1/ticker/price` | GET | 獲取最新價格 | ❌ |
| `/fapi/v1/ticker/24hr` | GET | 獲取24小時統計 | ❌ |

### 2️⃣ USER_DATA端點（需要簽名）

| 端點 | 方法 | 用途 | 簽名 | 需要權限 |
|-----|------|------|------|---------|
| `/fapi/v2/account` | GET | 獲取賬戶信息 | ✅ | Reading + Futures |
| `/fapi/v1/positionSide/dual` | GET | 查詢持倉模式 | ✅ | Reading + Futures |
| `/fapi/v1/order` | POST | 創建訂單 | ✅ | Trading + Futures |
| `/fapi/v1/order` | DELETE | 取消訂單 | ✅ | Trading + Futures |
| `/fapi/v1/order` | GET | 查詢訂單 | ✅ | Reading + Futures |
| `/fapi/v1/openOrders` | GET | 查詢所有掛單 | ✅ | Reading + Futures |
| `/fapi/v1/leverage` | POST | 調整槓桿 | ✅ | Trading + Futures |

### 3️⃣ USER_STREAM端點（只需API Key）

| 端點 | 方法 | 用途 | 簽名 | 需要權限 |
|-----|------|------|------|---------|
| `/fapi/v1/listenKey` | POST | 創建listenKey | ❌ | Reading + Futures |
| `/fapi/v1/listenKey` | PUT | 續期listenKey | ❌ | Reading + Futures |
| `/fapi/v1/listenKey` | DELETE | 關閉listenKey | ❌ | Reading + Futures |

---

## ✅ API密鑰配置檢查清單

### 必須啟用的權限

在Binance API管理頁面，確保以下權限已勾選：

```
✅ Enable Reading       ← 必須（查詢賬戶、持倉、訂單）
✅ Enable Futures       ← 必須（訪問期貨API）
✅ Enable Trading       ← 可選（僅需下單時啟用）
❌ Enable Withdrawals   ← 禁用（安全考慮）
```

### IP白名單配置

#### 選項A：不限制IP（測試環境）
```
• 設置：選擇"不限制訪問IP"
• 優點：部署時無需調整
• 缺點：安全性較低
• 適用：開發/測試環境
```

#### 選項B：限制特定IP（生產環境）
```
• 設置：添加部署服務器IP到白名單
• Railway部署：需在Railway控制台查看Outbound IP
• 優點：安全性高
• 缺點：IP變更時需更新
• 適用：生產環境
```

---

## 🔧 v4.1+ 增強功能

### 1. API密鑰分離支持

系統現支持獨立的交易密鑰配置：

```bash
# 環境變量配置
BINANCE_API_KEY=<讀取專用密鑰>          # 用於查詢賬戶、市場數據
BINANCE_API_SECRET=<讀取密鑰Secret>

BINANCE_TRADING_API_KEY=<交易專用密鑰>  # 用於下單、調整槓桿
BINANCE_TRADING_API_SECRET=<交易密鑰Secret>
```

**優先級**：
- 系統優先使用 `BINANCE_TRADING_API_*`（如已設置）
- 否則回退到 `BINANCE_API_*`

**最佳實踐**：
- 創建2個API密鑰
- 讀取密鑰：只啟用 Reading + Futures
- 交易密鑰：啟用 Reading + Futures + Trading

### 2. 啟動時權限驗證

系統會在啟動時自動檢測API密鑰權限：

```
✅ 步驟1：測試網絡連通性（/fapi/v1/ping）
✅ 步驟2：驗證API密鑰權限（嘗試/fapi/v2/account）
✅ 步驟3：檢測Position Mode（Hedge/One-Way）
```

如遇 **HTTP 401 / -2015 錯誤**，會顯示詳細配置指南。

---

## 🚨 常見錯誤與解決方案

### 錯誤1：HTTP 401, code=-2015
```
錯誤訊息：Invalid API-key, IP, or permissions for action
```

**解決方案**：
1. 檢查API密鑰是否啟用 "Enable Futures" 和 "Enable Reading"
2. 如設置IP白名單，確認部署服務器IP已加入
3. 確認API密鑰未過期或被禁用

### 錯誤2：HTTP 451
```
錯誤訊息：Service unavailable from a restricted location
```

**解決方案**：
- Replit環境受Binance地理限制
- 必須部署到Railway或其他支持的雲平台

### 錯誤3：Signature Mismatch
```
錯誤訊息：Signature for this request is not valid
```

**解決方案**：
1. 檢查 `BINANCE_API_SECRET` 是否正確
2. 確認系統時間同步（Binance要求時間戳誤差<1秒）

---

## 📚 官方文檔參考

- Binance Futures API文檔：https://developers.binance.com/docs/derivatives/usds-margined-futures
- API權限設置指南：https://www.binance.com/en/support/faq/binance-api-product-page-guidance-865f0fe3cb6a4d73a21609b3b7326f31
- 常見錯誤碼：https://developers.binance.com/docs/derivatives/usds-margined-futures/error-codes

---

## ✨ 系統實現亮點

### 正確的簽名實現
```python
# HMAC-SHA256簽名機制（符合Binance規範）
query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
signature = hmac.new(
    api_secret.encode('utf-8'),
    query_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()
```

### listenKey端點正確設置
```python
# USER_STREAM類型端點不需要簽名
POST /fapi/v1/listenKey - signed=False ✅
PUT /fapi/v1/listenKey - signed=False ✅
DELETE /fapi/v1/listenKey - signed=False ✅
```

### 所有USER_DATA端點正確簽名
```python
# 需要簽名的端點都已正確標記
GET /fapi/v2/account - signed=True ✅
POST /fapi/v1/order - signed=True ✅
DELETE /fapi/v1/order - signed=True ✅
```

---

最後更新：2025-11-11 v4.1
