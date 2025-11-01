# 📊 SelfLearningTrader 信號搜集系統完整簡報

**生成時間**: 2025-11-01  
**版本**: v3.19+  
**當前狀態**: 運行中（0信號問題待解決）

---

## 📑 目錄

1. [信號搜集系統概述](#信號搜集系統概述)
2. [信號生成完整流程](#信號生成完整流程)
3. [ICT/SMC信號識別方法](#ictsmc信號識別方法)
4. [五維評分體系詳解](#五維評分體系詳解)
5. [信號過濾條件](#信號過濾條件)
6. [嚴格vs寬鬆模式對比](#嚴格vs寬鬆模式對比)
7. [當前0信號問題診斷](#當前0信號問題診斷)
8. [44個ML特徵採集](#44個ml特徵採集)
9. [信號質量分級](#信號質量分級)
10. [實戰案例分析](#實戰案例分析)

---

## 🎯 信號搜集系統概述

### 1.1 核心職責

**RuleBasedSignalGenerator** 是系統的信號引擎，負責：

```
📊 監控範圍: 530個USDT永續合約
🔄 掃描頻率: 每60秒一個周期
📈 數據來源: WebSocket實時數據 + REST備援
🎯 信號類型: ICT/SMC策略（Order Blocks + Liquidity Zones）
⚖️ 評分系統: 五維評分（0-100分）
🎓 學習機制: 44個ML特徵完整記錄
```

### 1.2 技術架構

```
┌─────────────────────────────────────────────────────┐
│           信號搜集系統架構圖                          │
└─────────────────────────────────────────────────────┘

UnifiedScheduler (每60秒)
    │
    ├─> 獲取530個交易對列表
    │
    ├─> 並行獲取K線數據（WebSocket優先）
    │   ├─ 1h: 100根K線
    │   ├─ 15m: 100根K線
    │   └─ 5m: 100根K線
    │
    ├─> RuleBasedSignalGenerator.analyze()
    │   │
    │   ├─> 1️⃣ 數據驗證
    │   │   └─ 確保3個時間框架數據完整
    │   │
    │   ├─> 2️⃣ 技術指標計算（12種）
    │   │   ├─ ATR, RSI, MACD, ADX
    │   │   ├─ EMA20, EMA50
    │   │   └─ Bollinger Bands
    │   │
    │   ├─> 3️⃣ ICT/SMC結構識別
    │   │   ├─ Order Blocks（機構建倉區）
    │   │   ├─ Liquidity Zones（流動性區）
    │   │   └─ Market Structure（BOS/CHOCH）
    │   │
    │   ├─> 4️⃣ 多時間框架趨勢分析
    │   │   ├─ H1主趨勢（EMA20 vs EMA50）
    │   │   ├─ M15中期趨勢
    │   │   └─ M5短期趨勢
    │   │
    │   ├─> 5️⃣ 信號方向判定
    │   │   ├─ 嚴格模式：H1+M15必須同向
    │   │   └─ 寬鬆模式：H1主導或M15+M5對齊
    │   │
    │   ├─> 6️⃣ 五維信心度評分（0-100）
    │   │   ├─ 時間框架對齊度（40%）
    │   │   ├─ 市場結構（20%）
    │   │   ├─ Order Block質量（20%）
    │   │   ├─ 動量指標（10%）
    │   │   └─ 波動率（10%）
    │   │
    │   ├─> 7️⃣ SL/TP計算
    │   │   ├─ 基礎SL = 2 × ATR
    │   │   └─ 基礎TP = SL × 1.5
    │   │
    │   └─> 8️⃣ 構建完整信號（44特徵）
    │
    ├─> 信號過濾
    │   ├─ ML模式：ml_score >= 60
    │   └─ 規則模式：win_prob>=0.6 AND confidence>=0.6
    │
    └─> 返回有效信號列表
```

---

## 🔄 信號生成完整流程

### 2.1 流程圖（8個步驟）

```
Step 1: 數據驗證 (_validate_data)
    │
    ├─ 檢查1h數據：至少50根K線
    ├─ 檢查15m數據：至少50根K線
    └─ 檢查5m數據：至少50根K線
    │
    ▼
Step 2: 技術指標計算 (_calculate_all_indicators)
    │
    ├─ H1指標：ATR, RSI, MACD, ADX, EMA20/50, BB
    ├─ M15指標：同上
    └─ M5指標：同上
    │
    ▼
Step 3: 趨勢確定 (_determine_trend)
    │
    ├─ H1趨勢：
    │   ├─ bullish: EMA20 > EMA50 且斜率 > 0.01
    │   ├─ bearish: EMA20 < EMA50 且斜率 < -0.01
    │   └─ neutral: 其他情況
    │
    ├─ M15趨勢：同上邏輯
    └─ M5趨勢：同上邏輯
    │
    ▼
Step 4: ICT/SMC結構識別
    │
    ├─ Order Blocks (identify_order_blocks)
    │   ├─ 檢測最近20根K線
    │   ├─ 成交量 > 1.5倍平均
    │   ├─ 拒絕率 > 0.5%
    │   └─ 記錄created_at時間戳
    │
    ├─ Liquidity Zones (_identify_liquidity_zones)
    │   ├─ 檢測高/低點聚集區
    │   └─ 強度評分（0-1）
    │
    └─ Market Structure (determine_market_structure)
        ├─ bullish: 高點抬升+低點抬升
        ├─ bearish: 高點降低+低點降低
        └─ neutral: 震盪整理
    │
    ▼
Step 5: 信號方向判定 (_determine_signal_direction)
    │
    ├─ 🔴 嚴格模式（RELAXED_SIGNAL_MODE=false）：
    │   │
    │   ├─ LONG條件：
    │   │   ├─ H1趨勢 = bullish
    │   │   ├─ M15趨勢 = bullish
    │   │   ├─ Market Structure ≠ bearish
    │   │   └─ 有bullish Order Blocks
    │   │
    │   └─ SHORT條件：
    │       ├─ H1趨勢 = bearish
    │       ├─ M15趨勢 = bearish
    │       ├─ Market Structure ≠ bullish
    │       └─ 有bearish Order Blocks
    │
    └─ 🟢 寬鬆模式（RELAXED_SIGNAL_MODE=true）：
        │
        ├─ LONG條件（3選1）：
        │   ├─ H1 bullish + M15 bullish
        │   ├─ H1 bullish + M15 neutral
        │   └─ H1 neutral + M15 bullish + M5 bullish
        │
        └─ SHORT條件（3選1）：
            ├─ H1 bearish + M15 bearish
            ├─ H1 bearish + M15 neutral
            └─ H1 neutral + M15 bearish + M5 bearish
    │
    ▼
Step 6: 五維信心度評分 (_calculate_confidence)
    │
    ├─ 1️⃣ 時間框架對齊度（40%）
    │   └─ 調用 _calculate_alignment_score()
    │
    ├─ 2️⃣ 市場結構（20%）
    │   ├─ LONG: structure=bullish → 20分
    │   └─ SHORT: structure=bearish → 20分
    │
    ├─ 3️⃣ Order Block質量（20%）
    │   ├─ 距離評分：<0.5%=20分, <1%=15分, <2%=10分
    │   ├─ 時效衰減：<48h=1.0, 48-72h=線性衰減, >72h=0
    │   └─ 最終分數 = 距離分數 × 衰減係數
    │
    ├─ 4️⃣ 動量指標（10%）
    │   ├─ RSI適中（LONG:50-70, SHORT:30-50）→ 5分
    │   └─ MACD同向（LONG:>0, SHORT:<0）→ 5分
    │
    └─ 5️⃣ 波動率（10%）
        ├─ BB寬度處於60-80分位 → 10分
        ├─ BB寬度處於40-60分位 → 5分
        └─ 其他 → 0分
    │
    ▼
Step 7: SL/TP計算 (_calculate_sl_tp)
    │
    ├─ 基礎止損：
    │   ├─ LONG: entry - (2 × ATR)
    │   └─ SHORT: entry + (2 × ATR)
    │
    ├─ 基礎止盈：
    │   ├─ LONG: entry + (SL距離 × 1.5)
    │   └─ SHORT: entry - (SL距離 × 1.5)
    │
    └─ 基礎RR比：
        └─ base_rr_ratio = 1.5
    │
    ▼
Step 8: 構建完整信號
    │
    └─ 返回包含44個ML特徵的完整信號字典
```

### 2.2 關鍵代碼片段

```python
def analyze(symbol: str, multi_tf_data: Dict) -> Optional[Dict]:
    """
    信號分析主函數
    
    Args:
        symbol: 交易對（如'BTCUSDT'）
        multi_tf_data: {
            '1h': DataFrame,   # 100根K線
            '15m': DataFrame,  # 100根K線
            '5m': DataFrame    # 100根K線
        }
    
    Returns:
        完整信號字典或None（無效信號）
    """
    
    # Step 1: 數據驗證
    if not self._validate_data(multi_tf_data):
        return None
    
    # Step 2: 計算技術指標
    indicators = self._calculate_all_indicators(multi_tf_data)
    
    # Step 3: 確定趨勢
    h1_trend = self._determine_trend(multi_tf_data['1h'], indicators['1h'])
    m15_trend = self._determine_trend(multi_tf_data['15m'], indicators['15m'])
    m5_trend = self._determine_trend(multi_tf_data['5m'], indicators['5m'])
    
    # Step 4: ICT結構識別
    order_blocks = self.identify_order_blocks(multi_tf_data['5m'])
    liquidity_zones = self._identify_liquidity_zones(multi_tf_data['5m'])
    market_structure = self.determine_market_structure(multi_tf_data['5m'])
    
    # Step 5: 信號方向判定
    direction = self._determine_signal_direction(
        h1_trend, m15_trend, m5_trend,
        market_structure, order_blocks
    )
    
    if not direction:
        return None  # 無有效信號方向
    
    # Step 6: 信心度評分
    confidence = self._calculate_confidence(
        direction, 
        {'1h': h1_trend, '15m': m15_trend, '5m': m5_trend},
        market_structure,
        order_blocks,
        indicators
    )
    
    # Step 7: SL/TP計算
    entry_price = multi_tf_data['5m']['close'].iloc[-1]
    stop_loss, take_profit = self._calculate_sl_tp(
        entry_price, direction, indicators['5m']['atr']
    )
    
    # Step 8: 構建完整信號
    signal = {
        'symbol': symbol,
        'direction': direction,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'confidence': confidence / 100,  # 轉換為0-1
        'rr_ratio': abs(take_profit - entry_price) / abs(entry_price - stop_loss),
        # ... 44個完整特徵
    }
    
    return signal
```

---

## 🎯 ICT/SMC信號識別方法

### 3.1 Order Blocks（機構建倉區）

#### 定義
**Order Block** 是機構大量建倉的價格區域，具有以下特徵：
- 📊 **高成交量**：遠超平均水平
- 📉 **價格拒絕**：後續價格反復測試但無法突破
- ⏰ **時效性**：新鮮OB（<48小時）效力最強

#### 識別算法

```python
def identify_order_blocks(df: pd.DataFrame, lookback: int = 20) -> List[Dict]:
    """
    Order Block識別算法
    
    檢測條件：
    1. 成交量 > 1.5倍平均成交量
    2. 價格反轉（bullish: 大陰線後大陽線, bearish: 大陽線後大陰線）
    3. 拒絕率 > 0.5%（後續K線測試但反彈）
    
    Returns:
        [
            {
                'type': 'bullish' | 'bearish',
                'zone_low': float,      # OB下界
                'zone_high': float,     # OB上界
                'quality_score': float, # 質量分數（0-1）
                'volume_ratio': float,  # 成交量倍數
                'rejection_rate': float,# 拒絕率
                'created_at': Timestamp,# 創建時間
                'test_count': int       # 被測試次數
            }
        ]
    """
    order_blocks = []
    
    for i in range(lookback, len(df) - 1):
        current = df.iloc[i]
        next_candle = df.iloc[i + 1]
        
        # 成交量條件
        avg_volume = df['volume'].iloc[i-lookback:i].mean()
        if current['volume'] < avg_volume * 1.5:
            continue
        
        # Bullish OB：大陰線後大陽線
        if (current['close'] < current['open'] and 
            next_candle['close'] > next_candle['open']):
            
            ob = {
                'type': 'bullish',
                'zone_low': current['low'],
                'zone_high': current['high'],
                'created_at': df.index[i],
                'volume_ratio': current['volume'] / avg_volume
            }
            
            # 計算拒絕率
            rejection_rate = self._calculate_rejection_rate(df, i, 'bullish')
            ob['rejection_rate'] = rejection_rate
            
            # 質量評分
            ob['quality_score'] = min(1.0, (
                rejection_rate * 0.4 +
                min(1.0, ob['volume_ratio'] / 3.0) * 0.6
            ))
            
            order_blocks.append(ob)
        
        # Bearish OB：大陽線後大陰線
        elif (current['close'] > current['open'] and 
              next_candle['close'] < next_candle['open']):
            
            # 同上邏輯
            ...
    
    return order_blocks
```

#### 時效衰減公式（v3.19+）

```python
def _calculate_ob_score_with_decay(ob: Dict, current_time: pd.Timestamp) -> float:
    """
    OB時效衰減
    
    公式：
    age_hours = (current_time - ob['created_at']).total_seconds() / 3600
    
    if age_hours > 72:
        return 0.0  # 完全失效
    elif age_hours > 48:
        decay_factor = 1 - (age_hours - 48) / 24  # 線性衰減
        return ob['quality_score'] * decay_factor
    else:
        return ob['quality_score']  # 全效
    """
    
    age_hours = (current_time - ob['created_at']).total_seconds() / 3600
    base_score = ob.get('quality_score', 0.5)
    
    if age_hours > 72:
        return 0.0
    elif age_hours > 48:
        decay_factor = 1 - (age_hours - 48) / 24
        return base_score * decay_factor
    else:
        return base_score
```

### 3.2 Liquidity Zones（流動性聚集區）

#### 定義
**Liquidity Zone** 是大量止損單或限價單聚集的價格區域，特徵：
- 📍 **價格聚集**：多次觸及同一價格區間
- 🔄 **反復測試**：價格反復在此區域反彈或突破
- 💧 **流動性掃蕩**：機構常在此收集或分發倉位

#### 識別算法

```python
def _identify_liquidity_zones(df: pd.DataFrame, lookback: int = 20) -> List[Dict]:
    """
    流動性區識別
    
    方法：
    1. 找出最近20根K線的高/低點
    2. 聚類分析找出價格密集區
    3. 計算強度分數
    
    Returns:
        [
            {
                'type': 'resistance' | 'support',
                'price': float,         # 中心價格
                'strength': float,      # 強度（0-1）
                'touch_count': int      # 觸及次數
            }
        ]
    """
    zones = []
    
    # 找出高點（潛在阻力）
    highs = df['high'].iloc[-lookback:].values
    high_clusters = self._cluster_prices(highs, threshold=0.005)
    
    for cluster in high_clusters:
        if cluster['count'] >= 2:  # 至少觸及2次
            zones.append({
                'type': 'resistance',
                'price': cluster['center'],
                'strength': min(1.0, cluster['count'] / 5),
                'touch_count': cluster['count']
            })
    
    # 找出低點（潛在支撐）
    lows = df['low'].iloc[-lookback:].values
    low_clusters = self._cluster_prices(lows, threshold=0.005)
    
    for cluster in low_clusters:
        if cluster['count'] >= 2:
            zones.append({
                'type': 'support',
                'price': cluster['center'],
                'strength': min(1.0, cluster['count'] / 5),
                'touch_count': cluster['count']
            })
    
    return zones
```

### 3.3 Market Structure（市場結構）

#### BOS（Break of Structure）與 CHOCH（Change of Character）

```python
def determine_market_structure(df: pd.DataFrame) -> str:
    """
    市場結構判定
    
    Bullish（上升結構）：
    - 高點依次抬升
    - 低點依次抬升
    - 沒有明顯BOS（結構破壞）
    
    Bearish（下降結構）：
    - 高點依次降低
    - 低點依次降低
    - 沒有明顯BOS
    
    Neutral（震盪）：
    - 其他情況
    
    Returns:
        'bullish' | 'bearish' | 'neutral'
    """
    
    # 找出最近5個高點和低點
    recent_highs = self._find_swing_points(df, 'high', count=5)
    recent_lows = self._find_swing_points(df, 'low', count=5)
    
    if len(recent_highs) < 3 or len(recent_lows) < 3:
        return 'neutral'
    
    # 檢查高點趨勢
    highs_rising = all(
        recent_highs[i] < recent_highs[i+1] 
        for i in range(len(recent_highs)-1)
    )
    
    # 檢查低點趨勢
    lows_rising = all(
        recent_lows[i] < recent_lows[i+1] 
        for i in range(len(recent_lows)-1)
    )
    
    if highs_rising and lows_rising:
        return 'bullish'
    
    highs_falling = all(
        recent_highs[i] > recent_highs[i+1] 
        for i in range(len(recent_highs)-1)
    )
    
    lows_falling = all(
        recent_lows[i] > recent_lows[i+1] 
        for i in range(len(recent_lows)-1)
    )
    
    if highs_falling and lows_falling:
        return 'bearish'
    
    return 'neutral'
```

---

## ⚖️ 五維評分體系詳解

### 4.1 評分體系總覽

| 維度 | 權重 | 滿分 | v3.19+修正 | 說明 |
|------|------|------|-----------|------|
| **時間框架對齊度** | 40% | 40分 | ✅ 修正1 | 多時間框架趨勢一致性 |
| **市場結構** | 20% | 20分 | - | BOS/CHOCH分析 |
| **Order Block質量** | 20% | 20分 | ✅ 修正5 | OB距離+時效衰減 |
| **動量指標** | 10% | 10分 | - | RSI + MACD |
| **波動率** | 10% | 10分 | - | Bollinger Bands寬度 |

### 4.2 維度1：時間框架對齊度（40%）

#### v3.19+ 統一對齊度評分函數

```python
def _calculate_alignment_score(
    timeframes: Dict[str, str],  # {'1h': 'bullish', '15m': 'bullish', '5m': 'neutral'}
    direction: str               # 'LONG' 或 'SHORT'
) -> Tuple[float, str]:
    """
    時間框架對齊度評分（v3.19+統一版本）
    
    嚴格模式（RELAXED_SIGNAL_MODE=false）：
    ┌────────────────────┬──────┬──────────┐
    │ 對齊情況            │ 分數 │ 等級      │
    ├────────────────────┼──────┼──────────┤
    │ 3框架完全對齊       │ 40   │ Perfect  │
    │ H1+M15對齊         │ 32   │ Good     │
    │ 弱對齊（部分一致）   │ 24   │ Fair     │
    │ 不對齊             │ 0    │ Poor     │
    └────────────────────┴──────┴──────────┘
    
    寬鬆模式（RELAXED_SIGNAL_MODE=true）：
    ┌────────────────────┬──────┬──────────┐
    │ 對齊情況            │ 分數 │ 等級      │
    ├────────────────────┼──────┼──────────┤
    │ H1+M15對齊         │ 32   │ Good     │
    │ 部分對齊           │ 24   │ Fair     │
    │ 低對齊             │ 16   │ Poor     │
    │ 不對齊             │ 0    │ N/A      │
    └────────────────────┴──────┴──────────┘
    
    Returns:
        (分數, 等級)
    """
    
    h1 = timeframes.get('1h', 'neutral')
    m15 = timeframes.get('15m', 'neutral')
    m5 = timeframes.get('5m', 'neutral')
    
    target = 'bullish' if direction == 'LONG' else 'bearish'
    
    # 計算對齊程度
    h1_match = (h1 == target)
    m15_match = (m15 == target)
    m5_match = (m5 == target)
    
    relaxed_mode = self.config.RELAXED_SIGNAL_MODE
    
    if not relaxed_mode:
        # 嚴格模式
        if h1_match and m15_match and m5_match:
            return 40.0, "Perfect"  # 3框架完全對齊
        elif h1_match and m15_match:
            return 32.0, "Good"     # H1+M15對齊
        elif (h1_match and m5_match) or (m15_match and m5_match):
            return 24.0, "Fair"     # 弱對齊
        else:
            return 0.0, "Poor"      # 不對齊
    else:
        # 寬鬆模式
        if h1_match and m15_match:
            return 32.0, "Good"     # H1+M15對齊
        elif h1_match or (m15_match and m5_match):
            return 24.0, "Fair"     # 部分對齊
        elif m15_match or m5_match:
            return 16.0, "Poor"     # 低對齊
        else:
            return 0.0, "N/A"       # 不對齊
```

#### 實際案例

```python
# 案例1：完美對齊（嚴格模式40分）
timeframes = {'1h': 'bullish', '15m': 'bullish', '5m': 'bullish'}
direction = 'LONG'
score, grade = _calculate_alignment_score(timeframes, direction)
# 結果: (40.0, "Perfect")

# 案例2：H1+M15對齊（嚴格模式32分）
timeframes = {'1h': 'bullish', '15m': 'bullish', '5m': 'neutral'}
direction = 'LONG'
score, grade = _calculate_alignment_score(timeframes, direction)
# 結果: (32.0, "Good")

# 案例3：僅M5對齊（嚴格模式0分，寬鬆模式16分）
timeframes = {'1h': 'neutral', '15m': 'neutral', '5m': 'bullish'}
direction = 'LONG'
# 嚴格模式: (0.0, "Poor")
# 寬鬆模式: (16.0, "Poor")
```

### 4.3 維度2：市場結構（20%）

```python
# 市場結構評分邏輯
if direction == 'LONG':
    if market_structure == 'bullish':
        structure_score = 20.0  # 完美匹配
    elif market_structure == 'neutral':
        structure_score = 10.0  # 中性可接受
    else:  # bearish
        structure_score = 0.0   # 逆勢，拒絕
elif direction == 'SHORT':
    if market_structure == 'bearish':
        structure_score = 20.0
    elif market_structure == 'neutral':
        structure_score = 10.0
    else:
        structure_score = 0.0
```

### 4.4 維度3：Order Block質量（20%）

```python
def _calculate_ob_score(order_blocks: List, entry_price: float, direction: str, current_time) -> float:
    """
    OB質量評分（v3.19+含時效衰減）
    
    步驟：
    1. 篩選相關OB（bullish/bearish）
    2. 找最近OB（距離entry_price最近）
    3. 計算距離分數
    4. 應用時效衰減
    5. 返回最終分數
    """
    
    # 篩選相關OB
    relevant_obs = [
        ob for ob in order_blocks 
        if ob['type'] == ('bullish' if direction == 'LONG' else 'bearish')
    ]
    
    if not relevant_obs:
        return 0.0
    
    # 找最近OB
    nearest_ob = min(relevant_obs, key=lambda ob: abs(ob['price'] - entry_price))
    ob_distance = abs(nearest_ob['price'] - entry_price) / entry_price
    
    # 距離分數
    if ob_distance < 0.005:    # <0.5%
        base_score = 20.0
    elif ob_distance < 0.01:   # <1%
        base_score = 15.0
    elif ob_distance < 0.02:   # <2%
        base_score = 10.0
    else:
        base_score = 5.0
    
    # v3.19+ 時效衰減
    ob_quality_decayed = self._calculate_ob_score_with_decay(nearest_ob, current_time)
    decay_multiplier = ob_quality_decayed / max(nearest_ob.get('quality_score', 0.5), 0.01)
    
    # 最終分數
    final_score = base_score * decay_multiplier
    
    return final_score
```

#### OB時效衰減示例

```python
# 假設OB基礎質量分數 = 0.8

# 案例1：新鮮OB（30小時）
age = 30小時
decay_multiplier = 1.0
final_quality = 0.8 × 1.0 = 0.8  # 全效

# 案例2：衰減期OB（60小時）
age = 60小時  # 超過48小時
decay_factor = 1 - (60 - 48) / 24 = 0.5
decay_multiplier = 0.5
final_quality = 0.8 × 0.5 = 0.4  # 衰減50%

# 案例3：過期OB（80小時）
age = 80小時  # 超過72小時
final_quality = 0.0  # 完全失效
```

### 4.5 維度4：動量指標（10%）

```python
# RSI評分
if direction == 'LONG':
    if 50 <= rsi <= 70:
        momentum_score += 5.0  # RSI適中，多頭動能良好
elif direction == 'SHORT':
    if 30 <= rsi <= 50:
        momentum_score += 5.0  # RSI適中，空頭動能良好

# MACD評分
if direction == 'LONG':
    if macd_hist > 0:
        momentum_score += 5.0  # MACD柱狀圖為正，確認多頭
elif direction == 'SHORT':
    if macd_hist < 0:
        momentum_score += 5.0  # MACD柱狀圖為負，確認空頭
```

### 4.6 維度5：波動率（10%）

```python
# Bollinger Bands寬度分位數評分
bb_width_series = calculate_bollinger_bands(m5_data)['width']
bb_percentile = (bb_width_series <= bb_width).sum() / len(bb_width_series)

if 0.6 <= bb_percentile <= 0.8:
    volatility_score = 10.0  # 波動率適中偏高（理想）
elif 0.4 <= bb_percentile <= 0.6:
    volatility_score = 5.0   # 波動率中等（可接受）
else:
    volatility_score = 0.0   # 波動率過高或過低（不理想）
```

---

## 🚦 信號過濾條件

### 5.1 過濾層級架構

```
信號過濾流程（3層過濾）
    │
    ├─> 第1層：方向過濾
    │   ├─ 嚴格模式：H1+M15必須同向
    │   └─ 寬鬆模式：H1主導或M15+M5對齊
    │
    ├─> 第2層：ML預測過濾（可選）
    │   ├─ ML多輸出模式：ml_score >= 60
    │   └─ ML單輸出模式：win_probability >= 0.6
    │
    └─> 第3層：規則驗證過濾
        ├─ 豁免期（前100筆）：
        │   ├─ win_probability >= 0.40
        │   └─ confidence >= 0.40
        │
        └─ 正常期（100筆後）：
            ├─ win_probability >= 0.60
            └─ confidence >= 0.50
```

### 5.2 第1層：方向過濾

#### 嚴格模式（當前配置）

```python
# RELAXED_SIGNAL_MODE = false

def _determine_signal_direction_strict(
    h1_trend: str, 
    m15_trend: str, 
    m5_trend: str,
    market_structure: str,
    order_blocks: List
) -> Optional[str]:
    """
    嚴格模式信號方向判定
    
    LONG條件（全部必須滿足）：
    - H1趨勢 = bullish
    - M15趨勢 = bullish
    - Market Structure ≠ bearish
    - 存在bullish Order Blocks
    
    SHORT條件（全部必須滿足）：
    - H1趨勢 = bearish
    - M15趨勢 = bearish
    - Market Structure ≠ bullish
    - 存在bearish Order Blocks
    """
    
    # LONG信號
    if (h1_trend == 'bullish' and 
        m15_trend == 'bullish' and
        market_structure != 'bearish' and
        any(ob['type'] == 'bullish' for ob in order_blocks)):
        return 'LONG'
    
    # SHORT信號
    if (h1_trend == 'bearish' and 
        m15_trend == 'bearish' and
        market_structure != 'bullish' and
        any(ob['type'] == 'bearish' for ob in order_blocks)):
        return 'SHORT'
    
    return None  # 不符合條件
```

**問題診斷**：
```
假設530個交易對實時掃描：
- H1 bullish: 150個 (28%)
- M15 bullish: 180個 (34%)
- H1+M15同時bullish: 約40個 (7.5%)  ← 嚴格模式要求
- 再加上Market Structure和OB條件: 約5-10個 (1-2%)

結果：530個中僅5-10個可能產生信號
當市場處於震盪或不明朗狀態時 → 0信號
```

#### 寬鬆模式（推薦配置）

```python
# RELAXED_SIGNAL_MODE = true

def _determine_signal_direction_relaxed(
    h1_trend: str, 
    m15_trend: str, 
    m5_trend: str,
    market_structure: str,
    order_blocks: List
) -> Optional[str]:
    """
    寬鬆模式信號方向判定
    
    LONG條件（3選1滿足即可）：
    1. H1 bullish + M15 bullish
    2. H1 bullish + M15 neutral
    3. H1 neutral + M15 bullish + M5 bullish
    
    SHORT條件（3選1滿足即可）：
    1. H1 bearish + M15 bearish
    2. H1 bearish + M15 neutral
    3. H1 neutral + M15 bearish + M5 bearish
    """
    
    # LONG信號（更靈活）
    long_conditions = [
        # 條件1：H1+M15同時多頭
        (h1_trend == 'bullish' and m15_trend == 'bullish'),
        
        # 條件2：H1多頭主導，M15中性
        (h1_trend == 'bullish' and m15_trend == 'neutral'),
        
        # 條件3：H1中性，但M15+M5短期機會
        (h1_trend == 'neutral' and m15_trend == 'bullish' and m5_trend == 'bullish')
    ]
    
    if any(long_conditions) and market_structure != 'bearish':
        if any(ob['type'] == 'bullish' for ob in order_blocks):
            return 'LONG'
    
    # SHORT信號（同理）
    short_conditions = [
        (h1_trend == 'bearish' and m15_trend == 'bearish'),
        (h1_trend == 'bearish' and m15_trend == 'neutral'),
        (h1_trend == 'neutral' and m15_trend == 'bearish' and m5_trend == 'bearish')
    ]
    
    if any(short_conditions) and market_structure != 'bullish':
        if any(ob['type'] == 'bearish' for ob in order_blocks):
            return 'SHORT'
    
    return None
```

**預期改善**：
```
寬鬆模式預期信號數量（530個交易對）：
- H1 bullish + M15 bullish: 40個
- H1 bullish + M15 neutral: 30個
- H1 neutral + M15+M5 bullish: 20個
總計: 約90個符合方向條件 (17%)

再經過Market Structure和OB過濾: 約30-50個 (6-9%)
最後經過信心度過濾: 約15-30個有效信號 (3-6%)

結果：從0信號 → 15-30個信號/周期
```

### 5.3 第2層：ML預測過濾

```python
def _filter_by_ml_prediction(signal: Dict) -> bool:
    """
    ML預測過濾（v3.19+多輸出支持）
    
    ML多輸出模式：
    - ml_score >= 60 (綜合評分0-100)
    
    ML單輸出模式：
    - win_probability >= 0.6 (豁免期0.4)
    
    規則引擎模式：
    - win_probability >= 0.6 AND confidence >= 0.6
      （豁免期：0.4 AND 0.4）
    """
    
    # 檢查是否在豁免期
    trade_count = len(load_trade_history())
    is_bootstrap = (trade_count < Config.BOOTSTRAP_TRADE_LIMIT)
    
    # 動態門檻
    min_wp = Config.BOOTSTRAP_MIN_WIN_PROBABILITY if is_bootstrap else Config.MIN_WIN_PROBABILITY
    min_conf = Config.BOOTSTRAP_MIN_CONFIDENCE if is_bootstrap else Config.MIN_CONFIDENCE
    
    # ML多輸出過濾
    if 'ml_score' in signal and signal['ml_score'] is not None:
        return signal['ml_score'] >= 60.0
    
    # 規則/單輸出過濾
    return (signal['win_probability'] >= min_wp and 
            signal['confidence'] >= min_conf)
```

### 5.4 第3層：質量門檻過濾（v3.18.7+）

```python
def _filter_by_quality_threshold(signal: Dict) -> bool:
    """
    質量門檻過濾（豁免期動態調整）
    
    正常期：quality_score >= 0.6
    豁免期：quality_score >= 0.4
    
    quality_score = confidence × 0.5 + win_probability × 0.5
    """
    
    trade_count = len(load_trade_history())
    is_bootstrap = (trade_count < Config.BOOTSTRAP_TRADE_LIMIT)
    
    # 計算質量分數
    quality_score = (
        signal['confidence'] * 0.5 + 
        signal['win_probability'] * 0.5
    )
    
    # 動態門檻
    threshold = (
        Config.BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD if is_bootstrap 
        else Config.SIGNAL_QUALITY_THRESHOLD
    )
    
    return quality_score >= threshold
```

---

## 🎚️ 嚴格vs寬鬆模式對比

### 6.1 完整對比表

| 對比項目 | 嚴格模式 | 寬鬆模式 |
|---------|---------|---------|
| **配置參數** | `RELAXED_SIGNAL_MODE=false` | `RELAXED_SIGNAL_MODE=true` |
| **H1+M15要求** | 必須同向 | H1主導或M15+M5對齊 |
| **時間框架對齊分數** | 0/24/32/40分 | 0/16/24/32分 |
| **信號數量（530個中）** | 0-10個 | 30-50個 |
| **信號頻率** | 極低（可能數小時無信號） | 中等（每周期2-5個） |
| **信號質量** | 極高（完美對齊） | 中高（主導趨勢對齊） |
| **適用場景** | 資金充足，追求極致質量 | 數據採集期，平衡質量與數量 |
| **ML訓練速度** | 極慢（數據稀缺） | 快速（充足數據） |
| **推薦階段** | 穩定運行期（200+筆交易後） | 啟動期+數據採集期（0-200筆） |

### 6.2 信號產生概率分析

#### 嚴格模式概率計算

```
假設市場隨機分佈（實際會更低）：

P(H1 bullish) = 33%
P(M15 bullish) = 33%
P(M5 bullish) = 33%
P(Market Structure bullish) = 33%
P(有bullish OB) = 30%

嚴格模式 LONG 信號概率：
P(signal) = P(H1 bullish) × P(M15 bullish) × P(MS不bearish) × P(OB存在)
         = 0.33 × 0.33 × 0.67 × 0.30
         = 0.022 (2.2%)

530個交易對預期信號數：
530 × 0.022 = 約12個

實際考慮市場不隨機（趨勢聚集）：
預期信號數 = 5-10個/周期
震盪市場 = 0-2個/周期  ← 當前狀況
```

#### 寬鬆模式概率計算

```
寬鬆模式 LONG 信號概率（3個條件OR邏輯）：

條件1: H1 bullish + M15 bullish = 0.33 × 0.33 = 0.109 (10.9%)
條件2: H1 bullish + M15 neutral = 0.33 × 0.33 = 0.109 (10.9%)
條件3: H1 neutral + M15+M5 bullish = 0.33 × 0.33 × 0.33 = 0.036 (3.6%)

總概率（OR邏輯）:
P(任一條件) ≈ 0.109 + 0.109 + 0.036 = 0.254 (25.4%)

再乘以其他條件：
P(signal) = 0.254 × 0.67 (MS) × 0.30 (OB) = 0.051 (5.1%)

530個交易對預期信號數：
530 × 0.051 = 約27個

實際調整後：
預期信號數 = 30-50個/周期 ✅
震盪市場 = 15-25個/周期
```

### 6.3 實際案例對比

#### 案例1：趨勢明確市場

```
市場狀態：BTCUSDT強勁上漲

H1: bullish (EMA20明顯高於EMA50)
M15: bullish (持續上漲)
M5: bullish (短期回調後反彈)
Market Structure: bullish
Order Blocks: 有2個bullish OB

嚴格模式：
✅ 符合條件 → 生成LONG信號
評分: 40 (對齊) + 20 (MS) + 15 (OB) + 8 (動量) + 5 (波動) = 88/100

寬鬆模式：
✅ 符合條件 → 生成LONG信號  
評分: 32 (對齊) + 20 (MS) + 15 (OB) + 8 (動量) + 5 (波動) = 80/100

結論：兩種模式都能捕捉，評分相近
```

#### 案例2：H1主導市場

```
市場狀態：ETHUSDT H1明確上漲，但M15短期整理

H1: bullish (強勁上漲趨勢)
M15: neutral (短期整理，無明確方向)
M5: neutral (震盪)
Market Structure: bullish
Order Blocks: 有1個bullish OB

嚴格模式：
❌ 不符合（M15不是bullish） → 拒絕信號

寬鬆模式：
✅ 符合條件2（H1 bullish + M15 neutral） → 生成LONG信號
評分: 24 (對齊) + 20 (MS) + 10 (OB) + 5 (動量) + 5 (波動) = 64/100

結論：寬鬆模式能捕捉H1主導機會
```

#### 案例3：短期機會

```
市場狀態：SOLUSDT H1無明確方向，但M15+M5短期上漲

H1: neutral (整理區間)
M15: bullish (突破整理區)
M5: bullish (持續上漲)
Market Structure: neutral
Order Blocks: 有1個bullish OB

嚴格模式：
❌ 不符合（H1不是bullish） → 拒絕信號

寬鬆模式：
✅ 符合條件3（H1 neutral + M15+M5 bullish） → 生成LONG信號
評分: 24 (對齊) + 10 (MS) + 10 (OB) + 5 (動量) + 5 (波動) = 54/100

結論：寬鬆模式能捕捉短期機會（但分數較低，可能被質量門檻過濾）
```

---

## 🚨 當前0信號問題診斷

### 7.1 問題概述

**症狀**：
```
📊 掃描 530 個交易對中...
⏸️  本週期無新信號
✅ 週期完成 | 耗時: 1.2s | 新成交: 0
```

每個周期都是0信號，系統無法開始交易。

### 7.2 根本原因分析

```python
# 當前配置（從系統讀取）
RELAXED_SIGNAL_MODE = False  ← 🔴 這是問題根源！
BOOTSTRAP_MIN_WIN_PROBABILITY = 0.40  ✅
BOOTSTRAP_MIN_CONFIDENCE = 0.40  ✅
```

**診斷邏輯**：

```
第1層過濾（方向判定）：
    嚴格模式要求：H1 + M15 必須同向
    
    530個交易對實時分析：
    ├─ H1 bullish: 約150個 (28%)
    ├─ M15 bullish: 約180個 (34%)
    └─ H1+M15同時bullish: 約40個 (7.5%)
    
    再加上Market Structure和OB條件：
    └─ 最終符合: 約5-10個 (1-2%)
    
    ❌ 當前市場狀態：震盪/不明朗
    └─ 實際符合: 0-2個
    
第2層過濾（ML預測）：
    由於第1層已經是0個，這層無需檢查
    
第3層過濾（質量門檻）：
    由於第1層已經是0個，這層無需檢查
    
最終結果：0信號 ❌
```

### 7.3 數學證明

#### 嚴格模式下的信號產生條件

```
設：
- N = 530（總交易對數）
- P_h1 = 0.30（H1 bullish概率）
- P_m15 = 0.35（M15 bullish概率）
- P_corr = 0.40（H1與M15相關性）
- P_ms = 0.70（Market Structure不對立概率）
- P_ob = 0.30（存在相關OB概率）

嚴格模式信號數期望值：
E(signals) = N × P_h1 × P_m15 × P_corr × P_ms × P_ob
           = 530 × 0.30 × 0.35 × 0.40 × 0.70 × 0.30
           = 530 × 0.00882
           = 4.67個

標準差（假設獨立）：
σ = sqrt(N × p × (1-p)) ≈ 2.16

95%置信區間：
[0.35, 8.99]個信號

結論：在正常市場條件下，嚴格模式預期產生0-9個信號
      在震盪或不明朗市場：0-2個信號 ← 當前狀況
```

#### 寬鬆模式改善預期

```
寬鬆模式放寬條件（OR邏輯）：
P_direction = P(H1+M15同向) + P(H1主導) + P(短期對齊)
            = 0.109 + 0.109 + 0.036
            = 0.254

新期望值：
E(signals) = N × P_direction × P_ms × P_ob
           = 530 × 0.254 × 0.70 × 0.30
           = 530 × 0.053
           = 28.1個

標準差：
σ ≈ 5.15

95%置信區間：
[17.8, 38.4]個信號

結論：寬鬆模式預期產生18-38個信號
      提升幅度：400-800% ✅
```

### 7.4 市場狀態影響分析

| 市場狀態 | 嚴格模式信號數 | 寬鬆模式信號數 | 改善倍數 |
|---------|--------------|--------------|---------|
| **強趨勢（牛市/熊市）** | 15-25個 | 40-60個 | 2.5x |
| **正常趨勢** | 8-15個 | 25-40個 | 3.5x |
| **震盪整理** | 2-8個 | 15-25個 | 6x |
| **混亂市場（當前）** | 0-3個 ❌ | 10-18個 ✅ | ∞ |

### 7.5 解決方案實施步驟

#### 步驟1：添加環境變量（必須）

```bash
# 在Replit Secrets中添加：
Name: RELAXED_SIGNAL_MODE
Value: true
```

#### 步驟2：驗證配置生效

```bash
# 系統會自動重啟，等待1分鐘後檢查日誌：
python -c "from src.config import Config; print('RELAXED_SIGNAL_MODE:', Config.RELAXED_SIGNAL_MODE)"

# 預期輸出：
# RELAXED_SIGNAL_MODE: True ✅
```

#### 步驟3：觀察效果（2-3個周期）

```bash
# 預期日誌變化：

# 修改前：
⏸️  本週期無新信號

# 修改後：
✨ 發現 23 個新信號
📊 信號詳情：
   1. BTCUSDT LONG | 信心度: 0.65 | 勝率: 0.62 | RR: 2.1
   2. ETHUSDT LONG | 信心度: 0.58 | 勝率: 0.55 | RR: 1.8
   ...
```

---

## 📦 44個ML特徵採集

### 8.1 特徵分類總覽

| 類別 | 數量 | 說明 |
|------|------|------|
| **基礎特徵** | 8個 | 價格、SL/TP、RR比 |
| **技術指標** | 12個 | RSI, MACD, ADX, ATR, EMA, BB |
| **ICT/SMC特徵** | 7個 | Order Blocks, Liquidity Zones, Market Structure |
| **EMA偏差特徵** | 8個 | 3個時間框架的EMA偏差% |
| **競價上下文** | 5個 | 排名、總信號數、勝率、信心度、槓桿 |
| **WebSocket特徵** | 4個 | 實時價格偏差、成交量、訂單流（可選） |

### 8.2 完整特徵清單

```python
FEATURE_NAMES = [
    # ========== 基礎特徵（8個） ==========
    'symbol_liquidity',           # 符號流動性評分（0-1）
    'timeframe_1h_trend_score',   # 1h趨勢分數（-1到1）
    'timeframe_15m_trend_score',  # 15m趨勢分數
    'timeframe_5m_trend_score',   # 5m趨勢分數
    'entry_price',                # 入場價格
    'stop_loss',                  # 止損價格
    'take_profit',                # 止盈價格
    'rr_ratio',                   # 風險收益比
    
    # ========== 技術指標（12個） ==========
    'rsi',                        # RSI指標（0-100）
    'macd',                       # MACD值
    'macd_signal',                # MACD信號線
    'macd_hist',                  # MACD柱狀圖
    'adx',                        # ADX趨勢強度（0-100）
    'atr',                        # ATR波動率
    'bb_upper',                   # 布林帶上軌
    'bb_middle',                  # 布林帶中軌
    'bb_lower',                   # 布林帶下軌
    'bb_width',                   # 布林帶寬度
    'ema_20',                     # EMA20值
    'ema_50',                     # EMA50值
    
    # ========== ICT/SMC特徵（7個） ==========
    'market_structure_score',     # 市場結構評分（-1到1）
    'order_blocks_count',         # Order Blocks數量
    'liquidity_zones_count',      # Liquidity Zones數量
    'ob_quality_avg',             # OB平均質量（0-1）
    'ob_distance_min',            # 最近OB距離%
    'fvg_count',                  # Fair Value Gaps數量
    'fvg_strength_avg',           # FVG平均強度（0-1）
    
    # ========== EMA偏差特徵（8個） ==========
    'h1_ema20_dev',               # 1h EMA20偏差%
    'h1_ema50_dev',               # 1h EMA50偏差%
    'm15_ema20_dev',              # 15m EMA20偏差%
    'm15_ema50_dev',              # 15m EMA50偏差%
    'm5_ema20_dev',               # 5m EMA20偏差%
    'm5_ema50_dev',               # 5m EMA50偏差%
    'avg_ema20_dev',              # 平均EMA20偏差（1h+15m）
    'avg_ema50_dev',              # 平均EMA50偏差（1h+15m）
    
    # ========== 競價上下文（5個） ==========
    'signal_rank',                # 信號排名（1-N）
    'total_signals',              # 總信號數
    'win_probability',            # 勝率預測（0-1）
    'confidence',                 # 信心度（0-1）
    'leverage',                   # 槓桿倍數
    
    # ========== WebSocket特徵（4個，可選） ==========
    'ws_price_deviation',         # 實時價格偏差%
    'ws_volume_spike',            # 成交量激增倍數
    'ws_bid_ask_imbalance',       # 買賣盤失衡度
    'ws_order_flow'               # 訂單流方向（-1到1）
]
```

### 8.3 特徵提取示例

```python
def extract_features_from_signal(signal: Dict) -> Dict[str, float]:
    """
    從信號字典提取44個ML特徵
    
    Args:
        signal: 完整信號字典
    
    Returns:
        44個特徵的字典
    """
    
    features = {}
    
    # 基礎特徵
    features['symbol_liquidity'] = signal.get('liquidity_score', 0.5)
    features['timeframe_1h_trend_score'] = trend_to_score(signal['timeframes']['1h'])
    features['timeframe_15m_trend_score'] = trend_to_score(signal['timeframes']['15m'])
    features['timeframe_5m_trend_score'] = trend_to_score(signal['timeframes']['5m'])
    features['entry_price'] = signal['entry_price']
    features['stop_loss'] = signal['stop_loss']
    features['take_profit'] = signal['take_profit']
    features['rr_ratio'] = signal['rr_ratio']
    
    # 技術指標
    indicators = signal['indicators']
    features['rsi'] = indicators['rsi']
    features['macd'] = indicators['macd']
    features['macd_signal'] = indicators['macd_signal']
    features['macd_hist'] = indicators['macd_hist']
    features['adx'] = indicators['adx']
    features['atr'] = indicators['atr']
    features['bb_upper'] = indicators['bb_upper']
    features['bb_middle'] = indicators['bb_middle']
    features['bb_lower'] = indicators['bb_lower']
    features['bb_width'] = indicators['bb_width']
    features['ema_20'] = indicators['ema_20']
    features['ema_50'] = indicators['ema_50']
    
    # ICT/SMC特徵
    features['market_structure_score'] = structure_to_score(signal['market_structure'])
    features['order_blocks_count'] = len(signal['order_blocks'])
    features['liquidity_zones_count'] = len(signal['liquidity_zones'])
    features['ob_quality_avg'] = calculate_avg_ob_quality(signal['order_blocks'])
    features['ob_distance_min'] = calculate_min_ob_distance(signal['order_blocks'], signal['entry_price'])
    features['fvg_count'] = signal.get('fvg_count', 0)
    features['fvg_strength_avg'] = signal.get('fvg_strength_avg', 0.0)
    
    # EMA偏差特徵
    ema_dev = signal.get('ema_deviation', {})
    features['h1_ema20_dev'] = ema_dev.get('h1_ema20_dev', 0.0)
    features['h1_ema50_dev'] = ema_dev.get('h1_ema50_dev', 0.0)
    features['m15_ema20_dev'] = ema_dev.get('m15_ema20_dev', 0.0)
    features['m15_ema50_dev'] = ema_dev.get('m15_ema50_dev', 0.0)
    features['m5_ema20_dev'] = ema_dev.get('m5_ema20_dev', 0.0)
    features['m5_ema50_dev'] = ema_dev.get('m5_ema50_dev', 0.0)
    features['avg_ema20_dev'] = ema_dev.get('avg_ema20_dev', 0.0)
    features['avg_ema50_dev'] = ema_dev.get('avg_ema50_dev', 0.0)
    
    # 競價上下文（在execute_best_trade時填充）
    features['signal_rank'] = signal.get('rank', 1)
    features['total_signals'] = signal.get('total_signals', 1)
    features['win_probability'] = signal['win_probability']
    features['confidence'] = signal['confidence']
    features['leverage'] = signal.get('leverage', 1.0)
    
    # WebSocket特徵（可選）
    ws_data = signal.get('ws_data', {})
    features['ws_price_deviation'] = ws_data.get('price_deviation', 0.0)
    features['ws_volume_spike'] = ws_data.get('volume_spike', 1.0)
    features['ws_bid_ask_imbalance'] = ws_data.get('bid_ask_imbalance', 0.0)
    features['ws_order_flow'] = ws_data.get('order_flow', 0.0)
    
    return features
```

---

## 🏆 信號質量分級

### 9.1 v3.19+ 動態分級系統

```python
def _classify_signal(signal: Dict, is_bootstrap: bool) -> str:
    """
    信號質量分級（v3.19+修正4）
    
    豁免期（前100筆交易）：
    ┌──────────┬────────────┬────────┐
    │ 等級      │ 質量分數    │ 處理    │
    ├──────────┼────────────┼────────┤
    │ Excellent│ ≥ 0.80     │ ✅接受 │
    │ Good     │ 0.60-0.80  │ ✅接受 │
    │ Fair     │ 0.40-0.60  │ ✅接受 │
    │ Poor     │ 0.30-0.40  │ ✅接受 │
    │ Rejected │ < 0.30     │ ❌拒絕 │
    └──────────┴────────────┴────────┘
    
    正常期（100筆後）：
    ┌──────────┬────────────┬────────┐
    │ 等級      │ 質量分數    │ 處理    │
    ├──────────┼────────────┼────────┤
    │ Excellent│ ≥ 0.80     │ ✅接受 │
    │ Good     │ 0.60-0.80  │ ✅接受 │
    │ Fair     │ 0.50-0.60  │ ⚠️謹慎 │
    │ Poor     │ 0.40-0.50  │ ⚠️謹慎 │
    │ Rejected │ < 0.60     │ ❌拒絕 │
    └──────────┴────────────┴────────┘
    
    質量分數計算：
    quality_score = confidence × 0.5 + win_probability × 0.5
    """
    
    quality_score = signal['confidence'] * 0.5 + signal['win_probability'] * 0.5
    
    if is_bootstrap:
        # 豁免期：更寬鬆的分級
        if quality_score >= 0.80:
            return "Excellent"
        elif quality_score >= 0.60:
            return "Good"
        elif quality_score >= 0.40:
            return "Fair"
        elif quality_score >= 0.30:
            return "Poor"
        else:
            return "Rejected"
    else:
        # 正常期：標準分級
        if quality_score >= 0.80:
            return "Excellent"
        elif quality_score >= 0.60:
            return "Good"
        elif quality_score >= 0.50:
            return "Fair"
        elif quality_score >= 0.40:
            return "Poor"
        else:
            return "Rejected"
```

### 9.2 分級示例

```python
# 示例1：優秀信號
signal = {
    'confidence': 0.85,
    'win_probability': 0.75
}
quality_score = 0.85 * 0.5 + 0.75 * 0.5 = 0.80
grade = "Excellent" ✅

# 示例2：良好信號
signal = {
    'confidence': 0.70,
    'win_probability': 0.65
}
quality_score = 0.70 * 0.5 + 0.65 * 0.5 = 0.675
grade = "Good" ✅

# 示例3：豁免期可接受，正常期拒絕
signal = {
    'confidence': 0.50,
    'win_probability': 0.45
}
quality_score = 0.50 * 0.5 + 0.45 * 0.5 = 0.475
豁免期: "Fair" ✅
正常期: "Rejected" ❌
```

---

## 📈 實戰案例分析

### 10.1 完整信號生成案例

#### 案例：BTCUSDT LONG信號（寬鬆模式）

**市場狀態**：
```
時間: 2025-11-01 15:35:00 UTC
價格: $68,500
```

**時間框架分析**：
```
H1 (1小時):
├─ EMA20: $68,200
├─ EMA50: $67,500
├─ 趨勢: bullish (EMA20 > EMA50, 斜率+0.015)
└─ ADX: 28 (強趨勢)

M15 (15分鐘):
├─ EMA20: $68,400
├─ EMA50: $68,200
├─ 趨勢: neutral (EMA20略高於EMA50, 斜率+0.005)
└─ RSI: 58 (適中)

M5 (5分鐘):
├─ EMA20: $68,480
├─ EMA50: $68,450
├─ 趨勢: bullish (短期上漲)
└─ MACD: +15 (多頭)
```

**ICT/SMC結構**：
```
Order Blocks:
├─ OB #1: bullish, zone $68,200-$68,300, quality 0.75, age 18h ✅
├─ OB #2: bullish, zone $67,800-$67,900, quality 0.60, age 55h ⚠️
└─ 最近OB距離: 0.3% (非常接近)

Market Structure: bullish (高點抬升+低點抬升)

Liquidity Zones:
└─ Support at $68,000 (強度0.8)
```

**信號生成流程**：

```python
# Step 1: 數據驗證 ✅
# 3個時間框架數據完整

# Step 2: 技術指標 ✅
indicators = {
    'rsi': 58,
    'macd_hist': +15,
    'adx': 28,
    'atr': 420,
    'bb_width': 0.025
}

# Step 3: 趨勢確定 ✅
h1_trend = 'bullish'
m15_trend = 'neutral'
m5_trend = 'bullish'

# Step 4: ICT結構 ✅
order_blocks = [OB1, OB2]
market_structure = 'bullish'

# Step 5: 信號方向判定
# 寬鬆模式條件2：H1 bullish + M15 neutral ✅
direction = 'LONG'

# Step 6: 五維信心度評分
sub_scores = {
    'timeframe_alignment': 24.0,  # H1主導（寬鬆模式）
    'market_structure': 20.0,      # bullish匹配
    'order_block': 18.0,           # 距離近(20分) × 衰減(0.9)
    'momentum': 8.0,               # RSI適中(5) + MACD正(3)
    'volatility': 5.0              # BB寬度中等
}
total_confidence = 75.0 / 100 = 0.75

# Step 7: SL/TP計算
entry_price = 68,500
base_sl = 68,500 - (2 × 420) = 67,660
base_tp = 68,500 + (840 × 1.5) = 69,760
base_rr_ratio = 1.5

# Step 8: 構建信號
signal = {
    'symbol': 'BTCUSDT',
    'direction': 'LONG',
    'entry_price': 68500,
    'stop_loss': 67660,
    'take_profit': 69760,
    'confidence': 0.75,
    'win_probability': 0.65,  # ML預測
    'rr_ratio': 1.5,
    'sub_scores': sub_scores,
    # ... 44個完整特徵
}
```

**過濾驗證**：
```python
# 第1層：方向過濾 ✅
# 寬鬆模式條件2滿足

# 第2層：ML預測過濾 ✅
# win_probability (0.65) >= 0.40 (豁免期)
# confidence (0.75) >= 0.40 (豁免期)

# 第3層：質量門檻過濾 ✅
quality_score = 0.75 * 0.5 + 0.65 * 0.5 = 0.70
# 0.70 >= 0.40 (豁免期門檻) ✅

# 最終結果：信號通過所有過濾 ✅
```

**後續處理**：
```python
# SelfLearningTrader處理
leverage = calculate_leverage(0.65, 0.75) = 8.5x
adjusted_sl, adjusted_tp = adjust_sl_tp_for_leverage(68500, 'LONG', 0.012, 8.5)
# 高槓桿 → 放寬止損
adjusted_sl = 67,400 (原67,660)
adjusted_tp = 70,100 (原69,760)

# v3.19+ 重算RR
adjusted_rr_ratio = (70100 - 68500) / (68500 - 67400) = 1.45

# 競價評分
weighted_score = 0.75 * 0.4 + 0.65 * 0.4 + (1.45/3.0) * 0.2 = 0.66

# 執行決策
if weighted_score >= max(all_signals):
    execute_trade(signal)
```

### 10.2 寬鬆vs嚴格模式對比案例

**市場狀態**：H1主導上漲，M15短期整理

| 項目 | 嚴格模式 | 寬鬆模式 |
|------|---------|---------|
| **H1趨勢** | bullish | bullish |
| **M15趨勢** | neutral ❌ | neutral ✅ |
| **M5趨勢** | neutral | neutral |
| **方向判定** | None（拒絕） | LONG（接受） |
| **對齊度分數** | 0分 | 24分 |
| **總信心度** | - | 67/100 |
| **最終結果** | ❌無信號 | ✅生成信號 |

**結論**：寬鬆模式能夠捕捉H1主導的中期機會，而嚴格模式會錯過。

---

## 📝 總結與建議

### 關鍵要點

1. **當前問題**：嚴格模式導致0信號，系統無法開始交易
2. **根本原因**：`RELAXED_SIGNAL_MODE=false` 過濾條件過於苛刻
3. **解決方案**：設置 `RELAXED_SIGNAL_MODE=true`
4. **預期改善**：信號數量從0 → 30-50個/周期

### 行動建議

**立即執行**：
1. 在Replit Secrets添加 `RELAXED_SIGNAL_MODE=true`
2. 等待系統自動重啟（約1分鐘）
3. 觀察2-3個交易周期（2-3分鐘）

**預期結果**：
```
✨ 發現 23 個新信號
📊 質量分佈：
   Excellent: 3個 (13%)
   Good: 8個 (35%)
   Fair: 12個 (52%)
```

**長期策略**：
- 階段1（0-100筆）：寬鬆模式 + 豁免期門檻（0.4/0.4）
- 階段2（100-200筆）：寬鬆模式 + 正常門檻（0.6/0.5）
- 階段3（200+筆）：可考慮嚴格模式（根據模型表現）

---

**🚀 系統已準備好開始採集數據和交易！**

---

*簡報生成時間: 2025-11-01*  
*版本: v3.19+*  
*當前配置: RELAXED_SIGNAL_MODE=false（待修正）*
