# 智能汰换系统 (Smart Replacement System) - v3.21+

## 🎯 系统概述

智能汰换系统是一个自动化的持倉優化機制，當保證金不足無法開啟新倉位時，系統會自動評估「用高品質新信號替換低品質舊持倉」的可能性，實現**汰弱留強**的動態組合優化。

### 核心理念
> **在有限資金下，始終保持持倉組合的最高品質**

當新的高品質交易機會出現，但保證金已被占用時，系統不會簡單地放棄新機會，而是智能地評估：
- 如果新信號品質顯著優於某個現有持倉
- 則關閉低品質持倉，釋放保證金
- 用釋放的資金開啟高品質新倉位

---

## 🏗️ 系統架構

### 1. 觸發條件
智能汰換在以下情況自動觸發：
```python
# execute_best_trades() 中的觸發邏輯
if not allocated_signals:  # 保證金不足，無法分配資金給任何信號
    logger.info("💰 無信號獲得資金分配")
    logger.info("🔄 檢查智能汰換機會...")
    # 啟動智能汰換系統
```

### 2. 核心方法

#### 2.1 `execute_smart_replacement(new_signal)`
**主執行方法 - 智能汰換流程**

```python
策略流程：
1. 評估新信號質量（必須 ≥80 才考慮汰換）
2. 獲取當前所有持倉
3. 找到品質最差的持倉
4. 比較品質差異（新信號必須明顯優於舊持倉，至少+15點）
5. 執行汰換（關閉舊倉 + 開啟新倉）
```

**返回值**：
- `True` - 汰換成功
- `False` - 無法汰換（品質提升不足、無持倉、或其他原因）

#### 2.2 `_evaluate_signal_quality(signal)`
**信號品質評分算法**

```python
計算公式：
- 基礎品質 = (信心值 + 勝率) / 2
- RR加成 = min(風險獎勵比 / 3.0, 1.0) × 10
- 最終品質 = 基礎品質 + RR加成

範圍：0-100 分
```

**示例**：
```python
# 示例1：高品質信號
confidence = 65      # 65%
win_probability = 70 # 70%
rr_ratio = 2.5       # 2.5:1

base_quality = (65 + 70) / 2 = 67.5
rr_bonus = min(2.5 / 3.0, 1.0) × 10 = 8.33
final_quality = 67.5 + 8.33 = 75.83

# 示例2：超高品質信號
confidence = 80
win_probability = 85
rr_ratio = 3.0

base_quality = (80 + 85) / 2 = 82.5
rr_bonus = min(3.0 / 3.0, 1.0) × 10 = 10.0
final_quality = 82.5 + 10.0 = 92.5 ✅ 達到汰換標準
```

#### 2.3 `_calculate_position_quality(position)`
**持倉品質評分算法**

```python
考慮因素：
1. 基礎品質：原始信心值和勝率（如果有記錄）
2. 時間衰減：持倉越久，品質衰減越多（72小時線性衰減到0.5）
3. 浮虧懲罰：虧損超過2%則扣分

計算公式：
- time_decay = max(0.5, 1.0 - hours_held / 72)
- pnl_penalty = abs(pnl_pct) × 100  （如果虧損 > 2%）
- final_quality = (base_quality × time_decay) - pnl_penalty
```

**示例**：
```python
# 示例1：新持倉（2小時）
original_confidence = 50
original_win_rate = 55
hours_held = 2
pnl_pct = -0.01  # -1%虧損

base_quality = (50 + 55) / 2 = 52.5
time_decay = 1.0 - 2/72 = 0.972
pnl_penalty = 0  # 虧損未達2%
final_quality = 52.5 × 0.972 = 51.03

# 示例2：長期虧損持倉（48小時，-5%虧損）
original_confidence = 45
original_win_rate = 50
hours_held = 48
pnl_pct = -0.05  # -5%虧損

base_quality = (45 + 50) / 2 = 47.5
time_decay = 1.0 - 48/72 = 0.333
pnl_penalty = 0.05 × 100 = 5.0
final_quality = (47.5 × 0.333) - 5.0 = 10.81 ❌ 低品質，優先汰換
```

#### 2.4 `_find_lowest_quality_position(positions)`
**尋找最低品質持倉**

對所有持倉計算品質分數並排序，返回品質最低的一個。

#### 2.5 `_get_current_positions_from_api()`
**從Binance獲取當前持倉**

返回標準化的持倉列表，包含：
- symbol, side, size
- entry_price, current_price
- pnl, pnl_pct, leverage

