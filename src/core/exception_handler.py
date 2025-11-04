"""
🛡️ v3.23+ 統一異常處理策略
提供裝飾器規範化API調用、關鍵區段的異常處理

新增功能：
- 同步/異步雙模式支持
- 智能重試機制（指數退避）
- 資源清理保證
- 標準化錯誤響應
"""

import functools
import asyncio
import aiohttp
import json
import logging
import time
from typing import Callable, Any, Optional, Union
from inspect import iscoroutinefunction

logger = logging.getLogger(__name__)


class ExceptionHandler:
    """v3.23+ 統一的異常處理策略（同步/異步雙模式）"""
    
    @staticmethod
    def async_api_call(func: Callable) -> Callable:
        """
        API調用異常處理裝飾器
        
        用於包裝所有外部API調用，提供：
        - 超時處理
        - 網絡錯誤處理
        - JSON解析錯誤處理
        - 詳細錯誤日誌
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except asyncio.TimeoutError as e:
                logger.error(f"⏰ API調用超時: {func.__name__}")
                raise
            except aiohttp.ClientError as e:
                logger.error(f"🌐 網絡錯誤: {func.__name__} - {e}")
                raise
            except json.JSONDecodeError as e:
                logger.error(f"📄 JSON解析錯誤: {func.__name__} - {e}")
                raise
            except (KeyboardInterrupt, asyncio.CancelledError):
                logger.info(f"⚠️ 用戶中斷或任務取消: {func.__name__}")
                raise
            except Exception as e:
                logger.error(f"❌ 未預期錯誤: {func.__name__} - {type(e).__name__}: {e}")
                raise
        return wrapper
    
    @staticmethod
    def critical_section(max_retries: int = 3, backoff_base: float = 2.0) -> Callable:
        """
        🔥 v3.23+ 關鍵區段異常處理裝飾器工廠（同步/異步雙模式）
        
        用於包裝關鍵操作，提供：
        - 自動重試機制（指數退避）
        - 系統級異常不捕獲（KeyboardInterrupt, CancelledError）
        - 關鍵失敗日誌
        - 同步和異步函數都支持
        
        Args:
            max_retries: 最大重試次數
            backoff_base: 退避基數（秒）
        """
        def decorator(func: Callable) -> Callable:
            if iscoroutinefunction(func):
                # 異步版本
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs) -> Any:
                    last_exception = None
                    
                    for attempt in range(max_retries):
                        try:
                            return await func(*args, **kwargs)
                        except (asyncio.CancelledError, KeyboardInterrupt):
                            logger.info(f"⚠️ 關鍵操作被中斷: {func.__name__}")
                            raise
                        except Exception as e:
                            last_exception = e
                            
                            if attempt == max_retries - 1:
                                logger.critical(
                                    f"💥 關鍵操作失敗（{max_retries}次重試後）: {func.__name__}\n"
                                    f"   錯誤類型: {type(e).__name__}\n"
                                    f"   錯誤信息: {e}"
                                )
                                raise
                            else:
                                backoff_time = backoff_base ** attempt
                                logger.warning(
                                    f"⚠️ 關鍵操作失敗，{backoff_time:.1f}秒後重試 "
                                    f"({attempt + 1}/{max_retries}): {func.__name__} - {e}"
                                )
                                await asyncio.sleep(backoff_time)
                    
                    if last_exception:
                        raise last_exception
                        
                return async_wrapper
            else:
                # 同步版本
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs) -> Any:
                    last_exception = None
                    
                    for attempt in range(max_retries):
                        try:
                            return func(*args, **kwargs)
                        except KeyboardInterrupt:
                            logger.info(f"⚠️ 關鍵操作被中斷: {func.__name__}")
                            raise
                        except Exception as e:
                            last_exception = e
                            
                            if attempt == max_retries - 1:
                                logger.critical(
                                    f"💥 關鍵操作失敗（{max_retries}次重試後）: {func.__name__}\n"
                                    f"   錯誤類型: {type(e).__name__}\n"
                                    f"   錯誤信息: {e}"
                                )
                                raise
                            else:
                                backoff_time = backoff_base ** attempt
                                logger.warning(
                                    f"⚠️ 關鍵操作失敗，{backoff_time:.1f}秒後重試 "
                                    f"({attempt + 1}/{max_retries}): {func.__name__} - {e}"
                                )
                                time.sleep(backoff_time)
                    
                    if last_exception:
                        raise last_exception
                        
                return sync_wrapper
        return decorator
    
    @staticmethod
    def safe_execution(default_return: Any = None) -> Callable:
        """
        🔥 v3.23+ 安全執行裝飾器（同步/異步雙模式）
        
        捕獲所有異常並返回默認值
        用於非關鍵路徑，確保系統不會因為單個組件失敗而崩潰
        
        Args:
            default_return: 異常時的默認返回值
        """
        def decorator(func: Callable) -> Callable:
            if iscoroutinefunction(func):
                # 異步版本
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs) -> Any:
                    try:
                        return await func(*args, **kwargs)
                    except (KeyboardInterrupt, asyncio.CancelledError):
                        raise
                    except Exception as e:
                        logger.error(
                            f"❌ 安全執行失敗，返回默認值: {func.__name__}\n"
                            f"   錯誤: {type(e).__name__}: {e}\n"
                            f"   默認返回值: {default_return}"
                        )
                        return default_return
                return async_wrapper
            else:
                # 同步版本
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs) -> Any:
                    try:
                        return func(*args, **kwargs)
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        logger.error(
                            f"❌ 安全執行失敗，返回默認值: {func.__name__}\n"
                            f"   錯誤: {type(e).__name__}: {e}\n"
                            f"   默認返回值: {default_return}"
                        )
                        return default_return
                return sync_wrapper
        return decorator
    
    @staticmethod
    def log_exceptions(func: Callable) -> Callable:
        """
        🔥 v3.23+ 僅記錄異常但不處理的裝飾器（同步/異步雙模式）
        
        用於需要詳細錯誤日誌但不改變異常傳播行為的場景
        """
        if iscoroutinefunction(func):
            # 異步版本
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.exception(
                        f"❌ 異常發生在 {func.__name__}\n"
                        f"   錯誤類型: {type(e).__name__}\n"
                        f"   錯誤信息: {e}"
                    )
                    raise
            return async_wrapper
        else:
            # 同步版本
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.exception(
                        f"❌ 異常發生在 {func.__name__}\n"
                        f"   錯誤類型: {type(e).__name__}\n"
                        f"   錯誤信息: {e}"
                    )
                    raise
            return sync_wrapper


class ResourceCleanupHandler:
    """資源清理處理器"""
    
    @staticmethod
    async def safe_cleanup(cleanup_func: Callable, context: str = "") -> bool:
        """
        安全執行清理操作
        
        Args:
            cleanup_func: 清理函數
            context: 上下文描述
            
        Returns:
            清理是否成功
        """
        try:
            if asyncio.iscoroutinefunction(cleanup_func):
                await cleanup_func()
            else:
                cleanup_func()
            logger.debug(f"✅ 資源清理成功: {context}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ 資源清理失敗（繼續執行）: {context} - {e}")
            return False


class ValidationErrorHandler:
    """驗證錯誤處理器"""
    
    @staticmethod
    def handle_validation_error(error: Exception, context: str = "") -> dict:
        """
        處理驗證錯誤並返回標準化響應
        
        Args:
            error: 驗證異常
            context: 上下文描述
            
        Returns:
            標準化錯誤響應
        """
        error_response = {
            'success': False,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context
        }
        
        logger.error(
            f"❌ 驗證失敗: {context}\n"
            f"   錯誤類型: {error_response['error_type']}\n"
            f"   錯誤信息: {error_response['error_message']}"
        )
        
        return error_response
