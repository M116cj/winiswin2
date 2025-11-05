"""
System Health Monitor v3.29+ - 全面健康监控系统
职责：实时检测各组件状态、及时告警、生成健康报告
"""

import asyncio
import psutil
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态等级"""
    HEALTHY = "healthy"  # 所有正常
    DEGRADED = "degraded"  # 部分降级但可用
    UNHEALTHY = "unhealthy"  # 严重问题
    CRITICAL = "critical"  # 紧急状态


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    component: str
    status: HealthStatus
    message: str
    metrics: Dict
    timestamp: str
    latency_ms: float = 0


class SystemHealthMonitor:
    """
    系统健康监控器 v3.29+
    
    特性：
    1. 分层健康状态（HEALTHY/DEGRADED/UNHEALTHY/CRITICAL）
    2. 监控组件（WebSocket、内存、API、数据库、交易性能、延迟）
    3. 定期健康检查循环（可配置间隔）
    4. 告警触发机制（阈值可配置）
    5. 健康状态摘要和详细报告
    6. 资源使用监控（内存、CPU、线程）
    """
    
    def __init__(
        self,
        check_interval: int = 60,
        alert_threshold: int = 3,
        binance_client=None,
        websocket_manager=None,
        trade_recorder=None
    ):
        """
        初始化健康监控器
        
        Args:
            check_interval: 检查间隔（秒）
            alert_threshold: 告警阈值（连续N次失败触发告警）
            binance_client: Binance客户端
            websocket_manager: WebSocket管理器
            trade_recorder: 交易记录器
        """
        self.check_interval = check_interval
        self.alert_threshold = alert_threshold
        
        # 组件引用
        self.binance_client = binance_client
        self.websocket_manager = websocket_manager
        self.trade_recorder = trade_recorder
        
        # 健康检查历史
        self.check_history: List[HealthCheckResult] = []
        self.failure_counts: Dict[str, int] = {}
        
        # 监控任务
        self.monitoring_task: Optional[asyncio.Task] = None
        self.running = False
        
        # 阈值配置
        self.thresholds = {
            'memory_percent': 85.0,  # 内存使用率
            'cpu_percent': 90.0,  # CPU使用率
            'thread_count': 500,  # 线程数
            'api_latency_ms': 5000,  # API延迟
            'ws_lag_seconds': 60,  # WebSocket滞后
        }
        
        logger.info("=" * 80)
        logger.info("✅ SystemHealthMonitor v3.29+ 初始化完成")
        logger.info(f"   ⏱️  检查间隔: {check_interval}秒")
        logger.info(f"   🚨 告警阈值: 连续{alert_threshold}次失败")
        logger.info("   📊 监控组件: WS/内存/API/DB/交易/延迟")
        logger.info("=" * 80)
    
    async def start_monitoring(self) -> None:
        """启动健康监控"""
        if self.running:
            logger.warning("⚠️ 健康监控已在运行")
            return
        
        self.running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("🏥 健康监控已启动")
    
    async def stop_monitoring(self) -> None:
        """停止健康监控"""
        self.running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
        logger.info("🏥 健康监控已停止")
    
    async def _monitoring_loop(self) -> None:
        """监控主循环"""
        while self.running:
            try:
                # 执行全面健康检查
                await self.perform_full_health_check()
                
                # 等待下一个周期
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"❌ 监控循环错误: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)
    
    async def perform_full_health_check(self) -> Dict:
        """
        执行全面健康检查
        
        Returns:
            健康检查摘要
        """
        start_time = datetime.now()
        results = []
        
        # 1. WebSocket连接健康检查
        ws_result = await self._check_websocket_health()
        results.append(ws_result)
        
        # 2. 内存使用检查
        memory_result = self._check_memory_usage()
        results.append(memory_result)
        
        # 3. API连接性检查
        api_result = await self._check_api_connectivity()
        results.append(api_result)
        
        # 4. 数据库健康检查
        db_result = self._check_database_health()
        results.append(db_result)
        
        # 5. 交易性能检查
        trading_result = self._check_trading_performance()
        results.append(trading_result)
        
        # 6. 延迟指标检查
        latency_result = await self._check_latency_metrics()
        results.append(latency_result)
        
        # 保存到历史
        self.check_history.extend(results)
        
        # 限制历史大小（最多保留100次检查）
        if len(self.check_history) > 600:  # 100次 × 6个组件
            self.check_history = self.check_history[-600:]
        
        # 检查告警
        self._check_alerts(results)
        
        # 生成摘要
        total_time = (datetime.now() - start_time).total_seconds()
        summary = self._generate_summary(results, total_time)
        
        logger.info(
            f"🏥 健康检查完成: {summary['overall_status']} "
            f"({total_time:.2f}秒)"
        )
        
        return summary
    
    async def _check_websocket_health(self) -> HealthCheckResult:
        """检查WebSocket连接健康"""
        start_time = datetime.now()
        
        try:
            if not self.websocket_manager:
                return HealthCheckResult(
                    component="websocket",
                    status=HealthStatus.DEGRADED,
                    message="WebSocket管理器未初始化",
                    metrics={},
                    timestamp=datetime.now().isoformat(),
                    latency_ms=0
                )
            
            # 获取WebSocket统计
            stats = getattr(self.websocket_manager, 'get_stats', lambda: {})()
            
            # 检查连接状态
            connected = stats.get('connected', False)
            lag_seconds = stats.get('time_since_message', 0)
            
            # 判断健康状态
            if not connected:
                status = HealthStatus.CRITICAL
                message = "WebSocket未连接"
            elif lag_seconds > self.thresholds['ws_lag_seconds']:
                status = HealthStatus.UNHEALTHY
                message = f"WebSocket滞后{lag_seconds:.1f}秒"
            else:
                status = HealthStatus.HEALTHY
                message = "WebSocket正常"
            
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            return HealthCheckResult(
                component="websocket",
                status=status,
                message=message,
                metrics={
                    'connected': connected,
                    'lag_seconds': lag_seconds,
                    'reconnect_count': stats.get('reconnect_count', 0)
                },
                timestamp=datetime.now().isoformat(),
                latency_ms=latency
            )
            
        except Exception as e:
            logger.error(f"❌ WebSocket健康检查失败: {e}")
            return HealthCheckResult(
                component="websocket",
                status=HealthStatus.CRITICAL,
                message=f"检查失败: {e}",
                metrics={},
                timestamp=datetime.now().isoformat(),
                latency_ms=0
            )
    
    def _check_memory_usage(self) -> HealthCheckResult:
        """检查内存使用"""
        start_time = datetime.now()
        
        try:
            # 获取系统内存信息
            memory = psutil.virtual_memory()
            process = psutil.Process()
            process_memory = process.memory_info()
            
            memory_percent = memory.percent
            process_memory_mb = process_memory.rss / (1024 * 1024)
            
            # 判断健康状态
            if memory_percent >= self.thresholds['memory_percent']:
                status = HealthStatus.CRITICAL
                message = f"内存使用率{memory_percent:.1f}%（超过阈值）"
            elif memory_percent >= self.thresholds['memory_percent'] * 0.9:
                status = HealthStatus.UNHEALTHY
                message = f"内存使用率{memory_percent:.1f}%（接近阈值）"
            else:
                status = HealthStatus.HEALTHY
                message = f"内存使用率{memory_percent:.1f}%"
            
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            return HealthCheckResult(
                component="memory",
                status=status,
                message=message,
                metrics={
                    'total_memory_gb': memory.total / (1024**3),
                    'available_memory_gb': memory.available / (1024**3),
                    'memory_percent': memory_percent,
                    'process_memory_mb': process_memory_mb
                },
                timestamp=datetime.now().isoformat(),
                latency_ms=latency
            )
            
        except Exception as e:
            logger.error(f"❌ 内存检查失败: {e}")
            return HealthCheckResult(
                component="memory",
                status=HealthStatus.UNHEALTHY,
                message=f"检查失败: {e}",
                metrics={},
                timestamp=datetime.now().isoformat(),
                latency_ms=0
            )
    
    async def _check_api_connectivity(self) -> HealthCheckResult:
        """检查API连接性"""
        start_time = datetime.now()
        
        try:
            if not self.binance_client:
                return HealthCheckResult(
                    component="api",
                    status=HealthStatus.DEGRADED,
                    message="API客户端未初始化",
                    metrics={},
                    timestamp=datetime.now().isoformat(),
                    latency_ms=0
                )
            
            # 测试API连接（ping）
            try:
                await self.binance_client.test_connectivity()
                api_ok = True
            except:
                api_ok = False
            
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            # 判断健康状态
            if not api_ok:
                status = HealthStatus.CRITICAL
                message = "API连接失败"
            elif latency > self.thresholds['api_latency_ms']:
                status = HealthStatus.UNHEALTHY
                message = f"API延迟{latency:.0f}ms（超过阈值）"
            else:
                status = HealthStatus.HEALTHY
                message = f"API正常（{latency:.0f}ms）"
            
            return HealthCheckResult(
                component="api",
                status=status,
                message=message,
                metrics={
                    'connected': api_ok,
                    'latency_ms': latency
                },
                timestamp=datetime.now().isoformat(),
                latency_ms=latency
            )
            
        except Exception as e:
            logger.error(f"❌ API检查失败: {e}")
            return HealthCheckResult(
                component="api",
                status=HealthStatus.CRITICAL,
                message=f"检查失败: {e}",
                metrics={},
                timestamp=datetime.now().isoformat(),
                latency_ms=0
            )
    
    def _check_database_health(self) -> HealthCheckResult:
        """检查数据库健康"""
        start_time = datetime.now()
        
        try:
            if not self.trade_recorder:
                return HealthCheckResult(
                    component="database",
                    status=HealthStatus.DEGRADED,
                    message="交易记录器未初始化",
                    metrics={},
                    timestamp=datetime.now().isoformat(),
                    latency_ms=0
                )
            
            # 获取数据库统计
            stats = getattr(self.trade_recorder, 'get_stats', lambda: {})()
            
            error_rate = stats.get('error_count', 0) / max(stats.get('total_entries', 1), 1)
            
            # 判断健康状态
            if error_rate > 0.1:  # 错误率>10%
                status = HealthStatus.UNHEALTHY
                message = f"数据库错误率{error_rate:.1%}"
            else:
                status = HealthStatus.HEALTHY
                message = "数据库正常"
            
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            return HealthCheckResult(
                component="database",
                status=status,
                message=message,
                metrics=stats,
                timestamp=datetime.now().isoformat(),
                latency_ms=latency
            )
            
        except Exception as e:
            logger.error(f"❌ 数据库检查失败: {e}")
            return HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                message=f"检查失败: {e}",
                metrics={},
                timestamp=datetime.now().isoformat(),
                latency_ms=0
            )
    
    def _check_trading_performance(self) -> HealthCheckResult:
        """检查交易性能"""
        start_time = datetime.now()
        
        try:
            if not self.trade_recorder:
                return HealthCheckResult(
                    component="trading",
                    status=HealthStatus.DEGRADED,
                    message="交易记录器未初始化",
                    metrics={},
                    timestamp=datetime.now().isoformat(),
                    latency_ms=0
                )
            
            # 获取交易统计
            stats = getattr(self.trade_recorder, 'get_stats', lambda: {})()
            
            total_trades = stats.get('total_exits', 0)
            
            # 判断健康状态（简单检查）
            status = HealthStatus.HEALTHY
            message = f"交易系统正常（{total_trades}笔）"
            
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            return HealthCheckResult(
                component="trading",
                status=status,
                message=message,
                metrics=stats,
                timestamp=datetime.now().isoformat(),
                latency_ms=latency
            )
            
        except Exception as e:
            logger.error(f"❌ 交易性能检查失败: {e}")
            return HealthCheckResult(
                component="trading",
                status=HealthStatus.UNHEALTHY,
                message=f"检查失败: {e}",
                metrics={},
                timestamp=datetime.now().isoformat(),
                latency_ms=0
            )
    
    async def _check_latency_metrics(self) -> HealthCheckResult:
        """检查延迟指标"""
        start_time = datetime.now()
        
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 线程数
            process = psutil.Process()
            thread_count = process.num_threads()
            
            # 判断健康状态
            if cpu_percent > self.thresholds['cpu_percent']:
                status = HealthStatus.UNHEALTHY
                message = f"CPU使用率{cpu_percent:.1f}%（超过阈值）"
            elif thread_count > self.thresholds['thread_count']:
                status = HealthStatus.UNHEALTHY
                message = f"线程数{thread_count}（超过阈值）"
            else:
                status = HealthStatus.HEALTHY
                message = "延迟指标正常"
            
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            return HealthCheckResult(
                component="latency",
                status=status,
                message=message,
                metrics={
                    'cpu_percent': cpu_percent,
                    'thread_count': thread_count
                },
                timestamp=datetime.now().isoformat(),
                latency_ms=latency
            )
            
        except Exception as e:
            logger.error(f"❌ 延迟检查失败: {e}")
            return HealthCheckResult(
                component="latency",
                status=HealthStatus.UNHEALTHY,
                message=f"检查失败: {e}",
                metrics={},
                timestamp=datetime.now().isoformat(),
                latency_ms=0
            )
    
    def _check_alerts(self, results: List[HealthCheckResult]) -> None:
        """检查是否需要触发告警"""
        for result in results:
            component = result.component
            
            if result.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
                self.failure_counts[component] = self.failure_counts.get(component, 0) + 1
                
                if self.failure_counts[component] >= self.alert_threshold:
                    self._trigger_alert(result)
            else:
                # 恢复时重置计数器
                self.failure_counts[component] = 0
    
    def _trigger_alert(self, result: HealthCheckResult) -> None:
        """触发告警"""
        logger.critical(
            f"🚨 告警触发: {result.component} - {result.status.value} - {result.message}"
        )
        # 这里可以集成Discord/Email/Webhook等通知方式
    
    def _generate_summary(
        self,
        results: List[HealthCheckResult],
        total_time: float
    ) -> Dict:
        """生成健康检查摘要"""
        status_counts = {}
        for result in results:
            status = result.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # 确定整体状态
        if any(r.status == HealthStatus.CRITICAL for r in results):
            overall_status = "critical"
        elif any(r.status == HealthStatus.UNHEALTHY for r in results):
            overall_status = "unhealthy"
        elif any(r.status == HealthStatus.DEGRADED for r in results):
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        return {
            'overall_status': overall_status,
            'total_checks': len(results),
            'status_breakdown': status_counts,
            'check_duration_seconds': total_time,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_detailed_report(self) -> Dict:
        """获取详细健康报告"""
        if not self.check_history:
            return {'message': '暂无健康检查历史'}
        
        # 按组件分组
        by_component = {}
        for result in self.check_history[-60:]:  # 最近10次检查
            component = result.component
            if component not in by_component:
                by_component[component] = []
            by_component[component].append(asdict(result))
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_checks': len(self.check_history),
            'components': by_component,
            'failure_counts': self.failure_counts
        }
