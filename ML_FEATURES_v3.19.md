# ML Features Documentation v3.19

**版本**: v3.19  
**特征总数**: 56个（v3.18.10: 44个 → v3.19: 56个）  
**更新日期**: 2025-11-02

---

## 📊 特征总览

### **版本历史**

| 版本 | 特征数 | 新增内容 |
|------|--------|---------|
| v3.17.10 | 41个 | 初始版本 |
| v3.17.2 | 44个 | +3个WebSocket特征 |
| v3.18.10 | 44个 | ADX优化 |
| **v3.19** | **56个** | **+12个ICT/SMC高级特征** |

---

## 🔢 特征分类（56个）

### **1. 基本特征（8个）**

| # | 特征名 | 类型 | 范围 | 说明 |
|---|--------|------|------|------|
| 1 | `confidence` | float | 0-1 | 信号置信度 |
| 2 | `leverage` | float | 1-20 | 杠杆倍数 |
| 3 | `position_value` | float | ≥0 | 仓位价值（USDT） |
| 4 | `risk_reward_ratio` | float | ≥0 | 风险回报比 |
| 5 | `order_blocks_count_legacy` | int | ≥0 | 订单块数量（旧版） |
| 6 | `liquidity_zones_count` | int | ≥0 | 流动性区域数量 |
| 7 | `entry_price` | float | >0 | 入场价格 |
| 8 | `win_probability` | float | 0-1 | 获胜概率 |

---

### **2. 技术指标（10个）**

| # | 特征名 | 类型 | 范围 | 说明 |
|---|--------|------|------|------|
| 9 | `rsi` | float | 0-100 | 相对强弱指数 |
| 10 | `macd` | float | - | MACD值 |
| 11 | `macd_signal` | float | - | MACD信号线 |
| 12 | `macd_histogram` | float | - | MACD柱状图 |
| 13 | `atr` | float | ≥0 | 平均真实波幅 |
| 14 | `bb_width` | float | ≥0 | 布林带宽度 |
| 15 | `volume_sma_ratio` | float | ≥0 | 成交量/SMA比率 |
| 16 | `ema50` | float | >0 | 50周期EMA |
| 17 | `ema200` | float | >0 | 200周期EMA |
| 18 | `volatility_24h` | float | ≥0 | 24小时波动率 |

---

### **3. 趋势特征（6个）**

| # | 特征名 | 类型 | 范围 | 说明 |
|---|--------|------|------|------|
| 19 | `trend_1h` | int | -1,0,1 | 1小时趋势 |
| 20 | `trend_15m` | int | -1,0,1 | 15分钟趋势 |
| 21 | `trend_5m` | int | -1,0,1 | 5分钟趋势 |
| 22 | `market_structure_legacy` | int | -1,0,1 | 市场结构（旧版） |
| 23 | `direction` | int | -1,1 | 交易方向（LONG=1, SHORT=-1） |
| 24 | `trend_alignment` | float | 0-1 | 趋势对齐度 |

---

### **4. 其他技术特征（14个）**

| # | 特征名 | 类型 | 范围 | 说明 |
|---|--------|------|------|------|
| 25 | `ema50_slope` | float | - | EMA50斜率 |
| 26 | `ema200_slope` | float | - | EMA200斜率 |
| 27 | `higher_highs` | int | ≥0 | 更高的高点数量 |
| 28 | `lower_lows` | int | ≥0 | 更低的低点数量 |
| 29 | `support_strength` | float | 0-1 | 支撑强度 |
| 30 | `resistance_strength` | float | 0-1 | 阻力强度 |
| 31 | `fvg_count_legacy` | int | ≥0 | FVG数量（旧版） |
| 32 | `swing_high_distance_legacy` | float | - | 摆动高点距离（旧版） |
| 33 | `swing_low_distance` | float | - | 摆动低点距离 |
| 34 | `volume_profile` | float | 0-1 | 成交量分布 |
| 35 | `price_momentum` | float | - | 价格动量 |
| 36 | `order_flow_legacy` | float | -1,1 | 订单流（旧版） |
| 37 | `liquidity_grab_legacy` | int | 0,1 | 流动性抓取（旧版） |
| 38 | `institutional_candle_legacy` | int | 0,1 | 机构K线（旧版） |

