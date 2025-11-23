"""
🛡️ Error Handler - Contextual Error Wrappers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 2: Contextual Error Wrappers
Provides decorators for critical functions to log detailed error context:
- Function name
- Arguments and kwargs
- Full exception traceback
"""

import logging
import functools
import inspect
from typing import Callable, Any

logger = logging.getLogger(__name__)


def catch_and_log(critical: bool = False) -> Callable:
    """
    Decorator: Catch exceptions and log detailed context
    
    Args:
        critical: If True, use logger.critical instead of logger.error
    
    Usage:
        @catch_and_log(critical=False)
        async def execute_order(order):
            ...
    
    Logs:
        ❌ ERROR in [function_name]
           Args: [...] kwargs: {...}
           Reason: exception message
           [Full traceback]
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Extract function context
                func_name = func.__name__
                
                # Filter out 'self' from args
                filtered_args = args[1:] if (args and hasattr(args[0], '__dict__')) else args
                
                # Log error with full context
                log_func = logger.critical if critical else logger.error
                
                log_func(f"❌ ERROR in [{func_name}]")
                log_func(f"   Args: {filtered_args}")
                log_func(f"   Kwargs: {kwargs}")
                log_func(f"   Reason: {str(e)}", exc_info=True)
                
                # Re-raise so system knows it failed
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Extract function context
                func_name = func.__name__
                
                # Filter out 'self' from args
                filtered_args = args[1:] if (args and hasattr(args[0], '__dict__')) else args
                
                # Log error with full context
                log_func = logger.critical if critical else logger.error
                
                log_func(f"❌ ERROR in [{func_name}]")
                log_func(f"   Args: {filtered_args}")
                log_func(f"   Kwargs: {kwargs}")
                log_func(f"   Reason: {str(e)}", exc_info=True)
                
                # Re-raise so system knows it failed
                raise
        
        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def log_function_entry(func: Callable) -> Callable:
    """
    Optional: Log when critical functions are called (DEBUG level)
    
    Usage:
        @log_function_entry
        async def critical_operation():
            ...
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        logger.debug(f"→ Entering [{func.__name__}]")
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"← Exiting [{func.__name__}] (success)")
            return result
        except Exception as e:
            logger.debug(f"← Exiting [{func.__name__}] (error: {e})")
            raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        logger.debug(f"→ Entering [{func.__name__}]")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"← Exiting [{func.__name__}] (success)")
            return result
        except Exception as e:
            logger.debug(f"← Exiting [{func.__name__}] (error: {e})")
            raise
    
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
