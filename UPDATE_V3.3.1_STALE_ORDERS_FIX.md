# v3.3.1 - 修复止损止盈僵尸订单问题

## 📋 更新日期
2025-10-26

## 🎯 问题描述

### 用户反馈
**问题**：仓位关闭后，止损/止盈订单仍然留在订单簿中成为"僵尸订单"

**影响**：
- 未成交的止损/止盈订单积累在订单簿中
- 可能意外触发（如果价格再次波动到该区域）
- 增加系统混乱度，影响后续交易

**根本原因**：
```python
# 平仓时只关闭持仓，没有清理相关的止损止盈订单
del self.active_orders[symbol]  # ❌ 订单仍在交易所订单簿中
```

---

## ✅ 修复内容

### 1. 添加BinanceClient.get_open_orders()方法

**新增API方法**：
```python
async def get_open_orders(self, symbol: Optional[str] = None) -> list:
    """
    获取所有未成交订单
    
    Args:
        symbol: 交易对（可选）
    
    Returns:
        未成交订单列表
    """
    params = {}
    if symbol:
        params["symbol"] = symbol
    return await self._request("GET", "/fapi/v1/openOrders", params=params, signed=True)
```

**支持**：
- 获取特定symbol的未成交订单
- 获取所有symbol的未成交订单（symbol=None）

---

### 2. 添加_cancel_all_open_orders()清理方法

**新增私有方法**（在TradingService中）：
```python
async def _cancel_all_open_orders(self, symbol: str) -> int:
    """
    取消指定交易对的所有未成交订单（止损止盈等）
    
    Returns:
        int: 取消的订单数量
    """
    try:
        # 获取所有未成交订单
        open_orders = await self.client.get_open_orders(symbol)
        
        if not open_orders:
            return 0
        
        cancelled_count = 0
        for order in open_orders:
            try:
                await self.client.cancel_order(
                    symbol=symbol,
                    order_id=order['orderId']
                )
                cancelled_count += 1
                logger.debug(f"已取消订单: {order['orderId']} ({order.get('type', 'UNKNOWN')})")
            except Exception as e:
                logger.warning(f"取消订单失败 {order['orderId']}: {e}")
        
        return cancelled_count
        
    except Exception as e:
        logger.error(f"获取未成交订单失败: {e}")
        return 0
```

**功能**：
- 获取特定symbol的所有未成交订单
- 逐个取消这些订单
- 返回成功取消的订单数量
- 错误容忍：单个订单失败不影响其他订单

---

### 3. 在close_position()中集成清理逻辑

**修改后的close_position()**：
```python
async def close_position(self, symbol: str, reason: str = "manual"):
    """平仓"""
    try:
        # ... 执行平仓 ...
        
        self.risk_manager.update_trade_result(close_result)
        
        # 记录平仓到TradeRecorder
        if self.trade_recorder:
            self.trade_recorder.record_exit(close_result)
        
        # ✅ 清理止损止盈订单（避免僵尸订单）
        try:
            cancelled_count = await self._cancel_all_open_orders(symbol)
            if cancelled_count > 0:
                logger.info(f"🧹 已清理 {cancelled_count} 个止损止盈订单: {symbol}")
        except Exception as e:
            logger.warning(f"清理订单失败: {e}")
        
        del self.active_orders[symbol]
        
        logger.info(f"✅ 平仓成功: {symbol} PnL: {pnl:+.2f} ({pnl_pct:+.2%}) 原因: {reason}")
        
        return close_result
```

**执行顺序**：
1. 平仓持仓（市价单）
2. 更新风险管理器
3. 记录到TradeRecorder
4. **清理所有未成交订单** ✨
5. 从active_orders中删除
6. 记录日志

---

## 🔄 工作流程

### 手动平仓流程

```
用户调用close_position(symbol)
    ↓
执行市价平仓单
    ↓
记录PnL到TradeRecorder
    ↓
清理所有未成交订单 ← ✨ 新增步骤
    ├─ 取消止损订单
    ├─ 取消止盈订单
    └─ 取消其他挂单
    ↓
从active_orders中删除
    ↓
完成
```

### 自动止损/止盈触发流程

```
Binance自动触发止损/止盈
    ↓
持仓自动关闭
    ↓
❌ 问题：剩余的止盈/止损订单未清理
    ↓
⚠️ 已知限制：需要v3.3.2添加自动检测
```

---

## 📊 日志示例

### 成功清理