---

### **5. 竞价上下文特征（3个）**

| # | 特征名 | 类型 | 范围 | 说明 |
|---|--------|------|------|------|
| 39 | `competition_rank` | int | ≥1 | 信号在竞价中的排名 |
| 40 | `score_gap_to_best` | float | ≥0 | 与最佳信号的分数差距 |
| 41 | `num_competing_signals` | int | ≥1 | 竞争信号总数 |

---

### **6. WebSocket专属特征（3个）**

| # | 特征名 | 类型 | 范围 | 说明 |
|---|--------|------|------|------|
| 42 | `latency_zscore` | float | - | 网络延迟Z值 |
| 43 | `shard_load` | float | 0-1 | WebSocket分片负载 |
| 44 | `timestamp_consistency` | int | 0,1 | 时间戳一致性 |

---

### **7. 🔥 ICT/SMC高级特征 - 基础特征（8个）**

| # | 特征名 | 类型 | 范围 | 说明 | 数据源 |
|---|--------|------|------|------|--------|
| 45 | `market_structure` | int | -1,0,1 | 市场结构（MSB/MSS）| 1h K线 |
| 46 | `order_blocks_count` | int | ≥0 | 已验证的订单块数量 | 15m K线 |
| 47 | `institutional_candle` | int | 0,1 | 机构K线识别 | 5m K线 + 成交量 |
| 48 | `liquidity_grab` | int | 0,1 | 流动性抓取检测 | 5m K线 + ATR |
| 49 | `order_flow` | float | -1,1 | 订单流（买卖压力） | 交易流 |
| 50 | `fvg_count` | int | ≥0 | 未回填的FVG数量 | 5m K线 |
| 51 | `trend_alignment_enhanced` | float | 0-1 | 多时间框架趋势对齐度 | 1h/15m/5m K线 |
| 52 | `swing_high_distance` | float | - | 到最近摆动高点的ATR标准化距离 | 15m K线 |

**特征详解**:

**45. market_structure（市场结构）**
- **计算**: 基于摆动高低点（Swing High/Low）的变化
  - `1`: 多头结构（Higher Highs & Higher Lows）
  - `-1`: 空头结构（Lower Highs & Lower Lows）
  - `0`: 中性结构
- **窗口**: 100根K线
- **识别**: 连续摆动点上移/下移判断

**46. order_blocks_count（订单块数量）**
- **定义**: 机构集中买入/卖出导致价格反转的区域
- **识别**:
  - 看涨订单块: 价格创新低 → 阴线 → 突破该阴线高点
  - 看跌订单块: 价格创新高 → 阳线 → 跌破该阳线低点
- **验证**: 价格回测并反转

**47. institutional_candle（机构K线）**
- **条件**:
  - 实体比率 > 0.7（实体主导）
  - 成交量Z值 > 2（异常放量）
  - 影线比率 < 0.3（影线短）
- **意义**: 反映大资金进场

**48. liquidity_grab（流动性抓取）**
- **识别**:
  - 价格突破摆动点 > 0.5 ATR
  - 下一根K线迅速反转
- **意义**: 机构触发止损后反向操作

**49. order_flow（订单流）**
- **公式**: `(主动买入量 - 主动卖出量) / 总量`
- **数据源**: Binance逐笔交易流（`btcusdt@trade`）
- **时间窗口**: 1分钟

**50. fvg_count（公允价值缺口）**
- **识别**:
  - 看涨FVG: K1最低价 > K3最高价
  - 看跌FVG: K1最高价 < K3最低价
- **统计**: 未回填的FVG数量

**51. trend_alignment_enhanced（趋势对齐度增强）**
- **计算**:
  - 三个时间框架趋势相同 → 1.0
  - 两个相同 → 0.5
  - 全部不同 → 0.0

