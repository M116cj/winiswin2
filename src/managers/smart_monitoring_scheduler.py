"""
智能监控频率调度器
优化5：智能监控频率调整
"""
import asyncio
from src.utils.logger_factory import get_logger
import time
from typing import Dict, Callable, Set

logger = get_logger(__name__)


class SmartMonitoringScheduler:
    """智能监控频率调度器"""
    
    def __init__(self):
        self.monitoring_intervals: Dict[str, float] = {}  # position_id -> interval
        self.last_check: Dict[str, float] = {}
        self.active_positions: Set[str] = set()
        self.monitor_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info("✅ 智能监控频率调度器初始化")
    
    def get_monitoring_interval(self, position) -> float:
        """
        根据仓位风险动态调整监控频率
        
        Args:
            position: 虚拟仓位对象
        
        Returns:
            监控间隔（秒）
        """
        if position.is_closed:
            return 3600  # 已关闭仓位，1小时检查一次
        
        # 计算风险分数
        risk_score = self._calculate_risk_score(position)
        
        if risk_score > 0.8:  # 高风险（接近止盈止损）
            return 0.1  # 100ms
        elif risk_score > 0.5:  # 中风险
            return 0.5  # 500ms
        elif risk_score > 0.2:  # 低风险
            return 2.0  # 2秒
        else:  # 极低风险
            return 5.0  # 5秒
    
    def _calculate_risk_score(self, position) -> float:
        """
        计算仓位风险分数
        
        Args:
            position: 虚拟仓位对象
        
        Returns:
            风险分数（0-1）
        """
        try:
            current_price = position.current_price
            entry_price = position.entry_price
            
            if position.direction == 1:  # LONG
                tp_distance = (position.take_profit - current_price) / (position.take_profit - entry_price)
                sl_distance = (current_price - position.stop_loss) / (entry_price - position.stop_loss)
            else:  # SHORT
                tp_distance = (current_price - position.take_profit) / (entry_price - position.take_profit)
                sl_distance = (position.stop_loss - current_price) / (position.stop_loss - entry_price)
            
            # 风险分数：越接近边界，风险越高
            risk_score = max(1 - tp_distance, 1 - sl_distance, 0)
            return min(risk_score, 1.0)
        
        except Exception as e:
            logger.error(f"计算风险分数失败: {e}")
            return 0.5  # 默认中等风险
    
    async def smart_monitor_position(self, position_id: str, position, monitor_func: Callable):
        """
        智能监控仓位
        
        Args:
            position_id: 仓位ID
            position: 虚拟仓位对象
            monitor_func: 监控函数
        """
        logger.info(f"🎯 开始智能监控: {position_id}")
        self.active_positions.add(position_id)
        
        try:
            while position_id in self.active_positions:
                # 动态计算监控间隔
                interval = self.get_monitoring_interval(position)
                
                # 记录上次检查时间
                self.last_check[position_id] = time.time()
                self.monitoring_intervals[position_id] = interval
                
                # 执行监控
                try:
                    await monitor_func(position_id, position)
                except Exception as e:
                    logger.error(f"监控函数执行失败 {position_id}: {e}")
                
                # 等待下一个周期
                await asyncio.sleep(interval)
        
        except asyncio.CancelledError:
            logger.info(f"监控任务被取消: {position_id}")
        except Exception as e:
            logger.error(f"智能监控错误 {position_id}: {e}", exc_info=True)
        finally:
            # 清理
            if position_id in self.active_positions:
                self.active_positions.remove(position_id)
            if position_id in self.monitoring_intervals:
                del self.monitoring_intervals[position_id]
            if position_id in self.last_check:
                del self.last_check[position_id]
            
            logger.info(f"🛑 停止监控: {position_id}")
    
    def start_monitoring(self, position_id: str, position, monitor_func: Callable) -> asyncio.Task:
        """
        启动监控任务
        
        Args:
            position_id: 仓位ID
            position: 虚拟仓位对象
            monitor_func: 监控函数
        
        Returns:
            监控任务
        """
        if position_id in self.monitor_tasks:
            logger.warning(f"⚠️ 仓位已在监控中: {position_id}")
            return self.monitor_tasks[position_id]
        
        task = asyncio.create_task(
            self.smart_monitor_position(position_id, position, monitor_func)
        )
        self.monitor_tasks[position_id] = task
        
        logger.info(f"✅ 启动监控任务: {position_id}")
        return task
    
    def stop_monitoring(self, position_id: str):
        """
        停止监控任务
        
        Args:
            position_id: 仓位ID
        """
        if position_id in self.active_positions:
            self.active_positions.remove(position_id)
        
        if position_id in self.monitor_tasks:
            task = self.monitor_tasks[position_id]
            task.cancel()
            del self.monitor_tasks[position_id]
            logger.info(f"🛑 停止监控任务: {position_id}")
    
    async def stop_all_monitoring(self):
        """停止所有监控任务"""
        logger.info("🛑 停止所有监控任务...")
        
        # 复制列表以避免修改迭代中的集合
        position_ids = list(self.active_positions)
        
        for position_id in position_ids:
            self.stop_monitoring(position_id)
        
        # 等待所有任务完成
        if self.monitor_tasks:
            await asyncio.gather(*self.monitor_tasks.values(), return_exceptions=True)
        
        logger.info("✅ 所有监控任务已停止")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        active_count = len(self.active_positions)
        
        if active_count > 0:
            intervals = list(self.monitoring_intervals.values())
            avg_interval = sum(intervals) / len(intervals)
            min_interval = min(intervals)
            max_interval = max(intervals)
        else:
            avg_interval = 0
            min_interval = 0
            max_interval = 0
        
        return {
            "active_positions": active_count,
            "average_interval": avg_interval,
            "min_interval": min_interval,
            "max_interval": max_interval,
            "total_tasks": len(self.monitor_tasks)
        }
    
    def get_position_interval(self, position_id: str) -> float:
        """获取仓位的当前监控间隔"""
        return self.monitoring_intervals.get(position_id, 0)
    
    def is_monitoring(self, position_id: str) -> bool:
        """检查仓位是否正在监控"""
        return position_id in self.active_positions
