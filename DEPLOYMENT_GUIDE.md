# 🚀 V3.0 系統部署指南

## 部署前檢查清單

### 環境準備

#### 1. 系統要求
- **Python**: 3.11+
- **CPU**: 建議 32 vCPU（最低 8 vCPU）
- **記憶體**: 建議 32GB（最低 8GB）
- **磁盤空間**: 至少 10GB（用於日誌和數據歸檔）

#### 2. 必需的環境變量
```bash
# Binance API（必需）
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"

# Discord 通知（可選）
export DISCORD_TOKEN="your_discord_token_here"
export DISCORD_CHANNEL_ID="your_channel_id_here"

# 交易模式
export BINANCE_TESTNET="false"  # true=測試網，false=主網
export TRADING_ENABLED="false"  # true=實盤交易，false=模擬模式

# 系統配置（可選）
export MAX_POSITIONS="3"
export CYCLE_INTERVAL="60"
export LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR
```

#### 3. 創建必要的目錄
```bash
mkdir -p data/logs
mkdir -p ml_data
mkdir -p data
```

---

## Railway 部署步驟

### 步驟 1: 創建新項目
```bash
# 初始化 Railway 項目
railway init

# 鏈接到現有項目
railway link
```

### 步驟 2: 設置環境變量
在 Railway Dashboard 中設置：
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `DISCORD_TOKEN`（可選）
- `DISCORD_CHANNEL_ID`（可選）
- `BINANCE_TESTNET=false`
- `TRADING_ENABLED=false`（首次部署建議先使用模擬模式）
- `LOG_LEVEL=INFO`

### 步驟 3: 配置資源
推薦配置：
- **vCPU**: 32 vCPU
- **記憶體**: 32GB
- **磁盤**: 10GB

### 步驟 4: 部署
```bash
# 推送代碼
git push origin main

# 或使用 Railway CLI
railway up
```

### 步驟 5: 監控啟動
```bash
# 查看日誌
railway logs

# 或
railway run python -m src.main
```

---

## 啟動順序與預期輸出

### 正常啟動流程

#### 1. 初始化階段（約 5-10 秒）
```
🚀 高頻交易系統 v3.0 啟動中...
📌 代碼版本: 2025-10-25-v3.0 (期望值驅動+五維評分系統)
✅ 配置驗證通過
✅ Binance 連接成功
✅ 數據服務已就緒
✅ 智能數據管理器已就緒
✅ 期望值計算器已就緒 (窗口大小: 30 筆交易)
✅ 數據歸檔器已就緒 (目錄: ml_data)
✅ ML 預測器已就緒
✅ Discord Bot 已連接
✅ 系統初始化完成
```

#### 2. 首次掃描（約 10-30 秒）
```
🔄 交易週期開始
⏰ 時間框架調度狀態:
  1h: 需掃描=是
  15m: 需掃描=是
  5m: 需掃描=是
🔍 開始掃描市場，目標選擇前 200 個高流動性交易對...
📊 ✅ 已選擇 200 個高流動性交易對
📈 流動性最高的前10個交易對:
  #1 BTCUSDT: 65000.0000 USDT (24h交易額: $50,000,000,000)
  ...
🔍 使用 32 核心並行分析 200 個高流動性交易對...
```

#### 3. 信號生成（若有信號）
```
🎯 生成 3 個交易信號
  #1 BTCUSDT LONG 信心度 78.50%
  #2 ETHUSDT LONG 信心度 72.30%
  #3 SOLUSDT SHORT 信心度 68.90%
```

#### 4. 期望值檢查（首次運行）
```
✅ 期望值檢查通過 - 期望值: 1.25%, 盈虧比: 1.80, 建議槓桿: 12x
```
或（交易記錄不足時）
```
⚠️  交易記錄不足（0/30），使用勝率驅動模式
```

#### 5. 週期完成
```
✅ 數據已刷新到磁盤
✅ 週期完成，耗時: 25.34 秒
⏳ 等待 60 秒...
```

---

## 驗證部署成功

### 檢查清單

#### 1. 日誌檢查
```bash
# Railway
railway logs

# 本地
tail -f data/logs/trading_bot.log
```

**預期看到**：
- ✅ "系統初始化完成"
- ✅ "已選擇 200 個高流動性交易對"
- ✅ "週期完成"
- ❌ 無 "ERROR" 或 "CRITICAL" 級別錯誤

#### 2. Discord 通知檢查
- ✅ 收到 "🚀 交易系統已啟動" 消息
- ✅ 收到交易信號通知（若有信號）

#### 3. 數據歸檔檢查
```bash
# Railway
railway run ls -la ml_data/

# 本地
ls -la ml_data/
```

**預期看到**：
- `signals.csv` - 信號記錄
- `positions.csv` - 倉位記錄（若有交易）

#### 4. 性能指標檢查
```bash
# 查看系統資源使用
railway ps

# 或本地
htop
```

**預期**：
- CPU 使用率：分析時 ~80-100%（32 核心並行），待機時 <10%
- 記憶體使用：~2-4GB
- 網絡：正常 API 請求

---

## 常見問題排查

### 問題 1: "無法連接到 Binance API"

**可能原因**：
1. API Key 錯誤
2. IP 限制
3. 網絡問題

