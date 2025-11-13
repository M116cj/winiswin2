# 🚀 快速开始：Railway 部署（30分钟）

## 📌 一键迁移指南

### ⚡ 前置条件
- ✅ GitHub 账户
- ✅ Binance API 密钥（已有）
- ✅ 30分钟时间

---

## 🔥 3步完成部署

### STEP 1: 创建 Railway 项目（5分钟）

1. **访问 Railway**
   ```
   https://railway.app/
   ```

2. **使用 GitHub 登录**
   - 点击 "Login with GitHub"
   - 授权 Railway 访问

3. **新建项目**
   - 点击 "New Project"
   - 选择 "Deploy from GitHub repo"
   - 选择此仓库

4. **添加 PostgreSQL**
   - 点击 "+ New"
   - 选择 "Database" → "PostgreSQL"
   - 等待创建完成

---

### STEP 2: 配置环境变量（10分钟）

点击你的服务 → Variables 标签，添加以下变量：

```bash
# ========== 必需配置 ==========
BINANCE_API_KEY=你的API密钥
BINANCE_API_SECRET=你的API密钥Secret
BINANCE_TESTNET=false

# ========== 交易配置 ==========
TRADING_ENABLED=true
MAX_CONCURRENT_ORDERS=5

# ========== 时间止损（2小时强制平仓）==========
TIME_BASED_STOP_LOSS_ENABLED=true
TIME_BASED_STOP_LOSS_HOURS=2.0
TIME_BASED_STOP_LOSS_CHECK_INTERVAL=60

# ========== 全仓保护（85%触发）==========
CROSS_MARGIN_PROTECTOR_ENABLED=true
CROSS_MARGIN_PROTECTOR_THRESHOLD=0.85

# ========== WebSocket配置 ==========
WEBSOCKET_ONLY_KLINES=true
DISABLE_REST_FALLBACK=true
```

💡 **提示**：数据库变量（DATABASE_URL等）会自动配置，无需手动添加！

---

### STEP 3: 部署并验证（15分钟）

1. **触发部署**
   - Railway 会自动检测到环境变量变化
   - 自动开始构建和部署

2. **查看部署日志**
   - 点击 Deployments 标签
   - 等待状态变为 "Success"

3. **验证成功标志**
   
   在日志中查找以下内容：
   
   ```
   ✅ 应该看到：
   ✅ SelfLearningTrader v4.0+ 启动中...
   ✅ OrderValidator 初始化完成
   ✅ 数据库连接池已初始化
   ✅ PositionController 24/7 監控已啟動
   ✅ WebSocket連接成功
   
   ❌ 不应该看到：
   ❌ HTTP 451 地理限制  # 这个错误应该消失！
   ```

4. **运行诊断验证**
   
   在 Railway Shell 中执行：
   ```bash
   python diagnostics/run_full_diagnostics.py
   ```
   
   期望结果：
   ```
   📊 總體健康評分: 90%+
   ✅ REST API: 95%+  (从 0% 提升！)
   ✅ WebSocket: 95%+
   ✅ 交易協議: 95%+
   ```

---

## ✅ 成功标准

部署成功后，您应该看到：

| 指标 | Replit | Railway | 状态 |
|------|--------|---------|------|
| HTTP 451 错误 | ❌ 100% | ✅ 0% | **解决** |
| REST API 可用性 | ❌ 0% | ✅ 95%+ | **修复** |
| WebSocket 稳定性 | ⚠️ 80% | ✅ 95%+ | **提升** |
| 总体健康评分 | ❌ 50% | ✅ 90%+ | **优秀** |

---

## 🎯 下一步

部署成功后：

1. **监控运行状态**
   - Railway Dashboard → Metrics
   - 查看 CPU/内存使用情况

2. **配置 Discord 通知（可选）**
   ```bash
   DISCORD_TOKEN=你的Token
   DISCORD_CHANNEL_ID=你的频道ID
   ```

3. **开始交易**
   - 系统已自动运行
   - 监控日志中的交易信号
   - 查看持仓和平仓记录

---

## 🚨 常见问题

### Q1: 部署失败怎么办？
**A**: 查看 Deployments 日志，通常是依赖安装问题：
- 检查 requirements.txt 是否完整
- 确认 Python 3.11 环境

### Q2: 仍然看到 HTTP 451？
**A**: 极少见情况，可能需要：
- 联系 Railway 支持更换 IP
- 或尝试重新部署

### Q3: 数据库连接失败？
**A**: 检查：
- PostgreSQL 服务是否 Running
- DATABASE_URL 变量是否存在
- 重启 PostgreSQL 服务

### Q4: 如何查看交易记录？
**A**: 
```bash
# 在 Railway Shell 中执行
python -c "import asyncio; from src.managers.unified_trade_recorder import UnifiedTradeRecorder; asyncio.run(UnifiedTradeRecorder().get_statistics())"
```

---

## 📚 详细文档

- 完整部署指南: `RAILWAY_DEPLOYMENT_GUIDE.md`
- 迁移检查清单: `MIGRATION_CHECKLIST.md`
- 系统诊断工具: `diagnostics/`

---

## 💡 重要提示

1. **Replit 环境已不可用**
   - HTTP 451 限制无法解决
   - 必须迁移到 Railway

2. **代码已完全准备好**
   - v4.4.1 所有优化已完成
   - 仓位控制系统已审查通过
   - 只需要正确的运行环境

3. **Railway 免费额度**
   - $5/月免费额度
   - 足够运行此交易系统
   - 可随时升级

---

## 🎉 准备好了吗？

现在就开始部署：

1. ✅ 打开 https://railway.app/
2. ✅ 10分钟创建项目和数据库
3. ✅ 10分钟配置环境变量
4. ✅ 10分钟部署验证
5. 🚀 开始自动交易！

**总计：30分钟让系统完全运行！** 

---

**需要帮助？** 查看详细部署指南或联系技术支持。
