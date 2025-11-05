"""
SmartLogger 使用示例
展示速率限制、日志聚合、结构化日志等功能
"""

import logging
import time
from src.utils.smart_logger import create_smart_logger

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def demo_rate_limiting():
    """演示速率限制功能"""
    print("\n" + "=" * 80)
    print("📝 演示1: 速率限制（防止日志洪水）")
    print("=" * 80)
    
    logger = create_smart_logger(
        name="RateLimitDemo",
        rate_limit_window=5.0,  # 5秒窗口
        enable_aggregation=False
    )
    
    # 快速记录相同消息10次（只会记录1次）
    for i in range(10):
        logger.info("WebSocket连接成功")
        time.sleep(0.1)
    
    print("\n✅ 相同消息在5秒内只记录1次，其余9次被速率限制")
    
    # 等待5秒后再次记录（会被记录）
    time.sleep(5.5)
    logger.info("WebSocket连接成功")
    print("✅ 5秒后再次记录，成功写入")
    
    # 打印统计
    stats = logger.get_stats()
    print(f"\n📊 统计: 总尝试{stats['total_logs']}次, 限制{stats['rate_limited']}次, 效率{stats['rate_limit_efficiency']:.1f}%")


def demo_aggregation():
    """演示日志聚合功能"""
    print("\n" + "=" * 80)
    print("📊 演示2: 日志聚合（合并重复消息）")
    print("=" * 80)
    
    logger = create_smart_logger(
        name="AggregationDemo",
        rate_limit_window=2.0,  # 2秒窗口
        enable_aggregation=True
    )
    
    # 记录多次相同消息
    for i in range(20):
        logger.warning(f"价格波动超过阈值")
        time.sleep(0.3)
    
    # 刷新聚合日志
    aggregations = logger.flush_aggregations()
    
    print(f"\n📊 聚合结果: {len(aggregations)}条消息被聚合")
    for agg in aggregations:
        print(f"   - '{agg['message']}' 重复{agg['count']}次, 持续{agg['duration']:.1f}秒")
    
    stats = logger.get_stats()
    print(f"\n📊 统计: 聚合{stats['aggregated']}次日志调用")


def demo_structured_logging():
    """演示结构化日志"""
    print("\n" + "=" * 80)
    print("📋 演示3: 结构化日志（JSON格式）")
    print("=" * 80)
    
    logger = create_smart_logger(
        name="StructuredDemo",
        rate_limit_window=60.0,
        enable_structured=True,
        structured_log_file="data/structured_logs.jsonl"
    )
    
    # 记录结构化日志
    logger.info("交易开仓", extra={
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry_price': 50000.0,
        'position_size': 0.1
    })
    
    logger.info("交易平仓", extra={
        'symbol': 'BTCUSDT',
        'exit_price': 50500.0,
        'pnl': 50.0,
        'pnl_pct': 1.0
    })
    
    logger.error("订单失败", extra={
        'error_code': 'INSUFFICIENT_BALANCE',
        'required': 1000,
        'available': 500
    })
    
    print("✅ 结构化日志已写入: data/structured_logs.jsonl")
    print("   每行是一个JSON对象，包含timestamp、level、message和extra字段")
    
    logger.close()


def demo_mixed_levels():
    """演示混合日志级别"""
    print("\n" + "=" * 80)
    print("🔀 演示4: 混合日志级别（不同级别不同行为）")
    print("=" * 80)
    
    logger = create_smart_logger(
        name="MixedLevelDemo",
        rate_limit_window=3.0,
        enable_aggregation=True
    )
    
    # DEBUG日志（会被限速）
    for i in range(5):
        logger.debug("调试信息: 数据包处理中")
        time.sleep(0.1)
    
    # INFO日志（会被限速）
    for i in range(5):
        logger.info("WebSocket心跳检测")
        time.sleep(0.1)
    
    # ERROR日志（不会被限速）
    for i in range(5):
        logger.error(f"严重错误 #{i}")
        time.sleep(0.1)
    
    # CRITICAL日志（不会被限速）
    for i in range(5):
        logger.critical(f"致命错误 #{i}")
        time.sleep(0.1)
    
    print("\n✅ ERROR和CRITICAL级别不受速率限制，全部记录")
    print("   DEBUG和INFO级别受速率限制，只记录首次")
    
    stats = logger.get_stats()
    print(f"\n📊 统计按级别:")
    for level, count in stats['by_level'].items():
        print(f"   {level}: {count}次")


def demo_performance():
    """演示性能优化效果"""
    print("\n" + "=" * 80)
    print("⚡ 演示5: 性能对比（SmartLogger vs 原生logger）")
    print("=" * 80)
    
    # 原生logger测试
    native_logger = logging.getLogger("NativeDemo")
    start = time.time()
    for i in range(1000):
        native_logger.info("测试消息")
    native_duration = time.time() - start
    
    # SmartLogger测试
    smart_logger = create_smart_logger(
        name="SmartDemo",
        rate_limit_window=1.0,
        enable_aggregation=True
    )
    start = time.time()
    for i in range(1000):
        smart_logger.info("测试消息")
    smart_duration = time.time() - start
    
    print(f"\n📊 性能对比:")
    print(f"   原生logger: {native_duration*1000:.2f}ms (1000次)")
    print(f"   SmartLogger: {smart_duration*1000:.2f}ms (1000次)")
    print(f"   速率限制效率: {smart_logger.get_stats()['rate_limit_efficiency']:.1f}%")
    print(f"   实际写入: {1000 - smart_logger.get_stats()['rate_limited']}次")
    
    smart_logger.close()


def main():
    """运行所有演示"""
    print("\n" + "🚀" * 40)
    print("SmartLogger 功能演示")
    print("🚀" * 40)
    
    # 演示1: 速率限制
    demo_rate_limiting()
    
    # 演示2: 日志聚合
    demo_aggregation()
    
    # 演示3: 结构化日志
    demo_structured_logging()
    
    # 演示4: 混合级别
    demo_mixed_levels()
    
    # 演示5: 性能对比
    demo_performance()
    
    print("\n" + "✅" * 40)
    print("所有演示完成！")
    print("✅" * 40 + "\n")


if __name__ == "__main__":
    main()
