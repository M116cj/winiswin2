# Winiswin2 v1 Enhanced - 高性能加密貨幣自動交易系統

## 專案概述

這是一個基於 ICT/SMC 策略的高性能加密貨幣自動交易系統，專為 Binance USDT 永續合約設計。

### 核心特性

- 📊 **全市場監控**: 監控全部 648 個 Binance USDT 永續合約
- 🎯 **ICT/SMC 策略**: 多時間框架分析 (1h/15m/5m/1m)
- ⚡ **非同步架構**: 使用 asyncio + aiohttp 實現高性能並發
- 🎲 **動態風險管理**: 槓桿 3-20x，倉位 3%-13%
- 🤖 **Discord 通知**: 實時交易信號和狀態更新
- 🧠 **ML 數據收集**: 38 個特徵的完整交易數據記錄

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

**可選變量：**
- `BINANCE_TESTNET`: 使用測試網（true/false，默認 false）
- `TRADING_ENABLED`: 啟用實盤交易（true/false，默認 false）
- `MAX_POSITIONS`: 最大持倉數（默認 3）
- `CYCLE_INTERVAL`: 週期間隔秒數（默認 60）
- `MIN_CONFIDENCE`: 最小信心度（默認 0.70）
- `LOG_LEVEL`: 日誌級別（DEBUG/INFO/WARNING/ERROR，默認 INFO）

### 快速開始

1. **設置環境變量**: 在 Replit Secrets 中配置所有必需的 API 密鑰
2. **啟動系統**: 點擊 Run 按鈕或運行 `python -m src.main`
3. **監控運行**: 查看控制台日誌和 Discord 通知

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

當前版本: v1.0.0 (基礎框架)

已完成:
- ✅ 項目結構
- ✅ 配置管理系統
- ✅ Binance API 客戶端
- ✅ 核心基礎設施（緩存、限流、熔斷器）
- ✅ 技術指標計算
- ✅ 主程序框架

待實現:
- ⏳ ICT/SMC 策略引擎
- ⏳ 風險管理器
- ⏳ 交易執行服務
- ⏳ Discord 通知系統
- ⏳ 虛擬倉位追蹤
- ⏳ ML 數據收集

### 注意事項

⚠️ **重要提醒:**
- 本系統處於開發階段，建議先在測試網測試
- 默認交易功能是關閉的，需手動啟用
- 務必設置正確的 API 密鑰權限（僅需要交易權限）
- 定期監控系統運行狀態和賬戶餘額

### 聯繫與支持

如有問題，請查看日誌文件或聯繫開發團隊。
