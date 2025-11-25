# A.E.G.I.S. v8.0 交易邏輯與機器學習特徵詳解

---

## 目錄

1. [系統架構概覽](#系統架構概覽)
2. [交易邏輯](#交易邏輯)
   - [信號生成流程](#信號生成流程)
   - [多時間框架分析](#多時間框架分析)
   - [技術指標計算](#技術指標計算)
   - [信心度評分系統](#信心度評分系統)
3. [機器學習特徵](#機器學習特徵)
   - [核心特徵集 (8個)](#核心特徵集-8個)
   - [完整特徵集 (44個)](#完整特徵集-44個)
   - [特徵提取方法](#特徵提取方法)
4. [虛擬交易系統](#虛擬交易系統)
   - [倉位管理](#倉位管理)
   - [止盈止損計算](#止盈止損計算)
5. [獎懲機制與訓練](#獎懲機制與訓練)
   - [獎懲分數計算](#獎懲分數計算)
   - [樣本權重生成](#樣本權重生成)
6. [數據流架構](#數據流架構)

---

## 系統架構概覽

A.E.G.I.S. v8.0 是一個**生產級高頻交易引擎**，採用加強型三進程架構：

```
┌─────────────────────────────────────────────────────────────────┐
│                     A.E.G.I.S. v8.0 架構                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│   │  Feed 進程   │───▶│ Ring Buffer  │───▶│  Brain 進程  │      │
│   │  (PID: 611)  │    │ (共享記憶體)  │    │  (PID: 612)  │      │
│   │              │    │   480KB      │    │              │      │
│   │  WebSocket   │    │  10000 slots │    │  SMC 分析    │      │
│   │  數據攝取    │    │              │    │  ML 預測     │      │
│   └──────────────┘    └──────────────┘    └──────────────┘      │
│          │                   │                   │               │
│          │                   │                   │               │
│          ▼                   ▼                   ▼               │
│   ┌──────────────────────────────────────────────────────┐      │
│   │              PostgreSQL 數據庫                        │      │
│   │  ┌─────────┐ ┌─────────┐ ┌─────────────────────┐     │      │
│   │  │ signals │ │ market_ │ │ virtual_trades/     │     │      │
│   │  │         │ │  data   │ │ virtual_positions   │     │      │
│   │  └─────────┘ └─────────┘ └─────────────────────┘     │      │
│   └──────────────────────────────────────────────────────┘      │
│                              │                                   │
│                              ▼                                   │
│                    ┌──────────────────┐                         │
│                    │  Orchestrator    │                         │
│                    │  (PID: 613)      │                         │
│                    │                  │                         │
│                    │  • ML 訓練觸發   │                         │
│                    │  • 虛擬 TP/SL    │                         │
│                    │  • 系統維護      │                         │
│                    └──────────────────┘                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 核心進程職責

| 進程 | 優先級 | 職責 |
|------|--------|------|
| **Orchestrator** | 999 | 初始化 DB + Ring Buffer，系統維護 |
| **Feed** | 100 | WebSocket 數據攝取，寫入 Ring Buffer |
| **Brain** | 50 | SMC/ML 分析，交易信號生成與執行 |

---

## 交易邏輯

### 信號生成流程

```
                    ┌─────────────────────┐
                    │   WebSocket Feed    │
                    │   (實時 K 線數據)    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Ring Buffer       │
                    │   (零鎖 IPC)        │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Timeframe Buffer   │
                    │  (K 線聚合)         │
                    │  1m → 5m → 15m → 1H │
                    └──────────┬──────────┘
                               │
                               ▼
              ┌────────────────┴────────────────┐
              │                                  │
              ▼                                  ▼
   ┌─────────────────────┐          ┌─────────────────────┐
   │  技術指標計算        │          │  多時間框架分析      │
   │  (Numba JIT 加速)    │          │  (趨勢一致性檢查)    │
   │                      │          │                      │
   │  • RSI (14)          │          │  1H: 40% 權重       │
   │  • MACD (12/26/9)    │          │  15m: 30% 權重      │
   │  • ATR (14)          │          │  5m: 20% 權重       │
   │  • BB Width (20)     │          │  1m: 10% 權重       │
   │  • FVG 檢測          │          │                      │
   │  • 流動性計算        │          │                      │
   └──────────┬──────────┘          └──────────┬──────────┘
              │                                  │
              └────────────────┬────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  信心度計算         │
                    │  (技術面評分)       │
                    │                     │
                    │  RSI Score × 0.40   │
                    │  MACD Score × 0.35  │
                    │  ATR Score × 0.25   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  ML 模型預測        │
                    │  (XGBoost)          │
                    │                     │
                    │  輸入: 8 個特徵     │
                    │  輸出: 勝率預測     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  信號過濾與執行     │
                    │                     │
                    │  • 信心度 > 閾值    │
                    │  • 勝率 > 閾值      │
                    │  • 風險回報比檢查   │
                    └─────────────────────┘
```

### 多時間框架分析

系統採用**自上而下**的多時間框架分析方法，確保交易方向與主趨勢一致：

```python
# 時間框架權重配置
TIMEFRAME_WEIGHTS = {
    '1h':  0.40,  # 主趨勢 (40% 權重)
    '15m': 0.30,  # 確認   (30% 權重)
    '5m':  0.20,  # 機會   (20% 權重)
    '1m':  0.10   # 進場   (10% 權重)
}
```

#### 趨勢一致性驗證規則

| 條件 | 結果 |
|------|------|
| 1H ≠ 15m 趨勢 | ❌ 拒絕信號 |
| 15m ≠ 5m 趨勢 | ❌ 拒絕信號 |
| 1m ≠ 主趨勢 | ❌ 拒絕信號 |
| 全部對齊 | ✅ 生成信號 |

#### 綜合信心度計算

```python
composite_confidence = (
    h1_analysis['confidence'] * 0.40 +   # 1H 趨勢
    m15_analysis['confidence'] * 0.30 +  # 15m 確認
    m5_analysis['confidence'] * 0.20 +   # 5m 機會
    m1_analysis['confidence'] * 0.10     # 1m 進場
)

# 最低信心度閾值: 0.60
if composite_confidence < 0.60:
    return None  # 拒絕信號
```

### 技術指標計算

系統使用 **Numba JIT** 加速的技術指標，性能提升 **50-200 倍**：

#### RSI (相對強弱指數)

```python
@jit(cache=True, nogil=True)
def rsi_jit(prices, period=14):
    """
    計算 RSI (0-100)
    
    - RSI < 30: 超賣
    - RSI > 70: 超買
    - RSI = 50: 中立
    """
    gains = sum(diff for diff in deltas if diff > 0)
    losses = sum(-diff for diff in deltas if diff < 0)
    
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
```

#### MACD (移動平均收斂/發散)

```python
@jit(cache=True, nogil=True)
def macd_jit(prices, fast=12, slow=26, signal=9):
    """
    計算 MACD 三線
    
    Returns:
        - macd_line: 快速 EMA - 慢速 EMA
        - signal_line: MACD 的 9 期 EMA
        - histogram: macd_line - signal_line
    """
    fast_ema = ema(prices, 12)
    slow_ema = ema(prices, 26)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_series, 9)
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram
```

#### ATR (平均真實範圍)

```python
@jit(cache=True, nogil=True)
def atr_jit(highs, lows, closes, period=14):
    """
    計算 ATR 用於波動性評估
    
    True Range = max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close)
    )
    
    ATR = SMA(True Range, 14)
    """
```

#### 布林帶寬度

```python
@jit(cache=True, nogil=True)
def bollinger_width_jit(prices, period=20, std_dev=2.0):
    """
    計算布林帶寬度 (波動性指標)
    
    Upper Band = SMA + 2 × 標準差
    Lower Band = SMA - 2 × 標準差
    Width = Upper - Lower
    """
```

#### FVG 檢測 (公允價值缺口)

```python
def detect_fvg(closes, highs, lows):
    """
    檢測 Fair Value Gap (ICT 概念)
    
    多頭 FVG: 前一根 K 線高點 < 後一根 K 線低點
    空頭 FVG: 前一根 K 線低點 > 後一根 K 線高點
    
    Returns:
        0.0-1.0 (FVG 強度)
    """
```

#### 流動性計算

```python
def calculate_liquidity(bid_price, ask_price, volume, volume_ma):
    """
    計算流動性分數
    
    基於:
    - 買賣價差
    - 成交量相對於均量
    
    Returns:
        0.0-1.0 (流動性分數)
    """
```

### 信心度評分系統

系統採用**五維評分機制**計算綜合信心度：

| 維度 | 權重 | 說明 |
|------|------|------|
| 趨勢對齊分數 | 40% | 多時間框架趨勢一致性 |
| 市場結構分數 | 20% | 高點/低點結構分析 |
| 價格位置分數 | 20% | 相對於支撐/阻力位置 |
| 動量分數 | 10% | RSI, MACD 等動量指標 |
| 波動率分數 | 10% | ATR, BB Width 波動性 |

#### 技術面信心度公式

```python
# RSI 評分 (50 = 最佳中立值)
rsi_score = (50 - abs(rsi_value - 50)) / 50  
# RSI=50 → 1.0, RSI=30/70 → 0.6, RSI=20/80 → 0.4

# MACD 評分 (正值加分)
macd_score = 0.5 + (0.5 * min(max(macd_line / 100, -1), 1))

# ATR 評分 (正常波動加分)
atr_score = 0.5 + (0.5 * min(atr_value / 0.05, 1.0))

# 綜合技術信心度
technical_confidence = (
    rsi_score * 0.40 +
    macd_score * 0.35 +
    atr_score * 0.25
)
```

---

## 機器學習特徵

### 核心特徵集 (8個)

系統使用 **8 個核心特徵** 進行 ML 模型訓練：

```python
FEATURE_NAMES = [
    'confidence',        # 信心度分數 (0.0-1.0)
    'fvg_detected',      # FVG 檢測值 (0.0-1.0)
    'liquidity_score',   # 流動性分數 (0.0-1.0)
    'position_size_pct', # 倉位百分比 (0.0-1.0)
    'rsi',               # RSI 指標 (0-100)
    'atr',               # ATR 絕對值
    'macd',              # MACD 線值
    'bb_width'           # 布林帶寬度
]
```

#### 特徵向量提取

```python
def extract_ml_features(signal_data: Dict) -> List[float]:
    """
    統一特徵提取方法
    
    輸出: [confidence, fvg, liquidity, position_size_pct, 
           rsi, atr, macd, bb_width]
    """
    return [
        float(signal_data.get("confidence", 0.5)),
        float(features.get("fvg", 0.5)),
        float(features.get("liquidity", 0.5)),
        position_size / 10000.0,  # 標準化
        float(features.get("rsi", 50.0)),
        float(features.get("atr", 0.0)),
        float(features.get("macd", 0.0)),
        float(features.get("bb_width", 0.0))
    ]
```

### 完整特徵集 (44個)

系統在進階模式下支持 **44 個完整特徵**：

#### 1. 基本特徵 (8個)

| 特徵名 | 說明 | 數據範圍 |
|--------|------|----------|
| `confidence` | 信心度分數 | 0-1 |
| `leverage` | 槓桿倍數 | 1-125 |
| `position_value` | 倉位價值 | >0 |
| `holding_duration` | 持倉時間(小時) | >0 |
| `risk_reward_ratio` | 風險回報比 | >0 |
| `order_blocks_count` | Order Block 數量 | 0+ |
| `liquidity_zones_count` | 流動性區域數量 | 0+ |
| `entry_price` | 入場價格 | >0 |

#### 2. 技術指標 (10個)

| 特徵名 | 說明 | 數據範圍 |
|--------|------|----------|
| `rsi` | 相對強弱指標 | 0-100 |
| `macd` | MACD 值 | 任意實數 |
| `macd_signal` | MACD 信號線 | 任意實數 |
| `macd_histogram` | MACD 柱狀圖 | 任意實數 |
| `atr` | 平均真實範圍 | >0 |
| `bb_width` | 布林帶寬度 | >0 |
| `volume_sma_ratio` | 成交量/SMA 比率 | >0 |
| `ema50` | 50 周期 EMA | >0 |
| `ema200` | 200 周期 EMA | >0 |
| `volatility_24h` | 24 小時波動率 | 0-1 |

#### 3. 趨勢特徵 (6個)

| 特徵名 | 說明 | 編碼 |
|--------|------|------|
| `trend_1h` | 1 小時趨勢 | 1=多頭, -1=空頭, 0=中性 |
| `trend_15m` | 15 分鐘趨勢 | 1=多頭, -1=空頭, 0=中性 |
| `trend_5m` | 5 分鐘趨勢 | 1=多頭, -1=空頭, 0=中性 |
| `market_structure` | 市場結構 | 1=看多, -1=看空, 0=中性 |
| `direction` | 交易方向 | 1=LONG, -1=SHORT |
| `trend_alignment` | 趨勢對齊度 | 0-1 (完全對齊=1.0) |

**趨勢對齊度計算:**

```python
# 完全對齊 (H1+M15+M5 都是多頭或都是空頭) = 1.0
# 部分對齊 (2 個同向，1 個不同) = 0.67
# 完全不對齊 (混合) = 0.33 或 0
alignment = abs(trend_1h + trend_15m + trend_5m) / 3.0
```

#### 4. SMC/ICT 特徵 (14個)

| 特徵名 | 說明 | 數據範圍 |
|--------|------|----------|
| `ema50_slope` | EMA50 斜率 | 任意實數 |
| `ema200_slope` | EMA200 斜率 | 任意實數 |
| `higher_highs` | 更高高點數量 | 0+ |
| `lower_lows` | 更低低點數量 | 0+ |
| `support_strength` | 支撐強度 | 0-1 |
| `resistance_strength` | 阻力強度 | 0-1 |
| `fvg_count` | FVG 數量 | 0+ |
| `swing_high_distance` | 到擺動高點距離 | >0 |
| `swing_low_distance` | 到擺動低點距離 | >0 |
| `volume_profile` | 成交量分佈 | 0-1 |
| `price_momentum` | 價格動量 | 任意實數 |
| `order_flow` | 訂單流 | 任意實數 |
| `liquidity_grab` | 流動性抓取 | 0/1 (布爾值) |
| `institutional_candle` | 機構 K 線 | 0/1 (布爾值) |

#### 5. 競價上下文特徵 (3個)

| 特徵名 | 說明 | 數據範圍 |
|--------|------|----------|
| `competition_rank` | 競爭排名 | 1+ |
| `score_gap_to_best` | 與最佳差距 | 0-1 |
| `competing_signals_count` | 競爭信號數量 | 0+ |

#### 6. WebSocket 特徵 (3個)

| 特徵名 | 說明 | 數據範圍 |
|--------|------|----------|
| `latency_zscore` | 延遲 Z-score | 任意實數 |
| `shard_load` | 分片負載 | 0-1 |
| `timestamp_consistency` | 時間戳一致性 | 0-1 |

### 特徵提取方法

#### 從虛擬交易提取 ML 格式

```python
def convert_to_ml_format(trade: Dict) -> Dict:
    """
    將虛擬交易轉換為 ML 訓練格式
    """
    # 提取 8 個核心特徵
    signal_data = {
        'confidence': trade.get('confidence', 0.65),
        'features': {
            'fvg': trade.get('fvg', 0.5),
            'liquidity': trade.get('liquidity', 0.5),
            'rsi': trade.get('rsi', 50.0),
            'atr': trade.get('atr', 0.0),
            'macd': trade.get('macd', 0.0),
            'bb_width': trade.get('bb_width', 0.0),
            'position_size_pct': trade.get('position_size_pct', 0.01)
        }
    }
    
    # 統一特徵提取
    feature_vector = extract_ml_features(signal_data)
    
    # 獎懲機制
    reward_score = trade.get('reward_score', 0)
    sample_weight = get_sample_weight(reward_score)
    label = get_label_from_score(reward_score)
    
    return {
        'features': feature_vector,  # [8 個浮點數]
        'label': label,              # 0 或 1
        'weight': sample_weight,     # 樣本權重
        'metadata': {
            'symbol': trade.get('symbol'),
            'pnl': trade.get('pnl'),
            'roi_pct': trade.get('roi_pct'),
            'source': 'virtual'
        }
    }
```

---

## 虛擬交易系統

### 倉位管理

虛擬交易系統使用 **PostgreSQL** 進行跨進程倉位追蹤：

```python
# 虛擬帳戶初始狀態
_virtual_account = {
    'balance': 10000.0,     # 起始資本
    'positions': {},        # 活躍倉位
    'trades': [],           # 已完成交易
    'total_pnl': 0.0,       # 累計盈虧
    'win_rate': 0.0,        # 勝率
    'max_drawdown': 0.0     # 最大回撤
}
```

#### 倉位數據結構

```sql
CREATE TABLE virtual_positions (
    id SERIAL PRIMARY KEY,
    position_id VARCHAR(255) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,           -- BUY/SELL
    quantity FLOAT NOT NULL,
    entry_price FLOAT NOT NULL,
    entry_confidence FLOAT DEFAULT 0,
    entry_time TIMESTAMP NOT NULL,
    tp_level FLOAT NOT NULL,              -- 止盈價位
    sl_level FLOAT NOT NULL,              -- 止損價位
    status VARCHAR(20) DEFAULT 'OPEN',
    
    -- ML 特徵欄位
    confidence FLOAT DEFAULT 0,
    fvg FLOAT DEFAULT 0,
    liquidity FLOAT DEFAULT 0,
    rsi FLOAT DEFAULT 0,
    atr FLOAT DEFAULT 0,
    macd FLOAT DEFAULT 0,
    bb_width FLOAT DEFAULT 0,
    position_size_pct FLOAT DEFAULT 0
);
```

### 止盈止損計算

#### 基於 ATR 的動態計算

```python
# 基礎止損 = 2.0 × ATR
base_stop_loss = atr_value * 2.0

# 止盈目標 = 1.5 × 止損距離 (1:1.5 風險回報比)
take_profit = base_stop_loss * 1.5
```

#### 默認百分比設置

```python
def calculate_tp_sl(side: str, entry_price: float):
    """
    計算 TP/SL 價位
    
    多頭 (BUY):
        TP = 入場價 × 1.05  (5% 盈利)
        SL = 入場價 × 0.98  (2% 止損)
    
    空頭 (SELL):
        TP = 入場價 × 0.95  (5% 盈利)
        SL = 入場價 × 1.02  (2% 止損)
    """
    if side == 'BUY':
        tp_level = entry_price * 1.05
        sl_level = entry_price * 0.98
    else:  # SELL
        tp_level = entry_price * 0.95
        sl_level = entry_price * 1.02
    
    return tp_level, sl_level
```

#### 倉位監控流程

```
┌─────────────────────────────────────┐
│     Virtual Monitor (每 5 秒)       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  check_virtual_tp_sl()              │
│                                      │
│  for position in open_positions:     │
│      current_price = get_price()    │
│                                      │
│      if side == 'BUY':              │
│          if current_price >= TP:    │
│              close_position('TP')   │
│          elif current_price <= SL:  │
│              close_position('SL')   │
│                                      │
│      if side == 'SELL':             │
│          if current_price <= TP:    │
│              close_position('TP')   │
│          elif current_price >= SL:  │
│              close_position('SL')   │
└─────────────────────────────────────┘
```

---

## 獎懲機制與訓練

### 獎懲分數計算

系統採用**非對稱評分機制**，虧損扣分更重：

#### 盈利等級

| ROI% | 分數 | 說明 |
|------|------|------|
| ≤30% | +1 | 小幅盈利 |
| ≤50% | +3 | 中等盈利 |
| ≤80% | +5 | 大幅盈利 |
| >80% | +8 | 超額盈利 |

#### 虧損等級

| ROI% | 分數 | 說明 |
|------|------|------|
| ≥-30% | -1 | 小幅虧損 |
| ≥-50% | -3 | 中等虧損 |
| ≥-80% | -7 | 大幅虧損 |
| <-80% | -10 | 嚴重虧損 |

#### 計算函數

```python
def calculate_reward_score(roi_pct: float) -> float:
    """
    根據 ROI% 計算獎懲分數
    
    Args:
        roi_pct: ROI 百分比 (0.15 = 15%, -0.25 = -25%)
    
    Returns:
        獎懲分數 (-10.0 到 +8.0)
    
    Examples:
        ROI: +15% → Score: +1.0
        ROI: +40% → Score: +3.0
        ROI: +65% → Score: +5.0
        ROI: +95% → Score: +8.0
        ROI: -15% → Score: -1.0
        ROI: -40% → Score: -3.0
        ROI: -65% → Score: -7.0
        ROI: -95% → Score: -10.0
    """
```

### 樣本權重生成

```python
def get_sample_weight(reward_score: float) -> float:
    """
    將獎懲分數轉換為樣本權重
    
    使用絕對值：高分數 = 高權重
    
    -10 分 → 10 倍權重 (嚴重虧損，模型應高度注意)
    +8 分 → 8 倍權重 (大幅盈利，模型應學習)
    
    Returns:
        樣本權重 (0.1 - 10.0)
    """
    weight = abs(reward_score)
    return max(0.1, min(weight, 10.0))
```

### 二元標籤生成

```python
def get_label_from_score(reward_score: float) -> int:
    """
    將獎懲分數轉換為二元標籤
    
    Returns:
        1 (盈利) 或 0 (虧損)
    """
    return 1 if reward_score > 0 else 0
```

### ML 訓練觸發條件

```python
# 自動訓練觸發
MINIMUM_TRADES_FOR_TRAINING = 50  # 最少 50 筆完整交易

async def check_training_trigger():
    """
    檢查是否觸發 ML 訓練
    """
    complete_trades = await experience_buffer.get_training_data()
    
    if len(complete_trades) >= MINIMUM_TRADES_FOR_TRAINING:
        await ml_model.train(complete_trades)
        logger.info(f"🎯 ML 模型訓練完成: {len(complete_trades)} 筆交易")
```

---

## 數據流架構

### 完整數據流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                          數據攝取層                                  │
│  ┌─────────────┐                                                    │
│  │  Binance    │                                                    │
│  │  WebSocket  │ ──────▶ 實時 K 線數據 (20 個交易對)               │
│  │  Streams    │         1m, 5m, 15m, 1h 時間框架                   │
│  └─────────────┘                                                    │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          處理層                                      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │   Ring Buffer   │───▶│  Timeframe      │───▶│   Indicators    │ │
│  │   (共享記憶體)   │    │  Aggregator     │    │   (Numba JIT)   │ │
│  │                 │    │                 │    │                 │ │
│  │   480KB         │    │  K 線聚合       │    │  RSI/MACD/ATR   │ │
│  │   10000 slots   │    │  多 TF 同步     │    │  BB/FVG/流動性  │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘ │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          分析層                                      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │   Multi-TF      │───▶│   Confidence    │───▶│   ML Model      │ │
│  │   Analyzer      │    │   Scoring       │    │   (XGBoost)     │ │
│  │                 │    │                 │    │                 │ │
│  │   趨勢一致性    │    │   五維評分      │    │   勝率預測      │ │
│  │   驗證          │    │   技術評分      │    │   8 特徵輸入    │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘ │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          執行層                                      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │   Signal        │───▶│   Position      │───▶│   Order         │ │
│  │   Filter        │    │   Sizing        │    │   Execution     │ │
│  │                 │    │                 │    │                 │ │
│  │   信心度過濾    │    │   Kelly/固定    │    │   虛擬/實盤     │ │
│  │   風險回報比    │    │   倉位計算      │    │   TP/SL 設置    │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘ │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          持久化層                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                     PostgreSQL                               │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────────────────┐ │    │
│  │  │ signals  │ │ market_  │ │ virtual_trades/positions     │ │    │
│  │  │          │ │ data     │ │                              │ │    │
│  │  │ 60,404   │ │ 6,361    │ │ 26,407 筆完整交易            │ │    │
│  │  │ 信號     │ │ K 線     │ │ 含 ML 特徵 + 獎懲分數        │ │    │
│  │  └──────────┘ └──────────┘ └──────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                       Redis                                  │    │
│  │  • 最新 OHLCV 緩存 (1 小時 TTL)                             │    │
│  │  • 帳戶狀態同步                                              │    │
│  │  • 跨進程通信                                                │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 數據表關係

```sql
-- 信號 → 虛擬倉位 → 虛擬交易
signals (id) 
    │
    └──▶ virtual_positions (signal_id FK)
            │
            └──▶ virtual_trades (position_id FK)
                    │
                    └──▶ experience_buffer (ML 訓練數據)
```

### 性能指標

| 指標 | 數值 | 說明 |
|------|------|------|
| K 線處理速度 | 280+ /10s | Ring Buffer 吞吐量 |
| Numba JIT 加速 | 100-200x | 技術指標計算 |
| 信號生成 | 60,404 條 | 20 個交易對均勻分佈 |
| 虛擬交易 | 26,407 筆 | 完整生命週期記錄 |
| 勝率 | 55.7% | 虛擬交易系統 |
| 內存使用 | 41.65 MB | 0.06% 系統內存 |
| Ring Buffer | w=r | 完全同步，零延遲 |

---

## 附錄：代碼示例

### 完整信號生成示例

```python
# 1. 接收 K 線數據
candle = (timestamp, open, high, low, close, volume)

# 2. 計算技術指標 (Numba 加速)
rsi_value = Indicators.rsi(closes, period=14)
macd_line, signal_line, histogram = Indicators.macd(closes)
atr_value = Indicators.atr(highs, lows, closes)
bb_width = Indicators.bollinger_bands(closes)
fvg_value = Indicators.detect_fvg(closes, highs, lows)
liquidity = Indicators.calculate_liquidity(bid, ask, vol, vol_ma)

# 3. 計算技術信心度
rsi_score = (50 - abs(rsi_value - 50)) / 50
macd_score = 0.5 + (0.5 * min(max(macd_line / 100, -1), 1))
atr_score = 0.5 + (0.5 * min(atr_value / 0.05, 1.0))
technical_confidence = (rsi_score * 0.4) + (macd_score * 0.35) + (atr_score * 0.25)

# 4. 組裝信號
signal_data = {
    'symbol': symbol,
    'direction': 'LONG' if closes[-1] > closes[-2] else 'SHORT',
    'confidence': technical_confidence,
    'entry_price': candle[4],
    'fvg': fvg_value,
    'liquidity': liquidity,
    'rsi': rsi_value,
    'atr': atr_value,
    'macd': macd_line,
    'bb_width': bb_width
}

# 5. ML 預測 (可選)
ml_features = extract_ml_features(signal_data)
win_probability = ml_model.predict(ml_features)

# 6. 執行交易
if technical_confidence > 0.60 and win_probability > 0.55:
    await open_virtual_position(signal_data)
```

---

*文檔版本: v8.0 | 最後更新: Nov 25, 2025*