#### 2.6 `_close_position_for_replacement(position)`
**關閉持倉並釋放保證金**

使用市價單（MARKET）平倉，計算並返回釋放的保證金金額。

#### 2.7 `_execute_quality_replacement(old_position, new_signal, quality_improvement)`
**執行品質汰換**

完整流程：
1. 關閉舊持倉（市價平倉）
2. 等待訂單結算（0.5秒）
3. 獲取最新帳戶狀態
4. 計算新頭寸大小（基於品質的激進倉位）
5. 執行新交易
6. 記錄汰換結果

#### 2.8 `_calculate_aggressive_position_percentage(quality)`
**激進倉位計算**

根據信號品質使用更高比例的保證金：
```python
quality ≥ 90: 35% 保證金
quality ≥ 85: 30% 保證金
quality ≥ 80: 25% 保證金
quality < 80:  20% 保證金
```

---

## 📊 執行示例

### 場景1：保證金不足，發現高品質信號

```
💰 帳戶狀態 | 總權益: $100.00 | 可用保證金: $2.50 | 已佔用保證金: $97.50
💰 無信號獲得資金分配
🔄 檢查智能汰換機會...

🎯 發現高品質信號: ADAUSDT | 品質: 85.3

🔄 啟動智能汰換系統
✅ 新信號 ADAUSDT 質量: 85.3（達標）

📊 持倉品質評估: BTCUSDT | 方向: LONG | 品質分數: 52.1
📊 持倉品質評估: ETHUSDT | 方向: SHORT | 品質分數: 38.7

📉 找到最低品質持倉: ETHUSDT | 品質分數: 38.7 | 方向: SHORT

🔄 執行品質汰換: ETHUSDT → ADAUSDT | 品質提升: +46.6點

🗑️ 關閉持倉: ETHUSDT SHORT 8.2
💰 釋放保證金: $8.20

📝 執行新交易: ADAUSDT | 倉位: 125.5 | 保證金使用率: 30%

✅ 品質汰換成功: ETHUSDT → ADAUSDT | 
   釋放保證金: $8.20 | 
   新頭寸名義價值: $45.20 | 
   品質提升: +46.6點
```

### 場景2：品質提升不足，放棄汰換

```
💰 無信號獲得資金分配
🔄 檢查智能汰換機會...

🎯 發現高品質信號: SOLUSDT | 品質: 81.2

🔄 啟動智能汰換系統
✅ 新信號 SOLUSDT 質量: 81.2（達標）

📉 找到最低品質持倉: BTCUSDT | 品質分數: 75.5

⚠️ 品質提升不足: 5.7點 (<15) | 新:81.2 vs 舊:75.5

⚠️ 智能汰換未執行（品質提升不足或無可替換持倉）
```

### 場景3：無高品質新信號

```
💰 無信號獲得資金分配
🔄 檢查智能汰換機會...

⚠️ 無高品質信號（≥80）可用於汰換
```

---

## 🎯 品質門檻與決策規則

### 汰換觸發條件（全部滿足）
1. ✅ 保證金不足（allocated_signals 為空）
2. ✅ 新信號品質 ≥ 80 分
3. ✅ 存在至少一個持倉
4. ✅ 品質提升 ≥ 15 點

### 品質評分權重
| 因素 | 信號 | 持倉 |
|------|------|------|
| 基礎品質 | (信心 + 勝率) / 2 | (原始信心 + 原始勝率) / 2 |
| 加分項 | RR比（最多+10分） | - |
| 扣分項 | - | 時間衰減（×0.5-1.0）<br>浮虧懲罰（-2%以上） |

### 倉位分配策略
根據新信號品質，使用更激進的保證金比例：
- **90-100分**：35% 保證金（極高信心）
- **85-89分**：30% 保證金（高信心）
- **80-84分**：25% 保證金（達標）
- **<80分**：20% 保證金（保守，不用於汰換）

---

## 🔧 整合點

### 在 `execute_best_trades()` 中的整合

