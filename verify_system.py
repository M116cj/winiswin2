#!/usr/bin/env python3
"""
系统完整性验证脚本
验证所有核心组件和配置
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

async def verify_imports():
    """验证所有核心导入"""
    print("🔍 验证核心模块导入...")
    try:
        from src.config import Config
        from src.clients.binance_client import BinanceClient
        from src.services.data_service import DataService
        from src.services.parallel_analyzer import ParallelAnalyzer
        from src.services.timeframe_scheduler import SmartDataManager
        from src.strategies.ict_strategy import ICTStrategy
        from src.managers.risk_manager import RiskManager
        from src.services.trading_service import TradingService
        from src.managers.virtual_position_manager import VirtualPositionManager
        from src.managers.trade_recorder import TradeRecorder
        from src.integrations.discord_bot import TradingDiscordBot
        from src.monitoring.health_monitor import HealthMonitor
        from src.monitoring.performance_monitor import PerformanceMonitor
        from src.ml.predictor import MLPredictor
        print("✅ 所有核心模块导入成功")
        return True, Config
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False, None

async def verify_config(Config):
    """验证配置"""
    print("\n🔍 验证系统配置...")
    try:
        is_valid, errors = Config.validate()
        if not is_valid:
            print("⚠️  配置验证警告（这在没有 API 密钥时是正常的）:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("✅ 配置验证通过")
        
        print(f"\n📊 配置参数:")
        print(f"  TOP_VOLATILITY_SYMBOLS: {Config.TOP_VOLATILITY_SYMBOLS}")
        print(f"  MAX_POSITIONS: {Config.MAX_POSITIONS}")
        print(f"  TRADING_ENABLED: {Config.TRADING_ENABLED}")
        print(f"  BINANCE_TESTNET: {Config.BINANCE_TESTNET}")
        return True
    except Exception as e:
        print(f"❌ 配置验证失败: {e}")
        return False

async def verify_file_structure():
    """验证文件结构"""
    print("\n🔍 验证文件结构...")
    required_files = [
        "src/main.py",
        "src/config.py",
        "src/clients/binance_client.py",
        "src/services/data_service.py",
        "src/services/parallel_analyzer.py",
        "src/services/timeframe_scheduler.py",
        "src/strategies/ict_strategy.py",
        "src/managers/virtual_position_manager.py",
        "src/ml/model_trainer.py",
        "railway.json",
        "nixpacks.toml",
        "requirements.txt",
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
            print(f"  ❌ 缺少: {file_path}")
        else:
            print(f"  ✅ 存在: {file_path}")
    
    if missing_files:
        print(f"\n❌ 缺少 {len(missing_files)} 个必需文件")
        return False
    else:
        print(f"\n✅ 所有必需文件存在")
        return True

async def verify_version():
    """验证版本标识"""
    print("\n🔍 验证版本标识...")
    try:
        with open("src/main.py", "r", encoding="utf-8") as f:
            content = f.read()
            if "2025-10-25-v2.0" in content and "200個高波動率交易對" in content:
                print("✅ 版本标识正确: 2025-10-25-v2.0")
                return True
            else:
                print("❌ 未找到正确的版本标识")
                return False
    except Exception as e:
        print(f"❌ 版本验证失败: {e}")
        return False

async def verify_no_legacy_code():
    """验证没有旧代码"""
    print("\n🔍 验证没有遗留代码...")
    try:
        # 搜索所有 Python 文件
        legacy_patterns = ["獲取前 5 個", "BTCUSDT", "個交易對價格"]
        found_legacy = False
        
        for py_file in Path("src").rglob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                for pattern in legacy_patterns:
                    if pattern in content:
                        print(f"  ⚠️  在 {py_file} 中找到可疑模式: {pattern}")
                        found_legacy = True
        
        if not found_legacy:
            print("✅ 未找到旧版本代码")
            return True
        else:
            print("❌ 发现可能的旧版本代码")
            return False
    except Exception as e:
        print(f"❌ 遗留代码检查失败: {e}")
        return False

async def main():
    """主验证函数"""
    print("=" * 60)
    print("🚀 Winiswin2 v2.0 系统完整性验证")
    print("=" * 60)
    
    results = []
    
    # 1. 导入验证
    import_ok, Config = await verify_imports()
    results.append(("模块导入", import_ok))
    
    if not import_ok:
        print("\n❌ 模块导入失败，无法继续验证")
        return False
    
    # 2. 配置验证
    config_ok = await verify_config(Config)
    results.append(("配置验证", config_ok))
    
    # 3. 文件结构验证
    structure_ok = await verify_file_structure()
    results.append(("文件结构", structure_ok))
    
    # 4. 版本验证
    version_ok = await verify_version()
    results.append(("版本标识", version_ok))
    
    # 5. 遗留代码检查
    no_legacy = await verify_no_legacy_code()
    results.append(("无遗留代码", no_legacy))
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 验证总结")
    print("=" * 60)
    
    for check_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{check_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有验证通过！系统已准备好部署到 Railway")
        print("=" * 60)
        print("\n📌 下一步:")
        print("1. 确保代码已推送到 GitHub")
        print("2. 在 Railway 控制台点击 'Redeploy' 按钮")
        print("3. 检查 Railway 日志中的版本号: 2025-10-25-v2.0")
        return True
    else:
        print("⚠️  部分验证失败，请检查上述错误")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
