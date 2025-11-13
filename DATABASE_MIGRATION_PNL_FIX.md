# 数据库迁移：PnL字段冗余修复

## 📋 迁移概述

**日期**: 2025-11-13  
**类型**: Schema优化 - 删除冗余字段  
**影响**: trades表  
**风险级别**: 低（表为空，无数据丢失）

---

## 🎯 问题描述

**问题**: trades表中存在两个冗余的盈亏字段：
- `pnl` - 实际使用的字段 ✅
- `profit_loss` - 从未使用的字段 ❌

**影响**:
- 字段冗余导致潜在数据不一致
- 增加存储空间浪费
- 代码只写入pnl，profit_loss永远为NULL

---

## ✅ 执行的变更

### 1. 数据库Schema变更

```sql
-- 删除冗余字段
ALTER TABLE trades DROP COLUMN IF EXISTS profit_loss;
```

**结果**:
- ✅ trades表列数：64 → 63
- ✅ 保留字段：pnl, pnl_pct
- ✅ 所有索引和约束完整

### 2. 代码变更

**文件**: `src/database/initializer.py`
```python
# 删除前
pnl DECIMAL(18, 8),
pnl_pct DECIMAL(10, 4),
profit_loss DECIMAL(18, 8),  # ❌ 已删除

# 删除后
pnl DECIMAL(18, 8),
pnl_pct DECIMAL(10, 4),
```

**文件**: `src/database/service.py`
```python
# 修复INSERT语句占位符数量
# 之前：59个占位符 vs 60个字段 ❌
# 之后：60个占位符 vs 60个字段 ✅
```

---

## 🔍 验证步骤

运行验证脚本确认修复成功：

```bash
python verify_pnl_fix.py
```

**验证项**:
- ✅ profit_loss列已删除
- ✅ pnl和pnl_pct字段正常
- ✅ 交易CRUD操作正常
- ✅ 无代码引用profit_loss
- ✅ 列数正确（63列）

---

## 📊 验证结果

```
✅ 步骤1：数据库schema验证通过
✅ 步骤2：交易CRUD操作测试通过
✅ 步骤3：代码引用检查通过

修复总结:
  ✅ profit_loss列已从数据库删除
  ✅ initializer.py已更新
  ✅ 交易CRUD操作正常
  ✅ 列数从64减少到63
  ✅ 系统功能完整
```

---

## 🚨 回滚方案

如果需要回滚（不推荐，因为字段从未使用）：

```sql
-- 恢复profit_loss列（如有必要）
ALTER TABLE trades ADD COLUMN profit_loss DECIMAL(18, 8);

-- 同步数据（如果有数据）
UPDATE trades SET profit_loss = pnl WHERE pnl IS NOT NULL;
```

---

## 📝 部署清单

部署到生产环境前：

- [x] 开发环境验证通过
- [x] Architect代码审查通过
- [x] 验证脚本执行成功
- [ ] Staging环境验证
- [ ] 备份生产数据库
- [ ] 生产环境执行

---

## 🔧 技术细节

**变更文件**:
1. `src/database/initializer.py` - 删除profit_loss字段定义
2. `src/database/service.py` - 修复INSERT占位符数量
3. `verify_pnl_fix.py` - 验证脚本（新增）

**影响范围**:
- 数据库：trades表结构
- 代码：2个文件修改
- 数据：无影响（表为空）

**性能提升**:
- 行宽减少：~1.5%
- 存储优化：每条记录节省8字节

---

## ✅ Architect审查

**状态**: PASS ✅

**评估**:
- 数据库schema正确（63列，索引完整）
- INSERT语句修复正确（60字段↔60占位符）
- 验证脚本全部通过
- 无数据丢失
- 生产就绪

**建议**:
1. 添加自动化测试确保INSERT列↔占位符一致
2. 在staging/production执行前运行验证脚本

---

## 📞 联系信息

如有问题，请查看验证脚本输出或检查日志文件。

**相关文档**:
- 数据库架构问题报告
- PnL字段冗余分析

---

*最后更新: 2025-11-13*
