"""
虚拟仓位全生命周期监控器
监控虚拟仓位从创建到关闭的完整生命周期
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable
from collections import defaultdict

from src.managers.virtual_position_events import (
    VirtualPositionEvent, 
    VirtualPositionEventPayload
)
from src.core.data_models import VirtualPosition

logger = logging.getLogger(__name__)


class VirtualPositionLifecycleMonitor:
    """虚拟仓位全生命周期监控器"""
    
    def __init__(self, event_callback: Optional[Callable] = None):
        self.active_positions: Dict[str, VirtualPosition] = {}
        self.position_history: Dict[str, List[VirtualPositionEventPayload]] = defaultdict(list)
        self.event_callback = event_callback
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.max_pnl_tracker: Dict[str, float] = {}
        self.min_pnl_tracker: Dict[str, float] = {}
        
        self.tp_approach_threshold = 0.8
        self.sl_approach_threshold = 0.8
        self.update_interval = 1.0
        
    def add_position(self, position: VirtualPosition):
        """添加虚拟仓位到监控"""
        position_id = position.signal_id
        if position_id in self.active_positions:
            logger.warning(f"⚠️ 倉位 {position_id} 已存在，先移除舊監控")
            self.remove_position(position_id)
        
        self.active_positions[position_id] = position
        self.max_pnl_tracker[position_id] = position.pnl_pct
        self.min_pnl_tracker[position_id] = position.pnl_pct
        
        self._emit_event(VirtualPositionEvent.CREATED, position)
        
        if position_id not in self.monitoring_tasks:
            task = asyncio.create_task(self._monitor_position_lifecycle(position_id))
            self.monitoring_tasks[position_id] = task
            
        logger.debug(f"开始监控虚拟仓位: {position_id}")
    
    def remove_position(self, position_id: str):
        """移除虚拟仓位监控"""
        if position_id in self.active_positions:
            del self.active_positions[position_id]
        if position_id in self.max_pnl_tracker:
            del self.max_pnl_tracker[position_id]
        if position_id in self.min_pnl_tracker:
            del self.min_pnl_tracker[position_id]
        if position_id in self.monitoring_tasks:
            self.monitoring_tasks[position_id].cancel()
            del self.monitoring_tasks[position_id]
        logger.debug(f"停止监控虚拟仓位: {position_id}")
    
    async def _monitor_position_lifecycle(self, position_id: str):
        """监控单个仓位的生命周期"""
        try:
            while position_id in self.active_positions:
                position = self.active_positions[position_id]
                
                if position.is_closed:
                    self._record_position_history(position_id)
                    self.remove_position(position_id)
                    break
                
                self._update_pnl_trackers(position_id, position)
                await self._check_lifecycle_events(position_id, position)
                await asyncio.sleep(self.update_interval)
                
        except asyncio.CancelledError:
            logger.debug(f"监控任务被取消: {position_id}")
        except Exception as e:
            logger.error(f"监控任务错误 {position_id}: {e}")
    
    def _update_pnl_trackers(self, position_id: str, position: VirtualPosition):
        """更新最大/最小 PnL 追踪"""
        current_pnl = position.pnl_pct
        self.max_pnl_tracker[position_id] = max(
            self.max_pnl_tracker[position_id], 
            current_pnl
        )
        self.min_pnl_tracker[position_id] = min(
            self.min_pnl_tracker[position_id], 
            current_pnl
        )
    
    async def _check_lifecycle_events(self, position_id: str, position: VirtualPosition):
        """检查生命周期事件"""
        current_pnl = position.pnl_pct
        max_pnl = self.max_pnl_tracker[position_id]
        min_pnl = self.min_pnl_tracker[position_id]
        
        if current_pnl != getattr(position, '_last_pnl', None):
            position._last_pnl = current_pnl
            self._emit_event(VirtualPositionEvent.PRICE_UPDATED, position)
        
        if max_pnl > getattr(position, '_last_max_pnl', current_pnl):
            position._last_max_pnl = max_pnl
            self._emit_event(VirtualPositionEvent.MAX_PNL_UPDATED, position, max_pnl=max_pnl)
            
        if min_pnl < getattr(position, '_last_min_pnl', current_pnl):
            position._last_min_pnl = min_pnl
            self._emit_event(VirtualPositionEvent.MIN_PNL_UPDATED, position, min_pnl=min_pnl)
        
        await self._check_approach_events(position_id, position)
        close_reason = await self._check_close_conditions(position_id, position)
        if close_reason:
            await self._close_position(position_id, position, close_reason)
    
    async def _check_approach_events(self, position_id: str, position: VirtualPosition):
        """检查接近止盈/止损事件"""
        if position.is_closed:
            return
            
        current_price = position.current_price
        
        if position.direction == 1:
            tp_distance = (position.take_profit - current_price) / (position.take_profit - position.entry_price)
            sl_distance = (current_price - position.stop_loss) / (position.entry_price - position.stop_loss)
            
            if 0 < tp_distance <= (1 - self.tp_approach_threshold):
                self._emit_event(
                    VirtualPositionEvent.TP_APPROACHING, 
                    position,
                    distance_to_tp=tp_distance,
                    estimated_time_to_tp=self._estimate_time_to_target(position, 'tp')
                )
            
            if 0 < sl_distance <= (1 - self.sl_approach_threshold):
                self._emit_event(
                    VirtualPositionEvent.SL_APPROACHING,
                    position, 
                    distance_to_sl=sl_distance,
                    estimated_time_to_sl=self._estimate_time_to_target(position, 'sl')
                )
                
        else:
            tp_distance = (current_price - position.take_profit) / (position.entry_price - position.take_profit)
            sl_distance = (position.stop_loss - current_price) / (position.stop_loss - position.entry_price)
            
            if 0 < tp_distance <= (1 - self.tp_approach_threshold):
                self._emit_event(
                    VirtualPositionEvent.TP_APPROACHING,
                    position,
                    distance_to_tp=tp_distance,
                    estimated_time_to_tp=self._estimate_time_to_target(position, 'tp')
                )
                
            if 0 < sl_distance <= (1 - self.sl_approach_threshold):
                self._emit_event(
                    VirtualPositionEvent.SL_APPROACHING,
                    position,
                    distance_to_sl=sl_distance,
                    estimated_time_to_sl=self._estimate_time_to_target(position, 'sl')
                )
    
    async def _check_close_conditions(self, position_id: str, position: VirtualPosition) -> Optional[str]:
        """检查平仓条件"""
        if position.is_closed:
            return None
            
        current_price = position.current_price
        current_time = time.time()
        
        if position.direction == 1 and current_price >= position.take_profit:
            return "tp"
        elif position.direction == -1 and current_price <= position.take_profit:
            return "tp"
            
        if position.direction == 1 and current_price <= position.stop_loss:
            return "sl"
        elif position.direction == -1 and current_price >= position.stop_loss:
            return "sl"
            
        if current_time - position.entry_timestamp > 96 * 3600:
            return "expired"
            
        return None
    
    async def _close_position(self, position_id: str, position: VirtualPosition, reason: str):
        """关闭仓位"""
        position.is_closed = True
        position.close_timestamp = time.time()
        position.close_reason = reason
        
        if reason == "tp":
            event_type = VirtualPositionEvent.TP_TRIGGERED
        elif reason == "sl":
            event_type = VirtualPositionEvent.SL_TRIGGERED
        elif reason == "expired":
            event_type = VirtualPositionEvent.EXPIRED
        else:
            event_type = VirtualPositionEvent.MANUAL_CLOSE
            
        self._emit_event(event_type, position, close_reason=reason)
        self._emit_event(VirtualPositionEvent.CLOSED, position, close_reason=reason)
        
        self._record_position_history(position_id)
        self.remove_position(position_id)
        
        logger.info(f"虚拟仓位关闭: {position_id}, 原因: {reason}, PnL: {position.pnl_pct:.2f}%")
    
    def _emit_event(self, event_type: VirtualPositionEvent, position: VirtualPosition, **metadata):
        """发送事件"""
        event_payload = VirtualPositionEventPayload.create(
            event_type, position, **metadata
        )
        
        self.position_history[position.signal_id].append(event_payload)
        
        if self.event_callback:
            try:
                if asyncio.iscoroutinefunction(self.event_callback):
                    asyncio.create_task(self.event_callback(event_payload))
                else:
                    self.event_callback(event_payload)
            except Exception as e:
                logger.error(f"事件回调错误: {e}")
        
        if event_type in [
            VirtualPositionEvent.TP_TRIGGERED,
            VirtualPositionEvent.SL_TRIGGERED,
            VirtualPositionEvent.EXPIRED,
            VirtualPositionEvent.CLOSED
        ]:
            logger.info(f"仓位事件: {event_type.value} - {position.symbol} PnL: {position.pnl_pct:.2f}%")
    
    def _record_position_history(self, position_id: str):
        """记录仓位完整历史"""
        if position_id in self.active_positions:
            position = self.active_positions[position_id]
    
    def _estimate_time_to_target(self, position: VirtualPosition, target_type: str) -> float:
        """估算到达目标时间（秒）"""
        try:
            return 300.0
        except:
            return 600.0
    
    def get_position_events(self, position_id: str) -> List[VirtualPositionEventPayload]:
        """获取仓位的所有事件历史"""
        return self.position_history.get(position_id, [])
    
    def get_active_positions_count(self) -> int:
        """获取活跃仓位数量"""
        return len(self.active_positions)
    
    def get_position_summary(self, position_id: str) -> Dict:
        """获取仓位摘要信息"""
        if position_id not in self.active_positions:
            return {}
            
        position = self.active_positions[position_id]
        events = self.position_history.get(position_id, [])
        
        return {
            'symbol': position.symbol,
            'direction': 'LONG' if position.direction == 1 else 'SHORT',
            'entry_price': position.entry_price,
            'current_price': position.current_price,
            'pnl_pct': position.pnl_pct,
            'max_pnl': self.max_pnl_tracker.get(position_id, position.pnl_pct),
            'min_pnl': self.min_pnl_tracker.get(position_id, position.pnl_pct),
            'hold_time_seconds': time.time() - position.entry_timestamp,
            'event_count': len(events),
            'is_closed': position.is_closed,
            'close_reason': position.close_reason if position.is_closed else None
        }


async def default_event_handler(event_payload: VirtualPositionEventPayload):
    """默认事件处理器"""
    if event_payload.event_type == VirtualPositionEvent.TP_TRIGGERED:
        message = f"🎯 **止盈触发**\n{event_payload.symbol} 盈利 {event_payload.pnl_pct:.2f}%"
        logger.info(message)
        
    elif event_payload.event_type == VirtualPositionEvent.SL_TRIGGERED:
        message = f"⚠️ **止损触发**\n{event_payload.symbol} 亏损 {abs(event_payload.pnl_pct):.2f}%"
        logger.info(message)
        
    elif event_payload.event_type == VirtualPositionEvent.EXPIRED:
        message = f"⏰ **仓位过期**\n{event_payload.symbol} PnL: {event_payload.pnl_pct:.2f}%"
        logger.info(message)
        
    elif event_payload.event_type == VirtualPositionEvent.TP_APPROACHING:
        distance = event_payload.metadata.get('distance_to_tp', 0)
        message = f"🚀 **接近止盈**\n{event_payload.symbol} 距离止盈 {(1-distance)*100:.1f}%"
        logger.info(message)
