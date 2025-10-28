# 🚀 SelfLearningTrader v3.17+ Railway 部署指南

## 📋 部署前檢查清單

### ✅ 系統配置確認
- **交易狀態**: ✅ 已啟用 (TRADING_ENABLED=true)
- **監控範圍**: ✅ 所有 USDT 永續合約 (TOP_LIQUIDITY_SYMBOLS=999)
- **最大倉位**: ✅ 999 個（無限制）
- **槓桿控制**: ✅ 無上限（基於勝率 × 信心度）

### ✅ 核心功能
- ✅ 無限制槓桿（勝率 70% + 信心度 100% → 24x+）
- ✅ 10 USDT 最小倉位（符合 Binance 規格）
- ✅ 動態 SL/TP（高槓桿 → 寬止損）
- ✅ 24/7 倉位監控（2 秒週期）
- ✅ 100% 虧損熔斷（PnL ≤ -99% 立即平倉）
- ✅ 100 分制模型評級（6 大維度）
- ✅ 每日自動報告（JSON + Markdown）

---

## 🔧 Railway 部署步驟

### 1️⃣ 創建 Railway 專案
1. 訪問 [Railway.app](https://railway.app)
2. 登入並創建新專案
3. 選擇「Deploy from GitHub repo」
4. 連接您的 GitHub 倉庫

### 2️⃣ 設置環境變量

在 Railway 專案的「Variables」頁面添加以下環境變量：

#### 🔑 必需變量（Binance API）
```bash
BINANCE_API_KEY=your_actual_api_key_here
BINANCE_API_SECRET=your_actual_api_secret_here
BINANCE_TESTNET=false
```

#### 🎯 核心交易設置
```bash
TRADING_ENABLED=true
MAX_POSITIONS=999
CYCLE_INTERVAL=60
```

#### 📊 監控配置（所有 USDT 合約）
```bash
SCAN_INTERVAL=60
TOP_LIQUIDITY_SYMBOLS=999
```

#### 💡 開倉條件
```bash
MIN_WIN_PROBABILITY=0.55
MIN_CONFIDENCE=0.50
MIN_RR_RATIO=1.0
MAX_RR_RATIO=2.0
```

#### 💰 倉位計算
```bash
EQUITY_USAGE_RATIO=0.8
MIN_NOTIONAL_VALUE=10.0
MIN_STOP_DISTANCE_PCT=0.003
```

#### 🛡️ 倉位監控
```bash
POSITION_MONITOR_ENABLED=true
POSITION_MONITOR_INTERVAL=2
RISK_KILL_THRESHOLD=0.99
```

#### 🎨 動態 SL/TP
```bash
SLTP_SCALE_FACTOR=0.05
SLTP_MAX_SCALE=3.0
```

#### 📈 模型評級
```bash
MODEL_RATING_ENABLED=true
ENABLE_DAILY_REPORT=true
REPORTS_DIR=reports/daily
RATING_LOSS_PENALTY=15.0
```

#### ⚙️ 系統設置
```bash
LOG_LEVEL=INFO
MAX_WORKERS=4
```

#### 📢 Discord 通知（可選）
```bash
# DISCORD_TOKEN=your_discord_bot_token
# DISCORD_CHANNEL_ID=your_channel_id
```

### 3️⃣ 部署
1. Railway 會自動檢測 `railway.toml` 配置
2. 點擊「Deploy」開始部署
3. 等待構建完成（約 2-3 分鐘）

### 4️⃣ 驗證部署
查看 Railway 日誌，確認以下輸出：

```
🚀 SelfLearningTrader v3.17+ 啟動中...
📌 核心理念: 模型擁有無限制槓桿控制權，唯一準則是勝率 × 信心度
✅ 配置驗證通過
✅ 交易已啟用 (trading_enabled: True)
✅ Binance API 連接成功
📊 掃描到 XXX 個 USDT 永續合約，監控前 999 個
🔄 UnifiedScheduler 啟動成功
```

---

## 📊 監控和管理

### 查看日誌
```bash
# Railway 控制台 → Deployments → View Logs
# 或使用 Railway CLI:
railway logs
```

### 檢查倉位
系統每 2 秒自動監控所有倉位，PnL ≤ -99% 自動平倉。

### 每日報告
報告自動生成在 `reports/daily/` 目錄：
- `model_rating_YYYYMMDD.json` - JSON 格式評級
- `model_rating_YYYYMMDD.md` - Markdown 格式報告

---

## ⚠️ 重要安全提示

### API 密鑰權限
確保 Binance API 密鑰配置：
- ✅ 啟用「合約交易」權限
- ✅ 設置 IP 白名單（Railway IP）
- ✅ 啟用雙重驗證
- ❌ **不要**啟用「提現」權限

### 風險控制
系統內建多層保護：
1. **100% 虧損熔斷** - PnL ≤ -99% 立即平倉
2. **動態 SL/TP** - 高槓桿自動放寬止損範圍
3. **信心度過濾** - 低於 50% 信心度不開倉
4. **勝率門檻** - 低於 55% 預測勝率不開倉

### 資金管理建議
- 初始測試建議使用小額資金（如 100-500 USDT）
- 監控前 24-48 小時表現
- 根據模型評級調整參數

---

## 🔄 更新和維護

### 更新代碼
```bash
# 推送到 GitHub
git add .
git commit -m "Update trading parameters"
git push

# Railway 會自動重新部署
```

### 調整參數
在 Railway Variables 中修改環境變量，保存後自動重啟。

### 緊急停止
```bash
# 方法 1: Railway 控制台停止服務
# 方法 2: 設置 TRADING_ENABLED=false
```

---

## 📞 故障排查

### 常見問題

#### 1. 無法連接 Binance API
- 檢查 API 密鑰是否正確
- 確認 IP 白名單包含 Railway IP
- 驗證 API 權限已啟用「合約交易」

#### 2. 沒有生成交易信號
- 檢查市場狀態（震盪市場不交易）
- 降低 MIN_CONFIDENCE（如 0.40）
- 降低 MIN_WIN_PROBABILITY（如 0.50）

#### 3. 倉位無法開啟
- 確認帳戶餘額 ≥ 10 USDT
- 檢查交易對是否支援
- 查看日誌中的具體錯誤信息

---

## 📈 性能優化

### 高頻監控
```bash
POSITION_MONITOR_INTERVAL=1  # 1 秒極速檢查
SCAN_INTERVAL=30              # 30 秒掃描週期
```

### 記憶體優化
```bash
MAX_WORKERS=2                 # 降低並發數（Railway 512MB 限制）
TOP_LIQUIDITY_SYMBOLS=100     # 減少監控交易對數量
```

---

## ✅ 部署完成確認

部署成功後，您應該看到：
- ✅ Railway 服務狀態為「Running」
- ✅ 日誌顯示「Binance API 連接成功」
- ✅ 系統開始掃描 USDT 永續合約
- ✅ 每 60 秒執行一次交易週期

**祝您交易順利！** 🚀

---

*SelfLearningTrader v3.17+ - 完全自主的高頻交易系統*
