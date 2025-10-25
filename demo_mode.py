#!/usr/bin/env python3
"""
演示模式 - 使用模拟数据展示系统功能
不需要连接到真实的 Binance API
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd

from src.strategies.ict_strategy import ICTStrategy
from src.managers.risk_manager import RiskManager
from src.managers.expectancy_calculator import ExpectancyCalculator
from src.ml.data_archiver import DataArchiver
from src.config import Config


class MockBinanceData:
    """模拟 Binance 数据"""
    
    @staticmethod
    def generate_kline(symbol: str, base_price: float, timeframe: str, trend: str = 'bullish') -> List[List]:
        """生成模拟 K 线数据，可以指定趋势"""
        klines = []
        current_time = int(datetime.now().timestamp() * 1000)
        
        # 根据时间框架确定 K 线数量和间隔
        intervals = {
            '1h': (100, 3600000),
            '15m': (100, 900000),
            '5m': (200, 300000)
        }
        count, interval_ms = intervals.get(timeframe, (100, 3600000))
        
        # 趋势因子
        trend_factor = 1.002 if trend == 'bullish' else 0.998 if trend == 'bearish' else 1.0
        
        for i in range(count):
            timestamp = current_time - (count - i) * interval_ms
            
            # 生成带趋势的价格波动
            volatility = base_price * 0.015  # 1.5% 波动
            
            # 根据趋势生成价格
            if trend == 'bullish':
                open_price = base_price
                close = base_price * (1 + random.uniform(0.001, 0.015))  # 上涨
                high = close + random.uniform(0, volatility * 0.3)
                low = open_price - random.uniform(0, volatility * 0.2)
            elif trend == 'bearish':
                open_price = base_price
                close = base_price * (1 - random.uniform(0.001, 0.015))  # 下跌
                low = close - random.uniform(0, volatility * 0.3)
                high = open_price + random.uniform(0, volatility * 0.2)
            else:  # neutral
                open_price = base_price + random.uniform(-volatility, volatility)
                close = base_price + random.uniform(-volatility, volatility)
                high = max(open_price, close) + random.uniform(0, volatility * 0.5)
                low = min(open_price, close) - random.uniform(0, volatility * 0.5)
            
            volume = random.uniform(1000000, 10000000)
            
            # [timestamp, open, high, low, close, volume, ...]
            kline = [
                timestamp,
                str(open_price),
                str(high),
                str(low),
                str(close),
                str(volume),
                timestamp + interval_ms - 1,
                str(volume * close),
                100,
                str(volume * 0.5),
                str(volume * close * 0.5),
                "0"
            ]
            klines.append(kline)
            
            # 更新基准价格（带趋势）
            base_price = close * trend_factor
        
        return klines


class DemoTradingSystem:
    """演示交易系统"""
    
    def __init__(self):
        self.config = Config()
        self.strategy = ICTStrategy()
        self.risk_manager = RiskManager()
        self.expectancy_calculator = ExpectancyCalculator(window_size=30)
        self.data_archiver = DataArchiver(data_dir="ml_data")
        
        self.mock_data = MockBinanceData()
        self.all_trades = []
        self.account_balance = 10000.0  # 模拟账户余额
        
        # 模拟交易对
        self.symbols = [
            ('BTCUSDT', 45000.0),
            ('ETHUSDT', 2500.0),
            ('SOLUSDT', 100.0),
            ('BNBUSDT', 350.0),
            ('ADAUSDT', 0.5),
        ]
    
    def print_header(self):
        """打印标题"""
        print("\n" + "=" * 80)
        print("🎮 演示模式 - v3.0 高頻交易系統")
        print("=" * 80)
        print("\n📌 這是演示模式，使用模擬數據展示系統功能")
        print("📌 實際部署請使用 Railway 等支持的平台\n")
        print("系統配置:")
        print(f"  • 模擬賬戶餘額: ${self.account_balance:,.2f}")
        print(f"  • 監控交易對: {len(self.symbols)} 個")
        print(f"  • 最小信心度: {self.config.MIN_CONFIDENCE * 100:.0f}%")
        print(f"  • 期望值窗口: {self.expectancy_calculator.window_size} 筆交易")
        print("=" * 80 + "\n")
    
    async def generate_signals(self) -> List[Dict]:
        """生成交易信号"""
        signals = []
        
        print("🔍 掃描市場...")
        print("-" * 80)
        
        for symbol, base_price in self.symbols:
            # 随机选择趋势（增加获得信号的概率）
            trend = random.choice(['bullish', 'bullish', 'bearish', 'neutral'])  # 更多看涨
            
            # 生成 K 线数据（带趋势）
            h1_klines = self.mock_data.generate_kline(symbol, base_price, '1h', trend)
            m15_klines = self.mock_data.generate_kline(symbol, base_price, '15m', trend)
            m5_klines = self.mock_data.generate_kline(symbol, base_price, '5m', trend)
            
            # 转换为 DataFrame
            def klines_to_df(klines):
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                    'taker_buy_quote', 'ignore'
                ])
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                return df
            
            multi_tf_data = {
                '1h': klines_to_df(h1_klines),
                '15m': klines_to_df(m15_klines),
                '5m': klines_to_df(m5_klines)
            }
            
            # 分析信号
            signal = self.strategy.analyze(
                symbol=symbol,
                multi_tf_data=multi_tf_data
            )
            
            if signal:
                signals.append(signal)
                
                # 打印信号详情
                direction = "🟢 LONG" if signal['direction'] == 'LONG' else "🔴 SHORT"
                print(f"\n✨ {symbol} {direction}")
                print(f"   信心度: {signal['confidence'] * 100:.1f}%")
                print(f"   子指標:")
                print(f"     • 趨勢對齊: {signal['scores']['trend_alignment'] * 100:.0f}%")
                print(f"     • 市場結構: {signal['scores']['market_structure'] * 100:.0f}%")
                print(f"     • 價格位置: {signal['scores']['price_position'] * 100:.0f}%")
                print(f"     • 動量指標: {signal['scores']['momentum'] * 100:.0f}%")
                print(f"     • 波動率: {signal['scores']['volatility'] * 100:.0f}%")
                print(f"   價格: {signal['entry_price']:.2f}")
                print(f"   止損: {signal['stop_loss']:.2f}")
                print(f"   止盈: {signal['take_profit']:.2f}")
        
        print("-" * 80)
        print(f"\n📊 共生成 {len(signals)} 個交易信號\n")
        
        return signals
    
    def process_signals(self, signals: List[Dict]):
        """处理交易信号"""
        if not signals:
            print("⚠️  當前市場條件下無符合條件的信號\n")
            return
        
        print("=" * 80)
        print("🎯 處理交易信號")
        print("=" * 80 + "\n")
        
        for i, signal in enumerate(signals, 1):
            print(f"\n[信號 {i}/{len(signals)}] {signal['symbol']} {signal['direction']}")
            print("-" * 60)
            
            # 1. 计算期望值指标
            expectancy_metrics = self.expectancy_calculator.calculate_expectancy(self.all_trades)
            
            if len(self.all_trades) >= 30:
                print(f"✅ 期望值指標:")
                print(f"   • 期望值: {expectancy_metrics['expectancy']:.2f}%")
                print(f"   • 盈虧比: {expectancy_metrics['profit_factor']:.2f}")
                print(f"   • 勝率: {expectancy_metrics['win_rate'] * 100:.1f}%")
                print(f"   • 連續虧損: {expectancy_metrics['consecutive_losses']}")
                
                # 2. 期望值检查
                can_trade, reason = self.expectancy_calculator.should_trade(
                    expectancy=expectancy_metrics['expectancy'],
                    profit_factor=expectancy_metrics['profit_factor'],
                    consecutive_losses=expectancy_metrics['consecutive_losses'],
                    daily_loss_pct=self.expectancy_calculator.get_daily_loss(self.all_trades)
                )
                
                if not can_trade:
                    print(f"❌ 期望值檢查未通過: {reason}")
                    self.data_archiver.archive_signal(signal, accepted=False, rejection_reason=reason)
                    continue
                
                # 3. 计算动态杠杆
                leverage = self.risk_manager.calculate_leverage(
                    expectancy=expectancy_metrics['expectancy'],
                    profit_factor=expectancy_metrics['profit_factor'],
                    consecutive_losses=expectancy_metrics['consecutive_losses']
                )
                print(f"   • 建議槓桿: {leverage}x")
            else:
                print(f"⚠️  交易記錄不足（{len(self.all_trades)}/30），使用默認設置")
                leverage = 10
            
            # 4. 风险管理检查
            can_trade_risk, risk_reason = self.risk_manager.should_trade(
                self.account_balance, len([t for t in self.all_trades if not t.get('closed', False)])
            )
            
            if not can_trade_risk:
                print(f"❌ 風險管理限制: {risk_reason}")
                self.data_archiver.archive_signal(signal, accepted=False, rejection_reason=risk_reason)
                continue
            
            # 5. 记录接受的信号
            print(f"✅ 信號已接受")
            self.data_archiver.archive_signal(signal, accepted=True)
            
            # 6. 模拟开仓
            position = {
                'position_id': f"DEMO_{len(self.all_trades):04d}",
                'symbol': signal['symbol'],
                'direction': signal['direction'],
                'entry_price': signal['entry_price'],
                'stop_loss': signal['stop_loss'],
                'take_profit': signal['take_profit'],
                'leverage': leverage,
                'confidence': signal['confidence'],
                'quantity': 0.01,
                'is_virtual': True,
                'timestamp': datetime.now(),
                'closed': False
            }
            
            # 模拟交易结果（随机）
            win_prob = signal['confidence']  # 信心度越高，获胜概率越高
            won = random.random() < win_prob
            
            if won:
                pnl_pct = random.uniform(0.5, 3.0)
                close_reason = 'TAKE_PROFIT'
            else:
                pnl_pct = random.uniform(-2.0, -0.5)
                close_reason = 'STOP_LOSS'
            
            position['pnl_pct'] = pnl_pct
            position['pnl'] = self.account_balance * pnl_pct / 100
            position['won'] = won
            position['close_reason'] = close_reason
            position['closed'] = True
            
            # 记录交易
            self.all_trades.append(position)
            self.account_balance += position['pnl']
            
            # 归档仓位
            self.data_archiver.archive_position_open({**position, **signal['scores']}, is_virtual=True)
            self.data_archiver.archive_position_close(
                {**position, **signal['scores']},
                {'pnl': position['pnl'], 'pnl_pct': pnl_pct, 'close_price': signal['entry_price'] * (1 + pnl_pct/100)},
                is_virtual=True
            )
            
            # 打印结果
            result = "✅ 盈利" if won else "❌ 虧損"
            print(f"\n   模擬交易結果: {result}")
            print(f"   • 盈虧: ${position['pnl']:.2f} ({pnl_pct:+.2f}%)")
            print(f"   • 新餘額: ${self.account_balance:,.2f}")
    
    def print_summary(self):
        """打印总结"""
        print("\n" + "=" * 80)
        print("📊 演示總結")
        print("=" * 80 + "\n")
        
        if not self.all_trades:
            print("未執行任何交易")
            return
        
        won_trades = [t for t in self.all_trades if t.get('won', False)]
        lost_trades = [t for t in self.all_trades if not t.get('won', False)]
        
        total_pnl = sum(t.get('pnl', 0) for t in self.all_trades)
        win_rate = len(won_trades) / len(self.all_trades) if self.all_trades else 0
        
        print(f"交易統計:")
        print(f"  • 總交易數: {len(self.all_trades)}")
        print(f"  • 盈利交易: {len(won_trades)} ({win_rate * 100:.1f}%)")
        print(f"  • 虧損交易: {len(lost_trades)}")
        print(f"  • 總盈虧: ${total_pnl:+,.2f} ({total_pnl / 10000 * 100:+.2f}%)")
        print(f"  • 最終餘額: ${self.account_balance:,.2f}")
        
        # 期望值指标
        if len(self.all_trades) >= 5:
            metrics = self.expectancy_calculator.calculate_expectancy(self.all_trades)
            print(f"\n期望值指標:")
            print(f"  • 期望值: {metrics['expectancy']:.2f}%")
            print(f"  • 盈虧比: {metrics['profit_factor']:.2f}")
            print(f"  • 平均盈利: {metrics['avg_win']:.2f}%")
            print(f"  • 平均虧損: {metrics['avg_loss']:.2f}%")
        
        # 数据归档
        self.data_archiver.flush_all()
        print(f"\n數據歸檔:")
        print(f"  • signals.csv: 已保存")
        print(f"  • positions.csv: 已保存")
        print(f"  • 位置: ml_data/")
        
        print("\n" + "=" * 80)
        print("🎉 演示完成！")
        print("=" * 80)
        print("\n💡 提示: 實際部署請使用 Railway 等支持 Binance API 的平台")
        print("   詳見: DEPLOYMENT_GUIDE.md\n")
    
    async def run(self):
        """运行演示"""
        self.print_header()
        
        # 生成信号
        signals = await self.generate_signals()
        
        # 处理信号
        self.process_signals(signals)
        
        # 打印总结
        self.print_summary()


async def main():
    """主函数"""
    demo = DemoTradingSystem()
    await demo.run()


if __name__ == "__main__":
    print("\n" + "🎮" * 40)
    print("演示模式啟動中...")
    print("🎮" * 40 + "\n")
    
    asyncio.run(main())
