# 🛡️ 安全機制強化 v3.6.0

**日期**: 2025-10-27  
**版本**: v3.6.0  
**狀態**: ✅ 完成

---

## 📋 用戶需求

### 1️⃣ 止損止盈同步設置
**問題**: 止損止盈設置可能有缺漏，導致倉位無保護  
**要求**: 建倉的同時必須同步設置止損止盈

### 2️⃣ 單倉位保證金限制
**問題**: 需要控制單個倉位風險  
**要求**: 單個倉位最高保證金不得超過總餘額的50%

---

## ✅ 實施方案

### 1️⃣ 止損止盈同步設置強化

#### **v3.5.0 原有機制**
```python
# 開倉後立即設置止損止盈
await self._set_stop_loss_take_profit_parallel(
    symbol, direction, quantity, stop_loss, take_profit
)

# 如果失敗，嘗試平倉
if 設置失敗:
    await self._place_market_order(...)  # 平倉
```

**問題**:
- 重試次數僅3次
- 無訂單驗證機制
- 部分失敗處理不夠嚴格

---

#### **v3.6.0 強化機制** ✅

##### **A. 增加重試次數：3次 → 5次**
```python
await self._set_stop_loss_take_profit_parallel(
    symbol, direction, quantity, stop_loss, take_profit,
    max_retries=5  # 從3次增加到5次
)
```

##### **B. 添加訂單驗證機制**
```python
# 設置成功後，驗證訂單確實存在
sl_order_id, tp_order_id = await self._set_stop_loss_take_profit_parallel(...)

# 驗證止損訂單
sl_verified = await self._verify_order_exists(symbol, sl_order_id)
# 驗證止盈訂單
tp_verified = await self._verify_order_exists(symbol, tp_order_id)

if not sl_verified or not tp_verified:
    raise Exception("止損止盈訂單驗證失敗")
```

**驗證邏輯** (`_verify_order_exists`):
```python
async def _verify_order_exists(symbol, order_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            order = await self.client.get_order(symbol, order_id)
            if order and order.get('orderId') == order_id:
                return True  # 訂單存在
        except:
            await asyncio.sleep(0.5)
            continue
    return False  # 驗證失敗
```

##### **C. 強化錯誤處理**
```python
try:
    # 設置 + 驗證
    sl_order_id, tp_order_id = await self._set_stop_loss_take_profit_parallel(...)
    sl_verified = await self._verify_order_exists(symbol, sl_order_id)
    tp_verified = await self._verify_order_exists(symbol, tp_order_id)
    
    if not sl_verified or not tp_verified:
        raise Exception("止損止盈訂單驗證失敗")
        
except Exception as e:
    logger.critical(f"🚨 建倉成功但無保護，必須立即平倉！{symbol}")
    
    # 🔴 強制平倉
    close_order = await self._place_market_order(
        symbol=symbol,
        side="SELL" if direction == "LONG" else "BUY",
        quantity=quantity,
        direction=direction
    )
    
    if not close_order:
        logger.critical(f"🚨🚨 致命錯誤：{symbol} 平倉失敗！請立即手動處理！")
    
    return None  # 拒絕開倉
```

##### **D. 返回訂單ID用於追蹤**
```python
async def _set_stop_loss_take_profit_parallel(...) -> Tuple[int, int]:
    """
    Returns:
        Tuple[int, int]: (止損訂單ID, 止盈訂單ID)
    """
    # ...設置止損止盈...
    
    return (sl_order_id, tp_order_id)
```

---

#### **安全保障流程**

```
┌──────────────────────────────────────────────────────────────┐
│ 1. 開倉成功                                                  │
│    └─ 獲取實際成交數量（處理部分成交）                      │
└───────────────────────┬──────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. 並行設置止損止盈（5次重試）                               │
│    ├─ 止損訂單: STOP_MARKET, closePosition=true             │
│    └─ 止盈訂單: TAKE_PROFIT_MARKET, closePosition=true      │
└───────────────────────┬──────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. 訂單驗證（3次重試）                                       │
│    ├─ 查詢止損訂單: GET /fapi/v1/order                       │
│    ├─ 查詢止盈訂單: GET /fapi/v1/order                       │
│    └─ 確認訂單ID匹配、狀態正常                               │
└───────────────────────┬──────────────────────────────────────┘
                        ↓
                  驗證成功？
                   /      \
                 是         否
                ↓           ↓
        ┌──────────────┐  ┌──────────────────────────────────┐
        │ 4a. 開倉成功  │  │ 4b. 驗證失敗                      │
        │    記錄交易   │  │    ├─ 記錄錯誤日誌                │
        └──────────────┘  │    ├─ 強制平倉（避免無保護倉位）  │
                          │    ├─ 平倉成功：記錄警告          │
                          │    └─ 平倉失敗：CRITICAL警報      │
                          └──────────────────────────────────┘
```

