"""
安全测试套件 - ConfigValidator模块
验证配置验证器的核心功能和边界条件
"""

import unittest
import logging
from src.utils.config_validator import ConfigValidator, validate_config
from src.config import Config


class MockInvalidConfig:
    """模拟无效配置（MIN > MAX）"""
    BINANCE_API_KEY = "test_api_key"
    BINANCE_API_SECRET = "test_api_secret"
    TRADING_ENABLED = True
    BINANCE_TESTNET = False
    
    MIN_CONFIDENCE = 0.60
    MIN_WIN_PROBABILITY = 0.50
    MIN_RISK_REWARD_RATIO = 1.5
    MAX_CONCURRENT_ORDERS = 5
    
    INITIAL_QUALITY_THRESHOLD = 0.50
    TRADES_EXEMPTION_COUNT = 50
    
    MAX_DRAWDOWN_THRESHOLD = 0.15
    MAX_LEVERAGE = 10
    
    INDICATORS_MACD_FAST = 12
    INDICATORS_MACD_SLOW = 26
    INDICATORS_MACD_SIGNAL = 9
    INDICATORS_RSI_PERIOD = 14
    INDICATORS_BOLLINGER_PERIOD = 20
    INDICATORS_ATR_PERIOD = 14
    INDICATORS_VOLUME_MA_PERIOD = 20
    
    STRATEGY_INTERVALS = ["1h", "15m", "5m"]
    
    WS_RECONNECT_DELAY = 5
    WS_PING_INTERVAL = 30
    WS_MESSAGE_TIMEOUT = 120


class MockMissingAPIConfig:
    """模拟缺少API密钥的配置"""
    BINANCE_API_KEY = ""
    BINANCE_API_SECRET = ""
    TRADING_ENABLED = True
    BINANCE_TESTNET = False
    
    MIN_CONFIDENCE = 0.40
    MIN_WIN_PROBABILITY = 0.50
    MIN_RISK_REWARD_RATIO = 1.5
    MAX_CONCURRENT_ORDERS = 5
    
    INITIAL_QUALITY_THRESHOLD = 0.25
    TRADES_EXEMPTION_COUNT = 50
    
    MAX_DRAWDOWN_THRESHOLD = 0.15
    MAX_LEVERAGE = 10
    
    INDICATORS_MACD_FAST = 12
    INDICATORS_MACD_SLOW = 26
    INDICATORS_MACD_SIGNAL = 9
    INDICATORS_RSI_PERIOD = 14
    INDICATORS_BOLLINGER_PERIOD = 20
    INDICATORS_ATR_PERIOD = 14
    INDICATORS_VOLUME_MA_PERIOD = 20
    
    STRATEGY_INTERVALS = ["1h", "15m", "5m"]
    
    WS_RECONNECT_DELAY = 5
    WS_PING_INTERVAL = 30
    WS_MESSAGE_TIMEOUT = 120


