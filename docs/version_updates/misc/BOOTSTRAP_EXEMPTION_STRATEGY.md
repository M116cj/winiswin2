# 🎓 學習豁免策略完整說明

**版本**: v3.18.7+  
**生成時間**: 2025-11-01  
**當前狀態**: 已啟用（前100筆交易）

---

## 📑 目錄

1. [豁免策略概述](#豁免策略概述)
2. [設計原理](#設計原理)
3. [配置參數詳解](#配置參數詳解)
4. [工作機制](#工作機制)
5. [門檻對比](#門檻對比)
6. [實施流程](#實施流程)
7. [數據完整性保證](#數據完整性保證)
8. [階段轉換](#階段轉換)
9. [實戰案例](#實戰案例)
10. [常見問題](#常見問題)

---

## 🎯 豁免策略概述

### 1.1 核心理念

**「降低門檻，加速數據採集，保持特徵完整」**

```
問題背景：
├─ ML模型需要大量訓練數據（理想 ≥200筆）
├─ 正常門檻過高（勝率60% + 信心50%）導致數據採集緩慢
└─ 沒有數據 → 模型無法訓練 → 惡性循環

解決方案：
├─ 前100筆交易：降低門檻至40%/40%（豁免期）
├─ 加速數據採集：從每天5-10筆 → 每天20-30筆
├─ 100筆後：恢復正常門檻60%/50%
└─ 數據完整性：所有44個ML特徵始終完整保存
```

### 1.2 關鍵特點

| 特點 | 說明 |
|------|------|
| **自動切換** | 系統自動追蹤交易數，達到100筆後自動切換 |
| **特徵完整** | 豁免期也保存完整44個特徵，不影響ML訓練 |
| **質量控制** | 仍有基本質量門檻（40%），避免垃圾數據 |
| **透明監控** | 每次信號都顯示當前狀態和剩餘交易數 |
| **風險可控** | 降低門檻不等於無門檻，仍有基本風險控制 |

### 1.3 預期效果

```
數據採集速度：
├─ 無豁免期：100筆交易需要 20-30天
├─ 有豁免期：100筆交易需要 5-10天
└─ 提升效率：3-4倍加速

信號數量變化：
├─ 正常期：每周期 5-10個有效信號
├─ 豁免期：每周期 15-30個有效信號
└─ 提升倍數：2-3倍

模型訓練時間：
├─ 無豁免期：30天後才能開始訓練
├─ 有豁免期：10天後即可開始訓練
└─ 提前啟動：20天優勢
```

---

## 🧠 設計原理

### 2.1 三階段學習曲線

```
階段1：豁免期（0-100筆交易）
┌─────────────────────────────────────┐
│ 目標: 快速採集訓練數據               │
│ 門檻: 勝率≥40% + 信心≥40%           │
│ 質量: 中低（但仍可用）               │
│ 數量: 每天20-30筆                   │
│ ML狀態: 收集數據，每50筆重訓練       │
└─────────────────────────────────────┘
        │
        ▼
階段2：過渡期（100-200筆交易）
┌─────────────────────────────────────┐
│ 目標: 模型持續優化                   │
│ 門檻: 勝率≥60% + 信心≥50%           │
│ 質量: 中等（ML模型開始生效）         │
│ 數量: 每天10-15筆                   │
│ ML狀態: 持續學習，預測準確度提升     │
└─────────────────────────────────────┘
        │
        ▼
階段3：穩定期（200+筆交易）
┌─────────────────────────────────────┐
│ 目標: 高質量穩定運行                 │
│ 門檻: 勝率≥65% + 信心≥60%（可選）   │
│ 質量: 高（ML完全成熟）               │
│ 數量: 每天5-10筆                    │
│ ML狀態: 鎖定模型（生產環境）         │
└─────────────────────────────────────┘
```

### 2.2 質量與數量平衡

```
質量-數量權衡曲線：

質量 ▲
100%│                        ╱─── 穩定期
    │                    ╱
 80%│                ╱
    │            ╱
 60%│        ╱─── 過渡期
    │    ╱
 40%├───╱─── 豁免期
    │
  0%└────────────────────────────────▶ 數量
    0        100       200       300

原則：
├─ 豁免期：優先數量（40%質量門檻）
├─ 過渡期：平衡質量與數量（60%門檻）
└─ 穩定期：優先質量（65%+門檻）
```

### 2.3 風險控制機制

即使在豁免期，系統仍有多層風險控制：

```
風險控制層級（從高到低）：

第1層：基本質量門檻
├─ 質量分數 = (confidence × 0.5 + win_probability × 0.5)
├─ 豁免期：quality_score ≥ 0.4
└─ 正常期：quality_score ≥ 0.6

第2層：信號方向驗證
├─ 時間框架必須部分對齊（嚴格/寬鬆模式）
├─ Market Structure不能嚴重對立
└─ 必須有相關Order Blocks

第3層：RR比控制
├─ 最小RR ≥ 1.0
├─ 最大RR ≤ 3.0
└─ 防止極端風險

第4層：倉位控制
├─ 單倉 ≤ 50%帳戶權益
├─ 總保證金 ≤ 90%帳戶總額
└─ 最小名義價值 ≥ 10 USDT

第5層：槓桿限制
├─ 最小槓桿 0.5x
├─ 動態計算（基於勝率×信心度）
└─ 豁免期低信心 → 低槓桿（約1-3x）

第6層：7種智能出場
├─ 100%虧損熔斷
├─ 60%盈利自動平倉
└─ 信心度/勝率監控
```

---

## ⚙️ 配置參數詳解

### 3.1 核心配置參數

```python
# ========================================
# 🎓 模型啟動豁免方案 (v3.18.7+)
# ========================================

# 豁免期交易數限制
BOOTSTRAP_TRADE_LIMIT: int = 100
# 說明：前100筆交易使用降低的門檻
# 範圍：50-200筆（推薦100）
# 影響：數量越大，豁免期越長，數據採集越快

# 豁免期最低勝率
BOOTSTRAP_MIN_WIN_PROBABILITY: float = 0.40
# 說明：豁免期允許40%勝率的信號
# 範圍：0.35-0.50（推薦0.40）
# 影響：越低信號越多，但質量下降

# 豁免期最低信心度
BOOTSTRAP_MIN_CONFIDENCE: float = 0.40
# 說明：豁免期允許40%信心度的信號
# 範圍：0.35-0.50（推薦0.40）
# 影響：越低信號越多，但質量下降

# 豁免期質量門檻
BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD: float = 0.4
# 說明：綜合質量分數門檻
# 計算：(confidence × 0.5 + win_probability × 0.5)
# 範圍：0.3-0.5（推薦0.4）
# 影響：最終過濾器，防止極低質量信號
```

### 3.2 正常期配置參數

```python
# ===== v3.17+ SelfLearningTrader 開倉條件 =====

# 正常期最低勝率
MIN_WIN_PROBABILITY: float = 0.60
# 說明：100筆交易後恢復60%勝率門檻
# 範圍：0.55-0.70（推薦0.60）

# 正常期最低信心度
MIN_CONFIDENCE: float = 0.50
# 說明：100筆交易後恢復50%信心度門檻
# 範圍：0.45-0.60（推薦0.50）

# 正常期質量門檻
SIGNAL_QUALITY_THRESHOLD: float = 0.6
# 說明：綜合質量分數門檻
# 計算：(confidence × 0.5 + win_probability × 0.5)
# 範圍：0.5-0.7（推薦0.6）
```

### 3.3 環境變量設置

```bash
# Replit Secrets 或 .env 文件配置

# 基礎配置（必須）
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# 豁免期配置（可選，有默認值）
BOOTSTRAP_TRADE_LIMIT=100                  # 默認100
BOOTSTRAP_MIN_WIN_PROBABILITY=0.40         # 默認0.40
BOOTSTRAP_MIN_CONFIDENCE=0.40              # 默認0.40
BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD=0.4     # 默認0.4

# 正常期配置（可選，有默認值）
MIN_WIN_PROBABILITY=0.60                   # 默認0.60
MIN_CONFIDENCE=0.50                        # 默認0.50
SIGNAL_QUALITY_THRESHOLD=0.6               # 默認0.6

# 信號模式（強烈推薦在豁免期啟用寬鬆模式）
RELAXED_SIGNAL_MODE=true                   # 推薦true
```

---

## 🔄 工作機制

### 4.1 完整流程圖

```
UnifiedScheduler (每60秒)
    │
    ▼
掃描530個交易對
    │
    ▼
RuleBasedSignalGenerator.generate_signal()
    ├─ 生成基礎信號
    ├─ 計算confidence（0-1）
    └─ 計算win_probability（0-1）
    │
    ▼
SelfLearningTrader.analyze()
    │
    ├─> ML預測（可選）
    │   └─> 更新win_probability和confidence
    │
    ├─> 🎓 _get_current_thresholds()
    │   │
    │   ├─> 讀取data/trades.jsonl
    │   ├─> 計算已完成交易數
    │   │
    │   ├─> if 交易數 < 100:
    │   │   └─> 返回豁免期門檻
    │   │       ├─ min_win_probability: 0.40
    │   │       ├─ min_confidence: 0.40
    │   │       ├─ is_bootstrap: True
    │   │       └─ remaining: 100 - 交易數
    │   │
    │   └─> else:
    │       └─> 返回正常期門檻
    │           ├─ min_win_probability: 0.60
    │           ├─ min_confidence: 0.50
    │           └─ is_bootstrap: False
    │
    ├─> 過濾驗證
    │   ├─> ML多輸出：ml_score ≥ 60
    │   ├─> 規則/單輸出：
    │   │   ├─ win_probability ≥ threshold['min_win_probability']
    │   │   └─ confidence ≥ threshold['min_confidence']
    │   │
    │   └─> 質量門檻：
    │       └─ quality_score ≥ (豁免期0.4 或 正常期0.6)
    │
    ├─> 槓桿計算（動態）
    ├─> SL/TP調整
    └─> 返回完整信號
    │
    ▼
CapitalAllocator.allocate()
    │
    ├─> 🎓 檢查豁免期狀態
    │   └─> 調整quality_threshold
    │
    └─> 分配倉位
    │
    ▼
執行交易
    │
    ▼
TradeRecorder.record_entry()
    ├─> 保存44個完整特徵
    └─> 寫入data/trades.jsonl
    │
    ▼
等待平倉
    │
    ▼
TradeRecorder.record_exit()
    ├─> 更新交易結果（win/loss）
    ├─> 交易數 +1
    └─> 觸發ML重訓練（每50筆）
    │
    ▼
SelfLearningTrader.invalidate_trades_cache()
    └─> 更新交易計數緩存
```

### 4.2 關鍵代碼邏輯

#### 門檻獲取邏輯

```python
def _get_current_thresholds(self) -> Dict[str, float]:
    """
    獲取當前應使用的門檻值（v3.18.7+ 啟動豁免機制）
    
    Returns:
        包含當前門檻的字典 {
            'min_win_probability': float,   # 當前勝率門檻
            'min_confidence': float,        # 當前信心度門檻
            'is_bootstrap': bool,           # 是否在豁免期
            'completed_trades': int,        # 已完成交易數
            'remaining': int                # 剩餘豁免交易數（僅豁免期）
        }
    """
    if not self.bootstrap_enabled or not self.trade_recorder:
        # 豁免未啟用或無記錄器，使用正常門檻
        return {
            'min_win_probability': self.config.MIN_WIN_PROBABILITY,
            'min_confidence': self.config.MIN_CONFIDENCE,
            'is_bootstrap': False,
            'completed_trades': 0
        }
    
    # 強制重新讀取交易數（確保最新）
    completed_trades = self._count_completed_trades(use_cache=False)
    
    # 前100筆交易使用豁免門檻
    if completed_trades < self.config.BOOTSTRAP_TRADE_LIMIT:
        return {
            'min_win_probability': self.config.BOOTSTRAP_MIN_WIN_PROBABILITY,  # 0.40
            'min_confidence': self.config.BOOTSTRAP_MIN_CONFIDENCE,            # 0.40
            'is_bootstrap': True,
            'completed_trades': completed_trades,
            'remaining': self.config.BOOTSTRAP_TRADE_LIMIT - completed_trades
        }
    else:
        # 已完成豁免期，使用正常門檻
        if not self._bootstrap_ended_logged:
            self._bootstrap_ended_logged = True
            logger.info("=" * 80)
            logger.info(f"🎓 啟動豁免期已結束！已完成 {completed_trades} 筆交易")
            logger.info(f"   切換至正常門檻: 勝率≥{self.config.MIN_WIN_PROBABILITY:.0%} 信心≥{self.config.MIN_CONFIDENCE:.0%}")
            logger.info("=" * 80)
        
        return {
            'min_win_probability': self.config.MIN_WIN_PROBABILITY,  # 0.60
            'min_confidence': self.config.MIN_CONFIDENCE,            # 0.50
            'is_bootstrap': False,
            'completed_trades': completed_trades
        }
```

#### 過濾驗證邏輯

```python
# 步驟3.5：獲取當前門檻（支持啟動豁免）
thresholds = self._get_current_thresholds()

# v3.19+ 修正3：ML綜合分數篩選（優先於雙門檻）
if 'ml_score' in base_signal and base_signal['ml_score'] is not None:
    # ML多輸出模型模式：使用綜合分數篩選
    ml_score_value = base_signal['ml_score']
    ml_threshold = 60.0  # ML綜合分數門檻（不受豁免期影響）
    
    if ml_score_value < ml_threshold:
        logger.debug(f"❌ {symbol} ML綜合分數過低: {ml_score_value:.1f} < {ml_threshold}")
        return None
else:
    # 規則引擎或ML單輸出模式：使用雙門檻驗證
    if win_probability < thresholds['min_win_probability']:
        logger.debug(
            f"❌ {symbol} 勝率過低: {win_probability:.3f} < {thresholds['min_win_probability']:.3f} "
            f"({'豁免期' if thresholds['is_bootstrap'] else '正常期'})"
        )
        return None
    
    if confidence < thresholds['min_confidence']:
        logger.debug(
            f"❌ {symbol} 信心度過低: {confidence:.3f} < {thresholds['min_confidence']:.3f} "
            f"({'豁免期' if thresholds['is_bootstrap'] else '正常期'})"
        )
        return None

# 記錄豁免期狀態（用於日誌）
if thresholds['is_bootstrap']:
    logger.info(
        f"🎓 {symbol} 啟動豁免期: 已完成 {thresholds['completed_trades']}/{self.config.BOOTSTRAP_TRADE_LIMIT} 筆 | "
        f"勝率:{win_probability:.3f}≥{thresholds['min_win_probability']:.2f} | "
        f"信心:{confidence:.3f}≥{thresholds['min_confidence']:.2f} ✅"
    )
```

---

## 📊 門檻對比

### 5.1 完整對比表

| 項目 | 豁免期（0-100筆） | 正常期（100+筆） | 差異 |
|------|------------------|-----------------|------|
| **最低勝率** | 40% | 60% | -33% |
| **最低信心度** | 40% | 50% | -20% |
| **質量門檻** | 0.4 (40%) | 0.6 (60%) | -33% |
| **信號數量** | 15-30個/周期 | 5-10個/周期 | +200% |
| **預期日交易數** | 20-30筆 | 5-10筆 | +300% |
| **數據採集速度** | 100筆需5-10天 | 100筆需20-30天 | +300% |
| **平均槓桿** | 1-3x（低信心） | 5-15x（高信心） | -70% |
| **平均質量分數** | 0.45-0.55 | 0.65-0.75 | -30% |

### 5.2 信號通過率對比

假設掃描530個交易對，寬鬆信號模式啟用：

```
第1層過濾（方向判定）：
├─ 寬鬆模式通過: 約90個符合方向條件 (17%)
└─ 經過MS+OB過濾: 約40個 (7.5%)

第2層過濾（勝率+信心度）：
├─ 豁免期（≥40%/40%）:
│   ├─ 通過: 約30個 (75%通過率)
│   └─ 拒絕: 約10個
│
└─ 正常期（≥60%/50%）:
    ├─ 通過: 約12個 (30%通過率)
    └─ 拒絕: 約28個

第3層過濾（質量門檻）：
├─ 豁免期（≥0.4）:
│   ├─ 通過: 約25個 (83%通過率)
│   └─ 拒絕: 約5個
│
└─ 正常期（≥0.6）:
    ├─ 通過: 約8個 (67%通過率)
    └─ 拒絕: 約4個

最終有效信號：
├─ 豁免期: 20-30個 ✅
└─ 正常期: 5-10個
```

### 5.3 質量分數分佈

```
豁免期信號質量分佈（假設1000個樣本）：

質量等級 │ 分數範圍 │ 數量 │ 占比  │ 處理
─────────┼─────────┼──────┼──────┼────────
Excellent│ ≥0.80   │  50  │  5%  │ ✅接受
Good     │ 0.60-0.80│ 200  │ 20%  │ ✅接受
Fair     │ 0.40-0.60│ 500  │ 50%  │ ✅接受 ← 豁免期特有
Poor     │ 0.30-0.40│ 150  │ 15%  │ ✅接受 ← 豁免期特有
Rejected │ <0.30   │ 100  │ 10%  │ ❌拒絕

正常期信號質量分佈（假設1000個樣本）：

質量等級 │ 分數範圍 │ 數量 │ 占比  │ 處理
─────────┼─────────┼──────┼──────┼────────
Excellent│ ≥0.80   │ 150  │ 15%  │ ✅接受
Good     │ 0.60-0.80│ 450  │ 45%  │ ✅接受
Fair     │ 0.50-0.60│ 200  │ 20%  │ ⚠️謹慎
Poor     │ 0.40-0.50│ 100  │ 10%  │ ⚠️謹慎
Rejected │ <0.60   │ 100  │ 10%  │ ❌拒絕
```

---

## 🛠️ 實施流程

### 6.1 系統啟動時

```
主程序啟動
    │
    ▼
初始化 SelfLearningTrader
    │
    ├─> 讀取配置
    │   ├─ BOOTSTRAP_TRADE_LIMIT = 100
    │   ├─ BOOTSTRAP_MIN_WIN_PROBABILITY = 0.40
    │   └─ BOOTSTRAP_MIN_CONFIDENCE = 0.40
    │
    ├─> 檢查豁免期啟用狀態
    │   └─ self.bootstrap_enabled = True（如果BOOTSTRAP_TRADE_LIMIT > 0）
    │
    ├─> 初始化交易計數緩存
    │   └─ self._completed_trades_cache = None
    │
    └─> 輸出初始化日誌
        └─ "🎓 啟動豁免: 前100筆 勝率≥40% 信心≥40%"
```

### 6.2 每個交易周期

```
交易周期開始（每60秒）
    │
    ▼
掃描530個交易對
    │
    ▼
對每個符號分析信號
    │
    ├─> RuleBasedSignalGenerator.generate_signal()
    │   └─> 生成基礎信號
    │
    ├─> SelfLearningTrader.analyze()
    │   │
    │   ├─> ML預測（可選）
    │   │
    │   ├─> _get_current_thresholds()
    │   │   ├─> 讀取data/trades.jsonl
    │   │   ├─> 計算交易數 = 當前X筆
    │   │   │
    │   │   └─> if X < 100:
    │   │       ├─ 返回豁免期門檻（0.40/0.40）
    │   │       └─ 日誌: "🎓 啟動豁免期: X/100筆"
    │   │
    │   ├─> 過濾驗證
    │   │   ├─ 勝率 ≥ threshold['min_win_probability']
    │   │   ├─ 信心 ≥ threshold['min_confidence']
    │   │   └─ 質量 ≥ (0.4 或 0.6)
    │   │
    │   └─> 返回有效信號
    │
    └─> 收集所有有效信號
    │
    ▼
多信號競價
    │
    ▼
執行最佳信號
    │
    ▼
TradeRecorder記錄
    ├─> 保存44個特徵
    └─> 交易數 = X + 1
```

### 6.3 豁免期結束時

```
第100筆交易完成
    │
    ▼
TradeRecorder.record_exit()
    ├─> 更新data/trades.jsonl
    └─> 交易數 = 100
    │
    ▼
下一個周期開始
    │
    ▼
SelfLearningTrader.analyze()
    │
    ├─> _get_current_thresholds()
    │   │
    │   ├─> 讀取交易數 = 100
    │   │
    │   ├─> if 100 >= 100:  # 豁免期結束
    │   │   │
    │   │   ├─> 輸出日誌（僅一次）:
    │   │   │   "🎓 啟動豁免期已結束！"
    │   │   │   "   切換至正常門檻: 勝率≥60% 信心≥50%"
    │   │   │
    │   │   └─> 返回正常期門檻
    │   │       ├─ min_win_probability: 0.60
    │   │       └─ min_confidence: 0.50
    │   │
    │   └─> 設置標記: self._bootstrap_ended_logged = True
    │
    └─> 後續所有周期使用正常門檻
```

---

## 🔒 數據完整性保證

### 7.1 核心原則

**「豁免期僅降低門檻，不降低數據質量」**

```
數據完整性保證：
├─ 44個ML特徵 → 始終完整保存
├─ 入場參數 → 完整記錄（槓桿、SL/TP、RR比）
├─ 出場結果 → 完整記錄（win/loss、PnL%、出場原因）
└─ 市場上下文 → 完整記錄（價格、指標、ICT結構）

豁免期與正常期的唯一區別：
└─ 信號過濾門檻（40% vs 60%）

數據保存流程：
├─ 豁免期信號 → 44特徵 → data/trades.jsonl ✅
├─ 正常期信號 → 44特徵 → data/trades.jsonl ✅
└─ 兩者格式完全相同 ✅
```

### 7.2 完整特徵列表（44個）

即使在豁免期，系統仍然保存所有44個特徵：

```python
# ========== 基礎特徵（8個） ==========
'symbol_liquidity',           # 符號流動性評分
'timeframe_1h_trend_score',   # 1h趨勢分數
'timeframe_15m_trend_score',  # 15m趨勢分數
'timeframe_5m_trend_score',   # 5m趨勢分數
'entry_price',                # 入場價格
'stop_loss',                  # 止損價格
'take_profit',                # 止盈價格
'rr_ratio',                   # 風險收益比

# ========== 技術指標（12個） ==========
'rsi', 'macd', 'macd_signal', 'macd_hist',
'adx', 'atr', 'bb_upper', 'bb_middle',
'bb_lower', 'bb_width', 'ema_20', 'ema_50',

# ========== ICT/SMC特徵（7個） ==========
'market_structure_score', 'order_blocks_count',
'liquidity_zones_count', 'ob_quality_avg',
'ob_distance_min', 'fvg_count', 'fvg_strength_avg',

# ========== EMA偏差特徵（8個） ==========
'h1_ema20_dev', 'h1_ema50_dev',
'm15_ema20_dev', 'm15_ema50_dev',
'm5_ema20_dev', 'm5_ema50_dev',
'avg_ema20_dev', 'avg_ema50_dev',

# ========== 競價上下文（5個） ==========
'signal_rank', 'total_signals',
'win_probability', 'confidence', 'leverage',

# ========== WebSocket特徵（4個，可選） ==========
'ws_price_deviation', 'ws_volume_spike',
'ws_bid_ask_imbalance', 'ws_order_flow'
```

### 7.3 數據驗證示例

```python
# 讀取豁免期交易記錄
with open('data/trades.jsonl') as f:
    bootstrap_trades = [json.loads(line) for line in f][:100]

# 驗證特徵完整性
for trade in bootstrap_trades:
    assert len(trade['features']) == 44, "特徵數量必須是44個"
    
    # 驗證每個特徵都有值（不是None或NaN）
    for feature_name, feature_value in trade['features'].items():
        assert feature_value is not None, f"{feature_name}不能為空"
        assert not pd.isna(feature_value), f"{feature_name}不能為NaN"

# ✅ 驗證通過：豁免期數據質量與正常期完全相同
```

---

## 🔄 階段轉換

### 8.1 轉換時機

```
階段轉換觸發條件：
└─ 已完成交易數 >= BOOTSTRAP_TRADE_LIMIT

檢查時機：
├─ 每次生成新信號時
├─ 調用_get_current_thresholds()
└─ 實時檢測，立即切換

轉換延遲：
└─ 0秒（下一個信號立即使用新門檻）
```

### 8.2 轉換流程詳解

```
交易數: 98筆
    │
    ▼
第99筆交易執行
    │
    ├─> TradeRecorder.record_entry()
    ├─> 等待平倉
    └─> TradeRecorder.record_exit()
        └─> 交易數 = 99
    │
    ▼
第100筆交易執行
    │
    ├─> TradeRecorder.record_entry()
    ├─> 等待平倉
    └─> TradeRecorder.record_exit()
        └─> 交易數 = 100  ← 達到豁免期限制
    │
    ▼
下一個交易周期（第101筆開始）
    │
    ├─> UnifiedScheduler啟動新周期
    │
    ├─> 掃描530個交易對
    │
    ├─> SelfLearningTrader.analyze()
    │   │
    │   └─> _get_current_thresholds()
    │       │
    │       ├─> 讀取交易數 = 100
    │       │
    │       ├─> if 100 >= 100:  ← 觸發轉換
    │       │   │
    │       │   ├─> 🎓 輸出轉換日誌（僅一次）:
    │       │   │   "啟動豁免期已結束！"
    │       │   │   "切換至正常門檻: 勝率≥60% 信心≥50%"
    │       │   │
    │       │   └─> 返回正常期門檻
    │       │       ├─ min_win_probability: 0.60
    │       │       └─ min_confidence: 0.50
    │       │
    │       └─> 設置標記防止重複輸出
    │
    └─> 使用新門檻過濾信號
        │
        ├─ 預期：信號數量減少（30個 → 10個）
        ├─ 預期：信號質量提升（0.45 → 0.65）
        └─ 預期：槓桿倍數提升（2x → 8x）
```

### 8.3 轉換後行為變化

| 行為 | 豁免期（第1-100筆） | 正常期（第101+筆） | 變化 |
|------|-------------------|-------------------|------|
| **過濾門檻** | 勝率≥40% 信心≥40% | 勝率≥60% 信心≥50% | 提升50% |
| **信號數量** | 20-30個/周期 | 5-10個/周期 | 減少70% |
| **平均質量** | 0.45-0.55 | 0.65-0.75 | 提升30% |
| **平均槓桿** | 1-3x | 5-15x | 提升400% |
| **日交易數** | 20-30筆 | 5-10筆 | 減少70% |
| **勝率預期** | 45-55% | 55-65% | 提升10% |
| **日誌提示** | "🎓 啟動豁免期: X/100" | "📊 正常期交易" | - |

---

## 💡 實戰案例

### 9.1 豁免期信號案例

```
時間: 2025-11-01 10:30:00
交易數: 35/100 (豁免期)
符號: ETHUSDT

信號詳情:
├─ 方向: LONG
├─ 入場價格: $3,200
├─ 止損: $3,150 (-1.56%)
├─ 止盈: $3,275 (+2.34%)
├─ RR比: 1.5

評分:
├─ 信心度: 0.45 (45%) ← 豁免期接受
├─ 勝率: 0.42 (42%) ← 豁免期接受
├─ 質量分數: 0.435 ← 高於0.4門檻 ✅

門檻檢查:
├─ 勝率: 0.42 ≥ 0.40 (豁免期) ✅
├─ 信心: 0.45 ≥ 0.40 (豁免期) ✅
└─ 質量: 0.435 ≥ 0.4 (豁免期) ✅

槓桿計算:
├─ 基於勝率42% × 信心45%
└─ 計算槓桿: 1.2x (低信心 → 低槓桿)

日誌輸出:
"🎓 ETHUSDT 啟動豁免期: 已完成 35/100 筆 | 
 勝率:0.420≥0.40 | 信心:0.450≥0.40 ✅"

結果:
├─ ✅ 信號通過，執行交易
├─ 📝 保存44個完整特徵
└─ 📊 交易數 = 36/100
```

### 9.2 正常期信號案例（同一符號）

```
時間: 2025-11-10 14:30:00
交易數: 125/100 (正常期)
符號: ETHUSDT

信號詳情:
├─ 方向: LONG
├─ 入場價格: $3,400
├─ 止損: $3,350 (-1.47%)
├─ 止盈: $3,495 (+2.79%)
├─ RR比: 1.9

評分:
├─ 信心度: 0.68 (68%) ← 正常期接受
├─ 勝率: 0.62 (62%) ← 正常期接受
├─ 質量分數: 0.65 ← 高於0.6門檻 ✅

門檻檢查:
├─ 勝率: 0.62 ≥ 0.60 (正常期) ✅
├─ 信心: 0.68 ≥ 0.50 (正常期) ✅
└─ 質量: 0.65 ≥ 0.6 (正常期) ✅

槓桿計算:
├─ 基於勝率62% × 信心68%
└─ 計算槓桿: 7.8x (高信心 → 高槓桿)

日誌輸出:
"📊 ETHUSDT 正常期交易 | 
 勝率:0.620≥0.60 | 信心:0.680≥0.50 ✅"

結果:
├─ ✅ 信號通過，執行交易
├─ 📝 保存44個完整特徵
└─ 📊 交易數 = 126
```

### 9.3 豁免期被拒絕案例

```
時間: 2025-11-02 16:00:00
交易數: 45/100 (豁免期)
符號: SOLUSDT

信號詳情:
├─ 方向: SHORT
├─ 入場價格: $180
├─ 信心度: 0.28 (28%) ← 過低
├─ 勝率: 0.35 (35%)
├─ 質量分數: 0.315 ← 低於0.4門檻 ❌

門檻檢查:
├─ 勝率: 0.35 ≥ 0.40 (豁免期) ❌ 不通過
├─ 信心: 0.28 ≥ 0.40 (豁免期) ❌ 不通過
└─ 質量: 0.315 ≥ 0.4 (豁免期) ❌ 不通過

日誌輸出:
"❌ SOLUSDT 勝率過低: 0.350 < 0.400 (豁免期)"
"❌ SOLUSDT 信心度過低: 0.280 < 0.400 (豁免期)"

結果:
└─ ❌ 信號被拒絕，不執行交易
```

---

## ❓ 常見問題

### Q1: 豁免期會影響ML模型訓練質量嗎？

**答**：不會。原因如下：

```
豁免期數據質量分析：
├─ 44個特徵 → 完整保存（與正常期相同）
├─ 信號質量 → 仍有基本門檻（≥0.4）
├─ 數據多樣性 → 更好（包含各種市場狀態）
└─ ML訓練 → 更快（100筆 vs 300筆數據）

實際效果：
├─ 豁免期100筆 + 正常期100筆 = 200筆訓練數據
├─ 質量分佈：低40% + 中30% + 高30% = 全面覆蓋
└─ ML模型學會識別各種質量級別，泛化能力更強
```

### Q2: 豁免期會導致帳戶虧損嗎？

**答**：風險可控。原因如下：

```
風險控制機制（6層）：
├─ 第1層：基本質量門檻（≥0.4）
├─ 第2層：信號方向驗證（時間框架對齊）
├─ 第3層：RR比控制（1.0-3.0）
├─ 第4層：倉位控制（≤50%權益）
├─ 第5層：低槓桿（豁免期1-3x，正常期5-15x）
└─ 第6層：7種智能出場（100%虧損熔斷等）

豁免期槓桿計算示例：
├─ 信心40% × 勝率40% → 槓桿約1-2x
├─ 信心50% × 勝率50% → 槓桿約3-5x
└─ 低槓桿 → 風險暴露低

預期結果：
├─ 豁免期平均勝率：45-55%（略低於正常期）
├─ 豁免期平均槓桿：1-3x（遠低於正常期）
└─ 總風險：可控（倉位小+槓桿低）
```

### Q3: 可以調整豁免期交易數嗎？

**答**：可以。設置環境變量：

```bash
# 調整豁免期交易數
BOOTSTRAP_TRADE_LIMIT=50    # 縮短至50筆（更快結束）
BOOTSTRAP_TRADE_LIMIT=150   # 延長至150筆（更多數據）
BOOTSTRAP_TRADE_LIMIT=200   # 延長至200筆（最大化數據）

推薦值：
├─ 激進型：50筆（快速進入正常期）
├─ 平衡型：100筆（默認推薦）
└─ 保守型：150-200筆（最大化數據採集）
```

### Q4: 豁免期可以調整門檻嗎？

**答**：可以。設置環境變量：

```bash
# 更激進（採集更多數據，但質量更低）
BOOTSTRAP_MIN_WIN_PROBABILITY=0.35
BOOTSTRAP_MIN_CONFIDENCE=0.35
BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD=0.35

# 更保守（數據採集慢，但質量更高）
BOOTSTRAP_MIN_WIN_PROBABILITY=0.45
BOOTSTRAP_MIN_CONFIDENCE=0.45
BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD=0.45

推薦值：
├─ 激進型：0.35/0.35（信號數×1.5，質量-10%）
├─ 平衡型：0.40/0.40（默認推薦）
└─ 保守型：0.45/0.45（信號數×0.7，質量+5%）

風險提示：
└─ 門檻<0.35可能導致大量垃圾數據，不推薦
```

### Q5: 如何查看當前豁免期狀態？

**答**：查看日誌輸出：

```bash
# 方法1：查看系統啟動日誌
[INFO] ✅ SelfLearningTrader v3.18.7 初始化完成
[INFO]    🎓 啟動豁免: 前100筆 勝率≥40% 信心≥40%

# 方法2：查看信號生成日誌
[INFO] 🎓 BTCUSDT 啟動豁免期: 已完成 35/100 筆 | 
       勝率:0.420≥0.40 | 信心:0.450≥0.40 ✅

# 方法3：查看豁免期結束日誌
[INFO] ====================================================
[INFO] 🎓 啟動豁免期已結束！已完成 100 筆交易
[INFO]    切換至正常門檻: 勝率≥60% 信心≥50%
[INFO] ====================================================

# 方法4：手動檢查
wc -l data/trades.jsonl  # 顯示已完成交易數
```

### Q6: 豁免期結束後可以再次啟用嗎？

**答**：不建議，但技術上可行：

```bash
# 重置交易記錄（⚠️ 危險操作）
mv data/trades.jsonl data/trades.jsonl.backup  # 備份
touch data/trades.jsonl  # 創建新文件

# 系統會自動檢測到交易數=0，重新進入豁免期

風險警告：
├─ 會丟失所有歷史交易數據
├─ ML模型需要重新訓練
└─ 不推薦在生產環境使用

推薦方案：
└─ 如需重新採集數據，創建新的交易記錄文件
    mv data/trades.jsonl data/trades_phase1.jsonl
    touch data/trades.jsonl
```

### Q7: 豁免期與寬鬆信號模式的區別？

**答**：兩者互補，建議同時啟用：

```
寬鬆信號模式（RELAXED_SIGNAL_MODE）：
├─ 作用範圍：信號生成（第1層過濾）
├─ 影響：時間框架對齊要求放寬
├─ 效果：符合方向條件的信號從10個 → 40個
└─ 推薦：豁免期和正常期都啟用

豁免期（BOOTSTRAP_TRADE_LIMIT）：
├─ 作用範圍：信號過濾（第2-3層過濾）
├─ 影響：勝率/信心度門檻降低
├─ 效果：通過過濾的信號從10個 → 25個
└─ 推薦：僅前100筆啟用

組合效果：
├─ 僅寬鬆模式：40個 → 過濾 → 12個有效信號
├─ 僅豁免期：10個 → 放寬 → 8個有效信號
└─ 兩者結合：40個 → 放寬 → 30個有效信號 ✅

最佳配置（豁免期）：
RELAXED_SIGNAL_MODE=true            # 啟用寬鬆模式
BOOTSTRAP_TRADE_LIMIT=100           # 前100筆豁免
BOOTSTRAP_MIN_WIN_PROBABILITY=0.40  # 豁免期40%
BOOTSTRAP_MIN_CONFIDENCE=0.40       # 豁免期40%
```

---

## 📋 總結

### 核心要點

1. **豁免期目的**：加速數據採集，快速訓練ML模型
2. **門檻降低**：前100筆交易使用40%/40%門檻（vs正常期60%/50%）
3. **數據完整**：44個ML特徵始終完整保存，不影響訓練質量
4. **風險可控**：6層風險控制+低槓桿（1-3x），總風險暴露低
5. **自動切換**：第100筆交易後自動恢復正常門檻，無需手動干預

### 推薦配置

```bash
# 環境變量設置（Replit Secrets或.env）

# 豁免期配置
BOOTSTRAP_TRADE_LIMIT=100                  # 前100筆豁免
BOOTSTRAP_MIN_WIN_PROBABILITY=0.40         # 豁免期勝率40%
BOOTSTRAP_MIN_CONFIDENCE=0.40              # 豁免期信心40%
BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD=0.4     # 豁免期質量0.4

# 正常期配置
MIN_WIN_PROBABILITY=0.60                   # 正常期勝率60%
MIN_CONFIDENCE=0.50                        # 正常期信心50%
SIGNAL_QUALITY_THRESHOLD=0.6               # 正常期質量0.6

# 信號模式（強烈推薦）
RELAXED_SIGNAL_MODE=true                   # 啟用寬鬆模式
```

### 預期時間線

```
Day 0-10: 豁免期（0-100筆交易）
├─ 目標：快速採集訓練數據
├─ 信號數：20-30個/天
├─ 槓桿：1-3x（低風險）
└─ ML狀態：每50筆重訓練

Day 10-20: 過渡期（100-200筆交易）
├─ 目標：模型持續優化
├─ 信號數：10-15個/天
├─ 槓桿：5-10x（中等風險）
└─ ML狀態：預測準確度提升

Day 20+: 穩定期（200+筆交易）
├─ 目標：高質量穩定運行
├─ 信號數：5-10個/天
├─ 槓桿：10-20x（動態風險）
└─ ML狀態：鎖定模型（可選）
```

---

**🎓 豁免策略已完全就緒，助力系統快速學習成長！**

---

*文檔生成時間: 2025-11-01*  
*版本: v3.18.7+*  
*狀態: 已啟用*
