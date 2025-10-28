"""
虚拟仓位事件定义模块
用于虚拟仓位全生命周期监控
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any
import time


class VirtualPositionEvent(Enum):
    """虚拟仓位生命周期事件"""
    CREATED = "created"           # 仓位创建
    PRICE_UPDATED = "price_updated"  # 价格更新
    MAX_PNL_UPDATED = "max_pnl_updated"  # 最大盈利更新
    MIN_PNL_UPDATED = "min_pnl_updated"  # 最大亏损更新
    TP_APPROACHING = "tp_approaching"    # 接近止盈
    SL_APPROACHING = "sl_approaching"    # 接近止损
    TP_TRIGGERED = "tp_triggered"        # 止盈触发
    SL_TRIGGERED = "sl_triggered"        # 止损触发
    EXPIRED = "expired"                  # 过期平仓
    MANUAL_CLOSE = "manual_close"        # 手动平仓
    CLOSED = "closed"                    # 仓位关闭（最终状态）


@dataclass
class VirtualPositionEventPayload:
    """事件载荷"""
    event_type: VirtualPositionEvent
    position_id: str
    symbol: str
    timestamp: float
    current_price: float
    pnl_pct: float
    max_pnl: float
    min_pnl: float
    metadata: Dict[str, Any]
    
    @classmethod
    def create(cls, event_type: VirtualPositionEvent, position, **kwargs):
        return cls(
            event_type=event_type,
            position_id=position.signal_id,
            symbol=position.symbol,
            timestamp=time.time(),
            current_price=position.current_price,
            pnl_pct=position.pnl_pct,
            max_pnl=getattr(position, 'max_pnl', position.pnl_pct),
            min_pnl=getattr(position, 'min_pnl', position.pnl_pct),
            metadata=kwargs
        )
