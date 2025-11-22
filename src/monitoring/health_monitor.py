"""
健康監控服務
職責：系統健康檢查、性能指標監控、異常檢測
"""

import asyncio
from typing import Dict, List
from datetime import datetime, timedelta
import psutil
import logging

from src.core.unified_config_manager import config_manager as config

logger = logging.getLogger(__name__)


class HealthMonitor:
    """健康監控服務"""
    
    def __init__(self):
        """初始化健康監控"""
        self.config = Config
        self.start_time = datetime.now()
        self.api_call_count = 0
        self.api_error_count = 0
        self.last_api_call_time = None
        self.alerts_sent: List[Dict] = []
    
    async def check_system_health(self) -> Dict:
        """
        檢查系統健康狀態
        
        Returns:
            Dict: 健康檢查結果
        """
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'uptime_hours': self._get_uptime_hours(),
            'checks': {}
        }
        
        cpu_check = self._check_cpu()
        memory_check = self._check_memory()
        api_check = self._check_api_health()
        
        health_status['checks']['cpu'] = cpu_check
        health_status['checks']['memory'] = memory_check
        health_status['checks']['api'] = api_check
        
        if not all([
            cpu_check['healthy'],
            memory_check['healthy'],
            api_check['healthy']
        ]):
            health_status['status'] = 'unhealthy'
        
        return health_status
    
    def _get_uptime_hours(self) -> float:
        """獲取系統運行時間（小時）"""
        uptime = datetime.now() - self.start_time
        return uptime.total_seconds() / 3600
    
    def _check_cpu(self) -> Dict:
        """檢查 CPU 使用率"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                'healthy': cpu_percent < 80,
                'value': cpu_percent,
                'unit': '%',
                'threshold': 80,
                'message': 'CPU 正常' if cpu_percent < 80 else 'CPU 使用率過高'
            }
        except Exception as e:
            logger.error(f"檢查 CPU 失敗: {e}")
            return {
                'healthy': False,
                'value': 0,
                'unit': '%',
                'message': f"檢查失敗: {e}"
            }
    
    def _check_memory(self) -> Dict:
        """檢查內存使用率"""
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            return {
                'healthy': memory_percent < 85,
                'value': memory_percent,
                'unit': '%',
                'threshold': 85,
                'used_mb': memory.used / (1024 * 1024),
                'total_mb': memory.total / (1024 * 1024),
                'message': '內存正常' if memory_percent < 85 else '內存使用率過高'
            }
        except Exception as e:
            logger.error(f"檢查內存失敗: {e}")
            return {
                'healthy': False,
                'value': 0,
                'unit': '%',
                'message': f"檢查失敗: {e}"
            }
    
    def _check_api_health(self) -> Dict:
        """檢查 API 健康狀態"""
        if self.api_call_count == 0:
            return {
                'healthy': True,
                'total_calls': 0,
                'error_rate': 0.0,
                'message': 'API 正常（無調用）'
            }
        
        error_rate = self.api_error_count / self.api_call_count
        
        time_since_last_call = None
        if self.last_api_call_time:
            time_since_last_call = (datetime.now() - self.last_api_call_time).total_seconds()
        
        is_healthy = error_rate < 0.1 and (
            time_since_last_call is None or time_since_last_call < 300
        )
        
        return {
            'healthy': is_healthy,
            'total_calls': self.api_call_count,
            'error_count': self.api_error_count,
            'error_rate': error_rate,
            'last_call_seconds_ago': time_since_last_call,
            'message': 'API 正常' if is_healthy else 'API 異常'
        }
    
    def record_api_call(self, success: bool = True):
        """
        記錄 API 調用
        
        Args:
            success: 調用是否成功
        """
        self.api_call_count += 1
        if not success:
            self.api_error_count += 1
        self.last_api_call_time = datetime.now()
    
    def get_performance_metrics(self) -> Dict:
        """
        獲取性能指標
        
        Returns:
            Dict: 性能指標
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'uptime_hours': self._get_uptime_hours(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': psutil.cpu_count()
                },
                'memory': {
                    'percent': memory.percent,
                    'used_mb': memory.used / (1024 * 1024),
                    'available_mb': memory.available / (1024 * 1024),
                    'total_mb': memory.total / (1024 * 1024)
                },
                'api': {
                    'total_calls': self.api_call_count,
                    'error_count': self.api_error_count,
                    'error_rate': self.api_error_count / self.api_call_count if self.api_call_count > 0 else 0
                }
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"獲取性能指標失敗: {e}")
            return {}
    
    async def detect_anomalies(self, metrics: Dict) -> List[Dict]:
        """
        檢測異常
        
        Args:
            metrics: 性能指標
        
        Returns:
            List[Dict]: 異常列表
        """
        anomalies = []
        
        if metrics.get('cpu', {}).get('percent', 0) > 80:
            anomalies.append({
                'type': 'high_cpu',
                'severity': 'warning',
                'message': f"CPU 使用率過高: {metrics['cpu']['percent']:.1f}%",
                'timestamp': datetime.now().isoformat()
            })
        
        if metrics.get('memory', {}).get('percent', 0) > 85:
            anomalies.append({
                'type': 'high_memory',
                'severity': 'warning',
                'message': f"內存使用率過高: {metrics['memory']['percent']:.1f}%",
                'timestamp': datetime.now().isoformat()
            })
        
        api_error_rate = metrics.get('api', {}).get('error_rate', 0)
        if api_error_rate > 0.1:
            anomalies.append({
                'type': 'high_api_error_rate',
                'severity': 'critical',
                'message': f"API 錯誤率過高: {api_error_rate:.1%}",
                'timestamp': datetime.now().isoformat()
            })
        
        return anomalies
    
    def should_send_alert(self, anomaly: Dict) -> bool:
        """
        判斷是否應該發送提醒
        
        Args:
            anomaly: 異常信息
        
        Returns:
            bool: 是否應該發送提醒
        """
        cooldown_minutes = 15
        
        for alert in self.alerts_sent:
            if alert['type'] == anomaly['type']:
                alert_time = datetime.fromisoformat(alert['timestamp'])
                if datetime.now() - alert_time < timedelta(minutes=cooldown_minutes):
                    return False
        
        self.alerts_sent.append(anomaly)
        
        if len(self.alerts_sent) > 100:
            self.alerts_sent = self.alerts_sent[-50:]
        
        return True
    
    def reset_stats(self):
        """重置統計數據"""
        self.api_call_count = 0
        self.api_error_count = 0
        self.last_api_call_time = None
        logger.info("監控統計已重置")
