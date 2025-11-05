"""
ConfigValidator 使用示例
展示配置验证功能
"""

import logging
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.utils.config_validator import ConfigValidator, validate_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def demo_valid_config():
    """演示有效配置验证"""
    print("\n" + "=" * 80)
    print("✅ 演示1: 有效配置验证")
    print("=" * 80)
    
    # 使用默认配置（应该是有效的）
    valid, errors, warnings = validate_config(Config)
    
    if valid:
        print("✅ 配置验证通过")
    else:
        print("❌ 配置验证失败")
        for error in errors:
            print(f"   {error}")
    
    if warnings:
        print("\n警告:")
        for warning in warnings:
            print(f"   {warning}")


def demo_invalid_config():
    """演示无效配置验证"""
    print("\n" + "=" * 80)
    print("❌ 演示2: 无效配置验证")
    print("=" * 80)
    
    # 创建一个临时配置类模拟无效配置
    class InvalidConfig:
        BINANCE_API_KEY = ""  # ❌ 缺失
        BINANCE_API_SECRET = ""  # ❌ 缺失
        DISCORD_TOKEN = ""
        
        MIN_CONFIDENCE = 1.5  # ❌ 超出范围（应该0-1）
        MIN_WIN_PROBABILITY = -0.1  # ❌ 负数
        MIN_RR_RATIO = 5.0
        MAX_RR_RATIO = 3.0  # ❌ 小于MIN_RR_RATIO
        
        MAX_CONCURRENT_ORDERS = 100  # ⚠️  过高
        CYCLE_INTERVAL = 5  # ❌ 过低
        
        MAX_TOTAL_BUDGET_RATIO = 1.2  # ❌ 超出范围
        MAX_SINGLE_POSITION_RATIO = 0.5
        MAX_TOTAL_MARGIN_RATIO = 0.9
        EQUITY_USAGE_RATIO = 0.8
        MIN_NOTIONAL_VALUE = 5.0
        MIN_STOP_DISTANCE_PCT = 0.003
        RISK_KILL_THRESHOLD = 0.99
        MIN_LEVERAGE = 0.5
        
        EMA_FAST = 50  # ❌ 大于EMA_SLOW
        EMA_SLOW = 20
        RSI_PERIOD = 14
        RSI_OVERBOUGHT = 50  # ❌ 小于等于RSI_OVERSOLD
        RSI_OVERSOLD = 70
        ATR_PERIOD = 14
        ATR_MULTIPLIER = 2.0
        ADX_PERIOD = 14
        ADX_TREND_THRESHOLD = 20.0
        ADX_HARD_REJECT_THRESHOLD = 15.0  # ⚠️  应小于WEAK_TREND
        ADX_WEAK_TREND_THRESHOLD = 10.0
        
        SCAN_INTERVAL = 60
        POSITION_MONITOR_INTERVAL = 60
        VIRTUAL_POSITION_CYCLE_INTERVAL = 10
        
        WEBSOCKET_SYMBOL_LIMIT = 200
        WEBSOCKET_SHARD_SIZE = 500  # ⚠️  大于SYMBOL_LIMIT
        WEBSOCKET_HEARTBEAT_TIMEOUT = 30
        
        DATA_DIR = "data"
        LOG_FILE = "data/logs/trading_bot.log"
        
        BOOTSTRAP_TRADE_LIMIT = 50
        BOOTSTRAP_MIN_WIN_PROBABILITY = 0.5  # ❌ 大于MIN_WIN_PROBABILITY
        BOOTSTRAP_MIN_CONFIDENCE = 2.0  # ❌ 大于MIN_CONFIDENCE
        BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD = 0.25
        SIGNAL_QUALITY_THRESHOLD = 0.40
        
        CROSS_MARGIN_PROTECTOR_THRESHOLD = 0.95  # ⚠️  应小于MAX_TOTAL_MARGIN_RATIO
    
    validator = ConfigValidator(InvalidConfig)
    valid, errors, warnings = validator.validate_all()
    
    print(f"\n验证结果: {'✅ 通过' if valid else '❌ 失败'}")
    print(f"错误数: {len(errors)}")
    print(f"警告数: {len(warnings)}")


