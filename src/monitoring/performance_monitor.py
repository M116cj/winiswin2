"""
性能監控器（v3.3.7優化版）
職責：系統性能指標追蹤、資源使用監控、瓶頸檢測、實時性能追踪
"""

import psutil
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
import time
from collections import deque

logger = logging.getLogger(__name__)


class OperationTimer:
    """操作計時器上下文管理器"""
    
    def __init__(self, monitor: 'PerformanceMonitor', operation_name: str):
        self.monitor = monitor
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        duration = time.time() - self.start_time
        self.monitor.record_operation(self.operation_name, duration)


class PerformanceMonitor:
    """系統性能監控器（v3.3.7增強版）"""
    
    def __init__(self):
        """初始化性能監控器"""
        self.start_time = time.time()
        
        # 基礎統計
        self.total_signals_generated = 0
        self.total_trades_executed = 0
        self.total_api_calls = 0
        self.total_errors = 0
        
        # ✨ v3.3.7新增：詳細性能追踪
        self.operation_times = deque(maxlen=1000)  # 最近1000次操作
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_latency = 0.0
        self.operation_count = 0
        
        # 操作類型統計
        self.operation_stats = {}  # {operation_name: [durations]}
    
    def get_system_metrics(self) -> Dict:
        """
        獲取系統資源使用指標
        
        Returns:
            Dict: 系統指標
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024 ** 3)
            memory_total_gb = memory.total / (1024 ** 3)
            
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            net_io = psutil.net_io_counters()
            
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'per_core': psutil.cpu_percent(percpu=True)
                },
                'memory': {
                    'percent': memory_percent,
                    'used_gb': round(memory_used_gb, 2),
                    'total_gb': round(memory_total_gb, 2),
                    'available_gb': round(memory.available / (1024 ** 3), 2)
                },
                'disk': {
                    'percent': disk_percent,
                    'used_gb': round(disk.used / (1024 ** 3), 2),
                    'total_gb': round(disk.total / (1024 ** 3), 2)
                },
                'network': {
                    'bytes_sent_mb': round(net_io.bytes_sent / (1024 ** 2), 2),
                    'bytes_recv_mb': round(net_io.bytes_recv / (1024 ** 2), 2)
                }
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"獲取系統指標失敗: {e}")
            return {}
    
    def get_application_metrics(self) -> Dict:
        """
        獲取應用程序性能指標
        
        Returns:
            Dict: 應用程序指標
        """
        uptime_seconds = time.time() - self.start_time
        uptime_hours = uptime_seconds / 3600
        
        metrics = {
            'uptime': {
                'seconds': round(uptime_seconds, 2),
                'hours': round(uptime_hours, 2),
                'days': round(uptime_hours / 24, 2)
            },
            'statistics': {
                'signals_generated': self.total_signals_generated,
                'trades_executed': self.total_trades_executed,
                'api_calls': self.total_api_calls,
                'errors': self.total_errors
            },
            'rates': {
                'signals_per_hour': round(self.total_signals_generated / max(uptime_hours, 0.01), 2),
                'trades_per_hour': round(self.total_trades_executed / max(uptime_hours, 0.01), 2)
            }
        }
        
        return metrics
    
    def record_signal(self):
        """記錄信號生成"""
        self.total_signals_generated += 1
    
    def record_trade(self):
        """記錄交易執行"""
        self.total_trades_executed += 1
    
    def record_api_call(self):
        """記錄 API 調用"""
        self.total_api_calls += 1
    
    def record_error(self):
        """記錄錯誤"""
        self.total_errors += 1
    
    def record_operation(self, operation_name: str, duration: float):
        """
        記錄操作時間（v3.3.7新增）
        
        Args:
            operation_name: 操作名稱
            duration: 持續時間（秒）
        """
        self.operation_times.append({
            'name': operation_name,
            'duration': duration,
            'timestamp': time.time()
        })
        
        self.total_latency += duration
        self.operation_count += 1
        
        # 記錄到操作統計
        if operation_name not in self.operation_stats:
            self.operation_stats[operation_name] = deque(maxlen=100)
        self.operation_stats[operation_name].append(duration)
    
    def track_operation(self, operation_name: str) -> OperationTimer:
        """
        追蹤操作時間的上下文管理器（v3.3.7新增）
        
        Args:
            operation_name: 操作名稱
        
        Returns:
            OperationTimer: 計時器上下文管理器
        
        Example:
            with perf_monitor.track_operation("get_klines_BTCUSDT"):
                data = await client.get_klines(...)
        """
        return OperationTimer(self, operation_name)
    
    def record_cache_hit(self):
        """記錄緩存命中（v3.3.7新增）"""
        self.cache_hits += 1
    
    def record_cache_miss(self):
        """記錄緩存未命中（v3.3.7新增）"""
        self.cache_misses += 1
    
    def get_cache_hit_rate(self) -> float:
        """
        獲取緩存命中率（v3.3.7新增）
        
        Returns:
            float: 緩存命中率（0.0-1.0）
        """
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total
    
    def get_avg_latency(self) -> float:
        """
        獲取平均延遲（v3.3.7新增）
        
        Returns:
            float: 平均延遲（毫秒）
        """
        if self.operation_count == 0:
            return 0.0
        return (self.total_latency / self.operation_count) * 1000
    
    def get_operation_stats(self, operation_name: str) -> Dict:
        """
        獲取特定操作的統計信息（v3.3.7新增）
        
        Args:
            operation_name: 操作名稱
        
        Returns:
            Dict: 統計信息
        """
        if operation_name not in self.operation_stats:
            return {}
        
        durations = list(self.operation_stats[operation_name])
        if not durations:
            return {}
        
        return {
            'count': len(durations),
            'avg_ms': sum(durations) / len(durations) * 1000,
            'min_ms': min(durations) * 1000,
            'max_ms': max(durations) * 1000,
            'total_s': sum(durations)
        }
    
    def detect_bottlenecks(self) -> List[str]:
        """
        檢測性能瓶頸（v3.3.7新增）
        
        Returns:
            List[str]: 瓶頸列表
        """
        bottlenecks = []
        
        # 1. 檢查平均延遲
        avg_latency_ms = self.get_avg_latency()
        if avg_latency_ms > 1000:  # 超過1秒
            bottlenecks.append(
                f"⚠️  平均操作延遲過高: {avg_latency_ms:.0f}ms"
            )
        
        # 2. 檢查緩存命中率
        cache_hit_rate = self.get_cache_hit_rate()
        if cache_hit_rate < 0.5 and (self.cache_hits + self.cache_misses) > 100:
            bottlenecks.append(
                f"⚠️  緩存命中率過低: {cache_hit_rate:.1%}"
            )
        
        # 3. 檢查CPU使用
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            if cpu > 90:
                bottlenecks.append(f"⚠️  CPU使用率過高: {cpu:.1f}%")
        except:
            pass
        
        # 4. 檢查內存使用
        try:
            mem = psutil.virtual_memory().percent
            if mem > 85:
                bottlenecks.append(f"⚠️  內存使用率過高: {mem:.1f}%")
        except:
            pass
        
        # 5. 檢查慢操作
        for op_name, durations in self.operation_stats.items():
            if durations:
                avg_duration = sum(durations) / len(durations)
                if avg_duration > 2.0:  # 超過2秒
                    bottlenecks.append(
                        f"⚠️  操作過慢: {op_name} ({avg_duration:.2f}s)"
                    )
        
        return bottlenecks
    
    def generate_recommendations(self, bottlenecks: List[str]) -> List[str]:
        """
        生成優化建議（v3.3.7新增）
        
        Args:
            bottlenecks: 瓶頸列表
        
        Returns:
            List[str]: 優化建議
        """
        recommendations = []
        
        for bottleneck in bottlenecks:
            if 'CPU' in bottleneck:
                recommendations.append("💡 建議: 減少並行工作線程數或優化CPU密集型操作")
            elif '緩存' in bottleneck:
                recommendations.append("💡 建議: 增加緩存TTL或預取數據")
            elif '延遲' in bottleneck or '操作過慢' in bottleneck:
                recommendations.append("💡 建議: 啟用數據預取、增加批次大小或優化算法")
            elif '內存' in bottleneck:
                recommendations.append("💡 建議: 啟用流式處理或減小批次大小")
        
        return recommendations
    
    def get_full_report(self) -> Dict:
        """
        獲取完整性能報告（v3.3.7增強版）
        
        Returns:
            Dict: 完整報告
        """
        bottlenecks = self.detect_bottlenecks()
        
        return {
            'system': self.get_system_metrics(),
            'application': self.get_application_metrics(),
            'performance': {
                'avg_latency_ms': self.get_avg_latency(),
                'cache_hit_rate': self.get_cache_hit_rate(),
                'operations_per_second': (
                    self.operation_count / 
                    max(time.time() - self.start_time, 1)
                ),
                'total_operations': self.operation_count
            },
            'bottlenecks': bottlenecks,
            'recommendations': self.generate_recommendations(bottlenecks)
        }
    
    def log_metrics(self):
        """記錄性能指標到日誌（v3.3.7增強版）"""
        try:
            metrics = self.get_full_report()
            
            logger.info("=" * 60)
            logger.info("📊 性能監控報告 (v3.3.7)")
            logger.info("=" * 60)
            
            sys_metrics = metrics.get('system', {})
            app_metrics = metrics.get('application', {})
            perf_metrics = metrics.get('performance', {})
            
            # CPU
            cpu = sys_metrics.get('cpu', {})
            logger.info(f"CPU: {cpu.get('percent', 0):.1f}% ({cpu.get('count', 0)} 核心)")
            
            # 內存
            mem = sys_metrics.get('memory', {})
            logger.info(
                f"內存: {mem.get('used_gb', 0):.2f}/{mem.get('total_gb', 0):.2f} GB "
                f"({mem.get('percent', 0):.1f}%)"
            )
            
            # 應用統計
            uptime = app_metrics.get('uptime', {})
            stats = app_metrics.get('statistics', {})
            rates = app_metrics.get('rates', {})
            
            logger.info(f"運行時間: {uptime.get('hours', 0):.2f} 小時")
            logger.info(f"信號生成: {stats.get('signals_generated', 0)} 個")
            logger.info(f"交易執行: {stats.get('trades_executed', 0)} 筆")
            logger.info(f"API 調用: {stats.get('api_calls', 0)} 次")
            logger.info(f"信號速率: {rates.get('signals_per_hour', 0):.2f} 個/小時")
            
            # ✨ v3.3.7新增：性能指標
            logger.info("─" * 60)
            logger.info("⚡ 性能指標:")
            logger.info(f"  平均延遲: {perf_metrics.get('avg_latency_ms', 0):.2f}ms")
            logger.info(f"  緩存命中率: {perf_metrics.get('cache_hit_rate', 0):.1%}")
            logger.info(f"  操作速率: {perf_metrics.get('operations_per_second', 0):.2f} ops/s")
            logger.info(f"  總操作數: {perf_metrics.get('total_operations', 0)}")
            
            # ✨ v3.3.7新增：瓶頸和建議
            bottlenecks = metrics.get('bottlenecks', [])
            if bottlenecks:
                logger.info("─" * 60)
                logger.warning("⚠️  檢測到性能瓶頸:")
                for bottleneck in bottlenecks:
                    logger.warning(f"  {bottleneck}")
                
                recommendations = metrics.get('recommendations', [])
                if recommendations:
                    logger.info("💡 優化建議:")
                    for rec in recommendations:
                        logger.info(f"  {rec}")
            else:
                logger.info("─" * 60)
                logger.info("✅ 系統性能良好，無明顯瓶頸")
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"記錄性能指標失敗: {e}")
    
    async def start_monitoring(self, interval: int = 300):
        """
        啟動定期監控（每 5 分鐘）
        
        Args:
            interval: 監控間隔（秒）
        """
        logger.info(f"啟動性能監控，間隔 {interval} 秒")
        
        while True:
            try:
                await asyncio.sleep(interval)
                self.log_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"性能監控異常: {e}")
