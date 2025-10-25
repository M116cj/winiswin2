"""
性能監控器
職責：系統性能指標追蹤、資源使用監控
"""

import psutil
import asyncio
import logging
from typing import Dict
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """系統性能監控器"""
    
    def __init__(self):
        """初始化性能監控器"""
        self.start_time = time.time()
        self.total_signals_generated = 0
        self.total_trades_executed = 0
        self.total_api_calls = 0
        self.total_errors = 0
    
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
    
    def get_full_report(self) -> Dict:
        """
        獲取完整性能報告
        
        Returns:
            Dict: 完整報告
        """
        return {
            'system': self.get_system_metrics(),
            'application': self.get_application_metrics()
        }
    
    def log_metrics(self):
        """記錄性能指標到日誌"""
        try:
            metrics = self.get_full_report()
            
            logger.info("=" * 60)
            logger.info("📊 性能監控報告")
            logger.info("=" * 60)
            
            sys_metrics = metrics.get('system', {})
            app_metrics = metrics.get('application', {})
            
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
