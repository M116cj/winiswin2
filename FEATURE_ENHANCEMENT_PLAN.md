# 🧠 ICT/SMC高级特征增强方案

**版本**: v3.19 (计划中)  
**当前特征数**: 44个  
**计划新增**: 12个ICT/SMC高级特征（8基础 + 4合成）  
**数据源**: Binance WebSocket实时数据流

---

## 📊 特征总览

### **当前特征（44个）- v3.18.10**

参见 `ML_FEATURES_v3.18.md`

### **计划新增特征（12个）**

#### **基础特征（8个）**
1. `market_structure` - 市场结构（MSB/MSS）
2. `order_blocks_count` - 订单块数量
3. `institutional_candle` - 机构K线识别
4. `liquidity_grab` - 流动性抓取
5. `order_flow` - 订单流（买卖压力）
6. `fvg_count` - 公允价值缺口数量
7. `trend_alignment` - 多时间框架对齐度（增强版）
8. `swing_high_distance` - 摆动高点距离

#### **合成特征（4个）**
1. `structure_integrity` - 结构完整性
2. `institutional_participation` - 机构参与度
3. `timeframe_convergence` - 时间框架收敛度
4. `liquidity_context` - 流动性情境

---

## 📋 基础特征详细定义

### 1. **market_structure** - 市场结构

**定义**: 识别市场趋势方向（多头、空头、中性），基于价格摆动点（Swing High/Low）的变化。参考市场结构破坏（MSB）和转换（MSS）概念。

**计算方式**:
```python
def calculate_market_structure(klines):
    """
    数据源: Binance K线流 (1h/15m/5m)
    
    步骤:
    1. 在滚动窗口（100根K线）中识别摆动点
       - 摆动高点: 某根K线最高价 > 前后N根K线最高价 (N=5)
       - 摆动低点: 某根K线最低价 < 前后N根K线最低价
    
    2. 判断趋势:
       - 若连续摆动高点和低点上移 → 1 (多头)
       - 若连续摆动高点和低点下移 → -1 (空头)
       - 否则 → 0 (中性)
    
    返回: 整数 (1, -1, 0)
    """
    swings = find_swing_highs_lows(klines, window=100, lookback=5)
    
    if is_uptrend(swings):
        return 1
    elif is_downtrend(swings):
        return -1
    else:
        return 0
```

---

### 2. **order_blocks_count** - 订单块数量

**定义**: 订单块是机构集中买入/卖出导致价格反转的区域。看涨订单块出现在下跌趋势末端（突破前最后一根阴线），看跌订单块出现在上涨趋势末端（突破前最后一根阳线）。

**计算方式**:
```python
def calculate_order_blocks_count(klines):
    """
    数据源: Binance K线流 (15m)
    
    识别条件:
    - 看涨订单块: 价格创新低后，出现阴线，随后突破该阴线高点
    - 看跌订单块: 价格创新高后，出现阳线，随后跌破该阳线低点
    
    在滚动窗口（50根K线）内统计已验证的订单块数量
    
    返回: 整数 (≥0)
    """
    order_blocks = []
    
    for i in range(len(klines) - 2):
        # 看涨订单块
        if is_new_low(klines, i) and is_bearish_candle(klines[i]):
            if klines[i+1]['high'] > klines[i]['high']:
                order_blocks.append(('bullish', i))
        
        # 看跌订单块
        if is_new_high(klines, i) and is_bullish_candle(klines[i]):
            if klines[i+1]['low'] < klines[i]['low']:
                order_blocks.append(('bearish', i))
    
    # 统计已验证的订单块（价格回测并反转）
    verified_blocks = [ob for ob in order_blocks if is_verified(ob, klines)]
    
    return len(verified_blocks)
```

---

### 3. **institutional_candle** - 机构K线

**定义**: 反映大资金进场的K线，通常具有大实体、小影线和高成交量。

