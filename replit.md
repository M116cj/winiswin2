# Winiswin2 v1 Enhanced - 高性能加密貨幣自動交易系統

## 專案概述

這是一個基於 ICT/SMC 策略的高性能加密貨幣自動交易系統，專為 Binance USDT 永續合約設計。

### 核心特性

- 📊 **全市場監控**: 監控全部 648 個 Binance USDT 永續合約
- ⚡ **差異化掃描**: 1h/15m 低頻緩存，5m/1m 高頻入場（NEW!）
- 🎯 **ICT/SMC 策略**: 多時間框架分析，專注 1:1-1:2 盈虧比
- 🚀 **32 核心並行**: 充分利用 Railway 32vCPU 資源
- 🎲 **動態風險管理**: 槓桿 3-20x，倉位 3%-13%
- 🤖 **Discord 通知**: 實時交易信號和狀態更新
- 🧠 **XGBoost ML**: 39 特徵預測，GPU 加速訓練

### 最新更新（2025-10-25）

#### ✨ 差異化時間框架掃描系統

**問題**：傳統方法所有時間框架同頻掃描 → 浪費 API 配額

**解決方案**：智能調度不同時間框架
- **1h**：每小時掃描一次（趨勢確認）
- **15m**：每15分鐘掃描一次（趨勢確認）
- **5m/1m**：高頻掃描（入場信號）

**效果**：
- ✅ API 效率提升 5 倍（從 40 個 → 200 個交易對）
- ✅ 真正超高頻交易（5m 每分鐘更新）
- ✅ 智能緩存（1h/15m 緩存至下次更新時間）

**詳細文檔**：
- [完整監控指南](docs/FULL_MONITORING_GUIDE.md) - 多 API 配置與全幣種監控
- [高頻交易指南](docs/HIGH_FREQUENCY_TRADING_GUIDE.md) - 差異化掃描策略詳解
- [API 優化總結](docs/API_OPTIMIZATION_SUMMARY.md) - 性能優化對比

### 技術架構

```
src/
├── main.py                 # 主程序入口
├── config.py               # 全局配置
├── clients/                # API 客戶端
│   └── binance_client.py   # Binance API 封裝
├── core/                   # 核心基礎設施
│   ├── cache_manager.py    # 緩存管理
│   ├── rate_limiter.py     # API 限流
│   └── circuit_breaker.py  # 熔斷器
├── strategies/             # 策略層
├── services/               # 服務層
├── managers/               # 業務管理
├── integrations/           # 第三方集成
├── monitoring/             # 監控
└── utils/                  # 工具
    ├── indicators.py       # 技術指標
    └── helpers.py          # 輔助函數
```

### 環境變量配置

在 Replit Secrets 中設置以下變量：

**必需變量：**
- `BINANCE_API_KEY`: Binance API 密鑰
- `BINANCE_API_SECRET`: Binance API 私鑰
- `DISCORD_TOKEN`: Discord 機器人 Token

**雙 API 配置（推薦）：**
- `BINANCE_TRADING_API_KEY`: 交易專用 API 密鑰（可選）
- `BINANCE_TRADING_API_SECRET`: 交易專用 API 私鑰（可選）

**可選變量：**
- `BINANCE_TESTNET`: 使用測試網（true/false，默認 false）
- `TRADING_ENABLED`: 啟用實盤交易（true/false，默認 false）
- `MAX_POSITIONS`: 最大持倉數（默認 3）
- `CYCLE_INTERVAL`: 週期間隔秒數（默認 60）
- `MIN_CONFIDENCE`: 最小信心度（默認 0.70）
- `LOG_LEVEL`: 日誌級別（DEBUG/INFO/WARNING/ERROR，默認 INFO）
- `MAX_ANALYZE_SYMBOLS`: 分析交易對數量（0=全部，默認 0）
- `SCAN_INTERVAL`: 掃描間隔秒數（默認 300）
- `RATE_LIMIT_REQUESTS`: API 限流請求數（默認 1920）

### 快速開始

