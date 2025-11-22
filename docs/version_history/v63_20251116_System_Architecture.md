# 系統架構文檔

## 概述
高性能 Binance USDT 永續合約自動化交易系統，使用 ICT/SMC 策略，充分利用 32vCPU 32GB 資源。

## 系統分層架構

### 1. 策略層 (Strategy Layer)
負責：市場分析、信號生成、技術指標計算

#### 核心模塊
- **ICTStrategy** (`src/strategies/ict_strategy.py`)
  - Order Block 識別
  - Liquidity Zone 檢測
  - Fair Value Gap 分析
  - Market Structure 判斷
  - 多時間框架分析（1h/15m/5m/1m）
  - 12 種技術指標集成

#### 技術指標
1. RSI (相對強弱指數)
2. MACD (移動平均收斂散度)
3. ATR (平均真實波幅)
4. Bollinger Bands (布林帶)
5. Volume SMA Ratio (成交量比率)
6. EMA50/EMA200 (指數移動平均線)
7. Price Position Analysis (價格位置分析)

### 2. 服務層 (Service Layer)
負責：數據獲取、交易執行、並行處理

#### 核心模塊
- **DataService** (`src/services/data_service.py`)
  - K線數據批量獲取
  - 市場掃描（648 交易對）
  - 多時間框架數據聚合
  - 智能緩存管理

- **ParallelAnalyzer** (`src/services/parallel_analyzer.py`)
  - 32 核心並行分析
  - 批量處理（200 交易對/週期）
  - ThreadPoolExecutor 優化
  - 內存高效批次處理

- **TradingService** (`src/services/trading_service.py`)
  - 訂單下單執行
  - 倉位管理
  - 止盈止損設置
  - 訂單狀態追蹤

### 3. 機器學習層 (ML Layer)
負責：XGBoost 模型訓練、預測、信心度校準

#### 核心模塊
- **MLDataProcessor** (`src/ml/data_processor.py`)
  - 特徵工程（39 個特徵）
  - 數據清洗與編碼
  - 訓練集/測試集分割
  - 特徵重要性分析

- **XGBoostTrainer** (`src/ml/model_trainer.py`)
  - GPU 加速訓練
  - 超參數優化
  - 模型評估（準確率、F1、ROC-AUC）
  - 自動訓練機制

- **MLPredictor** (`src/ml/predictor.py`)
  - 實時預測
  - 勝率計算
  - 信心度校準（傳統策略 60% + ML 40%）
  - 模型熱加載

#### ML 特徵集（39 個）
**基礎交易特徵 (14)**
- confidence_score, leverage, position_value
- hold_duration_hours, risk_reward_ratio
- order_blocks_count, liquidity_zones_count

**技術指標特徵 (12)**
- RSI, MACD, MACD Signal, MACD Histogram
- ATR, BB Width%, Volume SMA Ratio
- Price vs EMA50, Price vs EMA200

**市場結構特徵 (6)**
- trend_1h_encoded, trend_15m_encoded, trend_5m_encoded
- market_structure_encoded, direction_encoded

**風險管理特徵 (5)**
- stop_loss_distance, take_profit_distance
- position_risk_percent

**元數據 (2)**
- entry_timestamp, timeframe_alignment_score

### 4. 業務管理層 (Business Management Layer)
負責：風險控制、倉位管理、交易記錄

#### 核心模塊
- **RiskManager** (`src/managers/risk_manager.py`)
  - 動態槓桿計算（3-20x）
  - 倉位大小計算（3%-13%）
  - 止損/止盈優化
  - 風險報酬比評估

- **VirtualPositionManager** (`src/managers/virtual_position_manager.py`)
  - 虛擬倉位追蹤
  - 盈虧計算
  - 倉位狀態管理
  - 持倉時間追蹤

- **TradeRecorder** (`src/managers/trade_recorder.py`)
  - 交易數據記錄（JSON Lines）
  - ML 訓練數據收集
  - 績效統計
  - 自動數據持久化

### 5. 第三方集成層 (Integration Layer)
負責：外部服務集成、通知系統

#### 核心模塊
- **BinanceClient** (`src/clients/binance_client.py`)
  - API 認證與簽名
  - 限流控制
  - 熔斷器保護
  - 連接池管理
  - WebSocket 支援（可選）

- **TradingDiscordBot** (`src/integrations/discord_bot.py`)
  - 信號通知
  - 交易執行通知
  - 系統警報
  - 狀態報告

### 6. 監控層 (Monitoring Layer)
負責：系統健康監控、性能指標追蹤

#### 核心模塊
- **HealthMonitor** (`src/monitoring/health_monitor.py`)
  - 系統狀態檢查
  - 組件健康監控
  - 異常檢測

