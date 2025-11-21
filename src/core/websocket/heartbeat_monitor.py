"""
🔥 Application-Level Heartbeat Monitor v1.0
职责：检测WebSocket数据流是否停滞（独立于websockets库的ping/pong）

问题背景：
- websockets库的ping/pong机制依赖于事件循环及时处理
- 如果主事件循环被CPU密集操作阻塞（DB写、特征计算），心跳信号会延迟
- 导致"1011 keepalive ping timeout"错误，即使心跳参数已优化

解决方案：
- 应用层监控：记录最后一条消息进入队列的时间
- 独立检查任务：每10秒检查一次，如果60秒无新数据则强制重连
- 防御性重连：不依赖websockets库的内部状态
"""

import asyncio
import time
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class ApplicationLevelHeartbeatMonitor:
    """
    应用层心跳监控器
    
    独立于WebSocket库，在应用层跟踪数据流健康状况。
    用于检测死连接（连接打开但无数据流）。
    """
    
    def __init__(
        self,
        name: str = "HeartbeatMonitor",
        check_interval: int = 10,
        stale_threshold: int = 60,
        on_stale_connection: Optional[Callable] = None
    ):
        """
        初始化应用层心跳监控器
        
        Args:
            name: 监控器名称
            check_interval: 检查间隔（秒）
            stale_threshold: 判定为死连接的阈值（秒）
            on_stale_connection: 检测到死连接时的回调函数
        """
        self.name = name
        self.check_interval = check_interval
        self.stale_threshold = stale_threshold
        self.on_stale_connection = on_stale_connection
        
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.last_message_ts: float = 0
        
        logger.info(f"✅ {self.name} 初始化完成（阈值: {stale_threshold}秒）")
    
    async def start(self) -> None:
        """启动应用层心跳监控"""
        if self.running:
            logger.warning(f"⚠️ {self.name} 已在运行")
            return
        
        self.running = True
        self.last_message_ts = time.time()
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"🫀 {self.name} 已启动")
    
    async def stop(self) -> None:
        """停止应用层心跳监控"""
        self.running = False
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
        logger.info(f"✅ {self.name} 已停止")
    
    def record_message(self) -> None:
        """记录消息到达时间"""
        self.last_message_ts = time.time()
    
    async def _monitor_loop(self) -> None:
        """监控主循环"""
        while self.running:
            try:
                await asyncio.sleep(self.check_interval)
                
                time_since_message = time.time() - self.last_message_ts
                
                if time_since_message > self.stale_threshold:
                    logger.warning(
                        f"🚨 {self.name}: 检测到死连接 "
                        f"({time_since_message:.1f}秒无数据接收)"
                    )
                    
                    # 触发回调（通常是强制重连）
                    if self.on_stale_connection:
                        try:
                            await self.on_stale_connection()
                        except Exception as e:
                            logger.error(
                                f"❌ {self.name}: 死连接处理失败: {e}"
                            )
                    
                    # 重置计时器
                    self.last_message_ts = time.time()
            
            except asyncio.CancelledError:
                logger.info(f"⏸️ {self.name} 监控循环已取消")
                break
            except Exception as e:
                logger.error(f"❌ {self.name} 监控异常: {e}")
                await asyncio.sleep(self.check_interval)
    
    def get_health_status(self) -> dict:
        """获取健康状态"""
        time_since_message = time.time() - self.last_message_ts
        is_healthy = time_since_message < self.stale_threshold
        
        return {
            'running': self.running,
            'healthy': is_healthy,
            'time_since_message': time_since_message,
            'last_message_ts': self.last_message_ts
        }
