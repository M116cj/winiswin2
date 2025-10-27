"""
测试增量K线缓存（v3.13.0修复计划任务3验证）

验证get_klines_incremental的完整功能
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.data_service import DataService


class TestIncrementalCache:
    """增量K线缓存测试"""
    
    @pytest.fixture
    def data_service(self):
        """创建DataService测试实例"""
        mock_client = Mock()
        mock_client.cache = Mock()
        mock_client.cache.get = Mock(return_value=None)
        mock_client.cache.set = Mock()
        
        service = DataService(mock_client)
        return service
    
    @pytest.mark.asyncio
    async def test_first_fetch_full_data(self, data_service):
        """
        测试首次获取完整数据
        
        验证点：
        1. 缓存未命中时获取完整数据
        2. 正确设置缓存元数据
        """
        # Mock完整数据
        mock_klines = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=100, freq='1H'),
            'open': range(100),
            'high': range(100, 200),
            'low': range(50, 150),
            'close': range(75, 175),
            'volume': range(1000, 1100),
            'close_time': range(1000000, 1000000 + 100)
        })
        
        data_service._fetch_full_klines = AsyncMock(return_value=mock_klines)
        data_service.cache.get = Mock(return_value=None)  # 缓存未命中
        
        # 执行
        result = await data_service.get_klines_incremental('BTCUSDT', '1h', limit=100)
        
        # ✅ 验证1：调用了完整拉取
        data_service._fetch_full_klines.assert_called_once_with('BTCUSDT', '1h', 100)
        
        # ✅ 验证2：设置了缓存
        data_service.cache.set.assert_called_once()
        cache_args = data_service.cache.set.call_args
        assert cache_args[0][0] == 'BTCUSDT_1h'  # cache_key
        assert 'data' in cache_args[0][1]  # 缓存结构
        assert 'timestamp' in cache_args[0][1]
        assert 'last_close_time' in cache_args[0][1]
        
        # ✅ 验证3：返回数据正确
        assert len(result) == 100
    
    @pytest.mark.asyncio
    async def test_incremental_update(self, data_service):
        """
        测试增量更新
        
        验证点：
        1. 缓存命中后只拉取新数据
        2. 正确合并新旧数据
        3. 更新缓存时间戳
        """
        # Mock缓存数据
        cached_data = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=50, freq='1H'),
            'open': range(50),
            'high': range(50, 100),
            'low': range(25, 75),
            'close': range(37, 87),
            'volume': range(500, 550),
            'close_time': range(1000000, 1000050)
        })
        
        cached_value = {
            'data': cached_data,
            'timestamp': time.time() - 400,  # 超过TTL
            'last_close_time': 1000049
        }
        
        # Mock新数据
        new_data = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-03', periods=10, freq='1H'),
            'open': range(50, 60),
            'high': range(100, 110),
            'low': range(75, 85),
            'close': range(87, 97),
            'volume': range(550, 560),
            'close_time': range(1000050, 1000060)
        })
        
        data_service.cache.get = Mock(return_value=cached_value)
        data_service._fetch_klines_since = AsyncMock(return_value=new_data)
        data_service._calculate_volatility = Mock(return_value=0.05)
        
        # 执行
        result = await data_service.get_klines_incremental('BTCUSDT', '1h', limit=100)
        
        # ✅ 验证1：调用了增量拉取
        data_service._fetch_klines_since.assert_called_once_with(
            'BTCUSDT', '1h', 1000049
        )
        
        # ✅ 验证2：合并了数据
        assert len(result) == 60  # 50旧 + 10新
        
        # ✅ 验证3：更新了缓存
        data_service.cache.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_dynamic_ttl_calculation(self, data_service):
        """
        测试动态TTL计算
        
        验证点：
        1. 高波动率 → 短TTL
        2. 低波动率 → 长TTL
        """
        # 高波动率数据
        high_vol_data = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=50, freq='1H'),
            'open': range(50),
            'high': [i * 1.5 for i in range(50, 100)],  # 高波动
            'low': range(25, 75),
            'close': range(37, 87),
            'volume': range(500, 550)
        })
        
        # ✅ 验证高波动率计算
        high_volatility = data_service._calculate_volatility(high_vol_data)
        assert high_volatility > 0.05
        
        # 低波动率数据
        low_vol_data = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=50, freq='1H'),
            'open': range(50),
            'high': [i + 1 for i in range(50, 100)],  # 低波动
            'low': range(25, 75),
            'close': range(37, 87),
            'volume': range(500, 550)
        })
        
        # ✅ 验证低波动率计算
        low_volatility = data_service._calculate_volatility(low_vol_data)
        assert low_volatility < high_volatility
    
    @pytest.mark.asyncio
    async def test_cache_hit_ttl_not_expired(self, data_service):
        """
        测试缓存命中且TTL未过期
        
        验证点：
        1. 直接返回缓存数据
        2. 不调用API
        """
        # Mock缓存数据（TTL未过期）
        cached_data = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=50, freq='1H'),
            'open': range(50),
            'high': range(50, 100),
            'low': range(25, 75),
            'close': range(37, 87),
            'volume': range(500, 550),
            'close_time': range(1000000, 1000050)
        })
        
        cached_value = {
            'data': cached_data,
            'timestamp': time.time() - 50,  # 仅50秒前（远未过期）
            'last_close_time': 1000049
        }
        
        data_service.cache.get = Mock(return_value=cached_value)
        data_service._calculate_volatility = Mock(return_value=0.01)  # 低波动
        data_service._fetch_klines_since = AsyncMock()
        
        # 执行
        result = await data_service.get_klines_incremental('BTCUSDT', '1h', limit=100)
        
        # ✅ 验证：未调用API
        data_service._fetch_klines_since.assert_not_called()
        
        # ✅ 验证：返回缓存数据
        assert len(result) == 50
        pd.testing.assert_frame_equal(result, cached_data)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--asyncio-mode=auto'])
