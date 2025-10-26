# 🔧 v3.2.1: 修复签名验证失败（-1022）

**日期**: 2025-10-26  
**狀態**: ✅ 就緒  
**問題**: Binance API 錯誤 -1022（Signature not valid）  
**原因**: 交易對符號包含中文字符  
**解決**: 添加ASCII過濾器

---

## 🚨 問題分析

### Railway日誌顯示錯誤

```
Binance API 錯誤 400: code=-1022, msg=Signature for this request is not valid.
endpoint=/fapi/v1/order
params={'symbol': '币安人生USDT', ...}
```

**錯誤代碼**: `-1022`  
**錯誤信息**: "Signature for this request is not valid"  
**問題符號**: `币安人生USDT` （包含中文字符）

---

## 🔍 根本原因

### 1. Binance API返回包含非ASCII字符的交易對

某些Binance交易對符號包含**中文字符**：
- `币安人生USDT` ❌
- `BTCUSDT` ✅  
- `ETHUSDT` ✅

### 2. URL編碼導致簽名計算失敗

當交易對符號包含非ASCII字符時：

```python
# 原始符號
symbol = '币安人生USDT'

# URL編碼後（用於簽名計算）
symbol_encoded = '%E5%B8%81%E5%AE%89%E4%BA%BA%E7%94%9FUSDT'

# 簽名計算錯誤
# Binance服務器無法驗證簽名 → -1022錯誤
```

### 3. 簽名驗證流程

```
1. 構建請求參數: symbol=币安人生USDT&quantity=11.0&...
2. URL編碼參數
3. 計算HMAC-SHA256簽名
4. 發送到Binance API
5. Binance服務器驗證簽名 → ❌ 失敗（-1022）
```

---

## ✅ 解決方案

### v3.2.1: 添加ASCII過濾器

**位置**: `src/services/data_service.py` (第58行)

**修改前**：
```python
self.all_symbols = [
    symbol['symbol']
    for symbol in exchange_info.get('symbols', [])
    if symbol['symbol'].endswith('USDT') 
    and symbol['status'] == 'TRADING'
    and symbol.get('contractType') == 'PERPETUAL'
]
```

**修改後**：
```python
self.all_symbols = [
    symbol['symbol']
    for symbol in exchange_info.get('symbols', [])
    if symbol['symbol'].endswith('USDT') 
    and symbol['status'] == 'TRADING'
    and symbol.get('contractType') == 'PERPETUAL'
    and symbol['symbol'].isascii()  # ✅ 排除中文等非ASCII交易對
]
```

**新增過濾規則**：
```python
symbol['symbol'].isascii()  # 只允許ASCII字符（A-Z, 0-9等）
```

---

## 📊 效果對比

### 修改前（會選中的符號）

```
✅ BTCUSDT
✅ ETHUSDT
❌ 币安人生USDT    # 導致簽名錯誤
✅ BNBUSDT
❌ 其他中文符號    # 導致簽名錯誤
```

### 修改後（會選中的符號）

```
✅ BTCUSDT
✅ ETHUSDT
🚫 币安人生USDT    # 已過濾
✅ BNBUSDT
🚫 其他中文符號    # 已過濾
```

---

## 🎯 預期改進

### 開倉成功率提升

**修改前**：
```
生成信號: 54個
開倉失敗: 某些包含中文符號的訂單（-1022錯誤）
成功率: <100%
```

**修改後**：
```
生成信號: ~50個（略少，因為過濾了中文符號）
開倉失敗: 0個（-1022錯誤）
成功率: 100% ✅
```

### 錯誤日誌改進

**修改前**：
```
❌ Binance API 錯誤 400: code=-1022, msg=Signature not valid
   symbol='币安人生USDT'
```

**修改後**：
```
✅ 無 -1022 錯誤（中文符號已被過濾）
```

---

## 🔧 其他可能的簽名錯誤

