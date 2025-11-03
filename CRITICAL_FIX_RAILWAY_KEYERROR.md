# 🚨 Critical Fix: Railway KeyError 'adx_distribution_gte25'

## 问题诊断

**症状**：Railway上100%信号生成失败  
**错误**：`KeyError: 'adx_distribution_gte25'`  
**位置**：`src/strategies/rule_based_signal_generator.py:418`  
**影响**：所有交易对无法生成信号

---

## 根本原因

**问题代码**：`src/core/unified_scheduler.py:327-349`

在每个交易周期开始时，`unified_scheduler.py`重置`_pipeline_stats`字典，但**只包含24个键**，缺少后面的**11个必需键**：

### 缺失的键
```python
# 原代码只到stage7_passed_double_gate，缺少：
'stage7_rejected_win_prob': 0,
'stage7_rejected_confidence': 0,
'stage7_rejected_rr': 0,
'stage8_passed_quality': 0,
'stage8_rejected_quality': 0,
'stage9_ranked_signals': 0,
'stage9_executed_signals': 0,
'adx_distribution_lt10': 0,
'adx_distribution_10_15': 0,
'adx_distribution_15_20': 0,
'adx_distribution_20_25': 0,
'adx_distribution_gte25': 0  # ← KeyError来源
```

### 失败流程
1. ✅ UnifiedScheduler开始交易周期
2. ❌ 第327行：重置`_pipeline_stats`为**不完整字典**（缺11个键）
3. ✅ 数据获取成功（Stage1通过率98%）
4. ✅ 方向判断成功（Stage3通过率94%）
5. ❌ 第418行：尝试访问`_pipeline_stats['adx_distribution_gte25']`
6. 💥 **KeyError崩溃**（100%失败）

---

## 修复方案

**文件**：`src/core/unified_scheduler.py`  
**行号**：327-366  
**修复内容**：添加缺失的11个键到统计字典重置代码

### 修复前（第327-349行）
```python
self.self_learning_trader.signal_generator._pipeline_stats = {
    'stage0_total_symbols': 0,
    # ... 只到 stage7_passed_double_gate (24个键)
    'stage7_passed_double_gate': 0,
}  # ❌ 缺少11个键
```

### 修复后（第327-366行）
```python
self.self_learning_trader.signal_generator._pipeline_stats = {
    'stage0_total_symbols': 0,
    # ... 所有stage0-7键
    'stage7_passed_double_gate': 0,
    # ✅ 新增：缺失的11个键
    'stage7_rejected_win_prob': 0,
    'stage7_rejected_confidence': 0,
    'stage7_rejected_rr': 0,
    'stage8_passed_quality': 0,
    'stage8_rejected_quality': 0,
    'stage9_ranked_signals': 0,
    'stage9_executed_signals': 0,
    'adx_distribution_lt10': 0,
    'adx_distribution_10_15': 0,
    'adx_distribution_15_20': 0,
    'adx_distribution_20_25': 0,
    'adx_distribution_gte25': 0
}
logger.info("✅ Pipeline統計計數器已完整重置（包含所有ADX分布鍵）")
```

---

## 影响范围

**受影响的交易对**：
- 主流币：BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT
- Meme币：PONKEUSDT, COWUSDT, HIPPOUSDT, PNUTUSDT
- DeFi币：AAVEUSDT, UNIUSDT, GRTUSDT
- 小市值币：1000000MOGUSDT, 1000CHEEMSUSDT, 等等
- **总计**：100+个交易对（100%失败）

**失败时间范围**：
- 自unified_scheduler.py引入统计重置以来
- 每次交易周期开始时触发

---

## 验证方法

### 修复前（Railway日志）
```
❌ KeyError: 'adx_distribution_gte25' (418行)
❌ PONKEUSDT 信號生成失敗
❌ CETUSUSDT 信號生成失敗
... (100+个交易对全部失败)
```

### 修复后（预期）
```
✅ Pipeline統計計數器已完整重置（包含所有ADX分布鍵）
📊 掃描 530 個交易對中...
✅ Stage1驗證: 有效=520, 拒絕=10
✅ ADX分佈統計正常
✅ 信號生成成功：3-10個信號/週期
```

---

## 部署清单

- [x] 修复unified_scheduler.py（添加11个缺失键）
- [x] 验证所有3处初始化位置一致性：
  - [x] `src/strategies/rule_based_signal_generator.py:80-114` (__init__)
  - [x] `src/strategies/rule_based_signal_generator.py:139-173` (reset_debug_stats)
  - [x] `src/core/unified_scheduler.py:327-366` (_execute_trading_cycle) ✅ 已修复
- [ ] 推送到Railway
- [ ] 验证日志无KeyError
- [ ] 确认信号生成恢复

---

## Phase 6 完成状态

**v3.20.3 Critical Hotfix**：
- ✅ EliteTechnicalEngine共享实例优化
- ✅ 21个ICT回归测试100%通过
- ✅ Order Blocks & Swing Points算法优化
- ✅ **修复Railway KeyError（本次）**

**准备就绪部署到Railway！** 🚀