**计算方式**:
```python
def calculate_institutional_candle(kline, recent_klines):
    """
    数据源: Binance K线流 (5m) + 交易流
    
    识别条件:
    1. 实体比率 > 0.7 (实体主导)
       实体比率 = |收盘 - 开盘| / (最高 - 最低)
    
    2. 成交量Z值 > 2 (异常放量)
       成交量Z = (当前成交量 - 均值) / 标准差
    
    3. 影线比率 < 0.3 (影线短)
    
    返回: 二进制 (0或1)
    """
    # 计算实体比率
    body = abs(kline['close'] - kline['open'])
    range_size = kline['high'] - kline['low']
    body_ratio = body / range_size if range_size > 0 else 0
    
    # 计算成交量Z值
    volumes = [k['volume'] for k in recent_klines[-20:]]
    mean_vol = np.mean(volumes)
    std_vol = np.std(volumes)
    volume_z = (kline['volume'] - mean_vol) / std_vol if std_vol > 0 else 0
    
    # 计算影线比率
    upper_wick = kline['high'] - max(kline['open'], kline['close'])
    lower_wick = min(kline['open'], kline['close']) - kline['low']
    wick_ratio = (upper_wick + lower_wick) / range_size if range_size > 0 else 0
    
    # 判断是否为机构K线
    if body_ratio > 0.7 and volume_z > 2 and wick_ratio < 0.3:
        return 1
    else:
        return 0
```

---

### 4. **liquidity_grab** - 流动性抓取

**定义**: 价格快速突破支撑/阻力位以触发止损单，随后迅速反转。

**计算方式**:
```python
def calculate_liquidity_grab(klines, atr):
    """
    数据源: Binance K线流 (5m)
    
    识别条件:
    1. 识别流动性池（最近摆动高低点）
    2. 价格在1根K线内突破 > 0.5 ATR
    3. 下一根K线收盘价回归原区间并形成反转
    
    返回: 二进制 (0或1)
    """
    # 识别最近摆动点
    swing_high = find_recent_swing_high(klines)
    swing_low = find_recent_swing_low(klines)
    
    current = klines[-1]
    previous = klines[-2]
    
    # 检测突破阻力后反转
    if current['high'] > swing_high + 0.5 * atr:
        if current['close'] < swing_high and is_reversal_pattern(current):
            return 1
    
    # 检测跌破支撑后反转
    if current['low'] < swing_low - 0.5 * atr:
        if current['close'] > swing_low and is_reversal_pattern(current):
            return 1
    
    return 0
```

---

### 5. **order_flow** - 订单流

**定义**: 实时买卖压力平衡，通过主动买入/卖出量衡量。

**计算方式**:
```python
def calculate_order_flow(trades):
    """
    数据源: Binance逐笔交易流 (btcusdt@trade)
    
    解析交易数据:
    - m = true: 主动卖出（做市方卖出）
    - m = false: 主动买入（做市方买入）
    
    在时间窗口（1分钟）内计算:
    订单流 = (主动买入量 - 主动卖出量) / (总量)
    
    返回: 标准化值 (-1到1)
    """
    buy_volume = sum(t['q'] for t in trades if not t['m'])
    sell_volume = sum(t['q'] for t in trades if t['m'])
    total_volume = buy_volume + sell_volume
    
    if total_volume > 0:
        order_flow = (buy_volume - sell_volume) / total_volume
    else:
        order_flow = 0
    
    return order_flow
```

---

### 6. **fvg_count** - FVG数量

**定义**: 公允价值缺口（Fair Value Gap），是价格跳空形成的未交易区域，通常被回填。

