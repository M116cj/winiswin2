# 🧠 ML模型学习特征列表 v3.18

**总计**: **44个特征**  
**文件**: `src/ml/feature_engine.py`  
**版本**: v3.17.2+ (加入WebSocket专属特征)

---

## 📊 特征分类

### 1. 基本特征（8个）

| 特征名 | 说明 | 数据范围 |
|-------|------|---------|
| `confidence` | 信心度 | 0-1 |
| `leverage` | 杠杆倍数 | 1-125x |
| `position_value` | 仓位价值（USDT） | 10+ |
| `risk_reward_ratio` | 风险回报比（R:R） | 1.0-3.0 |
| `order_blocks_count` | OrderBlock数量 | 0+ |
| `liquidity_zones_count` | 流动性区域数量 | 0+ |
| `entry_price` | 入场价格 | >0 |
| `win_probability` | 预估胜率 | 0-1 |

---

### 2. 技术指标（10个）

| 特征名 | 说明 | 数据范围 |
|-------|------|---------|
| `rsi` | 相对强弱指标 | 0-100 |
| `macd` | MACD值 | 任意实数 |
| `macd_signal` | MACD信号线 | 任意实数 |
| `macd_histogram` | MACD柱状图 | 任意实数 |
| `atr` | 平均真实范围 | >0 |
| `bb_width` | 布林带宽度 | >0 |
| `volume_sma_ratio` | 成交量/SMA比率 | >0 |
| `ema50` | 50周期EMA | >0 |
| `ema200` | 200周期EMA | >0 |
| `volatility_24h` | 24小时波动率 | 0-1 |

---

### 3. 趋势特征（6个）

| 特征名 | 说明 | 编码 |
|-------|------|------|
| `trend_1h` | 1小时趋势 | 1=多头, -1=空头, 0=中性 |
| `trend_15m` | 15分钟趋势 | 1=多头, -1=空头, 0=中性 |
| `trend_5m` | 5分钟趋势 | 1=多头, -1=空头, 0=中性 |
| `market_structure` | 市场结构 | 1=看多, -1=看空, 0=中性 |
| `direction` | 交易方向 | 1=LONG, -1=SHORT |
| `trend_alignment` | 趋势对齐度 | 0-1（完全对齐=1.0） |

**趋势对齐度计算**:
```python
# 完全对齐（H1+M15+M5都是多头或都是空头）= 1.0
# 部分对齐（2个同向，1个不同）= 0.67
# 完全不对齐（混合）= 0.33或0
alignment = abs(trend_1h + trend_15m + trend_5m) / 3.0
```

---

### 4. 其他特征（14个）

| 特征名 | 说明 | 数据范围 |
|-------|------|---------|
| `ema50_slope` | EMA50斜率 | 任意实数 |
| `ema200_slope` | EMA200斜率 | 任意实数 |
| `higher_highs` | 更高高点数量 | 0+ |
| `lower_lows` | 更低低点数量 | 0+ |
| `support_strength` | 支撑强度 | 0-1 |
| `resistance_strength` | 阻力强度 | 0-1 |
| `fvg_count` | FVG（公允价值缺口）数量 | 0+ |
| `swing_high_distance` | 到摆动高点距离 | >0 |
| `swing_low_distance` | 到摆动低点距离 | >0 |
| `volume_profile` | 成交量分布 | 0-1 |
| `price_momentum` | 价格动量 | 任意实数 |
| `order_flow` | 订单流 | 任意实数 |
| `liquidity_grab` | 流动性抓取 | 0/1（布尔值） |
| `institutional_candle` | 机构K线 | 0/1（布尔值） |

**注**: 这14个特征目前使用默认值，未来可根据需要补充计算逻辑。

---

### 5. 竞价上下文特征（3个）- v3.17.10+

| 特征名 | 说明 | 数据范围 |
|-------|------|---------|
| `competition_rank` | 信号在竞价中的排名 | 1, 2, 3... |
| `score_gap_to_best` | 与最高分的差距 | 0-1（越小越好） |
| `num_competing_signals` | 竞争信号总数 | 1+ |

**目的**: 捕捉信号质量的相对优势，帮助模型学习"什么样的信号更容易在竞价中胜出"。

---

### 6. 🔥 WebSocket专属特征（3个）- v3.17.2+

| 特征名 | 说明 | 计算方法 |
|-------|------|---------|
| `latency_zscore` | 网络延迟Z-score | (当前延迟 - 平均延迟) / 标准差 |
| `shard_load` | 分片负载 | 该分片请求数 / 总请求数 |
| `timestamp_consistency` | 时间戳一致性 | 1=一致(<1秒差异), 0=不一致 |

**目的**: 捕捉网络质量对交易的影响。

**latency_zscore解读**:
- **Z < -1**: 延迟异常低（可能数据陈旧或缓存）
- **-1 ≤ Z ≤ 1**: 延迟正常
- **Z > 1**: 延迟异常高（网络拥塞或连接不稳定）

---

## 🎯 特征提取流程

```python
# 1. 构建基础特征（38个）
base_features = _build_base_features(signal)

# 2. 加入竞价上下文特征（3个）
rank_features = {
    'competition_rank': 1,
    'score_gap_to_best': 0.0,
    'num_competing_signals': 5
}

# 3. 加入WebSocket专属特征（3个）
websocket_features = {
    'latency_zscore': 0.5,
    'shard_load': 0.25,
    'timestamp_consistency': 1
}

# 4. 合并为完整特征（44个）
enhanced_features = {**base_features, **rank_features, **websocket_features}
```

---

## 📋 特征完整列表（按顺序）

**用于模型训练的44个特征（严格顺序）**:

```python
[
    # 基本特征 (8)
    'confidence', 'leverage', 'position_value', 'risk_reward_ratio',
    'order_blocks_count', 'liquidity_zones_count', 'entry_price', 'win_probability',
    
    # 技术指标 (10)
    'rsi', 'macd', 'macd_signal', 'macd_histogram', 'atr', 'bb_width',
    'volume_sma_ratio', 'ema50', 'ema200', 'volatility_24h',
    
    # 趋势特征 (6)
    'trend_1h', 'trend_15m', 'trend_5m', 'market_structure', 'direction', 'trend_alignment',
    
    # 其他特征 (14)
    'ema50_slope', 'ema200_slope', 'higher_highs', 'lower_lows',
    'support_strength', 'resistance_strength', 'fvg_count',
    'swing_high_distance', 'swing_low_distance', 'volume_profile',
    'price_momentum', 'order_flow', 'liquidity_grab', 'institutional_candle',
    
    # 竞价上下文特征 (3) - v3.17.10+
    'competition_rank', 'score_gap_to_best', 'num_competing_signals',
    
    # WebSocket专属特征 (3) - v3.17.2+
    'latency_zscore', 'shard_load', 'timestamp_consistency'
]
```

---

## 🔍 特征工程增强建议

### 已实现的特征

✅ **8个基本特征**: 完整实现  
✅ **10个技术指标**: 完整实现  
✅ **6个趋势特征**: 完整实现  
✅ **3个竞价特征**: 完整实现  
✅ **3个WebSocket特征**: 完整实现

### 可优化的特征（14个）

⚠️ **其他特征（14个）**: 目前使用默认值，可补充以下计算逻辑：

1. **EMA斜率**（`ema50_slope`, `ema200_slope`）:
   ```python
   ema50_slope = (ema50[-1] - ema50[-5]) / 5  # 5根K线斜率
   ```

2. **摆动高低点**（`higher_highs`, `lower_lows`）:
   ```python
   higher_highs = count_higher_highs(df, lookback=20)
   lower_lows = count_lower_lows(df, lookback=20)
   ```

3. **支撑/阻力强度**（`support_strength`, `resistance_strength`）:
   ```python
   support_strength = calculate_support_strength(price, support_level)
   resistance_strength = calculate_resistance_strength(price, resistance_level)
   ```

4. **FVG计数**（`fvg_count`）:
   ```python
   fvg_count = detect_fair_value_gaps(df, lookback=50)
   ```

5. **成交量分布**（`volume_profile`）:
   ```python
   volume_profile = calculate_volume_profile(df, current_price)
   ```

6. **价格动量**（`price_momentum`）:
   ```python
   price_momentum = (close[-1] - close[-14]) / close[-14]
   ```

7. **订单流**（`order_flow`）:
   ```python
   order_flow = (buy_volume - sell_volume) / total_volume
   ```

8. **流动性抓取/机构K线**（`liquidity_grab`, `institutional_candle`）:
   ```python
   liquidity_grab = 1 if detect_liquidity_grab(df) else 0
   institutional_candle = 1 if is_institutional_candle(candle) else 0
   ```

---

## 🧮 特征归一化

**模型输入要求**: 所有特征需要归一化至相似范围，避免某些特征主导训练。

**XGBoost内置处理**:
- XGBoost对特征缩放不敏感（树模型优势）
- 但建议对异常值进行裁剪（如`leverage`限制在1-50范围）

**可选归一化方法**:
```python
# MinMax归一化（0-1范围）
normalized = (value - min_value) / (max_value - min_value)

# Z-score归一化（均值0，标准差1）
normalized = (value - mean) / std
```

---

## 📊 特征重要性分析

**XGBoost自动计算特征重要性**，可通过以下代码查看：

```python
import xgboost as xgb

# 加载模型
model = xgb.Booster()
model.load_model('models/xgboost_model.json')

# 获取特征重要性
importance = model.get_score(importance_type='gain')

# 按重要性排序
sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)

for feature, score in sorted_importance[:10]:
    print(f"{feature}: {score:.2f}")
```

**预期高重要性特征**:
1. `win_probability` - 预估胜率（直接影响结果）
2. `confidence` - 信心度（核心评分指标）
3. `trend_alignment` - 趋势对齐度（多时间框架一致性）
4. `risk_reward_ratio` - R:R比率（风险控制）
5. `competition_rank` - 竞价排名（相对优势）

---

## 🎓 训练数据来源

**文件**: `training_data.jsonl`

**每笔交易记录的字段**:
```json
{
  "symbol": "BTCUSDT",
  "direction": "LONG",
  "entry_price": 67000.0,
  "stop_loss": 66500.0,
  "take_profit": 68000.0,
  
  // 44个特征（用于训练）
  "confidence": 0.75,
  "leverage": 5.2,
  "win_probability": 0.68,
  ...
  
  // 标签（训练目标）
  "outcome": 1,  // 1=盈利，0=亏损
  "pnl": 150.23,
  "roi": 0.015
}
```

**训练流程**:
1. 收集100笔交易数据（豁免期结束后）
2. 提取44个特征 + 标签（`outcome`）
3. 训练XGBoost模型
4. 保存模型至`models/xgboost_model.json`

---

## ✅ 总结

**特征总数**: **44个**  
**分类**:
- 基本特征: 8个
- 技术指标: 10个
- 趋势特征: 6个
- 其他特征: 14个（可优化）
- 竞价特征: 3个
- WebSocket特征: 3个

**模型**: XGBoost（梯度提升树）  
**预测目标**: 交易胜率（0-1）  
**训练数据**: `training_data.jsonl`（每笔交易的44个特征 + 结果标签）

**下一步优化**:
1. 补充14个"其他特征"的计算逻辑
2. 分析特征重要性，剔除低贡献特征
3. 收集更多训练数据（目标：1000+笔交易）