雖然v3.2.1修復了主要問題，但如果仍有-1022錯誤，可能原因：

### 1. 時間戳問題
```
症狀: 間歇性 -1022 錯誤
原因: 服務器時間不同步
解決: 使用 Binance 服務器時間
```

### 2. API密鑰錯誤
```
症狀: 所有請求都 -1022
原因: BINANCE_API_SECRET 錯誤
解決: 檢查環境變量
```

### 3. 特殊字符編碼
```
症狀: 特定交易對 -1022
原因: 符號包含特殊字符（空格、連字符等）
解決: 擴展ASCII檢查
```

---

## 📋 完整更新列表

| 版本 | 功能 | 狀態 |
|------|------|------|
| v3.1.6 | 錯誤診斷增強 | ✅ |
| v3.2.0 | 自動讀取賬戶餘額 | ✅ |
| **v3.2.1** | **ASCII過濾器（修復-1022）** | ✅ |

---

## 🚀 部署

### 推送到Railway

```bash
git add .
git commit -m "🔧 v3.2.1: 修復簽名錯誤（ASCII過濾器）"
git push railway main
```

### 驗證修復

```bash
railway logs --follow | grep "簽名\|1022\|Signature"
```

**預期輸出（應該沒有-1022錯誤）**：
```
✅ 成功加載 598 個交易對  # 略少於600，因為過濾了中文符號
✅ 開倉成功: BTCUSDT LONG @ 67834.5
✅ 開倉成功: ETHUSDT LONG @ 3456.7
# 沒有 -1022 錯誤
```

---

## 💡 技術細節

### `.isascii()` 方法

```python
# True: 只包含ASCII字符（0-127）
'BTCUSDT'.isascii()  # True
'ETH-USDT'.isascii()  # True  
'1000PEPEUSDT'.isascii()  # True

# False: 包含非ASCII字符（128+）
'币安人生USDT'.isascii()  # False
'ÉTHUSDT'.isascii()  # False
```

**ASCII字符集**：
- 字母: `A-Z`, `a-z`
- 數字: `0-9`
- 符號: `!@#$%^&*()-_=+`等
- **不包含**: 中文、日文、韓文、重音符號等

### 性能影響

**過濾器開銷**: 可忽略不計  
```python
# 每個符號只需 O(n) 時間檢查
symbol.isascii()  # 非常快

# 總時間: ~600個符號 × 0.0001秒 = 0.06秒
```

**對信號生成的影響**：
- 交易對數量: 600個 → ~598個（-2個中文符號）
- 影響: 微小（-0.3%）
- 信號質量: 更高（避免簽名錯誤）

---

## ✅ 驗證清單

部署v3.2.1後，確認：

- [ ] ✅ 無 -1022 錯誤（簽名驗證）
- [ ] ✅ 交易對加載成功（~598個）
- [ ] ✅ 信號生成正常
- [ ] ✅ 限價單成功
- [ ] ✅ 市價單成功
- [ ] ✅ 止損止盈設置成功
- [ ] 💰 賬戶餘額自動讀取（v3.2.0）
- [ ] 🔍 詳細錯誤診斷（v3.1.6）

---

## 🎯 下一步

1. **立即部署** v3.2.1到Railway
2. 監控日誌確認**無-1022錯誤**
3. 如果仍有其他400錯誤，根據v3.1.6的詳細錯誤碼診斷
4. 達到**100%開倉成功率**

---

## 🎉 總結

**v3.2.1修復了關鍵簽名驗證問題！**

**問題**: 中文交易對符號導致簽名失敗  
**解決**: ASCII過濾器排除非ASCII符號  
**效果**: 消除-1022錯誤，提升成功率

**立即部署命令**：
```bash
git add .
git commit -m "🔧 v3.2.1: ASCII過濾器修復簽名錯誤"
git push railway main
railway logs --follow
```

**現在系統會自動排除中文等非ASCII交易對，避免簽名驗證失敗！** ✅🔧
