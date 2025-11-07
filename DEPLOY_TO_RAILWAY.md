# 🚀 Railway 部署指南 - SelfLearningTrader 自动交易系统

## ✅ 系统状态

- ✅ **代码已修复**: 负杠杆 BUG 已解决
- ✅ **止损逻辑**: 进场理由失效 + 信心值<70% → 平仓
- ✅ **Railway 配置**: 已完成所有配置文件
- ✅ **数据库支持**: PostgreSQL 已集成
- ⏳ **待部署**: 需要部署到 Railway 避免 HTTP 451

---

## 📋 快速部署步骤（5分钟）

### 第一步：连接 GitHub 仓库到 Railway

1. **登录 Railway**: https://railway.app/
2. **创建新项目**: 
   - 点击 "New Project"
   - 选择 "Deploy from GitHub repo"
   - 授权并选择您的仓库

### 第二步：添加 PostgreSQL 数据库

1. **在 Railway 项目中**:
   - 点击 "+ New"
   - 选择 "Database" → "PostgreSQL"
   - Railway 会自动创建并设置 `DATABASE_URL`

### 第三步：配置环境变量

在 Railway 项目的 **Variables** 标签中添加：

```bash
# ===== Binance API 配置（必需）=====
BINANCE_API_KEY=<您的 Binance API Key>
BINANCE_API_SECRET=<您的 Binance API Secret>

# ===== 豁免期配置（必需）=====
BOOTSTRAP_MIN_CONFIDENCE=0.18
BOOTSTRAP_MIN_WIN_PROBABILITY=0.45
BOOTSTRAP_TRADE_LIMIT=50

# ===== 正常期配置（必需）=====
MIN_CONFIDENCE=0.40
MIN_WIN_PROBABILITY=0.45

# ===== 其他配置 =====
SESSION_SECRET=<任意随机字符串>
```

**注意**: `DATABASE_URL` 等数据库环境变量会由 Railway 自动设置，无需手动添加。

### 第四步：部署

Railway 会自动检测配置并部署：

1. **自动构建**: 使用 `nixpacks.toml` 配置
2. **自动安装依赖**: 从 `requirements.txt`
3. **自动启动**: 运行 `python -m src.main`

---

## 🔍 验证部署成功

### 检查日志

在 Railway 项目的 **Deployments** → **View Logs** 中查找：

```
✅ PostgreSQL连接池初始化成功
✅ 数据库表格初始化完成
✅ WebSocketManager启动完成
✅ 监控交易对: 50个
✅ 24/7 倉位監控器初始化完成
🚀 交易机器人启动成功
```

### 确认无 HTTP 451 错误

✅ **成功**: 
```
✅ K線Feed: 已连接
✅ 價格Feed: 已连接
✅ 帳戶Feed: 已连接
```

❌ **失败**: 
```
❌ HTTP 451: Service unavailable from a restricted location
```

如果看到 HTTP 451，说明 Railway 的 IP 可能被限制（极少见），需要联系 Railway 支持。

---

## 🛡️ 部署后配置检查

### 1. 豁免期设置确认

系统日志应显示：

```
🎓 豁免期配置:
   交易数限制: 50笔
   最低信心值: 18.0%
   最低胜率: 45.0%
   杠杆范围: 1-3x（强制压制）
```

### 2. 止损逻辑确认

系统日志应显示：

```
⚠️ 進場理由失效（信心<70%）: 啟用
✅ 強制止盈（信心/勝率降20%）: 啟用
💰 60%盈利自動平倉50%（每倉一次）: 啟用
🟡 智能持倉（深度虧損+高信心）: 啟用
```

### 3. 数据库连接确认

```
✅ PostgreSQL连接池初始化成功
   最小连接数: 2
   最大连接数: 10
   当前活跃: 2
```

---

## 📊 监控和管理

### Railway Dashboard 功能