#### Replit 部署
1. **設置環境變量**: 在 Replit Secrets 中配置所有必需的 API 密鑰
2. **啟動系統**: 點擊 Run 按鈕或運行 `python -m src.main`
3. **監控運行**: 查看控制台日誌和 Discord 通知

#### Railway 雲端部署
1. **推送代碼到 GitHub**: 確保所有代碼已提交
2. **連接 Railway**: 在 Railway.app 選擇您的 GitHub 倉庫
3. **配置環境變量**: 在 Railway Variables 中設置所有必需的 API 密鑰
4. **自動部署**: Railway 會自動檢測配置並部署
5. **查看詳細指南**: 參考 `docs/RAILWAY_DEPLOYMENT.md`

### 風險管理策略

#### 動態槓桿計算
- 基礎槓桿: 3x
- 勝率調整:
  - > 60%: +2x
  - > 70%: +4x
  - > 80%: +6x
- 連續虧損懲罰: -1x/次
- 回撤保護: > 10% → 重置 3x
- 限制範圍: 3x - 20x

#### 動態倉位大小
- 基礎保證金 = 總資本 × 10%
- 信心度調整 = 基礎 × (信心度/100)
- 最終保證金範圍: 3% - 13%

#### 止損止盈
- 止損距離 = ATR × 2
- 止盈距離 = 止損 × 2 (2:1 風險回報比)

### ICT/SMC 策略

#### 信心度評分系統
- 趨勢對齊 (40%): 15m與5m趨勢一致性
- 市場結構 (20%): 更高高點/更低低點分析
- 價格位置 (20%): Order Blocks 和 Liquidity Zones
- 動量指標 (10%): MACD 和 RSI
- 波動率 (10%): ATR 和布林帶

#### 執行邏輯
- 信心度 ≥ 70%: 生成交易信號
- Rank 1-3: 立即執行（最多 3 個實倉）
- Rank 4-10: 虛擬追蹤（ML 數據收集）

### 數據文件

- `data/trades.json`: 所有交易歷史
- `data/ml_pending_entries.json`: 待配對的 ML 數據
- `data/logs/trading_bot.log`: 系統運行日誌

### 開發狀態

當前版本: v2.0.0 (完整系統 + 高頻優化)

已完成:
- ✅ 完整 6 層架構（策略/服務/監控/業務/集成/ML）
- ✅ ICT/SMC 策略引擎（Order Blocks, Fair Value Gaps, Liquidity Zones）
- ✅ XGBoost ML 預測器（39 特徵，GPU 加速）
- ✅ 32 核心並行分析器（充分利用 Railway 資源）
- ✅ 動態風險管理器（槓桿 3-20x，倉位 3%-13%）
- ✅ Discord 通知系統（信號/交易/狀態）
- ✅ 虛擬倉位管理（ML 數據收集）
- ✅ 差異化時間框架掃描（API 優化）
- ✅ 健康監控和性能報告
- ✅ Railway 部署配置

最新優化:
- ⚡ 差異化掃描系統（1h每小時，15m每15分鐘，5m/1m高頻）
- ⚡ 智能數據管理器（緩存優化）
- ⚡ API 效率提升 5 倍
- ⚡ 支持監控全部 648 個交易對

### 部署選項

本系統支持兩種部署方式：

#### 1. Replit (開發和測試)
- 適合快速開發和測試
- 內置 IDE 和調試工具
- 免費額度充足
- 參考: `docs/ENVIRONMENT_VARIABLES.md`

#### 2. Railway (生產環境)
- 24/7 穩定運行
- 自動擴展和重啟
- 更接近 Binance 服務器（低延遲）
- 成本約 $10-15/月
- 參考: `docs/RAILWAY_DEPLOYMENT.md`

### 注意事項

⚠️ **重要提醒:**
- 本系統處於開發階段，建議先在測試網測試
- 默認交易功能是關閉的，需手動啟用
- 務必設置正確的 API 密鑰權限（僅需要交易權限）
- 定期監控系統運行狀態和賬戶餘額

### 聯繫與支持

如有問題，請查看日誌文件或聯繫開發團隊。
