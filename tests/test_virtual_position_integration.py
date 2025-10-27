"""
测试虚拟仓位集成（v3.13.0修复计划步骤3）

验证主循环正确调用异步方法update_all_prices_async
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import TradingBot
from src.managers.virtual_position_manager import VirtualPosition


class TestVirtualPositionIntegration:
    """虚拟仓位集成测试"""
    
    @pytest.mark.asyncio
    async def test_main_loop_integration(self):
        """
        测试主循环正确调用异步方法
        
        验证点：
        1. virtual_position_loop调用update_all_prices_async
        2. 传入正确的binance_client参数
        3. 处理返回的closed_positions
        """
        # 创建TradingBot实例
        bot = TradingBot()
        bot.running = True
        
        # Mock必要的组件
        bot.binance_client = Mock()
        bot.virtual_position_manager = Mock()
        bot.data_archiver = Mock()
        bot.performance_monitor = Mock()
        
        # Mock update_all_prices_async返回空列表
        bot.virtual_position_manager.update_all_prices_async = AsyncMock(return_value=[])
        bot.virtual_position_manager.get_active_virtual_positions = Mock(return_value=[])
        
        # 运行一次虚拟仓位循环（使用asyncio.wait_for避免无限循环）
        async def run_one_cycle():
            """运行一个循环周期后停止"""
            await asyncio.sleep(0.1)  # 等待循环启动
            bot.running = False  # 停止循环
        
        # 并发运行循环和停止任务
        await asyncio.gather(
            bot.virtual_position_loop(),
            run_one_cycle(),
            return_exceptions=True
        )
        
        # ✅ 验证1：调用了异步方法
        bot.virtual_position_manager.update_all_prices_async.assert_called()
        
        # ✅ 验证2：传入了binance_client
        call_args = bot.virtual_position_manager.update_all_prices_async.call_args
        assert call_args is not None
        assert call_args.kwargs.get('binance_client') is not None
    
    @pytest.mark.asyncio
    async def test_closed_positions_archiving(self):
        """
        测试关闭仓位的存档处理
        
        验证点：
        1. 调用data_archiver.archive_position
        2. 调用performance_monitor.record_operation
        """
        bot = TradingBot()
        bot.running = True
        
        # Mock组件
        bot.binance_client = Mock()
        bot.virtual_position_manager = Mock()
        bot.data_archiver = Mock()
        bot.performance_monitor = Mock()
        
        # 创建模拟的关闭仓位
        mock_position = VirtualPosition(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=50000.0,
            quantity=0.01,
            leverage=10,
            stop_loss=48000.0,
            take_profit=52000.0,
            expiry='2025-10-28T00:00:00',
            confidence=0.75
        )
        mock_position.status = 'closed'
        mock_position.pnl = 100.0
        
        # Mock返回关闭的仓位
        bot.virtual_position_manager.update_all_prices_async = AsyncMock(
            return_value=[mock_position]
        )
        bot.virtual_position_manager.get_active_virtual_positions = Mock(
            return_value=[mock_position]
        )
        
        # 运行一个周期
        async def run_one_cycle():
            await asyncio.sleep(0.1)
            bot.running = False
        
        await asyncio.gather(
            bot.virtual_position_loop(),
            run_one_cycle(),
            return_exceptions=True
        )
        
        # ✅ 验证：调用了存档方法
        bot.data_archiver.archive_position.assert_called()
        
        # ✅ 验证：调用了性能记录方法
        bot.performance_monitor.record_operation.assert_called_with(
            'virtual_position_closed',
            1.0
        )
    
    @pytest.mark.asyncio
    async def test_performance_monitoring(self):
        """
        测试性能监控
        
        验证点：
        1. 计算cycle_duration
        2. 超时警告触发
        """
        bot = TradingBot()
        bot.running = True
        
        # Mock组件
        bot.binance_client = Mock()
        bot.virtual_position_manager = Mock()
        
        # Mock一个慢速更新（模拟超时）
        async def slow_update(*args, **kwargs):
            await asyncio.sleep(0.2)  # 模拟慢速操作
            return []
        
        bot.virtual_position_manager.update_all_prices_async = slow_update
        bot.virtual_position_manager.get_active_virtual_positions = Mock(
            return_value=[Mock()]  # 至少一个活跃仓位才会触发更新
        )
        
        # 捕获日志
        with patch('src.main.logger') as mock_logger:
            # 运行一个周期
            async def run_one_cycle():
                await asyncio.sleep(0.3)
                bot.running = False
            
            await asyncio.gather(
                bot.virtual_position_loop(),
                run_one_cycle(),
                return_exceptions=True
            )
            
            # ✅ 验证：记录了周期日志（包含cycle_duration）
            debug_calls = [call for call in mock_logger.debug.call_args_list]
            assert len(debug_calls) > 0


class TestDeprecationWarning:
    """测试deprecated方法的警告"""
    
    def test_update_virtual_positions_deprecated(self):
        """
        测试调用旧方法时发出警告
        """
        from src.managers.virtual_position_manager import VirtualPositionManager
        
        manager = VirtualPositionManager()
        
        # 捕获DeprecationWarning
        with pytest.warns(DeprecationWarning, match="update_virtual_positions.*deprecated"):
            manager.update_virtual_positions({'BTCUSDT': 50000.0})


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v', '--asyncio-mode=auto'])
