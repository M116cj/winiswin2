"""
快速验证测试 - Phase 2-3修复核心功能
验证ConfigValidator、ConcurrentDictManager、SmartLogger、OptimizedTradeRecorder
"""

import os
import sys
import time
import asyncio
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_validator():
    """测试1：ConfigValidator基本验证"""
    from src.utils.config_validator import validate_config
    from src.config import Config
    
    print("🧪 测试1：ConfigValidator...")
    
    is_valid, errors, warnings = validate_config(Config)
    
    if is_valid:
        print("   ✅ 配置验证通过")
        return True
    else:
        print(f"   ❌ 配置验证失败: {len(errors)} 个错误")
        for error in errors[:3]:
            print(f"      - {error}")
        return False


def test_concurrent_dict_manager():
    """测试2：ConcurrentDictManager线程安全"""
    from src.core.concurrent_dict_manager import ConcurrentDictManager
    from concurrent.futures import ThreadPoolExecutor
    
    print("🧪 测试2：ConcurrentDictManager...")
    
    manager = ConcurrentDictManager(name="QuickTest", max_size=100)
    
    # 基本操作
    manager.set("key1", "value1")
    if manager.get("key1") != "value1":
        print("   ❌ 基本get/set失败")
        return False
    
    # 并发写入
    def write_task(idx):
        for i in range(50):
            manager.set(f"concurrent_key{idx}_{i}", f"value{idx}_{i}")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(write_task, i) for i in range(5)]
        for future in futures:
            future.result()
    
    stats = manager.get_stats()
    
    # 验证：5个线程各写50条 = 250条，但max_size=100，LRU应保留100条
    if stats["size"] == 100:
        print(f"   ✅ 并发测试通过（{stats['size']} 项，LRU淘汰正常）")
        return True
    else:
        print(f"   ❌ 并发测试失败：预期100项，实际{stats['size']}项")
        return False


def test_smart_logger():
    """测试3：SmartLogger速率限制"""
    from src.utils.smart_logger import create_smart_logger
    
    print("🧪 测试3：SmartLogger...")
    
    logger = create_smart_logger(
        "quick_test",
        rate_limit_window=1.0,
        enable_aggregation=True,
        enable_structured=False
    )
    
    # 发送100条重复消息
    for i in range(100):
        logger.info("重复消息测试")
    
    stats = logger.get_stats()
    
    if stats["rate_limited"] > 0:
        efficiency = stats["rate_limit_efficiency"]
        print(f"   ✅ 速率限制工作（效率: {efficiency:.1f}%）")
        return True
    else:
        print("   ❌ 速率限制未生效")
        return False


async def test_optimized_trade_recorder():
    """测试4：OptimizedTradeRecorder批量写入"""
    from src.managers.optimized_trade_recorder import OptimizedTradeRecorder
    import json
    
    print("🧪 测试4：OptimizedTradeRecorder...")
    
    test_file = tempfile.mktemp(suffix=".jsonl")
    
    recorder = OptimizedTradeRecorder(
        trades_file=test_file,
        buffer_size=10,
        enable_compression=False
    )
    
    # 写入20条记录（使用正确的write_trade方法）
    for i in range(20):
        await recorder.write_trade({
            "trade_id": f"test_{i:03d}",
            "symbol": "BTCUSDT",
            "entry_price": 67000.0 + i,
            "timestamp": time.time()
        })
    
    await recorder.flush()
    
    # 验证文件
    try:
        if os.path.exists(test_file):
            with open(test_file, 'r') as f:
                lines = f.readlines()
                
                # 验证：应该有正好20条记录
                if len(lines) != 20:
                    print(f"   ❌ 记录数不匹配：预期20条，实际{len(lines)}条")
                    os.remove(test_file)
                    return False
                
                # 验证：数据完整性（检查第一条和最后一条）
                import json
                first_record = json.loads(lines[0])
                last_record = json.loads(lines[-1])
                
                if first_record["trade_id"] != "test_000":
                    print(f"   ❌ 第一条记录错误：{first_record['trade_id']}")
                    os.remove(test_file)
                    return False
                
                if last_record["trade_id"] != "test_019":
                    print(f"   ❌ 最后一条记录错误：{last_record['trade_id']}")
                    os.remove(test_file)
                    return False
                
                print(f"   ✅ 批量写入成功（{len(lines)}条记录，数据完整）")
                os.remove(test_file)
                return True
        else:
            print(f"   ❌ 文件未创建")
            return False
    except Exception as e:
        print(f"   ❌ 验证失败: {e}")
        if os.path.exists(test_file):
            os.remove(test_file)
        return False


def run_all_tests():
    """运行所有快速验证测试"""
    print("=" * 80)
    print("🚀 Phase 2-3修复快速验证测试套件")
    print("=" * 80)
    print()
    
    results = []
    
    # 测试1：ConfigValidator
    try:
        results.append(("ConfigValidator", test_config_validator()))
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        results.append(("ConfigValidator", False))
    
    print()
    
    # 测试2：ConcurrentDictManager
    try:
        results.append(("ConcurrentDictManager", test_concurrent_dict_manager()))
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        results.append(("ConcurrentDictManager", False))
    
    print()
    
    # 测试3：SmartLogger
    try:
        results.append(("SmartLogger", test_smart_logger()))
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        results.append(("SmartLogger", False))
    
    print()
    
    # 测试4：OptimizedTradeRecorder
    try:
        result = asyncio.run(test_optimized_trade_recorder())
        results.append(("OptimizedTradeRecorder", result))
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        results.append(("OptimizedTradeRecorder", False))
    
    print()
    print("=" * 80)
    print("📊 测试结果摘要")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("=" * 80)
    print(f"通过: {passed}/{total} ({passed/total*100:.0f}%)")
    print("=" * 80)
    
    return all(result for _, result in results)


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
