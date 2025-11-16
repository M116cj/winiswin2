#!/usr/bin/env python3
"""
快速系统检查脚本 - 无需导入项目模块
"""

import os
import sys
from pathlib import Path

def main():
    print("\n" + "="*80)
    print("📊 SelfLearningTrader v4.4.1 - 系统检查报告")
    print("="*80)
    
    # 统计结果
    total_checks = 0
    passed_checks = 0
    
    # 1. 环境配置检查
    print("\n✅ 环境配置:")
    print(f"  • Python版本: {sys.version.split()[0]} ✅")
    passed_checks += 1
    total_checks += 1
    
    # Binance API
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    if api_key and api_secret:
        print(f"  • Binance API: 已配置 ✅")
        passed_checks += 1
    else:
        print(f"  • Binance API: 未配置 ❌ (无法执行实际交易)")
    total_checks += 1
    
    # 数据库
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        print(f"  • 数据库: 已配置 ✅")
        passed_checks += 1
    else:
        print(f"  • 数据库: 未配置 ❌")
    total_checks += 1
    
    # WebSocket模式
    ws_only = os.getenv("WEBSOCKET_ONLY_KLINES", "true").lower() == "true"
    if ws_only:
        print(f"  • WebSocket模式: 已启用 ✅")
        passed_checks += 1
    else:
        print(f"  • WebSocket模式: 未启用 ⚠️")
    total_checks += 1
    
    # 风险控制
    time_stop = os.getenv("TIME_BASED_STOP_LOSS_ENABLED", "true").lower() == "true"
    cross_margin = os.getenv("CROSS_MARGIN_PROTECTOR_ENABLED", "true").lower() == "true"
    if time_stop and cross_margin:
        print(f"  • 风险控制: 已启用 ✅")
        passed_checks += 1
    else:
        print(f"  • 风险控制: 部分启用 ⚠️")
    total_checks += 1
    
    # 2. 核心文件检查
    print("\n✅ 核心文件:")
    core_files = [
        "src/main.py",
        "src/config.py",
        "src/core/unified_scheduler.py",
        "src/strategies/self_learning_trader.py",
        "requirements.txt"
    ]
    
    for file_path in core_files:
        if Path(file_path).exists():
            size = Path(file_path).stat().st_size
            print(f"  • {file_path}: {size:,} 字节 ✅")
            passed_checks += 1
        else:
            print(f"  • {file_path}: 不存在 ❌")
        total_checks += 1
    
    # 3. 依赖包检查
    print("\n✅ 依赖包:")
    packages = ["aiohttp", "pandas", "numpy", "xgboost", "ccxt"]
    
    for pkg in packages:
        try:
            __import__(pkg if pkg != "sklearn" else "sklearn")
            print(f"  • {pkg}: 已安装 ✅")
            passed_checks += 1
        except ImportError:
            print(f"  • {pkg}: 未安装 ❌")
        total_checks += 1
    
    # 生成总结
    print("\n" + "="*80)
    pass_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
    
    if pass_rate >= 95:
        status = "✅ 优秀"
    elif pass_rate >= 85:
        status = "⚠️ 良好"
    elif pass_rate >= 75:
        status = "🔶 需关注"
    else:
        status = "❌ 异常"
    
    print(f"总体状态: {status}")
    print(f"通过率: {passed_checks}/{total_checks} ({pass_rate:.1f}%)")
    print("="*80)
    
    # 关键问题
    print("\n⚠️ 需要注意:")
    
    if not api_key or not api_secret:
        print("  ❌ Binance API密钥未配置")
        print("     → 系统无法执行实际交易")
        print("     → 建议: 使用测试网模式或配置API密钥")
    
    if not db_url:
        print("  ❌ 数据库未配置")
        print("     → 无法持久化交易数据")
        print("     → 建议: 配置PostgreSQL数据库")
    
    if api_key and api_secret and db_url:
        print("  ✅ 核心配置完整，系统可以正常运行")
    
    print("\n" + "="*80)
    print("📋 下一步建议:")
    
    if not api_key or not api_secret:
        print("  1. 配置 BINANCE_API_KEY 和 BINANCE_API_SECRET")
        print("  2. 或设置 BINANCE_TESTNET=true 使用测试网")
    
    print("  3. 启动 Trading Bot workflow")
    print("  4. 监控日志输出")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