**计算方式**:
```python
def calculate_fvg_count(klines):
    """
    数据源: Binance K线流 (5m)
    
    识别条件（连续3根K线）:
    - 看涨FVG: K1最低价 > K3最高价
    - 看跌FVG: K1最高价 < K3最低价
    
    在滚动窗口（30根K线）内统计未回填的FVG
    
    返回: 整数 (≥0)
    """
    fvgs = []
    
    for i in range(len(klines) - 2):
        k1, k2, k3 = klines[i], klines[i+1], klines[i+2]
        
        # 看涨FVG
        if k1['low'] > k3['high']:
            fvgs.append({
                'type': 'bullish',
                'gap': (k3['high'], k1['low']),
                'index': i
            })
        
        # 看跌FVG
        if k1['high'] < k3['low']:
            fvgs.append({
                'type': 'bearish',
                'gap': (k1['high'], k3['low']),
                'index': i
            })
    
    # 统计未回填的FVG
    unfilled_fvgs = [fvg for fvg in fvgs if not is_filled(fvg, klines)]
    
    return len(unfilled_fvgs)
```

---

### 7. **trend_alignment** - 趋势对齐度（增强版）

**定义**: 多时间框架趋势的一致性，越高表示趋势动能越强。

**计算方式**:
```python
def calculate_trend_alignment(data_1h, data_15m, data_5m):
    """
    数据源: Binance多时间框架K线流 (1h, 15m, 5m)
    
    步骤:
    1. 分别计算各时间框架的market_structure
    2. 计算对齐度:
       - 三个时间框架趋势相同 → 1.0
       - 两个相同 → 0.5
       - 全部不同 → 0
    
    返回: 连续值 (0到1)
    """
    trend_1h = calculate_market_structure(data_1h)
    trend_15m = calculate_market_structure(data_15m)
    trend_5m = calculate_market_structure(data_5m)
    
    trends = [trend_1h, trend_15m, trend_5m]
    
    # 计算对齐度
    if len(set(trends)) == 1 and trends[0] != 0:
        return 1.0  # 完全对齐
    elif len([t for t in trends if t == trends[0]]) == 2:
        return 0.5  # 部分对齐
    else:
        return 0.0  # 不对齐
```

---

### 8. **swing_high_distance** - 摆动高点距离

**定义**: 当前价格与最近摆动高点的距离，反映价格相对位置。

**计算方式**:
```python
def calculate_swing_high_distance(klines, current_price, atr):
    """
    数据源: Binance K线流 (15m)
    
    步骤:
    1. 识别最近摆动高点
    2. 计算标准化距离:
       距离 = (当前价格 - 摆动高点) / ATR(14)
    
    使用ATR标准化以消除波动性影响
    
    返回: 标准化值 (负值表示当前价格低于摆动高点)
    """
    swing_high = find_recent_swing_high(klines, lookback=5)
    
    if swing_high and atr > 0:
        distance = (current_price - swing_high) / atr
    else:
        distance = 0
    
    return distance
```

---

## 📋 合成特征详细定义

### 1. **structure_integrity** - 结构完整性

**定义**: 市场结构的健康程度，基于订单块、FVG和市场趋势的稳定性。

**计算公式**:
```python
def calculate_structure_integrity(market_structure, fvg_count, order_blocks_count):
    """
    公式:
    structure_integrity = 0.4 * I(market_structure ≠ 0) 
                        + 0.3 * (1 - min(1, fvg_count / 5)) 
                        + 0.3 * tanh(order_blocks_count / 3)
    
    逻辑: 趋势明确、FVG少、订单块多时得分高
    
    返回: 连续值 (0到1)
    """
    structure_clear = 1 if market_structure != 0 else 0
    fvg_penalty = 1 - min(1, fvg_count / 5)
    ob_score = np.tanh(order_blocks_count / 3)
    
    integrity = 0.4 * structure_clear + 0.3 * fvg_penalty + 0.3 * ob_score
    
    return integrity
```

---

### 2. **institutional_participation** - 机构参与度

**定义**: 机构资金活跃度，结合机构K线、订单流和流动性抓取。

