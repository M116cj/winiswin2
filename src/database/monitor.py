"""
Database Monitor - PostgreSQL 实时数据监控系统
提供生产级的数据库性能监控和统计日志

Phase 3: 迁移到AsyncDatabaseManager (asyncpg)
"""

import asyncio
import logging
import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from .unified_database_manager import UnifiedDatabaseManager

logger = logging.getLogger(__name__)


class DatabaseMonitor:
    """
    PostgreSQL 实时数据监控服务
    
    功能：
    - 实时统计各资料表记录数
    - 监控数据库连接状态和性能
    - 交易统计分析
    - ML模型使用情况
    - 性能警告和阈值检测
    """
    
    def __init__(
        self,
        db_manager: UnifiedDatabaseManager,
        refresh_interval: int = 60,
        auto_start: bool = False,
        enable_alerts: bool = True
    ):
        """
        初始化监控服务
        
        Args:
            db_manager: 异步数据库管理器实例
            refresh_interval: 刷新间隔（秒），默认60秒
            auto_start: 是否自动启动监控，默认False
            enable_alerts: 是否启用警告，默认True
        """
        self.db_manager = db_manager
        self.refresh_interval = refresh_interval
        self.enable_alerts = enable_alerts
        
        # 监控状态
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._last_stats: Optional[Dict[str, Any]] = None
        self._error_count = 0
        self._last_error_time: Optional[datetime] = None
        
        # 性能阈值配置
        self.thresholds = {
            'max_response_time_ms': 1000,  # 最大响应时间
            'max_error_rate': 0.05,        # 最大错误率 5%
            'max_open_positions': 10,      # 最大未平仓数
            'min_connection_pool': 2,      # 最小连接数
        }
        
        # 统计缓存
        self._stats_cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 5  # 缓存有效期（秒）
        
        if auto_start:
            self.start_monitoring()
    
    def start_monitoring(self) -> bool:
        """
        启动监控服务（后台线程）
        
        Returns:
            是否成功启动
        """
        if self._monitoring:
            logger.warning("⚠️ 监控服务已在运行中")
            return False
        
        try:
            self._monitoring = True
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="DatabaseMonitor"
            )
            self._monitor_thread.start()
            
            logger.info("=" * 70)
            logger.info("🚀 数据库监控服务已启动")
            logger.info(f"   刷新间隔: {self.refresh_interval} 秒")
            logger.info(f"   警告系统: {'启用' if self.enable_alerts else '禁用'}")
            logger.info("=" * 70)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 启动监控服务失败: {e}")
            self._monitoring = False
            return False
    
    def stop_monitoring(self) -> None:
        """停止监控服务"""
        if not self._monitoring:
            return
        
        logger.info("🛑 正在停止数据库监控服务...")
        self._monitoring = False
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        
        logger.info("✅ 数据库监控服务已停止")
    
    def _monitoring_loop(self) -> None:
        """监控主循环（在后台线程中运行）"""
        logger.info("📊 监控循环已启动")
        
        while self._monitoring:
            try:
                # 收集并显示统计数据
                stats = self.get_real_time_stats()
                
                if stats:
                    self._last_stats = stats
                    self.display_stats(stats)
                    
                    # 检查阈值警告
                    if self.enable_alerts:
                        self.check_alerts(stats)
                    
                    self._error_count = 0  # 重置错误计数
                else:
                    self._handle_monitoring_error("统计数据获取失败")
                
            except Exception as e:
                self._handle_monitoring_error(f"监控循环异常: {e}")
            
            # 等待下一次刷新
            time.sleep(self.refresh_interval)
        
        logger.info("📊 监控循环已结束")
    
    def _handle_monitoring_error(self, error_msg: str) -> None:
        """处理监控错误"""
        self._error_count += 1
        self._last_error_time = datetime.utcnow()
        
        if self._error_count <= 3:
            logger.warning(f"⚠️ {error_msg} (错误次数: {self._error_count}/3)")
        else:
            logger.error(f"❌ 监控服务连续失败 {self._error_count} 次")
    
    async def get_real_time_stats_async(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取实时统计数据（异步版本）
        
        Args:
            use_cache: 是否使用缓存（默认True）
            
        Returns:
            统计数据字典，失败返回None
        """
        # 检查缓存
        if use_cache and self._is_cache_valid():
            return self._stats_cache
        
        try:
            start_time = time.time()
            
            stats = {
                'timestamp': datetime.utcnow().isoformat(),
                'trades': await self._get_trades_stats_async(),
                'ml_models': await self._get_ml_models_stats_async(),
                'market_data': await self._get_market_data_stats_async(),
                'trading_signals': await self._get_trading_signals_stats_async(),
                'performance': await self._get_performance_stats_async(),
            }
            
            # 计算查询响应时间
            response_time_ms = (time.time() - start_time) * 1000
            stats['performance']['query_time_ms'] = round(response_time_ms, 2)
            
            # 更新缓存
            self._stats_cache = stats
            self._cache_timestamp = datetime.utcnow()
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 获取统计数据失败: {e}")
            logger.exception("详细错误:")
            return None
    
    def get_real_time_stats(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取实时统计数据（同步wrapper）
        
        Args:
            use_cache: 是否使用缓存（默认True）
            
        Returns:
            统计数据字典，失败返回None
        """
        return asyncio.run(self.get_real_time_stats_async(use_cache))
    
    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self._cache_timestamp or not self._stats_cache:
            return False
        
        age = (datetime.utcnow() - self._cache_timestamp).total_seconds()
        return age < self._cache_ttl
    
    async def _get_trades_stats_async(self) -> Dict[str, Any]:
        """获取交易记录统计（异步版本）"""
        try:
            query = """
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open_positions,
                    COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed_trades,
                    COUNT(CASE WHEN won = TRUE THEN 1 END) as winning_trades,
                    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as today_trades,
                    ROUND(AVG(CASE WHEN status = 'CLOSED' THEN pnl_pct END)::numeric, 2) as avg_pnl_pct,
                    ROUND(SUM(CASE WHEN status = 'CLOSED' THEN pnl ELSE 0 END)::numeric, 2) as total_pnl
                FROM trades;
            """
            
            result = await self.db_manager.fetch(query)
            
            if result and len(result) > 0:
                row = result[0]
                total = row['total_trades'] or 0
                closed = row['closed_trades'] or 0
                winning = row['winning_trades'] or 0
                
                return {
                    'total_trades': total,
                    'open_positions': row['open_positions'] or 0,
                    'closed_trades': closed,
                    'winning_trades': winning,
                    'today_trades': row['today_trades'] or 0,
                    'avg_pnl_pct': float(row['avg_pnl_pct']) if row['avg_pnl_pct'] else 0.0,
                    'total_pnl': float(row['total_pnl']) if row['total_pnl'] else 0.0,
                    'win_rate': round(winning / closed * 100, 1) if closed > 0 else 0.0
                }
            
            return self._empty_trades_stats()
            
        except Exception as e:
            logger.error(f"❌ 获取交易统计失败: {e}")
            return self._empty_trades_stats()
    
    def _get_trades_stats(self) -> Dict[str, Any]:
        """获取交易记录统计（同步wrapper）"""
        return asyncio.run(self._get_trades_stats_async())
    
    async def _get_ml_models_stats_async(self) -> Dict[str, Any]:
        """获取ML模型统计（异步版本）"""
        try:
            query = """
                SELECT
                    COUNT(*) as total_models,
                    COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_models,
                    MAX(version) as latest_version,
                    ROUND(AVG(accuracy)::numeric, 3) as avg_accuracy
                FROM ml_models;
            """
            
            result = await self.db_manager.fetch(query)
            
            if result and len(result) > 0:
                row = result[0]
                return {
                    'total_models': row['total_models'] or 0,
                    'active_models': row['active_models'] or 0,
                    'latest_version': row['latest_version'] or 0,
                    'avg_accuracy': float(row['avg_accuracy']) if row['avg_accuracy'] else 0.0
                }
            
            return self._empty_ml_models_stats()
            
        except Exception as e:
            logger.error(f"❌ 获取ML模型统计失败: {e}")
            return self._empty_ml_models_stats()
    
    def _get_ml_models_stats(self) -> Dict[str, Any]:
        """获取ML模型统计（同步wrapper）"""
        return asyncio.run(self._get_ml_models_stats_async())
    
    async def _get_market_data_stats_async(self) -> Dict[str, Any]:
        """获取市场数据统计（异步版本）"""
        try:
            query = """
                SELECT
                    COUNT(*) as total_records,
                    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as today_records,
                    COUNT(DISTINCT symbol) as unique_symbols,
                    COUNT(DISTINCT timeframe) as unique_timeframes
                FROM market_data;
            """
            
            result = await self.db_manager.fetch(query)
            
            if result and len(result) > 0:
                row = result[0]
                return {
                    'total_records': row['total_records'] or 0,
                    'today_records': row['today_records'] or 0,
                    'unique_symbols': row['unique_symbols'] or 0,
                    'unique_timeframes': row['unique_timeframes'] or 0
                }
            
            return self._empty_market_data_stats()
            
        except Exception as e:
            logger.error(f"❌ 获取市场数据统计失败: {e}")
            return self._empty_market_data_stats()
    
    def _get_market_data_stats(self) -> Dict[str, Any]:
        """获取市场数据统计（同步wrapper）"""
        return asyncio.run(self._get_market_data_stats_async())
    
    async def _get_trading_signals_stats_async(self) -> Dict[str, Any]:
        """获取交易信号统计（异步版本）"""
        try:
            query = """
                SELECT
                    COUNT(*) as total_signals,
                    COUNT(CASE WHEN status = 'PENDING' THEN 1 END) as pending_signals,
                    COUNT(CASE WHEN status = 'EXECUTED' THEN 1 END) as executed_signals,
                    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as today_signals
                FROM trading_signals;
            """
            
            result = await self.db_manager.fetch(query)
            
            if result and len(result) > 0:
                row = result[0]
                return {
                    'total_signals': row['total_signals'] or 0,
                    'pending_signals': row['pending_signals'] or 0,
                    'executed_signals': row['executed_signals'] or 0,
                    'today_signals': row['today_signals'] or 0
                }
            
            return self._empty_trading_signals_stats()
            
        except Exception as e:
            logger.error(f"❌ 获取交易信号统计失败: {e}")
            return self._empty_trading_signals_stats()
    
    def _get_trading_signals_stats(self) -> Dict[str, Any]:
        """获取交易信号统计（同步wrapper）"""
        return asyncio.run(self._get_trading_signals_stats_async())
    
    async def _get_performance_stats_async(self) -> Dict[str, Any]:
        """获取性能统计（异步版本）"""
        try:
            # 获取数据库连接池状态
            pool_status = self._get_pool_status()
            
            # 数据库健康检查
            is_healthy = await self.db_manager.check_health()
            
            return {
                'database_healthy': is_healthy,
                'connection_count': pool_status.get('connections', 0),
                'max_connections': pool_status.get('max_connections', 20),
                'error_rate': self._calculate_error_rate(),
                'query_time_ms': 0  # 将在主方法中填充
            }
            
        except Exception as e:
            logger.error(f"❌ 获取性能统计失败: {e}")
            return {
                'database_healthy': False,
                'connection_count': 0,
                'max_connections': 20,
                'error_rate': 1.0,
                'query_time_ms': 0
            }
    
    def _get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计（同步wrapper）"""
        return asyncio.run(self._get_performance_stats_async())
    
    def _get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        try:
            # asyncpg连接池状态
            if hasattr(self.db_manager, 'pool') and self.db_manager.pool:
                return {
                    'connections': self.db_manager.min_connections,
                    'max_connections': self.db_manager.max_connections
                }
            return {'connections': 0, 'max_connections': 20}
        except:
            return {'connections': 0, 'max_connections': 20}
    
    def _calculate_error_rate(self) -> float:
        """计算错误率"""
        if self._error_count == 0:
            return 0.0
        
        # 简化版：基于最近的错误计数
        return min(self._error_count / 10.0, 1.0)
    
    def display_stats(self, stats: Dict[str, Any]) -> None:
        """
        显示格式化的统计信息
        
        Args:
            stats: 统计数据字典
        """
        try:
            timestamp = datetime.fromisoformat(stats['timestamp'].replace('Z', '+00:00'))
            
            logger.info("")
            logger.info("=" * 70)
            logger.info(f"🕒 [{timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}] 📊 数据库实时统计")
            logger.info("=" * 70)
            
            # 交易记录统计
            trades = stats.get('trades', {})
            logger.info("📈 交易记录:")
            logger.info(f"   • 总交易数: {trades.get('total_trades', 0):,}")
            logger.info(f"   • 今日新增: {trades.get('today_trades', 0)}")
            logger.info(f"   • 未平仓: {trades.get('open_positions', 0)}")
            logger.info(f"   • 已平仓: {trades.get('closed_trades', 0)}")
            logger.info(f"   • 胜率: {trades.get('win_rate', 0):.1f}%")
            logger.info(f"   • 平均盈亏: {trades.get('avg_pnl_pct', 0):.2f}%")
            logger.info(f"   • 总盈亏: ${trades.get('total_pnl', 0):.2f}")
            
            # ML模型统计
            ml = stats.get('ml_models', {})
            logger.info("")
            logger.info("🤖 ML 模型:")
            logger.info(f"   • 总模型数: {ml.get('total_models', 0)}")
            logger.info(f"   • 活跃模型: {ml.get('active_models', 0)}")
            logger.info(f"   • 最新版本: v{ml.get('latest_version', 0)}")
            logger.info(f"   • 平均准确率: {ml.get('avg_accuracy', 0):.1%}")
            
            # 市场数据统计
            market = stats.get('market_data', {})
            logger.info("")
            logger.info("📊 市场数据:")
            logger.info(f"   • 总记录数: {market.get('total_records', 0):,}")
            logger.info(f"   • 今日更新: {market.get('today_records', 0):,}")
            logger.info(f"   • 交易对数: {market.get('unique_symbols', 0)}")
            logger.info(f"   • 时间周期: {market.get('unique_timeframes', 0)}")
            
            # 交易信号统计
            signals = stats.get('trading_signals', {})
            logger.info("")
            logger.info("🚦 交易信号:")
            logger.info(f"   • 总信号数: {signals.get('total_signals', 0):,}")
            logger.info(f"   • 待执行: {signals.get('pending_signals', 0)}")
            logger.info(f"   • 已执行: {signals.get('executed_signals', 0)}")
            logger.info(f"   • 今日信号: {signals.get('today_signals', 0)}")
            
            # 性能指标
            perf = stats.get('performance', {})
            logger.info("")
            logger.info("⚡ 性能指标:")
            logger.info(f"   • 数据库状态: {'✅ 健康' if perf.get('database_healthy') else '❌ 异常'}")
            logger.info(f"   • 连接数: {perf.get('connection_count', 0)}/{perf.get('max_connections', 20)}")
            logger.info(f"   • 查询响应: {perf.get('query_time_ms', 0):.1f}ms")
            logger.info(f"   • 错误率: {perf.get('error_rate', 0):.1%}")
            
            logger.info("=" * 70)
            logger.info("")
            
        except Exception as e:
            logger.error(f"❌ 显示统计信息失败: {e}")
    
    def check_alerts(self, stats: Dict[str, Any]) -> None:
        """
        检查阈值并发出警告
        
        Args:
            stats: 统计数据字典
        """
        try:
            alerts = []
            
            # 检查未平仓数量
            open_positions = stats.get('trades', {}).get('open_positions', 0)
            if open_positions > self.thresholds['max_open_positions']:
                alerts.append(f"⚠️ 未平仓数量过多: {open_positions} > {self.thresholds['max_open_positions']}")
            
            # 检查响应时间
            query_time = stats.get('performance', {}).get('query_time_ms', 0)
            if query_time > self.thresholds['max_response_time_ms']:
                alerts.append(f"⚠️ 查询响应时间过长: {query_time:.1f}ms > {self.thresholds['max_response_time_ms']}ms")
            
            # 检查错误率
            error_rate = stats.get('performance', {}).get('error_rate', 0)
            if error_rate > self.thresholds['max_error_rate']:
                alerts.append(f"⚠️ 错误率过高: {error_rate:.1%} > {self.thresholds['max_error_rate']:.1%}")
            
            # 检查数据库健康
            if not stats.get('performance', {}).get('database_healthy'):
                alerts.append("❌ 数据库连接异常")
            
            # 显示警告
            if alerts:
                logger.warning("")
                logger.warning("🚨 阈值警告:")
                for alert in alerts:
                    logger.warning(f"   {alert}")
                logger.warning("")
            
        except Exception as e:
            logger.error(f"❌ 检查警告失败: {e}")
    
    def get_summary(self) -> Optional[Dict[str, Any]]:
        """
        获取监控摘要（一次性显示，不启动监控循环）
        
        Returns:
            统计摘要字典
        """
        stats = self.get_real_time_stats(use_cache=False)
        if stats:
            self.display_stats(stats)
        return stats
    
    # 辅助方法：返回空统计
    def _empty_trades_stats(self) -> Dict[str, Any]:
        return {
            'total_trades': 0, 'open_positions': 0, 'closed_trades': 0,
            'winning_trades': 0, 'today_trades': 0, 'avg_pnl_pct': 0.0,
            'total_pnl': 0.0, 'win_rate': 0.0
        }
    
    def _empty_ml_models_stats(self) -> Dict[str, Any]:
        return {
            'total_models': 0, 'active_models': 0,
            'latest_version': 0, 'avg_accuracy': 0.0
        }
    
    def _empty_market_data_stats(self) -> Dict[str, Any]:
        return {
            'total_records': 0, 'today_records': 0,
            'unique_symbols': 0, 'unique_timeframes': 0
        }
    
    def _empty_trading_signals_stats(self) -> Dict[str, Any]:
        return {
            'total_signals': 0, 'pending_signals': 0,
            'executed_signals': 0, 'today_signals': 0
        }
