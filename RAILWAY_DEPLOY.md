# 🚀 Railway 部署指南

## ⚠️ 為什麼必須使用 Railway？

**Replit 無法運行此交易系統！**

原因：Binance API 返回 **HTTP 451 錯誤**（地理位置限制）
- Replit 服務器位於被 Binance 限制的地區（美國或其他受限地區）
- **這不是代碼問題**，是 Binance 的地理政策
- **唯一解決方案**：部署到 Railway（服務器位於歐洲/亞洲允許地區）

---

## 📋 部署前準備

### 1. 確認您有以下賬號和信息

- ✅ **GitHub 賬號**（用於連接 Railway）
- ✅ **Railway 賬號**（註冊：https://railway.app）
- ✅ **Binance API 密鑰**：
  - `BINANCE_API_KEY`
  - `BINANCE_API_SECRET`
- ✅ **此代碼庫**（v3.17.6+）

### 2. 必需文件（已準備好）

```
✅ requirements.txt      # Python 依賴
✅ src/                  # 源代碼
✅ Procfile (可選)       # Railway 會自動檢測
✅ .python-version       # 可選：指定 Python 版本
```

---

## 🎯 方法 1：從 GitHub 部署（推薦）

### **步驟 1：推送代碼到 GitHub**

如果您還沒有 GitHub 倉庫：

```bash
# 1. 在 Replit Shell 中執行
git init
git add .
git commit -m "Deploy SelfLearningTrader v3.17.6 to Railway"

# 2. 在 GitHub 創建新倉庫（例如：trading-bot）
# 3. 連接並推送
git remote add origin https://github.com/YOUR_USERNAME/trading-bot.git
git branch -M main
git push -u origin main
```

### **步驟 2：在 Railway 創建項目**

1. 登入 https://railway.app
2. 點擊 **"New Project"**
3. 選擇 **"Deploy from GitHub repo"**
4. 授權 Railway 訪問您的 GitHub
5. 選擇您的 `trading-bot` 倉庫
6. Railway 會自動檢測 Python 項目並開始構建

### **步驟 3：配置環境變量（關鍵！）**

在 Railway 項目中：

1. 點擊您的服務
2. 進入 **"Variables"** 標籤
3. 添加以下變量：

```
BINANCE_API_KEY=您的_API_密鑰
BINANCE_API_SECRET=您的_API_密鑰
BINANCE_TESTNET=False
TRADING_ENABLED=True
```

**⚠️ 重要**：
- 不要在代碼中硬編碼 API 密鑰
- 確保 `BINANCE_API_SECRET` 已添加（Replit 缺少此密鑰）

### **步驟 4：等待部署完成**

- Railway 會自動安裝依賴（`requirements.txt`）
- 構建時間：約 2-3 分鐘
- 查看日誌確認啟動成功

### **步驟 5：驗證部署**

在 Railway **"Deployments"** → **"View Logs"** 中應該看到：

```
✅ Binance API 連接成功
✅ 查詢 Position Mode 成功
✅ 系統正常啟動
✅ 24/7 交易監控已激活
```

**不應該看到**：
- ❌ `HTTP 451 錯誤`
- ❌ `熔斷器阻斷`
- ❌ `地理位置限制`

---

## 🎯 方法 2：Railway CLI 部署

### **步驟 1：安裝 Railway CLI**

```bash
npm i -g @railway/cli
```

### **步驟 2：登入並初始化**

```bash
railway login
railway init
```

### **步驟 3：部署**

```bash
railway up
```

### **步驟 4：配置環境變量**

```bash
railway variables set BINANCE_API_KEY=您的_密鑰
railway variables set BINANCE_API_SECRET=您的_密鑰
railway variables set BINANCE_TESTNET=False
railway variables set TRADING_ENABLED=True
```

### **步驟 5：查看日誌**

```bash
railway logs
```

---

## 📊 Railway 項目配置

### **啟動命令（自動檢測）**

Railway 會自動檢測並運行：

```bash
python -m src.main
```

如需自定義，創建 `Procfile`：

```
worker: python -m src.main
```

### **Python 版本**

系統使用 Python 3.11+，Railway 會自動檢測 `requirements.txt`。

如需指定版本，創建 `.python-version`：

```
3.11
```

---

## 🔄 更新部署（推送新代碼）

每次修改代碼後：

```bash
git add .
git commit -m "Update trading strategy"
git push origin main
```

Railway 會自動檢測並重新部署（約 2-3 分鐘）。

---

## 💰 Railway 費用（2025）

- **免費額度**：每月 $5 試用額度
- **典型交易機器人成本**：$10-20/月
  - CPU 使用（策略計算）
  - 內存（數據處理）
  - 網絡（API 調用）

**實盤交易建議**：使用付費計劃確保 100% 正常運行時間。

---

## 🐛 常見問題

### **問題 1：仍然看到 HTTP 451 錯誤**

**原因**：環境變量未正確配置

**解決**：
1. 檢查 Railway Variables 中是否有 `BINANCE_API_KEY` 和 `BINANCE_API_SECRET`
2. 重新部署：Settings → Redeploy

---

### **問題 2：Application failed to respond**

**原因**：應用未正確啟動

**解決**：
1. 查看日誌：`railway logs`
2. 檢查 `requirements.txt` 是否完整
3. 確保 Python 版本 ≥ 3.11

---

### **問題 3：缺少 BINANCE_API_SECRET**

**症狀**：
```
❌ 缺少環境變量: BINANCE_API_SECRET
```

**解決**：
```bash
railway variables set BINANCE_API_SECRET=您的_密鑰
```

或在 Railway Web UI 中添加。

---

## ✅ 部署檢查清單

- [ ] GitHub 倉庫已創建並推送代碼
- [ ] Railway 項目已創建
- [ ] 環境變量已配置（API_KEY + API_SECRET）
- [ ] 部署成功（無 HTTP 451 錯誤）
- [ ] 日誌顯示 "Binance API 連接成功"
- [ ] 24/7 監控已啟動
- [ ] 測試模式驗證後再啟用實盤交易

---

## 🎯 下一步

1. **驗證部署**：確認日誌無錯誤
2. **測試模式**：先用 `BINANCE_TESTNET=True` 測試
3. **監控系統**：定期查看 Railway 日誌
4. **實盤交易**：確認策略穩定後啟用 `TRADING_ENABLED=True`

---

## 📚 相關資源

- **Railway 文檔**：https://docs.railway.com
- **Railway CLI**：https://docs.railway.com/develop/cli
- **Binance API 文檔**：https://binance-docs.github.io/apidocs/futures/en/

---

**🚀 您的交易系統將在 Railway 上 24/7 運行！**