**计算公式**:
```python
def calculate_institutional_participation(institutional_candle, order_flow, liquidity_grab):
    """
    公式:
    institutional_participation = 0.5 * institutional_candle 
                                 + 0.3 * abs(order_flow) 
                                 + 0.2 * liquidity_grab
    
    逻辑: 机构K线出现、订单流失衡、流动性抓取发生时得分高
    
    返回: 连续值 (0到1)
    """
    participation = (0.5 * institutional_candle + 
                    0.3 * abs(order_flow) + 
                    0.2 * liquidity_grab)
    
    return participation
```

---

### 3. **timeframe_convergence** - 时间框架收敛度

**定义**: 多时间框架趋势的动态收敛程度，基于短期趋势与长期趋势的相关性。

**计算公式**:
```python
def calculate_timeframe_convergence(trend_1h, trend_15m, trend_5m):
    """
    公式:
    convergence = 1 - (std(T) / 2)
    
    其中 T = [trend_1h, trend_15m, trend_5m]
    
    返回: 连续值 (0到1)
    """
    trends = np.array([trend_1h, trend_15m, trend_5m])
    std = np.std(trends)
    convergence = 1 - (std / 2)
    
    return max(0, min(1, convergence))
```

---

### 4. **liquidity_context** - 流动性情境

**定义**: 市场流动性的综合状态，结合订单簿深度和流动性抓取事件。

**计算公式**:
```python
def calculate_liquidity_context(depth_data, liquidity_grab):
    """
    数据源: Binance深度流 (btcusdt@depth)
    
    步骤:
    1. 从深度流获取最佳买卖价和数量
    2. 计算流动性得分:
       深度 = (最佳买价数量 + 最佳卖价数量) / 2
       价差 = (最佳卖价 - 最佳买价) / 最佳买价
       
       流动性得分 = 0.6 * tanh(深度 / 100) + 0.4 * (1 - min(1, 价差 / 0.001))
    
    3. 结合流动性抓取:
       liquidity_context = 0.7 * 流动性得分 + 0.3 * liquidity_grab
    
    返回: 连续值 (0到1)
    """
    best_bid_qty = depth_data['bids'][0][1]
    best_ask_qty = depth_data['asks'][0][1]
    depth = (best_bid_qty + best_ask_qty) / 2
    
    best_bid_price = depth_data['bids'][0][0]
    best_ask_price = depth_data['asks'][0][0]
    spread = (best_ask_price - best_bid_price) / best_bid_price
    
    liquidity_score = (0.6 * np.tanh(depth / 100) + 
                      0.4 * (1 - min(1, spread / 0.001)))
    
    context = 0.7 * liquidity_score + 0.3 * liquidity_grab
    
    return context
```

---

## 🔧 Binance WebSocket实施指南

### **关键数据流订阅**

#### 1. **K线流** - 用于大多数特征
```python
# 订阅多时间框架K线
streams = [
    "btcusdt@kline_1h",
    "btcusdt@kline_15m",
    "btcusdt@kline_5m"
]

# 数据字段
{
    'k': {
        't': 开盘时间,
        'o': 开盘价,
        'h': 最高价,
        'l': 最低价,
        'c': 收盘价,
        'v': 成交量
    }
}
```

#### 2. **交易流** - 用于订单流
```python
# 订阅逐笔交易
stream = "btcusdt@trade"

# 数据字段
{
    'p': 价格,
    'q': 数量,
    'm': 是否主动卖出  # true=卖出, false=买入
}
```

#### 3. **深度流** - 用于流动性情境
```python
# 订阅订单簿深度
stream = "btcusdt@depth"

# 数据字段
{
    'b': [[价格, 数量], ...],  # 买单
    'a': [[价格, 数量], ...]   # 卖单
}
```

---

### **实时计算引擎设计**

