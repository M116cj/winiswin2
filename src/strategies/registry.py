"""
策略注册中心 (v3.13.0 策略6)
职责：动态组合子策略，取代硬编码的巨型类

✅ 为什么使用注册中心：
1. ict_strategy.py 臃肿（>500行）→ 拆分为独立组件
2. 每次新增功能需修改主类 → 现在只需注册新组件
3. 便于测试（单独测试每个组件）
4. 支持热插拔（动态启用/禁用策略组件）

使用示例：
    # 注册组件
    @register_component("order_blocks")
    def detect_order_blocks(df, config):
        return ob_signals
    
    # 使用
    results = {}
    for name, func in STRATEGY_COMPONENTS.items():
        results[name] = func(df, config)
"""

import logging
from typing import Dict, Callable, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StrategyComponent:
    """策略组件元数据"""
    __slots__ = ('name', 'func', 'enabled', 'priority', 'description', 'version')
    
    name: str
    func: Callable
    enabled: bool
    priority: int  # 执行优先级（数字越小越早执行）
    description: str
    version: str


class StrategyRegistry:
    """
    策略组件注册中心
    
    支持：
    - 动态注册组件
    - 启用/禁用组件
    - 按优先级执行
    - 组件依赖管理
    """
    
    def __init__(self):
        """初始化注册中心"""
        self._components: Dict[str, StrategyComponent] = {}
        self._execution_order: List[str] = []
        logger.info("✅ 策略注册中心初始化")
    
    def register(
        self,
        name: str,
        func: Callable,
        enabled: bool = True,
        priority: int = 100,
        description: str = "",
        version: str = "1.0.0"
    ):
        """
        注册策略组件
        
        Args:
            name: 组件名称（唯一标识）
            func: 组件函数
            enabled: 是否启用
            priority: 执行优先级（数字越小越早执行）
            description: 组件描述
            version: 版本号
        """
        component = StrategyComponent(
            name=name,
            func=func,
            enabled=enabled,
            priority=priority,
            description=description,
            version=version
        )
        
        self._components[name] = component
        self._rebuild_execution_order()
        
        logger.debug(f"✅ 注册策略组件: {name} (优先级={priority}, 启用={enabled})")
    
    def unregister(self, name: str):
        """注销策略组件"""
        if name in self._components:
            del self._components[name]
            self._rebuild_execution_order()
            logger.debug(f"❌ 注销策略组件: {name}")
    
    def enable(self, name: str):
        """启用组件"""
        if name in self._components:
            self._components[name].enabled = True
            logger.debug(f"✅ 启用策略组件: {name}")
    
    def disable(self, name: str):
        """禁用组件"""
        if name in self._components:
            self._components[name].enabled = False
            logger.debug(f"❌ 禁用策略组件: {name}")
    
    def get_component(self, name: str) -> Optional[StrategyComponent]:
        """获取组件"""
        return self._components.get(name)
    
    def execute_all(self, df, config, **kwargs) -> Dict[str, Any]:
        """
        按优先级执行所有启用的组件
        
        Args:
            df: K线数据
            config: 配置对象
            **kwargs: 额外参数
        
        Returns:
            Dict[str, Any]: {组件名: 执行结果}
        """
        results = {}
        
        for name in self._execution_order:
            component = self._components[name]
            
            if not component.enabled:
                continue
            
            try:
                # 执行组件
                result = component.func(df, config, **kwargs)
                results[name] = result
            except Exception as e:
                logger.error(f"❌ 策略组件 {name} 执行失败: {e}", exc_info=True)
                results[name] = None
        
        return results
    
    def execute(self, name: str, *args, **kwargs) -> Any:
        """
        执行单个组件
        
        Args:
            name: 组件名称
            *args: 位置参数
            **kwargs: 关键字参数
        
        Returns:
            Any: 执行结果
        """
        component = self._components.get(name)
        
        if component is None:
            raise ValueError(f"组件 {name} 不存在")
        
        if not component.enabled:
            logger.warning(f"组件 {name} 已禁用")
            return None
        
        return component.func(*args, **kwargs)
    
    def get_enabled_components(self) -> List[str]:
        """获取所有启用的组件名称"""
        return [name for name, comp in self._components.items() if comp.enabled]
    
    def get_all_components(self) -> Dict[str, StrategyComponent]:
        """获取所有组件"""
        return self._components.copy()
    
    def _rebuild_execution_order(self):
        """重建执行顺序（按优先级排序）"""
        self._execution_order = sorted(
            self._components.keys(),
            key=lambda name: self._components[name].priority
        )
    
    def __repr__(self):
        """友好的字符串表示"""
        enabled_count = sum(1 for comp in self._components.values() if comp.enabled)
        return f"StrategyRegistry(components={len(self._components)}, enabled={enabled_count})"


