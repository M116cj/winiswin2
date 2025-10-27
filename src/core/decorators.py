"""
统一错误处理装饰器（v3.13.0 轻量化策略3）

✅ 为什么使用装饰器统一错误处理：
1. 消除200+行重复的 try/except 代码
2. 统一日志格式，易于调试和监控
3. 未来添加监控只需修改装饰器（单点修改）
4. 提升代码可读性（业务逻辑与错误处理分离）

使用示例：
    @handle_binance_errors
    def get_klines(self, symbol, interval):
        # 业务逻辑，无需 try/except
        return self.client.futures_klines(...)
    
    @handle_binance_errors(operation_name="下单", retry=True)
    def place_order(self, symbol, side, quantity):
        # 自动重试的下单逻辑
        return self.client.futures_create_order(...)
"""

import logging
import time
from functools import wraps
from typing import Callable, Optional, Any
from binance.exceptions import BinanceAPIException, BinanceRequestException

logger = logging.getLogger(__name__)


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
    统一 Binance API 错误处理装饰器
    
    Args:
        func: 被装饰的函数（自动传入）
        operation_name: 操作名称（用于日志），默认使用函数名
        retry: 是否启用自动重试（默认False）
        max_retries: 最大重试次数（默认3次）
        retry_delay: 重试延迟（秒，默认1.0）
        default_return: 错误时的默认返回值（默认None）
    
    使用方式：
        # 简单用法（无参数）
        @handle_binance_errors
        def get_klines(...):
            ...
        
        # 带参数用法
        @handle_binance_errors(operation_name="下单", retry=True, max_retries=5)
        def place_order(...):
            ...
    """
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 确定操作名称
            op_name = operation_name or f.__name__
            
            # 重试逻辑
            attempts = 0
            last_exception = None
            
            while attempts <= (max_retries if retry else 0):
                try:
                    result = f(*args, **kwargs)
                    
                    # 如果之前有重试，成功后记录日志
                    if attempts > 0:
                        logger.info(
                            f"✅ [{op_name}] 重试成功（第{attempts}次重试）"
                        )
                    
                    return result
                    
                except BinanceAPIException as e:
                    last_exception = e
                    attempts += 1
                    
                    # 特殊处理 HTTP 451（地理限制）
                    if e.status_code == 451:
                        logger.error(
                            f"❌ [{op_name}] Binance API 地理位置限制 (HTTP 451)\n"
                            f"   📍 此错误表示当前IP地址被Binance限制\n"
                            f"   ✅ 解决方案：请将系统部署到Railway或其他支持的云平台\n"
                            f"   ⚠️  Replit环境无法访问Binance API"
                        )
                        return default_return
                    
                    # 判断是否应该重试
                    should_retry = (
                        retry and 
                        attempts <= max_retries and
                        e.status_code in [429, 503, 504, -1001, -1003]  # 限流、服务不可用、超时
                    )
                    
                    if should_retry:
                        logger.warning(
                            f"⚠️  [{op_name}] Binance API 错误 {e.status_code}: {e.message}\n"
                            f"   🔄 将在{retry_delay}秒后重试（{attempts}/{max_retries}）"
                        )
                        time.sleep(retry_delay)
                    else:
                        logger.error(
                            f"❌ [{op_name}] Binance API 错误 {e.status_code}: {e.message}\n"
                            f"   Code: {e.code}\n"
                            f"   Endpoint: {getattr(e, 'endpoint', 'unknown')}\n"
                            f"   Params: {getattr(e, 'params', {})}"
                        )
                        
                        if retry and attempts > max_retries:
                            logger.error(
                                f"❌ [{op_name}] 已达最大重试次数（{max_retries}），放弃操作"
                            )
                        
                        return default_return
                
                except BinanceRequestException as e:
                    last_exception = e
                    attempts += 1
                    
                    should_retry = retry and attempts <= max_retries
                    
                    if should_retry:
                        logger.warning(
                            f"⚠️  [{op_name}] 网络请求失败: {str(e)}\n"
                            f"   🔄 将在{retry_delay}秒后重试（{attempts}/{max_retries}）"
                        )
                        time.sleep(retry_delay)
                    else:
                        logger.error(
                            f"❌ [{op_name}] 网络请求失败: {str(e)}"
                        )
                        return default_return
                
                except Exception as e:
                    # 未预期的错误，不重试
                    logger.error(
                        f"❌ [{op_name}] 未预期的错误: {type(e).__name__}: {str(e)}",
                        exc_info=True
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
        # 带参数调用：@handle_binance_errors(retry=True)
        return decorator
    else:
        # 无参数调用：@handle_binance_errors
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
    通用错误处理装饰器（非Binance API）
    
    适用于：数据处理、ML预测、文件操作等
    
    Args:
        func: 被装饰的函数
        operation_name: 操作名称（用于日志）
        log_level: 日志级别（'error', 'warning', 'info'）
        default_return: 错误时的默认返回值
        raise_exception: 是否重新抛出异常（默认False）
    
    使用示例：
        @handle_general_errors(operation_name="ML预测", default_return={})
        def predict(self, features):
            # 业务逻辑
            return model.predict(features)
    """
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            op_name = operation_name or f.__name__
            
            try:
                return f(*args, **kwargs)
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
    简单的速率限制装饰器
    
    Args:
        calls_per_second: 每秒允许的最大调用次数
    
    使用示例：
        @rate_limit(calls_per_second=5.0)
        def get_ticker(self, symbol):
            ...
    """
    min_interval = 1.0 / calls_per_second
    last_call_time = {'time': 0.0}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 计算需要等待的时间
            elapsed = time.time() - last_call_time['time']
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            
            last_call_time['time'] = time.time()
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator
