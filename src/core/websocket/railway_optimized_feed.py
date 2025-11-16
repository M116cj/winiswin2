"""
Railway优化WebSocket Feed - 云环境专用稳定连接
职责：适配Railway网络特性的WebSocket管理（宽松健康检查、智能重连）
Created: 2025-11-12 v4.3
"""

import asyncio
from src.utils.logger_factory import get_logger
import time
from typing import Optional, Dict, Any
from datetime import datetime

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK
except ImportError:
    websockets = None
    ConnectionClosed = Exception
    ConnectionClosedError = Exception
    ConnectionClosedOK = Exception

logger = get_logger(__name__)


class RailwayOptimizedFeed:
    """
    Railway云环境优化的WebSocket Feed
    
    特性：
    1. Grace Period（宽容期）：新连接后2分钟内宽松检查
    2. 智能重连：指数退避 + 断路器机制
    3. 网络波动容忍：允许短暂断线
    4. 连接池管理：优先复用现有连接
    5. Railway专用超时：适配云环境网络延迟
    """
    
    def __init__(
        self,
        name: str,
        url: str,
        grace_period: int = 180,  # 3分钟宽容期（Railway网络稳定后）
        max_reconnect_attempts: int = 10,
        base_reconnect_delay: float = 2.0,
        max_reconnect_delay: float = 60.0
    ):
        """
        初始化Railway优化Feed
        
        Args:
            name: Feed名称
            url: WebSocket URL
            grace_period: 宽容期（秒）- 新连接后多久内宽松检查
            max_reconnect_attempts: 最大重连次数
            base_reconnect_delay: 基础重连延迟（秒）
            max_reconnect_delay: 最大重连延迟（秒）
        """
        self.name = name
        self.url = url
        self.grace_period = grace_period
        self.max_reconnect_attempts = max_reconnect_attempts
        self.base_reconnect_delay = base_reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        
        # 连接状态
        self.ws: Optional[Any] = None
        self.is_connected_flag = False
        self.running = False
        
        # 时间戳追踪
        self.last_successful_connection = 0
        self.last_message_time = 0
        self.last_pong_time = 0
        self.connection_established_at = 0
        
        # 重连控制
        self.reconnect_attempts = 0
        self.consecutive_failures = 0
        
        # Railway优化参数
        self.connection_params = {
            'ping_interval': 20,  # Binance服务器20秒ping
            'ping_timeout': 15,   # Railway: 增加到15秒（云环境延迟）
            'close_timeout': 10,
            'max_queue': 2000,    # Railway: 更大队列应对突发流量
            'read_limit': 2 ** 20,  # 1MB
            'write_limit': 2 ** 20,
        }
        
        # 健康检查参数（Railway优化）
        self.health_check_params = {
            'grace_period_seconds': grace_period,
            'ping_timeout_extended': 30.0,  # 健康检查用更长超时
            'allow_temporary_disconnect': True,
            'min_uptime_for_strict_check': 300,  # 5分钟后才严格检查
        }
        
        logger.info(f"✅ {name} Railway优化Feed初始化")
        logger.info(f"   🌐 URL: {url}")
        logger.info(f"   ⏰ 宽容期: {grace_period}秒")
        logger.info(f"   🔄 最大重连: {max_reconnect_attempts}次")
        logger.info(f"   ⏱️  Ping超时: {self.connection_params['ping_timeout']}秒")
    
    async def connect(self) -> bool:
        """
        建立Railway优化的WebSocket连接
        
        Returns:
            是否成功连接
        """
        if not websockets:
            logger.error(f"❌ {self.name}: websockets模块未安装")
            return False
        
        try:
            logger.info(f"🚀 {self.name}: 连接 {self.url}")
            
            # Railway优化连接参数
            self.ws = await websockets.connect(
                self.url,
                ping_interval=20,
                ping_timeout=15,
                close_timeout=10,
                max_size=10 * 1024 * 1024
            )
            
            # 更新状态
            current_time = time.time()
            self.is_connected_flag = True
            self.last_successful_connection = current_time
            self.connection_established_at = current_time
            self.last_message_time = current_time
            self.last_pong_time = current_time
            self.consecutive_failures = 0
            self.reconnect_attempts = 0
            
            logger.info(f"✅ {self.name}: 连接成功（宽容期: {self.grace_period}秒）")
            return True
            
        except Exception as e:
            self.consecutive_failures += 1
            logger.warning(
                f"⚠️ {self.name}: 连接失败 "
                f"(尝试 {self.consecutive_failures}): {e}"
            )
            return False
    
    async def robust_health_check(self) -> bool:
        """
        Railway优化的健康检查（宽松容错）
        
        Returns:
            是否健康
        """
        current_time = time.time()
        
        # 1. 宽容期检查：新连接后宽松对待
        time_since_connection = current_time - self.connection_established_at
        in_grace_period = time_since_connection < self.grace_period
        
        if in_grace_period:
            logger.debug(
                f"🏥 {self.name}: 宽容期 "
                f"({time_since_connection:.0f}s/{self.grace_period}s) - 健康检查宽松"
            )
            # 宽容期只检查基本连接
            if self.ws and not self.ws.closed:
                return True
        
        # 2. 检查WebSocket对象是否存在且未关闭
        if not self.ws or self.ws.closed:
            logger.warning(f"🏥 {self.name}: WebSocket已关闭")
            self.is_connected_flag = False
            return False
        
        # 3. Railway优化：检查最近消息时间（允许5分钟无消息）
        time_since_last_message = current_time - self.last_message_time
        if time_since_last_message < 300:  # 5分钟
            logger.debug(f"✅ {self.name}: 最近有消息 ({time_since_last_message:.0f}s前)")
            return True
        
        # 4. 主动Ping检查（使用延长超时）
        try:
            pong_waiter = await asyncio.wait_for(
                self.ws.ping(),
                timeout=self.health_check_params['ping_timeout_extended']
            )
            await pong_waiter
            
            self.last_pong_time = current_time
            self.last_successful_connection = current_time
            logger.debug(f"✅ {self.name}: Ping/Pong成功")
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"🏥 {self.name}: Ping超时（{self.health_check_params['ping_timeout_extended']}s）")
            self.is_connected_flag = False
            return False
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as e:
            logger.warning(f"🏥 {self.name}: 连接已关闭 - {type(e).__name__}")
            self.is_connected_flag = False
            return False
    
    async def smart_reconnect(self) -> bool:
        """
        智能重连（指数退避 + 断路器）
        
        Returns:
            重连是否成功
        """
        # 1. 检查是否超过最大重连次数
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                f"🔌 {self.name}: 达到最大重连次数 "
                f"({self.max_reconnect_attempts})"
            )
            return False
        
        # 2. 计算指数退避延迟
        delay = min(
            self.base_reconnect_delay * (2 ** self.reconnect_attempts),
            self.max_reconnect_delay
        )
        
        self.reconnect_attempts += 1
        logger.info(
            f"🔄 {self.name}: 重连中... "
            f"延迟 {delay:.1f}s (尝试 {self.reconnect_attempts}/{self.max_reconnect_attempts})"
        )
        
        # 3. 等待后重连
        await asyncio.sleep(delay)
        
        try:
            success = await self.connect()
            if success:
                logger.info(f"✅ {self.name}: 重连成功")
                self.reconnect_attempts = 0  # 重置计数器
            return success
        except Exception as e:
            logger.warning(f"⚠️ {self.name}: 重连失败 - {e}")
            return False
    
    def is_connected(self) -> bool:
        """
        检查连接状态（Railway优化）
        
        Returns:
            是否已连接
        """
        # 1. 基本标志检查
        if not self.is_connected_flag:
            return False
        
        # 2. WebSocket对象检查
        if not self.ws or self.ws.closed:
            return False
        
        # 3. Railway优化：最近有成功交互视为已连接（5分钟内）
        current_time = time.time()
        if current_time - self.last_successful_connection < 300:
            return True
        
        return self.is_connected_flag
    
    async def receive_message(self, timeout: float = 30.0) -> Optional[Dict]:
        """
        接收消息（Railway优化错误处理）
        
        Args:
            timeout: 接收超时（秒）
            
        Returns:
            消息内容或None
        """
        try:
            if not self.ws or self.ws.closed:
                return None
            
            message = await asyncio.wait_for(
                self.ws.recv(),
                timeout=timeout
            )
            
            # 更新时间戳
            self.last_message_time = time.time()
            
            return message
            
        except asyncio.TimeoutError:
            # Railway: 超时不算错误（低流量正常）
            logger.debug(f"⏱️ {self.name}: 接收超时（正常，低流量）")
            return None
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as e:
            logger.warning(f"🔌 {self.name}: 连接关闭 - {type(e).__name__}")
            self.is_connected_flag = False
            return None
    
    async def close(self) -> None:
        """关闭连接"""
        if self.ws:
            try:
                await self.ws.close()
                logger.info(f"🔌 {self.name}: 连接已关闭")
            except Exception as e:
                logger.warning(f"⚠️ {self.name}: 关闭错误 - {e}")
            finally:
                self.ws = None
                self.is_connected_flag = False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        current_time = time.time()
        return {
            'name': self.name,
            'connected': self.is_connected(),
            'uptime_seconds': current_time - self.connection_established_at if self.connection_established_at else 0,
            'reconnect_attempts': self.reconnect_attempts,
            'consecutive_failures': self.consecutive_failures,
            'time_since_last_message': current_time - self.last_message_time if self.last_message_time else -1,
            'in_grace_period': (current_time - self.connection_established_at) < self.grace_period if self.connection_established_at else False,
        }
