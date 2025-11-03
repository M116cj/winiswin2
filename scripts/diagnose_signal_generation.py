#!/usr/bin/env python3
"""
信号生成深度诊断工具 - 简化版

基于用户提供的诊断指令，使用现有系统组件进行端到端诊断
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategies.rule_based_signal_generator import RuleBasedSignalGenerator
from src.services.data_service import DataService
from src.core.elite import EliteTechnicalEngine
from src.clients.binance_client import BinanceClient
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def diagnose_single_symbol(symbol: str, binance_client, data_service, signal_generator):
    """诊断单个交易对的完整信号生成流程"""
    
    print(f"\n{'='*70}")
    print(f"🚀 **开始诊断**: {symbol}")
    print(f"{'='*70}\n")
    
    # ========================
    # 第一阶段：数据获取诊断
    # ========================
    print(f"📊 **第一阶段：数据获取诊断**\n")
    
    try:
        timeframes = ['1h', '15m', '5m']
        klines_data = {}
        
        for tf in timeframes:
            print(f"  ⏱️  获取 {tf} 数据...")
            data = await data_service.get_klines(symbol, tf, limit=100)
            
            if data is None or data.empty:
                print(f"    ❌ {tf}: 数据为空")
                continue
            
            klines_data[tf] = data
            print(f"    ✅ {tf}: {len(data)}行数据")
            
            # 检查数据完整性
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing = [col for col in required_cols if col not in data.columns]
            if missing:
                print(f"    ⚠️  缺少列: {missing}")
            
            # 检查NaN
            nan_count = data[required_cols].isnull().sum().sum()
            if nan_count > 0:
                print(f"    ⚠️  发现 {nan_count} 个NaN值")
        
        if len(klines_data) != 3:
            print(f"\n  ❌ **数据获取失败**: 只获取到{len(klines_data)}/3个时间框架")
            return None
        
        print(f"\n  ✅ **数据获取阶段：通过**\n")
        
    except Exception as e:
        print(f"\n  ❌ **数据获取异常**: {e}\n")
        import traceback
        print(traceback.format_exc())
        return None
    
    # ========================
    # 第二阶段：技术指标诊断
    # ========================
    print(f"📈 **第二阶段：技术指标诊断**\n")
    
    tech_engine = EliteTechnicalEngine()
    
    try:
        # 使用1h数据测试指标
        df_1h = klines_data['1h']
        
        print(f"  🔹 测试EMA指标:")
        ema20 = tech_engine.calculate('ema', df_1h, period=20)
        print(f"    ✅ EMA20: {ema20.value:.2f if ema20.value is not None else 'None'}")
        
        print(f"\n  🔹 测试RSI指标:")
        rsi = tech_engine.calculate('rsi', df_1h, period=14)
        print(f"    ✅ RSI14: {rsi.value:.2f if rsi.value is not None else 'None'}")
        
        print(f"\n  🔹 测试MACD指标:")
        macd = tech_engine.calculate('macd', df_1h)
        if macd.value and isinstance(macd.value, dict):
            print(f"    ✅ MACD: {macd.value.get('macd', 0):.2f}")
        else:
            print(f"    ⚠️  MACD: 计算异常")
        
        print(f"\n  🔹 测试ICT指标:")
        
        # Market Structure
        ms = tech_engine.calculate('market_structure', df_1h, lookback=10)
        print(f"    ✅ Market Structure: {ms.value}")
        
        # Order Blocks
        ob = tech_engine.calculate('order_blocks', df_1h, lookback=20)
        print(f"    ✅ Order Blocks: 检测到{len(ob.value)}个订单块")
        
        # Fair Value Gaps
        fvg = tech_engine.calculate('fvg', df_1h)
        print(f"    ✅ Fair Value Gaps: 检测到{len(fvg.value)}个缺口")
        
        print(f"\n  ✅ **技术指标阶段：通过**\n")
        
    except Exception as e:
        print(f"\n  ❌ **技术指标异常**: {e}\n")
        import traceback
        print(traceback.format_exc())
        return None
    
    # ========================
    # 第三阶段：信号生成诊断
    # ========================
    print(f"🎯 **第三阶段：信号生成诊断**\n")
    
    try:
        print(f"  🚀 开始信号生成...")
        signal = await signal_generator.generate_signal(symbol, klines_data)
        
        if signal is None:
            print(f"  ⚠️  **信号生成返回None** - 可能未达到信号生成条件\n")
            return None
        
        print(f"\n  ✅ **信号生成成功**:")
        print(f"    交易对: {symbol}")
        print(f"    方向: {signal.get('direction', 'N/A')}")
        print(f"    信心值: {signal.get('confidence', 0)}%")
        print(f"    杠杆: {signal.get('leverage', 1)}x")
        print(f"    入场价: {signal.get('entry_price', 0)}")
        print(f"    止损: {signal.get('stop_loss', 0)}")
        print(f"    止盈: {signal.get('take_profit', 0)}")
        print(f"    原因: {signal.get('reason', 'N/A')}\n")
        
        return signal
        
    except Exception as e:
        print(f"\n  ❌ **信号生成异常**: {e}\n")
        import traceback
        print(traceback.format_exc())
        return None


async def main():
    """主函数"""
    print(f"\n{'*'*70}")
    print(f"*  🔍 **信号生成深度诊断工具**")
    print(f"*  基于Phase 6完成的Elite架构")
    print(f"{'*'*70}\n")
    
    # 初始化客户端
    print(f"🔧 初始化系统组件...\n")
    
    try:
        binance_client = BinanceClient()
        data_service = DataService(binance_client=binance_client, perf_monitor=None, websocket_monitor=None)
        signal_generator = RuleBasedSignalGenerator()
        
        print(f"✅ 系统组件初始化成功\n")
        
    except Exception as e:
        print(f"❌ 系统初始化失败: {e}")
        import traceback
        print(traceback.format_exc())
        return
    
    # 测试关键交易对
    test_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    
    results = {}
    
    for i, symbol in enumerate(test_symbols, 1):
        print(f"\n[{i}/{len(test_symbols)}] 诊断: {symbol}")
        signal = await diagnose_single_symbol(symbol, binance_client, data_service, signal_generator)
        results[symbol] = signal
        
        # 避免API限流
        if i < len(test_symbols):
            await asyncio.sleep(1)
    
    # ========================
    # 汇总报告
    # ========================
    print(f"\n\n{'*'*70}")
    print(f"*  📊 **诊断汇总报告**")
    print(f"{'*'*70}\n")
    
    signal_count = sum(1 for s in results.values() if s is not None)
    no_signal_count = sum(1 for s in results.values() if s is None)
    
    print(f"**统计结果**:")
    print(f"  总测试数: {len(test_symbols)}")
    print(f"  成功生成信号: {signal_count}")
    print(f"  未生成信号: {no_signal_count}")
    print(f"  成功率: {signal_count/len(test_symbols)*100:.1f}%\n")
    
    if signal_count > 0:
        print(f"**生成的信号**:")
        for symbol, signal in results.items():
            if signal:
                print(f"  ✅ {symbol}: {signal['direction']} (信心值: {signal['confidence']}%)")
    
    if no_signal_count > 0:
        print(f"\n**未生成信号的交易对**:")
        for symbol, signal in results.items():
            if not signal:
                print(f"  ⚠️  {symbol}: 未达到信号生成条件")
    
    print(f"\n✅ **诊断完成！**\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n⚠️  诊断被用户中断")
    except Exception as e:
        print(f"\n\n❌ 诊断过程发生错误: {e}")
        import traceback
        print(traceback.format_exc())
