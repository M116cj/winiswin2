"""
安全测试套件 - SmartLogger模块
验证智能日志记录器的速率限制和聚合功能
"""

import unittest
import time
import logging
from src.utils.smart_logger import SmartLogger, create_smart_logger


class TestSmartLogger(unittest.TestCase):
    """SmartLogger测试套件"""
    
    def setUp(self):
        """测试前设置"""
        self.test_logger_name = f"test_logger_{int(time.time() * 1000)}"
    
    def test_rate_limiting(self):
        """测试1：速率限制应该抑制重复消息"""
        logger = create_smart_logger(
            self.test_logger_name,
            rate_limit_window=1.0,
            enable_aggregation=True,
            enable_structured_logging=False
        )
        
        for i in range(100):
            logger.info("重复消息")
        
        stats = logger.get_stats()
        
        self.assertLess(stats["total_logged"], 100,
                       "速率限制应该抑制重复消息")
        self.assertGreater(stats["total_suppressed"], 0,
                          "应该有消息被抑制")
    
    def test_error_never_suppressed(self):
        """测试2：ERROR级别日志不应该被限速"""
        logger = create_smart_logger(
            self.test_logger_name,
            rate_limit_window=1.0,
            enable_aggregation=True,
            enable_structured_logging=False
        )
        
        error_count = 10
        for i in range(error_count):
            logger.error(f"错误消息 {i}")
        
        stats = logger.get_stats()
        
        self.assertGreaterEqual(stats["total_logged"], error_count,
                               "ERROR级别应该全部记录")
    
    def test_aggregation(self):
        """测试3：消息聚合应该正常工作"""
        logger = create_smart_logger(
            self.test_logger_name,
            rate_limit_window=1.0,
            enable_aggregation=True,
            enable_structured_logging=False
        )
        
        for i in range(50):
            logger.info("聚合测试消息")
        
        logger.flush()
        
        stats = logger.get_stats()
        self.assertGreater(stats["total_aggregated"], 0,
                          "应该有消息被聚合")
    
    def test_different_messages_not_suppressed(self):
        """测试4：不同消息不应该被限速"""
        logger = create_smart_logger(
            self.test_logger_name,
            rate_limit_window=1.0,
            enable_aggregation=True,
            enable_structured_logging=False
        )
        
        for i in range(10):
            logger.info(f"消息 {i}")
        
        stats = logger.get_stats()
        
        self.assertGreaterEqual(stats["total_logged"], 10,
                               "不同消息应该全部记录")
    
    def test_flush(self):
        """测试5：flush应该输出聚合报告"""
        logger = create_smart_logger(
            self.test_logger_name,
            rate_limit_window=1.0,
            enable_aggregation=True,
            enable_structured_logging=False
        )
        
        for i in range(20):
            logger.info("重复消息")
        
        logger.flush()
        
        stats = logger.get_stats()
        self.assertEqual(stats["flush_count"], 1, "应该执行了1次flush")
    
    def test_get_stats(self):
        """测试6：统计信息应该完整"""
        logger = create_smart_logger(
            self.test_logger_name,
            rate_limit_window=1.0,
            enable_aggregation=True,
            enable_structured_logging=False
        )
        
        logger.info("测试消息1")
        logger.warning("测试警告")
        logger.error("测试错误")
        
        stats = logger.get_stats()
        
        self.assertIn("total_logged", stats)
        self.assertIn("total_suppressed", stats)
        self.assertIn("total_aggregated", stats)
        self.assertIn("flush_count", stats)
        self.assertIn("rate_limit_efficiency", stats)
        
        self.assertGreaterEqual(stats["total_logged"], 3,
                               "应该至少记录3条消息")
    
    def test_rate_limit_window_expiry(self):
        """测试7：速率限制窗口过期后应该重新记录"""
        logger = create_smart_logger(
            self.test_logger_name,
            rate_limit_window=0.1,
            enable_aggregation=True,
            enable_structured_logging=False
        )
        
        logger.info("消息1")
        time.sleep(0.15)
        logger.info("消息1")
        
        stats = logger.get_stats()
        
        self.assertEqual(stats["total_logged"], 2,
                        "窗口过期后应该重新记录相同消息")
    
    def test_structured_logging(self):
        """测试8：结构化日志应该正常工作"""
        logger = create_smart_logger(
            self.test_logger_name,
            rate_limit_window=1.0,
            enable_aggregation=True,
            enable_structured_logging=True
        )
        
        logger.info("结构化消息", extra={"trade_id": "12345", "symbol": "BTCUSDT"})
        
        stats = logger.get_stats()
        self.assertGreaterEqual(stats["total_logged"], 1, "应该记录结构化消息")
    
    def test_no_aggregation_mode(self):
        """测试9：禁用聚合模式应该正常工作"""
        logger = create_smart_logger(
            self.test_logger_name,
            rate_limit_window=1.0,
            enable_aggregation=False,
            enable_structured_logging=False
        )
        
        for i in range(10):
            logger.info("测试消息")
        
        stats = logger.get_stats()
        
        self.assertEqual(stats["total_aggregated"], 0,
                        "禁用聚合模式不应该聚合消息")
    
    def test_efficiency_calculation(self):
        """测试10：效率计算应该正确"""
        logger = create_smart_logger(
            self.test_logger_name,
            rate_limit_window=1.0,
            enable_aggregation=True,
            enable_structured_logging=False
        )
        
        for i in range(100):
            logger.info("重复消息")
        
        stats = logger.get_stats()
        
        self.assertGreater(stats["rate_limit_efficiency"], 0.0,
                          "应该有速率限制效率")
        self.assertLessEqual(stats["rate_limit_efficiency"], 100.0,
                            "效率不应超过100%")


class TestSmartLoggerIntegration(unittest.TestCase):
    """SmartLogger集成测试"""
    
    def test_create_smart_logger(self):
        """测试11：create_smart_logger应该返回正确类型"""
        logger = create_smart_logger("integration_test")
        
        self.assertIsInstance(logger, SmartLogger,
                             "应该返回SmartLogger实例")
        self.assertTrue(hasattr(logger, "get_stats"),
                       "应该有get_stats方法")
    
    def test_logger_api_compatibility(self):
        """测试12：SmartLogger应该与标准logger API兼容"""
        logger = create_smart_logger("api_test", enable_structured_logging=False)
        
        self.assertTrue(hasattr(logger, "debug"), "应该有debug方法")
        self.assertTrue(hasattr(logger, "info"), "应该有info方法")
        self.assertTrue(hasattr(logger, "warning"), "应该有warning方法")
        self.assertTrue(hasattr(logger, "error"), "应该有error方法")
        self.assertTrue(hasattr(logger, "critical"), "应该有critical方法")
        
        logger.debug("调试消息")
        logger.info("信息消息")
        logger.warning("警告消息")
        logger.error("错误消息")
        logger.critical("严重消息")
        
        stats = logger.get_stats()
        self.assertGreaterEqual(stats["total_logged"], 5,
                               "应该记录所有级别的消息")


if __name__ == '__main__':
    unittest.main()
