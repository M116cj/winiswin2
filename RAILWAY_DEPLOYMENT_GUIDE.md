# 🚀 Railway 部署完整指南

## 📋 目录
1. [部署前准备](#部署前准备)
2. [Railway项目创建](#railway项目创建)
3. [环境变量配置](#环境变量配置)
4. [部署验证](#部署验证)
5. [监控与优化](#监控与优化)
6. [故障排查](#故障排查)

---

## 🔧 部署前准备

### ✅ 检查清单
- [ ] GitHub 仓库已同步最新代码
- [ ] 所有环境变量已准备好（API密钥、数据库URL等）
- [ ] 已阅读 Railway 定价信息
- [ ] 本地代码已通过诊断测试（基础环境 100%）

### 📦 必需文件验证
确保以下文件存在于项目根目录：

```bash
# 检查关键文件
✅ requirements.txt     # Python依赖
✅ src/main.py         # 主入口
✅ src/config.py       # 配置文件
✅ .gitignore          # Git忽略规则
```

---

## 🏗️ Railway 项目创建

### STEP 1: 创建 Railway 账户
1. 访问 https://railway.app/
2. 使用 GitHub 账户登录
3. 验证邮箱地址

### STEP 2: 新建项目
```bash
1. 点击 "New Project"
2. 选择 "Deploy from GitHub repo"
3. 授权 Railway 访问您的 GitHub
4. 选择此交易系统的仓库
```

### STEP 3: 配置服务
```yaml
服务名称: SelfLearningTrader
运行环境: Python 3.11
启动命令: python -m src.main
健康检查: 禁用（长期运行任务）
```

---

## ⚙️ 环境变量配置

### 🔴 关键环境变量（必须配置）

复制以下变量到 Railway 环境变量配置：

```bash
# ========== Binance API 配置 ==========
BINANCE_API_KEY=你的API密钥
BINANCE_API_SECRET=你的API密钥Secret
BINANCE_TESTNET=false

# ========== 数据库配置 ==========
DATABASE_URL=${{Postgres.DATABASE_URL}}  # Railway自动提供
PGHOST=${{Postgres.PGHOST}}
PGPORT=${{Postgres.PGPORT}}
PGUSER=${{Postgres.PGUSER}}
PGPASSWORD=${{Postgres.PGPASSWORD}}
PGDATABASE=${{Postgres.PGDATABASE}}

# ========== 交易配置 ==========
TRADING_ENABLED=true
MAX_CONCURRENT_ORDERS=5
CYCLE_INTERVAL=60

# ========== 时间止损配置 ==========
TIME_BASED_STOP_LOSS_ENABLED=true
TIME_BASED_STOP_LOSS_HOURS=2.0
TIME_BASED_STOP_LOSS_CHECK_INTERVAL=60

# ========== 全仓保护配置 ==========
CROSS_MARGIN_PROTECTOR_ENABLED=true
CROSS_MARGIN_PROTECTOR_THRESHOLD=0.85
CROSS_MARGIN_PROTECTOR_COOLDOWN=120

# ========== WebSocket配置 ==========
WEBSOCKET_ONLY_KLINES=true
DISABLE_REST_FALLBACK=true

# ========== 模型配置 ==========
DISABLE_MODEL_TRAINING=false
ENABLE_KLINE_WARMUP=false

# ========== 日志配置 ==========
LOG_LEVEL=INFO
```

### 🟡 可选环境变量

```bash
# Discord通知（可选）
DISCORD_TOKEN=你的Discord Token
DISCORD_CHANNEL_ID=你的频道ID

# 性能优化
DB_MIN_CONNECTIONS=2
DB_MAX_CONNECTIONS=10
```

---

## 🔗 添加 PostgreSQL 数据库

### STEP 1: 添加数据库服务
```bash
1. 在 Railway 项目中点击 "+ New"
2. 选择 "Database" → "Add PostgreSQL"
3. 等待数据库创建完成
```

### STEP 2: 连接数据库
```bash
# Railway 会自动生成以下变量：
- DATABASE_URL
- PGHOST
- PGPORT
- PGUSER
- PGPASSWORD
- PGDATABASE

# 这些变量会自动注入到你的应用中
```

### STEP 3: 初始化数据表
部署后，系统会自动创建 `position_entry_times` 表：

```sql
-- 自动创建（由代码管理）
CREATE TABLE IF NOT EXISTS position_entry_times (
    symbol VARCHAR(20) PRIMARY KEY,
    entry_time BIGINT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## ✅ 部署验证

### STEP 1: 查看部署日志
```bash
1. 在 Railway 控制台点击你的服务
2. 点击 "Deployments" 标签
3. 查看最新部署的日志
```

### STEP 2: 检查关键日志
验证以下日志出现：

```bash
✅ 期望看到的日志：
-------------------
✅ SelfLearningTrader v4.0+ 启动中...
✅ OrderValidator 初始化完成 (最小名义价值: 5.0 USDT)
✅ 数据库连接池已初始化
✅ 持倉時間已恢復: X 條記錄
✅ PositionController 24/7 監控已啟動
✅ WebSocket連接成功

❌ 不应该看到的错误：
-------------------
❌ HTTP 451 地理限制  # 这个错误应该消失
❌ Connection refused
❌ Database connection failed
```

### STEP 3: 运行验证诊断
在Railway环境中运行诊断：

```bash
# 通过 Railway Shell 执行
python diagnostics/run_full_diagnostics.py

# 预期结果：
📊 總體健康評分: 90%+
✅ REST API: 95%+
✅ WebSocket: 95%+
✅ 交易協議: 95%+
```

---

## 📊 监控与优化

### 🔍 Railway 内置监控
```bash
1. 在服务页面查看 "Metrics" 标签
2. 监控指标：
   - CPU 使用率 < 70%
   - 内存使用率 < 80%
   - 网络流量
   - 请求响应时间
```

### 🚨 设置告警

#### 方法1: Railway 通知
```bash
1. 进入 Project Settings → Notifications
2. 设置 Deployment Failed 通知
3. 设置 Service Crashed 通知
```

#### 方法2: Discord 集成（推荐）
系统已内置Discord通知，配置环境变量即可：

```bash
DISCORD_TOKEN=你的Token
DISCORD_CHANNEL_ID=你的频道ID
```

通知内容：
- ✅ 交易开仓/平仓
- ⚠️ 时间止损触发
- 🚨 全仓保护触发
- ❌ API错误告警

### 📈 性能优化配置

#### 1. 调整实例规格
```bash
推荐配置：
- 内存: 1 GB+
- CPU: 共享 vCPU
- 磁盘: 5 GB+
```

#### 2. 数据库连接池优化
```bash
DB_MIN_CONNECTIONS=2    # 最小连接数
DB_MAX_CONNECTIONS=10   # 最大连接数（Railway免费版限制）
DB_CONNECTION_TIMEOUT=30
```

#### 3. WebSocket 优化
```bash
# 已优化配置（无需修改）
- 自动重连: 已启用
- 指数退避: 1s → 2s → 4s → 8s
- 心跳检测: 20秒间隔
```

---

## 🔧 Railway 特定配置

### railway.json（可选）
在项目根目录创建配置文件：

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python -m src.main",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### nixpacks.toml（可选）
高级包管理配置：

```toml
[phases.setup]
nixPkgs = ["python311", "postgresql"]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[start]
cmd = "python -m src.main"
```

---

## 🚨 故障排查

### 问题1: 部署失败
```bash
症状: Deployment failed
检查:
  1. requirements.txt 是否完整
  2. Python版本是否兼容
  3. 环境变量是否配置

解决:
  - 查看部署日志中的错误堆栈
  - 确认所有依赖都能安装
```

### 问题2: HTTP 451 仍然出现
```bash
症状: Service unavailable from restricted location
原因: Railway IP被Binance限制（极少见）

解决:
  1. 联系 Railway 支持更换 IP 段
  2. 或迁移到 AWS/GCP
```

### 问题3: 数据库连接失败
```bash
症状: Database connection failed
检查:
  1. PostgreSQL 服务是否正常运行
  2. DATABASE_URL 是否正确
  3. 网络连接是否稳定

解决:
  - 重启 PostgreSQL 服务
  - 检查数据库变量引用格式
```

### 问题4: 内存不足
```bash
症状: Out of memory error
检查:
  - 当前内存使用率
  - XGBoost模型加载是否占用过多

解决:
  - 升级 Railway 套餐（8GB+）
  - 或优化模型加载策略
```

### 问题5: WebSocket 频繁断连
```bash
症状: WebSocket连接不稳定
检查:
  - 网络质量
  - Railway服务稳定性

解决:
  - 系统已内置自动重连（指数退避）
  - 检查日志中重连频率
  - 如果>10次/小时，联系Railway支持
```

---

## 📋 部署后检查清单

### ✅ 立即验证（部署后5分钟内）
- [ ] 服务状态显示 "Running"
- [ ] 日志中无 HTTP 451 错误
- [ ] 日志中看到 "PositionController 24/7 監控已啟動"
- [ ] 日志中看到 "WebSocket連接成功"
- [ ] 数据库连接正常
- [ ] 持仓时间恢复成功

### ✅ 短期验证（部署后1小时内）
- [ ] WebSocket 无异常断连
- [ ] REST API 调用成功率 > 95%
- [ ] 内存使用率 < 80%
- [ ] CPU 使用率 < 70%
- [ ] 无错误日志堆积

### ✅ 长期验证（部署后24小时内）
- [ ] 系统运行时间 > 23小时
- [ ] 自动重连机制正常工作
- [ ] 时间止损功能正常（如有持仓）
- [ ] 交易记录正确保存到数据库
- [ ] 模型推理性能正常

---

## 🎯 成功标准

部署成功后，重新运行诊断应达到：

```bash
🎯 總體健康評分: 90%+

✅ 基礎環境: 100%
✅ REST API: 95%+  (从 0% → 95%+)
✅ WebSocket: 95%+
✅ 交易協議: 95%+

📋 成功標準檢查:
✅ 總體健康評分 > 90%
✅ REST API評分 > 80%
✅ WebSocket評分 > 80%
✅ 交易協議評分 > 80%
```

---

## 💡 最佳实践

### 1. 定期备份
```bash
- Railway 自动备份 PostgreSQL
- 建议额外导出重要交易记录
```

### 2. 监控告警
```bash
- 配置 Discord 通知
- 每日检查交易统计
- 每周审查错误日志
```

### 3. 安全措施
```bash
- 定期轮换 API 密钥
- 启用 IP 白名单（Binance 设置）
- 限制 Railway 访问权限
```

### 4. 性能优化
```bash
- 定期清理旧日志
- 监控数据库大小
- 优化交易对列表
```

---

## 📞 获取帮助

- Railway 文档: https://docs.railway.app/
- Railway 社区: https://discord.gg/railway
- Binance API 文档: https://binance-docs.github.io/apidocs/futures/cn/

---

## 🚀 快速部署命令

```bash
# 1. 准备环境变量文件
cat > .env.railway << EOF
BINANCE_API_KEY=你的密钥
BINANCE_API_SECRET=你的密钥
TRADING_ENABLED=true
TIME_BASED_STOP_LOSS_ENABLED=true
TIME_BASED_STOP_LOSS_HOURS=2.0
EOF

# 2. 推送到GitHub
git add .
git commit -m "Ready for Railway deployment"
git push origin main

# 3. 在Railway控制台
# - 创建新项目
# - 连接GitHub仓库
# - 添加PostgreSQL
# - 配置环境变量
# - 部署！
```

---

**🎉 部署完成后，您的交易系统将完全自动化运行！**

记得在部署后立即运行诊断验证，确保所有功能正常。
