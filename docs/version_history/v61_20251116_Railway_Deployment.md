# Railway 部署指南

本文檔說明如何將 Winiswin2 v1 Enhanced 交易系統部署到 Railway。

## 🚀 快速部署步驟

### 1. 準備 Railway 帳號

1. 訪問 [Railway.app](https://railway.app)
2. 使用 GitHub 帳號登錄
3. 確保您的 GitHub 倉庫已創建並推送代碼

### 2. 創建 Railway 項目

#### 方法 A: 從 GitHub 部署（推薦）

1. 登錄 Railway 控制台
2. 點擊 **New Project**
3. 選擇 **Deploy from GitHub repo**
4. 選擇您的倉庫：`M116cj/winiswin2`
5. Railway 會自動檢測 Python 項目並開始部署

#### 方法 B: 使用 Railway CLI

```bash
# 安裝 Railway CLI
npm i -g @railway/cli

# 登錄
railway login

# 初始化項目
railway init

# 部署
railway up
```

### 3. 配置環境變數（重要！）

在 Railway 控制台中：

1. 進入您的服務
2. 點擊 **Variables** 標籤
3. 添加以下環境變數：

#### 必需變數：
```
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here
DISCORD_TOKEN=your_discord_bot_token_here
```

#### 推薦變數（測試用）：
```
BINANCE_TESTNET=true
TRADING_ENABLED=false
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
```

#### 可選變數：
```
MAX_POSITIONS=3
CYCLE_INTERVAL=60
MIN_CONFIDENCE=0.70
DISCORD_CHANNEL_ID=your_channel_id
```

### 4. 配置部署設置

根據您提供的 Railway 配置界面，按照以下設置：

#### **Builder 設置**
- **Builder**: `Railpack (Default)` ✅ 已自動配置

#### **Deploy 設置**
- **Start Command**: 
  ```
  python -m src.main
  ```
  
#### **Restart Policy**（重要！）
- **Restart Policy**: `On Failure` ✅
- **Max Restart Retries**: `10`

這確保系統在遇到錯誤時會自動重啟，最多重試 10 次。

#### **Regions**（區域設置）
- **Region**: `EU West (Amsterdam, Netherlands)` 或您偏好的區域
- **Replicas**: `1 Instance`

對於加密貨幣交易，建議選擇：
- **Asia Pacific (Singapore)** - 最接近 Binance 服務器
- **US West (Oregon)** - 美國用戶
- **EU West (Amsterdam)** - 歐洲用戶

#### **Resource Limits**（資源限制）
交易機器人建議配置：
- **CPU**: `1-2 vCPU`（足夠處理 648 個交易對）
- **Memory**: `1-2 GB`（根據實際使用調整）

如果運行過程中發現資源不足，可以在此調整。

#### **Networking**（網絡設置）

**注意**：此交易機器人不需要公網訪問，因為它是後台運行的服務。

❌ **不需要**設置以下項目：
- Generate Domain（不需要生成域名）
- Public Networking（不需要公網訪問）
- Custom Domain（不需要自定義域名）

✅ **如果需要**健康檢查（可選）：
- 保持 **Healthcheck Path** 為空

✅ **推薦**設置（對外部 API 調用有幫助）：
- **Static Outbound IPs**: 可以啟用，這樣 Binance 可以識別您的固定 IP（有助於白名單設置）

### 5. 高級配置（可選）

#### **Watch Paths**（觸發重新部署）
如果您只想在特定文件更改時重新部署，可以添加：
```
/src/**
/requirements.txt
```

這樣只有源代碼和依賴更改時才會觸發部署。

#### **Cron Schedule**（定時任務）
如果您想定時運行（例如每小時），可以設置：
```
0 * * * *
```
但對於持續運行的交易機器人，**不要**設置此項。

#### **Serverless**（無服務器模式）
❌ **不要啟用** - 交易機器人需要持續運行，不能使用無服務器模式。

### 6. 部署並驗證

#### 啟動部署
1. 完成上述配置後，點擊頁面頂部的 **Deploy** 或等待自動部署
2. 部署過程約需 2-5 分鐘

#### 檢查日誌
1. 進入 **Deployments** 標籤
2. 點擊最新的部署
3. 查看 **Build Logs** 和 **Deploy Logs**

**成功的標誌**：
```
✅ Python 依賴安裝完成
✅ 啟動命令執行
✅ 系統日誌顯示: "🚀 Winiswin2 v1 Enhanced 啟動中..."
✅ Binance API 連接成功
✅ Discord 機器人已連接
```

**失敗的標誌**：
```
❌ "缺少 BINANCE_API_KEY 環境變數"
   → 解決：在 Variables 中添加環境變數
   
❌ "ModuleNotFoundError"
   → 解決：檢查 requirements.txt 是否完整
   
❌ "Connection refused"
   → 解決：檢查 API 密鑰是否正確
```

### 7. 監控和維護

#### 查看實時日誌
```bash
# 使用 Railway CLI
railway logs
```

或在 Railway 控制台的 **Deployments** → **Logs** 標籤查看。

#### 重新部署
- **自動重新部署**：推送代碼到 GitHub 會自動觸發
- **手動重新部署**：在 Railway 控制台點擊 **Redeploy**

#### 停止服務
在 Railway 控制台：
1. 進入服務設置
2. 滾動到底部
3. 點擊 **Delete Service**（永久刪除）

或暫時停止（不刪除）：
1. 進入 **Deployments**
2. 點擊當前部署的 **...** 按鈕
3. 選擇 **Remove**

### 8. 成本估算

Railway 定價（2025 年）：
- **免費方案**: $5 免費額度/月（約 500 小時運行時間）
- **Pro 方案**: $20/月起（無限制運行時間）

**交易機器人預估成本**：
- CPU: 1 vCPU × 24h × 30d = 約 $5-10/月
- Memory: 1 GB × 24h × 30d = 約 $2-5/月
- **總計**: 約 $7-15/月（Pro 方案內）

## 🔧 故障排除

### 部署失敗

**問題**: "Build failed: No module named 'src'"
- **解決**: 確保 `railway.json` 中的啟動命令是 `python -m src.main`

**問題**: "Port binding failed"
- **解決**: 交易機器人不需要綁定端口，這是正常的。刪除任何端口綁定代碼。

### 運行時錯誤

**問題**: "API rate limit exceeded"
- **解決**: 檢查 `src/core/rate_limiter.py` 配置是否正確

**問題**: "Memory limit exceeded"
- **解決**: 在 Railway 控制台增加 Memory 限制到 2GB

### 環境變數問題

**問題**: "環境變數未生效"
- **解決**: 
  1. 確認在 Railway **Variables** 中正確添加
  2. 重新部署服務使變數生效
  3. 檢查變數名稱是否完全匹配（區分大小寫）

## 📊 生產環境建議

### 安全設置
1. ✅ 使用 Railway Variables 存儲 API 密鑰（不要寫在代碼中）
2. ✅ 啟用 Binance API IP 白名單（使用 Railway Static Outbound IPs）
3. ✅ 限制 Binance API 權限（只允許交易，不允許提現）
4. ✅ 定期輪換 API 密鑰

### 監控設置
1. ✅ 設置 Discord 通知接收交易提醒
2. ✅ 定期檢查 Railway 日誌
3. ✅ 監控賬戶餘額和持倉情況
4. ✅ 設置賬戶告警（餘額過低、異常交易等）

### 性能優化
1. ✅ 選擇靠近 Binance 服務器的區域（推薦新加坡）
2. ✅ 根據實際負載調整 CPU 和 Memory
3. ✅ 監控 API 請求頻率，避免超限
4. ✅ 優化代碼以減少不必要的 API 調用

### 備份策略
1. ✅ 定期備份交易記錄（存儲在 Railway Volume 或雲存儲）
2. ✅ 定期導出配置和策略參數
3. ✅ 使用版本控制（Git）管理代碼更改

## 🔗 相關資源

- [Railway 官方文檔](https://docs.railway.com)
- [Railway Python 部署指南](https://docs.railway.com/guides/python)
- [Binance API 文檔](https://binance-docs.github.io/apidocs/)
- [項目環境變量配置](./ENVIRONMENT_VARIABLES.md)

## ✅ 部署檢查清單

部署前請確認：

- [ ] GitHub 倉庫已創建並推送代碼
- [ ] 所有必需的環境變數已在 Railway 中設置
- [ ] 啟動命令設置為 `python -m src.main`
- [ ] Restart Policy 設置為 "On Failure"
- [ ] 已選擇合適的部署區域
- [ ] 資源限制設置合理（1-2 vCPU, 1-2 GB RAM）
- [ ] 已測試 Binance API 密鑰有效
- [ ] Discord 機器人 Token 有效
- [ ] 代碼中沒有硬編碼的密鑰
- [ ] `.gitignore` 已正確配置，不會提交敏感信息

完成上述配置後，您的交易系統將在 Railway 上 24/7 穩定運行！
