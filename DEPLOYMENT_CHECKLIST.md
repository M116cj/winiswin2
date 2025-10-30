# 🚀 部署檢查清單 - v3.18.4

## ✅ 部署前檢查

### 1. 代碼狀態
- [x] 所有功能已完成並測試
- [x] Binance API協議100%合規
- [x] Architect審查通過
- [x] 版本已鎖定（VERSION_LOCK_v3.18.4.md）

### 2. 環境準備
- [ ] GitHub倉庫已準備好
- [ ] Railway賬戶已設置
- [ ] Binance API密鑰已準備（生產環境）

### 3. 必需環境變量
```bash
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
SESSION_SECRET=your_session_secret_here
```

---

## 📝 部署步驟

### Step 1: 推送代碼到GitHub
```bash
# 1. 添加所有更改
git add .

# 2. 提交版本
git commit -m "v3.18.4: Production-ready stable version - Full Binance API compliance"

# 3. 推送到GitHub
git push origin main
```

### Step 2: Railway配置
1. 登錄 [Railway Dashboard](https://railway.app)
2. 創建新項目 → 從GitHub導入
3. 選擇您的倉庫
4. 配置環境變量：
   - 進入 `Variables` 標籤
   - 添加上述3個必需變量
5. Railway會自動開始部署

### Step 3: 驗證部署
1. 等待部署完成（通常2-3分鐘）
2. 檢查部署日誌：
   ```
   ✅ WebSocketManager啟動完成
   ✅ 監控交易對: 50個
   ✅ PositionController 24/7 監控已啟動
   ```
3. 確認無錯誤日誌

---

## 🔍 部署後監控

### 關鍵日誌檢查

#### 1. 系統啟動
```
✅ WebSocketManager啟動完成
📡 K線Feed: ✅
📡 價格Feed: ✅
📡 帳戶Feed: ✅
```

#### 2. 保證金監控
```
💰 保證金使用率: XX.X%
```
- 正常: <70%
- 注意: 70-85%
- 警告: >85%（會觸發全倉保護）

#### 3. 交易執行
```
🔄 交易週期 #X
📊 生成信號: X個
✅ 執行交易: symbol @ $price
```

#### 4. 倉位監控
```
🛡️ 倉位監控循環已啟動
📋 當前持倉: X個
```

---

## ⚠️ 常見問題處理

### 問題1: API錯誤 -4061
```
錯誤: Position Side does not match user's setting
解決: v3.18.4已修復，檢查是否使用最新版本
```

### 問題2: 熔斷器阻斷
```
錯誤: 🔴 熔斷器阻斷(失敗5次)，請60秒後重試
原因: Replit環境（被Binance阻止）
解決: 確認部署在Railway而非Replit
```

### 問題3: WebSocket斷線
```
日誌: ❌ WebSocket連接失敗
解決: 系統會自動重連（5-60秒指數退避）
```

### 問題4: 保證金使用率過高
```
日誌: 🚨 保證金使用率>85%
解決: 全倉保護會自動平倉虧損最大倉位
```

---

## 📊 性能基準

### 正常運行指標
```
CPU使用率: <30%
記憶體使用: <500MB
WebSocket延遲: <50ms
API響應時間: <200ms
```

### 交易性能
```
信號生成: 每60秒掃描一次
信號延遲: <1秒
下單延遲: <200ms
倉位更新: 實時（WebSocket）
```

---

## 🔐 安全檢查

### 部署後驗證
- [ ] API密鑰未在日誌中暴露
- [ ] 環境變量正確設置
- [ ] 無SQL注入風險
- [ ] 熔斷器正常工作

### 風險控制檢查
- [ ] 虧損熔斷功能啟用（99%）
- [ ] 全倉保護功能啟用（85%）
- [ ] 單倉上限設置（50%權益）
- [ ] 最小倉位限制（10 USDT）

---

## 📈 建議監控頻率

### 第一天（部署後24小時）
- ✅ 每30分鐘檢查一次日誌
- ✅ 監控保證金使用率
- ✅ 確認交易正常執行

### 第一週
- ✅ 每天檢查2-3次
- ✅ 記錄異常情況
- ✅ 優化策略參數

### 穩定期（一週後）
- ✅ 每天檢查1次
- ✅ 週報分析
- ✅ 按需調整

---

## 🎯 成功指標

### 部署成功標誌
- ✅ Railway顯示 "Deployed"
- ✅ 日誌無致命錯誤
- ✅ WebSocket連接穩定
- ✅ 至少執行1筆交易

### 運行穩定標誌
- ✅ 連續運行24小時無崩潰
- ✅ WebSocket無頻繁斷線
- ✅ API請求成功率>95%
- ✅ 保證金使用率<85%

---

## 📞 緊急聯繫

### Railway問題
- Dashboard: https://railway.app
- 日誌: 項目 → Deployments → Logs

### Binance API問題
- 文檔: https://developers.binance.com
- 狀態: https://www.binance.com/en/support/announcement

---

## 🔄 回滾計劃

### 如果部署失敗
```bash
# 1. 停止Railway部署
Railway Dashboard → Settings → Pause Deployment

# 2. 回滾代碼
git revert HEAD
git push origin main

# 3. Railway自動重新部署上一版本
```

### 緊急關閉
```bash
Railway Dashboard → Settings → Delete Service
```

---

## ✅ 最終確認

部署前請確認：
- [ ] 已閱讀此檢查清單
- [ ] 已準備好所有環境變量
- [ ] 已了解監控要點
- [ ] 已準備好應急方案

**準備就緒？開始部署！** 🚀

```bash
git add .
git commit -m "v3.18.4: Production deployment"
git push origin main
```
