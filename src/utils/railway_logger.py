"""
Railway日志优化器 - 只显示关键业务指标
职责：过滤冗余日志、聚合重复错误、突出模型学习和盈利状况
Created: 2025-11-12 v4.3
"""

import logging
import time
from typing import Dict, Set, Optional
from collections import defaultdict, deque
from datetime import datetime


class RailwayLogFilter(logging.Filter):
    """
    Railway专用日志过滤器
    
    功能：
    1. 聚合重复错误（相同错误只显示一次+计数）
    2. 过滤DEBUG/INFO噪音（只保留关键INFO）
    3. 突出显示：模型学习、盈利、关键错误
    4. 速率限制（相同日志5秒内只显示1次）
    """
    
    def __init__(self):
        super().__init__()
        
        # 关键字白名单（必须显示的日志）
        self.critical_keywords = {
            # 模型学习相关
            '胜率', '勝率', '信心', '信心度', 'confidence',
            '学习', '學習', 'learning',
            '交易记录', '交易紀錄', 'trade_record',
            '阶段', '階段', 'phase',
            
            # 盈利相关
            '盈利', '盈虧', 'PnL', 'profit',
            '余额', '餘額', 'balance',
            '收益', 'gain', 'loss',
            
            # 交易执行
            '开仓', '開倉', '平仓', '平倉',
            '买入', 'BUY', '卖出', 'SELL',
            '订单', '訂單', 'order',
            
            # 关键错误
            'CRITICAL', 'FATAL',
            '启动', '啟動', 'started', 'initialized',
            '停止', 'stopped', 'shutdown',
        }
        
        # 错误聚合（key: 错误签名, value: (计数, 首次时间, 最后时间)）
        self.error_aggregation: Dict[str, tuple] = {}
        
        # 速率限制（key: 日志签名, value: 最后显示时间）
        self.rate_limit_cache: Dict[str, float] = {}
        self.rate_limit_window = 5.0  # 5秒内相同日志只显示1次
        
        # 重复错误计数器
        self.duplicate_errors: defaultdict = defaultdict(int)
        self.last_error_flush = time.time()
        self.error_flush_interval = 60.0  # 每60秒输出一次聚合统计
        
        # 忽略的噪音日志
        self.noise_patterns = {
            '熔斷器阻斷',  # 熔断器已经聚合显示
            'circuit_breaker',
            '缓存命中',
            'cache hit',
            'ping_interval',
            'pong',
        }
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Returns:
            True = 显示此日志，False = 过滤掉
        """
        # 1. 始终显示 ERROR 和 CRITICAL
        if record.levelno >= logging.ERROR:
            return self._should_show_error(record)
        
        # 2. 检查是否包含关键词
        message = record.getMessage()
        if self._contains_critical_keyword(message):
            return self._apply_rate_limit(record)
        
        # 3. 过滤噪音
        if self._is_noise(message):
            return False
        
        # 4. WARNING级别选择性显示
        if record.levelno == logging.WARNING:
            # 只显示非重复的WARNING
            return self._apply_rate_limit(record)
        
        # 5. INFO级别只显示关键信息
        if record.levelno == logging.INFO:
            # 只显示包含关键词的INFO
            return False
        
        # 6. 过滤所有DEBUG
        return False
    
    def _contains_critical_keyword(self, message: str) -> bool:
        """检查是否包含关键词"""
        message_lower = message.lower()
        for keyword in self.critical_keywords:
            if keyword.lower() in message_lower:
                return True
        return False
    
    def _is_noise(self, message: str) -> bool:
        """检查是否是噪音日志"""
        message_lower = message.lower()
        for pattern in self.noise_patterns:
            if pattern.lower() in message_lower:
                return True
        return False
    
    def _should_show_error(self, record: logging.LogRecord) -> bool:
        """决定是否显示错误日志（聚合重复错误）"""
        message = record.getMessage()
        
        # 生成错误签名（忽略时间戳和数字）
        error_signature = self._get_error_signature(message)
        
        current_time = time.time()
        
        # 检查是否是重复错误
        if error_signature in self.duplicate_errors:
            self.duplicate_errors[error_signature] += 1
            
            # 每60秒输出一次聚合统计
            if current_time - self.last_error_flush > self.error_flush_interval:
                self._flush_error_statistics()
                return True  # 显示聚合统计
            
            return False  # 重复错误不显示
        else:
            # 首次出现的错误
            self.duplicate_errors[error_signature] = 1
            return True
    
    def _get_error_signature(self, message: str) -> str:
        """生成错误签名（用于聚合）"""
        # 移除时间戳和数字
        import re
        signature = re.sub(r'\d{4}-\d{2}-\d{2}.*?-', '', message)
        signature = re.sub(r'\d+', 'N', signature)
        signature = re.sub(r'失敗\d+次', '失败N次', signature)
        return signature[:200]  # 限制长度
    
    def _apply_rate_limit(self, record: logging.LogRecord) -> bool:
        """应用速率限制"""
        message = record.getMessage()
        signature = str(hash(message[:100]))  # 转换为字符串作为key
        
        current_time = time.time()
        last_shown = self.rate_limit_cache.get(signature, 0.0)
        
        if current_time - last_shown > self.rate_limit_window:
            self.rate_limit_cache[signature] = current_time
            return True
        
        return False
    
    def _flush_error_statistics(self) -> None:
        """输出错误聚合统计"""
        if not self.duplicate_errors:
            return
        
        logger = logging.getLogger('railway.error_stats')
        logger.info("=" * 60)
        logger.info("📊 错误统计（过去60秒）")
        
        # 按出现次数排序
        sorted_errors = sorted(
            self.duplicate_errors.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for error_sig, count in sorted_errors[:10]:  # 只显示top 10
            if count > 1:
                logger.info(f"   ❌ {error_sig[:80]}... (×{count})")
        
        logger.info("=" * 60)
        
        # 重置计数器
        self.duplicate_errors.clear()
        self.last_error_flush = time.time()


class RailwayBusinessLogger:
    """
    Railway业务日志记录器
    
    专注于记录：
    1. 模型学习进度（胜率、信心度、交易记录数）
    2. 系统盈利状况（余额、PnL、仓位）
    3. 关键错误（影响交易的错误）
    """
    
    def __init__(self, name: str = 'railway.business'):
        self.logger = logging.getLogger(name)
        self.last_stats_time = time.time()
        self.stats_interval = 300.0  # 5分钟输出一次统计
    
    def log_model_learning(
        self,
        win_rate: float,
        confidence: float,
        total_trades: int,
        phase: int
    ) -> None:
        """记录模型学习状况"""
        self.logger.info(
            f"🤖 模型学习 | "
            f"胜率: {win_rate:.1f}% | "
            f"信心: {confidence:.1f}% | "
            f"交易数: {total_trades} | "
            f"阶段: {phase}"
        )
    
    def log_trading_performance(
        self,
        balance: float,
        unrealized_pnl: float,
        position_count: int
    ) -> None:
        """记录交易表现"""
        self.logger.info(
            f"💰 盈利状况 | "
            f"余额: {balance:.2f} USDT | "
            f"未实现盈亏: {unrealized_pnl:+.2f} USDT | "
            f"持仓: {position_count}"
        )
    
    def log_critical_error(self, error_type: str, details: str) -> None:
        """记录关键错误"""
        self.logger.error(
            f"🚨 关键错误 | "
            f"类型: {error_type} | "
            f"详情: {details}"
        )
    
    def log_trade_execution(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        reason: str
    ) -> None:
        """记录交易执行"""
        self.logger.info(
            f"📈 交易执行 | "
            f"{symbol} {side} {quantity} @ {price:.4f} | "
            f"原因: {reason}"
        )
    
    def should_log_stats(self) -> bool:
        """检查是否应该输出统计信息"""
        current_time = time.time()
        if current_time - self.last_stats_time > self.stats_interval:
            self.last_stats_time = current_time
            return True
        return False


def setup_railway_logging() -> RailwayBusinessLogger:
    """
    设置Railway优化的日志系统
    
    配置：
    1. 添加RailwayLogFilter到根logger
    2. 只保留关键日志
    3. 减少噪音
    """
    # 获取根logger
    root_logger = logging.getLogger()
    
    # 添加Railway过滤器
    railway_filter = RailwayLogFilter()
    for handler in root_logger.handlers:
        handler.addFilter(railway_filter)
    
    # 设置日志级别（只显示INFO及以上）
    root_logger.setLevel(logging.INFO)
    
    # 创建业务日志记录器
    business_logger = RailwayBusinessLogger()
    
    logging.info("✅ Railway日志系统已优化")
    logging.info("   🎯 只显示: 模型学习/盈利/关键错误")
    logging.info("   🔇 已过滤: DEBUG/重复错误/噪音")
    
    return business_logger
