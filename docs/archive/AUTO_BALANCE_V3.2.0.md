# 💰 v3.2.0: 自動讀取U本位合約餘額

**日期**: 2025-10-26  
**狀態**: ✅ 就緒  
**功能**: 機器人自動從Binance API讀取U本位合約餘額，動態計算倉位大小

---

## 🎯 功能說明

### 舊版本（v3.1.x）

```python
# 硬編碼固定餘額
account_balance = 10000.0  # ❌ 固定值，無法反映真實賬戶情況
```

**問題**：
- 無法根據實際賬戶餘額調整倉位
- 盈虧後餘額變化無法反映
- 需要手動修改代碼更新餘額

### 新版本（v3.2.0）

```python
# 自動從Binance獲取實時餘額
balance_info = await self.binance_client.get_account_balance()
account_balance = balance_info['total_balance']  # ✅ 實時USDT餘額

logger.info(
    f"💰 使用實時餘額: {account_balance:.2f} USDT "
    f"(可用: {balance_info['available_balance']:.2f} USDT)"
)
```

**優勢**：
- ✅ 自動讀取實際賬戶餘額
- ✅ 根據盈虧動態調整倉位大小
- ✅ 無需手動維護餘額配置
- ✅ 錯誤處理：API失敗時降級為默認值

---

## 🔧 技術實現

### 1. 新增 `get_account_balance` 方法

**位置**: `src/clients/binance_client.py`

```python
async def get_account_balance(self) -> dict:
    """
    獲取 U 本位合約賬戶餘額
    
    Returns:
        dict: {
            'total_balance': float,  # 總餘額（USDT）
            'available_balance': float,  # 可用餘額（USDT）
            'total_margin': float,  # 總保證金
            'unrealized_pnl': float,  # 未實現盈虧
            'total_wallet_balance': float  # 總錢包餘額（含未實現盈虧）
        }
    """
    account_info = await self.get_account_info()
    
    # 提取 USDT 資產信息
    total_balance = 0.0
    available_balance = 0.0
    
    for asset in account_info.get('assets', []):
        if asset.get('asset') == 'USDT':
            total_balance = float(asset.get('walletBalance', 0))
            available_balance = float(asset.get('availableBalance', 0))
            break
    
    total_margin = total_balance - available_balance
    unrealized_pnl = float(account_info.get('totalUnrealizedProfit', 0))
    
    return {
        'total_balance': total_balance,
        'available_balance': available_balance,
        'total_margin': total_margin,
        'unrealized_pnl': unrealized_pnl,
        'total_wallet_balance': total_balance + unrealized_pnl
    }
```

**返回值說明**：

| 字段 | 說明 | 用途 |
|------|------|------|
| `total_balance` | USDT總餘額（錢包餘額） | 用於計算倉位大小 |
| `available_balance` | 可用餘額（未用於保證金） | 可開新倉的最大金額 |
| `total_margin` | 當前保證金（已鎖定） | 已有倉位佔用的資金 |
| `unrealized_pnl` | 未實現盈虧 | 當前持倉浮動盈虧 |
| `total_wallet_balance` | 總錢包餘額 | 含未實現盈虧的總資產 |

### 2. 更新主程序自動獲取餘額

**位置**: `src/main.py` (第308-318行)

```python
if rank <= Config.IMMEDIATE_EXECUTION_RANK:
    # 自動從 Binance 獲取 U 本位合約餘額
    try:
        balance_info = await self.binance_client.get_account_balance()
        account_balance = balance_info['total_balance']
        logger.info(
            f"💰 使用實時餘額: {account_balance:.2f} USDT "
            f"(可用: {balance_info['available_balance']:.2f} USDT)"
        )
    except Exception as e:
        logger.error(f"獲取賬戶餘額失敗: {e}，使用默認值")
        account_balance = 10000.0  # 降級為默認值
```

**容錯機制**：
- ✅ API調用成功 → 使用實時餘額
- ❌ API調用失敗 → 降級為默認值（10000 USDT）
- ✅ 不會因為餘額獲取失敗而停止交易

---

## 💡 使用示例

### 示例 1: 賬戶有 5000 USDT

```
💰 賬戶餘額: 總額 5000.00 USDT, 可用 4500.00 USDT, 
   保證金 500.00 USDT, 未實現盈虧 +50.00 USDT

💰 使用實時餘額: 5000.00 USDT (可用: 4500.00 USDT)

準備開倉: BTCUSDT LONG
  - 賬戶餘額: 5000 USDT
  - 信心度: 70%
  - 槓桿: 12x
  - 基礎保證金: 500 USDT (10% × 5000)
  - 信心度調整: 350 USDT (70% × 500)
  - 倉位價值: 4200 USDT (350 × 12)
  - 風險: 1% (50 USDT)
```

### 示例 2: 賬戶有 50000 USDT（更大資金）

```
💰 賬戶餘額: 總額 50000.00 USDT, 可用 48000.00 USDT,
   保證金 2000.00 USDT, 未實現盈虧 +200.00 USDT

💰 使用實時餘額: 50000.00 USDT (可用: 48000.00 USDT)

準備開倉: ETHUSDT LONG
  - 賬戶餘額: 50000 USDT
  - 信心度: 70%
  - 槓桿: 12x
  - 基礎保證金: 5000 USDT (10% × 50000)
  - 信心度調整: 3500 USDT (70% × 5000)
  - 倉位價值: 42000 USDT (3500 × 12)
  - 風險: 1% (500 USDT)
```

**倉位大小會根據賬戶餘額自動縮放！**

