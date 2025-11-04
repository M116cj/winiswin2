"""
🛡️ v3.23+ DataConsistencyManager - 统一数据一致性管理器

职责：
1. 统一管理WebSocket和REST API数据源
2. 自动检测数据缺失并触发fallback
3. 协调DataQualityMonitor和DataGapHandler
4. 提供健康状态监控接口
5. 集成ExceptionHandler异常处理

设计原则：
- WebSocket优先，REST API作为fallback
- 多层次健康检查（连接/数据/质量）
- 自动数据修复机制
- 统一异常处理
"""

import logging
import asyncio
import time
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from src.core.exception_handler import ExceptionHandler
from src.core.websocket.data_quality_monitor import DataQualityMonitor
from src.core.websocket.data_gap_handler import DataGapHandler

logger = logging.getLogger(__name__)


class DataSourceStatus(Enum):
    """数据源状态"""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class DataSourceType(Enum):
    """数据源类型"""
    WEBSOCKET = "WEBSOCKET"
    REST_API = "REST_API"


@dataclass
class DataHealth:
    """数据健康状态"""
    source: DataSourceType
    status: DataSourceStatus
    last_update: float
    update_count: int
    error_count: int
    latency_ms: float
    quality_score: float
    message: str


@dataclass
class FallbackDecision:
    """Fallback决策"""
    should_fallback: bool
    reason: str
    source: DataSourceType
    estimated_recovery_time: float


