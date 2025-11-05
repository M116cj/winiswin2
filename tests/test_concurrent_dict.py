"""
安全测试套件 - ConcurrentDictManager模块
验证并发字典管理器的线程安全和LRU功能
"""

import unittest
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from src.core.concurrent_dict_manager import ConcurrentDictManager


class TestConcurrentDictManager(unittest.TestCase):
    """ConcurrentDictManager测试套件"""
    
    def setUp(self):
        """测试前设置"""
        self.manager = ConcurrentDictManager(max_size=10, name="TestCache")
    
    def tearDown(self):
        """测试后清理"""
        self.manager.stop()
    
    def test_basic_get_set(self):
        """测试1：基本的get/set操作"""
        self.manager.set("key1", "value1")
        self.assertEqual(self.manager.get("key1"), "value1", "应该能够获取设置的值")
        
        self.assertIsNone(self.manager.get("nonexistent"), "不存在的键应该返回None")
    
    def test_concurrent_writes(self):
        """测试2：并发写入应该保持数据一致性"""
        def write_task(idx):
            for i in range(100):
                self.manager.set(f"key{idx}_{i}", f"value{idx}_{i}")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_task, i) for i in range(10)]
            for future in futures:
                future.result()
        
        total_items = len(self.manager.keys())
        self.assertGreater(total_items, 0, "应该有数据写入")
    
    def test_concurrent_reads(self):
        """测试3：并发读取应该不出错"""
        for i in range(10):
            self.manager.set(f"key{i}", f"value{i}")
        
        def read_task():
            results = []
            for i in range(10):
                value = self.manager.get(f"key{i}")
                results.append(value)
            return results
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_task) for _ in range(10)]
            for future in futures:
                results = future.result()
                self.assertEqual(len(results), 10, "每个线程应该读取10个值")
    
    def test_lru_eviction(self):
        """测试4：LRU淘汰应该按预期工作"""
        manager = ConcurrentDictManager(max_size=5, name="LRUTest")
        
        for i in range(10):
            manager.set(f"key{i}", f"value{i}")
        
        total_items = len(manager.keys())
        self.assertLessEqual(total_items, 5, "应该触发LRU淘汰，保持最多5个项")
        
        self.assertIsNone(manager.get("key0"), "最早的键应该被淘汰")
        self.assertIsNone(manager.get("key1"), "最早的键应该被淘汰")
        
        manager.stop()
    
    def test_contains(self):
        """测试5：contains操作应该正确"""
        self.manager.set("key1", "value1")
        
        self.assertTrue(self.manager.contains("key1"), "应该包含已设置的键")
        self.assertFalse(self.manager.contains("nonexistent"), "不应该包含不存在的键")
    
    def test_delete(self):
        """测试6：删除操作应该正确"""
        self.manager.set("key1", "value1")
        self.assertTrue(self.manager.contains("key1"), "删除前应该存在")
        
        self.manager.delete("key1")
        self.assertFalse(self.manager.contains("key1"), "删除后不应该存在")
    
    def test_clear(self):
        """测试7：清空操作应该正确"""
        for i in range(10):
            self.manager.set(f"key{i}", f"value{i}")
        
        self.manager.clear()
        self.assertEqual(len(self.manager.keys()), 0, "清空后应该没有数据")
    
    def test_keys_values_items(self):
        """测试8：keys/values/items方法应该正确"""
        test_data = {"key1": "value1", "key2": "value2", "key3": "value3"}
        for k, v in test_data.items():
            self.manager.set(k, v)
        
        keys = self.manager.keys()
        self.assertEqual(len(keys), 3, "应该有3个键")
        for key in test_data.keys():
            self.assertIn(key, keys, f"应该包含键{key}")
        
        values = self.manager.values()
        self.assertEqual(len(values), 3, "应该有3个值")
        
        items = self.manager.items()
        self.assertEqual(len(items), 3, "应该有3个项")
    
    def test_get_stats(self):
        """测试9：统计信息应该正确"""
        for i in range(10):
            self.manager.set(f"key{i}", f"value{i}")
        
        for i in range(10):
            self.manager.get(f"key{i}")
        
        stats = self.manager.get_stats()
        
        self.assertIn("total_items", stats, "统计应该包含total_items")
        self.assertIn("max_size", stats, "统计应该包含max_size")
        self.assertIn("hits", stats, "统计应该包含hits")
        self.assertIn("misses", stats, "统计应该包含misses")
        
        self.assertGreater(stats["hits"], 0, "应该有缓存命中")
    
    def test_start_stop(self):
        """测试10：启动/停止应该正确管理生命周期"""
        manager = ConcurrentDictManager(max_size=10, name="LifecycleTest")
        
        manager.start()
        self.assertTrue(manager.is_running, "启动后应该处于运行状态")
        
        manager.stop()
        self.assertFalse(manager.is_running, "停止后不应该处于运行状态")
    
    def test_update_multiple(self):
        """测试11：批量更新应该正确"""
        updates = {"key1": "value1", "key2": "value2", "key3": "value3"}
        self.manager.update_multiple(updates)
        
        for key, value in updates.items():
            self.assertEqual(self.manager.get(key), value, f"键{key}应该有正确的值")
    
    def test_thread_safety_stress(self):
        """测试12：压力测试线程安全"""
        def mixed_operations(thread_id):
            for i in range(50):
                self.manager.set(f"key{thread_id}_{i}", f"value{thread_id}_{i}")
                self.manager.get(f"key{thread_id}_{i}")
                if i % 10 == 0:
                    self.manager.delete(f"key{thread_id}_{i}")
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(mixed_operations, i) for i in range(20)]
            for future in futures:
                future.result()
        
        stats = self.manager.get_stats()
        self.assertGreater(stats["total_items"], 0, "压力测试后应该有数据")


class TestConcurrentDictManagerAsync(unittest.IsolatedAsyncioTestCase):
    """ConcurrentDictManager异步测试套件"""
    
    async def test_concurrent_async_operations(self):
        """测试13：异步并发操作应该正确"""
        manager = ConcurrentDictManager(max_size=100, name="AsyncTest")
        manager.start()
        
        async def async_write_task(idx):
            for i in range(50):
                manager.set(f"async_key{idx}_{i}", f"async_value{idx}_{i}")
                await asyncio.sleep(0.001)
        
        tasks = [async_write_task(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        total_items = len(manager.keys())
        self.assertGreater(total_items, 0, "异步并发写入应该成功")
        
        manager.stop()


if __name__ == '__main__':
    unittest.main()
