"""
XGBoost → ONNX 转换脚本（v3.12.0 ONNX 推理加速）
- 支援回歸/分類模型
- 自動驗證轉換正確性
- 生成相容性報告

使用方法：
    python scripts/convert_xgboost_to_onnx.py
"""

import os
import sys
import pickle
import numpy as np
from pathlib import Path
from typing import Tuple, Optional

# ONNX 相關
try:
    import onnxruntime as ort
    from onnxmltools import convert_xgboost
    from onnxmltools.convert.common.data_types import FloatTensorType
    ONNX_AVAILABLE = True
except ImportError as e:
    print(f"❌ ONNX 依賴缺失: {e}")
    print("請安裝: pip install onnxruntime onnxmltools")
    ONNX_AVAILABLE = False

# ===== 配置 =====
# ⚠️ CRITICAL: 必须与 predictor.py 中的模型路径一致！
MODEL_PATH = "data/models/xgboost_predictor_binary.pkl"  # binary分类模型（用于实时预测）
ONNX_PATH = "data/models/model.onnx"
FEATURE_ORDER_PATH = "data/models/feature_order.txt"
EXPECTED_FEATURES = 29  # ML 模型特徵數量（predictor 使用 29 个特征）


def load_xgboost_model(model_path: str):
    """安全載入 XGBoost 模型"""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型不存在: {model_path}")
    
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    
    # 驗證是否為 XGBoost 模型
    model_type = type(model).__name__
    if "XGB" not in model_type and "Booster" not in model_type:
        raise ValueError(f"非 XGBoost 模型: {model_type}")
    
    print(f"✅ 載入模型: {model_type}")
    return model


def get_feature_order_from_model(model) -> Optional[list]:
    """從模型獲取特徵順序（若支援）"""
    try:
        # XGBoost 1.7+ 支援 feature_names
        if hasattr(model, 'feature_names_in_'):
            return model.feature_names_in_.tolist()
        elif hasattr(model, 'feature_names'):
            return model.feature_names
        elif hasattr(model, 'get_booster'):
            booster = model.get_booster()
            if hasattr(booster, 'feature_names'):
                return booster.feature_names
    except Exception as e:
        print(f"⚠️  無法自動提取特徵順序: {e}")
    return None


def save_feature_order(features: list, path: str):
    """保存特徵順序到檔案"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        for feat in features:
            f.write(f"{feat}\n")
    print(f"📝 特徵順序已保存: {path}")


def create_sample_input(n_features: int = 31) -> np.ndarray:
    """創建標準化測試輸入"""
    np.random.seed(42)  # 確保可重現
    return np.random.uniform(0, 1, (10, n_features)).astype(np.float32)


def validate_conversion(
    xgb_model, 
    onnx_session, 
    sample_input: np.ndarray,
    tolerance: float = 1e-5
) -> bool:
    """驗證 ONNX 與 XGBoost 輸出一致性"""
    print("🔍 驗證轉換正確性...")
    
    # XGBoost 預測
    try:
        xgb_pred = xgb_model.predict(sample_input.astype(np.float64))
    except Exception as e:
        print(f"❌ XGBoost 預測失敗: {e}")
        return False
    
    # ONNX 預測
    try:
        ort_inputs = {onnx_session.get_inputs()[0].name: sample_input}
        onnx_pred = onnx_session.run(None, ort_inputs)[0].flatten()
    except Exception as e:
        print(f"❌ ONNX 預測失敗: {e}")
        return False
    
    # 比較
    diff = np.abs(xgb_pred - onnx_pred)
    max_diff = np.max(diff)
    mean_diff = np.mean(diff)
    
    print(f"  最大差異: {max_diff:.2e}")
    print(f"  平均差異: {mean_diff:.2e}")
    print(f"  容忍度: {tolerance:.2e}")
    
    if max_diff <= tolerance:
        print("✅ 轉換驗證通過！")
        return True
    else:
        print("❌ 轉換驗證失敗！")
        print(f"  XGBoost 預測範例: {xgb_pred[:3]}")
        print(f"  ONNX 預測範例: {onnx_pred[:3]}")
        return False


def convert_model(
    model_path: str, 
    onnx_path: str, 
    input_shape: Tuple[int, int] = (1, 31)
) -> bool:
    """
    主轉換函數
    Returns: bool - 是否成功
    """
    if not ONNX_AVAILABLE:
        print("❌ ONNX 依賴未安裝")
        return False
    
    try:
        # 1. 載入模型
        print(f"📂 載入模型: {model_path}")
        model = load_xgboost_model(model_path)
        
        # 2. 獲取/保存特徵順序
        feature_order = get_feature_order_from_model(model)
        if feature_order:
            print(f"✅ 偵測到 {len(feature_order)} 個特徵")
            save_feature_order(feature_order, FEATURE_ORDER_PATH)
        else:
            print("⚠️  無法獲取特徵順序，將使用預設")
            print(f"   請確認模型訓練時使用了 {EXPECTED_FEATURES} 個特徵")
        
        # 3. 轉換為 ONNX
        print("🔄 開始轉換為 ONNX...")
        initial_type = [('float_input', FloatTensorType(input_shape))]
        onnx_model = convert_xgboost(model, initial_types=initial_type)
        
        # 4. 保存 ONNX 模型
        os.makedirs(os.path.dirname(onnx_path), exist_ok=True)
        with open(onnx_path, 'wb') as f:
            f.write(onnx_model.SerializeToString())
        
        # 獲取文件大小
        onnx_size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
        print(f"✅ ONNX 模型已保存: {onnx_path} ({onnx_size_mb:.2f} MB)")
        
        # 5. 驗證轉換
        sample_input = create_sample_input(input_shape[1])
        onnx_session = ort.InferenceSession(onnx_path)
        is_valid = validate_conversion(model, onnx_session, sample_input)
        
        return is_valid
        
    except Exception as e:
        print(f"❌ 轉換失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函數"""
    print("🚀 XGBoost → ONNX 轉換工具（v3.12.0）")
    print(f"輸入模型: {MODEL_PATH}")
    print(f"輸出模型: {ONNX_PATH}")
    print("-" * 60)
    
    # 檢查模型是否存在
    if not os.path.exists(MODEL_PATH):
        print(f"\n❌ 模型文件不存在: {MODEL_PATH}")
        print("   請先訓練 XGBoost 模型或指定正確的模型路徑")
        sys.exit(1)
    
    success = convert_model(MODEL_PATH, ONNX_PATH, input_shape=(1, EXPECTED_FEATURES))
    
    if success:
        print("\n🎉 轉換成功！")
        print("\n下一步:")
        print("1. 檢查 data/models/model.onnx 是否存在")
        print("2. MLPredictor 會自動檢測並使用 ONNX 模型（如果存在）")
        print("3. 系統會自動回退到 XGBoost（如果 ONNX 不可用）")
        print("\n💡 性能提升預期: ML 預測時間 ↓ 50-70%")
    else:
        print("\n💥 轉換失敗！請檢查錯誤訊息")
        sys.exit(1)


if __name__ == "__main__":
    main()
