"""
安全测试套件 - OptimizedTradeRecorder模块
验证优化交易记录器的批量写入和异步I/O功能
"""

import unittest
import asyncio
import os
import json
import gzip
from pathlib import Path
from src.managers.optimized_trade_recorder import OptimizedTradeRecorder


class TestOptimizedTradeRecorder(unittest.IsolatedAsyncioTestCase):
    """OptimizedTradeRecorder异步测试套件"""
    
    def setUp(self):
        """测试前设置"""
        self.test_dir = Path("tests/test_data")
        self.test_dir.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """测试后清理"""
        for file in self.test_dir.glob("*"):
            file.unlink()
        self.test_dir.rmdir()
    
    async def test_basic_write(self):
        """测试1：基本写入操作应该正确"""
        filepath = self.test_dir / "test_trades.jsonl"
        recorder = OptimizedTradeRecorder(
            filepath=str(filepath),
            buffer_size=10,
            enable_compression=False
        )
        recorder.start()
        
        trade_data = {
            "trade_id": "test001",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "entry_price": 67000.0,
            "quantity": 0.1
        }
        
        await recorder.write_record(trade_data)
        await recorder.flush()
        await recorder.stop()
        
        self.assertTrue(filepath.exists(), "交易记录文件应该存在")
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1, "应该有1条记录")
            
            record = json.loads(lines[0])
            self.assertEqual(record["trade_id"], "test001", "trade_id应该匹配")
    
    async def test_batch_write(self):
        """测试2：批量写入应该正确"""
        filepath = self.test_dir / "test_batch.jsonl"
        recorder = OptimizedTradeRecorder(
            filepath=str(filepath),
            buffer_size=5,
            enable_compression=False
        )
        recorder.start()
        
        for i in range(20):
            trade_data = {
                "trade_id": f"batch_{i:03d}",
                "symbol": "ETHUSDT",
                "side": "LONG" if i % 2 == 0 else "SHORT",
                "entry_price": 3000.0 + i
            }
            await recorder.write_record(trade_data)
        
        await recorder.flush()
        await recorder.stop()
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 20, "应该有20条记录")
    
    async def test_compression(self):
        """测试3：压缩功能应该正确"""
        filepath = self.test_dir / "test_compressed.jsonl.gz"
        recorder = OptimizedTradeRecorder(
            filepath=str(filepath),
            buffer_size=10,
            enable_compression=True
        )
        recorder.start()
        
        for i in range(10):
            trade_data = {
                "trade_id": f"compressed_{i:03d}",
                "symbol": "BTCUSDT",
                "data": "x" * 1000
            }
            await recorder.write_record(trade_data)
        
        await recorder.flush()
        await recorder.stop()
        
        self.assertTrue(filepath.exists(), "压缩文件应该存在")
        
        with gzip.open(filepath, 'rt') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 10, "应该有10条压缩记录")
    
    async def test_auto_flush(self):
        """测试4：自动flush应该正常工作"""
        filepath = self.test_dir / "test_auto_flush.jsonl"
        recorder = OptimizedTradeRecorder(
            filepath=str(filepath),
            buffer_size=100,
            auto_flush_interval=0.5,
            enable_compression=False
        )
        recorder.start()
        
        for i in range(5):
            await recorder.write_record({"trade_id": f"auto_{i}"})
        
        await asyncio.sleep(1.0)
        
        stats = recorder.get_stats()
        self.assertGreater(stats["flush_count"], 0, "应该有自动flush")
        
        await recorder.stop()
    
    async def test_get_stats(self):
        """测试5：统计信息应该完整"""
        filepath = self.test_dir / "test_stats.jsonl"
        recorder = OptimizedTradeRecorder(
            filepath=str(filepath),
            buffer_size=10,
            enable_compression=False
        )
        recorder.start()
        
        for i in range(25):
            await recorder.write_record({"trade_id": f"stats_{i}"})
        
        await recorder.flush()
        
        stats = recorder.get_stats()
        
        self.assertIn("total_records", stats)
        self.assertIn("total_bytes", stats)
        self.assertIn("buffer_size", stats)
        self.assertIn("flush_count", stats)
        self.assertIn("batch_efficiency", stats)
        
        self.assertEqual(stats["total_records"], 25, "应该有25条记录")
        self.assertGreater(stats["flush_count"], 0, "应该有flush次数")
        
        await recorder.stop()
    
    async def test_concurrent_writes(self):
        """测试6：并发写入应该正确"""
        filepath = self.test_dir / "test_concurrent.jsonl"
        recorder = OptimizedTradeRecorder(
            filepath=str(filepath),
            buffer_size=20,
            enable_compression=False
        )
        recorder.start()
        
        async def write_task(task_id):
            for i in range(10):
                await recorder.write_record({
                    "task_id": task_id,
                    "record_id": i
                })
        
        tasks = [write_task(tid) for tid in range(10)]
        await asyncio.gather(*tasks)
        
        await recorder.flush()
        await recorder.stop()
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 100, "应该有100条并发写入的记录")
    
    async def test_buffer_overflow(self):
        """测试7：缓冲区溢出应该自动flush"""
        filepath = self.test_dir / "test_overflow.jsonl"
        recorder = OptimizedTradeRecorder(
            filepath=str(filepath),
            buffer_size=5,
            enable_compression=False
        )
        recorder.start()
        
        for i in range(12):
            await recorder.write_record({"trade_id": f"overflow_{i}"})
        
        stats = recorder.get_stats()
        
        self.assertGreaterEqual(stats["flush_count"], 2,
                               "缓冲区溢出应该触发至少2次flush")
        
        await recorder.stop()
    
    async def test_stop_flushes_buffer(self):
        """测试8：stop应该flush剩余缓冲"""
        filepath = self.test_dir / "test_stop_flush.jsonl"
        recorder = OptimizedTradeRecorder(
            filepath=str(filepath),
            buffer_size=100,
            enable_compression=False
        )
        recorder.start()
        
        for i in range(7):
            await recorder.write_record({"trade_id": f"stop_{i}"})
        
        await recorder.stop()
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 7,
                           "stop应该flush所有剩余记录")
    
    async def test_efficiency_calculation(self):
        """测试9：批量效率计算应该正确"""
        filepath = self.test_dir / "test_efficiency.jsonl"
        recorder = OptimizedTradeRecorder(
            filepath=str(filepath),
            buffer_size=10,
            enable_compression=False
        )
        recorder.start()
        
        for i in range(25):
            await recorder.write_record({"trade_id": f"eff_{i}"})
        
        await recorder.flush()
        
        stats = recorder.get_stats()
        
        expected_efficiency = (25 / (stats["flush_count"] or 1)) / 10 * 100
        self.assertAlmostEqual(stats["batch_efficiency"], expected_efficiency, delta=5.0,
                              msg="批量效率应该接近预期值")
        
        await recorder.stop()
    
    async def test_empty_flush(self):
        """测试10：空flush不应该出错"""
        filepath = self.test_dir / "test_empty_flush.jsonl"
        recorder = OptimizedTradeRecorder(
            filepath=str(filepath),
            buffer_size=10,
            enable_compression=False
        )
        recorder.start()
        
        await recorder.flush()
        
        stats = recorder.get_stats()
        self.assertEqual(stats["total_records"], 0, "空flush不应该有记录")
        
        await recorder.stop()


class TestOptimizedTradeRecorderSync(unittest.TestCase):
    """OptimizedTradeRecorder同步测试"""
    
    def setUp(self):
        """测试前设置"""
        self.test_dir = Path("tests/test_data_sync")
        self.test_dir.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """测试后清理"""
        for file in self.test_dir.glob("*"):
            file.unlink()
        if self.test_dir.exists():
            self.test_dir.rmdir()
    
    def test_lifecycle(self):
        """测试11：生命周期管理应该正确"""
        filepath = self.test_dir / "test_lifecycle.jsonl"
        recorder = OptimizedTradeRecorder(
            filepath=str(filepath),
            buffer_size=10,
            enable_compression=False
        )
        
        self.assertFalse(recorder.is_running, "启动前不应该在运行")
        
        recorder.start()
        self.assertTrue(recorder.is_running, "启动后应该在运行")
        
        asyncio.run(recorder.stop())
        self.assertFalse(recorder.is_running, "停止后不应该在运行")


if __name__ == '__main__':
    unittest.main()
