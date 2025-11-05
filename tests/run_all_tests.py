"""
安全测试套件 - 主测试运行器
运行所有Phase 2-3修复的测试
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_config_validator import TestConfigValidator, TestBootstrapValidation, TestRiskManagementValidation
from tests.test_concurrent_dict import TestConcurrentDictManager, TestConcurrentDictManagerAsync
from tests.test_smart_logger import TestSmartLogger, TestSmartLoggerIntegration
from tests.test_optimized_trade_recorder import TestOptimizedTradeRecorder, TestOptimizedTradeRecorderSync


def run_all_tests():
    """运行所有测试套件"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    print("=" * 80)
    print("🧪 SelfLearningTrader 安全测试套件 v3.26+")
    print("=" * 80)
    print()
    
    test_classes = [
        TestConfigValidator,
        TestBootstrapValidation,
        TestRiskManagementValidation,
        TestConcurrentDictManager,
        TestConcurrentDictManagerAsync,
        TestSmartLogger,
        TestSmartLoggerIntegration,
        TestOptimizedTradeRecorder,
        TestOptimizedTradeRecorderSync,
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    print(f"📋 测试套件总数: {len(test_classes)}")
    print(f"📋 测试用例总数: {suite.countTestCases()}")
    print()
    print("🚀 开始运行测试...")
    print("=" * 80)
    print()
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("=" * 80)
    print("📊 测试结果摘要")
    print("=" * 80)
    print(f"✅ 通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ 失败: {len(result.failures)}")
    print(f"🚨 错误: {len(result.errors)}")
    print(f"⏭️  跳过: {len(result.skipped)}")
    print("=" * 80)
    
    if result.wasSuccessful():
        print("🎉 所有测试通过！")
        return 0
    else:
        print("💥 部分测试失败，请检查上述错误信息")
        return 1


def run_specific_suite(suite_name):
    """运行特定测试套件"""
    suite_map = {
        "config": [TestConfigValidator, TestBootstrapValidation, TestRiskManagementValidation],
        "concurrent": [TestConcurrentDictManager, TestConcurrentDictManagerAsync],
        "logger": [TestSmartLogger, TestSmartLoggerIntegration],
        "recorder": [TestOptimizedTradeRecorder, TestOptimizedTradeRecorderSync],
    }
    
    if suite_name not in suite_map:
        print(f"❌ 未知测试套件: {suite_name}")
        print(f"可用套件: {', '.join(suite_map.keys())}")
        return 1
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    for test_class in suite_map[suite_name]:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    print(f"🧪 运行测试套件: {suite_name}")
    print(f"📋 测试用例数: {suite.countTestCases()}")
    print()
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        suite_name = sys.argv[1]
        exit_code = run_specific_suite(suite_name)
    else:
        exit_code = run_all_tests()
    
    sys.exit(exit_code)
