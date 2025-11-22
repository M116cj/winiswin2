# 📊 XGBoost 訓練數據示例

本目錄包含 v3.0 系統的 XGBoost 訓練數據格式示例和使用指南。

## 📁 文件說明

### 示例數據文件
- `example_signals.csv` - 100 個交易信號示例（包括被接受和被拒絕的）
- `example_positions.csv` - 50 個倉位的完整生命週期（開倉 + 平倉）
- `example_xgboost_training.csv` - 準備好的 XGBoost 訓練數據集

### 代碼和文檔
- `xgboost_data_example.py` - 完整的示例生成腳本
- `XGBOOST_DATA_FORMAT.md` - 詳細的數據格式說明文檔

## 🚀 快速開始

### 1. 查看示例數據
```bash
# 查看信號數據
head examples/example_signals.csv

# 查看倉位數據
head examples/example_positions.csv

# 查看訓練數據
head examples/example_xgboost_training.csv
```

### 2. 運行示例腳本
```bash
cd examples
python xgboost_data_example.py
```

這將生成新的示例數據並打印詳細的數據摘要。

### 3. 閱讀文檔
查看 `XGBOOST_DATA_FORMAT.md` 了解：
- 完整的數據格式說明
- 特徵選擇指南
- XGBoost 訓練代碼示例
- 實時預測使用方法

## 📊 數據概覽

### Signals.csv (25 個欄位)
**核心特徵**:
- 五維評分: trend_alignment, market_structure, price_position, momentum, volatility
- 技術指標: RSI, MACD, ATR, BB Width
- Order Block: order_blocks_count, liquidity_zones_count

### Positions.csv (29 個欄位)
**完整生命週期**:
- 開倉 (OPEN): 記錄入場信息和市場狀態
- 平倉 (CLOSE): 記錄出場、盈虧、持倉時長

### XGBoost Training Data (15 個欄位)
**特徵 (14 個)**:
- 五維評分 (5)
- 總信心度 (1)
- 技術指標 (4)
- Order Block (2)
- 計算特徵 (2): risk_reward_ratio, leverage

**目標變量 (1 個)**:
- won: 是否盈利 (1 = 盈利, 0 = 虧損)

## 🎯 使用場景

### 1. 學習數據格式
使用示例數據了解系統記錄的信息結構。

### 2. 開發 ML 模型
使用示例數據開發和測試 XGBoost 模型。

### 3. 特徵工程
基於示例數據進行特徵選擇和工程實驗。

### 4. 回測驗證
使用歷史數據驗證模型性能。

## 📈 實際數據位置

當系統運行後，實際數據將保存在：
- `ml_data/signals.csv`
- `ml_data/positions.csv`

## 📚 延伸閱讀

- [SYSTEM_V3_README.md](../SYSTEM_V3_README.md) - 完整系統文檔
- [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) - 部署指南
- [V3_COMPLETION_SUMMARY.md](../V3_COMPLETION_SUMMARY.md) - 升級完成報告

---

**提示**: 建議累積至少 100 筆交易記錄後再開始訓練 XGBoost 模型，以獲得更好的性能。
