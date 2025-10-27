# 高頻交易系統 v3.0 - 完整系統文檔

## 🎯 系統概述

版本：**v3.0.0**  
發布日期：2025-10-25  
核心升級：**期望值驅動 + 五維評分系統 + 嚴格 Order Block**

### 核心特性

1. **期望值驅動的動態槓桿系統**
   - 基於最近 30 筆交易滾動計算期望值和盈虧比
   - 自動調整槓桿倍數（3x-20x）
   - 智能熔斷機制（連續虧損保護）

2. **五維信心度評分框架**
   - 趨勢對齊（40%）：多時間框架 EMA 驗證
   - 市場結構（20%）：分形高低點分析
   - 價格位置（20%）：基於 ATR 的距離評分
   - 動量指標（10%）：RSI + MACD 組合
   - 波動率適宜度（10%）：布林帶寬分位數

3. **嚴格的 Order Block 檢測**
   - 實體 ≥ 70% 全長
   - 3 根 K 線方向確認
   - 返回完整 OB 區間

4. **XGBoost ML 數據歸檔**
   - 所有信號特徵完整記錄
   - 實際 + 虛擬倉位生命周期追蹤
   - 實時訓練數據集生成

---

## 📊 系統架構

```
┌──────────────────────────────────────────────────────┐
│                    TradingBot (main.py)               │
│                  系統協調器 + 主循環                    │
└──────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌──────▼──────┐  ┌────────▼────────┐
│ DataService    │  │ICTStrategy  │  │ RiskManager     │
│ 數據管理       │  │ 信號生成    │  │ 風險控制        │
└────────────────┘  └─────────────┘  └─────────────────┘
        │                   │                   │
        │         ┌─────────▼──────────┐        │
        │         │ ExpectancyCalc     │        │
        │         │ 期望值計算         │        │
        │         └────────────────────┘        │
        │                                       │
        └───────────────────┬───────────────────┘
                            │
                   ┌────────▼─────────┐
                   │  DataArchiver    │
                   │  數據歸檔        │
                   └──────────────────┘
```

---

## 🔧 核心模組詳解

### 1. ExpectancyCalculator (期望值計算器)
**文件**: `src/managers/expectancy_calculator.py`

#### 核心公式
```python
期望值 (Expectancy %) = (Win Rate × Avg Win) - ((1 - Win Rate) × Avg Loss)
盈虧比 (Profit Factor) = Total Wins / Total Losses
```

#### 槓桿映射邏輯
| 期望值 (%) | 盈虧比 | 槓桿範圍 |
|-----------|--------|---------|
| > 1.5     | > 1.5  | 15-20x  |
| > 0.8     | > 1.0  | 10-15x  |
| > 0.3     | > 0.8  | 5-10x   |
| ≤ 0.3     | < 0.8  | 3-5x    |
| < 0       | -      | 0x (禁止開倉) |

#### 熔斷機制
- **連續 3 筆虧損** → 槓桿降至 3x + 24 小時冷卻期
- **連續 5 筆虧損** → 強制停止交易，需要策略回測
- **日虧損 ≥ 3%** → 禁止開新倉位

#### 使用範例
```python
from src.managers.expectancy_calculator import ExpectancyCalculator

calc = ExpectancyCalculator(window_size=30)

# 計算期望值指標
metrics = calc.calculate_expectancy(all_trades)
# 返回: {
#     'expectancy': 1.25,  # 1.25%
#     'profit_factor': 1.8,
#     'win_rate': 0.65,
#     'avg_win': 2.5,
#     'avg_loss': 1.2,
#     'consecutive_losses': 0
# }

# 檢查是否可以交易
can_trade, reason = calc.should_trade(
    expectancy=metrics['expectancy'],
    profit_factor=metrics['profit_factor'],
    consecutive_losses=metrics['consecutive_losses'],
    daily_loss_pct=calc.get_daily_loss(all_trades)
)

# 確定槓桿範圍
min_lev, max_lev = calc.determine_leverage(
    expectancy=metrics['expectancy'],
    profit_factor=metrics['profit_factor'],
    consecutive_losses=metrics['consecutive_losses']
)
```