**52. swing_high_distance（摆动高点距离）**
- **公式**: `(当前价格 - 摆动高点) / ATR`
- **标准化**: 使用ATR消除波动性影响

---

### **8. 🔥 ICT/SMC高级特征 - 合成特征（4个）**

| # | 特征名 | 类型 | 范围 | 说明 |
|---|--------|------|------|------|
| 53 | `structure_integrity` | float | 0-1 | 结构完整性 |
| 54 | `institutional_participation` | float | 0-1 | 机构参与度 |
| 55 | `timeframe_convergence` | float | 0-1 | 时间框架收敛度 |
| 56 | `liquidity_context` | float | 0-1 | 流动性情境 |

**特征详解**:

**53. structure_integrity（结构完整性）**
- **公式**: `0.4 × I(市场结构明确) + 0.3 × (1 - FVG惩罚) + 0.3 × tanh(订单块数/3)`
- **逻辑**: 趋势明确、FVG少、订单块多时得分高

**54. institutional_participation（机构参与度）**
- **公式**: `0.5 × 机构K线 + 0.3 × |订单流| + 0.2 × 流动性抓取`
- **意义**: 综合评估机构活跃度

**55. timeframe_convergence（时间框架收敛度）**
- **公式**: `1 - (std([trend_1h, trend_15m, trend_5m]) / 2)`
- **范围**: 0-1（越高表示多时间框架趋势越一致）

**56. liquidity_context（流动性情境）**
- **数据源**: Binance深度流（`btcusdt@depth`）
- **公式**: 
  ```
  深度得分 = 0.6 × tanh(订单簿深度/100) + 0.4 × (1 - min(1, 价差/0.001))
  流动性情境 = 0.7 × 深度得分 + 0.3 × 流动性抓取
  ```

---

## 📦 数据源需求

### **Binance WebSocket订阅**

1. **K线流**（多时间框架）:
   ```
   btcusdt@kline_1h
   btcusdt@kline_15m
   btcusdt@kline_5m
   ```

2. **交易流**（订单流特征）:
   ```
   btcusdt@trade
   ```

3. **深度流**（流动性特征）:
   ```
   btcusdt@depth
   ```

---

## 🎯 特征使用建议

### **高优先级特征（Top 10）**

基于ICT/SMC理论和机构交易行为：

1. `market_structure` - 市场趋势基础
2. `order_blocks_count` - 机构订单区域
3. `structure_integrity` - 结构质量
4. `institutional_participation` - 机构活跃度
5. `order_flow` - 实时买卖压力
6. `liquidity_grab` - 机构陷阱识别
7. `trend_alignment_enhanced` - 多时间框架确认
8. `fvg_count` - 价格缺口
9. `timeframe_convergence` - 趋势收敛
10. `rsi` - 经典超买超卖

---

## ⚠️ 注意事项

### **1. 向后兼容**
- 系统支持44特征和56特征模型
- 44特征模型自动补齐12个默认值

### **2. 数据质量**
- 确保WebSocket连接稳定
- 交易流和深度流实时性要求高
- K线数据需要足够历史记录（≥100根）

### **3. 计算性能**
- 摆动点识别需要O(n)遍历
- 订单块和FVG检测需要窗口滑动
- 建议使用缓存优化重复计算

---

## 📈 模型训练建议

### **特征工程**

1. **标准化**:
   - 所有连续特征使用ATR或Z-score标准化
   - 确保跨资产可比性

2. **特征选择**:
   - 使用XGBoost特征重要性分析
   - 剔除低贡献特征（重要性<1%）

3. **回测验证**:
   - 历史K线数据验证准确性
   - 特征与交易绩效相关性分析

---

## 🚀 下一步

- [ ] 实施WebSocket数据流集成
- [ ] 历史数据回测验证特征有效性
- [ ] 使用56特征重训练XGBoost模型
- [ ] 特征重要性分析
- [ ] 生产环境部署

---

**版本**: v3.19  
**更新日期**: 2025-11-02  
**作者**: SelfLearningTrader Team
