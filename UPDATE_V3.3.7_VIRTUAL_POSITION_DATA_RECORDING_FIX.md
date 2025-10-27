# 更新 v3.3.7: 修復虛擬倉位數據記錄 Bug

**日期**: 2025-10-27  
**版本**: v3.3.7  
**類型**: 🔥 Critical Bug Fix

---

## 🚨 問題診斷

### 根本原因

**虛擬倉位平倉數據從未被記錄到 TradeRecorder 或 DataArchiver**，導致 XGBoost 訓練數據完全為空。

### 數據流追踪

#### ❌ 修復前（v3.3.6 及之前）

```
1. 創建虛擬倉位 ✅
   main.py:411 → virtual_position_manager.add_virtual_position()
   main.py:414-417 → data_archiver.archive_position_open(is_virtual=True)

2. 監控虛擬倉位 ✅
   main.py:434 → virtual_position_manager.update_virtual_positions()

3. 平倉虛擬倉位 ✅
   virtual_position_manager.py:144-159 → _close_virtual_position()
   → 只標記 status='closed'
   → ❌ 沒有調用 data_archiver.archive_position_close()
   → ❌ 沒有調用 trade_recorder.record_exit()
   → ❌ PnL數據丟失！

4. XGBoost訓練 ❌
   → 無法獲取虛擬倉位平倉數據
   → 訓練數據為空
   → 模型無法學習
```

### 影響範圍

| 項目 | 預期 | v3.3.6實際 | 影響 |
|------|------|-----------|------|
| 虛擬倉位創建 | 無限制 | ✅ 無限制 | 正常 |
| 虛擬倉位平倉 | 自動平倉 | ✅ 自動平倉 | 正常 |
| 平倉數據記錄 | 記錄到TradeRecorder | ❌ 未記錄 | **數據丟失** |
| XGBoost訓練數據 | 大量虛擬交易 | ❌ 0筆虛擬交易 | **無法學習** |
| XGBoost重訓練 | 每50筆觸發 | ❌ 永遠不觸發 | **模型停滯** |

---

## ✅ 修復方案

### 1. 添加虛擬倉位關閉回調機制

**修改文件**: `src/managers/virtual_position_manager.py`

```python
class VirtualPositionManager:
    def __init__(self, on_close_callback=None):
        """
        Args:
            on_close_callback: 虛擬倉位關閉時的回調函數 
                              (position_data, close_data) -> None
        """
        self.on_close_callback = on_close_callback
        # ...
    
    def _close_virtual_position(self, symbol: str, reason: str):
        """關閉虛擬倉位並觸發回調"""
        # ... 現有邏輯 ...
        
        # 🆕 新增：調用回調記錄平倉數據
        if self.on_close_callback:
            close_data = {
                'symbol': symbol,
                'exit_price': position['entry_price'] * (1 + final_pnl),
                'pnl': final_pnl,
                'pnl_pct': final_pnl,
                'close_reason': reason,
                'timestamp': close_timestamp,
                'is_virtual': True
            }
            self.on_close_callback(position, close_data)
```

### 2. 在主程序中設置回調函數

**修改文件**: `src/main.py`

```python
def on_virtual_position_close(position_data: Dict, close_data: Dict):
    """虛擬倉位關閉回調：記錄平倉數據到 TradeRecorder 和 DataArchiver"""
    # 格式化為 TradeRecorder 需要的格式
    signal_format = {
        'symbol': position_data['symbol'],
        'direction': position_data['direction'],
        'entry_price': position_data['entry_price'],
        'confidence': position_data['confidence'],
        'timestamp': datetime.fromisoformat(position_data['entry_timestamp']),
        # ...
    }
    
    # 記錄開倉
    self.trade_recorder.record_entry(signal_format, position_info)
    
    # 記錄平倉
    trade_result = {
        'symbol': close_data['symbol'],
        'exit_price': close_data['exit_price'],
        'pnl': close_data['pnl'],
        'pnl_pct': close_data['pnl_pct'],
        'close_reason': close_data['close_reason'],
        'close_timestamp': close_data['timestamp'],
    }
    
    ml_record = self.trade_recorder.record_exit(trade_result)
    
    # 同時歸檔到 DataArchiver
    if ml_record:
        self.data_archiver.archive_position_close(
            position_data=position_data,
            close_data=close_data,
            is_virtual=True
        )

# 創建時傳入回調
self.virtual_position_manager = VirtualPositionManager(
    on_close_callback=on_virtual_position_close
)
```

