"""
交易模拟器 - 生成100笔随机交易数据
测试豁免期策略的完整流程
"""

import logging
import random
import time
from typing import Dict, List
from datetime import datetime

from src.core.unified_config_manager import config_manager as config
from src.simulation.mock_binance_client import MockBinanceClient
from src.strategies.self_learning_trader import SelfLearningTrader
from src.managers.unified_trade_recorder import UnifiedTradeRecorder
from src.ml.feature_engine import FeatureEngine

logger = logging.getLogger(__name__)


class TradeSimulator:
    """
    交易模拟器
    
    功能：
    1. 生成随机交易信号（胜率、信心、RR等）
    2. 模拟交易执行和结果
    3. 记录完整交易数据
    4. 验证豁免期策略切换
    """
    
    def __init__(
        self,
        config: Config,
        mock_client: MockBinanceClient,
        trader: SelfLearningTrader,
        trade_recorder: UnifiedTradeRecorder
    ):
        self.config = config
        self.mock_client = mock_client
        self.trader = trader
        self.trade_recorder = trade_recorder
        
        logger.info("=" * 80)
        logger.info("🎮 TradeSimulator 初始化完成")
        logger.info(f"   🎯 目标: 生成100笔模拟交易")
        logger.info(f"   📊 豁免期门槛: {config.BOOTSTRAP_TRADE_LIMIT}笔")
        logger.info("=" * 80)
    
    def generate_random_signal(self, trade_number: int) -> Dict:
        """
        生成随机交易信号
        
        Args:
            trade_number: 交易编号（1-100）
            
        Returns:
            交易信号字典
        """
        # 随机选择交易对
        symbol = random.choice(self.mock_client.symbols)
        
        # 根据交易编号调整信号质量（模拟学习过程）
        # 前50笔：质量较低（40-60%）
        # 后50笔：质量提升（50-75%）
        if trade_number <= 50:
            win_probability = random.uniform(0.40, 0.60)
            confidence = random.uniform(0.40, 0.60)
        else:
            win_probability = random.uniform(0.50, 0.75)
            confidence = random.uniform(0.50, 0.75)
        
        # 随机方向
        direction = random.choice(['LONG', 'SHORT'])
        
        # 获取当前价格
        current_price = self.mock_client.current_prices.get(symbol, 100.0)
        
        # 随机止损距离（0.5% - 2%）
        sl_distance_pct = random.uniform(0.005, 0.02)
        tp_distance_pct = sl_distance_pct * random.uniform(1.5, 3.0)  # RR 1.5-3.0
        
        if direction == 'LONG':
            entry_price = current_price
            stop_loss = entry_price * (1 - sl_distance_pct)
            take_profit = entry_price * (1 + tp_distance_pct)
        else:
            entry_price = current_price
            stop_loss = entry_price * (1 + sl_distance_pct)
            take_profit = entry_price * (1 - tp_distance_pct)
        
        # 计算RR比
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        rr_ratio = reward / risk if risk > 0 else 2.0
        
        signal = {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'win_probability': win_probability,
            'confidence': confidence,
            'rr_ratio': rr_ratio,
            'timestamp': datetime.now().isoformat(),
            'trade_number': trade_number
        }
        
        return signal
    
    def simulate_trade_outcome(self, signal: Dict) -> str:
        """
        模拟交易结果
        
        Args:
            signal: 交易信号
            
        Returns:
            'WIN' 或 'LOSS'
        """
        # 使用win_probability决定结果
        win_prob = signal['win_probability']
        return 'WIN' if random.random() < win_prob else 'LOSS'
    
    def execute_simulated_trade(self, signal: Dict) -> Dict:
        """
        执行模拟交易
        
        Args:
            signal: 交易信号
            
        Returns:
            交易结果字典
        """
        symbol = signal['symbol']
        direction = signal['direction']
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        take_profit = signal['take_profit']
        
        # 获取当前账户余额
        account = self.mock_client.get_account_balance()
        available_balance = account['availableBalance']
        
        # 计算杠杆（通过trader）
        leverage = self.trader.leverage_engine.calculate_leverage(
            signal['win_probability'],
            signal['confidence'],
            is_bootstrap_period=(signal['trade_number'] <= self.config.BOOTSTRAP_TRADE_LIMIT),
            verbose=True
        )
        
        # 计算仓位大小（假设使用20%可用余额）
        risk_capital = available_balance * 0.20
        sl_distance = abs(entry_price - stop_loss) / entry_price
        position_value = risk_capital / sl_distance
        quantity = position_value / entry_price
        
        # 确保满足最小名义价值（10 USDT）
        notional = quantity * entry_price * leverage
        if notional < 10:
            quantity = 10 / (entry_price * leverage)
            notional = 10
        
        # 记录入场
        side = 'BUY' if direction == 'LONG' else 'SELL'
        order = self.mock_client.place_order(
            symbol=symbol,
            side=side,
            order_type='MARKET',
            quantity=quantity,
            leverage=leverage
        )
        
        # 模拟交易结果
        outcome = self.simulate_trade_outcome(signal)
        
        # 计算退出价格
        if outcome == 'WIN':
            exit_price = take_profit
            pnl_pct = abs(take_profit - entry_price) / entry_price
        else:
            exit_price = stop_loss
            pnl_pct = -abs(stop_loss - entry_price) / entry_price
        
        # SHORT时反转PnL
        if direction == 'SHORT':
            pnl_pct = -pnl_pct
        
        # 计算实际PnL
        pnl = notional * pnl_pct
        
        # 平仓
        close_side = 'SELL' if direction == 'LONG' else 'BUY'
        self.mock_client.place_order(
            symbol=symbol,
            side=close_side,
            order_type='MARKET',
            quantity=quantity,
            price=exit_price,
            leverage=leverage
        )
        
        # 更新余额
        self.mock_client.balance += pnl
        
        result = {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'leverage': leverage,
            'quantity': quantity,
            'notional': notional,
            'outcome': outcome,
            'pnl': pnl,
            'pnl_pct': pnl_pct * 100,
            'win_probability': signal['win_probability'],
            'confidence': signal['confidence'],
            'rr_ratio': signal['rr_ratio'],
            'trade_number': signal['trade_number'],
            'is_bootstrap': signal['trade_number'] <= self.config.BOOTSTRAP_TRADE_LIMIT
        }
        
        return result
    
    def run_simulation(self, num_trades: int = 100) -> List[Dict]:
        """
        运行完整模拟
        
        Args:
            num_trades: 交易数量
            
        Returns:
            所有交易结果列表
        """
        logger.info("=" * 80)
        logger.info(f"🎮 开始模拟 {num_trades} 笔交易")
        logger.info("=" * 80)
        
        all_trades = []
        
        for i in range(1, num_trades + 1):
            # 生成信号
            signal = self.generate_random_signal(i)
            
            # 执行交易
            result = self.execute_simulated_trade(signal)
            all_trades.append(result)
            
            # 记录到trade_recorder（用于豁免期计数）
            # 模拟完整的entry/exit记录
            try:
                # 创建模拟的signal和position_info
                entry_signal = {
                    'symbol': result['symbol'],
                    'direction': result['direction'],
                    'entry_price': result['entry_price'],
                    'stop_loss': result['stop_loss'],
                    'take_profit': result['take_profit'],
                    'win_probability': result['win_probability'],
                    'confidence': result['confidence'],
                    'rr_ratio': result['rr_ratio'],
                    'features': {}  # 简化特征
                }
                
                position_info = {
                    'symbol': result['symbol'],
                    'quantity': result['quantity'],
                    'leverage': result['leverage'],
                    'entry_price': result['entry_price'],
                    'orderId': i
                }
                
                # 记录entry（UnifiedTradeRecorder API）
                trade_id = self.trade_recorder.record_entry(
                    symbol=result['symbol'],
                    direction=result['direction'],
                    entry_price=result['entry_price'],
                    quantity=result['quantity'],
                    leverage=result['leverage'],
                    signal_data=entry_signal,
                    klines_data={}  # 模拟模式无K线数据
                )
                
                # 记录exit（UnifiedTradeRecorder API）
                if trade_id is not None:
                    self.trade_recorder.record_exit(
                        trade_id=trade_id,
                        exit_price=result['exit_price'],
                        pnl=result['pnl'],
                        pnl_pct=result['pnl_pct'],
                        reason='TP' if result['outcome'] == 'WIN' else 'SL'
                    )
                else:
                    logger.warning(f"⚠️ 交易{i}开仓记录失败，跳过平仓记录")
                
                # 使缓存失效
                self.trader.invalidate_trades_cache()
                
            except Exception as e:
                logger.warning(f"⚠️ 交易记录失败: {e}")
            
            # 日志输出
            phase = "🎓 豁免期" if result['is_bootstrap'] else "📊 正常期"
            outcome_icon = "✅" if result['outcome'] == 'WIN' else "❌"
            
            logger.info(
                f"{phase} #{i:03d} | {outcome_icon} {result['symbol']} {result['direction']} | "
                f"杠杆:{result['leverage']:.1f}x | "
                f"胜率:{result['win_probability']:.0%} 信心:{result['confidence']:.0%} | "
                f"PnL: ${result['pnl']:+.2f} ({result['pnl_pct']:+.2f}%)"
            )
            
            # 豁免期结束提示
            if i == self.config.BOOTSTRAP_TRADE_LIMIT:
                logger.info("=" * 80)
                logger.info("🎓 豁免期结束！")
                logger.info(f"   已完成 {i} 笔交易")
                logger.info("   切换至正常期门槛和杠杆策略")
                logger.info("=" * 80)
            
            # 短暂延迟（可选）
            # time.sleep(0.1)
        
        return all_trades
    
    def print_summary(self, trades: List[Dict]):
        """打印模拟总结"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 模拟交易总结")
        logger.info("=" * 80)
        
        # 分阶段统计
        bootstrap_trades = [t for t in trades if t['is_bootstrap']]
        normal_trades = [t for t in trades if not t['is_bootstrap']]
        
        def calc_stats(trade_list, phase_name):
            if not trade_list:
                return
            
            wins = [t for t in trade_list if t['outcome'] == 'WIN']
            losses = [t for t in trade_list if t['outcome'] == 'LOSS']
            
            win_rate = len(wins) / len(trade_list) * 100
            total_pnl = sum(t['pnl'] for t in trade_list)
            avg_leverage = sum(t['leverage'] for t in trade_list) / len(trade_list)
            min_leverage = min(t['leverage'] for t in trade_list)
            max_leverage = max(t['leverage'] for t in trade_list)
            
            logger.info(f"\n{phase_name}:")
            logger.info(f"  交易数: {len(trade_list)}")
            logger.info(f"  胜率: {win_rate:.1f}% ({len(wins)}胜 / {len(losses)}败)")
            logger.info(f"  总盈亏: ${total_pnl:+,.2f}")
            logger.info(f"  平均杠杆: {avg_leverage:.2f}x")
            logger.info(f"  杠杆范围: {min_leverage:.2f}x - {max_leverage:.2f}x")
        
        calc_stats(bootstrap_trades, "🎓 豁免期 (1-100笔)")
        calc_stats(normal_trades, "📊 正常期 (101+笔)")
        
        # 整体统计
        total_pnl = sum(t['pnl'] for t in trades)
        final_balance = self.mock_client.balance
        roi = (final_balance - self.mock_client.initial_balance) / self.mock_client.initial_balance * 100
        
        logger.info(f"\n💰 资金统计:")
        logger.info(f"  初始余额: ${self.mock_client.initial_balance:,.2f}")
        logger.info(f"  最终余额: ${final_balance:,.2f}")
        logger.info(f"  总盈亏: ${total_pnl:+,.2f}")
        logger.info(f"  ROI: {roi:+.2f}%")
        logger.info("=" * 80)
