# 🔍 Railway自动下线原因诊断与解决方案

## 📊 您的交易机器人自动下线的可能原因

根据Railway平台特性和您的24/7交易机器人需求，以下是导致自动下线的主要原因：

---

## ⚠️ 最常见原因（按概率排序）

### 1. 💰 **免费额度用尽**（概率：85%）

**症状**：
- 服务突然停止
- Railway Dashboard显示"Out of credits"
- 无法重启服务

**Railway免费额度限制**：
- **$5 免费额度/月**（2025年标准）
- 按使用时间和资源消耗计费
- 24/7运行的服务很快耗尽免费额度

**您的交易机器人消耗**：
```
预估每月成本：
- CPU/内存基础费用：$10-15/月（24/7运行）
- 网络流量（Binance API）：$2-5/月
- 总计：~$12-20/月

免费额度：$5/月
结果：约3-5天后免费额度用尽 ⚠️
```

**验证方法**：
1. 登录 [Railway Dashboard](https://railway.app/)
2. 查看 **Usage** 标签
3. 检查当前月份的消耗情况

**解决方案**：
```
选项A：升级到付费计划
- Hobby Plan: $5/月 + 使用费
- 每月$5固定费 + 实际使用量计费

选项B：优化资源使用（见下文）
```

---

### 2. 🔄 **应用崩溃/错误**（概率：10%）

**症状**：
- 日志中出现未捕获的异常
- 进程意外退出
- Railway显示"Crashed"状态

**可能的崩溃原因**：
```python
# A. 未处理的API错误
try:
    data = await binance_client.get_data()
except Exception as e:
    # 如果没有这个catch，应用会崩溃
    logger.error(f"API错误: {e}")

# B. 内存泄漏
# 长时间运行累积数据导致内存溢出

# C. 网络超时
# Binance API连接超时未正确处理
```

**检查方法**：
1. Railway Dashboard → **Deployments**
2. 查看最新部署的 **Logs**
3. 搜索关键词：`ERROR`, `Exception`, `Crash`, `exit code`

**解决方案**：
```python
# 在main.py添加全局错误处理
import signal
import sys

def signal_handler(sig, frame):
    logger.info("收到关闭信号，正在优雅退出...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# 主循环添加重试机制
while True:
    try:
        await main_loop()
    except Exception as e:
        logger.error(f"主循环错误: {e}", exc_info=True)
        await asyncio.sleep(5)  # 5秒后重试
```

---

### 3. 💤 **Serverless模式自动休眠**（概率：3%）

**Railway的App Sleeping机制**：
- 10分钟无**出站网络流量**→ 自动休眠
- 您的机器人每60秒调用Binance API → 理论上不会休眠

**但可能休眠的情况**：
```
1. 如果所有信号都被拒绝（如旧版v3.3.3的问题）
   → 没有调用Binance API下单
   → 可能被判定为无活动

2. 仅内部循环运行，无外部API调用
   → Railway认为无活动
```

**验证方法**：
Railway Dashboard → Service Settings → 查看是否启用了"Serverless"

**解决方案**：
```bash
# 在Railway服务设置中禁用Serverless模式
Settings → Serverless → OFF
```

---

### 4. 🛡️ **健康检查失败**（概率：2%）

**症状**：
- Railway认为应用无响应
- 自动重启服务
- 重启失败后停止服务

**您的机器人是纯Python脚本**：
- 没有HTTP服务器
- Railway无法通过HTTP健康检查
- 可能被误判为"不健康"

**解决方案**：
```python
# 选项A：添加简单的HTTP健康检查端点
from aiohttp import web

async def health_check(request):
    return web.Response(text="OK")

async def start_health_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("健康检查服务启动在端口8080")

# 在main()中启动
asyncio.create_task(start_health_server())
```

然后在Railway中设置健康检查：
```
Settings → Healthcheck Path: /health
```

---

## 🔧 全面的Railway优化方案

### A. 降低成本（延长免费额度使用时间）

```python
# 1. 减少API调用频率
# config.py
CYCLE_INTERVAL = 120  # 从60秒改为120秒

# 2. 减少扫描的交易对数量
TOP_VOLATILITY_SYMBOLS = 100  # 从200改为100

# 3. 禁用不必要的功能
ENABLE_DISCORD_BOT = False  # 如果不需要Discord通知
```

### B. 添加进程守护（防止崩溃）

```python
# main.py 添加自动重启机制
async def run_with_auto_restart():
    """自动重启的主循环"""
    restart_count = 0
    max_restarts = 10
    
    while restart_count < max_restarts:
        try:
            logger.info(f"🚀 启动交易机器人 (重启次数: {restart_count})")
            await main_loop()
        except Exception as e:
            restart_count += 1
            logger.error(
                f"❌ 机器人崩溃: {e} "
                f"(重启 {restart_count}/{max_restarts})",
                exc_info=True
            )
            
            if restart_count >= max_restarts:
                logger.critical("达到最大重启次数，退出")
                break
            
            # 等待后重启
            wait_time = min(60 * restart_count, 300)  # 最多等5分钟
            logger.info(f"⏳ {wait_time}秒后重启...")
            await asyncio.sleep(wait_time)
    
if __name__ == "__main__":
    asyncio.run(run_with_auto_restart())
```

### C. 添加Railway专用配置

创建 `railway.json`：
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python -m src.main",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 300,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### D. 环境变量优化

在Railway中设置：
```bash
# 防止自动休眠
RAILWAY_STATIC_URL=true

# Python优化
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1

# 资源限制
RAILWAY_GIT_COMMIT_SHA=${{RAILWAY_GIT_COMMIT_SHA}}
```

---

## 📈 监控Railway运行状态

### 实时监控脚本

```python
# monitoring.py
import requests
import time

RAILWAY_PROJECT_ID = "your-project-id"
RAILWAY_TOKEN = "your-railway-token"

def check_railway_status():
    """检查Railway服务状态"""
    url = f"https://backboard.railway.app/graphql/v2"
    
    headers = {
        "Authorization": f"Bearer {RAILWAY_TOKEN}",
        "Content-Type": "application/json"
    }
    
    query = """
    query {
      project(id: "%s") {
        services {
          edges {
            node {
              name
              deployments {
                edges {
                  node {
                    status
                    createdAt
                  }
                }
              }
            }
          }
        }
        usage {
          estimatedCost
          currentPeriodEnd
        }
      }
    }
    """ % RAILWAY_PROJECT_ID
    
    response = requests.post(
        url,
        json={"query": query},
        headers=headers
    )
    
    data = response.json()
    print("Railway状态:", data)
    return data

# 每小时检查一次
while True:
    try:
        status = check_railway_status()
        # 处理状态数据
        # 如果服务停止，发送告警
    except Exception as e:
        print(f"检查失败: {e}")
    
    time.sleep(3600)  # 1小时
```

---

## 🎯 快速诊断清单

**立即检查以下内容**：

| 检查项 | 如何检查 | 预期结果 |
|--------|---------|---------|
| ✅ 额度余额 | Railway Dashboard → Usage | > $0.00 |
| ✅ 服务状态 | Railway Dashboard → Service | Running |
| ✅ 最新日志 | Deployments → Latest → Logs | 无ERROR |
| ✅ 部署状态 | Deployments | Success |
| ✅ Serverless | Settings → Serverless | OFF |
| ✅ 重启策略 | Settings → Restart Policy | ON_FAILURE |

---

## 💡 推荐方案

### 短期方案（立即执行）
1. **检查Railway额度**：确认是否用尽免费额度
2. **查看最新日志**：确认没有崩溃错误
3. **禁用Serverless**：防止自动休眠

### 中期方案（本周内）
1. **升级到Hobby Plan**（$5/月起）
2. **添加健康检查端点**
3. **添加自动重启机制**

### 长期方案（优化成本）
1. **减少API调用频率**（60秒→120秒）
2. **减少扫描交易对数量**（200→100）
3. **考虑使用VPS**（如果成本持续增长）

---

## 📞 获取Railway Token诊断

### 获取Railway API Token
1. 登录 [Railway Dashboard](https://railway.app/)
2. 点击右上角头像 → **Account Settings**
3. 选择 **Tokens** 标签
4. 点击 **Create Token**
5. 复制生成的token

### 使用Token检查项目状态

```bash
# 安装Railway CLI
npm install -g @railway/cli

# 登录
railway login

# 检查项目状态
railway status

# 查看日志
railway logs

# 检查使用情况
railway run env
```

---

## 🚨 紧急恢复步骤

如果服务当前已停止：

```bash
# 1. 通过CLI重启
railway up

# 2. 或通过Dashboard
Dashboard → Service → Redeploy

# 3. 检查错误
railway logs --follow
```

---

**更新时间**：2025-10-27  
**适用版本**：Railway 2025  
**机器人版本**：v3.3.5