---

### 2. ICTStrategy (五維評分系統)
**文件**: `src/strategies/ict_strategy.py`

#### 信心度計算
```python
總分 = Σ (子指標分數 × 權重)

confidence_score = (
    trend_alignment_score    * 0.40 +  # 趨勢對齊
    market_structure_score   * 0.20 +  # 市場結構
    price_position_score     * 0.20 +  # 價格位置
    momentum_score           * 0.10 +  # 動量指標
    volatility_score         * 0.10    # 波動率
)
```

#### 1) 趨勢對齊評分 (40%)
基於多時間框架 EMA：
```python
5m:  價格 > EMA(20)  → +33.3%
15m: 價格 > EMA(50)  → +33.3%
1h:  價格 > EMA(100) → +33.3%

看多時，3/3 對齊 → 100%
看多時，2/3 對齊 → 67%
看多時，1/3 對齊 → 33%
```

#### 2) 市場結構評分 (20%)
基於分形高低點：
```python
if (bullish_structure and h1_trend == 'BULLISH'):
    score = 100%
elif (bearish_structure and h1_trend == 'BEARISH'):
    score = 100%
else:
    score = 50%  # 中性或矛盾
```

#### 3) 價格位置評分 (20%)
基於距離 Order Block 的 ATR 距離：
```python
distance = |Current Price - OB Price| / ATR

距離 ≤ 0.5 ATR → 100%  # 非常接近 OB
距離 ≤ 1.0 ATR → 80%   # 接近 OB
距離 ≤ 1.5 ATR → 60%   # 中等距離
距離 ≤ 2.0 ATR → 40%   # 較遠
距離 > 2.0 ATR → 20%   # 很遠

如果價格已突破 OB 區域 → 30%
```

#### 4) 動量指標評分 (10%)
RSI + MACD 組合：
```python
看多時:
  RSI 支持 (30-70) + MACD 金叉 → 100%
  僅一項支持               → 60%
  背離或反向               → 0%

看空時:
  RSI 支持 + MACD 死叉     → 100%
  僅一項支持               → 60%
  背離或反向               → 0%
```

#### 5) 波動率適宜度評分 (10%)
基於布林帶寬的 7 天分位數：
```python
當前 BB 寬度在 25%-75% 分位數之間 → 100%
當前 BB 寬度 < 25% 分位數         → 60% (波動過低)
當前 BB 寬度 > 75% 分位數         → 40% (波動過高)
```

#### 使用範例
```python
from src.strategies.ict_strategy import ICTStrategy

strategy = ICTStrategy()

signal = strategy.analyze(
    symbol='BTCUSDT',
    h1_data=h1_klines,
    m15_data=m15_klines,
    m5_data=m5_klines
)

# 返回信號包含:
# {
#     'symbol': 'BTCUSDT',
#     'direction': 'LONG',
#     'confidence': 0.78,  # 78%
#     'scores': {
#         'trend_alignment': 0.67,
#         'market_structure': 1.0,
#         'price_position': 0.8,
#         'momentum': 0.6,
#         'volatility': 1.0
#     },
#     'entry_price': 45000.0,
#     'stop_loss': 44500.0,
#     'take_profit': 46000.0,
#     ...
# }
```

---

### 3. DataArchiver (ML 數據歸檔)
**文件**: `src/ml/data_archiver.py`

#### 數據流
```
交易信號 → archive_signal()
    ↓
開倉 → archive_position_open()
    ↓
平倉 → archive_position_close()
    ↓
週期結束 → flush_all() → CSV 文件
```

#### 輸出文件

**1. signals.csv**
記錄所有交易信號（包括被拒絕的）：
```
timestamp, symbol, direction, confidence, accepted, rejection_reason,
trend_alignment_score, market_structure_score, price_position_score,
momentum_score, volatility_score, h1_trend, m15_trend, m5_trend,
current_price, entry_price, stop_loss, take_profit,
rsi, macd, macd_signal, atr, bb_width_pct,
order_blocks_count, liquidity_zones_count
```