# 全局注册中心实例（单例）
_global_registry: Optional[StrategyRegistry] = None


def get_global_registry() -> StrategyRegistry:
    """获取全局策略注册中心（单例）"""
    global _global_registry
    if _global_registry is None:
        _global_registry = StrategyRegistry()
    return _global_registry


def register_component(
    name: str,
    enabled: bool = True,
    priority: int = 100,
    description: str = "",
    version: str = "1.0.0"
):
    """
    装饰器：注册策略组件
    
    使用示例：
        @register_component("order_blocks", priority=10)
        def detect_order_blocks(df, config):
            return ob_signals
    
    Args:
        name: 组件名称
        enabled: 是否启用
        priority: 优先级
        description: 描述
        version: 版本号
    """
    def decorator(func: Callable) -> Callable:
        registry = get_global_registry()
        registry.register(
            name=name,
            func=func,
            enabled=enabled,
            priority=priority,
            description=description or func.__doc__ or "",
            version=version
        )
        return func
    
    return decorator


# ============================================================================
# 预定义组件（示例）
# ============================================================================

@register_component(
    name="order_blocks",
    priority=10,
    description="检测Order Block（供应/需求区域）",
    version="3.13.0"
)
def detect_order_blocks(df, config, **kwargs):
    """
    检测Order Block
    
    Args:
        df: K线数据
        config: 配置
    
    Returns:
        List[Dict]: Order Block列表
    """
    # 这是一个示例实现，实际逻辑在ict_strategy.py中
    # 这里只是展示如何使用注册中心
    
    # ✅ v3.20.2: 使用 EliteTechnicalEngine 的 swing_points
    from src.core.elite import EliteTechnicalEngine
    
    tech_engine = EliteTechnicalEngine()
    swing_points_result = tech_engine.calculate('swing_points', df, lookback=kwargs.get('lookback', 5))
    swing_highs = swing_points_result.value['highs']
    swing_lows = swing_points_result.value['lows']
    
    order_blocks = []
    
    # 简化逻辑：检测摆动点
    for i in range(len(df)):
        if not pd.isna(swing_highs.iloc[i]):
            order_blocks.append({
                'type': 'supply',
                'price': swing_highs.iloc[i],
                'index': i,
                'strength': 1.0
            })
        
        if not pd.isna(swing_lows.iloc[i]):
            order_blocks.append({
                'type': 'demand',
                'price': swing_lows.iloc[i],
                'index': i,
                'strength': 1.0
            })
    
    return order_blocks


@register_component(
    name="fair_value_gaps",
    priority=20,
    description="检测Fair Value Gap（价格失衡）",
    version="3.13.0"
)
def detect_fair_value_gaps(df, config, **kwargs):
    """
    检测Fair Value Gap
    
    Args:
        df: K线数据
        config: 配置
    
    Returns:
        pd.DataFrame: FVG数据
    """
    # ✅ v3.20.2: 使用 EliteTechnicalEngine 的 fvg
    from src.core.elite import EliteTechnicalEngine
    
    tech_engine = EliteTechnicalEngine()
    fvgs_result = tech_engine.calculate('fvg', df, min_gap_pct=kwargs.get('min_gap_pct', 0.001))
    fvgs = fvgs_result.value
    
    return fvgs


@register_component(
    name="market_structure",
    priority=30,
    description="分析市场结构（BOS/CHOCH）",
    version="3.13.0"
)
def analyze_market_structure(df, config, **kwargs):
    """
    分析市场结构
    
    Args:
        df: K线数据
        config: 配置
    
    Returns:
        Dict: 市场结构信息
    """
    # ✅ v3.20.2: 使用 EliteTechnicalEngine 的 market_structure
    from src.core.elite import EliteTechnicalEngine
    
    tech_engine = EliteTechnicalEngine()
    market_structure_result = tech_engine.calculate('market_structure', df, lookback=kwargs.get('lookback', 10))
    market_structure = market_structure_result.value
    
    return market_structure


# 导入pandas（用于示例组件）
import pandas as pd
