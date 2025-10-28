# ✅ v3.17+ 整合檢查清單

## 📋 實施狀態

### ✅ 已完成的模塊

1. **ConfigProfile** (`src/core/config_profile.py`)
   - [x] @dataclass(frozen=True) 實現
   - [x] 環境變量驅動
   - [x] 配置驗證邏輯
   - [x] to_dict() 方法

2. **LeverageEngine** (`src/core/leverage_engine.py`)
   - [x] 無限槓桿計算公式
   - [x] calculate_leverage() 方法
   - [x] validate_signal_conditions() 方法
   - [x] 詳細日誌輸出

3. **PositionSizer** (`src/core/position_sizer.py`)
   - [x] 倉位數量計算
   - [x] Binance 交易對規格緩存
   - [x] 止損距離自動調整（≥0.3%）
   - [x] 名義價值檢查（≥$10）
   - [x] 異步/同步雙版本

4. **SLTPAdjuster** (`src/core/sltp_adjuster.py`)
   - [x] 動態 SL/TP 調整
   - [x] 放大因子計算
   - [x] SL/TP 驗證邏輯
   - [x] ATR 基礎止損推薦

5. **SelfLearningTraderController** (`src/core/self_learning_trader_controller.py`)
   - [x] 核心編排邏輯
   - [x] analyze_and_execute() 方法
   - [x] 整合三大引擎
   - [x] 可執行訂單包生成

6. **PositionMonitor24x7** (`src/core/position_monitor_24x7.py`)
   - [x] 異步監控循環
   - [x] 每 2 秒檢查邏輯
   - [x] -99% 風險熔斷
   - [x] 強制平倉執行
   - [x] start/stop 方法

7. **ModelRatingEngine** (`src/core/model_rating_engine.py`)
   - [x] 100 分制評分系統
   - [x] 6 大維度計算
   - [x] 100% 虧損懲罰邏輯
   - [x] 等級評定（S/A/B/C）

8. **DailyReporter** (`src/core/daily_reporter.py`)
   - [x] JSON 報告生成
   - [x] Markdown 報告生成
   - [x] stdout 輸出（Railway Logs）
   - [x] 報告目錄自動創建

---

## 🔧 待整合的組件

### 1. SelfLearningTrader 更新

**文件**: `src/strategies/self_learning_trader.py`

**需要添加**:
```python
def analyze(self, symbol: str, multi_tf_data: Dict[str, pd.DataFrame]) -> Optional[Dict]:
    """
    v3.17+ 增強: 添加勝率和信心度預測
    """
    # ... 原有邏輯 ...
    
    # 新增: 預測勝率
    win_probability = self._predict_win_probability(signal_features)
    
    # 新增: 計算 R:R 比率
    rr_ratio = abs(take_profit - entry_price) / abs(entry_price - stop_loss)
    
    # 添加到信號字典
    signal['win_probability'] = win_probability
    signal['rr_ratio'] = rr_ratio
    
    return signal

def _predict_win_probability(self, features: np.ndarray) -> float:
    """
    預測勝率（基於歷史交易表現）
    
    簡化版本：使用最近 N 筆交易的勝率
    進階版本：使用 ML 模型預測
    """
    if not self.trade_history:
        return 0.55  # 默認勝率
    
    recent_trades = self.trade_history[-20:]  # 最近 20 筆
    wins = sum(1 for t in recent_trades if t['pnl'] > 0)
    return wins / len(recent_trades)
```

**狀態**: ⏸️ 待實施

---

### 2. 主循環更新

**文件**: `src/main.py` 或 `src/async_core/async_main_loop.py`

