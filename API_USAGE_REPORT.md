# Binance API 使用情況報告 v3.17.2+

## 📊 **當前API使用統計**

### **1. 配置參數**
```yaml
限流配置:
  - 最大請求數: 1920次/分鐘 (32次/秒)
  - 時間窗口: 60秒
  - 熔斷器: 5次失敗後阻斷60秒

緩存配置:
  - TICKER: 5秒
  - ACCOUNT: 10秒
  - KLINES: 300秒 (5分鐘)
  - EXCHANGE_INFO: 3600秒 (1小時)
  - 24H_TICKER: 60秒
```

---

## 🔍 **所有API調用點分析**

### **A. 初始化階段（啟動時1次）**

| API端點 | 調用位置 | 頻率 | 權重 | 緩存TTL |
|---------|---------|------|------|---------|
| `GET /fapi/v1/exchangeInfo` | `get_exchange_info()` | 1次/啟動 | 1 | 3600秒 |
| `GET /fapi/v1/ping` | `test_connection()` | 1次/啟動 | 1 | 無 |
| `POST /fapi/v1/listenKey` | `get_listen_key()` | 1次/啟動 | 1 | 無 |

**小計**: ~3次（僅啟動時）

---

### **B. 交易週期循環（每60秒）**

| API端點 | 調用位置 | 頻率 | 權重 | 緩存TTL |
|---------|---------|------|------|---------|
| `GET /fapi/v2/account` | `get_account_balance()` | 1次/週期 | 5 | 10秒 |
| `GET /fapi/v2/positionRisk` | `get_positions()` | 1次/週期 | 5 | 無 |
| `GET /fapi/v1/ticker/price` | `get_ticker()` (每幣種) | N次/週期 | 1 | 5秒 |
| `GET /fapi/v1/klines` | `get_klines()` (每幣種) | N次/週期 | 1 | 300秒 |

**每分鐘估算**:
- 固定調用: 2次（account + positions）
- 變動調用: N個幣種 × 2（ticker + klines）
- **假設監控200個幣種**: 2 + (200 × 2) = **402次/分鐘**

---

### **C. 倉位監控循環（每60秒）**

| API端點 | 調用位置 | 頻率 | 權重 | 緩存TTL |
|---------|---------|------|------|---------|
| `GET /fapi/v2/account` | `get_position_info_async()` | 1次/週期 | 5 | 10秒 |

**每分鐘估算**: 1次（如果WebSocket無數據）

---

### **D. 信號執行（按需）**

| API端點 | 調用位置 | 頻率 | 權重 | 緩存TTL |
|---------|---------|------|------|---------|
| `POST /fapi/v1/leverage` | `set_leverage()` | 1次/信號 | 1 | 無 |
| `POST /fapi/v1/order` | `place_order()` | 1次/信號 | 1 | 無 |
| `GET /fapi/v1/order` | `get_order()` | 1次/檢查 | 1 | 無 |
| `DELETE /fapi/v1/order` | `cancel_order()` | 1次/取消 | 1 | 無 |

**每分鐘估算**: 0-20次（取決於交易信號數量）

---

### **E. WebSocket維護（每30分鐘）**

| API端點 | 調用位置 | 頻率 | 權重 | 緩存TTL |
|---------|---------|------|------|---------|
| `PUT /fapi/v1/listenKey` | `renew_listen_key()` | 1次/30分鐘 | 1 | 無 |

**每分鐘估算**: 0.033次（可忽略）

---

## 📈 **總計API使用量（無WebSocket情況）**

### **最壞情況（200個幣種，每60秒輪詢）**

```
每分鐘總請求數:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
固定開銷（交易週期）:
  - get_account_balance: 1次
  - get_positions: 1次
  - get_position_info_async: 1次 (備援)
  小計: 3次

變動開銷（市場數據）:
  - get_ticker × 200幣種: 200次
  - get_klines × 200幣種: 200次
  小計: 400次

信號執行（假設每分鐘5個信號）:
  - set_leverage: 5次
  - place_order: 5次
  小計: 10次

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
總計: 413次/分鐘 ≈ 7次/秒
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**危險指標**:
- ⚠️ **Binance權重限制**: 2400權重/分鐘（部分端點權重>1）
- ⚠️ **系統限流**: 1920次/分鐘（32次/秒）
- 🔴 **實際使用**: 413次/分鐘（21%使用率）**但權重可能超標**

---

## 🚨 **問題診斷：為什麼被鎖？**

### **1. 權重計算錯誤**
```
實際權重計算（最壞情況）:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
每分鐘權重:
  - get_account_balance (權重5) × 1: 5
  - get_positions (權重5) × 1: 5
  - get_position_info_async (權重5) × 1: 5
  - get_ticker (權重1) × 200: 200
  - get_klines (權重1) × 200: 200
  - place_order (權重1) × 5: 5
  - set_leverage (權重1) × 5: 5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
