"""
持仓监控服务
职责：监控活跃持仓，动态调整止损止盈
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PositionMonitor:
    """持仓监控器 - 动态调整止损止盈"""
    
    def __init__(self, binance_client, trading_service, data_archiver):
        """
        初始化持仓监控器
        
        Args:
            binance_client: Binance客户端
            trading_service: 交易服务
            data_archiver: 数据归档器（记录XGBoost特征）
        """
        self.client = binance_client
        self.trading_service = trading_service
        self.data_archiver = data_archiver
        
        # 追踪止损配置
        self.trailing_stop_pct = 0.5  # 追踪止损触发阈值：盈利0.5%时启动
        self.trailing_distance_pct = 0.3  # 追踪距离：距离当前价0.3%
        
        # 追踪止盈配置
        self.trailing_profit_trigger_pct = 1.0  # 追踪止盈触发：盈利1%时启动
        self.trailing_profit_distance_pct = 0.5  # 距离峰值0.5%
        
        # 持仓状态追踪
        self.position_states: Dict[str, Dict] = {}
        
        logger.info("✅ 持仓监控器已初始化")
        logger.info(f"   - 追踪止损: 盈利>{self.trailing_stop_pct}%时启动, 距离{self.trailing_distance_pct}%")
        logger.info(f"   - 追踪止盈: 盈利>{self.trailing_profit_trigger_pct}%时启动, 距离峰值{self.trailing_profit_distance_pct}%")
    
    async def monitor_all_positions(self) -> Dict:
        """
        监控所有活跃持仓
        
        Returns:
            Dict: 监控统计信息
        """
        try:
            # 获取所有活跃持仓
            positions = await self.client.get_positions()
            active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
            
            if not active_positions:
                return {
                    'total': 0,
                    'adjusted': 0,
                    'in_profit': 0,
                    'in_loss': 0
                }
            
            stats = {
                'total': len(active_positions),
                'adjusted': 0,
                'in_profit': 0,
                'in_loss': 0,
                'adjustments': []
            }
            
            for position in active_positions:
                symbol = position['symbol']
                position_amt = float(position['positionAmt'])
                entry_price = float(position['entryPrice'])
                unrealized_pnl_pct = float(position.get('unRealizedProfit', 0)) / (abs(position_amt) * entry_price) * 100
                
                # 获取当前市场价
                ticker = await self.client.get_ticker_price(symbol)
                current_price = float(ticker['price'])
                
                # 计算盈亏百分比
                direction = "LONG" if position_amt > 0 else "SHORT"
                if direction == "LONG":
                    pnl_pct = (current_price - entry_price) / entry_price * 100
                else:
                    pnl_pct = (entry_price - current_price) / entry_price * 100
                
                # 统计盈亏
                if pnl_pct > 0:
                    stats['in_profit'] += 1
                else:
                    stats['in_loss'] += 1
                
                # 检查是否需要调整止损止盈
                adjustment = await self._check_and_adjust_position(
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    current_price=current_price,
                    quantity=abs(position_amt),
                    pnl_pct=pnl_pct,
                    unrealized_pnl_pct=unrealized_pnl_pct
                )
                
                if adjustment:
                    stats['adjusted'] += 1
                    stats['adjustments'].append(adjustment)
            
            # 记录监控摘要
            logger.info(
                f"📊 持仓监控: 总数={stats['total']}, "
                f"盈利={stats['in_profit']}, 亏损={stats['in_loss']}, "
                f"调整={stats['adjusted']}"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"持仓监控失败: {e}")
            return {'total': 0, 'adjusted': 0, 'in_profit': 0, 'in_loss': 0}
    
    async def _check_and_adjust_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        current_price: float,
        quantity: float,
        pnl_pct: float,
        unrealized_pnl_pct: float
    ) -> Optional[Dict]:
        """
        检查并调整单个持仓的止损止盈
        
        Returns:
            Optional[Dict]: 调整记录（用于XGBoost特征）
        """
        try:
            # 初始化持仓状态
            if symbol not in self.position_states:
                self.position_states[symbol] = {
                    'highest_price': current_price if direction == "LONG" else entry_price,
                    'lowest_price': current_price if direction == "SHORT" else entry_price,
                    'max_profit_pct': pnl_pct,
                    'trailing_stop_active': False,
                    'trailing_profit_active': False,
                    'adjustment_count': 0,
                    'last_adjustment_time': None,
                    'current_stop_loss': None,  # 当前止损价格
                    'current_take_profit': None  # 当前止盈价格
                }
            
            state = self.position_states[symbol]
            
            # 更新峰值
            if direction == "LONG":
                if current_price > state['highest_price']:
                    state['highest_price'] = current_price
                if pnl_pct > state['max_profit_pct']:
                    state['max_profit_pct'] = pnl_pct
            else:  # SHORT
                if current_price < state['lowest_price']:
                    state['lowest_price'] = current_price
                if pnl_pct > state['max_profit_pct']:
                    state['max_profit_pct'] = pnl_pct
            
            adjustment_made = False
            new_stop_loss = None
            new_take_profit = None
            adjustment_reason = []
            
            # === 1. 追踪止损逻辑 ===
            if pnl_pct > self.trailing_stop_pct:
                if not state['trailing_stop_active']:
                    state['trailing_stop_active'] = True
                    logger.info(f"🎯 启动追踪止损: {symbol} (当前盈利: {pnl_pct:.2f}%)")
                
                # 计算新止损位
                if direction == "LONG":
                    # LONG: 止损=当前价 - 追踪距离
                    calculated_stop = current_price * (1 - self.trailing_distance_pct / 100)
                    # 确保新止损高于入场价（保护利润）
                    if calculated_stop > entry_price:
                        # 【重要】只有当新止损比当前止损更高时才更新（只向上移动）
                        if state['current_stop_loss'] is None or calculated_stop > state['current_stop_loss']:
                            new_stop_loss = calculated_stop
                            adjustment_reason.append(f"追踪止损(LONG)至{calculated_stop:.6f}")
                            adjustment_made = True
                else:  # SHORT
                    # SHORT: 止损=当前价 + 追踪距离
                    calculated_stop = current_price * (1 + self.trailing_distance_pct / 100)
                    # 确保新止损低于入场价（保护利润）
                    if calculated_stop < entry_price:
                        # 【重要】只有当新止损比当前止损更低时才更新（只向下移动）
                        if state['current_stop_loss'] is None or calculated_stop < state['current_stop_loss']:
                            new_stop_loss = calculated_stop
                            adjustment_reason.append(f"追踪止损(SHORT)至{calculated_stop:.6f}")
                            adjustment_made = True
            
            # === 2. 追踪止盈逻辑 ===
            if pnl_pct > self.trailing_profit_trigger_pct:
                if not state['trailing_profit_active']:
                    state['trailing_profit_active'] = True
                    logger.info(f"🎯 启动追踪止盈: {symbol} (当前盈利: {pnl_pct:.2f}%)")
                
                # 基于峰值回撤调整止盈
                if direction == "LONG":
                    # LONG: 止盈=峰值 - 回撤距离
                    peak_price = state['highest_price']
                    calculated_tp = peak_price * (1 - self.trailing_profit_distance_pct / 100)
                    if calculated_tp > current_price * 1.005:  # 确保止盈仍有至少0.5%空间
                        # 【重要】只有当新止盈比当前止盈更高时才更新（允许利润增长）
                        if state['current_take_profit'] is None or calculated_tp > state['current_take_profit']:
                            new_take_profit = calculated_tp
                            adjustment_reason.append(f"追踪止盈(LONG)至{calculated_tp:.6f}")
                            adjustment_made = True
                else:  # SHORT
                    # SHORT: 止盈=谷值 + 回撤距离
                    valley_price = state['lowest_price']
                    calculated_tp = valley_price * (1 + self.trailing_profit_distance_pct / 100)
                    if calculated_tp < current_price * 0.995:  # 确保止盈仍有至少0.5%空间
                        # 【重要】只有当新止盈比当前止盈更低时才更新（允许利润增长）
                        if state['current_take_profit'] is None or calculated_tp < state['current_take_profit']:
                            new_take_profit = calculated_tp
                            adjustment_reason.append(f"追踪止盈(SHORT)至{calculated_tp:.6f}")
                            adjustment_made = True
            
            # === 3. 执行调整并记录特征 ===
            if adjustment_made:
                # 【重要】在更新状态之前记录旧值
                old_stop_loss = state['current_stop_loss']
                old_take_profit = state['current_take_profit']
                
                state['adjustment_count'] += 1
                state['last_adjustment_time'] = datetime.now()
                
                # 【重要】取消并重新设置止损止盈订单
                # 必须同时设置两者，确保不会遗漏任何保护订单
                await self._cancel_existing_sl_tp_orders(symbol)
                
                # 确定最终的止损价格（新的或保持旧的）
                final_stop_loss = new_stop_loss if new_stop_loss else state['current_stop_loss']
                final_take_profit = new_take_profit if new_take_profit else state['current_take_profit']
                
                # 设置止损（如果有的话）
                if final_stop_loss:
                    await self.trading_service._set_stop_loss(
                        symbol=symbol,
                        direction=direction,
                        quantity=quantity,
                        stop_price=final_stop_loss
                    )
                    # 更新状态中的当前止损
                    if new_stop_loss:
                        state['current_stop_loss'] = new_stop_loss
                
                # 设置止盈（如果有的话）
                if final_take_profit:
                    await self.trading_service._set_take_profit(
                        symbol=symbol,
                        direction=direction,
                        quantity=quantity,
                        take_profit_price=final_take_profit
                    )
                    # 更新状态中的当前止盈
                    if new_take_profit:
                        state['current_take_profit'] = new_take_profit
                
                # === 记录XGBoost特征 ===
                
                adjustment_record = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol,
                    'direction': direction,
                    'event_type': 'stop_loss_take_profit_adjustment',
                    
                    # 价格信息
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'highest_price': state['highest_price'],
                    'lowest_price': state['lowest_price'],
                    
                    # 止损止盈调整
                    'old_stop_loss': old_stop_loss,
                    'new_stop_loss': new_stop_loss,
                    'old_take_profit': old_take_profit,
                    'new_take_profit': new_take_profit,
                    
                    # 盈亏指标
                    'current_pnl_pct': pnl_pct,
                    'max_profit_pct': state['max_profit_pct'],
                    'unrealized_pnl_pct': unrealized_pnl_pct,
                    
                    # 追踪状态
                    'trailing_stop_active': state['trailing_stop_active'],
                    'trailing_profit_active': state['trailing_profit_active'],
                    'adjustment_count': state['adjustment_count'],
                    
                    # 计算特征
                    'price_from_entry_pct': pnl_pct,
                    'price_from_peak_pct': (current_price - state['highest_price']) / state['highest_price'] * 100 if direction == "LONG" else (state['lowest_price'] - current_price) / state['lowest_price'] * 100,
                    'profit_to_max_profit_ratio': pnl_pct / state['max_profit_pct'] if state['max_profit_pct'] > 0 else 0,
                    
                    # 调整原因
                    'adjustment_reason': ', '.join(adjustment_reason)
                }
                
                # 归档到DataArchiver
                self.data_archiver.archive_adjustment(adjustment_record)
                
                logger.info(
                    f"🔄 调整止损止盈: {symbol} {direction} "
                    f"盈亏={pnl_pct:.2f}% 峰值={state['max_profit_pct']:.2f}% "
                    f"调整次数={state['adjustment_count']} "
                    f"原因: {', '.join(adjustment_reason)}"
                )
                
                return adjustment_record
            
            return None
            
        except Exception as e:
            logger.error(f"调整持仓失败 {symbol}: {e}")
            return None
    
    async def _cancel_existing_sl_tp_orders(self, symbol: str):
        """取消现有的止损止盈订单"""
        try:
            # 获取当前未成交订单
            open_orders = await self.client.get_open_orders(symbol)
            
            for order in open_orders:
                order_type = order.get('type')
                if order_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET', 'STOP', 'TAKE_PROFIT']:
                    order_id = order.get('orderId')
                    await self.client.cancel_order(symbol, int(order_id))
                    logger.debug(f"取消订单: {symbol} {order_type} #{order_id}")
        
        except Exception as e:
            logger.warning(f"取消订单失败 {symbol}: {e}")
    
    def cleanup_closed_positions(self, closed_symbols: List[str]):
        """清理已平仓的持仓状态"""
        for symbol in closed_symbols:
            if symbol in self.position_states:
                del self.position_states[symbol]
                logger.debug(f"清理持仓状态: {symbol}")
    
    def get_position_state(self, symbol: str) -> Optional[Dict]:
        """获取持仓状态（用于调试）"""
        return self.position_states.get(symbol)
    
    def get_all_states(self) -> Dict:
        """获取所有持仓状态统计"""
        return {
            'total_positions': len(self.position_states),
            'trailing_stop_active_count': sum(1 for s in self.position_states.values() if s['trailing_stop_active']),
            'trailing_profit_active_count': sum(1 for s in self.position_states.values() if s['trailing_profit_active']),
            'total_adjustments': sum(s['adjustment_count'] for s in self.position_states.values()),
        }