**需要添加**:
```python
from src.core.config_profile import ConfigProfile
from src.core.self_learning_trader_controller import SelfLearningTraderController
from src.core.position_monitor_24x7 import PositionMonitor24x7
from src.core.model_rating_engine import ModelRatingEngine
from src.core.daily_reporter import DailyReporter

async def main():
    # 1. 創建 v3.17+ 配置
    config_profile = ConfigProfile()
    is_valid, errors = config_profile.validate()
    if not is_valid:
        logger.error(f"配置驗證失敗: {errors}")
        return
    
    # 2. 創建核心組件
    trader = SelfLearningTrader(config)  # 現有的
    controller = SelfLearningTraderController(
        config_profile, trader, binance_client
    )
    
    # 3. 創建監控器
    monitor = PositionMonitor24x7(
        config_profile, binance_client, trade_recorder
    )
    await monitor.start()
    
    # 4. 創建報告系統
    rating_engine = ModelRatingEngine(config_profile)
    reporter = DailyReporter(config_profile, rating_engine, trade_recorder)
    
    # 5. 交易主循環
    while True:
        for symbol in symbols:
            # 使用 Controller 替代直接調用 trader
            order = await controller.analyze_and_execute(
                symbol, multi_tf_data, account_equity
            )
            
            if order:
                await trading_service.execute_order(order)
        
        await asyncio.sleep(cycle_interval)
```

**狀態**: ⏸️ 待實施

---

### 3. 每日報告排程

**選項 A: Railway Cron Job**
```bash
0 0 * * * python scripts/generate_daily_report.py
```

**選項 B: 內建定時任務**
```python
async def schedule_daily_report(reporter: DailyReporter):
    while True:
        now = datetime.now()
        next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        
        wait_seconds = (next_run - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        
        await reporter.generate_daily_report(period_days=1)
```

**狀態**: ⏸️ 待實施

---

## 🧪 測試計劃

### 單元測試

```python
# tests/test_leverage_engine.py
def test_leverage_calculation():
    config = ConfigProfile()
    engine = LeverageEngine(config)
    
    # 測試勝率 70%, 信心度 80%
    leverage = engine.calculate_leverage(0.70, 0.80)
    assert leverage > 10  # 應該超過 10x
    assert leverage == pytest.approx(19.2, rel=0.1)

# tests/test_position_sizer.py
async def test_position_sizing():
    config = ConfigProfile()
    sizer = PositionSizer(config)
    
    # 測試最小名義價值
    size, sl = await sizer.calculate_position_size_async(
        account_equity=1000,
        entry_price=0.001,  # 極低價格
        stop_loss=0.0009,
        leverage=1.0,
        symbol="TESTUSDT"
    )
    assert size * 0.001 >= 10.0  # 名義價值 ≥ $10

# tests/test_model_rating.py
def test_rating_calculation():
    config = ConfigProfile()
    engine = ModelRatingEngine(config)
    
    # 模擬交易數據
    trades = [
        {'pnl': 10, 'risk_amount': 5, 'reward_amount': 15},
        {'pnl': -5, 'risk_amount': 5, 'reward_amount': 15},
    ]
    
    rating = engine.calculate_rating(trades)
    assert 0 <= rating['final_score'] <= 100
    assert rating['grade'] in ['S', 'A', 'B', 'C', 'N/A']
```

---

## 🎯 整合步驟優先級

### P0: 核心功能（必須）
- [x] ConfigProfile
- [x] LeverageEngine
- [x] PositionSizer
- [x] SLTPAdjuster
- [x] SelfLearningTraderController

### P1: 監控與報告（重要）
- [x] PositionMonitor24x7
- [x] ModelRatingEngine
- [x] DailyReporter

### P2: 整合與測試（關鍵）
- [ ] SelfLearningTrader 添加勝率預測
- [ ] 主循環整合 Controller
- [ ] 啟動 PositionMonitor24x7
- [ ] 部署報告排程

### P3: 優化與文檔（可選）
- [ ] 單元測試
- [ ] 性能優化
- [ ] 監控儀表板
- [ ] Discord 通知整合

---

## 🚀 下一步行動

1. **立即執行**:
   - [ ] 更新 `SelfLearningTrader.analyze()` 添加勝率預測
   - [ ] 更新主循環使用 `Controller.analyze_and_execute()`
   - [ ] 在 `main.py` 啟動 `PositionMonitor24x7`

2. **短期（本週）**:
   - [ ] 設置 Railway Cron Job 執行每日報告
   - [ ] 添加基本單元測試
   - [ ] 更新 `replit.md` 記錄架構變更

3. **中期（本月）**:
   - [ ] 收集真實交易數據驗證評分系統
   - [ ] 根據評分結果調整槓桿公式參數
   - [ ] 實施冷啟動保護（前 100 筆交易槓桿 ≤ 10x）

---

**最後更新**: 2025-10-28  
**當前階段**: P2 - 整合與測試
