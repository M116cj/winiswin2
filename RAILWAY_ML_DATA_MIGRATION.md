# 🚀 Railway ML數據遷移指南

## 📊 背景

v3.18.4-hotfix-ml 修復了ML學習系統的數據持久化問題：
- 文件格式統一：`trades.json` → `trades.jsonl`
- 實時保存：`ML_FLUSH_COUNT: 25 → 1`
- Graceful Shutdown：確保Railway重啟時數據不丟失

## ⚠️ Railway部署注意事項

### 1. 舊數據遷移（如果存在）

如果Railway生產環境已有 `data/trades.json` 文件，需要遷移數據：

```bash
# SSH進入Railway容器
railway shell

# 檢查是否有舊文件
ls -la data/

# 如果存在 trades.json，遷移數據
cd data
if [ -f "trades.json" ]; then
    echo "發現舊數據文件 trades.json"
    
    # 備份
    cp trades.json trades.json.backup
    
    # 轉換格式（如果是JSON數組）
    # 如果原文件是JSON Lines格式，直接重命名即可
    if head -1 trades.json | grep -q '^\['; then
        # JSON數組格式，需要轉換
        python3 << 'PYTHON'
import json
with open('trades.json', 'r') as f:
    trades = json.load(f)
with open('trades.jsonl', 'w') as f:
    for trade in trades:
        f.write(json.dumps(trade) + '\n')
print(f"✅ 已轉換 {len(trades)} 筆交易記錄")
PYTHON
    else
        # 已是JSON Lines格式，直接重命名
        mv trades.json trades.jsonl
        echo "✅ 已重命名 trades.json → trades.jsonl"
    fi
fi
```

### 2. 驗證數據完整性

```bash
# 檢查文件大小
ls -lh data/trades.jsonl

# 檢查行數（交易數）
wc -l data/trades.jsonl

# 查看最後幾筆交易
tail -5 data/trades.jsonl

# 驗證JSON格式
tail -1 data/trades.jsonl | python3 -m json.tool
```

### 3. 監控數據保存

部署後監控日誌，確認數據正常保存：

```bash
# 監控Railway日誌
railway logs

# 應該看到這些日誌：
# ✅ 強制保存完成: 1 條完成交易, 0 條待配對
# 💾 保存 1 條交易記錄到磁盤
# 📊 統計: 待配對0條, 已完成1條（內存）, 磁盤文件大小: 256 bytes
```

### 4. 重啟測試

```bash
# 測試Graceful Shutdown
railway restart

# 檢查數據是否保留
railway shell
wc -l data/trades.jsonl
```

## 🎯 預期行為

### **正常情況**
1. 每筆交易立即保存到 `data/trades.jsonl`
2. Railway重啟時自動調用 `force_flush()`
3. 數據持久化，不會丟失
4. 模型評分正常顯示

### **異常情況排查**

#### 問題1：「🎯 模型評分: 無交易記錄」

**原因**：
- 本地Replit環境無法連接Binance（HTTP 451）
- Railway新部署環境尚未產生交易
- 文件為空（正常初始狀態）

**解決方案**：
- ✅ 這是正常的！等待第一筆交易完成後會顯示評分
- ✅ 檢查 `data/trades.jsonl` 是否有數據：`wc -l data/trades.jsonl`

#### 問題2：數據未保存

**檢查步驟**：
```bash
# 1. 確認配置
railway logs | grep "ML_FLUSH_COUNT"
# 應顯示：ML_FLUSH_COUNT: 1

# 2. 確認文件路徑
railway logs | grep "TRADES_FILE"
# 應顯示：data/trades.jsonl

# 3. 確認保存日誌
railway logs | grep "保存.*交易記錄"
# 應看到：💾 保存 1 條交易記錄到磁盤
```

#### 問題3：Shutdown時數據丟失

**檢查Signal Handler**：
```bash
railway logs | grep "信號處理器已註冊"
# 應看到：✅ 信號處理器已註冊（SIGINT, SIGTERM）

railway logs | grep "正在保存ML訓練數據"
# Railway重啟時應看到：💾 正在保存ML訓練數據...
```

## 📝 檢查清單

部署前：
- [ ] 代碼已推送到GitHub
- [ ] 確認 `src/config.py` 中 `TRADES_FILE` 為 `.jsonl`
- [ ] 確認 `ML_FLUSH_COUNT = 1`

部署後：
- [ ] 檢查舊數據文件是否需要遷移
- [ ] 驗證數據保存日誌正常
- [ ] 測試系統重啟數據保留
- [ ] 確認模型評分功能正常

## 🔍 數據完整性驗證腳本

創建驗證腳本在Railway上運行：

```python
# verify_ml_data.py
import json
import os

trades_file = "data/trades.jsonl"

if not os.path.exists(trades_file):
    print("❌ trades.jsonl 不存在")
    exit(1)

trades = []
with open(trades_file, 'r') as f:
    for line in f:
        if line.strip():
            trades.append(json.loads(line))

print(f"✅ 總交易數: {len(trades)}")
if trades:
    print(f"✅ 最早交易: {trades[0].get('entry_timestamp')}")
    print(f"✅ 最新交易: {trades[-1].get('entry_timestamp')}")
    
    closed = [t for t in trades if t.get('status') == 'closed']
    print(f"✅ 已平倉: {len(closed)} 筆")
else:
    print("⚠️ 尚無交易記錄（正常初始狀態）")
```

運行：
```bash
railway run python verify_ml_data.py
```

## ✅ 成功指標

部署成功後應看到：
1. ✅ 日誌中顯示「✅ 信號處理器已註冊」
2. ✅ 每筆交易後顯示「💾 保存 1 條交易記錄到磁盤」
3. ✅ `data/trades.jsonl` 文件持續增長
4. ✅ 重啟後數據不丟失
5. ✅ 模型評分正常顯示（有交易後）

---

**修復版本**：v3.18.4-hotfix-ml  
**修復時間**：2025-10-31  
**部署狀態**：🚀 準備部署到Railway