```python
from collections import deque
import numpy as np

class ICTFeatureEngine:
    def __init__(self):
        # 数据缓冲
        self.kline_buffer_1h = deque(maxlen=100)
        self.kline_buffer_15m = deque(maxlen=100)
        self.kline_buffer_5m = deque(maxlen=100)
        self.trade_buffer = deque(maxlen=1000)
        
        # 特征缓存
        self.features = {}
    
    def on_kline_message(self, message):
        """处理K线数据"""
        kline = message['k']
        interval = message['k']['i']
        
        # 添加到对应缓冲区
        if interval == '1h':
            self.kline_buffer_1h.append(kline)
            self.update_market_structure()
        elif interval == '15m':
            self.kline_buffer_15m.append(kline)
            self.update_order_blocks()
        elif interval == '5m':
            self.kline_buffer_5m.append(kline)
            self.update_institutional_candle()
            self.update_fvg_count()
    
    def on_trade_message(self, message):
        """处理交易数据"""
        self.trade_buffer.append(message)
        self.update_order_flow()
    
    def on_depth_message(self, message):
        """处理深度数据"""
        self.update_liquidity_context(message)
    
    def get_all_features(self):
        """获取所有12个新特征"""
        return {
            # 基础特征
            'market_structure': self.features.get('market_structure', 0),
            'order_blocks_count': self.features.get('order_blocks_count', 0),
            'institutional_candle': self.features.get('institutional_candle', 0),
            'liquidity_grab': self.features.get('liquidity_grab', 0),
            'order_flow': self.features.get('order_flow', 0),
            'fvg_count': self.features.get('fvg_count', 0),
            'trend_alignment': self.features.get('trend_alignment', 0),
            'swing_high_distance': self.features.get('swing_high_distance', 0),
            
            # 合成特征
            'structure_integrity': self.features.get('structure_integrity', 0),
            'institutional_participation': self.features.get('institutional_participation', 0),
            'timeframe_convergence': self.features.get('timeframe_convergence', 0),
            'liquidity_context': self.features.get('liquidity_context', 0)
        }
```

---

## ⚠️ 注意事项

### 1. **滞后性控制**
- ✅ 优先使用短期K线（5分钟）和实时交易流
- ✅ 避免依赖移动平均等滞后指标
- ✅ 改用价格行为（摆动点、订单块）

### 2. **标准化处理**
- ✅ 所有连续特征使用ATR或Z-score标准化
- ✅ 确保跨资产可比性
- ✅ 归一化到0-1或-1到1范围

### 3. **验证与回测**
- ✅ 通过历史K线数据验证订单块和FVG识别准确性
- ✅ 回测特征与交易绩效的相关性（胜率、盈亏比）
- ✅ 使用特征重要性分析剔除低贡献特征

---

## 📊 特征总数变化

| 版本 | 特征数 | 新增特征 |
|------|--------|---------|
| v3.18.10 | 44个 | - |
| **v3.19 (计划)** | **56个** | **+12个ICT/SMC高级特征** |

---

## 🚀 实施建议

### **阶段1: 基础特征实现（1-2周）**
- [ ] 实现8个基础特征计算函数
- [ ] 集成到`feature_engine.py`
- [ ] WebSocket数据流接入

### **阶段2: 合成特征实现（1周）**
- [ ] 实现4个合成特征
- [ ] 验证计算逻辑正确性

### **阶段3: 历史数据回测（1周）**
- [ ] 使用历史K线验证特征有效性
- [ ] 分析特征重要性
- [ ] 调整权重系数

### **阶段4: 模型重训练（1周）**
- [ ] 使用新的56特征重训练XGBoost模型
- [ ] 对比新旧模型性能
- [ ] 部署到生产环境

---

## 📝 总结

这个ICT/SMC高级特征方案将系统特征从44个扩展到56个，新增的12个特征更贴近机构交易行为，有望显著提升模型预测准确性。

**关键优势**:
- ✅ 基于真实机构行为（订单块、流动性抓取）
- ✅ 实时计算（WebSocket数据流）
- ✅ 多维度综合（价格、成交量、订单簿）
- ✅ 低滞后性（避免传统指标延迟）

**下一步**: 根据项目优先级决定是否实施此方案。
