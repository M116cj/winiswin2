"""
v4.6.0 Phase 1A3-1A5 实用主义版本集成测试
验证三个新组件的功能和性能
"""

import time
import numpy as np
from src.config import Config
from src.ml.hybrid_ml_processor import HybridMLProcessor
from src.utils.pragmatic_resource_pool import PragmaticResourcePool
from src.core.on_demand_cache_warmer import OnDemandCacheWarmer


class MockMLModel:
    """模拟ML模型用于测试"""
    def predict(self, features):
        """单个预测"""
        time.sleep(0.01)  # 模拟计算时间
        return 0.75
    
    def predict_batch(self, features_batch):
        """批量预测"""
        time.sleep(0.015 * len(features_batch))  # 批量稍快
        return [0.75 + i * 0.01 for i in range(len(features_batch))]


class MockCache:
    """模拟缓存管理器"""
    def __init__(self):
        self.cache = {}
        self.hits = 0
        self.misses = 0
    
    def get(self, symbol, timeframe):
        key = f"{symbol}_{timeframe}"
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None
    
    def prefetch(self, symbol, timeframe):
        key = f"{symbol}_{timeframe}"
        self.cache[key] = {"data": "cached"}
    
    def get_latest_timestamp(self, symbol, timeframe):
        return time.time()


def test_hybrid_ml_processor():
    """测试HybridMLProcessor"""
    print("\n" + "="*60)
    print("测试1: HybridMLProcessor (混合批量ML推理)")
    print("="*60)
    
    model = MockMLModel()
    processor = HybridMLProcessor(
        model=model,
        batch_size=5,
        max_buffer_time=0.1,
        enable_batching=True
    )
    
    # 测试场景1：单个预测（批量未满）
    print("\n场景1: 单个预测（批量未满）")
    start = time.time()
    result1 = processor.predict("BTCUSDT", {"feature1": 1.0})
    elapsed1 = time.time() - start
    print(f"  结果: {result1:.2f}, 耗时: {elapsed1*1000:.1f}ms")
    
    # 测试场景2：触发批量处理
    print("\n场景2: 连续5个预测（触发批量）")
    start = time.time()
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]
    results = []
    for symbol in symbols:
        result = processor.predict(symbol, {"feature1": 1.0})
        results.append(result)
    elapsed2 = time.time() - start
    print(f"  结果: {[f'{r:.2f}' for r in results]}")
    print(f"  总耗时: {elapsed2*1000:.1f}ms, 平均: {elapsed2/5*1000:.1f}ms/个")
    
    # Flush剩余请求
    processor.flush()
    
    # 打印统计
    processor.log_stats()
    
    return processor.get_stats()


def test_pragmatic_resource_pool():
    """测试PragmaticResourcePool"""
    print("\n" + "="*60)
    print("测试2: PragmaticResourcePool (实用主义资源池)")
    print("="*60)
    
    pool = PragmaticResourcePool(
        array_pool_size=10,
        feature_buffer_pool_size=20,
        kline_buffer_pool_size=15,
        enable_pooling=True
    )
    
    # 测试移动平均计算（使用池化数组）
    print("\n场景1: 池化numpy数组计算")
    price_data = np.random.randn(100) * 100 + 50000
    
    start = time.time()
    for i in range(10):
        ma = pool.compute_moving_average_optimized(price_data, window=20)
    elapsed_pooled = time.time() - start
    print(f"  池化版本: 10次计算耗时 {elapsed_pooled*1000:.2f}ms")
    
    # 对比标准版本
    start = time.time()
    for i in range(10):
        ma = pool._compute_ma_standard(price_data, window=20)
    elapsed_standard = time.time() - start
    print(f"  标准版本: 10次计算耗时 {elapsed_standard*1000:.2f}ms")
    print(f"  性能提升: {(elapsed_standard/elapsed_pooled - 1)*100:.1f}%")
    
    # 测试特征构建
    print("\n场景2: 池化特征字典构建")
    
    def extract_features(data):
        return {"f1": 1.0, "f2": 2.0, "f3": 3.0}
    
    market_data = {"price": 50000}
    extractors = [extract_features]
    
    start = time.time()
    for i in range(100):
        features = pool.build_features_optimized(market_data, extractors)
    elapsed = time.time() - start
    print(f"  100次特征构建耗时: {elapsed*1000:.2f}ms")
    
    # 打印池统计
    pool.log_stats()
    
    return pool.get_pool_stats()


def test_on_demand_cache_warmer():
    """测试OnDemandCacheWarmer"""
    print("\n" + "="*60)
    print("测试3: OnDemandCacheWarmer (事件驱动缓存预热)")
    print("="*60)
    
    cache = MockCache()
    warmer = OnDemandCacheWarmer(
        cache_manager=cache,
        warm_threshold=3,
        cooldown_seconds=1,
        top_n_warm=3,
        enable_warming=True
    )
    
    # 场景1: 记录市场扫描
    print("\n场景1: 模拟市场扫描触发预热")
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    
    # 扫描3次（未达阈值）
    for i in range(3):
        warmer.record_market_scan(symbols, "1m")
        print(f"  扫描 #{i+1}")
    
    # 第4次扫描应触发预热
    print("  扫描 #4 (应触发预热)")
    warmer.record_market_scan(symbols, "1m")
    
    # 检查缓存命中率
    time.sleep(0.1)  # 等待预热完成
    
    # 场景2: 交易信号触发预热
    print("\n场景2: 交易信号触发立即预热")
    warmer.record_trading_signal("ADAUSDT", "1m")
    
    # 打印统计
    warmer.log_stats()
    
    return warmer.get_stats()


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("🚀 v4.6.0 Phase 1A3-1A5 实用主义版本集成测试")
    print("="*60)
    
    # 打印配置
    print(f"\n配置状态:")
    print(f"  HYBRID_ML_ENABLED: {Config.HYBRID_ML_ENABLED}")
    print(f"  HYBRID_ML_BATCH_SIZE: {Config.HYBRID_ML_BATCH_SIZE}")
    print(f"  PRAGMATIC_POOL_ENABLED: {Config.PRAGMATIC_POOL_ENABLED}")
    print(f"  ON_DEMAND_CACHE_WARMING: {Config.ON_DEMAND_CACHE_WARMING}")
    
    # 运行测试
    stats1 = test_hybrid_ml_processor()
    stats2 = test_pragmatic_resource_pool()
    stats3 = test_on_demand_cache_warmer()
    
    # 汇总结果
    print("\n" + "="*60)
    print("📊 测试汇总")
    print("="*60)
    
    print(f"\n1. HybridMLProcessor:")
    print(f"   - 批量效率: {stats1['batch_efficiency']:.1f}%")
    print(f"   - 缓存命中率: {stats1['cache_hit_rate']:.1f}%")
    print(f"   - 总预测数: {stats1['total_predictions']}")
    
    print(f"\n2. PragmaticResourcePool:")
    if stats2['enabled']:
        print(f"   - 启用状态: ✅")
        for pool_name, pool_stats in stats2['pools'].items():
            print(f"   - {pool_name}: 复用率 {pool_stats['reuse_rate']*100:.1f}%")
    else:
        print(f"   - 启用状态: ❌")
    
    print(f"\n3. OnDemandCacheWarmer:")
    print(f"   - 预热触发: {stats3['warmings_triggered']}次")
    print(f"   - 成功率: {stats3['warm_success_rate']:.1f}%")
    print(f"   - 访问模式: {stats3['access_patterns_count']}个")
    
    print("\n" + "="*60)
    print("✅ 所有测试完成！")
    print("="*60)


if __name__ == "__main__":
    main()