- **PerformanceMonitor** (`src/monitoring/performance_monitor.py`)
  - CPU/內存/磁盤監控
  - 應用性能指標
  - 信號/交易統計
  - 定期報告（5 分鐘間隔）

### 7. 核心基礎設施層 (Core Infrastructure)
負責：速率限制、熔斷保護、緩存管理

#### 核心模塊
- **RateLimiter** (`src/core/rate_limiter.py`)
  - 令牌桶算法
  - API 調用限流

- **CircuitBreaker** (`src/core/circuit_breaker.py`)
  - 熔斷器模式
  - 自動故障恢復

- **CacheManager** (`src/core/cache_manager.py`)
  - 內存緩存
  - TTL 管理
  - 緩存命中率優化

## 性能優化策略

### 1. CPU 資源利用（32 vCPU）
- **並行分析**: ThreadPoolExecutor 32 個工作線程
- **批量處理**: 每批處理 64 個交易對
- **異步 I/O**: asyncio 處理網絡請求
- **分析覆蓋**: 每週期分析 200 個交易對

### 2. 內存優化（32 GB）
- **批次處理**: 避免一次性加載所有數據
- **緩存策略**: 智能 TTL 緩存減少重複請求
- **數據流式處理**: 增量處理 K 線數據

### 3. 網絡優化
- **連接池**: aiohttp 連接復用
- **限流控制**: 避免觸發 API 限制
- **批量請求**: 合併相似請求

## 數據流程

```
1. 市場掃描
   ↓
2. 並行分析（32 核心）
   ↓
3. ML 預測增強
   ↓
4. 信心度校準
   ↓
5. 風險評估
   ↓
6. 交易執行
   ↓
7. 倉位追蹤
   ↓
8. 數據記錄（ML 訓練）
```

## 部署架構

### Railway 部署配置
- **CPU**: 32 vCPU
- **內存**: 32 GB
- **Python**: 3.11+
- **依賴**: requirements.txt
- **啟動**: `python -m src.main`

### 環境變量
必需：
- `BINANCE_API_KEY`: Binance API 密鑰
- `BINANCE_API_SECRET`: Binance API 秘鑰
- `DISCORD_TOKEN`: Discord Bot Token

可選：
- `BINANCE_TESTNET`: 是否使用測試網（default: true）
- `MAX_SIGNALS`: 最大信號數（default: 5）
- `SCAN_INTERVAL`: 掃描間隔秒數（default: 300）

## 系統特性

### 1. 完整的 ICT/SMC 策略
✅ Order Block 識別  
✅ Liquidity Zone 檢測  
✅ Fair Value Gap 分析  
✅ Market Structure 判斷  
✅ 多時間框架確認  

### 2. 動態風險管理
✅ 信心度驅動槓桿（3-20x）  
✅ 自適應倉位大小（3%-13%）  
✅ 智能止損/止盈  
✅ 風險報酬比優化  

### 3. XGBoost ML 增強
✅ 39 個特徵工程  
✅ GPU 加速訓練  
✅ 實時預測集成  
✅ 自動模型更新  

### 4. 高性能並發
✅ 32 核心並行分析  
✅ 批量數據處理  
✅ 異步 I/O 操作  
✅ 內存高效設計  

### 5. 完整監控系統
✅ 實時性能監控  
✅ 系統健康檢查  
✅ Discord 通知集成  
✅ 詳細日誌記錄  

### 6. 數據持久化
✅ 交易數據記錄  
✅ ML 訓練數據收集  
✅ 模型自動保存  
✅ 績效統計追蹤  

## 擴展性

### 水平擴展
- 支援多實例部署
- 無狀態設計（虛擬倉位除外）
- 可配置交易對分組

### 垂直擴展
- CPU 核心數可調
- 內存使用可控
- 批量大小可配置

## 維護指南

### 日誌文件
- `logs/trading_bot.log`: 主日誌
- `data/trades/trades.jsonl`: 交易記錄
- `data/models/`: ML 模型文件

### 監控指標
- CPU/內存使用率
- 信號生成率
- 交易執行率
- API 調用次數
- 錯誤率

### 定期任務
- ML 模型重訓練（累積 100+ 交易後）
- 性能報告（每 5 分鐘）
- 數據備份

## 技術棧

### 核心框架
- **Python 3.11+**
- **asyncio**: 異步編程
- **aiohttp**: 異步 HTTP 客戶端
- **ccxt**: 加密貨幣交易所統一 API

### 機器學習
- **XGBoost**: 梯度提升模型
- **scikit-learn**: 數據處理與評估
- **pandas**: 數據分析
- **numpy**: 數值計算

### 基礎設施
- **discord.py**: Discord 集成
- **psutil**: 系統監控
- **python-dotenv**: 環境變量管理

## 版本資訊
- **版本**: v2.0 Enhanced
- **更新日期**: 2025-10-25
- **作者**: Winiswin2 Team