---

## ✅ 修復後數據流

```
1. 創建虛擬倉位 ✅
   → main.py:411 → add_virtual_position()
   → main.py:414-417 → archive_position_open(is_virtual=True)

2. 監控虛擬倉位 ✅
   → main.py:434 → update_virtual_positions()

3. 平倉虛擬倉位 ✅
   → virtual_position_manager.py:153-187 → _close_virtual_position()
   → 🆕 調用 on_close_callback(position_data, close_data)
   → 🆕 trade_recorder.record_entry() + record_exit()
   → 🆕 data_archiver.archive_position_close(is_virtual=True)
   → ✅ PnL數據成功記錄！

4. XGBoost訓練 ✅
   → ✅ 可以獲取虛擬倉位平倉數據
   → ✅ 訓練數據充足（虛擬+真實）
   → ✅ 模型持續學習
   → ✅ 每50筆觸發重訓練
```

---

## 📊 預期效果

### 學習模式數據累積

| 場景 | v3.3.6 (Bug) | v3.3.7 (Fixed) |
|------|--------------|----------------|
| 虛擬倉位創建 | 130+/周期 | 130+/周期 |
| 虛擬倉位平倉 | 自動平倉 | 自動平倉 |
| 平倉數據記錄 | ❌ 0筆 | ✅ 全部記錄 |
| XGBoost訓練樣本 | 0筆 | 130+ * N周期 |
| 重訓練觸發 | 永不觸發 | 每50筆觸發 |

### XGBoost訓練進度

```
假設系統運行24小時（1440分鐘 = 24個周期@60秒）：

v3.3.6:
- 虛擬倉位: 130 * 24 = 3,120個
- 記錄到ML: 0筆
- XGBoost重訓練: 0次

v3.3.7:
- 虛擬倉位: 130 * 24 = 3,120個
- 記錄到ML: ~3,120筆（假設都平倉）
- XGBoost重訓練: 3120 / 50 = 62次
- 模型質量: 持續提升
```

---

## 🧪 驗證方式

### 1. 檢查虛擬倉位平倉日誌

```bash
# Railway 日誌中應該看到：
✅ 虛擬倉位關閉: BTCUSDT PnL: +1.23% 原因: take_profit
📝 已記錄虛擬倉位平倉: BTCUSDT
✅ 虛擬倉位平倉數據已記錄到 ML 訓練集: BTCUSDT PnL: +1.23%
```

### 2. 檢查 ML 訓練數據文件

```bash
# 應該看到虛擬倉位數據寫入
cat ml_data/trades.jsonl
```

### 3. 檢查 XGBoost 重訓練

```bash
# 累積50筆後應該觸發重訓練
🔄 檢測到 50 筆新交易數據，開始重訓練模型...
✅ 模型重訓練完成！準確率: 65.2%, AUC: 0.712
```

---

## 📝 部署說明

1. 推送代碼到 GitHub
2. Railway 自動部署 v3.3.7
3. 觀察日誌確認虛擬倉位平倉被正確記錄
4. 等待50筆交易後確認XGBoost重訓練觸發

---

## 🎯 結論

**v3.3.7 修復了學習模式無法累積數據的根本問題**：

- ✅ 虛擬倉位平倉數據現在會被正確記錄
- ✅ TradeRecorder 和 DataArchiver 雙重歸檔
- ✅ XGBoost 可以獲取大量虛擬交易數據
- ✅ 模型可以持續學習和優化
- ✅ 每50筆交易自動重訓練

**這是 v3.3.6 之後最關鍵的修復！**