class TestConfigValidator(unittest.TestCase):
    """ConfigValidator测试套件"""
    
    def setUp(self):
        """测试前设置"""
        logging.basicConfig(level=logging.WARNING)
    
    def test_valid_config(self):
        """测试1：有效配置应该通过验证"""
        is_valid, errors, warnings = validate_config(MockValidConfig)
        
        self.assertTrue(is_valid, "有效配置应该通过验证")
        self.assertEqual(len(errors), 0, "有效配置不应该有错误")
    
    def test_invalid_bootstrap_threshold(self):
        """测试2：Bootstrap阈值 > 正常阈值应该失败"""
        is_valid, errors, warnings = validate_config(MockInvalidConfig)
        
        self.assertFalse(is_valid, "Bootstrap阈值 > 正常阈值应该失败")
        self.assertGreater(len(errors), 0, "应该有至少一个错误")
        
        error_found = any("INITIAL_QUALITY_THRESHOLD" in err for err in errors)
        self.assertTrue(error_found, "应该有关于INITIAL_QUALITY_THRESHOLD的错误")
    
    def test_missing_api_keys(self):
        """测试3：缺少API密钥应该失败"""
        is_valid, errors, warnings = validate_config(MockMissingAPIConfig)
        
        self.assertFalse(is_valid, "缺少API密钥应该失败")
        
        error_found = any("BINANCE_API" in err for err in errors)
        self.assertTrue(error_found, "应该有关于BINANCE_API的错误")
    
    def test_out_of_range_confidence(self):
        """测试4：超出范围的置信度应该失败"""
        config = MockValidConfig()
        config.MIN_CONFIDENCE = 1.5
        
        is_valid, errors, warnings = validate_config(config)
        
        self.assertFalse(is_valid, "超出范围的置信度应该失败")
        error_found = any("MIN_CONFIDENCE" in err for err in errors)
        self.assertTrue(error_found, "应该有关于MIN_CONFIDENCE的错误")
    
    def test_negative_leverage(self):
        """测试5：负杠杆应该失败"""
        config = MockValidConfig()
        config.MAX_LEVERAGE = -5
        
        is_valid, errors, warnings = validate_config(config)
        
        self.assertFalse(is_valid, "负杠杆应该失败")
        error_found = any("MAX_LEVERAGE" in err for err in errors)
        self.assertTrue(error_found, "应该有关于MAX_LEVERAGE的错误")
    
    def test_validator_report(self):
        """测试6：验证报告应该包含完整信息"""
        validator = ConfigValidator(MockValidConfig)
        validator.validate_all()
        report = validator.get_validation_report()
        
        self.assertIn("valid", report, "报告应该包含valid字段")
        self.assertIn("total_errors", report, "报告应该包含total_errors字段")
        self.assertIn("total_warnings", report, "报告应该包含total_warnings字段")
        self.assertIn("config_summary", report, "报告应该包含config_summary字段")
        
        self.assertTrue(report["valid"], "有效配置的报告应该显示valid=True")
        self.assertEqual(report["total_errors"], 0, "有效配置不应该有错误")
    
    def test_invalid_indicator_period(self):
        """测试7：无效的指标周期应该失败"""
        config = MockValidConfig()
        config.INDICATORS_RSI_PERIOD = 0
        
        is_valid, errors, warnings = validate_config(config)
        
        self.assertFalse(is_valid, "零周期应该失败")
        error_found = any("RSI" in err for err in errors)
        self.assertTrue(error_found, "应该有关于RSI的错误")
    
    def test_empty_intervals(self):
        """测试8：空的时间周期列表应该失败"""
        config = MockValidConfig()
        config.STRATEGY_INTERVALS = []
        
        is_valid, errors, warnings = validate_config(config)
        
        self.assertFalse(is_valid, "空的时间周期列表应该失败")
        error_found = any("STRATEGY_INTERVALS" in err for err in errors)
        self.assertTrue(error_found, "应该有关于STRATEGY_INTERVALS的错误")
    
    def test_invalid_websocket_timeout(self):
        """测试9：无效的WebSocket超时应该失败"""
        config = MockValidConfig()
        config.WS_MESSAGE_TIMEOUT = -10
        
        is_valid, errors, warnings = validate_config(config)
        
        self.assertFalse(is_valid, "负超时应该失败")
        error_found = any("WS_MESSAGE_TIMEOUT" in err for err in errors)
        self.assertTrue(error_found, "应该有关于WS_MESSAGE_TIMEOUT的错误")
    
    def test_nan_values(self):
        """测试10：NaN值应该失败"""
        config = MockValidConfig()
        config.MIN_CONFIDENCE = float('nan')
        
        is_valid, errors, warnings = validate_config(config)
        
        self.assertFalse(is_valid, "NaN值应该失败")
        error_found = any("MIN_CONFIDENCE" in err for err in errors)
        self.assertTrue(error_found, "应该有关于MIN_CONFIDENCE的错误")
    
    def test_inf_values(self):
        """测试11：Inf值应该失败"""
        config = MockValidConfig()
        config.MAX_LEVERAGE = float('inf')
        
        is_valid, errors, warnings = validate_config(config)
        
        self.assertFalse(is_valid, "Inf值应该失败")
        error_found = any("MAX_LEVERAGE" in err for err in errors)
        self.assertTrue(error_found, "应该有关于MAX_LEVERAGE的错误")


class TestBootstrapValidation(unittest.TestCase):
    """Bootstrap配置验证测试"""
    
    def test_bootstrap_more_permissive(self):
        """测试12：Bootstrap应该比正常模式更宽松"""
        config = MockValidConfig()
        
        self.assertLess(config.INITIAL_QUALITY_THRESHOLD, config.MIN_CONFIDENCE,
                       "Bootstrap阈值应该 < 正常阈值")
    
    def test_bootstrap_exemption_count(self):
        """测试13：免责交易数量应该合理"""
        config = MockValidConfig()
        
        self.assertGreater(config.TRADES_EXEMPTION_COUNT, 0,
                          "免责交易数量应该 > 0")
        self.assertLessEqual(config.TRADES_EXEMPTION_COUNT, 100,
                            "免责交易数量应该 <= 100（合理范围）")


class TestRiskManagementValidation(unittest.TestCase):
    """风险管理验证测试"""
    
    def test_max_drawdown_range(self):
        """测试14：最大回撤范围应该合理"""
        config = MockValidConfig()
        
        self.assertGreater(config.MAX_DRAWDOWN_THRESHOLD, 0,
                          "最大回撤应该 > 0")
        self.assertLess(config.MAX_DRAWDOWN_THRESHOLD, 1.0,
                       "最大回撤应该 < 1.0")
    
    def test_risk_reward_ratio(self):
        """测试15：风险回报比应该合理"""
        config = MockValidConfig()
        
        self.assertGreaterEqual(config.MIN_RISK_REWARD_RATIO, 1.0,
                               "风险回报比应该 >= 1.0")


if __name__ == '__main__':
    unittest.main()