**2. positions.csv**
記錄所有倉位（實際 + 虛擬）：
```
event, timestamp, position_id, is_virtual, symbol, direction,
entry_price, exit_price, stop_loss, take_profit, quantity, leverage,
confidence, pnl, pnl_pct, close_reason, won,
trend_alignment_score, market_structure_score, price_position_score,
momentum_score, volatility_score, rsi, macd, atr, bb_width_pct,
holding_duration_minutes
```

#### 使用範例
```python
from src.ml.data_archiver import DataArchiver

archiver = DataArchiver(data_dir="ml_data")

# 1. 記錄信號
archiver.archive_signal(
    signal_data=signal,
    accepted=True
)

# 2. 記錄開倉
archiver.archive_position_open(
    position_data=position,
    is_virtual=False
)

# 3. 記錄平倉
archiver.archive_position_close(
    position_data=position,
    close_data={'pnl': 150, 'pnl_pct': 3.5, 'close_price': 45500},
    is_virtual=False
)

# 4. 刷新到磁盤
archiver.flush_all()

# 5. 獲取訓練數據
training_data = archiver.get_training_data(min_samples=100)
```

---

### 4. 嚴格的 Order Block 檢測
**文件**: `src/utils/indicators.py` - `identify_order_blocks()`

#### 新標準

**看漲 Order Block**:
```python
1. 實體 = Close - Open
2. 全長 = High - Low
3. 實體% = 實體 / 全長

條件:
- 實體% ≥ 70%
- Close > Open (陽K)
- 後續 3 根 K 線中，至少 2 根確認看漲 (Close > Open)

OB 區間: [Low, Open]
```

**看跌 Order Block**:
```python
條件:
- 實體% ≥ 70%
- Close < Open (陰K)
- 後續 3 根 K 線中，至少 2 根確認看跌 (Close < Open)

OB 區間: [High, Open]
```

#### 返回格式
```python
{
    'type': 'bullish',      # 或 'bearish'
    'price': 45000.0,       # 中心價格
    'zone_low': 44950.0,    # OB 區間下限
    'zone_high': 45050.0,   # OB 區間上限
    'timestamp': datetime,
    'body_pct': 0.75,       # 實體占比 75%
    'confirmed': True       # 已確認
}
```

---

## 🚀 主流程集成

### 完整交易決策流程

```python
# main.py - _process_signal()

# 1. 計算期望值指標
expectancy_metrics = expectancy_calculator.calculate_expectancy(all_trades)

# 2. 期望值檢查
can_trade, reason = expectancy_calculator.should_trade(
    expectancy=expectancy_metrics['expectancy'],
    profit_factor=expectancy_metrics['profit_factor'],
    consecutive_losses=expectancy_metrics['consecutive_losses'],
    daily_loss_pct=expectancy_calculator.get_daily_loss(all_trades)
)

if not can_trade:
    # 記錄被拒絕的信號
    data_archiver.archive_signal(signal, accepted=False, rejection_reason=reason)
    return

# 3. 風險管理檢查
can_trade_risk, reason = risk_manager.should_trade(
    account_balance,
    active_positions_count
)

if not can_trade_risk:
    data_archiver.archive_signal(signal, accepted=False, rejection_reason=reason)
    return

# 4. 計算動態槓桿 (期望值驅動)
leverage = risk_manager.calculate_leverage(
    expectancy=expectancy_metrics['expectancy'],
    profit_factor=expectancy_metrics['profit_factor'],
    consecutive_losses=expectancy_metrics['consecutive_losses']
)

if leverage == 0:
    # 期望值為負，禁止開倉
    data_archiver.archive_signal(signal, accepted=False, rejection_reason="期望值為負")
    return

# 5. 記錄接受的信號
data_archiver.archive_signal(signal, accepted=True)

# 6. 執行交易
trade_result = await trading_service.execute_signal(
    signal, account_balance, leverage
)

# 7. 記錄開倉
if trade_result:
    data_archiver.archive_position_open(position_data, is_virtual=False)
    all_trades.append(trade_info)
```

---

## ⚙️ 配置說明

### Config.py 新增配置