總權重: 425/分鐘
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Binance限制: 2400權重/分鐘（安全線）
當前使用率: 17.7% ✅ (理論上未超標)
```

### **2. 可能的觸發原因**

#### **A. 緩存失效導致重複調用**
```python
# 當前問題：緩存TTL太短
CACHE_TTL_TICKER = 5秒   # ⚠️ 每分鐘可能調用12次
CACHE_TTL_ACCOUNT = 10秒  # ⚠️ 每分鐘可能調用6次
```

#### **B. 並行循環重複調用**
```
系統有3個並行循環，可能重複調用相同API:
  1. 交易週期循環（60秒）→ get_account_balance
  2. 倉位監控循環（60秒）→ get_position_info_async (內部調用account)
  3. 信號生成（每個幣種）→ get_ticker + get_klines

⚠️ 重複調用風險：同一API在不同循環中被多次調用
```

#### **C. 爆發式請求（Burst）**
```
啟動時可能瞬間發送大量請求:
  - 200個幣種 × get_ticker = 200次（瞬時）
  - 200個幣種 × get_klines = 200次（瞬時）
  
⚠️ 短時間內400次請求可能觸發限流
```

#### **D. 熔斷器失效後重試風暴**
```
熔斷器阻斷60秒後解除 → 積壓請求一次性發送
→ 再次觸發限流 → 再次熔斷 → 惡性循環
```

---

## 💡 **優化方案（6個級別）**

### **🟢 方案1：增加緩存TTL（立即生效，低風險）**

**修改配置**:
```python
# src/config.py
CACHE_TTL_TICKER: int = 30        # 5秒 → 30秒（減少83%調用）
CACHE_TTL_ACCOUNT: int = 30       # 10秒 → 30秒（減少67%調用）
CACHE_TTL_KLINES_DEFAULT: int = 600  # 300秒 → 600秒（10分鐘）
```

**預期效果**:
- 減少API調用: **~60%**
- 每分鐘請求數: 413 → **~165次**
- 風險: 數據延遲增加（最多30秒）

---

### **🟡 方案2：減少監控幣種數量（立即生效）**

**修改配置**:
```python
# src/config.py
TOP_VOLATILITY_SYMBOLS: int = 50  # 999 → 50（減少75%幣種）
```

**預期效果**:
- 減少API調用: **~75%**
- 每分鐘請求數: 413 → **~113次**
- 風險: 錯過部分交易機會

---

### **🟡 方案3：增加監控週期（中等影響）**

**修改配置**:
```python
# src/config.py
CYCLE_INTERVAL: int = 120              # 60秒 → 120秒（2分鐘）
POSITION_MONITOR_INTERVAL: int = 120  # 60秒 → 120秒（2分鐘）
```

**預期效果**:
- 減少API調用: **~50%**
- 每分鐘請求數: 413 → **~206次**
- 風險: 市場反應速度降低

---

### **🟠 方案4：批量API調用（需要代碼修改）**

**實施方式**:
```python
# 替換單個ticker調用為批量調用
# 當前: 200次 × get_ticker(symbol)
# 優化: 1次 × get_24h_tickers()（所有幣種）

async def get_all_tickers_batch(self) -> Dict[str, float]:
    """批量獲取所有幣種價格（1次API調用）"""
    result = await self._request("GET", "/fapi/v1/ticker/price")
    return {item['symbol']: float(item['price']) for item in result}
```

**預期效果**:
- 減少API調用: **~48%**（200次ticker → 1次批量）
- 每分鐘請求數: 413 → **~214次**
- 風險: 需要修改代碼邏輯

---

### **🔴 方案5：完全依賴WebSocket（最佳，但Replit無法使用）**

**實施方式**:
```python
# 已實現：WebSocketManager v3.17.2+
# - KlineFeed: @kline_1m訂閱（取代REST輪詢）
# - AccountFeed: listenKey倉位監控（取代REST輪詢）

