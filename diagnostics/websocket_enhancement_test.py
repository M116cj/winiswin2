"""
WebSocket增强功能测试
测试DataQualityMonitor、DataGapHandler和AdvancedWebSocketManager
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.core.websocket.data_quality_monitor import DataQualityMonitor
from src.core.websocket.data_gap_handler import DataGapHandler
from src.core.websocket.advanced_feed_manager import AdvancedWebSocketManager
import logging
import asyncio
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_data_quality_monitor():
    """测试数据质量监控器"""
    logger.info("\n" + "=" * 80)
    logger.info("1️⃣ 测试 DataQualityMonitor")
    logger.info("=" * 80)
    
    monitor = DataQualityMonitor()
    
    # 测试1：有效消息
    valid_message = {
        'stream': 'btcusdt@kline_1m',
        'data': {
            't': 1234567890000,
            'k': {
                't': 1234567890000,
                'o': '50000.0',
                'h': '50100.0',
                'l': '49900.0',
                'c': '50050.0',
                'v': '100.5',
                'x': True
            }
        }
    }
    
    result = monitor.validate_message(valid_message)
    logger.info(f"✅ 有效消息验证: {result}")
    assert result == True, "有效消息应该通过验证"
    
    # 测试2：无效消息（缺少字段）
    invalid_message = {
        'stream': 'btcusdt@kline_1m',
        'data': {}
    }
    
    result = monitor.validate_message(invalid_message)
    logger.info(f"✅ 无效消息验证: {result}")
    assert result == False, "无效消息应该被拒绝"
    
    # 测试3：价格异常的消息
    bad_price_message = {
        'stream': 'btcusdt@kline_1m',
        'data': {
            't': 1234567890000,
            'k': {
                't': 1234567890000,
                'o': '50000.0',
                'h': '49000.0',  # 高价低于开盘价（异常）
                'l': '49900.0',
                'c': '50050.0',
                'v': '100.5',
                'x': True
            }
        }
    }
    
    result = monitor.validate_message(bad_price_message)
    logger.info(f"✅ 异常价格消息验证: {result}")
    assert result == False, "价格异常消息应该被拒绝"
    
    # 测试4：连续性检查
    monitor.check_continuity('BTCUSDT', valid_message)
    logger.info(f"✅ 连续性检查完成")
    
    # 测试5：质量报告
    report = monitor.get_quality_report()
    logger.info(f"✅ 质量报告: {report}")
    logger.info(f"   总验证: {report['total_validated']}")
    logger.info(f"   总拒绝: {report['total_rejected']}")
    logger.info(f"   接受率: {report['acceptance_rate']:.1f}%")
    
    logger.info("🎉 DataQualityMonitor 测试完成")
    return True

async def test_data_gap_handler():
    """测试数据缺口处理器"""
    logger.info("\n" + "=" * 80)
    logger.info("2️⃣ 测试 DataGapHandler")
    logger.info("=" * 80)
    
    handler = DataGapHandler()
    
    # 测试1：模拟数据缺口
    test_buffer = {
        'kline_1m': [
            {
                'timestamp': int((datetime.now().timestamp() - 300) * 1000),  # 5分钟前
                'open': 50000.0,
                'high': 50100.0,
                'low': 49900.0,
                'close': 50050.0,
                'volume': 100.5,
                'is_final': True
            }
        ],
        'kline_5m': [],
        'kline_15m': [],
        'kline_1h': [],
        'last_update': datetime.now(),
        'message_count': 10
    }
    
    await handler.handle_gap('BTCUSDT', test_buffer)
    logger.info(f"✅ 数据缺口处理完成")
    
    # 测试2：获取统计信息
    stats = handler.get_gap_statistics()
    logger.info(f"✅ 缺口统计: {stats}")
    logger.info(f"   检测到的缺口: {stats['total_gaps_detected']}")
    logger.info(f"   修复的缺口: {stats['total_gaps_fixed']}")
    
    logger.info("🎉 DataGapHandler 测试完成")
    return True

async def test_advanced_websocket_manager():
    """测试高级WebSocket管理器"""
    logger.info("\n" + "=" * 80)
    logger.info("3️⃣ 测试 AdvancedWebSocketManager")
    logger.info("=" * 80)
    
    # 创建模拟配置
    class MockConfig:
        pass
    
    config = MockConfig()
    manager = AdvancedWebSocketManager(config)
    
    # 测试1：初始化数据缓冲区
    test_symbols = {'BTCUSDT', 'ETHUSDT', 'ADAUSDT'}
    manager.initialize_data_buffers(test_symbols)
    logger.info(f"✅ 数据缓冲区初始化: {len(manager.data_buffers)}个交易对")
    assert len(manager.data_buffers) == 3, "应该有3个交易对缓冲区"
    
    # 测试2：创建包装回调
    async def dummy_callback(data):
        logger.debug(f"收到消息: {data.get('stream')}")
    
    wrapped_callback = manager.create_wrapped_callback(dummy_callback)
    logger.info(f"✅ 包装回调创建完成")
    
    # 测试3：模拟消息处理
    test_message = {
        'stream': 'btcusdt@kline_1m',
        'data': {
            't': int(datetime.now().timestamp() * 1000),
            'k': {
                't': int(datetime.now().timestamp() * 1000),
                'o': '50000.0',
                'h': '50100.0',
                'l': '49900.0',
                'c': '50050.0',
                'v': '100.5',
                'x': True
            }
        }
    }
    
    await wrapped_callback(test_message)
    logger.info(f"✅ 消息处理完成")
    
    # 测试4：获取缓冲区状态
    buffer_status = manager.get_buffer_status()
    logger.info(f"✅ 缓冲区状态: {buffer_status}")
    logger.info(f"   总交易对: {buffer_status['total_symbols']}")
    logger.info(f"   活跃交易对: {buffer_status['active_symbols']}")
    
    # 测试5：获取综合报告
    report = manager.get_comprehensive_report()
    logger.info(f"✅ 综合报告:")
    logger.info(f"   质量: {report['quality']}")
    logger.info(f"   缺口: {report['gaps']}")
    logger.info(f"   缓冲区: {report['buffer_status']}")
    
    # 测试6：获取交易对数据
    data = manager.get_symbol_data('BTCUSDT', '1m')
    logger.info(f"✅ 获取BTCUSDT数据: {len(data)}条K线")
    
    logger.info("🎉 AdvancedWebSocketManager 测试完成")
    return True

async def run_all_tests():
    """运行所有测试"""
    logger.info("=" * 80)
    logger.info("🚀 开始WebSocket增强功能测试")
    logger.info("=" * 80)
    
    try:
        # 测试1：DataQualityMonitor
        result1 = await test_data_quality_monitor()
        
        # 测试2：DataGapHandler
        result2 = await test_data_gap_handler()
        
        # 测试3：AdvancedWebSocketManager
        result3 = await test_advanced_websocket_manager()
        
        if all([result1, result2, result3]):
            logger.info("\n" + "=" * 80)
            logger.info("🎉 所有WebSocket增强功能测试通过 ✅")
            logger.info("=" * 80)
            logger.info("✅ DataQualityMonitor: 通过")
            logger.info("✅ DataGapHandler: 通过")
            logger.info("✅ AdvancedWebSocketManager: 通过")
            logger.info("=" * 80)
            return True
        else:
            logger.error("❌ 部分测试失败")
            return False
            
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        logger.error(f"详细错误:\n{traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
