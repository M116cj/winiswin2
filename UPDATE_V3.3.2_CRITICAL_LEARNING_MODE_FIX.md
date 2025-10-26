# v3.3.2 - 修复学习模式0/30问题和PnL异常

## 📋 更新日期
2025-10-26

## 🎯 问题描述

### 用户报告的两个关键问题

#### 问题1：收益率-225%异常
**现象**：
- 用户看到收益率显示为-225%
- 理论上不应该亏损超过100%

**根本原因**：
```python
# 之前的代码没有限制收益率下限
pnl_pct = pnl / trade['margin']
# 如果使用高杠杆，pnl可能远超margin
# 例如：20x杠杆，价格跌50% → 亏损1000% margin → -1000%
```

**问题分析**：
- 使用杠杆交易时，PnL可以超过保证金
- 但收益率应该限制在-100%（最多亏光保证金）
- 没有对PnL百分比设置下限

---

#### 问题2：学习模式永远0/30
**现象**：
```
🎓 学习模式 (0/30)：跳过期望值检查
🎓 学习模式 (0/30)：跳过期望值检查  # 永远不增长
```

**根本原因**：
1. **TRADING_ENABLED = false**（发现）
2. **模拟交易不记录数据**：
   ```python
   if not self.config.TRADING_ENABLED:
       return self._create_simulated_trade(...)
       # ❌ 没有调用 trade_recorder.record_entry()
   ```
3. **ml_data/trades.jsonl 为空**（0字节）
4. **get_all_completed_trades() 返回空列表**

**影响**：
- 即使生成了交易信号，系统也不记录
- 学习模式永远无法启动
- ExpectancyCalculator无法计算期望值
- 系统无法优化交易策略

---

## ✅ 修复内容

### 修复1：限制PnL收益率在-100%以内

**修改文件**：`src/services/trading_service.py`

**修改位置**：`close_position()` 方法

```python
# 計算收益率（相對於保證金）
pnl_pct = pnl / trade['margin']

# ⚠️ 限制收益率最低為-100%（不能虧損超過本金）
# 修復：避免出現-225%等異常收益率
if pnl_pct < -1.0:
    logger.warning(
        f"⚠️ 檢測到異常收益率 {pnl_pct:.2%}，限制為-100%。"
        f"PnL: {pnl:.2f}, Margin: {trade['margin']:.2f}"
    )
    pnl_pct = -1.0
```

**效果**：
- 收益率最低限制为-100%
- 记录警告日志，便于发现异常情况
- 保护数据完整性

---

### 修复2：模拟交易也记录到TradeRecorder

**问题**：TRADING_ENABLED=false时，系统创建模拟交易但不记录

**解决方案**：

#### 2.1 模拟开仓记录

**修改位置**：`execute_signal()` 方法

```python
if not self.config.TRADING_ENABLED:
    logger.warning("🎮 交易功能未啟用，創建模擬交易（用於學習模式）")
    simulated_trade = self._create_simulated_trade(
        signal, position_info, quantity
    )
    
    # 添加到active_orders以便追踪
    self.active_orders[symbol] = simulated_trade
    
    # ✨ 記錄模擬開倉到TradeRecorder（修復學習模式0/30問題）
    if self.trade_recorder:
        try:
            self.trade_recorder.record_entry(signal, simulated_trade)
            logger.info(f"📝 已記錄模擬開倉: {symbol} (學習模式)")
        except Exception as e:
            logger.error(f"記錄模擬開倉失敗: {e}")
    
    return simulated_trade
```

#### 2.2 真實开仓也记录

```python
# 真實交易成功後記錄
self.active_orders[symbol] = trade_result

# 記錄開倉到TradeRecorder（用於學習模式）
if self.trade_recorder:
    try:
        self.trade_recorder.record_entry(signal, trade_result)
        logger.debug(f"📝 已記錄開倉到TradeRecorder: {symbol}")
    except Exception as e:
        logger.error(f"記錄開倉失敗: {e}")
```

---

### 修复3：添加模拟平仓机制

