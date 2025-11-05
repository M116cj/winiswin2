"""
ConfigValidator - 配置验证系统
🔥 v3.26+ 新增功能：
- 全面验证所有配置参数
- 范围检查（最小值、最大值）
- 类型检查
- 依赖关系验证
- 详细错误报告
"""

import logging
from typing import List, Dict, Any, Tuple, Optional, Callable
from dataclasses import dataclass
import math


@dataclass
class ValidationRule:
    """验证规则"""
    name: str  # 配置项名称
    value: Any  # 配置值
    validator_type: str  # 验证器类型：range, type, dependency, custom
    min_value: Optional[float] = None  # 最小值（用于range）
    max_value: Optional[float] = None  # 最大值（用于range）
    expected_type: Optional[type] = None  # 期望类型（用于type）
    custom_validator: Optional[Callable] = None  # 自定义验证器
    severity: str = "error"  # 严重程度：error, warning
    description: str = ""  # 描述


class ConfigValidator:
    """
    配置验证系统
    
    验证所有关键配置项，确保系统启动前配置正确
    """
    
    def __init__(self, config: Any):
        """
        初始化ConfigValidator
        
        Args:
            config: Config类实例
        """
        self.config = config
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.logger = logging.getLogger(__name__)
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        验证所有配置项
        
        Returns:
            tuple[bool, list, list]: (是否有效, 错误列表, 警告列表)
        """
        # 重置错误和警告
        self.errors = []
        self.warnings = []
        
        # 🔥 第1组：API配置验证
        self._validate_api_config()
        
        # 🔥 第2组：交易参数验证
        self._validate_trading_params()
        
        # 🔥 第3组：风险管理参数验证
        self._validate_risk_params()
        
        # 🔥 第4组：技术指标参数验证
        self._validate_indicator_params()
        
        # 🔥 第5组：时间间隔参数验证
        self._validate_interval_params()
        
        # 🔥 第6组：WebSocket参数验证
        self._validate_websocket_params()
        
        # 🔥 第7组：数据库和文件路径验证
        self._validate_data_paths()
        
        # 🔥 第8组：依赖关系验证
        self._validate_dependencies()
        
        # 🔥 第9组：Bootstrap配置验证
        self._validate_bootstrap_config()
        
        # 打印结果
        self._print_validation_results()
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _validate_api_config(self):
        """验证API配置"""
        # Binance API密钥
        if not self.config.BINANCE_API_KEY:
            self.errors.append("❌ 缺少 BINANCE_API_KEY 环境变量")
        
        if not self.config.BINANCE_API_SECRET:
            self.errors.append("❌ 缺少 BINANCE_API_SECRET 环境变量")
        
        # Discord（可选）
        if not self.config.DISCORD_TOKEN:
            self.warnings.append("⚠️  未设置 DISCORD_TOKEN - Discord通知将被禁用")
    
    def _validate_trading_params(self):
        """验证交易参数"""
        # MIN_CONFIDENCE (0-1)
        self._validate_range(
            "MIN_CONFIDENCE",
            self.config.MIN_CONFIDENCE,
            0.0, 1.0,
            "最小信心值必须在0-1之间"
        )
        
        # MIN_WIN_PROBABILITY (0-1)
        self._validate_range(
            "MIN_WIN_PROBABILITY",
            self.config.MIN_WIN_PROBABILITY,
            0.0, 1.0,
            "最小胜率必须在0-1之间"
        )
        
        # MIN_RR_RATIO (正数)
        self._validate_range(
            "MIN_RR_RATIO",
            self.config.MIN_RR_RATIO,
            0.0, 10.0,
            "最小风险回报比必须在0-10之间"
        )
        
        # MAX_RR_RATIO (正数)
        self._validate_range(
            "MAX_RR_RATIO",
            self.config.MAX_RR_RATIO,
            0.0, 20.0,
            "最大风险回报比必须在0-20之间"
        )
        
        # MAX_CONCURRENT_ORDERS (正整数)
        self._validate_range(
            "MAX_CONCURRENT_ORDERS",
            self.config.MAX_CONCURRENT_ORDERS,
            1, 50,
            "最大并发订单数必须在1-50之间"
        )
        
        # CYCLE_INTERVAL (正整数)
        self._validate_range(
            "CYCLE_INTERVAL",
            self.config.CYCLE_INTERVAL,
            10, 3600,
            "周期间隔必须在10-3600秒之间"
        )
    
    def _validate_risk_params(self):
        """验证风险管理参数"""
        # MAX_TOTAL_BUDGET_RATIO (0-1)
        self._validate_range(
            "MAX_TOTAL_BUDGET_RATIO",
            self.config.MAX_TOTAL_BUDGET_RATIO,
            0.0, 1.0,
            "最大总预算比例必须在0-1之间"
        )
        
        # MAX_SINGLE_POSITION_RATIO (0-1)
        self._validate_range(
            "MAX_SINGLE_POSITION_RATIO",
            self.config.MAX_SINGLE_POSITION_RATIO,
            0.0, 1.0,
            "最大单仓比例必须在0-1之间"
        )
        
        # MAX_TOTAL_MARGIN_RATIO (0-1)
        self._validate_range(
            "MAX_TOTAL_MARGIN_RATIO",
            self.config.MAX_TOTAL_MARGIN_RATIO,
            0.0, 1.0,
            "最大总保证金比例必须在0-1之间"
        )
        
        # EQUITY_USAGE_RATIO (0-1)
        self._validate_range(
            "EQUITY_USAGE_RATIO",
            self.config.EQUITY_USAGE_RATIO,
            0.0, 1.0,
            "权益使用比例必须在0-1之间"
        )
        
        # MIN_NOTIONAL_VALUE (正数)
        self._validate_range(
            "MIN_NOTIONAL_VALUE",
            self.config.MIN_NOTIONAL_VALUE,
            1.0, 1000.0,
            "最小名义价值必须在1-1000 USDT之间"
        )
        
        # MIN_STOP_DISTANCE_PCT (0-1)
        self._validate_range(
            "MIN_STOP_DISTANCE_PCT",
            self.config.MIN_STOP_DISTANCE_PCT,
            0.0001, 0.1,
            "最小止损距离百分比必须在0.01%-10%之间"
        )
        
        # RISK_KILL_THRESHOLD (0-1)
        self._validate_range(
            "RISK_KILL_THRESHOLD",
            self.config.RISK_KILL_THRESHOLD,
            0.0, 1.0,
            "风险强平阈值必须在0-1之间"
        )
        
        # MIN_LEVERAGE (正数)
        self._validate_range(
            "MIN_LEVERAGE",
            self.config.MIN_LEVERAGE,
            0.1, 10.0,
            "最小杠杆必须在0.1-10之间"
        )
    
    def _validate_indicator_params(self):
        """验证技术指标参数"""
        # EMA_FAST < EMA_SLOW
        if self.config.EMA_FAST >= self.config.EMA_SLOW:
            self.errors.append(
                f"❌ EMA_FAST ({self.config.EMA_FAST}) 必须小于 EMA_SLOW ({self.config.EMA_SLOW})"
            )
        
        # RSI_PERIOD (正整数)
        self._validate_range(
            "RSI_PERIOD",
            self.config.RSI_PERIOD,
            2, 100,
            "RSI周期必须在2-100之间"
        )
        
        # RSI_OVERBOUGHT > RSI_OVERSOLD
        if self.config.RSI_OVERBOUGHT <= self.config.RSI_OVERSOLD:
            self.errors.append(
                f"❌ RSI_OVERBOUGHT ({self.config.RSI_OVERBOUGHT}) 必须大于 RSI_OVERSOLD ({self.config.RSI_OVERSOLD})"
            )
        
        # ATR_PERIOD (正整数)
        self._validate_range(
            "ATR_PERIOD",
            self.config.ATR_PERIOD,
            5, 50,
            "ATR周期必须在5-50之间"
        )
        
        # ATR_MULTIPLIER (正数)
        self._validate_range(
            "ATR_MULTIPLIER",
            self.config.ATR_MULTIPLIER,
            0.5, 10.0,
            "ATR倍数必须在0.5-10之间"
        )
        
        # ADX_PERIOD (正整数)
        self._validate_range(
            "ADX_PERIOD",
            self.config.ADX_PERIOD,
            5, 50,
            "ADX周期必须在5-50之间"
        )
        
        # ADX阈值递增关系
        if hasattr(self.config, 'ADX_HARD_REJECT_THRESHOLD') and \
           hasattr(self.config, 'ADX_WEAK_TREND_THRESHOLD') and \
           hasattr(self.config, 'ADX_TREND_THRESHOLD'):
            if not (self.config.ADX_HARD_REJECT_THRESHOLD < 
                    self.config.ADX_WEAK_TREND_THRESHOLD < 
                    self.config.ADX_TREND_THRESHOLD):
                self.warnings.append(
                    f"⚠️  ADX阈值应该递增: HARD_REJECT ({self.config.ADX_HARD_REJECT_THRESHOLD}) < "
                    f"WEAK_TREND ({self.config.ADX_WEAK_TREND_THRESHOLD}) < "
                    f"TREND ({self.config.ADX_TREND_THRESHOLD})"
                )
    
    def _validate_interval_params(self):
        """验证时间间隔参数"""
        # SCAN_INTERVAL (正整数)
        self._validate_range(
            "SCAN_INTERVAL",
            self.config.SCAN_INTERVAL,
            10, 3600,
            "扫描间隔必须在10-3600秒之间"
        )
        
        # POSITION_MONITOR_INTERVAL (正整数)
        self._validate_range(
            "POSITION_MONITOR_INTERVAL",
            self.config.POSITION_MONITOR_INTERVAL,
            10, 600,
            "仓位监控间隔必须在10-600秒之间"
        )
        
        # VIRTUAL_POSITION_CYCLE_INTERVAL (正整数)
        self._validate_range(
            "VIRTUAL_POSITION_CYCLE_INTERVAL",
            self.config.VIRTUAL_POSITION_CYCLE_INTERVAL,
            5, 300,
            "虚拟仓位周期间隔必须在5-300秒之间"
        )
    
    def _validate_websocket_params(self):
        """验证WebSocket参数"""
        # WEBSOCKET_SYMBOL_LIMIT (正整数)
        self._validate_range(
            "WEBSOCKET_SYMBOL_LIMIT",
            self.config.WEBSOCKET_SYMBOL_LIMIT,
            10, 1000,
            "WebSocket符号限制必须在10-1000之间"
        )
        
        # WEBSOCKET_SHARD_SIZE (正整数)
        self._validate_range(
            "WEBSOCKET_SHARD_SIZE",
            self.config.WEBSOCKET_SHARD_SIZE,
            10, 200,
            "WebSocket分片大小必须在10-200之间"
        )
        
        # WEBSOCKET_HEARTBEAT_TIMEOUT (正整数)
        self._validate_range(
            "WEBSOCKET_HEARTBEAT_TIMEOUT",
            self.config.WEBSOCKET_HEARTBEAT_TIMEOUT,
            5, 300,
            "WebSocket心跳超时必须在5-300秒之间"
        )
        
        # 分片大小应该小于符号限制
        if self.config.WEBSOCKET_SHARD_SIZE > self.config.WEBSOCKET_SYMBOL_LIMIT:
            self.warnings.append(
                f"⚠️  WEBSOCKET_SHARD_SIZE ({self.config.WEBSOCKET_SHARD_SIZE}) "
                f"大于 WEBSOCKET_SYMBOL_LIMIT ({self.config.WEBSOCKET_SYMBOL_LIMIT})"
            )
    
    def _validate_data_paths(self):
        """验证数据路径配置"""
        import os
        
        # 确保数据目录存在
        if not os.path.exists(self.config.DATA_DIR):
            try:
                os.makedirs(self.config.DATA_DIR, exist_ok=True)
                self.warnings.append(f"⚠️  数据目录 {self.config.DATA_DIR} 已自动创建")
            except Exception as e:
                self.errors.append(f"❌ 无法创建数据目录 {self.config.DATA_DIR}: {e}")
        
        # 确保日志目录存在
        log_dir = os.path.dirname(self.config.LOG_FILE)
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
                self.warnings.append(f"⚠️  日志目录 {log_dir} 已自动创建")
            except Exception as e:
                self.errors.append(f"❌ 无法创建日志目录 {log_dir}: {e}")
    
    def _validate_dependencies(self):
        """验证配置项之间的依赖关系"""
        # MIN_RR_RATIO < MAX_RR_RATIO
        if self.config.MIN_RR_RATIO >= self.config.MAX_RR_RATIO:
            self.errors.append(
                f"❌ MIN_RR_RATIO ({self.config.MIN_RR_RATIO}) 必须小于 MAX_RR_RATIO ({self.config.MAX_RR_RATIO})"
            )
        
        # MAX_SINGLE_POSITION_RATIO <= MAX_TOTAL_BUDGET_RATIO
        if self.config.MAX_SINGLE_POSITION_RATIO > self.config.MAX_TOTAL_BUDGET_RATIO:
            self.warnings.append(
                f"⚠️  MAX_SINGLE_POSITION_RATIO ({self.config.MAX_SINGLE_POSITION_RATIO}) "
                f"大于 MAX_TOTAL_BUDGET_RATIO ({self.config.MAX_TOTAL_BUDGET_RATIO})"
            )
        
        # CROSS_MARGIN_PROTECTOR_THRESHOLD < MAX_TOTAL_MARGIN_RATIO
        if hasattr(self.config, 'CROSS_MARGIN_PROTECTOR_THRESHOLD'):
            if self.config.CROSS_MARGIN_PROTECTOR_THRESHOLD >= self.config.MAX_TOTAL_MARGIN_RATIO:
                self.warnings.append(
                    f"⚠️  CROSS_MARGIN_PROTECTOR_THRESHOLD ({self.config.CROSS_MARGIN_PROTECTOR_THRESHOLD}) "
                    f"应小于 MAX_TOTAL_MARGIN_RATIO ({self.config.MAX_TOTAL_MARGIN_RATIO})"
                )
    
    def _validate_bootstrap_config(self):
        """验证Bootstrap配置（引导期配置应该更宽松）"""
        # BOOTSTRAP_MIN_WIN_PROBABILITY <= MIN_WIN_PROBABILITY
        if self.config.BOOTSTRAP_MIN_WIN_PROBABILITY > self.config.MIN_WIN_PROBABILITY:
            self.errors.append(
                f"❌ BOOTSTRAP_MIN_WIN_PROBABILITY ({self.config.BOOTSTRAP_MIN_WIN_PROBABILITY}) "
                f"必须小于等于 MIN_WIN_PROBABILITY ({self.config.MIN_WIN_PROBABILITY})"
            )
        
        # BOOTSTRAP_MIN_CONFIDENCE <= MIN_CONFIDENCE
        if self.config.BOOTSTRAP_MIN_CONFIDENCE > self.config.MIN_CONFIDENCE:
            self.errors.append(
                f"❌ BOOTSTRAP_MIN_CONFIDENCE ({self.config.BOOTSTRAP_MIN_CONFIDENCE}) "
                f"必须小于等于 MIN_CONFIDENCE ({self.config.MIN_CONFIDENCE})"
            )
        
        # BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD <= SIGNAL_QUALITY_THRESHOLD
        if self.config.BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD > self.config.SIGNAL_QUALITY_THRESHOLD:
            self.errors.append(
                f"❌ BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD ({self.config.BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD}) "
                f"必须小于等于 SIGNAL_QUALITY_THRESHOLD ({self.config.SIGNAL_QUALITY_THRESHOLD})"
            )
        
        # BOOTSTRAP_TRADE_LIMIT (合理范围)
        self._validate_range(
            "BOOTSTRAP_TRADE_LIMIT",
            self.config.BOOTSTRAP_TRADE_LIMIT,
            10, 500,
            "Bootstrap交易限制必须在10-500之间"
        )
    
    def _validate_range(
        self,
        name: str,
        value: Any,
        min_val: float,
        max_val: float,
        error_msg: str
    ):
        """
        验证数值范围
        
        Args:
            name: 配置项名称
            value: 配置值
            min_val: 最小值
            max_val: 最大值
            error_msg: 错误消息
        """
        try:
            # 转换为float进行比较
            num_value = float(value)
            
            # 检查NaN或Inf
            if math.isnan(num_value) or math.isinf(num_value):
                self.errors.append(f"❌ {name} 值无效(NaN/Inf): {value}")
                return
            
            # 检查范围
            if num_value < min_val or num_value > max_val:
                self.errors.append(
                    f"❌ {error_msg}: 当前值={value}, 有效范围=[{min_val}, {max_val}]"
                )
        
        except (TypeError, ValueError) as e:
            self.errors.append(f"❌ {name} 类型错误: {value} (期望数值)")
    
    def _print_validation_results(self):
        """打印验证结果"""
        if not self.errors and not self.warnings:
            self.logger.info("=" * 80)
            self.logger.info("✅ 配置验证通过：所有配置项有效")
            self.logger.info("=" * 80)
            return
        
        # 打印错误
        if self.errors:
            self.logger.error("=" * 80)
            self.logger.error("❌ 配置验证失败：发现以下错误")
            self.logger.error("=" * 80)
            for error in self.errors:
                self.logger.error(f"   {error}")
            self.logger.error("=" * 80)
        
        # 打印警告
        if self.warnings:
            self.logger.warning("=" * 80)
            self.logger.warning("⚠️  配置验证警告：发现以下警告")
            self.logger.warning("=" * 80)
            for warning in self.warnings:
                self.logger.warning(f"   {warning}")
            self.logger.warning("=" * 80)
    
    def get_validation_report(self) -> Dict[str, Any]:
        """
        获取验证报告
        
        Returns:
            验证报告字典
        """
        return {
            "valid": len(self.errors) == 0,
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "config_summary": {
                "min_confidence": self.config.MIN_CONFIDENCE,
                "min_win_probability": self.config.MIN_WIN_PROBABILITY,
                "max_concurrent_orders": self.config.MAX_CONCURRENT_ORDERS,
                "trading_enabled": self.config.TRADING_ENABLED,
                "binance_testnet": self.config.BINANCE_TESTNET
            }
        }


def validate_config(config: Any) -> Tuple[bool, List[str], List[str]]:
    """
    便捷函数：验证配置
    
    Args:
        config: Config类实例
    
    Returns:
        tuple[bool, list, list]: (是否有效, 错误列表, 警告列表)
    """
    validator = ConfigValidator(config)
    return validator.validate_all()
