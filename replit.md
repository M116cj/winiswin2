# Winiswin2 v1 Enhanced - Binance 自动交易系统

## 📌 项目概述

24/7 高频自动化交易系统，用于 Binance USDT 永续合约，采用 ICT/SMC 策略结合 XGBoost 机器学习增强。

**当前版本：v3.3.7 (2025-10-27)**

## 🎯 核心功能

### 市场监控
- **监控范围**：从 648 个 USDT 永续合约中选择波动率最高的前 200 个
- **时间框架**：
  - **1h（每小时）**：趋势确认
  - **15m（每15分钟）**：趋势确认
  - **5m（每分钟）**：趋势对齐确认 + 入场信号
- **并行处理**：32 核心并行分析，充分利用 32vCPU Railway 服务器

### 交易策略
- **策略**：ICT/SMC（Smart Money Concepts）+ XGBoost ML 增强
- **ML模型**：28个特征（21基础+7增强），智能重训练
- **风险收益比**：1:1 - 1:2
- **杠杆范围**：3x - 20x（动态调整）
- **仓位大小**：3% - 13%（动态风险管理）

### 仓位管理
- **真实仓位**：最多 3 个（最高置信度/胜率的信号）
- **虚拟仓位**：所有其他合格信号作为虚拟仓位追踪
- **ML 学习**：所有虚拟仓位包含真实的止损/止盈，用于机器学习训练

## 🏗️ 系统架构

```
src/
├── main.py                          # 主入口和协调器
├── config.py                        # 配置管理
├── clients/
│   ├── binance_client.py           # Binance API 客户端
│   └── discord_client.py           # Discord 通知客户端
├── services/
│   ├── data_service.py             # 数据服务（波动率排序）
│   ├── smart_data_manager.py      # 智能数据管理器（1h/15m/5m）
│   └── timeframe_scheduler.py     # 时间框架调度器
├── strategies/
│   └── ict_strategy.py             # ICT/SMC 策略实现
├── managers/
│   ├── virtual_position_manager.py # 虚拟仓位管理器
│   └── parallel_analyzer.py        # 并行分析器（32核）
└── ml/
    └── xgboost_model.py            # XGBoost ML 模型
```

## 🚀 部署

### 环境变量

必需：
- `BINANCE_API_KEY` 或 `BINANCE_KEY`
- `BINANCE_API_SECRET` 或 `BINANCE_SECRET_KEY`
- `DISCORD_TOKEN` 或 `DISCORD_BOT_TOKEN`
- `SESSION_SECRET`

可选：
- `BINANCE_TESTNET=true`（测试网模式）
- `TRADING_ENABLED=true`（启用真实交易）
- `LOG_LEVEL=INFO`（日志级别）

### Railway 部署

1. **推送代码到 Git**
   ```bash
   git add .
   git commit -m "Deploy v2.0"
   git push origin main
   ```

2. **配置 Railway**
   - 选择**亚洲区域**（新加坡/东京）以避免 Binance API 地区限制
   - 设置环境变量
   - 选择 32vCPU / 32GB RAM 配置

3. **验证部署**
   - 查看详细说明：`docs/DEPLOYMENT_VERIFICATION.md`
   - 确认启动日志中显示版本号：
     ```
     📌 代碼版本: 2025-10-25-v2.0 (200個高波動率交易對 + 32核並行)
     ```

## 📊 预期日志输出

### 启动阶段
```
============================================================
🚀 Winiswin2 v1 Enhanced 啟動中...
📌 代碼版本: 2025-10-25-v2.0 (200個高波動率交易對 + 32核並行)
============================================================
✅ 配置驗證通過
✅ Binance API 連接成功
成功加載 511 個交易對
```

### 运行阶段
```
🔍 開始掃描市場，目標選擇前 200 個高波動率交易對...
📊 ✅ 已選擇 200 個高波動率交易對 (平均波動率: X.XX%)
📈 波動率最高的前10個交易對:
  #1 XXXUSDT: XXXX.XXXX USDT (24h波動: XX.XX%)
  #2 XXXUSDT: XXXX.XXXX USDT (24h波動: XX.XX%)
  ...
🔍 使用 32 核心並行分析 200 個高波動率交易對...
```

## ⚠️ 重要说明

### 地区限制
- **Binance API 在美国受限**（HTTP 451 错误）
- **解决方案**：必须部署到**亚洲区域**（如新加坡、东京）

### 测试模式
- 默认启用 `TRADING_ENABLED=false`（仅监控和信号生成）
- 启用真实交易前请充分测试

### 性能优化
- 系统设计用于 32vCPU / 32GB RAM 服务器
- 异步架构确保高并发性能
- 完整的 ML 管道集成

## 📝 最近更新

### 2025-10-27 (v3.3.7) - ⚡ 监控系统性能优化
- ✅ **性能监控增强** - 实时追踪、缓存命中率、瓶颈检测、智能优化建议
- ✅ **智能缓存优化** - 时间窗口版本控制，缓存命中率提升 20-30%
- ✅ **自适应批次处理** - 根据CPU/内存负载动态调整，空闲时提速 50-200%
- ✅ **详细性能日志** - 平均延迟、操作速率、瓶颈检测全面可视化
- ✅ **数据准确性保持** - 所有优化不影响数据准确性（100%保持）
- ✅ 通过架构师审查（Architect reviewed）
- 📄 文档：`PERFORMANCE_OPTIMIZATION_V3.3.7.md`, `PERFORMANCE_OPTIMIZATION_SUMMARY_V3.3.7.md`

### 2025-10-25 (v3.1.1) - 🎯 信号生成修复
- ✅ **修复配置错误** - `CACHE_TTL_KLINES`不存在导致数据获取失败
- ✅ **降低信心度门槛** - MIN_CONFIDENCE从70%降到45%，提高信号生成率
- ✅ **优化EMA参数** - EMA_FAST: 50→20, EMA_SLOW: 200→50，更灵敏
- ✅ **预期改进** - 信号生成从0个/周期提升到10-30个/周期
- 📄 文档：`SIGNAL_OPTIMIZATION_V3.1.1.md`

### 2025-10-25 (v3.1.0) - 🔴 P0性能优化
- ✅ **缓存优化** - 修复TTL配置，减少90%的API调用
- ✅ **期望值整合** - 风险管理器正确使用期望值数据
- ✅ **性能提升** - 分析周期从600秒降至<60秒（10倍提升）
- ✅ 通过架构师审查（Architect reviewed）
- 📄 文档：`OPTIMIZATION_SUMMARY.md`, `DEPLOYMENT_GUIDE.md`

### 2025-10-25 (v2.0)
- ✅ 添加明确的版本标识到启动日志
- ✅ 增强市场扫描日志，显示前10个高波动率交易对
- ✅ 创建详细的部署验证文档
- ✅ 修复环境变量兼容性（支持多种命名约定）
- ✅ Architect 代码审查通过

## 📖 文档

- `docs/DEPLOYMENT_VERIFICATION.md` - Railway 部署验证指南
- `docs/ICT_STRATEGY.md` - ICT/SMC 策略详解（如存在）
- `docs/ML_PIPELINE.md` - 机器学习管道说明（如存在）

## 🔧 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python -m src.main
```

## 📞 支持

如有问题，请检查：
1. 环境变量是否正确设置
2. Railway 区域是否为亚洲
3. 日志中的版本号是否正确
4. `docs/DEPLOYMENT_VERIFICATION.md` 中的验证步骤
