# 🚀 Railway 部署完整指南

## 📋 当前系统状态

### ✅ 已完成验证

所有系统组件已通过完整性验证：

- ✅ 核心模块导入正常
- ✅ 配置参数正确（200个高波动率交易对 + 32核并行）
- ✅ 文件结构完整
- ✅ 版本标识：**2025-10-25-v2.0**
- ✅ 无遗留代码

### 📌 项目信息

- **项目 ID**: `ef7a7a00-69c2-4ed7-aac6-58efb6a60587`
- **服务 ID**: `65a8c8d7-b734-4bcf-bd04-13b83f95ba87`
- **环境 ID**: `7cdf5c02-eb2a-42cb-b419-924aae71ff53`
- **项目名称**: `skillful-perfection`
- **服务名称**: `winiswin2`

---

## 🎯 重新部署步骤

### 方法 1：Railway 控制台手动部署（推荐）

1. **登录 Railway**
   - 访问: https://railway.app/
   - 进入项目: `skillful-perfection`

2. **触发重新部署**
   - 选择服务: `winiswin2`
   - 点击右上角的 **"Redeploy"** 按钮
   - 或者点击 **"..."** 菜单选择 **"Redeploy"**

3. **等待部署完成**
   - 构建通常需要 2-3 分钟
   - 部署成功后状态会显示为 **SUCCESS ✅**

4. **验证版本**
   - 点击 **"View Logs"** 查看日志
   - 查找以下关键标识：
     ```
     📌 代碼版本: 2025-10-25-v2.0 (200個高波動率交易對 + 32核並行)
     ```

### 方法 2：使用监控脚本

```bash
# 检查当前部署状态
python3 monitor_railway.py

# 持续监控模式（每10秒检查一次）
python3 monitor_railway.py --monitor --interval 10

# 自定义监控参数
python3 monitor_railway.py --monitor --interval 15 --max-attempts 40
```

---

## 🔍 验证清单

部署完成后，请在 Railway 日志中确认以下内容：

### 启动阶段验证

```
✓ 版本标识
  📌 代碼版本: 2025-10-25-v2.0 (200個高波動率交易對 + 32核並行)

✓ 配置验证
  ✅ 配置驗證通過
  binance_testnet: False
  trading_enabled: False
  max_positions: 3

✓ API 连接
  ✅ Binance API 連接成功
  成功加載 511 個交易對

✓ 组件初始化
  ✅ 智能數據管理器已就緒
     - 1h: 每小時掃描（趨勢確認）
     - 15m: 每15分鐘掃描（趨勢確認）
     - 5m/1m: 高頻掃描（入場信號）
```

### 运行阶段验证

```
✓ 市场扫描
  🔍 開始掃描市場，目標選擇前 200 個高波動率交易對...
  📊 ✅ 已選擇 200 個高波動率交易對 (平均波動率: X.XX%)

✓ 波动率排名
  📈 波動率最高的前10個交易對:
    #1 XXXUSDT: XXXX.XXXX USDT (24h波動: XX.XX%)
    #2 XXXUSDT: XXXX.XXXX USDT (24h波動: XX.XX%)
    ...

✓ 并行分析
  🔍 使用 32 核心並行分析 200 個高波動率交易對...

✓ 时间框架调度
  ⏰ 時間框架調度狀態:
    1h: 間隔=3600, ...
    15m: 間隔=900, ...
    5m: 間隔=60, ...
```

---

## ❌ 旧版本识别

如果看到以下日志，说明运行的是**旧版本**，需要重新部署：

```
❌ 不应该看到:
  📈 獲取前 5 個交易對價格:
    BTCUSDT: $XXXXX
    ETHUSDT: $XXXX
```

---

## ⚠️ 常见问题处理

### Q1: 部署后立即崩溃 (CRASHED)

**可能原因:**
- Binance API 地区限制（HTTP 451）
- 环境变量未正确设置
- API 密钥无效

**解决方案:**
1. 确认 Railway 服务器区域为**亚洲**（新加坡/东京）
2. 验证环境变量:
   - `BINANCE_API_KEY` 或 `BINANCE_KEY`
   - `BINANCE_API_SECRET` 或 `BINANCE_SECRET_KEY`
   - `DISCORD_TOKEN` 或 `DISCORD_BOT_TOKEN`
   - `SESSION_SECRET`

### Q2: 部署成功但没有看到新日志

**可能原因:**
- 正在查看旧的缓存日志
- GitHub 代码未更新

**解决方案:**
1. 刷新 Railway 日志页面
2. 确认 GitHub 仓库有最新代码
3. 手动触发重新部署

### Q3: 无法连接 Binance API (HTTP 451)

**原因:**
美国地区无法访问 Binance API

**解决方案:**
在 Railway 项目设置中:
1. 进入 **Settings** → **Environment**
2. 更改 **Region** 为:
   - 🇸🇬 Singapore (推荐)
   - 🇯🇵 Tokyo
   - 🇭🇰 Hong Kong

---

## 🔧 本地测试工具

### 1. 系统完整性验证
```bash
python3 verify_system.py
```

### 2. Railway 部署监控
```bash
python3 monitor_railway.py
```

### 3. 本地运行测试
```bash
python -m src.main
```

---

## 📊 性能指标

### 预期资源使用

- **CPU**: 32 vCPU (Railway Pro/Scale plan)
- **内存**: 32 GB RAM
- **网络**: 每分钟约 200-500 API 请求

### 监控要点

- **交易对数量**: 应该是 200 个（不是 5 个）
- **并行核心**: 32 核心
- **扫描间隔**: 
  - 1h: 每小时
  - 15m: 每15分钟
  - 5m: 每分钟

---

## 🎯 成功标志

当您在 Railway 日志中看到以下所有内容时，系统正常运行：

- ✅ `📌 代碼版本: 2025-10-25-v2.0`
- ✅ `已選擇 200 個高波動率交易對`
- ✅ `使用 32 核心並行分析`
- ✅ `波動率最高的前10個交易對`（包含具体价格和波动率）
- ✅ `時間框架調度狀態`（显示三个时间框架）

---

## 📞 技术支持

### 有用的命令

```bash
# 检查 Git 状态
git status
git log -1 --oneline

# 验证系统
python3 verify_system.py

# 监控 Railway
python3 monitor_railway.py --monitor

# 查看环境变量（安全）
env | grep -E "BINANCE|DISCORD|SESSION" | sed 's/=.*/=***/'
```

### 调试技巧

1. **查看完整日志**: Railway 控制台 → Deployments → 点击最新部署 → View Logs
2. **检查环境变量**: Settings → Variables
3. **监控资源使用**: Metrics 标签页
4. **查看构建日志**: Deployments → Build Logs

---

## 📅 维护建议

### 每日检查
- ✓ 检查 Railway 日志确认系统正常运行
- ✓ 验证交易信号生成数量
- ✓ 监控资源使用情况

### 每周检查
- ✓ 审查 ML 模型性能
- ✓ 更新依赖包（如需要）
- ✓ 备份交易数据

### 每月检查
- ✓ 重新训练 ML 模型
- ✓ 优化策略参数
- ✓ 审查整体性能报告

---

## 🔐 安全建议

1. **永远不要**在代码中硬编码 API 密钥
2. **定期轮换** API 密钥（每月一次）
3. **启用 IP 白名单**（如 Binance 支持）
4. **使用只读密钥**进行测试
5. **监控异常登录**和 API 调用

---

**最后更新**: 2025-10-25  
**版本**: 2.0  
**状态**: ✅ 生产就绪
