# 📊 統一數據格式參考文檔

**所有系統層使用此文檔中定義的格式，確保 PostgreSQL、Redis、WebSocket 數據一致**

---

## 時間戳格式統一

### 標準格式
- **BIGINT milliseconds** (Binance 標準)
- 所有層都使用毫秒時間戳，不進行轉換

### 應用層級
| 層級 | 格式 | 例子 |
|------|------|------|
| WebSocket/Feed | BIGINT ms | 1732431918303 |
| Brain | BIGINT ms | 1732431918303 |
| Experience Buffer | BIGINT ms | 1732431918303 |
| PostgreSQL | BIGINT | 1732431918303 |
| Redis | BIGINT ms | 1732431918303 |

### 代碼常量
```python
# src/data_formats.py
CANDLE_IDX_TIMESTAMP = 0  # 毫秒
CANDLE_IDX_OPEN = 1
CANDLE_IDX_HIGH = 2
CANDLE_IDX_LOW = 3
CANDLE_IDX_CLOSE = 4
CANDLE_IDX_VOLUME = 5
```

---

## 信號 (Signal) 格式統一

### 標準信號結構
```python
signal = {
    'signal_id': str,           # UUID
    'symbol': str,              # e.g. 'BTCUSDT'
    'timestamp': int,           # 毫秒 (BIGINT)
    'confidence': float,        # 0.0 - 1.0
    'direction': str,           # 'BUY' or 'SELL'
    'strength': float,          # 0.0 - 1.0
    'features': {
        'confidence': float,    # 0.0 - 1.0
        'direction': str,       # 'BUY'/'SELL'
        'strength': float,      # 0.0 - 1.0
        'fvg': float,          # 0.0 - 1.0 (Fair Value Gap)
        'liquidity': float,     # 0.0 - 1.0
        'rsi': float,          # 0 - 100
        'atr': float,          # 絕對值 (Average True Range)
        'macd': float,         # 相對值 (MACD)
        'bb_width': float,     # 相對值 (Bollinger Band Width)
        'position_size': float,        # 數量
        'position_size_pct': float,    # 百分比 (0.0-1.0)
        'timeframe_analysis': dict,    # 多時間框架分析
    },
    'entry_price': float,      # 市場價格
}
```

### 數據流向
1. **Brain** 生成完整信號 + features
2. **Experience Buffer** 記錄 signal_id + features
3. **PostgreSQL signals** 表存儲為 JSONB (patterns)
4. **ML** 訓練時提取特徵向量

---

## K 線 (Candle) 格式統一

### 標準元組格式
```python
candle = (timestamp_ms, open, high, low, close, volume)
```

### 訪問方式
```python
# ✅ 正確方式 - 使用常量
from src.data_formats import CANDLE_IDX_*

timestamp = candle[CANDLE_IDX_TIMESTAMP]
close_price = candle[CANDLE_IDX_CLOSE]

# ❌ 錯誤方式 - 避免魔數
price = candle[4]  # 不清楚是什麼
```

### 應用流向
```
Binance WebSocket
  ↓
Feed: candle = (ts_ms, o, h, l, c, v)
  ↓
Ring Buffer: tuple 傳遞
  ↓
TimeframeBuffer: 聚合多時間框架
  ↓
Brain: 分析生成信號
```

---

## PostgreSQL 表結構統一

