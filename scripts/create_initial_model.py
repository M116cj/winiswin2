"""
🔥 创建初始ML模型（用于演示和测试）

当系统无法访问Binance API时，使用模拟数据创建初始XGBoost模型
使系统可以演示完整的ML预测功能
"""

import sys
import os
import numpy as np
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def create_minimal_model():
    """创建一个最小化的初始模型"""
    try:
        import xgboost as xgb
    except ImportError:
        print("❌ XGBoost未安装，无法创建模型")
        print("   请运行: pip install xgboost")
        return False
    
    print("=" * 80)
    print("🔥 创建初始ML模型（演示用）")
    print("=" * 80)
    
    # 创建模型目录
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)
    
    print("\n📊 生成模拟训练数据...")
    
    # 生成模拟训练数据（44个特征）
    # 策略：高信心度 + 高R:R + 趋势一致 → 高胜率
    np.random.seed(42)
    n_samples = 500
    
    # 特征生成（44个特征）
    X_samples = []
    y_samples = []
    
    for i in range(n_samples):
        # 基本特征 (8)
        confidence = np.random.uniform(0.4, 0.9)
        leverage = np.random.uniform(1.0, 3.0)
        position_value = np.random.uniform(10.0, 100.0)
        rr_ratio = np.random.uniform(1.0, 3.0)
        order_blocks = np.random.randint(0, 5)
        liquidity_zones = np.random.randint(0, 5)
        entry_price = np.random.uniform(20000, 60000)
        win_probability_base = np.random.uniform(0.4, 0.7)
        
        # 技术指标 (10)
        rsi = np.random.uniform(30, 70)
        macd = np.random.uniform(-50, 50)
        macd_signal = np.random.uniform(-50, 50)
        macd_histogram = macd - macd_signal
        atr = np.random.uniform(100, 1000)
        bb_width = np.random.uniform(0.01, 0.1)
        volume_sma_ratio = np.random.uniform(0.5, 1.5)
        ema50 = entry_price * np.random.uniform(0.98, 1.02)
        ema200 = entry_price * np.random.uniform(0.95, 1.05)
        volatility_24h = np.random.uniform(0.01, 0.05)
        
        # 趋势特征 (6)
        trend_1h = np.random.choice([-1.0, 0.0, 1.0])
        trend_15m = np.random.choice([-1.0, 0.0, 1.0])
        trend_5m = np.random.choice([-1.0, 0.0, 1.0])
        market_structure = np.random.choice([-1.0, 0.0, 1.0])
        direction = np.random.choice([-1.0, 1.0])
        
        # 趋势对齐度：3个趋势方向的平均值绝对值
        trend_alignment = abs(trend_1h + trend_15m + trend_5m) / 3.0
        
        # 其他特征 (14)
        ema50_slope = np.random.uniform(-0.01, 0.01)
        ema200_slope = np.random.uniform(-0.01, 0.01)
        higher_highs = np.random.randint(0, 10)
        lower_lows = np.random.randint(0, 10)
        support_strength = np.random.uniform(0, 1)
        resistance_strength = np.random.uniform(0, 1)
        fvg_count = np.random.randint(0, 5)
        swing_high_distance = np.random.uniform(0, 500)
        swing_low_distance = np.random.uniform(0, 500)
        volume_profile = np.random.uniform(0, 1)
        price_momentum = np.random.uniform(-0.05, 0.05)
        order_flow = np.random.uniform(-1, 1)
        liquidity_grab = np.random.randint(0, 2)
        institutional_candle = np.random.randint(0, 2)
        
        # 竞价上下文特征 (3)
        competition_rank = np.random.randint(1, 6)
        score_gap_to_best = np.random.uniform(0, 0.3)
        num_competing_signals = np.random.randint(1, 10)
        
        # WebSocket专属特征 (3)
        latency_zscore = np.random.uniform(-2, 2)
        shard_load = np.random.uniform(0, 1)
        timestamp_consistency = np.random.uniform(0.8, 1.0)
        
        # 组合44个特征
        features = [
            confidence, leverage, position_value, rr_ratio,
            order_blocks, liquidity_zones, entry_price, win_probability_base,
            rsi, macd, macd_signal, macd_histogram, atr, bb_width,
            volume_sma_ratio, ema50, ema200, volatility_24h,
            trend_1h, trend_15m, trend_5m, market_structure, direction, trend_alignment,
            ema50_slope, ema200_slope, higher_highs, lower_lows,
            support_strength, resistance_strength, fvg_count,
            swing_high_distance, swing_low_distance, volume_profile,
            price_momentum, order_flow, liquidity_grab, institutional_candle,
            competition_rank, score_gap_to_best, num_competing_signals,
            latency_zscore, shard_load, timestamp_consistency
        ]
        
        # 标签：基于规则的胜率预测
        # 高信心度 + 高R:R + 趋势一致 → 更高胜率
        win_prob = 0.5  # 基础胜率
        
        # 信心度影响
        win_prob += (confidence - 0.65) * 0.3
        
        # R:R影响
        if rr_ratio > 2.0:
            win_prob += 0.1
        
        # 趋势对齐影响
        if trend_alignment > 0.8:
            win_prob += 0.15
        
        # RSI影响（避免超买超卖）
        if 40 < rsi < 60:
            win_prob += 0.05
        
        # 限制在0-1范围
        win_prob = max(0.0, min(1.0, win_prob))
        
        X_samples.append(features)
        y_samples.append(win_prob)
    
    X = np.array(X_samples)
    y = np.array(y_samples)
    
    print(f"✅ 生成 {len(X)} 个训练样本")
    print(f"   特征维度: {X.shape}")
    print(f"   标签分布: min={y.min():.3f}, max={y.max():.3f}, mean={y.mean():.3f}")
    
    # 创建DMatrix
    print("\n🧠 训练XGBoost模型（生产级参数）...")
    dtrain = xgb.DMatrix(X, label=y)
    
    # 🔥 v3.18.6+ 生产级训练参数
    params = {
        # 🎯 目标函数（二分类）
        'objective': 'binary:logistic',     # 逻辑回归损失
        'eval_metric': 'logloss',           # 评估指标：对概率预测更敏感
        
        # 🌱 树结构（控制复杂度）
        'max_depth': 6,                     # 树深度：平衡偏差与方差
        'min_child_weight': 10,             # 叶节点最小样本权重：防止过拟合噪音
        
        # ⚖️ 正则化（提升泛化）
        'gamma': 0.1,                       # 分裂最小损失减少：避免无意义分裂
        'subsample': 0.8,                   # 训练样本采样率：引入随机性
        'colsample_bytree': 0.8,            # 特征采样率：降低特征相关性
        
        # 🚀 学习率（稳定收敛）
        'learning_rate': 0.1,               # 学习步长：平衡速度与稳定性
        
        # 🧠 其他配置
        'seed': 42,                         # 可重现性
        'n_jobs': -1,                       # 多核心加速
        'verbosity': 0                      # 静默模式（适合生产）
    }
    
    # 训练模型
    n_estimators = 100  # 树数量：足够学习，不过度
    model = xgb.train(
        params,
        dtrain,
        num_boost_round=n_estimators,
        verbose_eval=False
    )
    
    # 保存模型
    model_path = model_dir / "xgboost_model.json"
    model.save_model(str(model_path))
    
    model_size = model_path.stat().st_size / 1024
    
    print(f"✅ 模型训练完成")
    print(f"   🌱 树结构: n_estimators={n_estimators}, max_depth=6, min_child_weight=10")
    print(f"   ⚖️ 正则化: gamma=0.1, subsample=0.8, colsample_bytree=0.8")
    print(f"   🎯 目标函数: binary:logistic, eval_metric=logloss")
    print(f"   💾 保存路径: {model_path}")
    print(f"   📊 文件大小: {model_size:.2f} KB")
    
    # 创建初始化标记
    flag_file = model_dir / "initialized.flag"
    flag_file.write_text(f"Initialized at {Path(__file__).name}\n")
    
    print(f"\n✅ 创建初始化标记: {flag_file}")
    
    print("\n" + "=" * 80)
    print("🎉 初始ML模型创建成功！")
    print("=" * 80)
    print("\n📝 说明:")
    print("   - 这是一个基于模拟数据训练的初始模型")
    print("   - 用于演示ML预测功能")
    print("   - 部署到Railway后，系统会使用真实交易数据重新训练")
    print("   - 每累积50笔真实交易，模型会自动更新")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    success = create_minimal_model()
    sys.exit(0 if success else 1)
