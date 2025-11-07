"""
Database Monitor Usage Examples
数据库监控系统使用示例
"""

import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import DatabaseManager, TradingDataService, DatabaseMonitor, initialize_database
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_1_one_time_summary():
    """示例1: 一次性显示数据库统计摘要"""
    print("\n" + "=" * 70)
    print("示例 1: 一次性显示数据库统计摘要")
    print("=" * 70 + "\n")
    
    # 创建数据库管理器
    db_manager = DatabaseManager(min_connections=1, max_connections=5)
    
    # 创建监控器（不自动启动）
    monitor = DatabaseMonitor(
        db_manager=db_manager,
        auto_start=False
    )
    
    # 获取并显示一次性摘要
    print("📊 获取当前数据库统计...")
    summary = monitor.get_summary()
    
    if summary:
        print("\n✅ 统计数据获取成功！")
    else:
        print("\n❌ 统计数据获取失败")
    
    # 清理
    db_manager.close_all_connections()


def example_2_background_monitoring():
    """示例2: 后台监控模式（定期自动刷新）"""
    print("\n" + "=" * 70)
    print("示例 2: 后台监控模式")
    print("=" * 70 + "\n")
    
    # 创建数据库管理器
    db_manager = DatabaseManager(min_connections=2, max_connections=10)
    
    # 初始化数据库
    initialize_database(db_manager)
    
    # 创建监控器并自动启动
    monitor = DatabaseMonitor(
        db_manager=db_manager,
        refresh_interval=30,  # 30秒刷新一次
        auto_start=True,      # 自动启动
        enable_alerts=True    # 启用警告
    )
    
    try:
        print("\n监控服务已启动，将每30秒自动刷新统计数据...")
        print("按 Ctrl+C 停止监控\n")
        
        # 保持主线程运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n收到中断信号，正在停止监控...")
        monitor.stop_monitoring()
        db_manager.close_all_connections()
        print("✅ 监控服务已停止")


def example_3_custom_thresholds():
    """示例3: 自定义警告阈值"""
    print("\n" + "=" * 70)
    print("示例 3: 自定义警告阈值")
    print("=" * 70 + "\n")
    
    db_manager = DatabaseManager()
    
    # 创建监控器
    monitor = DatabaseMonitor(
        db_manager=db_manager,
        refresh_interval=60,
        enable_alerts=True
    )
    
    # 自定义阈值
    monitor.thresholds = {
        'max_response_time_ms': 500,   # 最大响应时间 500ms
        'max_error_rate': 0.02,        # 最大错误率 2%
        'max_open_positions': 5,       # 最大未平仓 5个
        'min_connection_pool': 1,      # 最小连接数 1个
    }
    
    print("✅ 已设置自定义阈值:")
    print(f"   • 最大响应时间: {monitor.thresholds['max_response_time_ms']}ms")
    print(f"   • 最大错误率: {monitor.thresholds['max_error_rate']:.1%}")
    print(f"   • 最大未平仓: {monitor.thresholds['max_open_positions']}")
    
    # 获取统计并检查警告
    stats = monitor.get_real_time_stats(use_cache=False)
    if stats:
        monitor.display_stats(stats)
        monitor.check_alerts(stats)
    
    db_manager.close_all_connections()


def example_4_integration_with_trading_bot():
    """示例4: 与交易机器人整合"""
    print("\n" + "=" * 70)
    print("示例 4: 与交易机器人整合")
    print("=" * 70 + "\n")
    
    print("""
    # 在交易机器人main.py中的整合示例
    
    from src.database import DatabaseManager, TradingDataService, DatabaseMonitor, initialize_database
    
    async def main():
        # 1. 初始化数据库
        db_manager = DatabaseManager(
            min_connections=2,
            max_connections=20
        )
        
        # 2. 初始化表结构
        initialize_database(db_manager)
        
        # 3. 创建数据服务
        db_service = TradingDataService(db_manager)
        
        # 4. 启动数据库监控（后台运行）
        monitor = DatabaseMonitor(
            db_manager=db_manager,
            refresh_interval=60,    # 每60秒刷新一次
            auto_start=True,        # 自动启动
            enable_alerts=True      # 启用警告
        )
        
        # 5. 运行交易机器人
        try:
            await run_trading_logic()
        finally:
            # 6. 清理资源
            monitor.stop_monitoring()
            db_manager.close_all_connections()
    
    # 这样配置后，监控服务会在后台自动运行，
    # 每60秒在日志中显示一次数据库统计信息
    """)


