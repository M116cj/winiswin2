# 🚀 Railway 部署指南 - v3.2.5

**重要**：此系统**只能**在Railway上运行，Replit会封锁Binance API（451错误）。

---

## ⚡ 快速部署（推荐）

### 1️⃣ 准备Railway项目

```bash
# 确保你在Railway上已经创建了项目
# 项目地址: https://railway.app/
```

### 2️⃣ 连接Git仓库

1. 在Railway dashboard点击 **"New Project"**
2. 选择 **"Deploy from GitHub repo"**
3. 选择你的仓库
4. Railway会自动检测Python项目

### 3️⃣ 配置环境变量

在Railway项目设置中添加以下环境变量：

```bash
# Binance API（必需）
BINANCE_API_KEY=你的API密钥
BINANCE_API_SECRET=你的API密钥

# 交易配置
TRADING_ENABLED=False          # 设为True开启真实交易
BINANCE_TESTNET=False         # 正式网络
MAX_POSITIONS=1               # 小账户建议设为1

# Discord通知（可选）
DISCORD_TOKEN=你的Discord_Token
DISCORD_CHANNEL_ID=你的频道ID

# 日志级别
LOG_LEVEL=INFO
```

### 4️⃣ 部署

Railway会自动：
1. ✅ 检测 `requirements.txt`
2. ✅ 安装Python依赖
3. ✅ 使用 `nixpacks.toml` 配置
4. ✅ 运行 `python -m src.main`

### 5️⃣ 验证部署

查看Railway日志，确认系统正常运行：

```
✅ 成功标志：
🚀 高頻交易系統 v3.0 啟動中...
✅ Binance API 連接成功
🔄 交易週期開始
📊 分析完成，生成 XX 個信號
```

---

## 🔄 如何更新到最新版本

### **重要**：v3.2.5包含关键修复

**v3.2.5新功能**：
- ✅ 自动补足小于5 USDT的订单到最低要求
- ✅ 修复所有LSP类型错误
- ✅ 代码库完全清理

### 方法1：Git推送（推荐）

```bash
# 1. 提交最新代码
git add .
git commit -m "Update to v3.2.5 - Auto topup orders"
git push origin main

# 2. Railway会自动重新部署
```

### 方法2：手动重新部署

1. 在Railway dashboard找到你的项目
2. 点击 **"Deployments"** 标签
3. 点击 **"Redeploy"** 按钮

---

## 📋 检查Railway上的代码版本

查看Railway日志中的版本号：

```
✅ v3.2.5版本标志：
準備開倉: SOLUSDT LONG 數量: 0.03 槓桿: 4x 信心度: 70.00% 訂單價值: 5.00 USDT
                                                              ↑
                                                          显示订单价值
```

```
❌ 旧版本标志：
準備開倉: SOLUSDT LONG 數量: 0.02 槓桿: 4x 信心度: 70.00%
                                                 ↑
                                            缺少订单价值显示
```

如果看到旧版本标志，说明Railway上的代码未更新，需要重新部署。

---

## 🐛 常见问题

### 1. 订单被拒绝：-4164错误

**错误信息**：
```
code=-4164, msg=Order's notional must be no smaller than 5
```

**原因**：Railway上运行的是旧版本代码

**解决**：
```bash
# 重新部署最新代码
git push origin main
```

### 2. Railway日志显示451错误

**错误**：这是Replit的错误，不是Railway的

**解决**：确保你在Railway上部署，不是Replit

### 3. 账户余额43 USDT，所有订单都失败

**原因**：
- 旧版本：每个订单只有3-4 USDT（小于5 USDT最低要求）
- 新版本：自动补足到5 USDT

**解决**：
1. 部署v3.2.5最新代码
2. 设置 `MAX_POSITIONS=1`（小账户建议）

---

## 🎯 小账户配置建议（< 50 USDT）

```bash
# 环境变量配置
MAX_POSITIONS=1              # 只开1个仓位
TRADING_ENABLED=False        # 先观察，确认无误后开启
MIN_CONFIDENCE=0.60          # 提高信心度阈值

# 结果
# 账户43 USDT → 单仓位约36 USDT → 自动补足到5 USDT ✅
```

---

## 📊 v3.2.5更新内容

### 核心修复

1. **自动订单补足**
   - 检测订单价值 < 5 USDT
   - 自动补足到最低要求
   - 防止-4164错误

2. **LSP错误修复**
   - risk_manager.py：4个类型错误
   - model_trainer.py：3个sklearn参数错误

3. **代码库清理**
   - 归档26个旧文档到 `docs/archive/`
   - 删除4个临时脚本
   - 清理所有Python缓存

### 代码示例

```python
# src/services/trading_service.py (第73-84行)
notional_value = quantity * entry_price
if notional_value < 5.0:
    logger.info(
        f"💰 訂單價值不足5 USDT，自動補足 {symbol}: "
        f"{notional_value:.2f} USDT → 5.0 USDT"
    )
    quantity = 5.0 / entry_price
    quantity = await self._round_quantity(symbol, quantity)
    notional_value = quantity * entry_price
```

---

## ✅ 部署验证清单

部署后检查Railway日志：

- [ ] ✅ 显示版本号 v3.0
- [ ] ✅ Binance API连接成功
- [ ] ✅ 生成交易信号（每周期约60个）
- [ ] ✅ 日志显示"訂單價值: XX USDT"
- [ ] ✅ 无-4164错误
- [ ] ✅ 订单成功创建或进入虚拟仓位

---

## 🚨 紧急回滚

如果新版本有问题：

```bash
# 回滚到之前的版本
git revert HEAD
git push origin main
```

Railway会自动部署回滚版本。

---

## 📞 获取帮助

**查看日志**：
1. 登录Railway dashboard
2. 选择你的项目
3. 点击 "Deployments"
4. 查看实时日志

**关键日志位置**：
- 启动日志：系统初始化
- 周期日志：每60秒一次
- 错误日志：红色ERROR标记

---

## 🎉 部署完成

部署成功后，系统会：

1. ⏰ 每60秒扫描一次市场
2. 📊 分析600+交易对，生成60个信号
3. 🎯 选择排名前N的信号（根据MAX_POSITIONS）
4. 💰 自动补足小订单到5 USDT最低要求
5. 📝 记录所有数据到 `ml_data/`

**系统状态查看**：Railway日志会显示每个周期的完整信息。

祝交易顺利！🚀
