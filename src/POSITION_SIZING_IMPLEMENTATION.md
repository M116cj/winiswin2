# 📊 百分比收益率 + 部位規模計算 - 完整實現指南

## 架構概述

```
信號生成 (Signal)
    ↓
ML 模型預測 (Confidence + Direction)
    ↓
百分比收益率轉換 (predicted_return_pct)
    ↓
部位規模計算 (Position Sizing)
    ├─ 版本 A: 固定風險比例
    └─ 版本 B: 凱利公式 + ATR 加權
    ↓
實際下單金額 (Order Amount)
    ↓
交易執行 (Trade Execution)
    ↓
資本追蹤 (Capital Tracker)
```

---

## 1️⃣ ML 模型輸出變更

### 舊架構
```python
# 模型輸出: 贏的概率
prediction = {
    'win_probability': 0.75,  # 75% 贏的機率
    'confidence': 0.80        # 80% 信心度
}
```

### 新架構
```python
# 模型輸出: 預測收益率 (%)
prediction = {
    'predicted_return_pct': 0.05,  # +5% 預測收益率
    'confidence': 0.80,
    'direction': 'UP'
}

# 計算方式:
# Base Return: 2%
# Confidence Factor: (0.80 - 0.60) * 10 * 0.7 / 100 = 0.014 (1.4%)
# Winrate Factor: (0.70 - 0.60) * 5 * 0.3 / 100 = 0.0015 (0.15%)
# Final: 2% + 1.4% + 0.15% ≈ 3.5% → 實際 5% (考慮市場波動)
```

---

## 2️⃣ 帳戶資本追蹤

### 初始化
```python
from src.capital_tracker import init_capital_tracker, get_total_equity

# 初始化（虛擬帳戶 $10,000）
tracker = init_capital_tracker(initial_balance=10000)

# 隨時獲取總權益
total_equity = get_total_equity()  # $10,000 初始化
```

### 帳戶狀態結構
```python
account_status = {
    'total_equity': 10500,           # 總權益 = 現金 + 開倉值
    'available_balance': 8000,       # 可用現金
    'unrealized_pnl': 500,           # 未實現損益
    'realized_pnl': 0,               # 已實現損益
    'open_positions': 1,             # 開倉數量
    'trade_count': 0,                # 完成交易數
    'win_rate': 0,                   # 勝率
    'total_return_pct': 5.0          # 總回報率 %
}
```

---

## 3️⃣ 部位規模計算 - 版本 A (基礎版)

### 公式
```
下單金額 = (總資金 × 風險%) / (停損%)

例子:
  總資金: $10,000
  風險: 2% = $200
  停損: 2%
  
  下單金額 = $200 / 0.02 = $10,000

  實際數量 = $10,000 / 當前價格
            = $10,000 / $42,000 = 0.238 BTC
```

### 使用方式
```python
from src.position_sizing import calculate_position_size_v1
from src.capital_tracker import get_total_equity

# 計算下單規模
total_capital = get_total_equity()  # $10,000

result = calculate_position_size_v1(
    total_capital=total_capital,
    predicted_return_pct=0.05,        # +5% 預測
    stop_loss_pct=0.02,               # 2% 停損
    symbol='BTCUSDT',
    current_price=42000,
    leverage=1
)

print(f"下單金額: ${result['order_amount']:.2f}")
print(f"下單數量: {result['quantity']:.6f} BTC")
print(f"風險金額: ${result['risk_amount']:.2f}")
print(f"止盈距離: {result['tp_pct']:.2%}")
print(f"止損距離: {result['sl_pct']:.2%}")

# 輸出:
# 下單金額: $10,000
# 下單數量: 0.238095 BTC
# 風險金額: $200
# 止盈距離: 7% (2% SL + 5% Prediction)
# 止損距離: 2%
```

---

## 4️⃣ 部位規模計算 - 版本 B (進階版)

### 凱利公式
```
Kelly % = (Win% × Avg Win - Loss% × Avg Loss) / Avg Win

例子:
  Winrate: 70%
  Avg Win: 5%
  Avg Loss: 1%
  
  Kelly = (0.70 × 5% - 0.30 × 1%) / 5%
        = (3.5% - 0.3%) / 5%
        = 3.2% / 5%
        = 0.64 = 64% (通常限制在 0.5% - 25%)

  Position Size = Capital × Kelly %
                = $10,000 × 6.4% (假設限制在 6.4%)
                = $640 下單金額
```

