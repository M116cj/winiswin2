# 🚀 Railway 立即部署指南

**版本**: v3.1.3  
**状态**: ✅ 就绪（冷启动问题已修复）

---

## ⚠️ 为什么必须使用 Railway？

**Replit 封锁 Binance API**（返回451错误）：

```
❌ Binance API 連接失敗: 451, message='', url='https://fapi.binance.com/fapi/v1/ping'
```

**解决方案**：部署到 Railway（亚洲区域服务器）

---

## 📋 部署前检查清单

### ✅ 已完成

- [x] **智能订单系统** v3.1.2（滑点保护）
- [x] **冷启动学习模式** v3.1.3（解决无法下单问题）
- [x] **XGBoost 特征保存**（38个特征 → ml_data/*.csv）
- [x] **止盈止损自动设置**（STOP_MARKET + TAKE_PROFIT_MARKET）
- [x] **3仓位限制 + 信心度排序**
- [x] **Railway 配置文件**（nixpacks.toml + railway.json）

### ⚠️ 需要设置

- [ ] **Railway 环境变量**（必需）

---

## 🔧 步骤 1: 设置 Railway 环境变量

### 登录 Railway Dashboard

https://railway.app/

### 必需的环境变量

```bash
# Binance API（必需）
BINANCE_API_KEY=<您的API密钥>
BINANCE_API_SECRET=<您的API密钥密码>

# 交易模式
BINANCE_TESTNET=false  # false=主网
TRADING_ENABLED=false  # 建议先false，验证连接后改true

# 可选
DISCORD_TOKEN=<您的Discord Token>
DISCORD_CHANNEL_ID=1430538906629050500
LOG_LEVEL=INFO
```

⚠️ **安全提醒**：
- **不要在聊天中提供** `BINANCE_API_SECRET`
- **直接在 Railway 网页**设置环境变量
- API密钥权限建议：仅开启"合约交易"，关闭"提现"

---

## 🚀 步骤 2: 部署代码

### 方法 A: 使用 Railway CLI（推荐）

```bash
# 1. 链接项目（如果未链接）
railway link

# 2. 推送代码
git add .
git commit -m "🎓 v3.1.3: 冷启动学习模式 + 智能订单系统"
git push railway main

# 3. 查看日志
railway logs --follow
```

### 方法 B: 通过 Railway Dashboard

1. 登录 https://railway.app/
2. 找到您的项目
3. 点击 "Settings" → "Deployments"
4. 手动触发重新部署

---

## 📊 步骤 3: 验证部署成功

### 预期启动日志

```
✅ Binance 連接成功
✅ 數據服務已就緒
✅ 智能數據管理器已就緒
✅ 期望值計算器已就緒（窗口大小: 30 筆交易）
✅ ML 預測器已就緒
✅ 系統初始化完成

🔍 開始掃描市場，目標選擇前 200 個高流動性交易對...
📊 ✅ 已選擇 200 個高流動性交易對

🎯 生成 3 個交易信號
  #1 ASTERUSDT LONG 信心度 70.00%
  #2 XRPUSDT LONG 信心度 60.00%
  #3 ZECUSDT LONG 信心度 52.67%
```

### 关键：学习模式激活

```
🎓 学习模式 (0/30)：跳过期望值检查，收集初始交易数据
✅ 準備開倉: ASTERUSDT LONG 數量: 0.15 槓桿: 15x
✅ 開倉成功: ASTERUSDT LONG @ 100.50
設置止損: ASTERUSDT @ 95.00
設置止盈: ASTERUSDT @ 110.00
```

---

## 🎯 步骤 4: 确认下单功能

### 检查日志关键字

```bash
# Railway CLI
railway logs --follow | grep -E "學習模式|開倉成功|設置止"

# 预期输出：
🎓 学习模式 (0/30)：跳过期望值检查
✅ 開倉成功: ASTERUSDT LONG @ 100.50
設置止損: ASTERUSDT @ 95.00
設置止盈: ASTERUSDT @ 110.00

🎓 学习模式 (1/30)：跳过期望值检查
✅ 開倉成功: XRPUSDT LONG @ 2.35
設置止損: XRPUSDT @ 2.25
設置止盈: XRPUSDT @ 2.50

🎓 学习模式 (2/30)：跳过期望值检查
✅ 開倉成功: ZECUSDT LONG @ 45.20
設置止損: ZECUSDT @ 43.00
設置止盈: ZECUSDT @ 50.00
```

### 验证 3 仓位限制

```bash
railway logs | grep "當前持倉"

# 预期输出：
當前持倉: 1/3
當前持倉: 2/3
當前持倉: 3/3（已满）  # 不会超过3个
```

---

## 📁 步骤 5: 验证 XGBoost 特征保存

### SSH 到 Railway 容器（如果有权限）

```bash
ls -lh ml_data/

# 预期输出：
signals.csv      # 信号特征（38 features）
positions.csv    # 仓位记录
```

### 检查数据归档日志

```bash
railway logs | grep "归档"

# 预期输出：
已归档 3 条信号记录到 ml_data/signals.csv
已归档 1 条仓位记录到 ml_data/positions.csv
```

---

## 🔍 常见问题排查

### Q1: 仍然没有下单

**检查**：
```bash
railway logs | grep "期望值檢查"
```

**可能原因**：
1. `TRADING_ENABLED=false`（模拟模式）
   - **解决**：改为 `TRADING_ENABLED=true`
   
2. 仍显示"盈亏比过低"
   - **确认**：代码是否最新（v3.1.3）
   - **解决**：`git push railway main` 重新部署

### Q2: 超过 3 个仓位

**检查配置**：
```bash
railway env | grep MAX_POSITIONS

# 应该是：
MAX_POSITIONS=3
```

### Q3: 没有看到学习模式日志

**检查**：
```bash
railway logs | grep "學習模式"
```

**如果没有输出**：
- 代码未更新，重新推送 v3.1.3
- 查看是否有错误日志

---

## 📊 监控仪表板

### 实时监控命令

```bash
# 实时日志
railway logs --follow

# 仅显示交易相关
railway logs --follow | grep -E "信號|開倉|平倉|止損|止盈"

# 仅显示学习进度
railway logs --follow | grep "學習模式"

# 仅显示错误
railway logs --follow | grep -E "ERROR|❌"
```

### 预期健康指标

```
📊 系統狀態: CPU 25.0% | 內存 30.5% | API 調用 1234
當前持倉: 3/3
虛擬倉位: 7
```

---

## 🎉 部署成功标志

当你看到以下日志时，说明系统已成功运行：

```
✅ 系統初始化完成

🎯 生成 3 個交易信號
  #1 ASTERUSDT LONG 信心度 70%
  #2 XRPUSDT LONG 信心度 60%
  #3 ZECUSDT LONG 信心度 52.67%

🎓 学习模式 (0/30)：跳过期望值检查，收集初始交易数据
✅ 準備開倉: ASTERUSDT LONG 數量: 0.15 槓桿: 15x 信心度: 70.00%
✅ 開倉成功: ASTERUSDT LONG @ 100.50
設置止損: ASTERUSDT @ 95.00
設置止盈: ASTERUSDT @ 110.00

🎓 学习模式 (1/30)：跳过期望值检查
✅ 開倉成功: XRPUSDT LONG @ 2.35

🎓 学习模式 (2/30)：跳过期望值检查
✅ 開倉成功: ZECUSDT LONG @ 45.20

當前持倉: 3/3（已满）
已归档 3 条信号记录到 ml_data/signals.csv
已归档 3 条仓位记录到 ml_data/positions.csv
```

---

## 🎯 下一步

### 学习阶段（0-30笔交易）

- ✅ 系统自动交易
- ✅ 收集特征数据
- ✅ 最多3个仓位
- ✅ 止盈止损保护
- ✅ 滑点保护（±0.2%）
- ✅ 日亏损上限（3%）

### 完整系统（31笔后）

- ✅ 启用期望值驱动
- ✅ 动态杠杆调整（3x-20x）
- ✅ XGBoost 预测增强
- ✅ 完整风险管理

---

## 📞 支持

如遇问题，请提供：
1. Railway 日志（`railway logs`）
2. 环境变量确认（不要泄露密钥）
3. 具体错误信息

**系统现已就绪，立即部署到 Railway 开始交易！** 🚀
