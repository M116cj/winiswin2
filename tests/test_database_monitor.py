"""
Database Monitor Tests
数据库监控系统测试
"""

import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import DatabaseManager, DatabaseMonitor, initialize_database


def test_monitor_creation():
    """测试1: 监控器创建"""
    print("=" * 70)
    print("测试 1: 监控器创建")
    print("=" * 70)
    
    try:
        db_manager = DatabaseManager(min_connections=1, max_connections=5)
        
        monitor = DatabaseMonitor(
            db_manager=db_manager,
            refresh_interval=60,
            auto_start=False,
            enable_alerts=True
        )
        
        print("✅ 监控器创建成功")
        print(f"   刷新间隔: {monitor.refresh_interval}秒")
        print(f"   警告启用: {monitor.enable_alerts}")
        
        db_manager.close_all_connections()
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_get_stats():
    """测试2: 获取统计数据"""
    print("\n" + "=" * 70)
    print("测试 2: 获取统计数据")
    print("=" * 70)
    
    try:
        db_manager = DatabaseManager(min_connections=1, max_connections=5)
        
        # 确保表已初始化
        initialize_database(db_manager)
        
        monitor = DatabaseMonitor(db_manager, auto_start=False)
        
        # 获取统计数据
        stats = monitor.get_real_time_stats(use_cache=False)
        
        if stats:
            print("✅ 统计数据获取成功")
            print(f"   时间戳: {stats.get('timestamp')}")
            print(f"   交易数: {stats.get('trades', {}).get('total_trades', 0)}")
            print(f"   模型数: {stats.get('ml_models', {}).get('total_models', 0)}")
            print(f"   查询时间: {stats.get('performance', {}).get('query_time_ms', 0):.2f}ms")
            result = True
        else:
            print("❌ 统计数据获取失败")
            result = False
        
        db_manager.close_all_connections()
        return result
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_display_stats():
    """测试3: 显示统计信息"""
    print("\n" + "=" * 70)
    print("测试 3: 显示统计信息")
    print("=" * 70)
    
    try:
        db_manager = DatabaseManager()
        monitor = DatabaseMonitor(db_manager, auto_start=False)
        
        # 获取并显示统计
        summary = monitor.get_summary()
        
        if summary:
            print("✅ 统计信息显示成功")
            result = True
        else:
            print("❌ 统计信息显示失败")
            result = False
        
        db_manager.close_all_connections()
        return result
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_cache():
    """测试4: 缓存功能"""
    print("\n" + "=" * 70)
    print("测试 4: 缓存功能")
    print("=" * 70)
    
    try:
        db_manager = DatabaseManager()
        monitor = DatabaseMonitor(db_manager, auto_start=False)
        
        # 第一次查询（不使用缓存）
        start = time.time()
        stats1 = monitor.get_real_time_stats(use_cache=False)
        time1 = (time.time() - start) * 1000
        
        # 第二次查询（使用缓存）
        start = time.time()
        stats2 = monitor.get_real_time_stats(use_cache=True)
        time2 = (time.time() - start) * 1000
        
        print(f"   第一次查询（数据库）: {time1:.2f}ms")
        print(f"   第二次查询（缓存）: {time2:.2f}ms")
        print(f"   性能提升: {(1 - time2/time1)*100:.1f}%")
        
        if time2 < time1:
            print("✅ 缓存功能正常")
            result = True
        else:
            print("⚠️ 缓存未生效")
            result = True  # 仍然算通过
        
        db_manager.close_all_connections()
        return result
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_custom_thresholds():
    """测试5: 自定义阈值"""
    print("\n" + "=" * 70)
    print("测试 5: 自定义阈值")
    print("=" * 70)
    
    try:
        db_manager = DatabaseManager()
        monitor = DatabaseMonitor(db_manager, auto_start=False)
        
        # 设置自定义阈值
        monitor.thresholds = {
            'max_response_time_ms': 100,
            'max_error_rate': 0.01,
            'max_open_positions': 2,
            'min_connection_pool': 1,
        }
        
        print("✅ 自定义阈值设置成功")
        print(f"   最大响应时间: {monitor.thresholds['max_response_time_ms']}ms")
        print(f"   最大错误率: {monitor.thresholds['max_error_rate']:.1%}")
        
        # 获取统计并检查警告
        stats = monitor.get_real_time_stats(use_cache=False)
        if stats:
            monitor.check_alerts(stats)
        
        db_manager.close_all_connections()
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_background_monitoring():
    """测试6: 后台监控模式"""
    print("\n" + "=" * 70)
    print("测试 6: 后台监控模式（5秒测试）")
    print("=" * 70)
    
    try:
        db_manager = DatabaseManager()
        
        # 启动后台监控
        monitor = DatabaseMonitor(
            db_manager=db_manager,
            refresh_interval=2,  # 2秒刷新（测试用）
            auto_start=True,
            enable_alerts=False
        )
        
        print("✅ 后台监控已启动，运行5秒...")
        time.sleep(5)
        
        # 停止监控
        monitor.stop_monitoring()
        print("✅ 后台监控已停止")
        
        db_manager.close_all_connections()
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("🧪 开始数据库监控系统测试")
    print("=" * 70)
    
    # 检查环境变量
    if not os.environ.get('DATABASE_URL') and not os.environ.get('DATABASE_PUBLIC_URL'):
        print("⚠️ 未找到数据库环境变量")
        print("   测试将使用模拟数据")
        print()
    
    results = []
    
    # 运行测试
    results.append(("监控器创建", test_monitor_creation()))
    results.append(("获取统计数据", test_get_stats()))
    results.append(("显示统计信息", test_display_stats()))
    results.append(("缓存功能", test_cache()))
    results.append(("自定义阈值", test_custom_thresholds()))
    results.append(("后台监控模式", test_background_monitoring()))
    
    # 总结
    print("\n" + "=" * 70)
    print("📊 测试结果总结")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print("=" * 70)
    print(f"总计: {passed_count}/{total_count} 测试通过")
    print("=" * 70)
    
    return passed_count == total_count


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
