# ⚡ 快速部署到Railway - v3.2.5

## 🚨 重要提醒

**如果你的Railway上出现 -4164 错误（订单价值太小），说明运行的是旧版本代码。**

请按以下步骤立即更新：

---

## 🔄 立即更新到 v3.2.5

### 步骤1：确认本地代码是最新的

```bash
# 检查文件内容
grep -A5 "Binance最小訂單價值檢查" src/services/trading_service.py
```

应该看到：
```python
# Binance最小訂單價值檢查（5 USDT）- 不足則補足
notional_value = quantity * entry_price
if notional_value < 5.0:
    logger.info(
        f"💰 訂單價值不足5 USDT，自動補足 {symbol}: "
```

### 步骤2：推送到Git

在你的本地终端执行：

```bash
git add .
git commit -m "Deploy v3.2.5 - Auto topup fix"
git push origin main
```

### 步骤3：等待Railway自动部署

Railway会在1-2分钟内自动重新部署。

### 步骤4：验证部署

查看Railway日志，确认看到：

```
✅ 新版本（v3.2.5）：
準備開倉: SOLUSDT LONG 數量: 0.03 槓桿: 4x 信心度: 70.00% 訂單價值: 5.00 USDT
                                                              ↑↑↑
                                                          显示订单价值
```

**不再出现**：
```
❌ 旧版本：
code=-4164, msg=Order's notional must be no smaller than 5
```

---

## 📊 快速检查版本

| 检查点 | 旧版本 | v3.2.5 |
|--------|--------|--------|
| **日志格式** | `準備開倉: SOLUSDT LONG 數量: 0.02 槓桿: 4x 信心度: 70.00%` | `準備開倉: SOLUSDT LONG 數量: 0.03 槓桿: 4x 信心度: 70.00% 訂單價值: 5.00 USDT` |
| **-4164错误** | ❌ 频繁出现 | ✅ 不再出现 |
| **小订单处理** | ❌ 直接拒绝 | ✅ 自动补足到5 USDT |
| **补足日志** | ❌ 无 | ✅ `💰 訂單價值不足5 USDT，自動補足` |

---

## 🎯 小账户配置（43 USDT）

```bash
# Railway环境变量
MAX_POSITIONS=1              # 确保单仓位有足够价值
TRADING_ENABLED=False        # 先观察确认
```

**效果**：
- 账户：43 USDT
- 单仓位保证金：~8.7 USDT (20%)
- 杠杆：4x
- 订单价值：~35 USDT → ✅ 远超5 USDT最低要求

---

## ❓ 仍然有问题？

### 问题1：推送后Railway没有重新部署

**解决**：
1. 登录 Railway dashboard
2. 进入项目
3. 点击 "Deployments"
4. 点击 "Redeploy" 按钮

### 问题2：日志仍显示旧版本格式

**解决**：
在本地终端执行强制重新部署：
```bash
git commit --allow-empty -m "Force redeploy"
git push origin main
```

### 问题3：仍然看到-4164错误

**检查**：
1. 确认Railway上的分支是 `main`
2. 确认本地代码已推送：`git log origin/main`
3. 确认Railway连接的是正确的仓库

---

部署完成后，系统会自动补足所有小于5 USDT的订单！✅