def example_5_manual_control():
    """示例5: 手动控制监控"""
    print("\n" + "=" * 70)
    print("示例 5: 手动控制监控")
    print("=" * 70 + "\n")
    
    db_manager = DatabaseManager()
    
    # 创建监控器（不自动启动）
    monitor = DatabaseMonitor(
        db_manager=db_manager,
        refresh_interval=20,
        auto_start=False
    )
    
    try:
        # 手动启动监控
        print("1️⃣ 手动启动监控...")
        monitor.start_monitoring()
        
        # 运行一段时间
        print("2️⃣ 监控运行中（将运行60秒）...")
        time.sleep(60)
        
        # 手动停止监控
        print("\n3️⃣ 手动停止监控...")
        monitor.stop_monitoring()
        
        print("✅ 监控生命周期演示完成")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
    finally:
        db_manager.close_all_connections()


def example_6_cache_usage():
    """示例6: 使用缓存优化性能"""
    print("\n" + "=" * 70)
    print("示例 6: 缓存使用示例")
    print("=" * 70 + "\n")
    
    db_manager = DatabaseManager()
    monitor = DatabaseMonitor(db_manager)
    
    # 第一次查询（从数据库获取）
    print("1️⃣ 第一次查询（从数据库）...")
    start = time.time()
    stats1 = monitor.get_real_time_stats(use_cache=False)
    time1 = (time.time() - start) * 1000
    print(f"   耗时: {time1:.2f}ms")
    
    # 第二次查询（使用缓存）
    print("\n2️⃣ 第二次查询（使用缓存）...")
    start = time.time()
    stats2 = monitor.get_real_time_stats(use_cache=True)
    time2 = (time.time() - start) * 1000
    print(f"   耗时: {time2:.2f}ms")
    
    print(f"\n💡 性能提升: {(1 - time2/time1)*100:.1f}%")
    
    # 等待缓存过期
    print("\n3️⃣ 等待5秒让缓存过期...")
    time.sleep(6)
    
    # 第三次查询（缓存已过期，重新查询）
    print("4️⃣ 缓存过期后查询...")
    start = time.time()
    stats3 = monitor.get_real_time_stats(use_cache=True)
    time3 = (time.time() - start) * 1000
    print(f"   耗时: {time3:.2f}ms")
    
    db_manager.close_all_connections()


def main():
    """运行所有示例"""
    print("🚀 数据库监控系统使用示例")
    print("=" * 70)
    
    # 检查环境变量
    if not os.environ.get('DATABASE_URL') and not os.environ.get('DATABASE_PUBLIC_URL'):
        print("⚠️ 未检测到数据库环境变量")
        print("   请在Railway中配置PostgreSQL服务")
        print("   或设置 DATABASE_URL 环境变量进行本地测试")
        return
    
    while True:
        print("\n" + "=" * 70)
        print("请选择示例:")
        print("=" * 70)
        print("1 - 一次性显示数据库统计摘要")
        print("2 - 后台监控模式（定期自动刷新）")
        print("3 - 自定义警告阈值")
        print("4 - 与交易机器人整合说明")
        print("5 - 手动控制监控")
        print("6 - 缓存使用示例")
        print("0 - 退出")
        print("=" * 70)
        
        try:
            choice = input("\n请输入选项 (0-6): ").strip()
            
            if choice == '1':
                example_1_one_time_summary()
            elif choice == '2':
                example_2_background_monitoring()
            elif choice == '3':
                example_3_custom_thresholds()
            elif choice == '4':
                example_4_integration_with_trading_bot()
            elif choice == '5':
                example_5_manual_control()
            elif choice == '6':
                example_6_cache_usage()
            elif choice == '0':
                print("\n👋 再见！")
                break
            else:
                print("\n❌ 无效选项，请重试")
                
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")


if __name__ == "__main__":
    main()