# REST API僅用於:
# - 初始化（1次）
# - listenKey續期（每30分鐘）
# - 下單執行（按需）
```

**預期效果**:
- 減少API調用: **~90%**
- 每分鐘請求數: 413 → **~40次**
- 風險: ❌ Replit地理限制（HTTP 451）

---

### **🟣 方案6：智能輪詢（動態調整，需要AI邏輯）**

**實施方式**:
```python
class AdaptivePoller:
    """自適應輪詢器（根據市場活躍度動態調整）"""
    
    def __init__(self):
        self.min_interval = 60   # 最小60秒
        self.max_interval = 300  # 最大5分鐘
        self.current_interval = 60
    
    async def adjust_interval(self, market_volatility: float):
        """根據市場波動性調整輪詢頻率"""
        if market_volatility > 0.02:  # 高波動
            self.current_interval = self.min_interval
        elif market_volatility < 0.005:  # 低波動
            self.current_interval = self.max_interval
        else:  # 中等波動
            self.current_interval = 120
```

**預期效果**:
- 減少API調用: **~30-70%**（動態）
- 每分鐘請求數: 變動（市場安靜時降低）
- 風險: 複雜度增加

---

## ✅ **推薦組合方案**

### **立即實施（0風險）**

```yaml
優先級1 - 緩存優化:
  CACHE_TTL_TICKER: 30秒
  CACHE_TTL_ACCOUNT: 30秒
  CACHE_TTL_KLINES_DEFAULT: 600秒
  
優先級2 - 減少幣種:
  TOP_VOLATILITY_SYMBOLS: 50個
  
優先級3 - 延長週期:
  CYCLE_INTERVAL: 120秒
  POSITION_MONITOR_INTERVAL: 120秒
```

**綜合效果**:
- API調用減少: **~85%**
- 每分鐘請求數: 413 → **~62次**
- 每分鐘權重: 425 → **~71權重**
- 使用率: 21% → **3%** ✅

---

### **中期優化（1-2週）**

```yaml
優先級4 - 批量調用:
  實施 get_all_tickers_batch()
  實施 get_all_positions_batch()
  
優先級5 - 智能輪詢:
  根據市場活躍度動態調整週期
  休市時段降低頻率
```

---

### **長期目標（部署到Railway）**

```yaml
優先級6 - WebSocket完全啟用:
  部署到Railway（避免地理限制）
  KlineFeed即時K線（零REST調用）
  AccountFeed即時倉位（零REST調用）
  
預期效果:
  - API調用減少90%
  - 每分鐘請求數: 413 → 40次
  - 零延遲市場數據
```

---

## 📊 **效果對比表**

| 方案 | API調用/分鐘 | 權重/分鐘 | 使用率 | 風險 | 實施難度 |
|------|-------------|----------|--------|------|---------|
| **當前** | 413 | 425 | 21% | 🔴高 | - |
| 方案1（緩存） | 165 | 180 | 7.5% | 🟡低 | ⭐ |
| 方案2（減幣種） | 113 | 115 | 4.8% | 🟡低 | ⭐ |
| 方案3（延長週期） | 206 | 213 | 8.9% | 🟡中 | ⭐ |
| 方案4（批量） | 214 | 220 | 9.2% | 🟠中 | ⭐⭐⭐ |
| 方案5（WebSocket） | 40 | 45 | 1.9% | 🟢低 | ⭐⭐⭐⭐⭐ |
| **組合1+2+3** | **62** | **71** | **3%** | 🟢低 | ⭐⭐ |

---

## 🎯 **立即行動建議**

### **Step 1: 修改配置文件（5分鐘）**
```bash
# 編輯 src/config.py
CACHE_TTL_TICKER = 30
CACHE_TTL_ACCOUNT = 30
TOP_VOLATILITY_SYMBOLS = 50
CYCLE_INTERVAL = 120
POSITION_MONITOR_INTERVAL = 120
```

### **Step 2: 重啟系統驗證**
```bash
# 監控API使用情況
# 觀察熔斷器狀態
# 確認不再被鎖
```

### **Step 3: 部署到Railway（長期）**
```bash
# 避開Replit地理限制
# 啟用WebSocket完整功能
# 減少90% API調用
```

---

**文檔生成時間**: 2025-10-29  
**系統版本**: v3.17.2+  
**當前狀態**: ⚠️ API使用過高，需要立即優化