class DataConsistencyManager:
    """
    数据一致性管理器
    
    核心功能：
    1. 多层次健康检查（连接/数据/质量）
    2. 智能fallback决策（WebSocket → REST API）
    3. 自动数据修复和缺口填充
    4. 统一异常处理和日志记录
    
    使用场景：
    - WebSocket连接失败或超时
    - 数据缺口超过阈值
    - 数据质量低于标准
    - REST API作为备援数据源
    """
    
    # 健康阈值配置
    WEBSOCKET_TIMEOUT = 60  # WebSocket数据超时（秒）
    DATA_GAP_THRESHOLD = 300  # 数据缺口阈值（秒）
    MIN_QUALITY_SCORE = 0.85  # 最小质量分数
    MAX_CONSECUTIVE_ERRORS = 5  # 最大连续错误次数
    
    # Fallback策略配置
    FALLBACK_COOLDOWN = 60  # Fallback冷却时间（秒）
    REST_RETRY_DELAY = 30  # REST API重试延迟（秒）
    
    def __init__(
        self,
        binance_client: Any = None,
        websocket_manager: Any = None,
        enable_auto_repair: bool = True
    ):
        """
        初始化数据一致性管理器
        
        Args:
            binance_client: Binance客户端（用于REST API fallback）
            websocket_manager: WebSocket管理器
            enable_auto_repair: 是否启用自动数据修复
        """
        self.binance_client = binance_client
        self.websocket_manager = websocket_manager
        self.enable_auto_repair = enable_auto_repair
        
        # 初始化监控组件
        self.quality_monitor = DataQualityMonitor()
        self.gap_handler = DataGapHandler(binance_client)
        
        # 数据源健康状态跟踪
        self.websocket_health: Dict[str, DataHealth] = {}
        self.rest_health: Dict[str, DataHealth] = {}
        
        # Fallback状态跟踪
        self.fallback_active: Dict[str, bool] = {}
        self.last_fallback_time: Dict[str, float] = {}
        
        # 统计信息
        self.stats = {
            'total_fallbacks': 0,
            'successful_fallbacks': 0,
            'failed_fallbacks': 0,
            'data_repairs': 0,
            'quality_alerts': 0,
            'start_time': datetime.now()
        }
        
        logger.info("=" * 80)
        logger.info("✅ DataConsistencyManager 初始化完成")
        logger.info(f"   🔧 自动修复: {'启用' if enable_auto_repair else '禁用'}")
        logger.info(f"   ⏱️  WebSocket超时: {self.WEBSOCKET_TIMEOUT}秒")
        logger.info(f"   📊 数据缺口阈值: {self.DATA_GAP_THRESHOLD}秒")
        logger.info(f"   🎯 最小质量分数: {self.MIN_QUALITY_SCORE:.2%}")
        logger.info("=" * 80)
    
    @ExceptionHandler.log_exceptions
    def process_websocket_message(
        self,
        symbol: str,
        message_data: Dict,
        latency_ms: float = 0
    ):
        """
        🔥 v3.23+ 处理WebSocket消息并更新健康状态
        
        这是WebSocket Manager的主要集成接口。
        对每条消息进行质量验证并更新健康状态。
        
        Args:
            symbol: 交易对
            message_data: WebSocket消息数据
            latency_ms: 网络延迟（毫秒）
        
        Returns:
            消息是否有效
        """
        # 1. 使用DataQualityMonitor验证消息质量
        is_valid = self.quality_monitor.validate_message(message_data)
        
        # 2. 检查数据连续性
        self.quality_monitor.check_continuity(symbol, message_data)
        
        # 3. 更新WebSocket健康状态
        self.update_websocket_health(
            symbol=symbol,
            latency_ms=latency_ms,
            has_error=not is_valid
        )
        
        # 4. 根据质量监控结果更新健康状态
        self._update_health_from_quality_metrics(symbol)
        
        return is_valid
    
    def _update_health_from_quality_metrics(self, symbol: str):
        """
        根据DataQualityMonitor的metrics更新健康状态
        
        Args:
            symbol: 交易对
        """
        if symbol not in self.websocket_health:
            return
        
        health = self.websocket_health[symbol]
        quality_report = self.quality_monitor.get_quality_report()
        
        # 获取质量指标（acceptance_rate是百分比0-100，需转换为比例0-1）
        acceptance_rate_pct = quality_report.get('acceptance_rate', 100)
        acceptance_rate = acceptance_rate_pct / 100  # 转换为0-1比例
        message_gaps = quality_report.get('message_gaps', 0)
        out_of_order = quality_report.get('out_of_order', 0)
        
        # 根据质量指标调整健康分数
        if acceptance_rate < 0.85:  # 接受率低于85%（使用0-1比例）
            health.quality_score *= 0.8
            self.stats['quality_alerts'] += 1
            logger.warning(
                f"⚠️ {symbol} 数据质量警告: 接受率 {acceptance_rate:.1%}"
            )
        
        if message_gaps > 10:  # 消息缺口过多
            health.quality_score *= 0.9
            logger.warning(
                f"⚠️ {symbol} 检测到{message_gaps}个消息缺口"
            )
        
        if out_of_order > 5:  # 乱序消息过多
            health.quality_score *= 0.95
            logger.warning(
                f"⚠️ {symbol} 检测到{out_of_order}条乱序消息"
            )
        
        # 根据最终分数更新状态
        if health.quality_score < self.MIN_QUALITY_SCORE:
            health.status = DataSourceStatus.DEGRADED
            health.message = (
                f"质量分数{health.quality_score:.2%} "
                f"(接受率:{acceptance_rate:.1f}%, 缺口:{message_gaps}, 乱序:{out_of_order})"
            )
    
    @ExceptionHandler.log_exceptions
    def update_websocket_health(
        self,
        symbol: str,
        latency_ms: float = 0,
        has_error: bool = False
    ):
        """
        更新WebSocket健康状态
        
        Args:
            symbol: 交易对
            latency_ms: 网络延迟（毫秒）
            has_error: 是否有错误
        """
        now = time.time()
        
        if symbol not in self.websocket_health:
            self.websocket_health[symbol] = DataHealth(
                source=DataSourceType.WEBSOCKET,
                status=DataSourceStatus.HEALTHY,
                last_update=now,
                update_count=0,
                error_count=0,
                latency_ms=latency_ms,
                quality_score=1.0,
                message="初始化"
            )
        
        health = self.websocket_health[symbol]
        health.last_update = now
        health.update_count += 1
        health.latency_ms = latency_ms
        
        if has_error:
            health.error_count += 1
        
        # 计算质量分数（基于延迟和错误率）
        error_rate = health.error_count / max(health.update_count, 1)
        latency_score = max(0, 1 - (latency_ms / 1000))  # 1秒延迟 = 0分
        health.quality_score = (1 - error_rate) * 0.7 + latency_score * 0.3
        
        # 更新状态
        if health.error_count >= self.MAX_CONSECUTIVE_ERRORS:
            health.status = DataSourceStatus.UNAVAILABLE
            health.message = f"连续错误超过{self.MAX_CONSECUTIVE_ERRORS}次"
        elif health.quality_score < self.MIN_QUALITY_SCORE:
            health.status = DataSourceStatus.DEGRADED
            health.message = f"质量分数低于阈值: {health.quality_score:.2%}"
        else:
            health.status = DataSourceStatus.HEALTHY
            health.message = "运行正常"
            health.error_count = 0  # 重置错误计数
    
    @ExceptionHandler.log_exceptions
    def check_data_freshness(self, symbol: str) -> Optional[FallbackDecision]:
        """
        检查数据新鲜度并决定是否需要fallback
        
        Args:
            symbol: 交易对
        
        Returns:
            Fallback决策，如果不需要fallback则返回None
        """
        health = self.websocket_health.get(symbol)
        if not health:
            return FallbackDecision(
                should_fallback=True,
                reason="无WebSocket数据",
                source=DataSourceType.REST_API,
                estimated_recovery_time=self.REST_RETRY_DELAY
            )
        
        # 检查数据是否过期
        time_since_update = time.time() - health.last_update
        if time_since_update > self.WEBSOCKET_TIMEOUT:
            return FallbackDecision(
                should_fallback=True,
                reason=f"数据超时: {time_since_update:.1f}秒未更新",
                source=DataSourceType.REST_API,
                estimated_recovery_time=self.REST_RETRY_DELAY
            )
        
        # 检查数据质量 - 🔥 v3.23+ 支持DEGRADED状态触发fallback
        if health.status == DataSourceStatus.UNAVAILABLE:
            return FallbackDecision(
                should_fallback=True,
                reason=health.message,
                source=DataSourceType.REST_API,
                estimated_recovery_time=self.REST_RETRY_DELAY
            )
        
        if health.status == DataSourceStatus.DEGRADED:
            return FallbackDecision(
                should_fallback=True,
                reason=f"数据质量降级: {health.message}",
                source=DataSourceType.REST_API,
                estimated_recovery_time=self.REST_RETRY_DELAY
            )
        
        # 检查是否在fallback冷却期
        if symbol in self.last_fallback_time:
            cooldown_remaining = self.FALLBACK_COOLDOWN - (
                time.time() - self.last_fallback_time[symbol]
            )
            if cooldown_remaining > 0:
                logger.debug(
                    f"⏳ {symbol} Fallback冷却中，剩余{cooldown_remaining:.1f}秒"
                )
                return None
        
        return None
    
    @ExceptionHandler.critical_section(max_retries=2, backoff_base=1.0)
    async def execute_fallback(
        self,
        symbol: str,
        data_type: str,
        decision: FallbackDecision
    ) -> Optional[Any]:
        """
        执行fallback操作（WebSocket → REST API）
        
        Args:
            symbol: 交易对
            data_type: 数据类型（kline/price/position等）
            decision: Fallback决策
        
        Returns:
            REST API数据，失败返回None
        """
        self.stats['total_fallbacks'] += 1
        self.last_fallback_time[symbol] = time.time()
        self.fallback_active[symbol] = True
        
        logger.warning(
            f"🔄 {symbol} 启动Fallback: {decision.reason} | "
            f"目标源: {decision.source.value}"
        )
        
        try:
            if not self.binance_client:
                logger.error(f"❌ {symbol} 无Binance客户端，Fallback失败")
                self.stats['failed_fallbacks'] += 1
                return None
            
            # 根据数据类型调用相应的REST API
            data = None
            if data_type == "kline":
                # 获取K线数据
                data = await self._fetch_kline_rest(symbol)
            elif data_type == "price":
                # 获取价格数据
                data = await self._fetch_price_rest(symbol)
            elif data_type == "position":
                # 获取持仓数据
                data = await self._fetch_position_rest(symbol)
            else:
                logger.error(f"❌ {symbol} 不支持的数据类型: {data_type}")
            
            if data:
                self.stats['successful_fallbacks'] += 1
                logger.info(f"✅ {symbol} Fallback成功获取{data_type}数据")
            else:
                self.stats['failed_fallbacks'] += 1
                logger.warning(f"⚠️ {symbol} Fallback未能获取数据")
            
            return data
            
        except Exception as e:
            logger.error(f"❌ {symbol} Fallback执行失败: {e}")
            self.stats['failed_fallbacks'] += 1
            raise
        finally:
            self.fallback_active[symbol] = False
    
    async def _fetch_kline_rest(self, symbol: str) -> Optional[List[Dict]]:
        """
        通过REST API获取K线数据
        
        Args:
            symbol: 交易对
        
        Returns:
            K线数据列表
        """
        try:
            # 获取最近100根1分钟K线
            klines = await self.binance_client.get_klines(
                symbol=symbol,
                interval="1m",
                limit=100
            )
            return klines
        except Exception as e:
            logger.error(f"❌ {symbol} REST API获取K线失败: {e}")
            return None
    
    async def _fetch_price_rest(self, symbol: str) -> Optional[Dict]:
        """
        通过REST API获取价格数据
        
        Args:
            symbol: 交易对
        
        Returns:
            价格数据
        """
        try:
            ticker = await self.binance_client.get_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"❌ {symbol} REST API获取价格失败: {e}")
            return None
    
    async def _fetch_position_rest(self, symbol: str) -> Optional[Dict]:
        """
        通过REST API获取持仓数据
        
        Args:
            symbol: 交易对
        
        Returns:
            持仓数据
        """
        try:
            positions = await self.binance_client.get_position_info_async()
            for pos in positions:
                if pos.get('symbol') == symbol:
                    return pos
            return None
        except Exception as e:
            logger.error(f"❌ {symbol} REST API获取持仓失败: {e}")
            return None
    
    @ExceptionHandler.log_exceptions
    async def auto_repair_data_gaps(
        self,
        symbol: str,
        buffer: Dict
    ) -> bool:
        """
        自动修复数据缺口
        
        Args:
            symbol: 交易对
            buffer: 数据缓冲区
        
        Returns:
            是否成功修复
        """
        if not self.enable_auto_repair:
            logger.debug(f"⚠️ {symbol} 自动修复已禁用，跳过")
            return False
        
        try:
            # 使用DataGapHandler检测和修复缺口
            await self.gap_handler.handle_gap(symbol, buffer)
            self.stats['data_repairs'] += 1
            logger.info(f"✅ {symbol} 数据缺口修复完成")
            return True
        except Exception as e:
            logger.error(f"❌ {symbol} 数据缺口修复失败: {e}")
            return False
    
    def get_health_summary(self) -> Dict:
        """
        获取健康状态摘要
        
        Returns:
            健康状态统计
        """
        total_symbols = len(self.websocket_health)
        healthy = sum(
            1 for h in self.websocket_health.values()
            if h.status == DataSourceStatus.HEALTHY
        )
        degraded = sum(
            1 for h in self.websocket_health.values()
            if h.status == DataSourceStatus.DEGRADED
        )
        unavailable = sum(
            1 for h in self.websocket_health.values()
            if h.status == DataSourceStatus.UNAVAILABLE
        )
        
        active_fallbacks = sum(1 for active in self.fallback_active.values() if active)
        
        # 获取质量监控报告
        quality_report = self.quality_monitor.get_quality_report()
        
        # 获取缺口统计
        gap_stats = self.gap_handler.get_gap_statistics()
        
        return {
            'websocket_health': {
                'total_symbols': total_symbols,
                'healthy': healthy,
                'degraded': degraded,
                'unavailable': unavailable,
                'health_rate': (healthy / total_symbols * 100) if total_symbols > 0 else 0
            },
            'fallback_status': {
                'active_fallbacks': active_fallbacks,
                'total_fallbacks': self.stats['total_fallbacks'],
                'successful_fallbacks': self.stats['successful_fallbacks'],
                'failed_fallbacks': self.stats['failed_fallbacks'],
                'success_rate': (
                    self.stats['successful_fallbacks'] / self.stats['total_fallbacks'] * 100
                    if self.stats['total_fallbacks'] > 0 else 0
                )
            },
            'data_quality': quality_report,
            'data_gaps': gap_stats,
            'data_repairs': self.stats['data_repairs'],
            'uptime_seconds': (datetime.now() - self.stats['start_time']).total_seconds()
        }
    
    def reset_statistics(self):
        """重置所有统计信息"""
        self.stats = {
            'total_fallbacks': 0,
            'successful_fallbacks': 0,
            'failed_fallbacks': 0,
            'data_repairs': 0,
            'quality_alerts': 0,
            'start_time': datetime.now()
        }
        self.quality_monitor.reset_metrics()
        self.gap_handler.reset_statistics()
        logger.info("📊 DataConsistencyManager 统计已重置")