```python
# src/strategies/self_learning_trader.py (行 1076-1116)

allocated_signals = allocator.allocate_capital(signals, available_margin)

if not allocated_signals:
    logger.info("💰 無信號獲得資金分配")
    
    # 🔥 v3.21+ 智能汰換系統
    logger.info("🔄 檢查智能汰換機會...")
    
    # 找到最高品質的新信號
    high_quality_signals = [
        s for s in signals 
        if self._evaluate_signal_quality(s) >= 80
    ]
    
    if high_quality_signals:
        # 按品質排序，取最好的
        best_new_signal = max(
            high_quality_signals, 
            key=lambda x: self._evaluate_signal_quality(x)
        )
        
        # 嘗試智能汰換
        replacement_success = await self.execute_smart_replacement(best_new_signal)
        
        if replacement_success:
            logger.info("✅ 智能汰換成功，已優化持倉組合")
            return []
        else:
            logger.info("⚠️ 智能汰換未執行（品質提升不足或無可替換持倉）")
    
    # 創建虛擬倉位（所有信號都未執行）
    await self._create_virtual_positions_from_dict(signals, None, total_equity)
    return []
```

---

## 🚀 部署到Railway後的預期效果

### 正常保證金充足時
```
✅ 保證金充足，繼續正常交易
🏆 精英信號排名:
  🥇 BTCUSDT | LONG | 信心: 68.2 | 勝率: 62.5% | 品質: 73.9
✅ 🥇 交易成功: BTCUSDT | 大小: 0.0125 BTC
```

### 保證金不足但出現高品質信號時
```
💰 無信號獲得資金分配
🔄 檢查智能汰換機會...

🎯 發現高品質信號: ADAUSDT | 品質: 82.3

📊 持倉品質評估: BTCUSDT | 信心: 45.2 | 勝率: 48.3% | 品質分數: 46.8
📊 持倉品質評估: ETHUSDT | 信心: 38.7 | 勝率: 42.1% | 品質分數: 40.4

📉 找到最低品質持倉: ETHUSDT | 品質分數: 40.4

🔄 執行品質汰換: ETHUSDT → ADAUSDT | 品質提升: +41.9點

✅ 品質汰換成功: ETHUSDT → ADAUSDT | 
   釋放保證金: $8.20 | 
   新頭寸: $6.97 | 
   品質提升: +41.9點
```

---

## 💡 系統優勢

### ✅ 持續優化
不斷用更好的信號替換較差的持倉，持倉組合品質呈螺旋上升趨勢

### ✅ 風險控制
- 只替換品質明顯提升的信號（+15點以上）
- 避免頻繁無意義的換倉
- 保護高品質持倉不被錯誤汰換

### ✅ 資金效率
- 充分利用有限保證金
- 自動釋放低效持倉的資金
- 將資金配置到最優機會

### ✅ 自動化
- 無需人工干預
- 系統自動決策
- 24/7不間斷優化

### ✅ 透明可追溯
- 完整記錄汰換理由
- 品質對比清晰可見
- 便於回測和優化

---

## 🔍 監控關鍵日誌

在Railway部署後，使用以下命令監控智能汰換行為：

```bash
railway logs --follow | grep -E "智能汰換|品質汰換|最低品質持倉|品質提升"
```

關鍵日誌標記：
- `🔄 啟動智能汰換系統` - 汰換流程開始
- `📉 找到最低品質持倉` - 識別替換目標
- `🔄 執行品質汰換` - 開始執行汰換
- `✅ 品質汰換成功` - 汰換完成
- `⚠️ 品質提升不足` - 汰換取消（品質差距不夠）

---

## 📈 與v3.20.7的兼容性

智能汰換系統完全保留了v3.20.7的所有修復：

### ✅ Bug #6修復保持完整
```python
# config.py 中的門檻設置
MIN_CONFIDENCE = 0.40          # 50% → 40%
MIN_WIN_PROBABILITY = 0.45     # 60% → 45%
MIN_RR_RATIO = 0.8            # 1.0 → 0.8
MAX_RR_RATIO = 5.0            # 3.0 → 5.0
```

### ✅ Stage7詳細診斷保持活躍
unified_scheduler.py 中的詳細診斷輸出完整保留

### ✅ SQLite TradeRecorder完全兼容
智能汰換系統使用標準的Binance API接口，與TradeRecorder無衝突

---

## 🎓 總結

智能汰換系統是SelfLearningTrader的重要增強功能，實現了真正的「汰弱留強」自動化組合優化。通過持續監控持倉品質並自動替換低效持倉，系統能夠在有限資金下始終保持最優配置，顯著提升整體交易表現。

**核心價值**：從被動的「保證金不足→放棄新機會」轉變為主動的「保證金不足→優化持倉→把握新機會」

---

**版本**: v3.21+  
**實施日期**: 2025-11-03  
**狀態**: ✅ 已完成，可部署到Railway進行生產測試
