# V3.0 系统升级摘要

## 🎯 升级目标
根据新的交易决策框架，全面升级评分系统、期望值驱动的槓桿调整、数据归档系统

## ✅ 已完成的核心模块

### 1. XGBoost 数据归档系统 (`src/ml/data_archiver.py`)
**功能**：
- 记录所有交易信号特征（包括被拒绝的信号）
- 记录实际仓位的完整生命周期
- 记录虚拟仓位的完整生命周期
- 支持增量写入和批量刷新到 CSV 文件
- 提供训练数据集生成接口

**使用方法**：
```python
from src.ml.data_archiver import DataArchiver

archiver = DataArchiver(data_dir="ml_data")

archiver.archive_signal(signal_data, accepted=True)

archiver.archive_position_open(position_data, is_virtual=False)

archiver.archive_position_close(position_data, close_data, is_virtual=False)

training_data = archiver.get_training_data(min_samples=100)
```

### 2. 期望值计算模块 (`src/managers/expectancy_calculator.py`)
**功能**：
- 基于最近 30 笔交易滚动计算期望值、盈亏比、胜率
- 根据期望值和盈亏比动态确定杠杆范围
- 检测连续亏损并触发熔断机制
- 计算日亏损并触发风控

**核心算法**：
```
期望值 (Expectancy) = (Win Rate × Avg Win) - ((1 - Win Rate) × Avg Loss)
盈亏比 (Profit Factor) = Total Wins / Total Losses
```

**杠杆映射**：
- Expectancy > 1.5% 且 Profit Factor > 1.5 → 15-20x
- Expectancy > 0.8% 且 Profit Factor > 1.0 → 10-15x
- Expectancy > 0.3% 且 Profit Factor > 0.8 → 5-10x
- Expectancy ≤ 0.3% 或 Profit Factor < 0.8 → 3-5x
- Expectancy < 0 → 0x (禁止开仓)

**熔断机制**：
- 连续 3 笔亏损 → 槓桿降至 3x + 24 小时冷却期
- 连续 5 笔亏损 → 强制停止交易，需要策略回测
- 日亏损 >= 3% → 禁止开仓

### 3. 严格的 Order Block 检测 (`src/utils/indicators.py`)
**新定义**：
- 看涨 OB：实体 ≥ 70% 全长的阳K，区间 = [Low, Open]
- 看跌 OB：实体 ≥ 70% 全长的阴K，区间 = [High, Open]
- 需要后续 3 根 K 线确认方向延续（至少 2/3 根确认）

**输出格式**：
```python
{
    'type': 'bullish' or 'bearish',
    'price': float,  # 中心价格
    'zone_low': float,  # OB区间下限
    'zone_high': float,  # OB区间上限
    'timestamp': datetime,
    'body_pct': float,  # 实体占比
    'confirmed': True
}
```

### 4. 升级的信心度评分系统 (`src/strategies/ict_strategy.py`)

**新的五大子指标**：

#### 1. 趋势对齐 (40%)
基于多时间框架 EMA：
- 5m: 价格 > EMA20 → +33.3%
- 15m: 价格 > EMA50 → +33.3%
- 1h: 价格 > EMA100 → +33.3%

#### 2. 市场结构 (20%)
基于分形高低点：
- 看涨结构 + 1h 看涨趋势 → 100%
- 看跌结构 + 1h 看跌趋势 → 100%
- 中性结构或矛盾 → 50%

#### 3. 价格位置 (20%)
基于距离 Order Block 的 ATR 距离：
- distance = |Price - OB| / ATR
- ≤ 0.5 ATR → 100%
- ≤ 1.0 ATR → 80%
- ≤ 1.5 ATR → 60%
- ≤ 2.0 ATR → 40%
- > 2.0 ATR → 20%
- 突破 OB 区域 → 30%

#### 4. 动量指标 (10%)
RSI + MACD 组合：
- 两者同向支持交易方向 → 100%
- 仅一项支持 → 60%
- 背离或反向 → 0%

#### 5. 波动率适宜度 (10%)
基于布林带宽的 7 天分位数：
- 当前宽度在 [25%, 75%] 分位数之间 → 100%
- 当前宽度 < 25% 分位数 → 60% (波动过低)
- 当前宽度 > 75% 分位数 → 40% (波动过高)

**输出**：
```python
confidence_score, sub_scores = self._calculate_confidence(...)

sub_scores = {
    'trend_alignment': 0.67,  # 2/3 对齐
    'market_structure': 1.0,  # 完美对齐
    'price_position': 0.8,    # 距离 OB 1.0 ATR
    'momentum': 0.6,          # 一项支持
    'volatility': 1.0         # 理想波动
}

confidence_score = 0.67*0.4 + 1.0*0.2 + 0.8*0.2 + 0.6*0.1 + 1.0*0.1
                 = 0.268 + 0.2 + 0.16 + 0.06 + 0.1
                 = 0.788 (78.8%)
```

