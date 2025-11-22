"""
🔥 UnifiedWebSocketFeed v1.0 - 统一的WebSocket基类
职责：提供单一心跳机制、Producer-Consumer架构、自动重连
这是所有Feed（PriceFeed、KlineFeed、AccountFeed）的共同基类。

核心特性：
- 单一心跳机制（Ping Interval: 20s, Ping Timeout: 20s）
- Producer-Consumer架构（asyncio.Queue，容量10000）
- 指数退避重连（5s → 300s）
- 自动错误恢复
- 统一参数和日志
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

try:
    import websockets  # type: ignore
    from websockets.exceptions import ConnectionClosed, ConnectionClosedError  # type: ignore
except ImportError:
    websockets = None  # type: ignore
    ConnectionClosed = Exception  # type: ignore
    ConnectionClosedError = Exception  # type: ignore

from src.utils.logger_factory import get_logger


class UnifiedWebSocketFeed(ABC):
    """
    🔥 UnifiedWebSocketFeed v1.0 - 统一的WebSocket基类
    
    所有Feed（PriceFeed、KlineFeed、AccountFeed）必须继承此类。
    
    设计原则：
    1. 单一心跳机制 - 所有Feed使用相同的ping/pong逻辑
    2. Producer-Consumer模式 - 接收和处理分离
    3. 自动重连 - 指数退避，最多60秒
    4. 标准化错误处理 - 一致的日志和异常处理
    """
    
    # 统一的WebSocket参数
    PING_INTERVAL = 20      # 20秒发送ping
    PING_TIMEOUT = 20       # 20秒等待pong
    RECONNECT_DELAY_MIN = 5  # 最小重连延迟（秒）
    RECONNECT_DELAY_MAX = 300  # 最大重连延迟（秒）
    MESSAGE_QUEUE_SIZE = 10000  # 消息队列大小
    MESSAGE_PROCESS_TIMEOUT = 1.0  # 消息处理超时（秒）
    
    def __init__(self, url: str, feed_name: str):
        """
        初始化UnifiedWebSocketFeed
        
        Args:
            url: WebSocket URL
            feed_name: Feed名称（用于日志）
        """
        self.url = url
        self.name = feed_name
        self.logger = get_logger(f"WS.{feed_name}")
        
        # 连接状态
        self.running = False
        self.connected = False
        self._ws: Optional[Any] = None
        
        # Producer-Consumer队列
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=self.MESSAGE_QUEUE_SIZE)
        self._stop_event = asyncio.Event()
        
        # 任务管理
        self._connection_task: Optional[asyncio.Task] = None
        self._consumer_task: Optional[asyncio.Task] = None
        
        # 连接重试
        self._reconnect_delay = self.RECONNECT_DELAY_MIN
        self._last_message_time = time.time()
        
        # 统计数据
        self.stats = {
            'total_messages': 0,
            'reconnections': 0,
            'connection_errors': 0,
            'processing_errors': 0,
            'last_error': None,
            'uptime_seconds': 0
        }
        
        self._start_time = None
    
    # ==================== 生命周期管理 ====================
    
    async def start(self):
        """启动WebSocket Feed"""
        if self.running:
            self.logger.warning(f"⚠️ {self.name} 已在运行中")
            return
        
        self.logger.info(f"🚀 {self.name} 启动中...")
        self.running = True
        self._stop_event.clear()
        self._start_time = time.time()
        
        # 启动连接循环和消息消费者
        self._connection_task = asyncio.create_task(self._connection_loop())
        self._consumer_task = asyncio.create_task(self._consumer_worker())
        
        self.logger.info(f"✅ {self.name} 已启动（Producer-Consumer架构）")
    
    async def stop(self):
        """停止WebSocket Feed"""
        if not self.running:
            return
        
        self.logger.info(f"⏸️  {self.name} 停止中...")
        self.running = False
        self._stop_event.set()
        
        # 关闭WebSocket连接
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                self.logger.warning(f"⚠️ {self.name} 关闭WebSocket失败: {e}")
        
        # 等待任务完成
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
        
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info(f"✅ {self.name} 已停止")
    
    # ==================== 连接管理 ====================
    
    async def _connection_loop(self):
        """
        连接循环 - 建立WebSocket连接，处理重连逻辑
        """
        while self.running and not self._stop_event.is_set():
            try:
                self.logger.debug(f"📡 {self.name} 连接到 {self.url[:80]}...")
                
                async with websockets.connect(
                    self.url,
                    ping_interval=self.PING_INTERVAL,
                    ping_timeout=self.PING_TIMEOUT,
                    close_timeout=10,
                    max_size=2**20  # 1MB消息缓冲区
                ) as websocket:  # type: ignore
                    self._ws = websocket
                    self.connected = True
                    self._reconnect_delay = self.RECONNECT_DELAY_MIN  # 重置重连延迟
                    
                    self.logger.info(f"✅ {self.name} WebSocket已连接")
                    await self.on_connect(websocket)  # 子类回调
                    
                    # 接收消息并放入队列（Producer）
                    async for message in websocket:
                        if not self.running or self._stop_event.is_set():
                            break
                        
                        # 记录消息接收时间（用于心跳检测）
                        self._last_message_time = time.time()
                        self.stats['total_messages'] += 1
                        
                        # 非阻塞方式放入队列
                        try:
                            self._message_queue.put_nowait(message)
                        except asyncio.QueueFull:
                            self.logger.warning(f"⚠️ {self.name} 消息队列满，丢弃消息")
                            # 不做任何事，简单丢弃这条消息
                
            except (ConnectionClosed, ConnectionClosedError) as e:
                self.connected = False
                error_code = getattr(e, 'rcvd_then_sent', (None, None))[1] if hasattr(e, 'rcvd_then_sent') else None
                
                if error_code in (1011, 1006):
                    self.logger.warning(f"⚠️ {self.name} WebSocket不稳定 ({error_code})，准备重连...")
                else:
                    self.logger.error(f"❌ {self.name} WebSocket连接关闭: {e}")
                
                self.stats['connection_errors'] += 1
                self.stats['last_error'] = str(e)
            
            except Exception as e:
                self.connected = False
                self.logger.error(f"❌ {self.name} 连接错误: {e}")
                self.stats['connection_errors'] += 1
                self.stats['last_error'] = str(e)
            
            finally:
                self._ws = None
                
                # 重连延迟（指数退避）
                if self.running and not self._stop_event.is_set():
                    self.stats['reconnections'] += 1
                    self.logger.warning(
                        f"🔄 {self.name} 将在 {self._reconnect_delay}秒 后重连"
                    )
                    
                    await asyncio.sleep(self._reconnect_delay)
                    
                    # 更新重连延迟（指数退避，最多300秒）
                    self._reconnect_delay = min(
                        self._reconnect_delay * 1.5,
                        self.RECONNECT_DELAY_MAX
                    )
    
    # ==================== 消息处理 (Consumer) ====================
    
    async def _consumer_worker(self):
        """
        消费者工作线程 - 从队列取消息，调用process_message处理
        """
        self.logger.info(f"📨 {self.name} 消费者工作线程已启动")
        
        while self.running and not self._stop_event.is_set():
            try:
                # 从队列取消息（带超时防止卡住）
                try:
                    message = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=self.MESSAGE_PROCESS_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    # 队列空，继续等待
                    continue
                
                # 调用子类的消息处理方法
                try:
                    await self.process_message(message)
                except Exception as e:
                    self.logger.error(f"❌ {self.name} 消息处理异常: {e}")
                    self.stats['processing_errors'] += 1
                
                # 标记消息已处理
                self._message_queue.task_done()
            
            except asyncio.CancelledError:
                self.logger.info(f"✅ {self.name} 消费者已停止")
                break
            
            except Exception as e:
                self.logger.error(f"❌ {self.name} 消费者异常: {e}")
                await asyncio.sleep(1)
    
    # ==================== 抽象方法（子类必须实现） ====================
    
    @abstractmethod
    async def on_connect(self, ws) -> None:
        """
        连接成功后的回调（子类实现）
        
        Args:
            ws: WebSocket连接对象
        """
        pass
    
    @abstractmethod
    async def process_message(self, raw_msg: str) -> None:
        """
        处理单条消息（子类实现）
        
        Args:
            raw_msg: 原始WebSocket消息（JSON字符串）
        
        注意：这个方法在消费者线程中调用，应该尽可能快地执行
        """
        pass
    
    # ==================== 工具方法 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计数据"""
        uptime = int(time.time() - self._start_time) if self._start_time else 0
        return {
            **self.stats,
            'name': self.name,
            'connected': self.connected,
            'uptime_seconds': uptime,
            'queue_size': self._message_queue.qsize()
        }
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connected
    
    def get_last_message_time(self) -> float:
        """获取最后一条消息接收时间"""
        return self._last_message_time
    
    @staticmethod
    def get_server_timestamp_ms(data: dict, key: str) -> int:
        """
        从数据中获取服务器时间戳（毫秒）
        
        Args:
            data: 数据字典
            key: 时间戳字段名
        
        Returns:
            时间戳（毫秒），如果不存在返回0
        """
        try:
            ts = data.get(key, 0)
            if isinstance(ts, str):
                return int(ts)
            return int(ts)
        except Exception:
            return 0
    
    @staticmethod
    def get_local_timestamp_ms() -> int:
        """获取本地时间戳（毫秒）"""
        return int(time.time() * 1000)
    
    @staticmethod
    def calculate_latency_ms(server_ts: int, local_ts: int) -> int:
        """
        计算网络延迟（毫秒）
        
        Args:
            server_ts: 服务器时间戳（毫秒）
            local_ts: 本地接收时间戳（毫秒）
        
        Returns:
            延迟（毫秒），如果无效返回0
        """
        if server_ts <= 0:
            return 0
        
        latency = local_ts - server_ts
        
        # 延迟应该在0-5000ms之间（>5秒表示时钟差异）
        if latency < 0 or latency > 5000:
            return 0
        
        return latency