def demo_validation_report():
    """演示验证报告"""
    print("\n" + "=" * 80)
    print("📊 演示3: 验证报告")
    print("=" * 80)
    
    validator = ConfigValidator(Config)
    validator.validate_all()
    
    report = validator.get_validation_report()
    
    print(f"\n验证状态: {'✅ 有效' if report['valid'] else '❌ 无效'}")
    print(f"总错误数: {report['total_errors']}")
    print(f"总警告数: {report['total_warnings']}")
    
    print("\n配置摘要:")
    for key, value in report['config_summary'].items():
        print(f"   {key}: {value}")
    
    if report['errors']:
        print("\n错误列表:")
        for error in report['errors']:
            print(f"   {error}")
    
    if report['warnings']:
        print("\n警告列表:")
        for warning in report['warnings']:
            print(f"   {warning}")


def demo_range_validation():
    """演示范围验证"""
    print("\n" + "=" * 80)
    print("📏 演示4: 范围验证")
    print("=" * 80)
    
    # 创建配置类测试不同范围
    class RangeTestConfig:
        BINANCE_API_KEY = "test_key"
        BINANCE_API_SECRET = "test_secret"
        DISCORD_TOKEN = ""
        
        # 测试边界值
        MIN_CONFIDENCE = 0.0  # ✅ 下界
        MIN_WIN_PROBABILITY = 1.0  # ✅ 上界
        MIN_RR_RATIO = 0.8
        MAX_RR_RATIO = 5.0
        
        MAX_CONCURRENT_ORDERS = 1  # ✅ 下界
        CYCLE_INTERVAL = 3600  # ✅ 上界
        
        MAX_TOTAL_BUDGET_RATIO = 0.9
        MAX_SINGLE_POSITION_RATIO = 0.5
        MAX_TOTAL_MARGIN_RATIO = 0.9
        EQUITY_USAGE_RATIO = 0.8
        MIN_NOTIONAL_VALUE = 5.0
        MIN_STOP_DISTANCE_PCT = 0.003
        RISK_KILL_THRESHOLD = 0.99
        MIN_LEVERAGE = 0.5
        
        EMA_FAST = 20
        EMA_SLOW = 50
        RSI_PERIOD = 14
        RSI_OVERBOUGHT = 70
        RSI_OVERSOLD = 30
        ATR_PERIOD = 14
        ATR_MULTIPLIER = 2.0
        ADX_PERIOD = 14
        ADX_TREND_THRESHOLD = 20.0
        ADX_HARD_REJECT_THRESHOLD = 5.0
        ADX_WEAK_TREND_THRESHOLD = 10.0
        
        SCAN_INTERVAL = 60
        POSITION_MONITOR_INTERVAL = 60
        VIRTUAL_POSITION_CYCLE_INTERVAL = 10
        
        WEBSOCKET_SYMBOL_LIMIT = 200
        WEBSOCKET_SHARD_SIZE = 50
        WEBSOCKET_HEARTBEAT_TIMEOUT = 30
        
        DATA_DIR = "data"
        LOG_FILE = "data/logs/trading_bot.log"
        
        BOOTSTRAP_TRADE_LIMIT = 50
        BOOTSTRAP_MIN_WIN_PROBABILITY = 0.2
        BOOTSTRAP_MIN_CONFIDENCE = 0.25
        BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD = 0.25
        SIGNAL_QUALITY_THRESHOLD = 0.40
        
        CROSS_MARGIN_PROTECTOR_THRESHOLD = 0.85
    
    valid, errors, warnings = validate_config(RangeTestConfig)
    
    print(f"边界值测试: {'✅ 通过' if valid else '❌ 失败'}")
    print(f"错误数: {len(errors)}")
    print(f"警告数: {len(warnings)}")


