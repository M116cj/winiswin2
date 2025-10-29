# SelfLearningTrader v3.17.2+ 系統架構藍圖

## 📋 版本信息
- **版本號**: v3.17.2+
- **發布日期**: 2025-10-29
- **核心特性**: WebSocket即時數據流 + 模組化架構 + 無限制槓桿控制

---

## 🏗️ 系統架構圖

```
┌────────────────────────────────────────────────────────────────┐
│                    UnifiedScheduler v3.17.2+                   │
│                    （統一調度器 - 24/7運行）                     │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │         WebSocketManager（統一管理器）                 │    │
│  │  ┌──────────────────┬──────────────────────────┐     │    │
│  │  │   KlineFeed      │    AccountFeed           │     │    │
│  │  │  （K線訂閱器）    │   （帳戶監控器）          │     │    │
│  │  │                  │                          │     │    │
│  │  │ • @kline_1m      │ • listenKey管理          │     │    │
│  │  │ • 即時OHLCV      │ • 30分鐘自動續期         │     │    │
│  │  │ • 自動重連       │ • ACCOUNT_UPDATE推送     │     │    │
│  │  │ • 閉盤K線緩存    │ • 即時倉位更新           │     │    │
│  │  └──────────────────┴──────────────────────────┘     │    │
│  └──────────────────────────────────────────────────────┘    │
│                           │                                   │
│                    統一接口調用                                │
│          ┌────────────────┴────────────────┐                 │
│          ↓                                  ↓                 │
│  ┌──────────────────┐             ┌──────────────────┐       │
│  │ SelfLearningTrader│             │PositionController│       │
│  │  (交易決策引擎)    │             │  (倉位監控器)     │       │
│  │                  │             │                  │       │
│  │ • get_kline()    │             │ • get_all_       │       │
│  │ • 市場上下文分析  │             │   positions()    │       │
│  │ • 信號生成       │             │ • 1分鐘監控週期   │       │
│  │ • 槓桿計算       │             │ • 緊急平倉       │       │
│  └──────────────────┘             └──────────────────┘       │
│                                                                │
│  降級機制: WebSocket無數據 → REST API備援 → 異常處理           │
└────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Binance API    │
                    │  (Futures USDT) │
                    └─────────────────┘
```

---

## 🎯 核心組件說明

### 1. **WebSocketManager（統一管理器）**
**文件**: `src/core/websocket/websocket_manager.py`

**職責**:
- 統一管理所有WebSocket Feed（KlineFeed + AccountFeed）
- 提供統一數據接口
- 生命週期管理（start/stop/統計）

**關鍵方法**:
```python
get_kline(symbol: str) -> Dict  # 獲取即時K線
get_all_positions() -> Dict     # 獲取所有即時倉位
get_price(symbol: str) -> float # 獲取即時價格
start()                         # 啟動所有Feed
stop()                          # 停止所有Feed
get_stats()                     # 獲取統計信息
```

---

### 2. **KlineFeed（K線訂閱器）**
**文件**: `src/core/websocket/kline_feed.py`

**職責**:
- 訂閱Binance WebSocket K線流（@kline_1m）
- 緩存最新K線數據（僅閉盤K線）
- 自動重連機制

**數據流**:
```
Binance WS → @kline_1m → is_final=True → 緩存 → SelfLearningTrader
```

**緩存格式**:
```python
{
    'BTCUSDT': {
        'open': 67000.0,
        'high': 67500.0,
        'low': 66800.0,
        'close': 67200.0,
        'volume': 1234.56,
        'timestamp': 1730177520000
    }
}
```

---

### 3. **AccountFeed（帳戶監控器）**
**文件**: `src/core/websocket/account_feed.py`

**職責**:
- 管理listenKey生命週期（獲取/續期/關閉）
- 訂閱ACCOUNT_UPDATE事件
- 即時倉位數據推送
- 30分鐘自動續期

**數據流**:
```
BinanceClient.get_listen_key() → WebSocket訂閱 → ACCOUNT_UPDATE
    ↓
緩存倉位數據 → PositionController
    ↓
每30分鐘: BinanceClient.renew_listen_key()
```