---

### 2️⃣ 單倉位保證金50%上限 ✅

#### **實施位置**: `src/managers/risk_manager.py`

```python
def calculate_position_size(
    self,
    account_balance: float,
    confidence_score: float,
    current_leverage: int
) -> Dict:
    """計算倉位大小"""
    
    # 基礎計算
    base_margin = account_balance * BASE_MARGIN_PCT  # 10%
    confidence_adjusted = base_margin * (confidence_score / 1.0)
    
    position_margin = max(
        account_balance * MIN_MARGIN_PCT,  # 最小3%
        min(confidence_adjusted, account_balance * MAX_MARGIN_PCT)  # 最大13%
    )
    
    position_value = position_margin * current_leverage
    
    # 風險限制：單筆交易不超過2%
    risk_per_trade = position_margin
    max_risk = account_balance * 0.02
    if risk_per_trade > max_risk:
        position_margin = max_risk
        position_value = position_margin * current_leverage
    
    # 🛡️ 硬性限制：單個倉位保證金不得超過可用資金50%
    # 無論信心指數、勝率、槓桿如何，這是絕對上限
    max_position_margin = account_balance * 0.5
    if position_margin > max_position_margin:
        logger.warning(
            f"⚠️  倉位保證金超過50%上限: "
            f"{position_margin:.2f} USDT ({position_margin/account_balance:.1%}) "
            f"→ 強制限制為 {max_position_margin:.2f} USDT (50%)"
        )
        position_margin = max_position_margin
        position_value = position_margin * current_leverage
    
    # 使用最終保證金計算風險百分比
    final_risk_pct = position_margin / account_balance
    
    return {
        'position_margin': position_margin,      # 實際保證金
        'position_value': position_value,        # 倉位價值
        'leverage': current_leverage,            # 槓桿
        'margin_pct': final_risk_pct,            # 保證金百分比
        'risk_pct': final_risk_pct               # 風險百分比
    }
```

#### **保障邏輯**

1. **基礎計算**:
   - 基礎保證金: 賬戶餘額 × 10%
   - 信心調整: 基礎保證金 × 信心度
   - 範圍限制: 3% ~ 13%

2. **風險限制**:
   - 單筆交易風險: ≤ 2% 賬戶餘額

3. **🛡️ 硬性上限** (優先級最高):
   - **絕對上限: 50% 賬戶餘額**
   - 無論其他條件如何，保證金不會超過此值
   - 超過時強制調整並記錄警告日誌

#### **示例場景**

**場景1: 正常倉位**
```
賬戶餘額: 10,000 USDT
信心度: 80%
槓桿: 10x

計算過程:
1. 基礎保證金: 10,000 × 10% = 1,000 USDT
2. 信心調整: 1,000 × 80% = 800 USDT
3. 範圍限制: 800 USDT (在3%-13%範圍內)
4. 風險限制: 800 USDT < 2% (200 USDT)? 否，調整為200 USDT
5. 50%上限: 200 USDT < 50% (5,000 USDT)? 是，通過 ✅

最終保證金: 200 USDT (2%)
倉位價值: 200 × 10 = 2,000 USDT
```

**場景2: 觸發50%上限**
```
賬戶餘額: 10,000 USDT
信心度: 100%
槓桿: 20x
異常情況（配置錯誤或極端市場）

假設計算出:
保證金: 6,000 USDT (60%)

50%上限檢查:
6,000 > 5,000 (50%) → 強制調整 🚨

最終保證金: 5,000 USDT (50%)
倉位價值: 5,000 × 20 = 100,000 USDT

日誌輸出:
⚠️  倉位保證金超過50%上限: 6,000 USDT (60%) → 強制限制為 5,000 USDT (50%)
```

---

## 📊 安全機制對比

| 機制 | v3.5.0 | v3.6.0 | 改進 |
|------|--------|--------|------|
| **止損止盈重試次數** | 3次 | 5次 | +67% |
| **訂單驗證** | ❌ 無 | ✅ 3次重試 | 新增 |
| **設置失敗處理** | 嘗試平倉 | 強制平倉+CRITICAL警報 | 更嚴格 |
| **訂單ID追蹤** | ❌ 無 | ✅ 返回+記錄 | 新增 |
| **單倉保證金上限** | ✅ 50% | ✅ 50% | 已實現 |
| **風險日誌** | INFO | WARNING/CRITICAL | 更明確 |

---

## 🔍 測試驗證

### 止損止盈測試用例