### ATR 波動率加權
```
ATR Weight = Reference ATR / Current ATR

例子:
  Reference ATR: 2% (正常)
  Current ATR: 1% (低波動 - 更安全)
  
  Weight = 2% / 1% = 2.0
  
  效果: 可以擴大部位 2 倍（因為市場更穩定）
  
  Current ATR: 4% (高波動 - 更風險)
  Weight = 2% / 4% = 0.5
  
  效果: 縮小部位 50%（因為市場波動性高）
```

### 信心度因子
```
Confidence Factor = 1.0 + (Confidence - 0.60) × 2.5

例子:
  Confidence: 0.60 → Factor: 1.0 (基準)
  Confidence: 0.70 → Factor: 1.25 (擴大 25%)
  Confidence: 0.80 → Factor: 1.5 (擴大 50%)
  Confidence: 1.00 → Factor: 2.0 (擴大 2 倍)
```

### 使用方式
```python
from src.position_sizing import calculate_position_size_v2
from src.capital_tracker import get_total_equity

# 計算下單規模 (V2 - 進階)
total_capital = get_total_equity()

result = calculate_position_size_v2(
    total_capital=total_capital,
    predicted_return_pct=0.05,        # 模型預測 +5%
    confidence=0.80,                  # 80% 信心度
    win_rate=0.70,                    # 70% 歷史勝率
    atr_pct=0.015,                    # 1.5% ATR (低於 2% 參考)
    current_price=42000,
    symbol='BTCUSDT',
    use_kelly=True                    # 使用凱利公式
)

print(f"下單金額: ${result['order_amount']:.2f}")
print(f"風險金額: ${result['risk_amount']:.2f}")
print(f"Kelly %: {result['kelly_pct']:.2%}")
print(f"ATR Weight: {result['atr_weight']:.2f}x")
print(f"Confidence Factor: {result['confidence_factor']:.2f}x")
print(f"止盈距離: {result['tp_pct']:.2%}")
print(f"止損距離: {result['sl_pct']:.2%}")

# 計算詳情:
calculation = result['calculation']
print(f"\n計算過程:")
print(f"  Base Risk %: {calculation['base_risk_pct']:.2%}")
print(f"  Kelly %: {calculation['kelly_pct']:.2%}")
print(f"  ATR Weight: {calculation['atr_weight']:.2f}x")
print(f"  Confidence: {calculation['confidence_factor']:.2f}x")
print(f"  Final Risk %: {calculation['final_risk_pct']:.2%}")

# 輸出範例:
# 下單金額: $1,512.50
# 風險金額: $30.25
# Kelly %: 6.4%
# ATR Weight: 1.33x (低波動 → 擴大部位)
# Confidence Factor: 1.5x (80% 信心 → 擴大部位)
# 止盈距離: 2.85% (1.85% SL + 5% Prediction)
# 止損距離: 1.85%
```

---

## 5️⃣ 停損停利改為百分比

### 舊架構 (絕對金額)
```python
stop_loss = 420  # $420 絕對虧損
take_profit = 2100  # $2,100 絕對收益

# 問題: 不同交易對的價格差異大，邏輯複雜
```

### 新架構 (百分比)
```python
# 基於進場價格的百分比
entry_price = 42000

sl_pct = 0.02  # 2% 停損
tp_pct = 0.07  # 7% 止盈

# 實際價格
stop_loss_price = entry_price * (1 - sl_pct)  # $42,000 × 0.98 = $41,160
take_profit_price = entry_price * (1 + tp_pct)  # $42,000 × 1.07 = $44,940

# 優點: 邏輯統一，易於管理
```

---

## 6️⃣ 交易結果記錄與損益計算

### 虛擬交易範例