**緩存格式**:
```python
{
    'BTCUSDT': {
        'symbol': 'BTCUSDT',
        'size': 0.5,
        'entry_price': 67000.0,
        'unrealized_pnl': 100.0,
        'leverage': 10
    }
}
```

---

### 4. **UnifiedScheduler（統一調度器）**
**文件**: `src/core/unified_scheduler.py`

**職責**:
- 管理3個並行循環（交易週期、倉位監控、每日報告）
- 注入WebSocketManager到所有組件
- 向後兼容（websocket_monitor別名）

**循環週期**:
- **交易週期**: 每60秒（生成信號、執行交易）
- **倉位監控**: 每60秒（監控倉位、風險管理）← **已修改**
- **每日報告**: 每24小時（00:00 UTC）

---

### 5. **SelfLearningTrader（交易決策引擎）**
**文件**: `src/strategies/self_learning_trader.py`

**職責**:
- 市場上下文分析（使用WebSocket K線數據）
- 信號生成與評分
- 無限制槓桿計算（基於勝率×信心度）
- 競價系統（多信號排序）

**關鍵升級**:
```python
# v3.17.2+: 優先使用WebSocket K線
def _get_market_context(symbol):
    kline = websocket_manager.get_kline(symbol)
    if kline:
        return analyze_kline(kline)  # WebSocket數據
    else:
        return fetch_from_rest_api()  # REST備援
```

---

### 6. **PositionController（倉位監控器）**
**文件**: `src/core/position_controller.py`

**職責**:
- 24/7倉位監控（每60秒）← **已修改**
- 優先使用WebSocket帳戶Feed
- 緊急平倉（PnL ≤ -99%）
- 整合PositionMonitor24x7（進場失效+逆勢平倉）

**關鍵升級**:
```python
# v3.17.2+: 優先使用WebSocket倉位數據
async def _fetch_all_positions():
    ws_positions = websocket_manager.get_all_positions()
    if ws_positions:
        return convert_to_standard_format(ws_positions)
    else:
        return await binance_client.get_position_info_async()
```

---

## 🔄 數據流向

### **K線數據流**
```
Binance WebSocket (@kline_1m)
    ↓
KlineFeed（緩存閉盤K線）
    ↓
WebSocketManager.get_kline()
    ↓
SelfLearningTrader._get_market_context()
    ↓
趨勢判斷 + 信號生成
```

### **倉位數據流**
```
Binance API (listenKey)
    ↓
AccountFeed（ACCOUNT_UPDATE事件）
    ↓
WebSocketManager.get_all_positions()
    ↓
PositionController._fetch_all_positions()
    ↓
倉位監控 + 風險管理
```

### **降級機制**
```
WebSocket數據 → 優先使用
    ↓ (無數據)
REST API備援 → 次優選擇
    ↓ (失敗)
異常處理 → 熔斷器保護
```

---

## ⚙️ 配置參數

### **監控週期**（config/config.yaml）
```yaml
trading:
  cycle_interval: 60           # 交易週期：60秒
  position_check_interval: 60  # 倉位監控：60秒（已修改）

websocket:
  kline_interval: '1m'         # K線週期：1分鐘
  listen_key_renewal: 1800     # listenKey續期：30分鐘
  reconnect_delay: 5           # 重連延遲：5秒
```

### **風險控制**
```yaml
risk:
  max_leverage: 125            # 最大槓桿：125x（無限制）
  min_confidence: 0.5          # 最小信心度：50%
  emergency_close_pnl: -0.99   # 緊急平倉：-99%
  min_notional: 10             # 最小名義價值：10 USDT
```

---

## 🛡️ 容錯機制

### **三級降級策略**
1. **Level 1**: WebSocket即時數據（零延遲）
2. **Level 2**: REST API備援（100-200ms延遲）
3. **Level 3**: 熔斷器保護（失敗5次→阻斷60秒）

### **自動重連**
- KlineFeed: WebSocket斷線 → 5秒後重連
- AccountFeed: listenKey失效 → 自動重新獲取

### **listenKey生命週期**
```
創建 → 使用 → 每30分鐘續期 → 停止時關閉
```