**解決方案**：
```bash
# 驗證 API Key
railway run python -c "import os; print(os.getenv('BINANCE_API_KEY'))"

# 測試 Binance 連接
railway run python -c "
from src.clients.binance_client import BinanceClient
import asyncio
async def test():
    client = BinanceClient()
    result = await client.test_connection()
    print('連接成功' if result else '連接失敗')
asyncio.run(test())
"
```

### 問題 2: "Discord Bot 連接失敗"

**可能原因**：
1. Discord Token 錯誤
2. Bot 權限不足

**解決方案**：
1. 檢查 Token 是否正確
2. 確保 Bot 有 "Send Messages" 權限
3. 檢查 Channel ID 是否正確

### 問題 3: "未生成交易信號"

**正常情況**：
- 市場無明確趨勢
- 信心度不足（< 55%）
- 期望值檢查未通過

**調試方法**：
```bash
# 設置 DEBUG 級別日誌
export LOG_LEVEL=DEBUG
railway restart

# 查看詳細拒絕原因
railway logs | grep "拒絕"
```

### 問題 4: "期望值為負，禁止開倉"

**原因**：
- 最近 30 筆交易期望值為負
- 策略需要優化

**解決方案**：
1. 查看交易記錄
2. 分析虧損原因
3. 調整策略參數或暫停交易

---

## 配置調優指南

### 降低信號門檻（增加信號數量）
```python
# src/config.py
MIN_CONFIDENCE = 0.50  # 從 0.55 降至 0.50
```

### 增加監控對象數量
```python
# src/config.py
TOP_VOLATILITY_SYMBOLS = 300  # 從 200 增至 300
```

### 調整期望值窗口
```python
# src/config.py
EXPECTANCY_WINDOW = 20  # 從 30 減至 20（更快適應市場）
```

### 調整熔斷參數
```python
# src/config.py
CONSECUTIVE_LOSS_LIMIT = 3  # 從 5 減至 3（更保守）
DAILY_LOSS_LIMIT_PCT = 0.02  # 從 0.03 減至 0.02（2% 日虧損上限）
```

---

## 安全建議

### 1. API Key 安全
- ✅ 使用環境變量，不要硬編碼
- ✅ 限制 API Key IP 白名單
- ✅ 設置 API Key 只有交易權限，無提現權限

### 2. 風險控制
- ✅ **首次部署使用測試網**（BINANCE_TESTNET=true）
- ✅ **測試通過後使用模擬模式**（TRADING_ENABLED=false）
- ✅ **觀察 1 週後再啟用實盤交易**

### 3. 監控設置
- ✅ 設置 Discord 通知
- ✅ 定期查看日誌
- ✅ 監控數據歸檔文件
- ✅ 設置異常告警

---

## 漸進式部署策略

### 階段 1: 測試網驗證（1-3 天）
```bash
export BINANCE_TESTNET="true"
export TRADING_ENABLED="true"
export MAX_POSITIONS="1"
```

**驗證**：
- 系統穩定性
- 信號質量
- 期望值計算正確性

### 階段 2: 主網模擬（1 週）
```bash
export BINANCE_TESTNET="false"
export TRADING_ENABLED="false"  # 模擬模式
export MAX_POSITIONS="3"
```

**驗證**：
- 真實市場數據表現
- 數據歸檔完整性
- 期望值指標變化

### 階段 3: 小規模實盤（2 週）
```bash
export BINANCE_TESTNET="false"
export TRADING_ENABLED="true"
export MAX_POSITIONS="1"  # 限制 1 個倉位
```

**驗證**：
- 實際交易執行
- 盈虧表現
- 熔斷機制是否觸發

### 階段 4: 全規模生產
```bash
export BINANCE_TESTNET="false"
export TRADING_ENABLED="true"
export MAX_POSITIONS="3"  # 完整倉位
```

**持續監控**：
- 每日查看期望值指標
- 每週查看盈虧報告
- 每月優化策略參數

---

## 回滾計劃

### 如需回滾到 v2.3

```bash
# 1. 切換到 v2.3 分支
git checkout v2.3

# 2. 重新部署
railway up

# 3. 驗證
railway logs
```

### 數據遷移

v3.0 向後兼容 v2.3 的數據格式，無需特殊遷移。

---

## 支持與聯絡

- **日誌位置**: `data/logs/trading_bot.log`
- **數據歸檔**: `ml_data/signals.csv`, `ml_data/positions.csv`
- **系統文檔**: `SYSTEM_V3_README.md`
- **升級摘要**: `UPGRADE_V3_SUMMARY.md`

---

## 最後檢查

部署前請確認：

- [ ] 環境變量已正確設置
- [ ] 目錄已創建（data/logs, ml_data）
- [ ] Python 依賴已安裝
- [ ] 測試網測試通過
- [ ] Discord 通知正常
- [ ] 日誌輸出正常
- [ ] 數據歸檔功能正常
- [ ] 已閱讀並理解風險控制機制

**✅ 全部確認後，可以開始部署！**

---

部署日期: _____________  
部署人員: _____________  
環境: [ ] 測試網 [ ] 主網  
模式: [ ] 模擬 [ ] 實盤  
