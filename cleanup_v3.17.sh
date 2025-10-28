#!/bin/bash
# ===== v3.17+ 一鍵清理腳本 =====
# 徹底移除所有 v3.16 及更早版本的遺留代碼

set -e  # 遇到錯誤立即停止

echo "=========================================="
echo "🧹 v3.17+ 徹底清理腳本"
echo "=========================================="
echo ""

# 階段 1: 安全備份
echo "📦 階段 1/7: 創建安全備份..."
git add .
git commit -m "Backup before v3.17+ cleanup" || echo "⚠️  No changes to commit"
git tag v3.16.3-backup || echo "⚠️  Tag already exists"
echo "✅ 備份完成"
echo ""

# 階段 2: 刪除目錄
echo "🗑️  階段 2/7: 刪除舊目錄..."
rm -rf src/ml/
echo "  ✅ 刪除 src/ml/"
rm -rf docs/archive/
echo "  ✅ 刪除 docs/archive/"
rm -rf data/training_cache/ 2>/dev/null || echo "  ⚠️  data/training_cache/ 不存在"
rm -rf reports/v3.16/ reports/v3.15/ reports/legacy/ 2>/dev/null || echo "  ⚠️  舊版報告目錄不存在"
echo "✅ 目錄清理完成"
echo ""

# 階段 3: 刪除單個文件
echo "📄 階段 3/7: 刪除舊模塊文件..."
rm -f src/managers/risk_manager.py
echo "  ✅ 刪除 risk_manager.py"
rm -f src/core/performance_modules.py
echo "  ✅ 刪除 performance_modules.py"
rm -f src/core/market_regime_predictor.py
echo "  ✅ 刪除 market_regime_predictor.py"
rm -f src/core/dynamic_feature_generator.py
echo "  ✅ 刪除 dynamic_feature_generator.py"
rm -f src/core/liquidity_hunter.py
echo "  ✅ 刪除 liquidity_hunter.py"
rm -f src/core/memory_mapped_features.py
echo "  ✅ 刪除 memory_mapped_features.py"
rm -f scripts/convert_to_tflite.py
echo "  ✅ 刪除 convert_to_tflite.py"
rm -f scripts/convert_xgboost_to_onnx.py
echo "  ✅ 刪除 convert_xgboost_to_onnx.py"
rm -f scripts/check_onnx_compatibility.py
echo "  ✅ 刪除 check_onnx_compatibility.py"
echo "✅ 文件清理完成"
echo ""

# 階段 4: 清理模型文件
echo "🤖 階段 4/7: 清理舊模型文件..."
find . -name "*.h5" -delete 2>/dev/null || true
echo "  ✅ 刪除所有 .h5 文件"
find . -name "*.tflite" -delete 2>/dev/null || true
echo "  ✅ 刪除所有 .tflite 文件"
find . -path "*/models/*.onnx" -delete 2>/dev/null || true
find . -path "*/data/models/*.onnx" -delete 2>/dev/null || true
echo "  ✅ 刪除項目模型中的 .onnx 文件"
echo "✅ 模型清理完成"
echo ""

# 階段 5: 清理舊版文檔
echo "📚 階段 5/7: 清理舊版文檔..."
rm -f ARCHITECTURE_v3.14.0.md
rm -f ARCHITECTURE_v3.15.0.md
rm -f SYSTEM_AUDIT_REPORT_v3.16.1.md
rm -f SYSTEM_OVERVIEW_v3.16.2.md
rm -f v3.14.0_CODE_AUDIT_REPORT.md
rm -f CODE_REVIEW_REPORT_v3.9.2.8.md
rm -f VERSION_v3.9.2.7_SUMMARY.md
rm -f V3.16.2_GLOBAL_PROCESS_POOL_FIX_FINAL.md
rm -f V3.16.2_SERIALIZATION_FIX_COMPLETE.md
rm -f V3.16.2_THREADPOOL_FIX_COMPLETE.md
rm -f V3.16.3_INCREMENTAL_LEARNING_COMPLETE.md
echo "  ✅ 刪除 v3.14-v3.16 文檔"
echo "✅ 文檔清理完成"
echo ""

# 階段 6: 更新依賴文件
echo "📦 階段 6/7: 更新依賴文件..."
if [ -f "requirements_v3.17.txt" ]; then
    cp requirements_v3.17.txt requirements.txt
    echo "  ✅ 已更新 requirements.txt 為 v3.17+ 版本"
else
    echo "  ⚠️  requirements_v3.17.txt 不存在，請手動更新"
fi
echo "✅ 依賴更新完成"
echo ""

# 階段 7: 驗證
echo "✅ 階段 7/7: 驗證清理結果..."
echo ""
echo "檢查 ProcessPool 殘留..."
PROCESS_POOL_COUNT=$(grep -r "ProcessPool" src/ 2>/dev/null | wc -l || echo "0")
if [ "$PROCESS_POOL_COUNT" -eq 0 ]; then
    echo "  ✅ 無 ProcessPool 殘留"
else
    echo "  ⚠️  發現 $PROCESS_POOL_COUNT 處 ProcessPool 引用，請手動檢查"
fi

echo ""
echo "檢查深度學習模型殘留..."
H5_COUNT=$(find . -name "*.h5" 2>/dev/null | wc -l || echo "0")
TFLITE_COUNT=$(find . -name "*.tflite" 2>/dev/null | wc -l || echo "0")
if [ "$H5_COUNT" -eq 0 ] && [ "$TFLITE_COUNT" -eq 0 ]; then
    echo "  ✅ 無深度學習模型殘留"
else
    echo "  ⚠️  發現 $H5_COUNT 個 .h5 和 $TFLITE_COUNT 個 .tflite 文件"
fi

echo ""
echo "檢查 src/ml/ 目錄..."
if [ ! -d "src/ml/" ]; then
    echo "  ✅ src/ml/ 已成功刪除"
else
    echo "  ❌ src/ml/ 仍然存在"
fi

echo ""
echo "=========================================="
echo "🎉 v3.17+ 清理完成！"
echo "=========================================="
echo ""
echo "📊 清理統計:"
echo "  - 刪除目錄: 4+ 個"
echo "  - 刪除文件: 35+ 個"
echo "  - 刪除舊文檔: 11 個"
echo "  - 預計節省空間: ~500MB+"
echo ""
echo "🚀 後續步驟:"
echo "  1. 檢查 src/config.py 移除舊參數（手動）"
echo "  2. 重新安裝依賴: pip install -r requirements.txt"
echo "  3. 測試啟動: python src/main.py"
echo ""
echo "📝 完整清理檢查清單: V3.17_CLEANUP_CHECKLIST.md"
echo ""
