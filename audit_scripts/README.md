# Audit & Testing Scripts

所有系統檢測、審計和驗證腳本位於此資料夾。

## 📋 核心審計腳本

### 系統層審計
- **system_master_audit.py** - 7層全面系統審計 (推薦首先執行)
  ```bash
  python3 audit_scripts/system_master_audit.py
  ```

### 數據庫層審計  
- **audit_db_layer.py** - 數據庫可靠性工程審計 (靜態分析)
  ```bash
  python3 audit_scripts/audit_db_layer.py
  ```
  
- **test_db_connectivity.py** - 數據庫連接測試 (功能測試)
  ```bash
  python3 audit_scripts/test_db_connectivity.py
  ```

### 文檔歸檔
- **archive_docs.py** - 文檔版本化歸檔
- **purge_legacy_code.py** - 清除舊代碼

## 📊 驗證腳本

- **verify_stability.py** - 系統穩定性驗證
- **verify_new_architecture.py** - 新架構驗證
- **verify_refactor.py** - 重構驗證
- **verify_pnl_fix.py** - PnL 修復驗證

## 🧪 功能測試

- **test_db_connectivity.py** - 數據庫連接
- **test_smc_logic.py** - SMC 邏輯測試
- **test_position_sizer_fix.py** - 倉位大小測試
- **test_pragmatic_integration.py** - 集成測試
- **test_hybrid_ml_regression.py** - ML 回歸測試

## 🔍 診斷工具

- **diagnostic_script.py** - 系統診斷
- **system_deep_scan.py** - 深度掃描
- **quick_system_check.py** - 快速檢查
- **system_self_check.py** - 自檢
- **validate_optimizations.py** - 優化驗證

## 🚀 快速執行

### 完整系統審計
```bash
# 執行主審計
python3 audit_scripts/system_master_audit.py

# 執行數據庫審計
python3 audit_scripts/audit_db_layer.py
python3 audit_scripts/test_db_connectivity.py
```

### 快速檢查
```bash
python3 audit_scripts/quick_system_check.py
```

### 深度診斷
```bash
python3 audit_scripts/diagnostic_script.py
```

## 📝 使用說明

1. **系統初始化後** → 執行 `system_master_audit.py`
2. **部署前** → 執行 `audit_db_layer.py` 和 `test_db_connectivity.py`
3. **功能變更後** → 執行相應的 `verify_*.py` 和 `test_*.py`

所有腳本均可獨立執行，不相互依賴。

---

**目的**: 集中管理所有檢測和審計腳本，保持根目錄整潔。
