# 🚂 Railway部署检查清单 v3.19

**版本**: v3.19  
**日期**: 2025-11-02  
**目标**: 部署特征增强版本（44→56特征）+ 验证0信号修复

---

## ✅ 部署前检查清单

### **1. 关键配置验证**

#### **环境变量（必须）**
```bash
# Binance API密钥
BINANCE_API_KEY=<your_api_key>
BINANCE_API_SECRET=<your_api_secret>

# 🔥 v3.18.10+ 关键修复：宽松信号模式
RELAXED_SIGNAL_MODE=true  # ✅ 默认已启用，无需手动设置

# 交易开关
TRADING_ENABLED=true

# 可选：会话密钥
SESSION_SECRET=<your_session_secret>
```

#### **配置确认**
- ✅ `src/config.py` 第38行：`RELAXED_SIGNAL_MODE`默认为`true`
- ✅ 宽松模式启用后，允许priority 4-5信号生成（预期3-8个/周期）

---

### **2. v3.19新特征状态**

#### **代码变更**
- ✅ `src/utils/ict_tools.py` - ICT/SMC工具类已创建
- ✅ `src/ml/feature_engine.py` - 56特征支持已完成
- ✅ `src/ml/model_wrapper.py` - 向后兼容44特征

#### **特征支持状态**

| 特征类别 | 数量 | 状态 | 数据源 |
|---------|------|------|--------|
| 基础特征 | 38个 | ✅ 完全支持 | Signal字典 |
| 竞价特征 | 3个 | ✅ 完全支持 | 竞价系统 |
| WebSocket特征 | 3个 | ✅ 完全支持 | WebSocket元数据 |
| ICT/SMC基础特征 | 8个 | ⚠️ 部分支持 | K线数据（当前） |
| ICT/SMC合成特征 | 4个 | ⚠️ 部分支持 | K线数据（当前） |

**⚠️ 注意**: 
- 当前ICT/SMC特征基于signal字典中的K线数据
- `order_flow`和`liquidity_context`暂时使用默认值（0）
- 完整支持需要WebSocket交易流和深度流集成（v3.20+计划）

---

### **3. 预期行为**

#### **信号生成**
- **修复前（v3.18.9）**: 0信号/周期（priority 1-3被过滤）
- **修复后（v3.18.10+）**: 3-8信号/周期（priority 4-5通过）

#### **ML模型**
- **44特征模型**: 自动补齐12个默认值 → 兼容
- **56特征模型**: 需要重新训练（未来版本）

---

### **4. 部署步骤（Railway）**

#### **Step 1: 推送代码到Git仓库**
```bash
git add .
git commit -m "v3.19: 特征增强（44→56）+ 0信号修复"
git push origin main
```

#### **Step 2: Railway自动部署**
- Railway检测到代码变更后自动部署
- 等待构建完成（约2-3分钟）

#### **Step 3: 验证部署**
```bash
# 检查Railway日志
# 查找以下关键日志：

✅ 特徵工程引擎已創建 v3.19
   📊 總特徵數：56個（44→56，新增12個ICT/SMC特徵）

✅ ML模型已加载
   🔥 v3.19：使用56个特征进行预测（44→56）
```

#### **Step 4: 监控首个周期**
- 观察信号生成数量（应为3-8个）
- 检查ICT/SMC特征是否正常计算
- 验证交易执行是否正常

---

### **5. 故障排查**

#### **问题1: 仍然0信号**
**检查**:
```python
# Railway日志中搜索
grep "RELAXED_SIGNAL_MODE" logs.txt

# 应显示：
Config.RELAXED_SIGNAL_MODE = True
```

**解决**:
- 手动设置环境变量`RELAXED_SIGNAL_MODE=true`
- 重启Railway服务

#### **问题2: 特征数量错误**
**症状**:
```
⚠️ 特征数量错误: XX != 56
```

**解决**:
- 检查`feature_engine.py`的`get_feature_names()`返回56个特征
- 检查`build_enhanced_features()`返回完整特征字典
- 重新部署

#### **问题3: ICT/SMC特征全为0**
**原因**:
- K线数据未传入
- WebSocket流未集成

**临时方案**:
- 当前版本可接受（使用默认值）
- v3.20+将集成完整WebSocket数据流

---

### **6. 性能基准**

#### **预期性能**
- **信号生成**: 3-8个/周期（60秒）
- **特征计算**: <500ms/信号
- **内存占用**: <200MB（稳定状态）
- **CPU使用**: <30%（平均）

#### **监控指标**
- 每周期信号数量
- 特征计算延迟
- ML预测成功率
- 交易执行成功率

---

### **7. 回滚计划**

如果v3.19出现严重问题：

#### **快速回滚到v3.18.10**
```bash
git revert <commit_hash>
git push origin main
```

#### **环境变量回滚**
```bash
RELAXED_SIGNAL_MODE=true  # 保持修复
# 其他配置保持不变
```

---

### **8. 后续优化（v3.20+）**

#### **待实现功能**
- [ ] WebSocket交易流集成（`btcusdt@trade`）
- [ ] WebSocket深度流集成（`btcusdt@depth`）
- [ ] 完整的ICT/SMC特征实时计算
- [ ] 使用56特征重训练XGBoost模型
- [ ] 特征重要性分析和优化

#### **数据流集成优先级**
1. **高优先级**: 交易流（order_flow）
2. **中优先级**: 深度流（liquidity_context）
3. **低优先级**: 多个深度档位（增强版liquidity_context）

---

## 📊 验证清单

### **部署成功标志**
- [ ] Railway构建成功
- [ ] 日志显示v3.19版本
- [ ] 特征引擎加载56特征
- [ ] ML模型兼容44/56特征
- [ ] 首个周期生成3-8个信号
- [ ] ICT/SMC特征计算无错误
- [ ] 交易执行正常

### **关键日志验证**
```bash
# 1. 版本确认
grep "v3.19" logs.txt

# 2. 特征数量确认
grep "56個" logs.txt

# 3. 信号生成确认
grep "✅ 生成.*信号" logs.txt

# 4. 交易执行确认
grep "開倉成功" logs.txt
```

---

## 🎯 成功标准

### **短期目标（1-3天）**
- ✅ 0信号问题已解决
- ✅ 信号数量稳定在3-8个/周期
- ✅ 系统稳定运行无崩溃

### **中期目标（1-2周）**
- ⏳ 收集足够数据用于56特征模型训练
- ⏳ 分析ICT/SMC特征对胜率的影响
- ⏳ 优化特征权重和计算逻辑

### **长期目标（1个月）**
- 📅 完成WebSocket实时数据流集成
- 📅 使用56特征重训练模型
- 📅 评估v3.19 vs v3.18.10性能提升

---

**部署联系人**: SelfLearningTrader Team  
**紧急联系**: 查看Railway Dashboard日志  
**版本**: v3.19  
**最后更新**: 2025-11-02