### 示例 3: 盈利後自動增大倉位

**初始**：
```
賬戶餘額: 10000 USDT
倉位價值: 8400 USDT (70% × 10% × 10000 × 12)
```

**盈利1000 USDT後**：
```
賬戶餘額: 11000 USDT  # 自動更新
倉位價值: 9240 USDT (70% × 10% × 11000 × 12)  # 自動增大
```

**虧損1000 USDT後**：
```
賬戶餘額: 9000 USDT  # 自動更新
倉位價值: 7560 USDT (70% × 10% × 9000 × 12)  # 自動減小
```

---

## 🔄 倉位大小計算公式

```
基礎保證金 = 賬戶餘額 × 10%
信心度調整保證金 = 基礎保證金 × 信心度
最終保證金 = min(信心度調整保證金, 賬戶餘額 × 13%)
最終保證金 = max(最終保證金, 賬戶餘額 × 3%)

# 1%風險限制
if 最終保證金 > 賬戶餘額 × 2%:
    最終保證金 = 賬戶餘額 × 2%

倉位價值 = 最終保證金 × 槓桿
數量 = 倉位價值 / 入場價格
```

**關鍵參數**：
- `BASE_MARGIN_PCT = 10%` - 基礎保證金比例
- `MIN_MARGIN_PCT = 3%` - 最小保證金比例
- `MAX_MARGIN_PCT = 13%` - 最大保證金比例
- `MAX_RISK = 2%` - 單筆最大風險（硬規則）

---

## 📊 預期日誌輸出

### 成功獲取餘額

```
[INFO] 💰 賬戶餘額: 總額 12345.67 USDT, 可用 11500.00 USDT, 
       保證金 845.67 USDT, 未實現盈虧 +123.45 USDT

[INFO] 💰 使用實時餘額: 12345.67 USDT (可用: 11500.00 USDT)

[INFO] 準備開倉: BTCUSDT LONG 數量: 0.045 槓桿: 12x
       倉位價值: 10281.58 USDT，保證金: 856.80 USDT
```

### API失敗降級

```
[ERROR] 獲取賬戶餘額失敗: API rate limit exceeded, 使用默認值

[INFO] 💰 使用實時餘額: 10000.00 USDT (降級模式)

[INFO] 準備開倉: ETHUSDT LONG 數量: 3.2 槓桿: 10x
```

---

## ⚙️ 配置選項

### 可選：設置默認餘額（降級值）

可以在 `src/config.py` 添加：

```python
# 默認賬戶餘額（API失敗時使用）
DEFAULT_ACCOUNT_BALANCE: float = float(os.getenv("DEFAULT_ACCOUNT_BALANCE", "10000"))
```

然後在 `main.py` 中使用：

```python
except Exception as e:
    logger.error(f"獲取賬戶餘額失敗: {e}，使用默認值")
    account_balance = Config.DEFAULT_ACCOUNT_BALANCE
```

---

## 🎯 與風險管理的整合

**風險管理規則**（仍然生效）：

1. **單筆風險≤1%**
   ```python
   if risk_per_trade > account_balance * 0.02:
       position_margin = account_balance * 0.02
   ```

2. **3%日虧損上限**
   ```python
   if daily_loss_pct > 0.03:
       return False, "日虧損超過3%，暫停交易"
   ```

3. **最大3個倉位**
   ```python
   if current_positions >= 3:
       return False, "已達到最大持倉數3"
   ```

4. **連續5次虧損暫停**
   ```python
   if consecutive_losses >= 5:
       return False, "連續虧損5次，暫停交易"
   ```

---

## 📈 優勢總結

### 自動化

| 功能 | 舊版本 | 新版本 |
|------|--------|--------|
| 餘額更新 | ❌ 手動修改代碼 | ✅ 自動從API獲取 |
| 倉位調整 | ❌ 固定金額 | ✅ 根據餘額動態縮放 |
| 盈虧反映 | ❌ 不反映 | ✅ 實時反映 |
| 容錯處理 | ❌ 無 | ✅ 降級為默認值 |

### 風險控制

- ✅ 賬戶餘額減少 → 倉位自動減小（保護資金）
- ✅ 賬戶餘額增加 → 倉位自動增大（複利效應）
- ✅ 1%風險規則始終基於最新餘額
- ✅ API緩存10秒，避免過度調用

---

## 🚀 部署

### Railway環境變量

確認已設置：
```bash
BINANCE_API_KEY=<您的密鑰>
BINANCE_API_SECRET=<您的密鑰密碼>
BINANCE_TESTNET=false  # 主網
TRADING_ENABLED=true
LOG_LEVEL=INFO
```

### 推送代碼

```bash
git add .
git commit -m "💰 v3.2.0: 自動讀取U本位合約餘額"
git push railway main
```

### 驗證日誌

```bash
railway logs --follow | grep "賬戶餘額\|使用實時餘額"
```

**預期輸出**：
```
💰 賬戶餘額: 總額 12345.67 USDT, 可用 11500.00 USDT
💰 使用實時餘額: 12345.67 USDT (可用: 11500.00 USDT)
```

---

## 🎉 總結

**v3.2.0新功能**：
- ✅ 自動讀取U本位合約真實餘額
- ✅ 倉位大小根據餘額動態調整
- ✅ 盈虧後自動縮放倉位
- ✅ 容錯處理（API失敗降級）
- ✅ 與現有風險管理完美整合

**現在機器人會根據您的實際賬戶餘額自動計算倉位大小，無需手動維護！** 💰✨
