# Winiswin2 v1 Enhanced

高性能加密貨幣自動交易系統 - 基於 ICT/SMC 策略

## 🚀 快速部署

### Railway 部署（推薦用於生產環境）

1. **推送代碼到 GitHub**
   ```bash
   git add .
   git commit -m "準備部署到 Railway"
   git push origin main
   ```

2. **在 Railway 創建項目**
   - 訪問 [Railway.app](https://railway.app)
   - 選擇 "Deploy from GitHub repo"
   - 連接您的倉庫 `M116cj/winiswin2`

3. **配置 Railway 設置**
   
   在 Railway 控制台中設置：
   
   **Deploy 設置**:
   - Start Command: `python -m src.main`
   - Restart Policy: `On Failure`
   - Max Retries: `10`
   
   **環境變數** (Variables 標籤):
   ```
   BINANCE_API_KEY=your_api_key_here
   BINANCE_API_SECRET=your_api_secret_here
   DISCORD_TOKEN=your_discord_token_here
   BINANCE_TESTNET=true
   TRADING_ENABLED=false
   LOG_LEVEL=INFO
   PYTHONUNBUFFERED=1
   ```
   
   **資源配置**:
   - CPU: 1-2 vCPU
   - Memory: 1-2 GB
   - Region: Asia Pacific (Singapore) - 推薦最接近 Binance

4. **查看完整部署指南**
   
   詳細配置說明請參考: [`docs/RAILWAY_DEPLOYMENT.md`](docs/RAILWAY_DEPLOYMENT.md)

### Replit 部署（用於開發和測試）

1. 在 Replit Secrets 中設置環境變數
2. 點擊 Run 按鈕
3. 查看控制台輸出

## 📋 環境變數說明

詳細的環境變數配置指南: [`docs/ENVIRONMENT_VARIABLES.md`](docs/ENVIRONMENT_VARIABLES.md)

### 必需變數
- `BINANCE_API_KEY` - Binance API 密鑰
- `BINANCE_API_SECRET` - Binance API 私鑰
- `DISCORD_TOKEN` - Discord 機器人 Token

### 重要可選變數
- `BINANCE_TESTNET=true` - 使用測試網（強烈推薦初次使用）
- `TRADING_ENABLED=false` - 默認關閉交易（安全第一）
- `MAX_POSITIONS=3` - 最大同時持倉數
- `LOG_LEVEL=INFO` - 日誌級別

## 🎯 系統特性

- 📊 監控 648 個 Binance USDT 永續合約
- ⚡ 非同步高性能架構（asyncio + aiohttp）
- 🎲 動態風險管理（槓桿 3-20x，倉位 3%-13%）
- 🧠 ICT/SMC 策略引擎
- 🤖 Discord 實時通知
- 📈 38 特徵 ML 數據收集

## 📂 項目結構

```
winiswin2/
├── src/                      # 源代碼
│   ├── main.py              # 主程序入口
│   ├── config.py            # 配置管理
│   ├── clients/             # API 客戶端
│   ├── core/                # 核心基礎設施
│   ├── strategies/          # 交易策略
│   ├── services/            # 業務服務
│   └── utils/               # 工具函數
├── docs/                    # 文檔
│   ├── RAILWAY_DEPLOYMENT.md      # Railway 部署指南
│   └── ENVIRONMENT_VARIABLES.md   # 環境變數說明
├── data/                    # 數據目錄
├── models/                  # ML 模型目錄
├── requirements.txt         # Python 依賴
├── railway.json             # Railway 配置
├── nixpacks.toml            # Nixpacks 構建配置
└── .python-version          # Python 版本

```

## ⚠️ 重要提醒

1. **首次使用請設置 `BINANCE_TESTNET=true`** - 在測試網環境測試
2. **默認交易是關閉的** - 需要手動設置 `TRADING_ENABLED=true`
3. **API 密鑰權限** - 僅需要「期貨交易」權限，不要給予提現權限
4. **監控資金** - 定期檢查賬戶餘額和持倉情況

## 📊 當前開發狀態

**Version**: v1.0.0 (基礎框架)

**已完成**:
- ✅ 核心基礎設施（緩存、限流、熔斷器）
- ✅ Binance API 客戶端
- ✅ 技術指標工具
- ✅ Railway 部署配置

**待實現**:
- ⏳ ICT/SMC 策略引擎
- ⏳ 風險管理器
- ⏳ 交易執行服務
- ⏳ Discord 通知系統

## 📞 支持

如有問題，請查看:
- [環境變數配置指南](docs/ENVIRONMENT_VARIABLES.md)
- [Railway 部署指南](docs/RAILWAY_DEPLOYMENT.md)
- 系統日誌文件

## 📄 授權

此項目僅供個人使用和學習。
