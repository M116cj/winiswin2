"""
Optimized WebSocket Feed v3.29+ - 优化心跳和重连机制
职责：稳定的WebSocket连接管理（Railway环境优化）
"""

import asyncio
from src.utils.logger_factory import get_logger
from typing import Optional
from datetime import datetime
import time

try:
    import websockets  # type: ignore
    from websockets.exceptions import ConnectionClosed  # type: ignore
except ImportError:
    websockets = None  # type: ignore
    ConnectionClosed = Exception  # type: ignore

logger = get_logger(__name__)


class OptimizedWebSocketFeed:
    """
    优化版WebSocket Feed v3.32+
    
    特性：
    1. 符合Binance规范的ping/pong机制（服务器ping，客户端pong）
    2. 指数退避算法的智能重连机制
    3. 连接健康监控任务
    4. 心跳超时检测和自动恢复
    5. 优化连接参数（close_timeout, max_size, read/write limits）
    6. 连接状态追踪（last_pong, reconnect_count）
    """
    
    def __init__(
        self,
        name: str = "WebSocketFeed",
        ping_interval: Optional[int] = None,
        ping_timeout: int = 120,
        max_reconnect_delay: int = 300,
        health_check_interval: int = 60
    ):
        """
        初始化优化版WebSocket Feed
        
        Args:
            name: Feed名称
            ping_interval: 心跳间隔（None=禁用客户端ping，让服务器发送）
            ping_timeout: 心跳超时（秒，默认120）
            max_reconnect_delay: 最大重连延迟（秒）
            health_check_interval: 健康检查间隔（秒）
        """
        self.name = name
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.max_reconnect_delay = max_reconnect_delay
        self.health_check_interval = health_check_interval
        
        # 连接状态
        self.ws = None
        self.running = False
        self.connected = False
        
        # 心跳监控
        self.last_pong_time: float = 0
        self.last_message_time: float = 0
        
        # 重连控制
        self.reconnect_count: int = 0
        self.consecutive_failures: int = 0
        self.last_reconnect_time: float = 0
        
        # 优化的连接参数（符合Binance规范）
        self.connection_params = {
            'ping_interval': ping_interval,
            'ping_timeout': ping_timeout,
            'close_timeout': 10,
            'max_size': 10 * 1024 * 1024
        }
        
        # 任务
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.health_check_task: Optional[asyncio.Task] = None
        
        # 统计
        self.stats = {
            'total_messages': 0,
            'total_errors': 0,
            'total_reconnects': 0,
            'uptime_seconds': 0,
            'avg_latency_ms': 0
        }
        
        logger.info("=" * 80)
        logger.info(f"✅ {name} 初始化完成（v3.32 Binance规范版）")
        logger.info(f"   💓 Ping机制: 服务器ping（每20秒）+ 客户端自动pong")
        logger.info(f"   ⏱️  Ping超时: {ping_timeout}秒")
        logger.info(f"   🔄 指数退避: 1s → {max_reconnect_delay}s")
        logger.info(f"   🏥 健康检查: 每{health_check_interval}秒")
        logger.info("=" * 80)
    
    async def connect(self, url: str) -> bool:
        """
        建立WebSocket连接（带指数退避重连）
        
        Args:
            url: WebSocket URL
            
        Returns:
            是否成功连接
        """
        if not websockets:
            logger.error(f"❌ {self.name}: websockets模块未安装")
            return False
        
        attempt = 0
        max_initial_attempts = 5  # 初始阶段最多尝试5次
        
        while self.running:
            try:
                # 计算退避延迟（指数退避算法）
                delay = min(
                    self.max_reconnect_delay,
                    (2 ** min(attempt, 8)) * 1.0  # 限制最大指数，避免过长延迟
                )
                
                if attempt > 0:
                    logger.info(
                        f"🔄 {self.name}: 重连尝试 #{attempt} "
                        f"(延迟{delay:.1f}秒)..."
                    )
                    await asyncio.sleep(delay)
                
                # 建立连接
                logger.info(f"🔌 {self.name}: 正在连接 {url}...")
                
                self.ws = await asyncio.wait_for(
                    websockets.connect(url, **self.connection_params),
                    timeout=30
                )
                
                self.connected = True
                self.last_pong_time = time.time()
                self.last_message_time = time.time()
                self.reconnect_count += 1
                self.stats['total_reconnects'] += 1
                self.consecutive_failures = 0
                
                logger.info(f"✅ {self.name}: 连接成功（尝试#{attempt + 1}）")
                
                # 启动心跳监控
                if not self.heartbeat_task or self.heartbeat_task.done():
                    self.heartbeat_task = asyncio.create_task(
                        self._heartbeat_monitor()
                    )
                
                return True
                
            except asyncio.TimeoutError:
                logger.error(f"❌ {self.name}: 连接超时（尝试#{attempt + 1}）")
                self.consecutive_failures += 1
                attempt += 1
                
                # 初始阶段失败太多次则放弃
                if attempt >= max_initial_attempts and self.reconnect_count == 0:
                    logger.error(
                        f"🔴 {self.name}: 初始连接失败{max_initial_attempts}次，"
                        f"可能是网络问题或Binance限流，暂时跳过此分片"
                    )
                    self.connected = False
                    return False
                
            except Exception as e:
                logger.error(f"❌ {self.name}: 连接失败: {e}（尝试#{attempt + 1}）")
                self.consecutive_failures += 1
                self.stats['total_errors'] += 1
                attempt += 1
                
                # 初始阶段失败太多次则放弃
                if attempt >= max_initial_attempts and self.reconnect_count == 0:
                    logger.error(
                        f"🔴 {self.name}: 初始连接失败{max_initial_attempts}次，"
                        f"错误: {e}，暂时跳过此分片"
                    )
                    self.connected = False
                    return False
                
                # 如果连续失败过多，增加延迟
                if self.consecutive_failures > 5:
                    logger.warning(
                        f"⚠️ {self.name}: 连续失败{self.consecutive_failures}次，"
                        f"进入长延迟模式"
                    )
                    await asyncio.sleep(60)
        
        return False
    
    async def _heartbeat_monitor(self) -> None:
        """
        心跳监控循环（v3.32：已禁用，websockets库自动处理ping/pong）
        
        注意：Binance服务器每20秒发送ping，websockets库自动响应pong。
        如果ping_timeout秒内未收到服务器ping，连接会自动断开。
        """
        logger.info(f"💓 {self.name}: 心跳监控已禁用（依赖websockets库自动处理）")
        return
    
    async def start_health_check(self) -> None:
        """启动健康检查任务"""
        if self.health_check_task and not self.health_check_task.done():
            logger.warning(f"⚠️ {self.name}: 健康检查已在运行")
            return
        
        self.health_check_task = asyncio.create_task(
            self._health_check_loop()
        )
        logger.info(f"🏥 {self.name}: 健康检查任务已启动")
    
    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        while self.running:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                health_status = self.get_health_status()
                
                if health_status['status'] == 'unhealthy':
                    logger.warning(
                        f"🏥 {self.name}: 健康检查失败 - "
                        f"{health_status['reason']}"
                    )
                    
                    # 触发重连
                    if self.ws:
                        await self.ws.close()
                        self.connected = False
                
            except Exception as e:
                logger.error(f"❌ {self.name}: 健康检查错误: {e}")
    
    def get_health_status(self) -> dict:
        """
        获取连接健康状态
        
        Returns:
            健康状态字典
        """
        time_since_message = time.time() - self.last_message_time
        time_since_pong = time.time() - self.last_pong_time
        
        if not self.connected:
            return {
                'status': 'unhealthy',
                'reason': 'not_connected',
                'connected': False
            }
        
        if time_since_message > 120:  # 2分钟无消息
            return {
                'status': 'unhealthy',
                'reason': 'no_messages',
                'time_since_message': time_since_message
            }
        
        if time_since_pong > self.ping_timeout:
            return {
                'status': 'unhealthy',
                'reason': 'ping_timeout',
                'time_since_pong': time_since_pong
            }
        
        return {
            'status': 'healthy',
            'connected': True,
            'time_since_message': time_since_message,
            'time_since_pong': time_since_pong,
            'reconnect_count': self.reconnect_count
        }
    
    async def receive_message(self) -> Optional[str]:
        """
        接收WebSocket消息（带异常处理）
        
        Returns:
            消息内容或None
        """
        if not self.ws:
            return None
        
        # 检查连接是否关闭（安全访问closed属性）
        try:
            if hasattr(self.ws, 'closed') and self.ws.closed:
                return None
        except AttributeError:
            pass
        
        try:
            message = await asyncio.wait_for(
                self.ws.recv(),
                timeout=self.ping_timeout
            )
            
            self.last_message_time = time.time()
            self.stats['total_messages'] += 1
            
            return message
            
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ {self.name}: 接收消息超时")
            return None
            
        except ConnectionClosed:
            logger.warning(f"⚠️ {self.name}: 连接已关闭")
            self.connected = False
            return None
            
        except Exception as e:
            logger.error(f"❌ {self.name}: 接收消息失败: {e}")
            self.stats['total_errors'] += 1
            return None
    
    async def shutdown(self) -> None:
        """优雅关闭"""
        logger.info(f"🔄 {self.name}: 开始关闭...")
        
        self.running = False
        self.connected = False
        
        # 取消任务
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        if self.health_check_task:
            self.health_check_task.cancel()
        
        # 关闭连接
        if self.ws:
            await self.ws.close()
        
        logger.info(f"✅ {self.name}: 已关闭")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self.stats,
            'connected': self.connected,
            'reconnect_count': self.reconnect_count,
            'consecutive_failures': self.consecutive_failures
        }