```python
from src.capital_tracker import get_capital_tracker

tracker = get_capital_tracker()

# 開倉
position = tracker.open_position(
    symbol='BTCUSDT',
    side='BUY',
    quantity=0.238095,
    entry_price=42000,
    order_amount=10000  # 下單金額
)

# 更新當前價格 (假設 BTC 漲到 44,100)
tracker.update_position_price('BTCUSDT', current_price=44100)

# 計算未實現 PnL
unrealized_pnl = tracker.get_unrealized_pnl()  # +$498.10 (近似 +5%)

# 平倉
realized_pnl = 498.10  # 實現收益

closed_pos = tracker.close_position(
    symbol='BTCUSDT',
    exit_price=44100,
    realized_pnl=realized_pnl
)

# 獲取帳戶狀態
status = tracker.get_account_status()
print(f"帳戶權益: ${status['total_equity']:.2f}")
print(f"可用餘額: ${status['available_balance']:.2f}")
print(f"已實現 PnL: ${status['realized_pnl']:.2f}")
print(f"勝率: {status['win_rate']:.1%}")
print(f"總回報率: {status['total_return_pct']:.2f}%")

# 輸出:
# 帳戶權益: $10,498.10
# 可用餘額: $10,498.10
# 已實現 PnL: $498.10
# 勝率: 100% (1/1)
# 總回報率: 4.98%
```

---

## 7️⃣ 完整交易流程示例

```python
from src.percentage_return_model import PercentageReturnModel
from src.position_sizing import PositionSizingFactory
from src.capital_tracker import init_capital_tracker, get_capital_tracker, get_total_equity

# ===== 初始化 =====
tracker = init_capital_tracker(initial_balance=10000)

# ===== 第一筆交易 =====
signal = {
    'symbol': 'BTCUSDT',
    'direction': 'UP',
    'confidence': 0.80
}

# 1️⃣ ML 模型預測收益率
ml_model = PercentageReturnModel()
prediction = ml_model.predict_signal(signal)
predicted_return_pct = prediction['predicted_return_pct']  # 例: 0.05 (+5%)

# 2️⃣ 計算部位規模 (使用版本 B)
total_capital = get_total_equity()  # $10,000
current_price = 42000

sizing_result = PositionSizingFactory.calculate(
    version='B',
    total_capital=total_capital,
    predicted_return_pct=predicted_return_pct,
    confidence=signal['confidence'],
    win_rate=0.70,  # 假設歷史勝率 70%
    atr_pct=0.015,
    current_price=current_price,
    symbol=signal['symbol']
)

order_amount = sizing_result['order_amount']
tp_pct = sizing_result['tp_pct']
sl_pct = sizing_result['sl_pct']

print(f"📈 交易 #1: {signal['symbol']} {signal['direction']}")
print(f"   下單金額: ${order_amount:.2f}")
print(f"   止損: {sl_pct:.2%}, 止盈: {tp_pct:.2%}")
print(f"   預測收益: {predicted_return_pct:.2%}")

# 3️⃣ 執行下單 (虛擬)
quantity = sizing_result['quantity']
tracker.open_position(
    symbol=signal['symbol'],
    side='BUY',
    quantity=quantity,
    entry_price=current_price,
    order_amount=order_amount
)

# 4️⃣ 模擬成交 (1 小時後，BTC 漲到 44,100)
import time
time.sleep(1)  # 模擬時間流逝

new_price = 44100  # +5% 漲幅
tracker.update_position_price(signal['symbol'], new_price)

# 計算 PnL
unrealized = tracker.get_unrealized_pnl()
print(f"\n💰 未實現 PnL: ${unrealized:.2f} ({unrealized/order_amount:.2%})")

# 5️⃣ 平倉
realized_pnl = unrealized  # 假設完全成交
tracker.close_position(
    symbol=signal['symbol'],
    exit_price=new_price,
    realized_pnl=realized_pnl
)

# 6️⃣ 查看帳戶狀態
status = tracker.get_account_status()
print(f"\n📊 帳戶狀態:")
print(f"   總權益: ${status['total_equity']:.2f}")
print(f"   已實現 PnL: ${status['realized_pnl']:.2f}")
print(f"   總回報率: {status['total_return_pct']:.2f}%")
print(f"   勝率: {status['win_rate']:.1%}")
```

---

## 8️⃣ 版本 A vs B 比較

