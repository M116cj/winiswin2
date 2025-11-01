# 🚂 Railway Environment Variables Checklist v3.18.8

## ✅ 必需设置（已完成）

| 变量名 | 当前状态 | 说明 |
|--------|----------|------|
| BINANCE_API_KEY | ✅ 已设置 | Binance API密钥 |
| BINANCE_API_SECRET | ✅ 已设置 | Binance API私钥 |
| BINANCE_TESTNET | ✅ 已设置 | 是否使用测试网（建议：false） |
| TRADING_ENABLED | ✅ 已设置 | 是否启用交易（建议：true） |

---

## ⚠️ 关键配置（需要调整）

根据v3.18.8诊断报告，**Railway上0信号问题的根本原因**是阈值设置过高。

### 🔥 必须立即修改（解决0信号问题）

| 变量名 | 当前值 | 建议值 | 原因 |
|--------|--------|--------|------|
| **MIN_WIN_PROBABILITY** | ? | **0.40** | ⚠️ 豁免期使用40%阈值，允许Poor/Fair信号 |
| **MIN_CONFIDENCE** | ? | **0.40** | ⚠️ 豁免期使用40%阈值，允许Poor/Fair信号 |
| **RELAXED_SIGNAL_MODE** | ? | **true** | ⚠️ 启用宽松模式，增加信号生成频率 |

**说明**：
- 前100笔交易是**数据采集期**（豁免期），需要降低阈值以获取足够信号
- 豁免期后会自动提升到正常阈值（60%/50%）
- 不修改这3个变量，Railway上将持续0信号！

---

## ✅ 豁免机制配置（已正确设置）

| 变量名 | 当前状态 | 建议值 | 说明 |
|--------|----------|--------|------|
| BOOTSTRAP_TRADE_LIMIT | ✅ 已设置 | 100 | 前100笔交易使用豁免阈值 |
| BOOTSTRAP_MIN_WIN_PROBABILITY | ✅ 已设置 | 0.40 | 豁免期最低胜率40% |
| BOOTSTRAP_MIN_CONFIDENCE | ✅ 已设置 | 0.40 | 豁免期最低信心40% |

---

## ✅ 核心功能配置（已正确设置）

| 变量名 | 当前状态 | 建议值 | 说明 |
|--------|----------|--------|------|
| DISABLE_MODEL_TRAINING | ✅ 已设置 | true | 禁用模型训练（生产环境稳定性） |
| CYCLE_INTERVAL | ✅ 已设置 | 60 | 交易周期间隔（秒） |
| SCAN_INTERVAL | ✅ 已设置 | 60 | 扫描间隔（秒） |
| TOP_VOLATILITY_SYMBOLS | ✅ 已设置 | 999 | 监控所有交易对 |

---

## ✅ Discord通知配置（可选）

| 变量名 | 当前状态 | 说明 |
|--------|----------|------|
| DISCORD_TOKEN | ✅ 已设置 | Discord机器人Token（可选） |
| DISCORD_CHANNEL_ID | ✅ 已设置 | Discord频道ID（可选） |

---

## 📋 可选配置（使用默认值即可）

以下变量**不需要**在Railway上设置，系统会使用合理的默认值：

### 风险管理（默认值已优化）
- `MAX_TOTAL_BUDGET_RATIO=0.8` - 总预算80%
- `MAX_SINGLE_POSITION_RATIO=0.5` - 单仓≤50%权益
- `MAX_TOTAL_MARGIN_RATIO=0.9` - 总保证金≤90%
- `MAX_CONCURRENT_ORDERS=5` - 每周期最多5单

### 全倉保护（默认已启用）
- `CROSS_MARGIN_PROTECTOR_ENABLED=true` - 启用全倉保护
- `CROSS_MARGIN_PROTECTOR_THRESHOLD=0.85` - 85%触发阈值
- `CROSS_MARGIN_PROTECTOR_COOLDOWN=120` - 平仓冷却120秒

### WebSocket优化（默认已优化）
- `WEBSOCKET_SYMBOL_LIMIT=200` - 监控前200个交易对
- `WEBSOCKET_SHARD_SIZE=50` - 每分片50个符号
- `WEBSOCKET_HEARTBEAT_TIMEOUT=30` - 心跳超时30秒

### 信号质量（自动适配豁免期）
- `SIGNAL_QUALITY_THRESHOLD=0.6` - 正常期质量门槛60%
- `BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD=0.4` - 豁免期质量门槛40%

### API限流（默认已优化）
- `RATE_LIMIT_REQUESTS=1920` - 每分钟1920次请求

---

## ❌ 可以删除的变量

以下变量**不需要**在Railway上设置：

| 变量名 | 原因 |
|--------|------|
| LOG_LEVEL | 系统自动管理日志级别 |
| PYTHONUNBUFFERED | Railway自动处理Python输出缓冲 |

---

## 🎯 Railway最终推荐配置

### 必须设置（16个）
```bash
# ===== Binance API =====
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
BINANCE_TESTNET=false

# ===== 关键阈值（解决0信号） =====
MIN_WIN_PROBABILITY=0.40      # ⚠️ 必须修改为0.40
MIN_CONFIDENCE=0.40            # ⚠️ 必须修改为0.40
RELAXED_SIGNAL_MODE=true       # ⚠️ 必须启用

# ===== 豁免机制 =====
BOOTSTRAP_TRADE_LIMIT=100
BOOTSTRAP_MIN_WIN_PROBABILITY=0.40
BOOTSTRAP_MIN_CONFIDENCE=0.40

# ===== 核心功能 =====
DISABLE_MODEL_TRAINING=true
TRADING_ENABLED=true
CYCLE_INTERVAL=60
SCAN_INTERVAL=60
TOP_VOLATILITY_SYMBOLS=999

# ===== Discord（可选）=====
DISCORD_TOKEN=your_discord_token
DISCORD_CHANNEL_ID=your_channel_id
```

### 可选设置（仅在需要调整时添加）
```bash
# 风险管理微调
MAX_CONCURRENT_ORDERS=5
MAX_TOTAL_BUDGET_RATIO=0.8
MAX_SINGLE_POSITION_RATIO=0.5

# WebSocket微调
WEBSOCKET_SYMBOL_LIMIT=200
WEBSOCKET_SHARD_SIZE=50
```

---

## 🚀 部署后验证

设置完成后，在Railway日志中检查：

1. **启动日志**：
```
✅ 系統配置:
  min_confidence: 40.0%          ← 应该是40%
  min_win_probability: 40.0%     ← 应该是40%
  relaxed_signal_mode: true      ← 应该是true
```

2. **信号生成日志**：
```
📊 本周期信号统计:
  生成信号: 30-60個            ← 应该有信号
  质量分布: Poor/Fair/Good     ← 应该有Poor/Fair信号
```

3. **预期信号恢复时间**：
   - 部署后5分钟：开始生成Poor质量信号（40%+）
   - 部署后15分钟：Fair质量信号增加
   - 部署后1小时：Good质量信号出现

---

**生成时间**: 2025-11-01  
**版本**: v3.18.8+railway_fix
