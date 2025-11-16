"""
异步错误处理装饰器 (v3.13.0 策略3)
职责：统一 Binance API 和通用错误处理，减少200+行重复代码

✅ 为什么使用装饰器：
1. 消除重复的 try/except 代码
2. 统一日志格式
3. 集中重试逻辑
4. 未来添加监控只需修改装饰器

使用示例：
    @handle_binance_errors(operation_name="获取K线", retry=True)
    async def get_klines(self, symbol, interval):
        # 业务逻辑，无需 try/except
        return await self._request('GET', '/fapi/v1/klines', ...)
"""

from src.utils.logger_factory import get_logger
import asyncio
from functools import wraps
from typing import Callable, Optional, Any, TypeVar

logger = get_logger(__name__)

T = TypeVar('T')


def handle_binance_errors(
    func: Optional[Callable] = None,
    *,
    operation_name: Optional[str] = None,
    retry: bool = False,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    default_return: Any = None
):
    """
    Binance API 异步错误处理装饰器
    
    Args:
        func: 被装饰的异步函数
        operation_name: 操作名称（用于日志）
        retry: 是否自动重试
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        default_return: 错误时的默认返回值
    
    处理的错误类型：
        - HTTP 429: 限流（自动重试）
        - HTTP 451: 地理限制（不重试，记录详细信息）
        - HTTP 503/504: 服务不可用（自动重试）
        - 网络错误: 自动重试
    
    使用示例：
        @handle_binance_errors(operation_name="下单", retry=True, max_retries=5)
        async def place_order(self, symbol, side, quantity):
            return await self._request('POST', '/fapi/v1/order', ...)
    """
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or f.__name__
            attempts = 0
            last_exception = None
            
            while attempts <= (max_retries if retry else 0):
                try:
                    result = await f(*args, **kwargs)
                    
                    # 重试成功后记录日志
                    if attempts > 0:
                        logger.info(
                            f"✅ [{op_name}] 重试成功（第{attempts}次重试）"
                        )
                    
                    return result
                
                except Exception as e:
                    last_exception = e
                    attempts += 1
                    
                    # 解析错误类型
                    error_type = type(e).__name__
                    error_msg = str(e)
                    
                    # 检查HTTP状态码（如果有）
                    status_code = None
                    if hasattr(e, 'status') or hasattr(e, 'status_code'):
                        status_code = getattr(e, 'status', None) or getattr(e, 'status_code', None)
                    
                    # 特殊处理 HTTP 451（地理限制）
                    if status_code == 451:
                        logger.error(
                            f"❌ [{op_name}] Binance API 地理限制 (HTTP 451)\n"
                            f"   📍 当前IP地址被Binance限制\n"
                            f"   ✅ 解决方案：部署到Railway或其他支持的云平台\n"
                            f"   ⚠️  Replit环境无法访问Binance API"
                        )
                        return default_return
                    
                    # 判断是否应该重试
                    retryable_status_codes = [429, 503, 504, -1001, -1003, -1021]
                    should_retry = (
                        retry and 
                        attempts <= max_retries and
                        (status_code in retryable_status_codes or 'timeout' in error_msg.lower() or 'network' in error_msg.lower())
                    )
                    
                    if should_retry:
                        logger.warning(
                            f"⚠️  [{op_name}] {error_type}: {error_msg}\n"
                            f"   🔄 将在{retry_delay}秒后重试（{attempts}/{max_retries}）"
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        # 记录详细错误信息
                        logger.error(
                            f"❌ [{op_name}] {error_type}: {error_msg}",
                            exc_info=True
                        )
                        
                        if retry and attempts > max_retries:
                            logger.error(
                                f"❌ [{op_name}] 已达最大重试次数（{max_retries}），放弃操作"
                            )
                        
                        return default_return
            
            # 所有重试都失败
            logger.error(
                f"❌ [{op_name}] 所有重试均失败，最后错误: {last_exception}"
            )
            return default_return
        
        return wrapper
    
    # 支持两种调用方式
    if func is None:
        # 带参数：@handle_binance_errors(retry=True)
        return decorator
    else:
        # 无参数：@handle_binance_errors
        return decorator(func)


def handle_general_errors(
    func: Optional[Callable] = None,
    *,
    operation_name: Optional[str] = None,
    log_level: str = "error",
    default_return: Any = None,
    raise_exception: bool = False
):
    """
    通用异步错误处理装饰器（非Binance API）
    
    适用于：数据处理、ML预测、文件操作等
    
    Args:
        func: 被装饰的异步函数
        operation_name: 操作名称（用于日志）
        log_level: 日志级别（'error', 'warning', 'info'）
        default_return: 错误时的默认返回值
        raise_exception: 是否重新抛出异常
    
    使用示例：
        @handle_general_errors(operation_name="ML预测", default_return={})
        async def predict(self, features):
            return await model.predict_async(features)
    """
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or f.__name__
            
            try:
                return await f(*args, **kwargs)
            except Exception as e:
                error_msg = f"[{op_name}] 操作失败: {type(e).__name__}: {str(e)}"
                
                if log_level == "error":
                    logger.error(f"❌ {error_msg}", exc_info=True)
                elif log_level == "warning":
                    logger.warning(f"⚠️  {error_msg}")
                else:
                    logger.info(f"ℹ️  {error_msg}")
                
                if raise_exception:
                    raise
                
                return default_return
        
        return wrapper
    
    if func is None:
        return decorator
    else:
        return decorator(func)


def rate_limit(calls_per_second: float = 10.0):
    """
    异步速率限制装饰器
    
    Args:
        calls_per_second: 每秒允许的最大调用次数
    
    使用示例：
        @rate_limit(calls_per_second=5.0)
        async def get_ticker(self, symbol):
            ...
    """
    min_interval = 1.0 / calls_per_second
    last_call_time = {'time': 0.0}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 计算需要等待的时间
            import time
            elapsed = time.time() - last_call_time['time']
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            
            last_call_time['time'] = time.time()
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def timeout_handler(seconds: float):
    """
    异步超时处理装饰器
    
    Args:
        seconds: 超时时间（秒）
    
    使用示例：
        @timeout_handler(seconds=30.0)
        async def long_running_task(self):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                logger.error(f"❌ [{func.__name__}] 操作超时（{seconds}秒）")
                raise
        
        return wrapper
    
    return decorator


def cache_async_result(ttl_seconds: int = 60):
    """
    异步结果缓存装饰器
    
    Args:
        ttl_seconds: 缓存有效期（秒）
    
    使用示例：
        @cache_async_result(ttl_seconds=300)
        async def get_account_info(self):
            # 5分钟内重复调用直接返回缓存结果
            ...
    """
    cache = {}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import time
            # 生成缓存键
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # 检查缓存
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if time.time() - timestamp < ttl_seconds:
                    return result
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 存入缓存
            cache[cache_key] = (result, time.time())
            
            return result
        
        return wrapper
    
    return decorator