```bash
✅ 平仓成功: BTCUSDT PnL: +45.23 (+1.2%) 原因: manual
🧹 已清理 2 个止损止盈订单: BTCUSDT
```

### 无订单需要清理

```bash
✅ 平仓成功: ETHUSDT PnL: -12.50 (-0.8%) 原因: stop_loss
# 没有"已清理"日志 = 订单已被自动触发
```

### 清理失败（容错）

```bash
✅ 平仓成功: SOLUSDT PnL: +8.90 (+0.5%) 原因: manual
⚠️ 清理订单失败: Connection timeout
# 继续执行，不影响平仓成功
```

---

## 🧪 测试场景

### 场景1：手动平仓
```python
# 开仓 → 设置止损止盈 → 手动平仓
await trading_service.execute_signal(signal)  # 创建2个订单：止损+止盈
await trading_service.close_position("BTCUSDT", reason="manual")
# ✅ 验证：2个订单被取消
```

### 场景2：PositionMonitor调用平仓
```python
# 追踪止损调整后平仓
await position_monitor.monitor_all_positions()  # 可能调用close_position
# ✅ 验证：旧订单被清理
```

### 场景3：自动止损触发
```
Binance自动触发止损
    ↓
止损订单成交，持仓关闭
    ↓
❌ 剩余止盈订单未清理（已知限制）
    ↓
计划：v3.3.2添加自动检测
```

---

## 📁 修改文件

### 新增/修改
- ✅ `src/clients/binance_client.py`
  - 新增 `get_open_orders()` 方法
  - 修复类型注解 `Optional[str]`

- ✅ `src/services/trading_service.py`
  - 新增 `_cancel_all_open_orders()` 方法
  - 修改 `close_position()` 集成清理逻辑

- ✅ `UPDATE_V3.3.1_STALE_ORDERS_FIX.md`
  - 本文档

---

## ⚠️ 已知限制

### 自动止损/止盈触发时的订单清理

**当前版本**：
- ✅ 手动平仓 → 清理所有订单
- ❌ 自动止损触发 → 剩余订单未清理
- ❌ 自动止盈触发 → 剩余订单未清理

**原因**：
- Binance自动平仓没有回调机制
- 系统不知道持仓已被自动关闭
- 需要主动检测持仓变化

**计划**（v3.3.2）：
1. 在每次监控循环中检测持仓变化
2. 对比`active_orders` vs 实际持仓
3. 发现不一致时清理订单
4. 同时记录自动平仓到TradeRecorder

**临时解决方案**：
- 定期运行清理脚本
- 手动检查订单簿
- Railway定时任务清理僵尸订单

---

## 🚀 部署指令

```bash
# 1. 提交代码
git add .
git commit -m "v3.3.1 - Fix stale SL/TP orders cleanup"

# 2. 推送到Railway
git push origin main

# 3. 监控日志
railway logs --tail 100 | grep "清理"
```

---

## ✅ 验证清单

部署后验证：

```bash
# 1. 验证订单清理
railway logs | grep "🧹 已清理"

# 2. 检查未成交订单数量
# 应该保持在低水平（每个symbol最多2个）

# 3. 验证平仓流程完整性
railway logs | grep "平仓成功"

# 4. 检查错误日志
railway logs | grep "清理订单失败" | tail -20
```

---

## 🔮 后续优化（v3.3.2）

### 计划功能

1. **自动检测平仓**
   ```python
   async def detect_auto_closed_positions():
       """检测自动平仓的持仓"""
       for symbol in active_orders.keys():
           if not has_position(symbol):
               # 清理订单
               await _cancel_all_open_orders(symbol)
               # 记录到TradeRecorder
               await record_auto_close(symbol)
   ```

2. **定期清理任务**
   ```python
   # 每小时清理一次僵尸订单
   @schedule.every(1).hour
   async def cleanup_stale_orders():
       """清理所有无持仓的订单"""
       pass
   ```

3. **订单对账机制**
   ```python
   async def reconcile_orders():
       """对账：订单簿 vs active_orders"""
       pass
   ```

---

## 📝 总结

### 本次修复解决了

✅ 手动平仓时止损止盈订单未清理的问题
✅ 避免订单簿中积累僵尸订单
✅ 提高系统整洁度和可维护性

### 仍需后续优化

⚠️ 自动止损/止盈触发后的订单清理
⚠️ 定期对账和清理机制
⚠️ 僵尸订单监控和告警

---

**版本**: v3.3.1  
**状态**: ✅ 已完成  
**下一步**: 部署到Railway并监控日志
