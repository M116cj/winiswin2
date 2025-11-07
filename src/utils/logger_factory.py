"""
Logger Factory v4.0 - 统一日志创建工厂

🎯 目标：
确保所有模块都使用SmartLogger，实现：
- 统一的日志格式
- 智能限流和聚合
- 一致的配置管理

🔥 替代：
- 84个文件的 `import logging` 和 `logging.getLogger()`
- 统一为SmartLogger
"""

from src.utils.smart_logger import create_smart_logger


def get_logger(name: str, **kwargs):
    """
    获取统一配置的logger
    
    Args:
        name: logger名称（通常使用__name__）
        **kwargs: SmartLogger额外参数
        
    Returns:
        配置好的SmartLogger实例
        
    使用示例:
    ```python
    from src.utils.logger_factory import get_logger
    
    logger = get_logger(__name__)
    logger.info("这是一条日志")
    ```
    """
    # 默认配置
    default_config = {
        'rate_limit_window': 2.0,
        'enable_aggregation': True,
        'enable_structured': False
    }
    
    # 合并用户配置
    config = {**default_config, **kwargs}
    
    return create_smart_logger(name, **config)
