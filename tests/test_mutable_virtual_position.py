"""
测试可变VirtualPosition性能和安全性（v3.13.0修复验证）

验证:
1. 高频更新效能 (<100ms for 1000次)
2. 内存效率 (<400 bytes/instance)
3. _entry_direction 安全性
4. signal_id 自动生成
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.data_models import VirtualPosition


def test_high_frequency_updates():
    """测试高频更新效能"""
    print("\n🔥 测试1: 高频更新效能")
    
    pos = VirtualPosition(
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=60000,
        stop_loss=59000,
        take_profit=62000,
        leverage=10,
        entry_timestamp=time.time(),
        signal_id="test_1"
    )
    
    # 模拟 1000 次价格更新
    start_time = time.perf_counter()
    for i in range(1000):
        price = 60000 + (i % 100)  # 模擬價格波動
        pos.update_price(price)
    end_time = time.perf_counter()
    
    duration_ms = (end_time - start_time) * 1000
    print(f"   1000 次更新耗時: {duration_ms:.2f} ms")
    
    assert duration_ms < 100, f"更新太慢: {duration_ms:.2f}ms"
    print(f"   ✅ 性能测试通过 ({duration_ms:.2f}ms < 100ms)")
    
    # 验证记忆体
    obj_size = sys.getsizeof(pos)
    print(f"   对象大小: {obj_size} bytes")
    assert obj_size < 400, f"内存占用过大: {obj_size} bytes"
    print(f"   ✅ 内存测试通过 ({obj_size} bytes < 400 bytes)")


def test_memory_efficiency():
    """测试记忆体效率"""
    print("\n💾 测试2: 内存效率")
    
    positions = []
    for i in range(100):
        pos = VirtualPosition(
            symbol=f"BTC{i}USDT",
            direction="LONG",
            entry_price=60000,
            stop_loss=59000,
            take_profit=62000,
            leverage=10,
            entry_timestamp=time.time(),
            signal_id=f"test_{i}"
        )
        positions.append(pos)
    
    total_size = sum(sys.getsizeof(pos) for pos in positions)
    avg_size = total_size / 100
    print(f"   100个仓位总内存: {total_size} bytes")
    print(f"   平均每个仓位: {avg_size:.0f} bytes")
    
    assert avg_size < 350, f"平均内存过大: {avg_size:.0f} bytes"
    print(f"   ✅ 内存效率测试通过 ({avg_size:.0f} bytes < 350 bytes)")


def test_entry_direction_safety():
    """测试 _entry_direction 安全性"""
    print("\n🛡️ 测试3: _entry_direction 安全性")
    
    pos = VirtualPosition(
        symbol="ETHUSDT",
        direction="SHORT",
        entry_price=3000,
        stop_loss=3100,
        take_profit=2800,
        leverage=5,
        entry_timestamp=time.time(),
        signal_id="test_short"
    )
    
    # 验证 _entry_direction 正确设置
    assert pos._entry_direction == -1, f"SHORT应该是-1，实际: {pos._entry_direction}"
    print(f"   _entry_direction 正确设置: {pos._entry_direction}")
    
    # 模拟方向被意外修改
    original_direction = pos.direction
    pos.direction = "LONG"  # 不应该影响 PnL 计算
    print(f"   意外修改: {original_direction} → {pos.direction}")
    
    # SHORT从3000跌到2900应该盈利
    pos.update_price(2900)
    expected_pnl = ((3000 - 2900) / 3000) * 100 * 5  # ~16.67%
    
    print(f"   计算PnL: {pos.current_pnl:.2f}% (预期: ~{expected_pnl:.2f}%)")
    assert abs(pos.current_pnl - expected_pnl) < 0.01, \
        f"PnL计算错误: {pos.current_pnl:.2f}% vs {expected_pnl:.2f}%"
    
    print(f"   ✅ _entry_direction 安全性测试通过")
    print(f"   （即使direction被修改为{pos.direction}，PnL仍正确使用初始方向{pos._entry_direction}）")


def test_signal_id_generation():
    """测试 signal_id 生成"""
    print("\n🆔 测试4: signal_id 自动生成")
    
    # 测试手动指定signal_id
    pos1 = VirtualPosition(
        symbol="SOLUSDT",
        direction="LONG",
        entry_price=100,
        stop_loss=90,
        take_profit=120,
        leverage=3,
        entry_timestamp=1730000000.123,
        signal_id="custom_id_123"
    )
    
    assert pos1.signal_id == "custom_id_123", f"自定义ID错误: {pos1.signal_id}"
    print(f"   自定义ID: {pos1.signal_id} ✅")
    
    # 测试自动生成（使用Unix时间戳）
    test_timestamp = 1730000001.456
    pos2 = VirtualPosition(
        symbol="ADAUSDT",
        direction="SHORT",
        entry_price=0.5,
        stop_loss=0.6,
        take_profit=0.4,
        leverage=10,
        entry_timestamp=test_timestamp  # 传入数值时间戳
    )
    
    # 应该自动生成为 "ADAUSDT_1730000001"
    expected_id = "ADAUSDT_1730000001"
    assert pos2.signal_id == expected_id, f"自动ID错误: {pos2.signal_id} (预期: {expected_id})"
    print(f"   自动生成ID: {pos2.signal_id} ✅")
    
    # 测试ISO格式时间戳
    pos3 = VirtualPosition(
        symbol="BNBUSDT",
        direction="LONG",
        entry_price=500,
        stop_loss=480,
        take_profit=550,
        leverage=5,
        entry_timestamp="2025-10-27T12:00:00"
    )
    
    print(f"   ISO时间戳生成ID: {pos3.signal_id} ✅")
    assert "BNBUSDT_" in pos3.signal_id
    
    print(f"   ✅ signal_id 生成测试全部通过")


def test_to_dict_includes_signal_id():
    """测试to_dict包含signal_id"""
    print("\n📦 测试5: to_dict() 包含 signal_id")
    
    pos = VirtualPosition(
        symbol="DOGEUSDT",
        direction="LONG",
        entry_price=0.1,
        stop_loss=0.09,
        take_profit=0.12,
        leverage=15,
        signal_id="doge_signal_001"
    )
    
    pos_dict = pos.to_dict()
    
    assert 'signal_id' in pos_dict, "to_dict() 缺少 signal_id"
    assert pos_dict['signal_id'] == "doge_signal_001"
    print(f"   to_dict()['signal_id'] = {pos_dict['signal_id']} ✅")
    print(f"   ✅ to_dict() 序列化测试通过")


if __name__ == "__main__":
    print("="*60)
    print("🧪 VirtualPosition 可变对象测试套件 (v3.13.0)")
    print("="*60)
    
    try:
        test_high_frequency_updates()
        test_memory_efficiency()
        test_entry_direction_safety()
        test_signal_id_generation()
        test_to_dict_includes_signal_id()
        
        print("\n" + "="*60)
        print("🎉 所有 VirtualPosition 测试通过！")
        print("="*60)
        print("\n验证项目:")
        print("  ✅ 高频更新性能 (<100ms for 1000次)")
        print("  ✅ 内存效率 (<350 bytes/instance)")
        print("  ✅ _entry_direction 安全保护")
        print("  ✅ signal_id 自动生成")
        print("  ✅ to_dict() 完整序列化")
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