**问题**：模拟交易开仓后，从未平仓，无法记录完整交易

**解决方案**：

#### 3.1 close_position支持模拟平仓

```python
# 模擬交易模式：使用市場價格模擬平倉
if trade.get('simulated', False) or not self.config.TRADING_ENABLED:
    logger.info(f"🎮 模擬平倉: {symbol} (原因: {reason})")
    # 獲取當前市場價格
    try:
        ticker = await self.client.get_ticker_price(symbol)
        exit_price = float(ticker['price'])
    except Exception as e:
        logger.error(f"獲取市場價格失敗: {e}，使用入場價")
        exit_price = trade['entry_price']
else:
    # 真實交易：執行市價平倉
    order = await self._place_market_order(...)
    exit_price = float(order.get('avgPrice', 0))
```

#### 3.2 自动触发模拟平仓

**新增方法**：`check_simulated_positions_for_close()`

```python
async def check_simulated_positions_for_close(self) -> int:
    """
    檢查模擬持倉並自動平倉（達到止損/止盈時）
    
    Returns:
        int: 平倉數量
    """
    closed_count = 0
    
    for symbol in list(self.active_orders.keys()):
        trade = self.active_orders[symbol]
        
        # 只處理模擬交易
        if not trade.get('simulated', False):
            continue
        
        # 獲取當前市場價
        ticker = await self.client.get_ticker_price(symbol)
        current_price = float(ticker['price'])
        
        # 檢查止損/止盈
        if trade['direction'] == "LONG":
            if current_price <= trade['stop_loss']:
                await self.close_position(symbol, reason="simulated_stop_loss")
                closed_count += 1
            elif current_price >= trade['take_profit']:
                await self.close_position(symbol, reason="simulated_take_profit")
                closed_count += 1
        else:  # SHORT
            if current_price >= trade['stop_loss']:
                await self.close_position(symbol, reason="simulated_stop_loss")
                closed_count += 1
            elif current_price <= trade['take_profit']:
                await self.close_position(symbol, reason="simulated_take_profit")
                closed_count += 1
    
    return closed_count
```

#### 3.3 主循环调用

**修改文件**：`src/main.py`

**修改位置**：`_update_positions()` 方法

```python
async def _update_positions(self):
    """更新所有持倉"""
    ...
    
    # ✨ 檢查模擬持倉並自動平倉（修復學習模式）
    if not Config.TRADING_ENABLED:
        closed_count = await self.trading_service.check_simulated_positions_for_close()
        if closed_count > 0:
            logger.info(f"🎮 本週期模擬平倉: {closed_count} 筆")
```

---

## 🔄 完整工作流程

### 模拟交易模式（TRADING_ENABLED=false）

```
信号生成
    ↓
execute_signal()
    ↓
创建模拟交易
    ↓
✨ trade_recorder.record_entry()  ← 新增
    ↓
添加到active_orders
    ↓
主循环每60秒检查
    ↓
check_simulated_positions_for_close()
    ↓
检测到止损/止盈触发
    ↓
close_position(reason="simulated_xxx")
    ↓
获取当前市场价格
    ↓
计算PnL（限制≥-100%）
    ↓
✨ trade_recorder.record_exit()  ← 已有
    ↓
完成的交易保存到ml_data/trades.jsonl
    ↓
🎓 学习模式计数增加: 0/30 → 1/30 → ...
```

---

## 📊 预期效果

### 修复前

```bash
# 日志
🎮 交易功能未启用，跳过实际下单
# ❌ 没有记录到TradeRecorder

# 数据
ml_data/trades.jsonl: 0字节
学习模式: 0/30（永远不变）

# 问题
收益率: -225% ⚠️
```

### 修复后