#### 用例1: 正常開倉
```
輸入:
- 開倉成功: BTCUSDT LONG 0.1 BTC @ 50,000
- 止損: 49,000
- 止盈: 52,000

預期流程:
1. 開倉成功 ✅
2. 並行設置止損止盈 ✅
3. 訂單驗證通過 ✅
4. 記錄交易 ✅

日誌:
✅ 止損止盈並行設置成功: BTCUSDT (SL:123456, TP:123457)
🔍 驗證止損止盈訂單...
✅ 訂單驗證成功: BTCUSDT 訂單ID 123456 狀態 NEW
✅ 訂單驗證成功: BTCUSDT 訂單ID 123457 狀態 NEW
✅ 止損止盈訂單已驗證: BTCUSDT (SL:123456, TP:123457)
```

#### 用例2: 止盈失敗，重試成功
```
輸入:
- 開倉成功
- 止損成功
- 止盈失敗（第1次）
- 止盈成功（第2次）

預期流程:
1. 開倉成功 ✅
2. 並行設置：止損✅ 止盈❌
3. 重試止盈 ✅
4. 訂單驗證通過 ✅

日誌:
⚠️  止損成功但止盈失敗 (第1次嘗試): BTCUSDT
🔄 重試止盈設置...
✅ 止盈重試成功: BTCUSDT
```

#### 用例3: 驗證失敗，強制平倉
```
輸入:
- 開倉成功
- 止損止盈設置返回成功
- 訂單驗證失敗（API異常）

預期流程:
1. 開倉成功 ✅
2. 設置止損止盈 ✅
3. 訂單驗證失敗 ❌
4. 觸發強制平倉 ✅

日誌:
❌ 訂單驗證失敗（已重試3次）: BTCUSDT 訂單ID 123456
❌ 止損止盈設置/驗證失敗: 止損止盈訂單驗證失敗: SL=不存在, TP=存在
🚨 建倉成功但無保護，必須立即平倉！BTCUSDT
✅ 已緊急平倉無保護持倉: BTCUSDT
```

#### 用例4: 平倉失敗，CRITICAL警報
```
輸入:
- 開倉成功
- 止損止盈設置失敗
- 強制平倉失敗

預期流程:
1. 開倉成功 ✅
2. 設置失敗 ❌
3. 平倉失敗 ❌
4. CRITICAL警報 🚨

日誌:
❌ 止損止盈設置/驗證失敗: ...
🚨 建倉成功但無保護，必須立即平倉！BTCUSDT
🚨🚨 致命錯誤：BTCUSDT 平倉失敗！請立即手動處理！
```

### 保證金限制測試用例

#### 用例1: 正常倉位（<50%）
```
輸入:
- 賬戶餘額: 10,000 USDT
- 信心度: 70%
- 槓桿: 10x

計算:
- 保證金: 200 USDT (2%)
- 倉位價值: 2,000 USDT

結果: ✅ 通過（< 50%）
```

#### 用例2: 觸發50%上限
```
輸入:
- 賬戶餘額: 10,000 USDT
- 計算出保證金: 6,000 USDT (60%)

預期:
- 調整為: 5,000 USDT (50%)
- 日誌: ⚠️  倉位保證金超過50%上限: 6,000 USDT (60%) → 強制限制為 5,000 USDT (50%)

結果: ✅ 強制限制
```

---

## 🚀 部署建議

### 環境配置
無需額外配置，使用現有Config參數：
```python
# 止損止盈配置（使用默認值即可）
# max_retries=5 已寫入代碼

# 保證金限制（已固定為50%）
# max_position_margin = account_balance * 0.5
```

### 監控重點
1. **止損止盈設置日誌**:
   - 關注 `✅ 止損止盈訂單已驗證` 日誌
   - 監控 `⚠️  止損成功但止盈失敗` 警告
   - 嚴格處理 `🚨 建倉成功但無保護` CRITICAL日誌

2. **保證金限制日誌**:
   - 監控 `⚠️  倉位保證金超過50%上限` 警告
   - 如頻繁觸發，檢查Config配置是否合理

---

## ✅ 完成清單

- [x] 止損止盈重試次數：3次 → 5次
- [x] 新增訂單驗證機制（`_verify_order_exists`）
- [x] 強化錯誤處理（強制平倉+CRITICAL警報）
- [x] 返回訂單ID用於追蹤
- [x] 驗證單倉保證金50%上限已實現
- [x] 創建安全機制文檔
- [ ] Architect代碼審查
- [ ] 生產環境測試

---

## 📝 版本歷史

### v3.6.0 (2025-10-27)
- ✅ 止損止盈同步設置強化（5次重試+訂單驗證）
- ✅ 確認單倉保證金50%上限已實現

### v3.5.0 (2025-10-26)
- 並行止損止盈設置（3次重試）
- 快速訂單確認（0.5秒間隔）
- 部分成交精確處理

### v3.0.0 (2025-10-25)
- 期望值驅動系統
- 動態槓桿調整
- 虛擬倉位管理

---

**文檔完成**: 2025-10-27  
**下一步**: Architect審查 → 部署測試
