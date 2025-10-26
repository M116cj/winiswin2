# 🚀 Railway 部署指令

## 快速部署

### 1. 在 Railway Dashboard 设置环境变量

```bash
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_secret_key
BINANCE_TESTNET=false
TRADING_ENABLED=false
DISCORD_TOKEN=your_discord_token  # 可选
DISCORD_CHANNEL_ID=your_channel_id  # 可选
LOG_LEVEL=INFO
```

### 2. 部署命令

```bash
# 方法 1: 使用 Railway CLI
railway up

# 方法 2: 推送到 Git
git push railway main
```

### 3. 验证部署

```bash
# 查看日志
railway logs

# 查看实时日志
railway logs --follow
```

## 预期启动输出

```
🚀 高頻交易系統 v3.0 啟動中...
📌 代碼版本: 2025-10-25-v3.0 (期望值驅動+五維評分系統)
✅ 配置驗證通過
✅ Binance 連接成功  ← 重要！
✅ 數據服務已就緒
✅ 期望值計算器已就緒
✅ 數據歸檔器已就緒
✅ 系統初始化完成
🔍 開始掃描市場...
```

## 故障排查

### 如果看到 "451 错误"
- 这是正常的，**Replit 无法访问 Binance API**
- **必须在 Railway 上运行**

### 如果看到 "API Key 错误"
- 检查 Railway 环境变量是否正确设置
- 确认 API Key 有期货交易权限

## 建议的部署策略

### 阶段 1: 测试网（1-3 天）
```bash
BINANCE_TESTNET=true
TRADING_ENABLED=true
```

### 阶段 2: 主网模拟（1 周）
```bash
BINANCE_TESTNET=false
TRADING_ENABLED=false  # 模拟模式
```

### 阶段 3: 实盘（小规模）
```bash
BINANCE_TESTNET=false
TRADING_ENABLED=true
MAX_POSITIONS=1
```

## 数据收集

系统运行后，数据会自动保存到：
- `ml_data/signals.csv` - 所有信号记录
- `ml_data/positions.csv` - 所有仓位记录

累积 100+ 笔交易后即可训练 XGBoost 模型。

---

**重要**: 此系统设计为在 Railway (32 vCPU, 32GB) 上运行，Replit 环境仅用于代码开发。
