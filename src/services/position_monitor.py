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
    
    def __init__(self, binance_client, trading_service, data_archiver, ml_predictor=None, virtual_position_manager=None):
        """
        初始化持仓监控器
        
        Args:
            binance_client: Binance客户端
            trading_service: 交易服务
            data_archiver: 数据归档器（记录XGBoost特征）
            ml_predictor: ML预测器（可选，用于反弹预测）🎯 v3.9.2.5新增
            virtual_position_manager: 虚拟仓位管理器（可选）🎯 v3.9.2.7新增
        """
        self.client = binance_client
        self.trading_service = trading_service
        self.data_archiver = data_archiver
        self.ml_predictor = ml_predictor  # 🎯 v3.9.2.5新增
        self.virtual_position_manager = virtual_position_manager  # 🎯 v3.9.2.7新增
        
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
        监控所有活跃持仓（真实 + 虚拟）
        
        🎯 v3.9.2.7增强：同时监控真实仓位和虚拟仓位
        🎯 v3.9.2.8性能优化：添加per-cycle指标缓存，避免重复获取
        
        Returns:
            Dict: 监控统计信息
        """
        try:
            # 🎯 v3.9.2.8.1: 指标缓存（带时间戳验证）
            indicators_cache = {}  # {symbol: {'indicators': Dict, 'timestamp': datetime}}
            
            async def get_indicators_cached(symbol: str, max_age_seconds: int = 30):
                """
                获取指标（带新鲜度验证）
                
                🚨 v3.9.2.8.1: 添加缓存时间验证，避免使用过期指标导致错误决策
                
                Args:
                    symbol: 交易对
                    max_age_seconds: 最大缓存时间（秒），默认30秒
                
                Returns:
                    Dict: 技术指标
                """
                now = datetime.now()
                
                if symbol in indicators_cache:
                    cache_age = (now - indicators_cache[symbol]['timestamp']).total_seconds()
                    if cache_age < max_age_seconds:
                        logger.debug(f"✅ 使用缓存指标 {symbol} (年龄:{cache_age:.1f}s)")
                        return indicators_cache[symbol]['indicators']
                    else:
                        logger.debug(f"⚠️ 缓存过期 {symbol} (年龄:{cache_age:.1f}s > {max_age_seconds}s)")
                
                # 缓存不存在或已过期，获取新指标
                indicators = await self._get_current_indicators(symbol)
                indicators_cache[symbol] = {
                    'indicators': indicators,
                    'timestamp': now
                }
                logger.debug(f"🔄 获取新指标 {symbol}")
                return indicators
            
            # === 1. 监控真实持仓 ===
            positions = await self.client.get_positions()
            active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
            
            # === 2. 🎯 v3.9.2.7新增：监控虚拟持仓 ===
            virtual_stats = {'total': 0, 'ml_analyzed': 0}
            if self.virtual_position_manager:
                # 🎯 v3.9.2.8: 传递缓存函数给虚拟持仓监控
                virtual_stats = await self.monitor_virtual_positions(get_indicators_cached)
            
            if not active_positions:
                if virtual_stats['total'] > 0:
                    logger.info(f"📊 真实持仓:0, 虚拟持仓:{virtual_stats['total']} (ML已分析:{virtual_stats['ml_analyzed']})")
                else:
                    logger.info("📊 当前无持仓")
                return {
                    'total': 0,
                    'adjusted': 0,
                    'in_profit': 0,
                    'in_loss': 0,
                    'virtual_total': virtual_stats['total'],
                    'virtual_ml_analyzed': virtual_stats['ml_analyzed']
                }
            
            # 📊 记录详细持仓状态
            logger.info(f"\n{'='*70}")
            logger.info(f"📊 当前持仓状态 [{len(active_positions)}个]")
            logger.info(f"{'='*70}")
            
            stats = {
                'total': len(active_positions),
                'adjusted': 0,
                'in_profit': 0,
                'in_loss': 0,
                'adjustments': [],
                'positions': []  # 存储详细持仓信息
            }
            
            for position in active_positions:
                symbol = position['symbol']
                position_amt = float(position['positionAmt'])
                entry_price = float(position['entryPrice'])
                unrealized_pnl_pct = float(position.get('unRealizedProfit', 0)) / (abs(position_amt) * entry_price) * 100
                
                # 获取当前市场价（v3.16.2 修復：get_ticker_price 返回 float）
                current_price = await self.client.get_ticker_price(symbol)
                
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
                
                # 获取当前止损止盈价格
                current_sl = self.position_states.get(symbol, {}).get('current_stop_loss')
                current_tp = self.position_states.get(symbol, {}).get('current_take_profit')
                
                # 计算持仓时间
                from datetime import datetime, timezone
                # 尝试获取持仓开始时间（如果有updateTime）
                update_time = position.get('updateTime', 0)
                if update_time > 0:
                    pos_time = datetime.fromtimestamp(update_time / 1000, tz=timezone.utc)
                    holding_hours = (datetime.now(timezone.utc) - pos_time).total_seconds() / 3600
                else:
                    holding_hours = 0
                
                # 🎯 v3.9.2.5：正确计算未实现盈亏（USDT）
                # unrealized_pnl_usdt = 仓位价值 * 盈亏百分比
                position_value = abs(position_amt) * entry_price
                unrealized_pnl_usdt = position_value * (pnl_pct / 100)
                
                # 记录详细持仓信息
                position_info = {
                    'symbol': symbol,
                    'direction': direction,
                    'quantity': abs(position_amt),
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'pnl_pct': pnl_pct,
                    'unrealized_pnl': unrealized_pnl_usdt,  # 使用计算值而非API值
                    'stop_loss': current_sl,
                    'take_profit': current_tp,
                    'holding_hours': holding_hours,
                    'leverage': float(position.get('leverage', 0))
                }
                stats['positions'].append(position_info)
                
                # 🎯 v3.9.2.8：获取ML信心值（从position_states或使用默认值）
                signal_confidence = 0.5  # 默认值
                if symbol in self.position_states:
                    signal_confidence = self.position_states[symbol].get('ml_confidence', 0.5)
                
                # 🤖 v3.9.2.8增强：ML智能决策系统（亏损分析 + 止盈分析）
                ml_suggestion = ""
                ml_executed = False
                
                # === 1. 亏损处理智能决策（仅当亏损>2%时） ===
                if self.ml_predictor and pnl_pct < -2.0:
                    try:
                        # 🚨 v3.9.2.8.3: ML决策前强制刷新指标（不使用缓存）
                        logger.debug(f"🔄 重新获取最新指标用于ML亏损分析 {symbol}")
                        indicators = await self._get_current_indicators(symbol)
                        
                        # 🎯 v3.9.2.8: 使用新的evaluate_loss_position方法
                        ml_analysis = await self.ml_predictor.evaluate_loss_position(
                            symbol=symbol,
                            direction=direction,
                            entry_price=entry_price,
                            current_price=current_price,
                            pnl_pct=pnl_pct,
                            ml_confidence=signal_confidence,
                            indicators=indicators
                        )
                        
                        action = ml_analysis['action']
                        action_emoji = {
                            'hold_and_monitor': '⏳',
                            'adjust_stop_loss': '🔧',
                            'close_immediately': '❌'
                        }.get(action, '❓')
                        
                        ml_suggestion = f" | ML:{action_emoji}{action[:4]} 风险:{ml_analysis['risk_level']}"
                        
                        # 根据ML建议执行
                        if action == 'close_immediately':
                            # 🚨 v3.9.2.8.1: 执行前重新验证（使用fresh指标）
                            logger.info(f"⚠️ 执行平仓前重新验证 {symbol}")
                            
                            # 获取最新价格（不使用缓存）（v3.16.2 修復：返回 float）
                            fresh_price = await self.client.get_ticker_price(symbol)
                            
                            # 重新计算PnL确认
                            if direction == 'LONG':
                                fresh_pnl_pct = ((fresh_price - entry_price) / entry_price) * 100
                            else:
                                fresh_pnl_pct = ((entry_price - fresh_price) / entry_price) * 100
                            
                            # 如果情况显著改善，取消平仓
                            if fresh_pnl_pct > -2.0:  # 亏损已经缓解到-2%以内
                                logger.info(
                                    f"✅ 情况改善，取消平仓 {symbol} "
                                    f"(原PnL:{pnl_pct:.2f}% -> 新PnL:{fresh_pnl_pct:.2f}%)"
                                )
                                ml_suggestion += " ⏸️已取消(情况改善)"
                                continue
                            
                            # 确认仍需平仓
                            logger.warning(
                                f"🚨 ML建议立即平仓 {symbol} (验证后PnL:{fresh_pnl_pct:.2f}%): "
                                f"{ml_analysis['reason']}"
                            )
                            await self._force_close_position(symbol, direction, abs(position_amt), "ml_suggested_close")
                            ml_suggestion += " ✅已执行"
                            continue  # 跳过后续检查
                            
                        elif action == 'adjust_stop_loss' and pnl_pct < -5.0:
                            # 🚨 v3.9.2.8.2: 执行前重新验证价格
                            logger.info(f"⚠️ 执行调整止损前重新验证 {symbol}")
                            fresh_price = await self.client.get_ticker_price(symbol)
                            
                            # 重新计算PnL
                            if direction == 'LONG':
                                fresh_pnl_pct = ((fresh_price - entry_price) / entry_price) * 100
                            else:
                                fresh_pnl_pct = ((entry_price - fresh_price) / entry_price) * 100
                            
                            # 如果情况改善，取消调整
                            if fresh_pnl_pct > -5.0:
                                logger.info(f"✅ 情况改善，取消调整 {symbol} (PnL:{fresh_pnl_pct:.2f}%)")
                                ml_suggestion += " ⏸️已取消(情况改善)"
                                continue
                            
                            # 确认仍需调整，执行止损调整
                            new_stop_loss_pct = abs(fresh_pnl_pct) * 1.05
                            if direction == "LONG":
                                new_stop_price = entry_price * (1 - new_stop_loss_pct / 100)
                            else:
                                new_stop_price = entry_price * (1 + new_stop_loss_pct / 100)
                            
                            try:
                                await self._update_stop_loss(symbol, direction, new_stop_price)
                                logger.info(f"🔧 ML调整止损 {symbol}: {new_stop_price:.4f} (验证后PnL:{fresh_pnl_pct:.2f}%)")
                                ml_suggestion += " ✅已执行"
                            except Exception as e:
                                logger.error(f"ML调整止损失败 {symbol}: {e}")
                        # 'hold_and_monitor' - 继续正常监控
                        
                    except Exception as e:
                        logger.debug(f"ML亏损分析失败 {symbol}: {e}")
                
                # === 2. 🎯 v3.9.2.8: 止盈智能决策（仅当盈利且有止盈目标时） ===
                if self.ml_predictor and pnl_pct > 0 and current_tp and current_tp > 0:
                    try:
                        # 计算止盈进度
                        if direction == 'LONG':
                            tp_progress = (current_price - entry_price) / (current_tp - entry_price) if current_tp > entry_price else 0
                        else:  # SHORT
                            tp_progress = (entry_price - current_price) / (entry_price - current_tp) if entry_price > current_tp else 0
                        
                        # 如果接近止盈（>75%），咨询ML
                        if tp_progress >= 0.75:
                            # 🚨 v3.9.2.8.3: ML决策前强制刷新指标（不使用缓存）
                            logger.debug(f"🔄 重新获取最新指标用于ML止盈分析 {symbol}")
                            indicators = await self._get_current_indicators(symbol)
                            
                            tp_analysis = await self.ml_predictor.evaluate_take_profit_opportunity(
                                symbol=symbol,
                                direction=direction,
                                entry_price=entry_price,
                                current_price=current_price,
                                take_profit_price=current_tp,
                                pnl_pct=pnl_pct,
                                ml_confidence=signal_confidence,
                                indicators=indicators
                            )
                            
                            logger.info(
                                f"💰 止盈决策 {symbol}: {tp_analysis['action']} "
                                f"(进度:{tp_progress:.1%}, 原因:{tp_analysis['reason']})"
                            )
                            
                            # 根据ML建议执行
                            if tp_analysis['action'] == 'take_profit_now':
                                # 🚨 v3.9.2.8.2: 执行前重新验证止盈进度
                                logger.info(f"⚠️ 执行提前止盈前重新验证 {symbol}")
                                fresh_price = await self.client.get_ticker_price(symbol)
                                
                                # 重新计算止盈进度
                                if direction == 'LONG':
                                    fresh_tp_progress = (fresh_price - entry_price) / (current_tp - entry_price) if current_tp > entry_price else 0
                                else:
                                    fresh_tp_progress = (entry_price - fresh_price) / (entry_price - current_tp) if entry_price > current_tp else 0
                                
                                # 如果进度下降，取消提前止盈
                                if fresh_tp_progress < 0.70:
                                    logger.info(f"✅ 止盈进度下降，取消提前止盈 {symbol} (进度:{fresh_tp_progress:.1%})")
                                    ml_suggestion += " ⏸️已取消(进度下降)"
                                    continue
                                
                                # 确认仍需止盈，执行平仓
                                logger.info(f"✅ ML建议提前止盈 {symbol} (验证后进度:{fresh_tp_progress:.1%}, PnL:{pnl_pct:.2f}%)")
                                await self._force_close_position(symbol, direction, abs(position_amt), "ml_take_profit")
                                ml_suggestion += " 💰提前止盈"
                                continue  # 跳过后续检查
                            # 🚨 v3.9.2.8.2: scale_in已完全删除
                            # 'hold_for_more' - 继续持有，不需要额外操作
                            
                    except Exception as e:
                        logger.debug(f"ML止盈分析失败 {symbol}: {e}")
                
                # 📊 日志输出每个持仓
                pnl_emoji = "🟢" if pnl_pct > 0 else "🔴"
                sl_status = f"止损:{current_sl:.6f}" if current_sl else "⚠️无止损"
                tp_status = f"止盈:{current_tp:.6f}" if current_tp else "无止盈"
                
                logger.info(
                    f"{pnl_emoji} {symbol:12s} {direction:5s} | "
                    f"盈亏:{pnl_pct:+7.2f}% | "
                    f"入场:{entry_price:.6f} 当前:{current_price:.6f} | "
                    f"{sl_status} {tp_status} | "
                    f"持仓:{holding_hours:.1f}h{ml_suggestion}"
                )
                
                # 🎯 v3.9.2.8: 预先获取indicators（使用缓存）
                indicators_for_adjust = await get_indicators_cached(symbol)
                
                # 检查是否需要调整止损止盈
                adjustment = await self._check_and_adjust_position(
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    current_price=current_price,
                    quantity=abs(position_amt),
                    pnl_pct=pnl_pct,
                    unrealized_pnl_pct=unrealized_pnl_pct,
                    indicators=indicators_for_adjust  # 🎯 v3.9.2.8: 传递缓存的indicators
                )
                
                if adjustment:
                    stats['adjusted'] += 1
                    stats['adjustments'].append(adjustment)
            
            # 记录监控摘要
            logger.info(f"{'='*70}")
            total_unrealized_pnl = sum(p['unrealized_pnl'] for p in stats['positions'])
            logger.info(
                f"💰 持仓汇总: 总数={stats['total']} | "
                f"盈利={stats['in_profit']}个 亏损={stats['in_loss']}个 | "
                f"未实现盈亏={total_unrealized_pnl:+.2f} USDT | "
                f"本周期调整={stats['adjusted']}个"
            )
            logger.info(f"{'='*70}\n")
            
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
        unrealized_pnl_pct: float,
        indicators: Optional[Dict] = None  # 🎯 v3.9.2.8: 性能优化 - 接受预先获取的indicators
    ) -> Optional[Dict]:
        """
        检查并调整单个持仓的止损止盈
        
        🚨 v3.9.2.3紧急修复：添加主动止损检查和强制平仓保护
        🎯 v3.9.2.8性能优化：接受预先获取的indicators，避免重复获取
        
        Args:
            indicators: 预先获取的技术指标（可选），如果未提供则内部获取
        
        Returns:
            Optional[Dict]: 调整记录（用于XGBoost特征）
        """
        try:
            # 🚨 v3.9.2.5智能止损：ML辅助决策
            # 从配置读取或使用默认值
            EMERGENCY_STOP_LOSS_PCT = getattr(self.trading_service.config, 'EMERGENCY_STOP_LOSS_PCT', -0.50) * 100  # -50%
            CRITICAL_STOP_LOSS_PCT = getattr(self.trading_service.config, 'CRITICAL_STOP_LOSS_PCT', -0.80) * 100  # -80%
            ML_REBOUND_CHECK_THRESHOLD = -0.30 * 100  # -30%开始询问ML
            
            # === 严重亏损：-80%直接平仓（无ML判断） ===
            if pnl_pct <= CRITICAL_STOP_LOSS_PCT:
                logger.critical(
                    f"🚨 检测到严重亏损 {symbol} {pnl_pct:.2f}% ≤ {CRITICAL_STOP_LOSS_PCT}% - 立即强制平仓！"
                )
                await self._force_close_position(symbol, direction, quantity, "critical_loss")
                return None
            
            # === 紧急亏损：-50%到-80%之间，询问ML智能决策 ===
            if pnl_pct <= EMERGENCY_STOP_LOSS_PCT:
                logger.warning(
                    f"⚠️  检测到紧急亏损 {symbol} {pnl_pct:.2f}% ≤ {EMERGENCY_STOP_LOSS_PCT}%"
                )
                
                # 🎯 v3.9.2.8：使用新的evaluate_loss_position方法
                if self.ml_predictor:
                    try:
                        # 🚨 v3.9.2.8.3: 强制刷新指标用于紧急止损ML分析（不使用缓存）
                        logger.debug(f"🔄 重新获取最新指标用于紧急止损分析 {symbol}")
                        current_indicators = await self._get_current_indicators(symbol)
                        
                        # 获取ML信心值（从position_states或使用默认值）
                        signal_confidence = 0.5
                        if symbol in self.position_states:
                            signal_confidence = self.position_states[symbol].get('ml_confidence', 0.5)
                        
                        # 使用新的智能平仓决策方法
                        ml_analysis = await self.ml_predictor.evaluate_loss_position(
                            symbol=symbol,
                            direction=direction,
                            entry_price=entry_price,
                            current_price=current_price,
                            pnl_pct=pnl_pct,
                            ml_confidence=signal_confidence,
                            indicators=current_indicators
                        )
                        
                        logger.info(
                            f"🎯 ML智能决策 {symbol}: {ml_analysis['reason']}"
                        )
                        
                        # 根据ML建议执行
                        if ml_analysis['action'] == 'close_immediately':
                            logger.warning(
                                f"🚨 ML强烈建议平仓 {symbol}: {ml_analysis['reason']}"
                            )
                            await self._force_close_position(symbol, direction, quantity, "ml_emergency_stop")
                            return None
                        elif ml_analysis['action'] == 'hold_and_monitor':
                            logger.info(
                                f"💡 ML建议继续持有 {symbol}: {ml_analysis['reason']}"
                            )
                            # 不执行强制平仓，让后续逻辑处理
                            pass
                        elif ml_analysis['action'] == 'adjust_stop_loss':
                            logger.info(
                                f"🔧 ML建议调整止损 {symbol} - 收紧止损到-{abs(pnl_pct)*1.05:.1f}%"
                            )
                            # 执行止损调整
                            new_stop_loss_pct = abs(pnl_pct) * 1.05  # 收紧5%
                            if direction == "LONG":
                                new_stop_price = entry_price * (1 - new_stop_loss_pct / 100)
                            else:
                                new_stop_price = entry_price * (1 + new_stop_loss_pct / 100)
                            
                            try:
                                # 更新止损订单
                                await self._update_stop_loss(symbol, direction, new_stop_price)
                                logger.info(f"✅ 已调整{symbol}止损至{new_stop_price:.4f}")
                            except Exception as e:
                                logger.error(f"调整止损失败 {symbol}: {e}")
                        
                    except Exception as e:
                        logger.error(f"ML智能决策失败 {symbol}: {e}，执行默认强制平仓")
                        await self._force_close_position(symbol, direction, quantity, "emergency_stop_loss")
                        return None
                else:
                    # 没有ML模型，使用传统强制平仓
                    await self._force_close_position(symbol, direction, quantity, "emergency_stop_loss")
                    return None
            
            # === 预警亏损：-30%到-50%之间，询问ML并可能调整策略 ===
            if pnl_pct <= ML_REBOUND_CHECK_THRESHOLD and self.ml_predictor:
                try:
                    # 🚨 v3.9.2.8.3: 强制刷新指标用于预警ML分析（不使用缓存）
                    logger.debug(f"🔄 重新获取最新指标用于预警止损分析 {symbol}")
                    current_indicators = await self._get_current_indicators(symbol)
                    
                    # 获取ML信心值
                    signal_confidence = 0.5
                    if symbol in self.position_states:
                        signal_confidence = self.position_states[symbol].get('ml_confidence', 0.5)
                    
                    # 🎯 v3.9.2.8：使用新的evaluate_loss_position方法
                    ml_analysis = await self.ml_predictor.evaluate_loss_position(
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        current_price=current_price,
                        pnl_pct=pnl_pct,
                        ml_confidence=signal_confidence,
                        indicators=current_indicators
                    )
                    
                    # 只记录日志，不强制平仓
                    if ml_analysis['action'] == 'close_immediately':
                        logger.warning(
                            f"⚠️  ML预警 {symbol}: {ml_analysis['reason']} - 建议关注"
                        )
                except Exception as e:
                    logger.debug(f"ML预警检查失败 {symbol}: {e}")
            
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
    
    async def _force_close_position(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        reason: str
    ):
        """
        强制平仓（紧急止损保护）
        
        Args:
            symbol: 交易对
            direction: 方向 (LONG/SHORT)
            quantity: 数量
            reason: 平仓原因
        """
        try:
            logger.critical(f"🚨 执行强制平仓: {symbol} {direction} 数量={quantity} 原因={reason}")
            
            # 调用交易服务的紧急平仓方法
            success = await self.trading_service._emergency_close_position(
                symbol=symbol,
                direction=direction,
                quantity=quantity
            )
            
            if success:
                logger.info(f"✅ 强制平仓成功: {symbol}")
                # 清理持仓状态
                if symbol in self.position_states:
                    del self.position_states[symbol]
            else:
                logger.critical(f"❌ 强制平仓失败: {symbol} - 需要人工介入！")
        
        except Exception as e:
            logger.critical(f"❌ 强制平仓异常: {symbol} - {e} - 需要人工介入！")
    
    async def _update_stop_loss(self, symbol: str, direction: str, new_stop_price: float):
        """
        更新止损价格
        
        🎯 v3.9.2.7新增：真正执行ML建议的止损调整
        
        Args:
            symbol: 交易对
            direction: 方向
            new_stop_price: 新止损价格
        """
        try:
            # 取消现有止损订单
            await self._cancel_existing_sl_tp_orders(symbol)
            
            # 获取当前持仓数量
            positions = await self.client.get_positions()
            position = next((p for p in positions if p['symbol'] == symbol), None)
            
            if not position:
                logger.warning(f"未找到持仓 {symbol}，无法更新止损")
                return
            
            quantity = abs(float(position['positionAmt']))
            
            # 设置新的止损订单
            side = "SELL" if direction == "LONG" else "BUY"
            
            await self.client.create_order(
                symbol=symbol,
                side=side,
                order_type='STOP_MARKET',
                quantity=quantity,
                stop_price=new_stop_price
            )
            
            # 更新持仓状态
            if symbol in self.position_states:
                self.position_states[symbol]['current_stop_loss'] = new_stop_price
            
            logger.info(f"✅ 更新止损成功 {symbol}: {new_stop_price:.4f}")
            
        except Exception as e:
            logger.error(f"更新止损失败 {symbol}: {e}")
            raise
    
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
    
    async def monitor_virtual_positions(self, get_indicators_fn=None) -> Dict:
        """
        🎯 v3.9.2.7新增：监控虚拟持仓，让ML模型分析
        🎯 v3.9.2.8性能优化：接受缓存函数，避免重复获取指标
        
        Args:
            get_indicators_fn: 获取指标的函数（可选），用于缓存优化
        
        Returns:
            Dict: 虚拟持仓统计信息
        """
        try:
            if not self.virtual_position_manager:
                return {'total': 0, 'ml_analyzed': 0}
            
            virtual_positions = self.virtual_position_manager.get_all_positions()
            active_virtual = [p for p in virtual_positions.values() if p.get('status') == 'active']
            
            if not active_virtual:
                return {'total': 0, 'ml_analyzed': 0}
            
            logger.info(f"\n🎯 虚拟持仓监控 [{len(active_virtual)}个]")
            
            ml_analyzed_count = 0
            
            for position in active_virtual:
                try:
                    symbol = position['symbol']
                    direction = position['direction']
                    entry_price = position['entry_price']
                    current_price = position['current_price']
                    pnl_pct = position['current_pnl']
                    
                    # 🎯 关键：让ML模型分析虚拟仓位
                    if self.ml_predictor and pnl_pct < -10:  # 亏损超过10%才询问ML
                        try:
                            # 🎯 v3.9.2.8: 使用缓存函数获取指标（如果提供）
                            if get_indicators_fn:
                                indicators = await get_indicators_fn(symbol)
                            else:
                                indicators = await self._get_current_indicators(symbol)
                            rebound_pred = await self.ml_predictor.predict_rebound(
                                symbol=symbol,
                                direction=direction,
                                entry_price=entry_price,
                                current_price=current_price,
                                pnl_pct=pnl_pct,
                                indicators=indicators
                            )
                            
                            if rebound_pred:
                                ml_analyzed_count += 1
                                logger.info(
                                    f"🤖 虚拟仓位ML分析 {symbol}: "
                                    f"{rebound_pred['recommended_action']} "
                                    f"(反弹:{rebound_pred['rebound_probability']:.0%})"
                                )
                        except Exception as e:
                            logger.debug(f"虚拟仓位ML分析失败 {symbol}: {e}")
                    
                except Exception as e:
                    logger.error(f"监控虚拟仓位失败: {e}")
            
            return {
                'total': len(active_virtual),
                'ml_analyzed': ml_analyzed_count
            }
            
        except Exception as e:
            logger.error(f"虚拟持仓监控失败: {e}")
            return {'total': 0, 'ml_analyzed': 0}
    
    async def _get_current_indicators(self, symbol: str) -> Optional[Dict]:
        """
        获取当前技术指标（用于ML反弹预测）
        
        🎯 v3.9.2.5新增：简化版指标获取
        
        Args:
            symbol: 交易对
        
        Returns:
            Optional[Dict]: 技术指标字典
        """
        try:
            # 尝试获取15m K线数据计算指标
            from src.utils.indicators import TechnicalIndicators
            
            # 获取最近50根15m K线
            klines = await self.client.get_klines(symbol, '15m', limit=50)
            
            if not klines or len(klines) < 20:
                logger.debug(f"K线数据不足，无法计算指标 {symbol}")
                return {}
            
            # 转换为DataFrame
            import pandas as pd
            # 🔧 显式定义列名以避免LSP类型推断问题
            column_names = [
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ]
            df = pd.DataFrame(data=klines, columns=column_names)
            
            # 转换数据类型
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 计算指标
            indicators_calc = TechnicalIndicators()
            close_prices = df['close'].values
            high_prices = df['high'].values
            low_prices = df['low'].values
            volumes = df['volume'].values
            
            # RSI
            rsi = indicators_calc.calculate_rsi(close_prices, period=14)
            
            # MACD
            macd_data = indicators_calc.calculate_macd(close_prices)
            macd_line = macd_data['macd']
            signal_line = macd_data['signal']
            histogram = macd_data['histogram']
            
            # 布林帶
            bb_data = indicators_calc.calculate_bollinger_bands(close_prices)
            bb_upper = bb_data['upper']
            bb_middle = bb_data['middle']
            bb_lower = bb_data['lower']
            current_price = close_prices[-1]
            bb_width_pct = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_middle.iloc[-1] * 100 if bb_middle.iloc[-1] > 0 else 0
            
            # 价格相对布林带位置 (0=下轨, 1=上轨)
            if bb_upper[-1] > bb_lower[-1]:
                price_vs_bb = (current_price - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1])
            else:
                price_vs_bb = 0.5
            
            indicators = {
                'rsi': rsi[-1] if len(rsi) > 0 else 50,
                'macd': macd_line[-1] if len(macd_line) > 0 else 0,
                'macd_signal': signal_line[-1] if len(signal_line) > 0 else 0,
                'macd_histogram': histogram[-1] if len(histogram) > 0 else 0,
                'bb_width_pct': bb_width_pct,
                'price_vs_bb': price_vs_bb
            }
            
            logger.debug(
                f"获取指标 {symbol}: RSI={indicators['rsi']:.1f}, "
                f"MACD={indicators['macd']:.6f}, BB宽度={indicators['bb_width_pct']:.2f}%"
            )
            
            return indicators
            
        except Exception as e:
            logger.warning(f"获取技术指标失败 {symbol}: {e}")
            return {}