```python
# 期望值計算配置
EXPECTANCY_WINDOW: int = 30          # 滾動窗口大小
MIN_EXPECTANCY_PCT: float = 0.3      # 最低期望值 (0.3%)
MIN_PROFIT_FACTOR: float = 0.8       # 最低盈虧比
CONSECUTIVE_LOSS_LIMIT: int = 5      # 連續虧損上限
DAILY_LOSS_LIMIT_PCT: float = 0.03   # 日虧損上限 (3%)
COOLDOWN_HOURS: int = 24             # 冷卻期 (小時)

# 信心度評分權重
CONFIDENCE_WEIGHTS = {
    "trend_alignment": 0.40,
    "market_structure": 0.20,
    "price_position": 0.20,
    "momentum": 0.10,
    "volatility": 0.10
}

# ML 數據目錄
ML_DATA_DIR: str = "ml_data"
```

---

## 📈 性能特性

### 系統規格適配
- **CPU**: 32 vCPU (Railway 伺服器)
- **記憶體**: 32GB
- **並行處理**: 32 核心並行分析
- **監控對象**: 前 200 個最高流動性交易對

### 時間框架調度
- **1h**: 每小時掃描 (趨勢確認)
- **15m**: 每 15 分鐘掃描 (趨勢確認)
- **5m**: 每分鐘掃描 (入場信號)

### 資本管理硬規則
- **單筆風險**: ≤ 總資金 1%
- **最大倉位數**: 3
- **槓桿範圍**: 3x - 20x (動態調整)

---

## 🧪 測試與驗證

### 單元測試 (待實施)
```bash
# 測試期望值計算
python -m pytest tests/test_expectancy_calculator.py

# 測試信心度評分
python -m pytest tests/test_ict_strategy.py

# 測試數據歸檔
python -m pytest tests/test_data_archiver.py
```

### 集成測試
```bash
# 啟動系統
python -m src.main

# 查看日誌
tail -f data/logs/trading_bot.log

# 查看歸檔數據
ls -lh ml_data/
cat ml_data/signals.csv
cat ml_data/positions.csv
```

---

## 📝 版本更新日誌

### v3.0.0 (2025-10-25)

**重大升級**:
1. ✅ 期望值驅動的動態槓桿系統
2. ✅ 五維信心度評分框架
3. ✅ 嚴格的 Order Block 檢測標準
4. ✅ XGBoost ML 數據歸檔系統
5. ✅ 連續虧損熔斷機制
6. ✅ 資本管理硬規則 (單筆風險 ≤ 1%)

**模組更新**:
- `src/managers/expectancy_calculator.py` - 新增
- `src/ml/data_archiver.py` - 新增
- `src/strategies/ict_strategy.py` - 完全重寫
- `src/utils/indicators.py` - Order Block 升級
- `src/managers/risk_manager.py` - 集成期望值驅動
- `src/main.py` - 集成所有新模組
- `src/config.py` - 新增配置項

**向後兼容性**:
- 保留舊的勝率驅動槓桿計算作為降級選項
- 保留原有的 Discord 通知系統
- 保留原有的虛擬倉位管理系統

---

## 🔮 未來規劃

### v3.1 (計劃中)
- [ ] XGBoost 模型自動訓練
- [ ] 實時信號質量反饋循環
- [ ] 多策略集成框架

### v3.2 (計劃中)
- [ ] 市場狀態自動識別
- [ ] 動態參數優化
- [ ] 回測系統集成

---

## 🆘 故障排除

### 常見問題

**Q: 系統顯示 "期望值為負，禁止開倉"**  
A: 這表示最近 30 筆交易的期望值為負數，系統自動暫停開新倉。需要等待策略回測或手動重置。

**Q: 數據歸檔文件為空**  
A: 確保：
1. `ml_data` 目錄存在
2. 已生成過交易信號
3. 調用過 `flush_all()` 方法

**Q: 信心度評分過低**  
A: 檢查：
1. 市場是否處於強趨勢
2. Order Block 是否明確
3. 多時間框架是否對齊
4. 考慮降低 `MIN_CONFIDENCE` (當前 55%)

---

## 📞 聯絡方式

項目: Winiswin2 高頻交易系統  
版本: v3.0.0  
團隊: Winiswin2 Team  
更新日期: 2025-10-25
