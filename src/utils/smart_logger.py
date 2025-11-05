"""
SmartLogger - 智能日志系统
🔥 v3.25+ 新增功能：
- 速率限制（防止日志洪水）
- 动态日志级别
- 日志聚合（防止重复）
- 结构化日志（JSON格式）
- 性能监控
- 异步写入缓冲
"""

import logging
import time
import json
from typing import Dict, Optional, Any, List
from collections import defaultdict, deque
from datetime import datetime
import threading
from pathlib import Path


class SmartLogger:
    """
    智能日志系统
    
    关键功能：
    1. 速率限制：同样的消息在时间窗口内只记录一次
    2. 日志聚合：相似消息合并计数
    3. 结构化日志：支持JSON格式输出
    4. 性能监控：跟踪日志统计
    5. 动态级别：运行时调整日志级别
    """
    
    def __init__(
        self,
        name: str,
        base_logger: Optional[logging.Logger] = None,
        rate_limit_window: float = 60.0,  # 速率限制窗口（秒）
        enable_aggregation: bool = True,  # 启用日志聚合
        enable_structured: bool = False,  # 启用结构化日志
        structured_log_file: Optional[str] = None  # 结构化日志文件
    ):
        """
        初始化SmartLogger
        
        Args:
            name: Logger名称
            base_logger: 底层logger（可选）
            rate_limit_window: 速率限制时间窗口（秒）
            enable_aggregation: 是否启用日志聚合
            enable_structured: 是否启用结构化日志
            structured_log_file: 结构化日志文件路径
        """
        self.name = name
        self.base_logger = base_logger or logging.getLogger(name)
        self.rate_limit_window = rate_limit_window
        self.enable_aggregation = enable_aggregation
        self.enable_structured = enable_structured
        self.structured_log_file = structured_log_file
        
        # 🔥 速率限制机制（记录最后一次日志时间）
        self._rate_limit_cache: Dict[str, float] = {}
        self._rate_limit_lock = threading.Lock()
        
        # 🔥 日志聚合机制（合并重复消息）
        self._aggregation_cache: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0,
            'first_time': 0,
            'last_time': 0,
            'level': logging.INFO
        })
        self._aggregation_lock = threading.Lock()
        
        # 🔥 性能统计
        self._stats = {
            'total_logs': 0,
            'rate_limited': 0,
            'aggregated': 0,
            'by_level': defaultdict(int)
        }
        self._stats_lock = threading.Lock()
        
        # 🔥 结构化日志写入器
        if enable_structured and structured_log_file:
            Path(structured_log_file).parent.mkdir(parents=True, exist_ok=True)
            self._structured_file = open(structured_log_file, 'a', encoding='utf-8')
        else:
            self._structured_file = None
    
    def _should_log(self, message: str, level: int) -> bool:
        """
        检查是否应该记录此消息（速率限制）
        
        Args:
            message: 日志消息
            level: 日志级别
        
        Returns:
            True如果应该记录，否则False
        """
        # 🔥 Critical/Error级别不限制
        if level >= logging.ERROR:
            return True
        
        # 生成缓存键（基于消息和级别）
        cache_key = f"{level}:{message}"
        
        with self._rate_limit_lock:
            now = time.time()
            last_time = self._rate_limit_cache.get(cache_key, 0)
            
            # 检查时间窗口
            if now - last_time < self.rate_limit_window:
                with self._stats_lock:
                    self._stats['rate_limited'] += 1
                return False
            
            # 更新最后记录时间
            self._rate_limit_cache[cache_key] = now
            
            # 清理过期缓存（保持缓存大小合理）
            if len(self._rate_limit_cache) > 1000:
                expired_keys = [
                    k for k, v in self._rate_limit_cache.items()
                    if now - v > self.rate_limit_window * 2
                ]
                for k in expired_keys:
                    del self._rate_limit_cache[k]
        
        return True
    
    def _aggregate_message(self, message: str, level: int):
        """
        聚合重复消息（计数）
        
        Args:
            message: 日志消息
            level: 日志级别
        """
        if not self.enable_aggregation:
            return
        
        cache_key = f"{level}:{message}"
        now = time.time()
        
        with self._aggregation_lock:
            agg = self._aggregation_cache[cache_key]
            
            if agg['count'] == 0:
                agg['first_time'] = now
                agg['level'] = level
            
            agg['count'] += 1
            agg['last_time'] = now
            
            with self._stats_lock:
                self._stats['aggregated'] += 1
    
    def _write_structured_log(self, level: int, message: str, extra: Optional[Dict] = None):
        """
        写入结构化日志（JSON格式）
        
        Args:
            level: 日志级别
            message: 日志消息
            extra: 额外数据
        """
        if not self._structured_file:
            return
        
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': logging.getLevelName(level),
                'logger': self.name,
                'message': message,
                **(extra or {})
            }
            
            self._structured_file.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            self._structured_file.flush()
        
        except Exception as e:
            # 避免日志错误影响主流程
            self.base_logger.error(f"❌ 结构化日志写入失败: {e}")
    
    def _log(self, level: int, message: str, *args, extra: Optional[Dict] = None, **kwargs):
        """
        内部日志方法（应用所有智能特性）
        
        Args:
            level: 日志级别
            message: 日志消息
            extra: 额外数据
        """
        # 更新统计
        with self._stats_lock:
            self._stats['total_logs'] += 1
            self._stats['by_level'][logging.getLevelName(level)] += 1
        
        # 🔥 v3.25.1 Critical Fix: 聚合必须在速率限制之前（统计所有调用）
        self._aggregate_message(message, level)
        
        # 🔥 速率限制检查
        if not self._should_log(message, level):
            return
        
        # 🔥 结构化日志
        if self.enable_structured:
            self._write_structured_log(level, message, extra)
        
        # 🔥 v3.25.1 Critical Fix: 转发extra到base_logger（保持API兼容性）
        if extra:
            self.base_logger.log(level, message, *args, extra=extra, **kwargs)
        else:
            self.base_logger.log(level, message, *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        """DEBUG级别日志"""
        self._log(logging.DEBUG, message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """INFO级别日志"""
        self._log(logging.INFO, message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """WARNING级别日志"""
        self._log(logging.WARNING, message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """ERROR级别日志（不限速）"""
        self._log(logging.ERROR, message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """CRITICAL级别日志（不限速）"""
        self._log(logging.CRITICAL, message, *args, **kwargs)
    
    def flush_aggregations(self) -> List[Dict]:
        """
        刷新聚合日志（报告重复次数）
        
        Returns:
            聚合日志列表
        """
        with self._aggregation_lock:
            aggregations = []
            now = time.time()
            
            for key, agg in list(self._aggregation_cache.items()):
                if agg['count'] > 1:
                    duration = agg['last_time'] - agg['first_time']
                    aggregations.append({
                        'message': key.split(':', 1)[1],
                        'level': logging.getLevelName(agg['level']),
                        'count': agg['count'],
                        'duration': duration,
                        'first_time': datetime.fromtimestamp(agg['first_time']).isoformat(),
                        'last_time': datetime.fromtimestamp(agg['last_time']).isoformat()
                    })
                    
                    # 报告聚合结果
                    self.base_logger.log(
                        agg['level'],
                        f"📊 聚合日志: {agg['count']}次 '{key.split(':', 1)[1]}' (过去{duration:.1f}秒)"
                    )
                
                # 清理旧聚合（超过窗口的2倍）
                if now - agg['last_time'] > self.rate_limit_window * 2:
                    del self._aggregation_cache[key]
            
            return aggregations
    
    def get_stats(self) -> Dict:
        """
        获取日志统计
        
        Returns:
            统计数据字典
        """
        with self._stats_lock:
            return {
                'total_logs': self._stats['total_logs'],
                'rate_limited': self._stats['rate_limited'],
                'aggregated': self._stats['aggregated'],
                'by_level': dict(self._stats['by_level']),
                'rate_limit_efficiency': (
                    self._stats['rate_limited'] / max(1, self._stats['total_logs'])
                ) * 100
            }
    
    def set_level(self, level: int):
        """
        动态设置日志级别
        
        Args:
            level: 新的日志级别
        """
        self.base_logger.setLevel(level)
    
    def close(self):
        """关闭SmartLogger（刷新聚合日志）"""
        # 刷新聚合日志
        self.flush_aggregations()
        
        # 关闭结构化日志文件
        if self._structured_file:
            self._structured_file.close()
        
        # 打印最终统计
        stats = self.get_stats()
        self.base_logger.info("=" * 80)
        self.base_logger.info("📊 SmartLogger 统计数据:")
        self.base_logger.info(f"   总日志数: {stats['total_logs']}")
        self.base_logger.info(f"   速率限制: {stats['rate_limited']} ({stats['rate_limit_efficiency']:.1f}%)")
        self.base_logger.info(f"   聚合次数: {stats['aggregated']}")
        self.base_logger.info(f"   按级别: {stats['by_level']}")
        self.base_logger.info("=" * 80)


# 🔥 便捷工厂函数
def create_smart_logger(
    name: str,
    rate_limit_window: float = 60.0,
    enable_aggregation: bool = True,
    enable_structured: bool = False,
    structured_log_file: Optional[str] = None
) -> SmartLogger:
    """
    创建SmartLogger实例
    
    Args:
        name: Logger名称
        rate_limit_window: 速率限制时间窗口（秒）
        enable_aggregation: 是否启用日志聚合
        enable_structured: 是否启用结构化日志
        structured_log_file: 结构化日志文件路径
    
    Returns:
        SmartLogger实例
    """
    return SmartLogger(
        name=name,
        rate_limit_window=rate_limit_window,
        enable_aggregation=enable_aggregation,
        enable_structured=enable_structured,
        structured_log_file=structured_log_file
    )
