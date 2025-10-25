# Binance USDT 永續合約自動化交易系統 v2.0 Enhanced

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success.svg)

高性能 Binance USDT 永續合約自動化交易系統，採用 ICT/SMC 策略，集成 XGBoost 機器學習，充分利用 32vCPU 32GB 資源。

## 🚀 快速部署

### Railway 部署（生產環境）

#### 1. 配置資源
- **CPU**: 32 vCPU
- **Memory**: 32 GB RAM
- **啟動命令**: `python -m src.main`

#### 2. 設置環境變量

**必需**:
```bash
BINANCE_API_KEY=你的_API_Key
BINANCE_API_SECRET=你的_API_Secret
DISCORD_TOKEN=你的_Discord_Bot_Token
```

**可選**:
```bash
BINANCE_TESTNET=false  # 生產環境設為 false
MAX_SIGNALS=5
SCAN_INTERVAL=300
```

#### 3. 完整部署指南

詳見: [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md)

### 本地運行

```bash
# 安裝依賴
pip install -r requirements.txt

# 配置環境變量
cp .env.example .env
# 編輯 .env 填入你的密鑰

# 運行系統
python -m src.main
```

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

## ✨ 核心特性

### 🎯 ICT/SMC 策略引擎
- ✅ **Order Block 識別** - 機構訂單區塊檢測
- ✅ **Liquidity Zone 分析** - 流動性區域追蹤
- ✅ **Fair Value Gap 檢測** - 價值缺口識別
- ✅ **Market Structure 判斷** - 市場結構分析
- ✅ **多時間框架確認** - 1h/15m/5m/1m 同步分析
- ✅ **12 種技術指標** - RSI, MACD, ATR, BB, EMA 等

### 🤖 XGBoost ML 增強
- ✅ **自動數據收集** - 交易數據實時記錄
- ✅ **智能模型訓練** - GPU 加速，自動訓練
- ✅ **實時預測服務** - 勝率計算，信心度校準
- ✅ **39 個特徵工程** - 全面市場特徵分析

### ⚡ 高性能架構
- ✅ **32 核心並行分析** - 充分利用 32vCPU
- ✅ **批量處理** - 每週期分析 200 個交易對
- ✅ **異步 I/O** - asyncio 高效網絡處理
- ✅ **智能緩存** - TTL 緩存減少 API 調用

### 🛡️ 動態風險管理
- ✅ **信心度驅動槓桿** - 3-20x 動態調整
- ✅ **自適應倉位大小** - 3%-13% 智能分配
- ✅ **ATR 止損** - 波動率驅動止損
- ✅ **風險報酬優化** - 動態 R:R 計算

### 📊 完整監控系統
- ✅ **實時性能監控** - CPU/內存/磁盤追蹤
- ✅ **應用指標統計** - 信號/交易/API 計數
- ✅ **Discord 通知** - 信號、交易、警報推送
- ✅ **詳細日誌** - 結構化日誌記錄

## 📁 系統架構

```
├── 策略層 (Strategy Layer)
│   └── ICT/SMC 策略引擎 + 12 技術指標
│
├── 服務層 (Service Layer)
│   ├── 數據服務 (648 交易對掃描)
│   ├── 並行分析器 (32 核心優化)
│   └── 交易執行服務
│
├── ML 層 (Machine Learning Layer)
│   ├── 數據處理器 (39 特徵工程)
│   ├── XGBoost 訓練器 (GPU 加速)
│   └── 預測服務 (實時預測)
│
├── 業務管理層 (Business Management)
│   ├── 風險管理器 (動態槓桿/倉位)
│   ├── 虛擬倉位管理器
│   └── 交易記錄器 (ML 數據收集)
│
├── 第三方集成層 (Integration)
│   ├── Binance API 客戶端
│   └── Discord 通知系統
│
└── 監控層 (Monitoring)
    ├── 健康監控器
    └── 性能監控器
```

## 📂 項目結構

```
winiswin2/
├── src/
│   ├── main.py                 # 主程序入口
│   ├── config.py               # 配置管理
│   ├── clients/                # API 客戶端
│   ├── services/               # 服務層
│   ├── strategies/             # 策略層
│   ├── ml/                     # ML 層
│   ├── managers/               # 業務管理層
│   ├── integrations/           # 第三方集成
│   ├── monitoring/             # 監控層
│   └── core/                   # 核心基礎設施
├── data/
│   ├── trades/                 # 交易記錄
│   └── models/                 # ML 模型
├── logs/                       # 日誌文件
├── docs/                       # 文檔
│   ├── SYSTEM_ARCHITECTURE.md         # 系統架構
│   ├── COMPLETE_FEATURE_VERIFICATION.md  # 功能驗證
│   └── DEPLOYMENT_GUIDE.md            # 部署指南
└── requirements.txt            # 依賴列表
```

## ⚠️ 重要提醒

1. **首次使用請設置 `BINANCE_TESTNET=true`** - 在測試網環境測試
2. **默認交易是關閉的** - 需要手動設置 `TRADING_ENABLED=true`
3. **API 密鑰權限** - 僅需要「期貨交易」權限，不要給予提現權限
4. **監控資金** - 定期檢查賬戶餘額和持倉情況

## 📊 系統狀態

**Version**: v2.0 Enhanced  
**Status**: ✅ **生產就緒**  
**更新日期**: 2025-10-25

**已完成功能** (17/17):
- ✅ ICT/SMC 策略引擎（完整實現）
- ✅ XGBoost ML 層（數據收集、訓練、預測）
- ✅ 32 核心並行分析器
- ✅ 動態風險管理器
- ✅ 交易執行服務
- ✅ Discord 通知系統
- ✅ 虛擬倉位追蹤
- ✅ 性能監控系統
- ✅ 完整文檔

## 📚 文檔

- [系統架構文檔](docs/SYSTEM_ARCHITECTURE.md) - 完整架構說明
- [完整功能驗證](docs/COMPLETE_FEATURE_VERIFICATION.md) - 功能清單
- [部署指南](docs/DEPLOYMENT_GUIDE.md) - Railway 部署教程

## 📈 性能指標

### 並發處理能力
- **分析速度**: 200 交易對/週期
- **並行線程**: 32 個工作線程
- **批次大小**: 64 個/批次
- **內存優化**: 批量處理，流式計算

### ML 模型性能
- **特徵數量**: 39 個特徵
- **訓練樣本**: 100+ 交易記錄
- **評估指標**: Accuracy, Precision, Recall, F1, ROC-AUC
- **信心度校準**: 傳統 60% + ML 40%

## 🔧 技術棧

### 核心框架
- **Python 3.11+** - 主語言
- **asyncio** - 異步編程
- **aiohttp** - 異步 HTTP 客戶端

### 機器學習
- **XGBoost** - 梯度提升模型
- **scikit-learn** - ML 工具庫
- **pandas** - 數據分析
- **numpy** - 數值計算

### 交易與通知
- **ccxt** - 交易所 API
- **discord.py** - Discord 集成
- **psutil** - 系統監控

## ⚠️ 免責聲明

本系統僅供教育和研究目的。加密貨幣交易存在高風險，請自行承擔風險。

## 📄 授權

MIT License - 詳見 [LICENSE](LICENSE) 文件

---

**系統狀態**: ✅ 生產就緒  
**版本**: v2.0 Enhanced  
**更新日期**: 2025-10-25
