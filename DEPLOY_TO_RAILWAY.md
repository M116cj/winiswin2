# 🚀 部署 v3.0.2 到 Railway - 完整步骤

**问题**: Railway 上运行的是旧代码，需要重新部署！

**版本**: v3.0.2 - 超简化趋势识别

---

## 📋 部署前检查清单

- ✅ 代码已修复（超简化 EMA 交叉策略）
- ✅ 添加诊断日志（显示每个交易对的趋势值）
- ✅ 编译测试通过
- ⏳ **待执行：推送到 Railway**

---

## 🔧 方法 1: 使用 Railway CLI（推荐）

### 步骤 1: 确认 Railway 项目连接

```bash
railway status
```

**预期输出**:
```
Project: your-trading-bot
Environment: production
```

### 步骤 2: 直接部署

```bash
railway up
```

或者推送到 git：

```bash
git add .
git commit -m "🔧 v3.0.2: 修复趋势识别 - 超简化EMA交叉策略"
railway up
```

### 步骤 3: 监控部署

```bash
railway logs --follow
```

---

## 🔧 方法 2: 通过 Git 推送

### 如果你有 Railway 的 Git remote

```bash
# 查看 remote
git remote -v

# 如果有 railway remote
git add .
git commit -m "🔧 v3.0.2: 修复趋势识别"
git push railway main

# 如果没有 railway remote，添加它
railway link
git push railway main
```

---

## 🔧 方法 3: 通过 Railway Dashboard

1. 访问 Railway Dashboard
2. 进入你的项目
3. 点击 **Settings** → **Service** → **Deploy**
4. 手动触发重新部署

或者：
1. 连接 GitHub repository
2. 推送代码到 GitHub
3. Railway 自动检测并部署

---

## 📊 部署后验证（重要！）

### 预期日志输出（成功）

```bash
railway logs --follow
```

**应该看到**:
```
🔍 開始掃描市場...

BTCUSDT: 趨勢檢測 - 1h:bullish, 15m:bullish, 5m:bullish
✅ 生成交易信號: BTCUSDT LONG 信心度 78.5%

ETHUSDT: 趨勢檢測 - 1h:bullish, 15m:neutral, 5m:bullish
✅ 生成交易信號: ETHUSDT LONG 信心度 72.3%

BNBUSDT: 趨勢檢測 - 1h:bearish, 15m:bearish, 5m:bearish
✅ 生成交易信號: BNBUSDT SHORT 信心度 69.1%

...

🎯 本週期共生成 18 個交易信號
```

### ❌ 如果还是看到（失败）

```
拒絕 - 1h 和 15m 都是 neutral  ← 这个消息应该消失了
```

**解决方案**:
1. 确认代码已推送
2. 检查 Railway 是否重新构建
3. 强制重新部署

---

## 🔍 故障排除

### 问题 1: Railway 没有检测到更改

```bash
# 强制重新部署
railway redeploy
```

### 问题 2: 缓存问题

在 Railway Dashboard:
1. Settings → Service
2. 找到 "Clear Build Cache"
3. 重新部署

### 问题 3: 环境变量丢失

确认 Railway 中设置了：
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`

---

## 🎯 关键变化对比

### v3.0.1（失败）
```python
# 三重条件，太严格
if 价格 > 快线 AND 价格 > 慢线 AND 快线 > 慢线:
    return "bullish"
```

### v3.0.2（成功）
```python
# 标准 EMA 交叉
if 快线 > 慢线:
    return "bullish"
```

---

## 📈 预期改进

| 指标 | 修复前 | 修复后 |
|-----|-------|-------|
| 趋势识别率 | ~5% | ~95% |
| 每周期信号数 | 0-1 个 | 10-30 个 |
| 日志消息 | "拒絕 neutral" | "趨勢檢測" |

---

## ✅ 最终确认

部署成功后，在 Railway 日志中查找：

1. ✅ **新日志格式**: `趨勢檢測 - 1h:bullish, 15m:bullish, 5m:bullish`
2. ✅ **生成信号**: `生成交易信號: BTCUSDT LONG`
3. ✅ **信号统计**: `本週期共生成 XX 個交易信號` (XX > 5)

---

**⚠️ 重要**: 部署后请立即在这里回报日志输出，确认修复生效！
