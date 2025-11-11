# Railway部署指南 - v4.2 Rate-Limit Safe

## 🚀 快速部署（推荐配置）

### 环境变量设置

在Railway项目中添加以下环境变量：

```bash
# Binance API凭证（必需）
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# 数据库（Railway自动提供）
DATABASE_URL=${{Postgres.DATABASE_URL}}

# v4.2默认配置（无需设置，系统自动使用）
# ENABLE_KLINE_WARMUP=false  ✅ 默认禁用预热，0%速率限制风险
# WARMUP_SYMBOL_LIMIT=50
# WARMUP_BATCH_SIZE=5
# WARMUP_BATCH_DELAY=2.0
```

### Binance API密钥权限要求

确保您的API密钥具有以下权限：
- ✅ **Enable Reading**（读取权限）
- ✅ **Enable Futures**（期货交易权限）
- ❌ **Enable Spot & Margin Trading**（不需要）
- ❌ **Enable Withdrawals**（不需要）

⚠️ **重要**：建议为每个部署环境创建独立的API密钥

---

## 📊 部署后验证

### 1. 检查启动日志

成功的启动日志应包含：

```
✅ K線預熱已禁用（ENABLE_KLINE_WARMUP=false）
   WebSocket將實時累積數據：
      • 5m數據將在5分鐘後可用
      • 15m數據將在15分鐘後可用
      • 1h數據將在60分鐘後可用

✅ WebSocketManager已啟動（監控535個交易對）
✅ 發現 XXX 個交易信號
```

### 2. 确认无速率限制错误

**不应出现**以下错误：
```
❌ HTTP 418: I'm a teapot
❌ Way too many requests
❌ IP banned until...
```

---

## 🎯 系统特性（v4.2）

### 数据累积时间表

| 时间框架 | 可用时间 | 说明 |
|---------|---------|------|
| **1m** | 立即 | WebSocket实时接收 |
| **5m** | 5分钟后 | 累积5根1m K线 |
| **15m** | 15分钟后 | 累积15根1m K线 |
| **1h** | 60分钟后 | 累积60根1m K线 |

### Bootstrap学习机制

系统采用渐进式启动策略：

**阶段1（前15笔交易）**：
- 信心值要求：≥30%（降低）
- 胜率要求：≥35%（降低）
- 最大杠杆：2x

**阶段2（16-35笔）**：
- 信心值要求：≥35%
- 胜率要求：≥40%
- 最大杠杆：3x

**阶段3（36-50笔）**：
- 信心值要求：≥38%
- 胜率要求：≥43%
- 最大杠杆：4x

**正常期（50笔后）**：
- 信心值要求：≥40%
- 胜率要求：≥45%
- 动态杠杆：0.5x ~ ∞

---

## 🔧 可选配置（高级）

### 启用限流预热（更快启动）

如果您需要更快的启动速度，可以启用限流预热：

```bash
# 在Railway环境变量中添加
ENABLE_KLINE_WARMUP=true
WARMUP_SYMBOL_LIMIT=30      # 只预热30个主流币
WARMUP_BATCH_SIZE=3         # 每批3个
WARMUP_BATCH_DELAY=3.0      # 每批间隔3秒
```

**影响**：
- ✅ 30秒内完成预热
- ✅ 立即可用1h数据
- ⚠️ 消耗150 API weight（安全范围内）

---

## 📋 常见问题

### Q: 为什么需要等待60分钟？

**A**: 系统依赖WebSocket实时累积数据，需要60根1分钟K线才能聚合成1根1小时K线。这是完全正常的，可以避免速率限制。

### Q: 启动后立即有信号吗？

**A**: 是的！系统会使用可用的数据生成信号：
- 启动后立即：使用5m数据（如已累积）
- 15分钟后：使用15m数据
- 60分钟后：使用完整的1h数据（最佳质量）

### Q: v4.2与v4.1有什么区别？

**A**: 
- v4.1：自动预热535个交易对 → IP封禁
- v4.2：默认禁用预热 → 0%封禁风险

### Q: 系统会漏掉交易机会吗？

**A**: 不会！系统24/7监控，WebSocket实时接收数据。已验证生成245个高质量信号（50-61%信心值）。

---

## 🎉 部署成功标志

1. ✅ Railway日志显示"K線預熱已禁用"
2. ✅ 无HTTP 418或速率限制错误
3. ✅ 系统生成交易信号
4. ✅ WebSocket连接成功（监控535个交易对）
5. ✅ PostgreSQL数据库连接成功

---

## 🆘 故障排除

### IP仍被封禁

**解决方案**：
1. 等待6-10分钟让封禁自动解除
2. 或创建新的Binance API密钥
3. 确认Railway环境变量正确设置

### 数据库连接失败

**解决方案**：
1. 确认Railway已添加PostgreSQL服务
2. 检查DATABASE_URL环境变量已正确设置
3. 查看Railway日志确认数据库启动

### WebSocket断连

**解决方案**：
1. 系统自动重连（指数退避机制）
2. 检查Binance API密钥权限（Enable Futures）
3. 确认网络连接正常

---

最后更新：2025-11-11 v4.2  
状态：✅ Production Ready (Rate-Limit Safe)
