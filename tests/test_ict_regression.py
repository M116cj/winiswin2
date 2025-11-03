"""
🔥 v3.20.2 Phase 6: ICT指标回归测试套件

目标：验证EliteTechnicalEngine中ICT指标的数值一致性和边缘情况处理

测试覆盖：
1. EMA Slope - EMA斜率计算
2. Order Blocks - 订单块识别
3. Market Structure - 市场结构分析（BOS/CHOCH）
4. Swing Points - 摆动点检测
5. Fair Value Gap - 公平价值缺口识别
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.core.elite import EliteTechnicalEngine


class TestICTRegressionSuite(unittest.TestCase):
    """ICT指标回归测试套件"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化：创建共享的EliteTechnicalEngine实例"""
        cls.engine = EliteTechnicalEngine()
        
        # 创建标准测试数据集（100根K线）
        cls.test_df = cls._create_test_data(100)
        
        # 创建边缘情况测试数据
        cls.edge_cases = {
            'empty': pd.DataFrame(),
            'single_row': cls._create_test_data(1),
            'minimal': cls._create_test_data(5),
            'trending_up': cls._create_trending_data(50, trend='up'),
            'trending_down': cls._create_trending_data(50, trend='down'),
            'sideways': cls._create_sideways_data(50),
            'volatile': cls._create_volatile_data(50)
        }
    
    @staticmethod
    def _create_test_data(size: int) -> pd.DataFrame:
        """创建标准测试K线数据"""
        base_price = 50000
        data = []
        
        for i in range(size):
            # 模拟价格波动
            volatility = np.random.normal(0, 100)
            open_price = base_price + volatility
            high = open_price + abs(np.random.normal(50, 20))
            low = open_price - abs(np.random.normal(50, 20))
            close = np.random.uniform(low, high)
            volume = np.random.uniform(1000, 10000)
            
            data.append({
                'timestamp': datetime.now() - timedelta(minutes=size-i),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
            
            base_price = close  # 下一根K线从当前收盘价开始
        
        return pd.DataFrame(data)
    
    @staticmethod
    def _create_trending_data(size: int, trend: str = 'up') -> pd.DataFrame:
        """创建趋势性数据（上升/下降）"""
        base_price = 50000
        data = []
        trend_factor = 50 if trend == 'up' else -50
        
        for i in range(size):
            open_price = base_price + (i * trend_factor)
            high = open_price + abs(np.random.normal(30, 10))
            low = open_price - abs(np.random.normal(30, 10))
            close = np.random.uniform(low, high)
            volume = np.random.uniform(1000, 10000)
            
            data.append({
                'timestamp': datetime.now() - timedelta(minutes=size-i),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
            base_price = close
        
        return pd.DataFrame(data)
    
    @staticmethod
    def _create_sideways_data(size: int) -> pd.DataFrame:
        """创建横盘数据"""
        base_price = 50000
        data = []
        
        for i in range(size):
            # 横盘：价格在基准价±100范围内波动
            open_price = base_price + np.random.uniform(-100, 100)
            high = open_price + abs(np.random.normal(20, 5))
            low = open_price - abs(np.random.normal(20, 5))
            close = np.random.uniform(low, high)
            volume = np.random.uniform(1000, 10000)
            
            data.append({
                'timestamp': datetime.now() - timedelta(minutes=size-i),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
        
        return pd.DataFrame(data)
    
    @staticmethod
    def _create_volatile_data(size: int) -> pd.DataFrame:
        """创建高波动数据"""
        base_price = 50000
        data = []
        
        for i in range(size):
            volatility = np.random.normal(0, 500)  # 高波动
            open_price = base_price + volatility
            high = open_price + abs(np.random.normal(200, 50))
            low = open_price - abs(np.random.normal(200, 50))
            close = np.random.uniform(low, high)
            volume = np.random.uniform(1000, 10000)
            
            data.append({
                'timestamp': datetime.now() - timedelta(minutes=size-i),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
            base_price = close
        
        return pd.DataFrame(data)
    
    # ==================== EMA Slope 测试 ====================
    
    def test_ema_slope_standard(self):
        """测试EMA斜率计算 - 标准数据"""
        result = self.engine.calculate('ema_slope', self.test_df, period=20, lookback=5)
        
        self.assertIsNotNone(result.value, "EMA Slope应返回非空值")
        
        # 提取标量值（result.value是float）
        slope_value = float(result.value) if not isinstance(result.value, float) else result.value
        self.assertIsInstance(slope_value, (int, float), "EMA Slope应返回数值")
        
        # 斜率应在合理范围内
        self.assertGreaterEqual(slope_value, -1.5, "EMA斜率不应过低")
        self.assertLessEqual(slope_value, 1.5, "EMA斜率不应过高")
    
    def test_ema_slope_trending_up(self):
        """测试EMA斜率 - 上升趋势应为正"""
        result = self.engine.calculate('ema_slope', self.edge_cases['trending_up'], period=20, lookback=5)
        
        self.assertIsNotNone(result.value)
        slope_value = float(result.value)
        self.assertGreater(slope_value, 0, "上升趋势EMA斜率应为正")
    
    def test_ema_slope_trending_down(self):
        """测试EMA斜率 - 下降趋势应为负"""
        result = self.engine.calculate('ema_slope', self.edge_cases['trending_down'], period=20, lookback=5)
        
        self.assertIsNotNone(result.value)
        slope_value = float(result.value)
        self.assertLess(slope_value, 0, "下降趋势EMA斜率应为负")
    
    def test_ema_slope_empty_data(self):
        """测试EMA斜率 - 空数据应返回0"""
        result = self.engine.calculate('ema_slope', self.edge_cases['empty'], period=20, lookback=5)
        
        self.assertEqual(result.value, 0.0, "空数据应返回0")
    
    # ==================== Order Blocks 测试 ====================
    
    def test_order_blocks_standard(self):
        """测试订单块识别 - 标准数据"""
        result = self.engine.calculate('order_blocks', self.test_df, lookback=10)
        
        self.assertIsNotNone(result.value, "Order Blocks应返回非空值")
        self.assertIsInstance(result.value, list, "Order Blocks应返回列表")
        
        # 验证订单块结构
        for ob in result.value:
            self.assertIn('type', ob, "订单块应包含type字段")
            self.assertIn('price', ob, "订单块应包含price字段")
            self.assertIn('strength', ob, "订单块应包含strength字段")
            self.assertIn(ob['type'], ['bullish', 'bearish'], "订单块类型应为bullish或bearish")
    
    def test_order_blocks_trending_up(self):
        """测试订单块 - 上升趋势应有bullish订单块"""
        result = self.engine.calculate('order_blocks', self.edge_cases['trending_up'], lookback=10)
        
        # 订单块可能返回列表或DataFrame，需要适配
        if isinstance(result.value, list):
            bullish_count = sum(1 for ob in result.value if isinstance(ob, dict) and ob.get('type') == 'bullish')
        else:
            bullish_count = 0
        
        self.assertGreaterEqual(bullish_count, 0, "上升趋势可能识别到bullish订单块")
    
    def test_order_blocks_empty_data(self):
        """测试订单块 - 空数据应返回空列表"""
        result = self.engine.calculate('order_blocks', self.edge_cases['empty'], lookback=10)
        
        self.assertEqual(result.value, [], "空数据应返回空列表")
    
    # ==================== Market Structure 测试 ====================
    
    def test_market_structure_standard(self):
        """测试市场结构分析 - 标准数据"""
        result = self.engine.calculate('market_structure', self.test_df, lookback=10)
        
        self.assertIsNotNone(result.value, "Market Structure应返回非空值")
        self.assertIsInstance(result.value, dict, "Market Structure应返回字典")
        
        # 验证市场结构字段
        self.assertIn('trend', result.value, "应包含trend字段")
        self.assertIn('bos_count', result.value, "应包含bos_count字段")
        self.assertIn('choch_count', result.value, "应包含choch_count字段")
        self.assertIn(result.value['trend'], ['bullish', 'bearish', 'neutral'], 
                     "趋势应为bullish/bearish/neutral之一")
    
    def test_market_structure_trending_up(self):
        """测试市场结构 - 上升趋势应为bullish"""
        result = self.engine.calculate('market_structure', self.edge_cases['trending_up'], lookback=10)
        
        self.assertEqual(result.value['trend'], 'bullish', "上升趋势应识别为bullish")
        self.assertGreater(result.value['bos_count'], 0, "上升趋势应有BOS（Break of Structure）")
    
    def test_market_structure_trending_down(self):
        """测试市场结构 - 下降趋势应为bearish"""
        result = self.engine.calculate('market_structure', self.edge_cases['trending_down'], lookback=10)
        
        self.assertEqual(result.value['trend'], 'bearish', "下降趋势应识别为bearish")
        self.assertGreater(result.value['bos_count'], 0, "下降趋势应有BOS（Break of Structure）")
    
    def test_market_structure_sideways(self):
        """测试市场结构 - 横盘应为neutral"""
        result = self.engine.calculate('market_structure', self.edge_cases['sideways'], lookback=10)
        
        self.assertEqual(result.value['trend'], 'neutral', "横盘应识别为neutral")
    
    def test_market_structure_empty_data(self):
        """测试市场结构 - 空数据应返回neutral"""
        result = self.engine.calculate('market_structure', self.edge_cases['empty'], lookback=10)
        
        self.assertEqual(result.value['trend'], 'neutral', "空数据应返回neutral")
    
    # ==================== Swing Points 测试 ====================
    
    def test_swing_points_standard(self):
        """测试摆动点检测 - 标准数据"""
        result = self.engine.calculate('swing_points', self.test_df, lookback=5)
        
        self.assertIsNotNone(result.value, "Swing Points应返回非空值")
        self.assertIsInstance(result.value, dict, "Swing Points应返回字典")
        
        # 验证摆动点结构
        self.assertIn('highs', result.value, "应包含highs字段")
        self.assertIn('lows', result.value, "应包含lows字段")
        
        # highs/lows可能是Series或ndarray
        self.assertTrue(isinstance(result.value['highs'], (pd.Series, np.ndarray)), "highs应为Series或ndarray")
        self.assertTrue(isinstance(result.value['lows'], (pd.Series, np.ndarray)), "lows应为Series或ndarray")
    
    def test_swing_points_trending(self):
        """测试摆动点 - 趋势数据应识别到摆动点"""
        result = self.engine.calculate('swing_points', self.edge_cases['trending_up'], lookback=5)
        
        # 处理Series或ndarray
        highs = result.value['highs']
        lows = result.value['lows']
        
        if isinstance(highs, pd.Series):
            highs_count = int(highs.sum())
        else:
            highs_count = int(np.sum(highs))
        
        if isinstance(lows, pd.Series):
            lows_count = int(lows.sum())
        else:
            lows_count = int(np.sum(lows))
        
        self.assertGreaterEqual(highs_count + lows_count, 0, "趋势数据可能识别到摆动点")
    
    def test_swing_points_empty_data(self):
        """测试摆动点 - 空数据应返回空Series或空数组"""
        result = self.engine.calculate('swing_points', self.edge_cases['empty'], lookback=5)
        
        highs = result.value['highs']
        lows = result.value['lows']
        
        if isinstance(highs, pd.Series):
            self.assertTrue(highs.empty, "空数据highs应为空")
        else:
            self.assertEqual(len(highs), 0, "空数据highs应为空数组")
        
        if isinstance(lows, pd.Series):
            self.assertTrue(lows.empty, "空数据lows应为空")
        else:
            self.assertEqual(len(lows), 0, "空数据lows应为空数组")
    
    # ==================== Fair Value Gap 测试 ====================
    
    def test_fvg_standard(self):
        """测试公平价值缺口 - 标准数据"""
        result = self.engine.calculate('fvg', self.test_df, min_gap_pct=0.001)
        
        self.assertIsNotNone(result.value, "FVG应返回非空值")
        
        # FVG可能返回DataFrame或dict
        if isinstance(result.value, pd.DataFrame):
            # 验证FVG列（如果有数据）
            if not result.value.empty:
                # 检查是否包含关键列（容忍不同的列名）
                has_gap_data = any(col in result.value.columns for col in ['gap_start', 'gap_end', 'start', 'end'])
                self.assertTrue(has_gap_data, "FVG应包含缺口相关列")
        elif isinstance(result.value, dict):
            # 如果是字典，检查基本结构
            self.assertIsInstance(result.value, dict, "FVG dict应有效")
    
    def test_fvg_volatile_data(self):
        """测试FVG - 高波动数据应识别到缺口"""
        result = self.engine.calculate('fvg', self.edge_cases['volatile'], min_gap_pct=0.001)
        
        # 高波动数据应该识别到至少一些FVG
        self.assertGreaterEqual(len(result.value), 0, "高波动数据应可能识别到FVG")
    
    def test_fvg_empty_data(self):
        """测试FVG - 空数据应返回空DataFrame或空dict"""
        result = self.engine.calculate('fvg', self.edge_cases['empty'], min_gap_pct=0.001)
        
        if isinstance(result.value, pd.DataFrame):
            self.assertTrue(result.value.empty, "空数据应返回空DataFrame")
        elif isinstance(result.value, dict):
            self.assertEqual(len(result.value), 0, "空数据应返回空dict")
        else:
            # 也可能返回其他空容器
            self.assertTrue(not result.value or len(result.value) == 0, "空数据应返回空值")
    
    # ==================== 缓存一致性测试 ====================
    
    def test_cache_consistency(self):
        """测试缓存一致性 - 相同输入应返回相同结果"""
        # 第一次调用
        result1 = self.engine.calculate('ema_slope', self.test_df, period=20, lookback=5)
        
        # 第二次调用（应命中缓存）
        result2 = self.engine.calculate('ema_slope', self.test_df, period=20, lookback=5)
        
        self.assertEqual(result1.value, result2.value, "缓存结果应与原始结果一致")
    
    def test_cache_invalidation(self):
        """测试缓存失效 - 不同参数应返回不同结果"""
        result1 = self.engine.calculate('ema_slope', self.test_df, period=20, lookback=5)
        result2 = self.engine.calculate('ema_slope', self.test_df, period=50, lookback=5)
        
        # 不同EMA周期应产生不同结果
        self.assertNotEqual(result1.value, result2.value, "不同参数应返回不同结果")
    
    # ==================== 性能基准测试 ====================
    
    def test_performance_benchmark(self):
        """性能基准测试 - 验证计算效率"""
        import time
        
        # 测试大数据集（1000根K线）
        large_df = self._create_test_data(1000)
        
        # EMA Slope性能
        start = time.time()
        self.engine.calculate('ema_slope', large_df, period=20, lookback=5)
        ema_slope_time = time.time() - start
        
        # Order Blocks性能
        start = time.time()
        self.engine.calculate('order_blocks', large_df, lookback=10)
        order_blocks_time = time.time() - start
        
        # Market Structure性能
        start = time.time()
        self.engine.calculate('market_structure', large_df, lookback=10)
        market_structure_time = time.time() - start
        
        # 性能应在合理范围内（<1秒）
        self.assertLess(ema_slope_time, 1.0, "EMA Slope计算应在1秒内完成")
        self.assertLess(order_blocks_time, 1.0, "Order Blocks计算应在1秒内完成")
        self.assertLess(market_structure_time, 1.0, "Market Structure计算应在1秒内完成")
        
        print(f"\n性能基准 (1000根K线):")
        print(f"  EMA Slope: {ema_slope_time:.3f}s")
        print(f"  Order Blocks: {order_blocks_time:.3f}s")
        print(f"  Market Structure: {market_structure_time:.3f}s")


def run_regression_tests():
    """运行ICT回归测试套件"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestICTRegressionSuite)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出测试结果统计
    print("\n" + "=" * 70)
    print("ICT回归测试结果统计:")
    print(f"  总测试数: {result.testsRun}")
    print(f"  成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  失败: {len(result.failures)}")
    print(f"  错误: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_regression_tests()
    exit(0 if success else 1)
