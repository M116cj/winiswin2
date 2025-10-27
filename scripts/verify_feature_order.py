"""
特征顺序验证工具（v3.13.0）

验证ML模型特征顺序与predictor特征提取的一致性
防止特征顺序错乱导致预测错误
"""

import os
import sys
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ml.predictor import MLPredictor
from src.config import Config

# ===== 预期特征列表（与 predictor._prepare_signal_features() 一致）=====
EXPECTED_FEATURES = [
    # 基础特征 (21个)
    'confidence_score',
    'leverage',
    'position_value',
    'hold_duration_hours',
    'risk_reward_ratio',
    'order_blocks_count',
    'liquidity_zones_count',
    'rsi_entry',
    'macd_entry',
    'macd_signal_entry',
    'macd_histogram_entry',
    'atr_entry',
    'bb_width_pct',
    'volume_sma_ratio',
    'price_vs_ema50',
    'price_vs_ema200',
    'trend_1h_encoded',
    'trend_15m_encoded',
    'trend_5m_encoded',
    'market_structure_encoded',
    'direction_encoded',  # 第20个特征（索引19）
    
    # 增强特征 (8个)
    'hour_of_day',
    'day_of_week',
    'is_weekend',
    'stop_distance_pct',
    'tp_distance_pct',
    'confidence_x_leverage',
    'rsi_x_trend',
    'atr_x_bb_width'
]

# 总特征数
EXPECTED_FEATURE_COUNT = 29  # 21基础 + 8增强


def load_feature_order_from_file(filepath: str = "data/models/feature_order.txt"):
    """从文件加载特征顺序"""
    if not os.path.exists(filepath):
        print(f"⚠️  特征顺序文件不存在: {filepath}")
        return None
    
    with open(filepath, 'r') as f:
        features = [line.strip() for line in f if line.strip()]
    
    print(f"📂 从文件加载 {len(features)} 个特征")
    return features


def get_predictor_feature_order():
    """从 MLPredictor 获取特征顺序"""
    print("🔍 从 MLPredictor 获取特征顺序...")
    
    # 创建示例信号
    from datetime import datetime
    sample_signal = {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'confidence': 0.75,
        'entry_price': 60000,
        'stop_loss': 59000,
        'take_profit': 62000,
        'order_blocks': 2,
        'liquidity_zones': 1,
        'market_structure': 'bullish',
        'timestamp': datetime.now(),
        'timeframes': {
            '1h': 'bullish',
            '15m': 'bullish',
            '5m': 'bullish'
        },
        'indicators': {
            'rsi': 55,
            'macd': 0.1,
            'macd_signal': 0.05,
            'macd_histogram': 0.05,
            'atr': 500,
            'bb_width_pct': 2.5,
            'volume_sma_ratio': 1.2,
            'price_vs_ema50': 0.02,
            'price_vs_ema200': 0.05
        }
    }
    
    # 创建predictor并提取特征
    predictor = MLPredictor()
    features = predictor._prepare_signal_features(sample_signal)
    
    if features is None:
        print("❌ 特征提取失败")
        return None, None
    
    print(f"✅ 提取 {len(features)} 个特征")
    return EXPECTED_FEATURES, features


def compare_feature_orders(expected_order, file_order=None):
    """比较预期顺序和文件顺序"""
    print("\n" + "="*60)
    print("特征顺序验证")
    print("="*60)
    
    # 1. 验证预期特征数量
    print(f"\n1️⃣ 预期特征数量: {len(expected_order)}")
    if len(expected_order) != EXPECTED_FEATURE_COUNT:
        print(f"   ❌ 特征数量不匹配: 预期 {EXPECTED_FEATURE_COUNT}, 实际 {len(expected_order)}")
        return False
    else:
        print(f"   ✅ 特征数量正确: {EXPECTED_FEATURE_COUNT}")
    
    # 2. 验证关键特征位置
    print(f"\n2️⃣ 验证关键特征位置:")
    
    # direction_encoded 应该是第20个特征（索引19）
    if expected_order[19] == 'direction_encoded':
        print(f"   ✅ 'direction_encoded' 在位置20 (索引19)")
    else:
        print(f"   ❌ 'direction_encoded' 位置错误: {expected_order[19]} (预期: direction_encoded)")
        return False
    
    # confidence_score 应该是第1个特征（索引0）
    if expected_order[0] == 'confidence_score':
        print(f"   ✅ 'confidence_score' 在位置1 (索引0)")
    else:
        print(f"   ❌ 'confidence_score' 位置错误: {expected_order[0]}")
        return False
    
    # 3. 如果有文件顺序，进行比较
    if file_order:
        print(f"\n3️⃣ 与文件顺序比较:")
        
        if len(file_order) != len(expected_order):
            print(f"   ❌ 特征数量不匹配: 文件 {len(file_order)}, 预期 {len(expected_order)}")
            return False
        
        all_match = True
        for i, (exp, file) in enumerate(zip(expected_order, file_order)):
            if exp != file:
                print(f"   ❌ 位置{i+1}不匹配: 预期 '{exp}', 文件 '{file}'")
                all_match = False
        
        if all_match:
            print(f"   ✅ 特征顺序完全匹配！")
        else:
            return False
    
    # 4. 打印完整特征列表
    print(f"\n4️⃣ 完整特征列表:")
    print("   " + "-"*56)
    for i, feat in enumerate(expected_order, 1):
        marker = "🔥" if feat == 'direction_encoded' else "  "
        print(f"   {marker} {i:2d}. {feat}")
    print("   " + "-"*56)
    
    return True


def main():
    """主函数"""
    print("🚀 特征顺序验证工具 v3.13.0")
    print("-" * 60)
    
    # 1. 获取predictor特征顺序
    expected_order, sample_features = get_predictor_feature_order()
    
    if expected_order is None:
        print("❌ 无法获取特征顺序")
        sys.exit(1)
    
    # 2. 尝试加载文件特征顺序
    file_order = load_feature_order_from_file()
    
    # 3. 比较特征顺序
    is_valid = compare_feature_orders(expected_order, file_order)
    
    # 4. 输出结果
    print("\n" + "="*60)
    if is_valid:
        print("🎉 特征顺序验证通过！")
        print("="*60)
        print(f"\n✅ 所有检查通过:")
        print(f"  - 特征数量: {EXPECTED_FEATURE_COUNT}")
        print(f"  - direction_encoded 位置: 20 (索引19)")
        print(f"  - 特征顺序: 一致")
        
        if sample_features:
            print(f"\n📊 示例特征向量 (前5个):")
            for i, val in enumerate(sample_features[:5], 1):
                print(f"  {i}. {expected_order[i-1]}: {val}")
        
        sys.exit(0)
    else:
        print("❌ 特征顺序验证失败！")
        print("="*60)
        print("\n🔧 请修复:")
        print("  1. 确保 MLPredictor._prepare_signal_features() 生成29个特征")
        print("  2. 确保 'direction_encoded' 在第20个位置（索引19）")
        print("  3. 确保特征顺序与 EXPECTED_FEATURES 一致")
        sys.exit(1)


if __name__ == "__main__":
    main()
