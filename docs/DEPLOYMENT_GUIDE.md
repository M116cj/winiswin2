# Railway 部署指南

## 系統要求
- **CPU**: 32 vCPU
- **內存**: 32 GB RAM
- **Python**: 3.11+
- **平台**: Railway / Docker / Linux

---

## Railway 部署步驟

### 1. 創建 Railway 項目
1. 登錄 [Railway.app](https://railway.app)
2. 點擊 "New Project"
3. 選擇 "Deploy from GitHub repo"
4. 連接此 Git 倉庫

### 2. 配置環境變量

在 Railway 項目設置中添加以下環境變量：

#### **必需變量**

```bash
# Binance API 配置
BINANCE_API_KEY=你的_Binance_API_Key
BINANCE_API_SECRET=你的_Binance_API_Secret

# Discord 通知配置
DISCORD_TOKEN=你的_Discord_Bot_Token

# 可選：是否使用測試網
BINANCE_TESTNET=false  # 生產環境設為 false
```

#### **可選變量**

```bash
# 最大信號數（每週期）
MAX_SIGNALS=5

# 掃描間隔（秒）
SCAN_INTERVAL=300

# 限流配置
RATE_LIMIT_REQUESTS=2400
RATE_LIMIT_PERIOD=60

# 熔斷器配置
CIRCUIT_BREAKER_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT=60
```

### 3. 配置資源

在 Railway 項目設置中：
- **CPU**: 設置為 32 vCPU
- **Memory**: 設置為 32 GB
- **Restart Policy**: Always

### 4. 部署

Railway 會自動：
1. 檢測 `requirements.txt`
2. 安裝 Python 依賴
3. 運行啟動命令：`python -m src.main`

---

## Binance API 配置

### 獲取 API 密鑰

1. 登錄 [Binance](https://www.binance.com)
2. 進入 "API Management"
3. 創建新的 API Key
4. 設置權限：
   - ✅ Enable Reading
   - ✅ Enable Spot & Margin Trading
   - ✅ Enable Futures（**必需**）
5. 記錄 API Key 和 Secret

### API 安全設置

1. **IP 白名單**（推薦）
   - 添加 Railway 服務器 IP
   - 限制訪問來源

2. **權限限制**
   - 不啟用 "Enable Withdrawals"
   - 不啟用 "Enable Internal Transfer"

---

## Discord Bot 配置

### 創建 Discord Bot

1. 訪問 [Discord Developer Portal](https://discord.com/developers/applications)
2. 創建新應用程序
3. 進入 "Bot" 標籤
4. 點擊 "Add Bot"
5. 複製 Bot Token

### Bot 權限設置

需要的權限：
- Send Messages
- Embed Links
- Read Message History

### 邀請 Bot 到服務器

1. 進入 "OAuth2" → "URL Generator"
2. 選擇 Scopes: `bot`
3. 選擇 Bot Permissions:
   - Send Messages
   - Embed Links
4. 複製生成的 URL
5. 在瀏覽器中打開 URL 並選擇服務器

---

## 驗證部署

### 檢查日誌

在 Railway 控制台查看日誌，應該看到：

```
============================================================
🚀 Winiswin2 v1 Enhanced 啟動中...
============================================================

✅ 配置驗證通過
🔧 初始化核心組件...
✅ Binance API 連接成功
✅ 數據服務初始化完成
✅ ML 預測器已就緒
✅ 系統初始化成功
============================================================
🎯 開始市場掃描循環...
============================================================
```

### 常見啟動日誌

**正常啟動**:
```
✅ Binance API 連接成功
✅ ML 預測器已就緒（或 ⚠️ ML 預測器未就緒，使用傳統策略）
✅ Discord Bot 已連接
📊 掃描到 648 個交易對
🔍 使用 32 核心並行分析...
```

**環境變量缺失**:
```
❌ 配置驗證失敗:
  - 缺少 BINANCE_API_SECRET 環境變量
  - 缺少 DISCORD_TOKEN 環境變量
```

---

## 性能監控

### 系統指標

每 5 分鐘自動輸出性能報告：

```
============================================================
📊 性能監控報告
============================================================
CPU: 45.2% (32 核心)
內存: 12.50/32.00 GB (39.1%)
運行時間: 2.50 小時
信號生成: 45 個
交易執行: 12 筆
API 調用: 1254 次
信號速率: 18.00 個/小時
============================================================
```

### Discord 通知

系統會發送以下通知：
- 🚀 系統啟動
- 🎯 交易信號（包含 ML 預測）
- ✅ 交易執行成功
- ❌ 交易執行失敗
- ⚠️  系統警報
- 👋 系統停止

---

## ML 模型訓練

### 自動訓練

系統會在累積 100+ 交易記錄後自動訓練 ML 模型。

### 手動訓練

如需手動訓練模型：

```python
from src.ml.model_trainer import XGBoostTrainer

trainer = XGBoostTrainer()
model, metrics = trainer.train()
trainer.save_model(model, metrics)
```

### 模型文件位置

- 模型: `data/models/xgboost_model.pkl`
- 指標: `data/models/model_metrics.json`
- 訓練數據: `data/trades/trades.jsonl`

---

## 故障排除

### 問題：系統無法連接 Binance API

**解決方案**:
1. 檢查 API Key 和 Secret 是否正確
2. 確認 API Key 已啟用 Futures 權限
3. 檢查 IP 白名單設置
4. 驗證網絡連接

### 問題：Discord 通知未發送

**解決方案**:
1. 確認 DISCORD_TOKEN 正確
2. 檢查 Bot 是否在服務器中
3. 驗證 Bot 權限
4. 查看日誌中的錯誤信息

### 問題：ML 模型未就緒

**解決方案**:
- 這是正常的，系統會使用傳統策略
- 累積 100+ 交易後會自動訓練模型
- 可以手動上傳已訓練的模型到 `data/models/`

### 問題：CPU 使用率低

**檢查**:
1. 確認 Railway 配置為 32 vCPU
2. 查看日誌中的並行分析線程數
3. 檢查是否有網絡瓶頸

---

## 數據備份

### 重要文件

定期備份以下文件：
- `data/trades/trades.jsonl` - 交易歷史
- `data/models/xgboost_model.pkl` - ML 模型
- `logs/trading_bot.log` - 日誌文件

### 自動備份（推薦）

在 Railway 中設置定期備份：
1. 使用 Railway Volumes
2. 配置 Cron 任務
3. 上傳到雲存儲（S3/GCS）

---

## 生產環境建議

### 安全性
- ✅ 啟用 IP 白名單
- ✅ 使用只讀 API Key（測試階段）
- ✅ 定期輪換密鑰
- ✅ 監控異常登錄

### 性能
- ✅ 調整 SCAN_INTERVAL 適應市場活躍度
- ✅ 監控 API 限流情況
- ✅ 定期檢查內存使用

### 監控
- ✅ 設置性能告警
- ✅ 監控錯誤率
- ✅ 追蹤交易成功率
- ✅ 定期審查 ML 模型性能

---

## 聯繫支援

遇到問題？
- 📧 Email: support@example.com
- 💬 Discord: [加入服務器]
- 📖 文檔: [查看完整文檔]

---

**部署檢查清單**

- [ ] Railway 項目已創建
- [ ] 32 vCPU / 32 GB 資源已配置
- [ ] BINANCE_API_KEY 已設置
- [ ] BINANCE_API_SECRET 已設置
- [ ] DISCORD_TOKEN 已設置
- [ ] API 權限已確認（Futures）
- [ ] Discord Bot 已邀請到服務器
- [ ] 日誌顯示系統正常啟動
- [ ] 性能監控正常運行
- [ ] Discord 通知正常接收

**準備就緒！** 🚀