## 🔧 需要集成的部分

### 集成到主流程 (`src/main.py`)

```python
from src.ml.data_archiver import DataArchiver
from src.managers.expectancy_calculator import ExpectancyCalculator

archiver = DataArchiver()
expectancy_calc = ExpectancyCalculator(window_size=30)

while running:
    for signal in signals:
        expectancy_metrics = expectancy_calc.calculate_expectancy(all_trades)
        
        can_trade, reason = expectancy_calc.should_trade(
            expectancy=expectancy_metrics['expectancy'],
            profit_factor=expectancy_metrics['profit_factor'],
            consecutive_losses=expectancy_metrics['consecutive_losses'],
            daily_loss_pct=expectancy_calc.get_daily_loss(all_trades)
        )
        
        if not can_trade:
            logger.warning(f"拒绝开仓: {reason}")
            archiver.archive_signal(signal, accepted=False, rejection_reason=reason)
            continue
        
        min_lev, max_lev = expectancy_calc.determine_leverage(
            expectancy=expectancy_metrics['expectancy'],
            profit_factor=expectancy_metrics['profit_factor'],
            consecutive_losses=expectancy_metrics['consecutive_losses']
        )
        
        leverage = (min_lev + max_lev) / 2
        
        archiver.archive_signal(signal, accepted=True)
        
        position = execute_trade(signal, leverage)
        archiver.archive_position_open(position, is_virtual=False)
    
    for closed_position in check_closed_positions():
        archiver.archive_position_close(
            closed_position,
            close_data={'pnl': pnl, 'pnl_pct': pnl_pct, 'close_price': price},
            is_virtual=False
        )
    
    archiver.flush_all()
```

### 资金管理硬规则实现

在 `src/managers/risk_manager.py` 中添加：

```python
def calculate_position_size_with_hard_rules(
    self,
    account_balance: float,
    entry_price: float,
    stop_loss: float,
    leverage: float,
    max_risk_pct: float = 0.01  # 单笔风险 ≤ 1%
) -> Dict:
    """
    计算符合硬规则的仓位大小
    
    硬规则：
    1. 单笔风险 ≤ 总资金 1%
    2. 倉位 = (1% × 帳戶餘額) / (止損距離% × 槓桿)
    """
    stop_loss_pct = abs(entry_price - stop_loss) / entry_price
    
    max_position_value = (max_risk_pct * account_balance) / (stop_loss_pct * leverage)
    
    max_position_value = min(max_position_value, account_balance * 0.95)
    
    position_margin = max_position_value / leverage
    
    quantity = max_position_value / entry_price
    
    return {
        'quantity': quantity,
        'position_value': max_position_value,
        'position_margin': position_margin,
        'leverage': leverage,
        'risk_amount': account_balance * max_risk_pct,
        'risk_pct': max_risk_pct
    }
```

## 📊 数据归档文件格式

### signals.csv
```
timestamp,symbol,direction,confidence,accepted,rejection_reason,
trend_alignment_score,market_structure_score,price_position_score,momentum_score,volatility_score,
h1_trend,m15_trend,m5_trend,current_price,entry_price,stop_loss,take_profit,
rsi,macd,macd_signal,atr,bb_width_pct,order_blocks_count,liquidity_zones_count
```

### positions.csv
```
event,timestamp,position_id,is_virtual,symbol,direction,
entry_price,exit_price,stop_loss,take_profit,quantity,leverage,confidence,
pnl,pnl_pct,close_reason,won,
trend_alignment_score,market_structure_score,price_position_score,momentum_score,volatility_score,
rsi,macd,atr,bb_width_pct,holding_duration_minutes
```

## 🎯 信心度门槛建议

根据新的评分系统，建议调整门槛：
- **当前**: 55% (0.55)
- **建议**: 保持 55% 或降至 50%，观察实际效果

## 📈 预期效果

1. **数据归档**：
   - 所有信号和仓位数据完整记录
   - 支持 XGBoost 实时训练
   - 可追溯所有决策过程

2. **期望值驱动**：
   - 更科学的杠杆调整
   - 有效的风险控制
   - 自动熔断机制

3. **严格 OB 检测**：
   - 减少虚假 OB
   - 提高入场点质量
   - 更准确的价格位置评分

4. **优化评分系统**：
   - 更合理的权重分配
   - 基于 EMA 的趋势判断
   - 基于 ATR 的距离评分
   - 动态波动率适应

## 🚀 下一步行动

1. 在 `src/main.py` 中集成所有模块
2. 测试完整流程
3. 修复剩余 LSP 错误
4. 部署到 Railway
5. 观察实际运行效果并调优