1. **实时日志**: 查看交易机器人运行日志
2. **资源使用**: 监控 CPU、内存、网络使用
3. **环境变量**: 随时修改配置（会自动重启）
4. **数据库管理**: 使用内置 PostgreSQL 客户端

### 重要日志位置

Railway 会自动收集所有日志，包括：

- ✅ 交易信号生成
- ✅ 进场/出场决策
- ✅ 杠杆计算详情
- ✅ 止损触发原因
- ✅ 数据库操作记录

---

## 🔧 故障排查

### 问题 1: 部署失败

**症状**: Build failed 或 Deployment failed

**解决方案**:
1. 检查 Railway 日志中的具体错误
2. 确认 `requirements.txt` 中的依赖版本兼容
3. 检查 `nixpacks.toml` 配置是否正确

### 问题 2: HTTP 451 仍然出现

**症状**: WebSocket 连接失败，API 调用 451

**解决方案**:
1. 这种情况极少见（Railway IP 通常不被限制）
2. 联系 Railway 支持请求更换 IP
3. 或考虑使用 VPN/代理服务

### 问题 3: 数据库连接失败

**症状**: `DATABASE_URL` 未定义

**解决方案**:
1. 确认 PostgreSQL 服务已创建
2. 检查 Railway 项目中是否有两个服务（App + Database）
3. 重启部署以重新加载环境变量

### 问题 4: 无交易信号生成

**症状**: 系统运行但不下单

**解决方案**:
1. 检查 `BOOTSTRAP_MIN_CONFIDENCE=0.18` 是否设置
2. 确认 Binance API 权限包含期货交易
3. 查看日志中的信号拒绝原因

---

## 🎯 豁免期策略说明

### 前 50 笔交易（豁免期）

- **杠杆限制**: 1x ~ 3x（强制压制）
- **信心值门槛**: 18%（降低准入）
- **胜率门槛**: 45%（降低准入）
- **目的**: 快速积累数据，训练模型

### 51+ 笔交易（正常期）

- **杠杆范围**: 0.5x ~ 无上限（模型自主决策）
- **信心值门槛**: 40%（恢复正常）
- **胜率门槛**: 45%（恢复正常）
- **目的**: 基于学习数据优化交易

---

## 📈 预期性能指标

### 豁免期（前 50 笔）

- **交易频率**: 约 5-10 笔/天
- **平均杠杆**: 1.5x ~ 2.5x
- **目标胜率**: 45%+
- **完成时间**: 约 5-10 天

### 正常期（51+ 笔）

- **交易频率**: 根据市场条件
- **平均杠杆**: 动态（高信心高杠杆）
- **目标胜率**: 50%+
- **止损触发**: 8 层保护机制

---

## 🔐 安全检查清单

- ✅ API 密钥使用环境变量（不提交代码）
- ✅ 数据库凭证由 Railway 自动管理
- ✅ 连接池限制防止资源耗尽
- ✅ 所有敏感信息不写入日志
- ✅ 使用内部 URL（`DATABASE_URL`）提高安全性

---

## 📚 相关文档

- **完整部署清单**: `RAILWAY_DEPLOYMENT_CHECKLIST.md`
- **数据库设置**: `docs/DATABASE_SETUP.md`
- **使用示例**: `examples/database_usage.py`
- **Railway 官方文档**: https://docs.railway.app/

---

## 🚀 开始部署！

准备好了吗？按照上面的步骤操作：

1. **连接 GitHub 到 Railway**
2. **添加 PostgreSQL 数据库**
3. **配置环境变量**
4. **等待自动部署完成**
5. **检查日志确认成功**

部署完成后，您的交易机器人将在 Railway 上 24/7 运行，实时监控 50 个 USDT 永续合约交易对！

---

**最后修复**: 2025-11-07  
**修复内容**: 负杠杆值 BUG（`leverage_engine.py:97` 添加 `max(0, ...)`）  
**系统版本**: v3.18.7+ (豁免期策略)  
**部署状态**: ✅ 准备就绪