def demo_dependency_validation():
    """演示依赖关系验证"""
    print("\n" + "=" * 80)
    print("🔗 演示5: 依赖关系验证")
    print("=" * 80)
    
    # Bootstrap阈值应该低于正常阈值
    class DependencyTestConfig:
        BINANCE_API_KEY = "test_key"
        BINANCE_API_SECRET = "test_secret"
        DISCORD_TOKEN = ""
        
        MIN_CONFIDENCE = 0.40
        MIN_WIN_PROBABILITY = 0.45
        MIN_RR_RATIO = 0.8
        MAX_RR_RATIO = 5.0
        
        MAX_CONCURRENT_ORDERS = 5
        CYCLE_INTERVAL = 60
        
        MAX_TOTAL_BUDGET_RATIO = 0.9
        MAX_SINGLE_POSITION_RATIO = 0.5
        MAX_TOTAL_MARGIN_RATIO = 0.9
        EQUITY_USAGE_RATIO = 0.8
        MIN_NOTIONAL_VALUE = 5.0
        MIN_STOP_DISTANCE_PCT = 0.003
        RISK_KILL_THRESHOLD = 0.99
        MIN_LEVERAGE = 0.5
        
        EMA_FAST = 20
        EMA_SLOW = 50
        RSI_PERIOD = 14
        RSI_OVERBOUGHT = 70
        RSI_OVERSOLD = 30
        ATR_PERIOD = 14
        ATR_MULTIPLIER = 2.0
        ADX_PERIOD = 14
        ADX_TREND_THRESHOLD = 20.0
        ADX_HARD_REJECT_THRESHOLD = 5.0
        ADX_WEAK_TREND_THRESHOLD = 10.0
        
        SCAN_INTERVAL = 60
        POSITION_MONITOR_INTERVAL = 60
        VIRTUAL_POSITION_CYCLE_INTERVAL = 10
        
        WEBSOCKET_SYMBOL_LIMIT = 200
        WEBSOCKET_SHARD_SIZE = 50
        WEBSOCKET_HEARTBEAT_TIMEOUT = 30
        
        DATA_DIR = "data"
        LOG_FILE = "data/logs/trading_bot.log"
        
        # ✅ Bootstrap阈值低于正常阈值
        BOOTSTRAP_TRADE_LIMIT = 50
        BOOTSTRAP_MIN_WIN_PROBABILITY = 0.20  # < MIN_WIN_PROBABILITY (0.45)
        BOOTSTRAP_MIN_CONFIDENCE = 0.25  # < MIN_CONFIDENCE (0.40)
        BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD = 0.25  # < SIGNAL_QUALITY_THRESHOLD (0.40)
        SIGNAL_QUALITY_THRESHOLD = 0.40
        
        CROSS_MARGIN_PROTECTOR_THRESHOLD = 0.85
    
    valid, errors, warnings = validate_config(DependencyTestConfig)
    
    print(f"依赖关系测试: {'✅ 通过' if valid else '❌ 失败'}")
    print(f"错误数: {len(errors)}")
    
    if errors:
        for error in errors:
            print(f"   {error}")


def main():
    """运行所有演示"""
    print("\n" + "🚀" * 40)
    print("ConfigValidator 功能演示")
    print("🚀" * 40)
    
    # 演示1: 有效配置
    demo_valid_config()
    
    # 演示2: 无效配置
    demo_invalid_config()
    
    # 演示3: 验证报告
    demo_validation_report()
    
    # 演示4: 范围验证
    demo_range_validation()
    
    # 演示5: 依赖关系验证
    demo_dependency_validation()
    
    print("\n" + "✅" * 40)
    print("所有演示完成！")
    print("✅" * 40 + "\n")


if __name__ == "__main__":
    main()