---

## 📊 性能優化

### **WebSocket優勢**
- ✅ **零輪詢**: 取代REST K線輪詢（減少API調用）
- ✅ **零延遲**: 即時價格推送（vs REST 100-200ms）
- ✅ **低負載**: 單一連接多幣種監控
- ✅ **自動更新**: 倉位變化即時推送

### **REST API降級時機**
- WebSocket連接失敗
- 數據緩存為空
- 超過30秒無更新

---

## 🚀 部署要求

### **環境變量**
```bash
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
SESSION_SECRET=random_string
```

### **依賴項**（requirements.txt）
```
aiohttp==3.13.1
websockets==15.0.1        # ← v3.17.2+新增
xgboost==3.1.1
tensorflow==2.20.0
pandas==2.3.3
```

### **部署平台**
- ❌ **Replit**: HTTP 451地理位置限制
- ✅ **Railway**: 歐洲/亞洲服務器（推薦）
- ✅ **AWS/GCP/Azure**: 全球可用

---

## 📈 監控指標

### **WebSocket健康度**
```python
stats = websocket_manager.get_stats()
{
    'kline_feed': {
        'connected': True,
        'symbols': 200,
        'last_update': '2025-10-29T05:09:00Z'
    },
    'account_feed': {
        'connected': True,
        'listen_key_valid': True,
        'last_renewal': '2025-10-29T04:39:00Z',
        'next_renewal': '2025-10-29T05:09:00Z'
    }
}
```

### **Architect建議監控**
- ✅ AccountFeed keep-alive成功率
- ✅ REST fallback觸發頻率
- ✅ WebSocket重連次數
- ✅ listenKey續期成功率

---

## 🔧 關鍵修改（v3.17.2+）

### **1. BinanceClient listenKey支持**
```python
# 新增方法
async def get_listen_key() -> str
async def renew_listen_key(listen_key: str) -> dict  # ← 修復：添加params參數
async def close_listen_key(listen_key: str) -> dict  # ← 修復：添加params參數
```

### **2. UnifiedScheduler WebSocket注入**
```python
# 替換WebSocketMonitor → WebSocketManager
self.websocket_manager = WebSocketManager(...)
self.websocket_monitor = self.websocket_manager  # 向後兼容別名
```

### **3. 倉位監控週期**
```python
# 修改前: 2秒
# 修改後: 60秒（1分鐘）
position_check_interval = 60
```

---

## 🎯 未來優化建議

### **短期（1-2週）**
- [ ] 添加WebSocket監控告警
- [ ] listenKey續期失敗重試機制
- [ ] WebSocket連接狀態儀表板

### **中期（1-2個月）**
- [ ] 多交易所支持（OKX、Bybit）
- [ ] 自適應監控週期（動態調整1-60秒）
- [ ] WebSocket消息隊列緩衝

### **長期（3-6個月）**
- [ ] 分佈式部署（多地區節點）
- [ ] 實時風險監控面板
- [ ] AI驅動的監控週期優化

---

## 📝 版本歷史

### **v3.17.2+ (2025-10-29)**
- ✅ 創建WebSocket模組化架構（KlineFeed + AccountFeed + WebSocketManager）
- ✅ 取代單一WebSocketMonitor
- ✅ listenKey完整生命週期管理
- ✅ 修復listenKey renewal/close參數缺失bug
- ✅ 倉位監控週期：2秒 → 60秒
- ✅ Architect兩次審查通過

### **v3.17.11 (2025-10-28)**
- ✅ 初始WebSocket整合
- ✅ Railway重啟循環修復

---

## 📞 技術支持

**Architect審查狀態**: ✅ **PASS**（已通過第二次審查）

**關鍵修復**:
- BinanceClient.renew_listen_key() → 添加{'listenKey': listen_key}參數
- BinanceClient.close_listen_key() → 添加{'listenKey': listen_key}參數

**部署狀態**: ✅ **READY**（準備部署到Railway）

---

**文檔生成時間**: 2025-10-29  
**架構版本**: v3.17.2+  
**作者**: SelfLearningTrader Team