| 特性 | 版本 A (基礎) | 版本 B (進階) |
|------|--------------|--------------|
| **複雜度** | 簡單 | 複雜 |
| **計算公式** | 固定風險 % | 凱利 + ATR + 信心度 |
| **適合場景** | 初學者、穩定交易 | 經驗豐富、動態調整 |
| **下單金額** | 固定（例: 2% 風險） | 動態（基於市場/信心） |
| **波動率敏感** | 否 | 是 (ATR 加權) |
| **信心度敏感** | 否 | 是 (Confidence 因子) |
| **風險** | 預測可控 | 風險更高（但潛力更大） |

### 選擇建議
- **版本 A**: 直到獲得 100+ 交易的統計數據為止使用
- **版本 B**: 有充分的歷史數據 + 想要最大化回報時使用

---

## 9️⃣ 數據損益對比

### 示例: $10,000 初始資金，連續 5 筆交易

#### 版本 A (固定 2% 風險)
```
Trade 1: 預測 +5% → 下單 $10,000 → 成交 +5% → 收益 +$500 (帳戶: $10,500)
Trade 2: 預測 +3% → 下單 $10,500 → 成交 -2% → 損失 -$210 (帳戶: $10,290)
Trade 3: 預測 +4% → 下單 $10,290 → 成交 +4% → 收益 +$412 (帳戶: $10,702)
Trade 4: 預測 +2% → 下單 $10,702 → 成交 +2% → 收益 +$214 (帳戶: $10,916)
Trade 5: 預測 +3% → 下單 $10,916 → 成交 +3% → 收益 +$327 (帳戶: $11,243)

最終: $11,243 (+12.43%)
勝率: 4/5 (80%)
平均回報: +2.48% per trade
```

#### 版本 B (凱利公式 + ATR)
```
Trade 1: 低波動 (ATR 1.2%) → 下單 $15,000 (擴大 50%) → +5% → +$750 (帳戶: $10,750)
Trade 2: 高波動 (ATR 3.5%) → 下單 $5,000 (縮小 50%) → -2% → -$100 (帳戶: $10,650)
Trade 3: 中波動 (ATR 2.0%) → 下單 $10,650 (正常) → +4% → +$426 (帳戶: $11,076)
Trade 4: 低波動 (ATR 1.0%) → 下單 $16,614 (擴大 55%) → +2% → +$332 (帳戶: $11,408)
Trade 5: 中波動 (ATR 1.8%) → 下單 $11,100 (略擴) → +3% → +$333 (帳戶: $11,741)

最終: $11,741 (+17.41%)
勝率: 4/5 (80%)
平均回報: +3.48% per trade
```

**版本 B 相較 A 多賺 $498 (+4.98%)**

---

## 🔟 實施步驟

### 1. 集成到 Brain Process
```python
# src/brain.py
from src.percentage_return_model import PercentageReturnModel
from src.position_sizing import PositionSizingFactory
from src.capital_tracker import get_total_equity

async def process_signal(signal, brain_config):
    # 預測收益率
    ml_model = PercentageReturnModel()
    prediction = ml_model.predict_signal(signal)
    
    # 計算下單規模
    total_capital = get_total_equity()
    sizing = PositionSizingFactory.calculate(
        version=brain_config.get('position_sizing_version', 'A'),
        total_capital=total_capital,
        predicted_return_pct=prediction['predicted_return_pct'],
        confidence=signal['confidence'],
        win_rate=brain_config.get('historical_winrate', 0.60),
        atr_pct=signal.get('atr', 0.02),
        current_price=signal.get('current_price', 0)
    )
    
    # 執行下單
    await execute_trade(signal, sizing)
```

### 2. 更新 Trade Module
- 使用計算出的下單金額
- 使用百分比停損停利
- 更新資本追蹤器

### 3. 更新虛擬交易
- 記錄百分比收益率
- 驗證預測準確性

---

## 📝 總結

新架構的三個核心優勢:

1. **模型純粹性**: ML 模型專注預測收益率，無需知道資本規模
2. **風險管理**: 部位規模層獨立負責資金管理（凱利公式或固定風險）
3. **資本意識**: 隨著帳戶增長，下單金額自動調整，沒有手動干預

這確保了:
- ✅ 無偏差的 ML 訓練（不受帳戶規模影響）
- ✅ 靈活的風險管理（可在 A/B 間切換）
- ✅ 可擴展的架構（易於添加新的部位規模計算方法）
