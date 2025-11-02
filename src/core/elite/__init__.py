"""
Elite Architecture v3.20 - 精英化重构核心模块

本模块包含重构后的高性能统一引擎：
- EliteTechnicalEngine: 统一技术指标计算引擎（消除3处重复）
- IntelligentCache: 智能分层缓存系统（L1内存+L2持久化）
- UnifiedDataPipeline: 统一数据获取管道（合并5个方法）
- ErrorHandler: 统一错误处理框架（统一重试逻辑）

性能目标：
- 分析速度提升：4-5倍（23-53秒 → 5-10秒）
- 缓存命中率：40% → 85%
- 代码重复率：35% → <5%
"""

from .intelligent_cache import IntelligentCache, CacheStats
from .technical_indicator_engine import EliteTechnicalEngine
from .unified_data_pipeline import UnifiedDataPipeline

__all__ = [
    'IntelligentCache',
    'CacheStats',
    'EliteTechnicalEngine',
    'UnifiedDataPipeline',
]

__version__ = '3.20.0'