```bash
# 日志
🎮 交易功能未啟用，創建模擬交易（用於學習模式）
📝 已記錄模擬開倉: BTCUSDT (學習模式)
...
✅ 模擬平倉觸發: BTCUSDT @ 94523.50 (simulated_stop_loss)
✅ 平倉成功: BTCUSDT PnL: -15.23 (-3.5%) 原因: simulated_stop_loss
📝 已記錄平倉到TradeRecorder: BTCUSDT
🎮 本週期模擬平倉: 1 筆

# 数据
ml_data/trades.jsonl: 有数据
学习模式: 1/30 → 2/30 → ... → 30/30（正常增长）

# 修复
收益率: 最低-100%（限制生效）
⚠️ 檢測到異常收益率-225%，限制為-100%
```

---

## 📁 修改文件

### 核心修改
- ✅ `src/services/trading_service.py`
  - `execute_signal()` - 模拟开仓记录
  - `close_position()` - PnL限制 + 模拟平仓
  - `check_simulated_positions_for_close()` - 新增方法

- ✅ `src/main.py`
  - `_process_signal()` - 移除重复record_entry
  - `_update_positions()` - 调用模拟平仓检查

- ✅ `UPDATE_V3.3.2_CRITICAL_LEARNING_MODE_FIX.md`
  - 本文档

---

## 🧪 测试验证

### 本地测试

```bash
# 1. 确保TRADING_ENABLED=false
export TRADING_ENABLED=false

# 2. 运行系统
python -m src.main

# 3. 观察日志
grep "模擬開倉\|模擬平倉\|學習模式" logs.txt

# 4. 检查数据文件
cat ml_data/trades.jsonl | wc -l  # 应该>0

# 5. 验证学习模式计数
grep "學習模式" logs.txt | tail -10
# 应该看到: 0/30 → 1/30 → 2/30 ...
```

### Railway部署后验证

```bash
# 1. 检查模拟交易记录
railway logs | grep "📝 已記錄模擬"

# 2. 检查模拟平仓
railway logs | grep "🎮 模擬平倉"

# 3. 验证学习模式进度
railway logs | grep "學習模式" | tail -20

# 4. 检查PnL限制
railway logs | grep "異常收益率"

# 5. 验证数据文件
# （需要在Railway控制台或通过API检查）
```

---

## ⚠️ 重要说明

### TRADING_ENABLED配置

**开发/测试环境**：
```bash
# Railway环境变量
TRADING_ENABLED=false  # 使用模拟交易，累积学习数据
```

**生产环境**（达到30笔交易后）：
```bash
TRADING_ENABLED=true   # 启用真实交易
```

### 学习模式阶段

**阶段1：冷启动（0-30笔）**
```
🎓 学习模式 (X/30)：跳过期望值检查，收集初始交易数据
```
- 接受所有通过基本过滤的信号
- 记录完整的交易数据
- 累积ML训练数据

**阶段2：优化运行（>30笔）**
```
📈 期望值检查通过 - 期望值: 2.5%, 盈亏比: 1.8
```
- 使用历史数据计算期望值
- 只接受正期望值的交易
- 动态调整杠杆

---

## 🔮 后续优化

### 计划功能（v3.3.3）

1. **模拟交易时间加速**
   - 当前：每60秒检查一次
   - 优化：检测到模拟持仓时，每10秒检查

2. **模拟交易强制平仓**
   - 持仓超过1小时自动平仓
   - 避免模拟持仓长期占用

3. **学习模式进度可视化**
   - Discord通知学习进度
   - "🎓 学习模式进度: 15/30 (50%)"

---

## 📝 总结

### 本次修复解决了

✅ **问题1**：收益率异常（-225%）
- 限制PnL最低为-100%
- 记录异常情况的警告日志

✅ **问题2**：学习模式永远0/30
- 模拟交易开仓时记录数据
- 模拟交易自动触发平仓
- 完整的交易数据保存到ml_data/trades.jsonl
- 学习模式计数正常增长

### 核心改进

1. **数据完整性** - 所有交易（真实+模拟）都被记录
2. **学习加速** - 即使TRADING_ENABLED=false也能累积数据
3. **异常保护** - PnL计算更加健壮
4. **可观测性** - 清晰的日志追踪模拟交易

---

**版本**: v3.3.2  
**状态**: ✅ 已完成  
**下一步**: 部署到Railway并验证学习模式计数增长