### market_data
```sql
CREATE TABLE market_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp BIGINT NOT NULL,              -- 毫秒
    open_price NUMERIC(20,8) NOT NULL,
    high_price NUMERIC(20,8) NOT NULL,
    low_price NUMERIC(20,8) NOT NULL,
    close_price NUMERIC(20,8) NOT NULL,
    volume NUMERIC(20,8) NOT NULL,
    timeframe VARCHAR(10) DEFAULT '1m',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### signals
```sql
CREATE TABLE signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    patterns JSONB,                         -- 完整特徵結構
    position_size DOUBLE PRECISION,
    timestamp BIGINT NOT NULL,              -- 毫秒
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### experience_buffer
```sql
CREATE TABLE experience_buffer (
    id SERIAL PRIMARY KEY,
    signal_id UUID REFERENCES signals(id),
    features JSONB NOT NULL,                -- 完整特徵集合
    outcome JSONB,                          -- 交易結果
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### ml_models
```sql
CREATE TABLE ml_models (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    model_data BYTEA NOT NULL,              -- 序列化模型
    training_samples INTEGER DEFAULT 0,
    accuracy NUMERIC(5,4),
    is_active BOOLEAN DEFAULT FALSE,
    trained_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## ML 特徵向量統一

### 標準特徵索引
```python
features = [
    confidence,         # index 0: 0.0 - 1.0
    fvg,               # index 1: 0.0 - 1.0
    liquidity,         # index 2: 0.0 - 1.0
    position_size_pct, # index 3: 0.0 - 1.0
    rsi,               # index 4: 0 - 100
    atr,               # index 5: 原始值
    macd,              # index 6: 原始值
    bb_width           # index 7: 原始值
]
```

### 特徵提取方法
```python
from src.data_formats import extract_ml_features

features = extract_ml_features(signal_data)
# 返回 8 個特徵的列表
```

### ML 訓練數據格式
```python
training_sample = {
    'features': [...],  # 8 個特徵
    'label': 0 | 1,     # 0=loss, 1=win
    'metadata': {
        'symbol': str,
        'timestamp': int,  # 毫秒
        'pnl': float,
        'source': 'virtual' | 'real'
    }
}
```

---

## Redis 數據格式統一

### 鍵空間設計
```python
# 市場數據快速訪問
market:{symbol}
  值: {
    "symbol": str,
    "timestamp": int (ms),
    "o": float,  # open
    "h": float,  # high
    "l": float,  # low
    "c": float,  # close
    "v": float   # volume
  }
  TTL: 3600 秒 (1 小時)

# 未來擴展
signal:{symbol}      # 最新信號
state:account        # 帳戶狀態快速查詢
```

### 序列化方式
```python
# ✅ 正確方式
import json
redis_client = await redis_async.from_url(redis_url, decode_responses=True)
data = json.dumps({...})
await redis_client.set(f"market:{symbol}", data, ex=3600)

# 讀取
data = await redis_client.get(f"market:{symbol}")
parsed = json.loads(data) if data else {}
```

---

## Experience Buffer 統一格式

### 完整經驗記錄
```python
record = {
    'signal_id': str,           # UUID
    'type': str,                # 'signal' 或 'complete_trade'
    'symbol': str,
    'timestamp': int,           # 毫秒
    'features': {...},          # 完整特徵集合
    'outcome': {
        'entry_price': float,
        'exit_price': float,
        'quantity': float,
        'side': 'BUY'/'SELL',
        'pnl': float,
        'pnl_percent': float,
        'status': 'FILLED'/'REJECTED',
        'close_reason': 'TP_HIT'/'SL_HIT'/'MANUAL',
        'win': bool
    } | None,
    'recorded_at': int          # 毫秒
}
```

### 使用方式
```python
from src.experience_buffer import get_experience_buffer

exp_buffer = get_experience_buffer()

# 記錄信號
await exp_buffer.record_signal(signal_id, signal_data)

# 記錄交易結果
await exp_buffer.record_trade_outcome(signal_id, trade_data)

# 獲取訓練數據
training_data = await exp_buffer.get_training_data()

# 持久化到 PostgreSQL
saved_count = await exp_buffer.save_to_database(db_url)
```

---

## 數據流驗證清單

- ✅ 所有時間戳統一為 BIGINT milliseconds
- ✅ 信號包含完整 features 結構
- ✅ ML 特徵提取統一使用 extract_ml_features()
- ✅ Experience Buffer 記錄完整 signal + outcome
- ✅ PostgreSQL 表列類型一致
- ✅ Redis 鍵空間設計清晰
- ✅ Candle 訪問使用常量而非魔數

---

## 相關文件

- **src/data_formats.py** - 格式定義和工具函數
- **src/brain.py** - 信號生成
- **src/experience_buffer.py** - 經驗記錄
- **src/ml_model.py** - ML 訓練
- **src/ml_virtual_integrator.py** - 虛擬交易訓練數據轉換
- **src/feed.py** - WebSocket 和 Redis/DB 寫入
