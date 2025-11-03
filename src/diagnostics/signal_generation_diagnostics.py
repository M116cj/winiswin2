"""
信号生成深度诊断工具

根据用户提供的诊断指令，从数据源头到信号输出的每个环节进行详细检查
"""

import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import traceback

from src.core.data_fetcher import DataFetcher
from src.strategies.rule_based_signal_generator import RuleBasedSignalGenerator
from src.core.elite import EliteTechnicalEngine


class SignalGenerationDiagnostics:
    """信号生成诊断工具"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.signal_generator = RuleBasedSignalGenerator()
        self.tech_engine = EliteTechnicalEngine()
        
        # 最低数据要求
        self.MINIMUM_DATA_REQUIREMENTS = {
            '1h': 20,    # EMA20需要至少20行
            '15m': 20,
            '5m': 20
        }
        
        # 技术指标最低要求
        self.INDICATOR_REQUIREMENTS = {
            'EMA20': 20,
            'EMA50': 50,
            'RSI14': 15,
            'BBANDS': 20,
            'MACD': 26
        }
    
    async def debug_data_acquisition(self, symbol: str) -> Dict:
        """
        第一阶段：数据流追踪
        检查数据获取完整性
        """
        print(f"\n{'='*60}")
        print(f"🔍 **第一阶段：数据获取诊断** - {symbol}")
        print(f"{'='*60}\n")
        
        result = {
            'symbol': symbol,
            'success': False,
            'data': {},
            'issues': []
        }
        
        try:
            # 1. 获取多时间框架数据
            print(f"📥 正在获取多时间框架数据...")
            data = await self.data_fetcher.get_multi_timeframe_data(symbol)
            
            if not data:
                result['issues'].append("❌ 数据获取失败：返回空数据")
                return result
            
            # 2. 检查每个时间框架
            for timeframe, df in data.items():
                print(f"\n  ⏱️  时间框架: {timeframe}")
                
                if df is None or df.empty:
                    issue = f"❌ {timeframe}: 数据为空"
                    result['issues'].append(issue)
                    print(f"    {issue}")
                    continue
                
                # 检查数据行数
                row_count = len(df)
                min_required = self.MINIMUM_DATA_REQUIREMENTS.get(timeframe, 20)
                
                if row_count < min_required:
                    issue = f"⚠️  {timeframe}: 数据不足（{row_count}行 < {min_required}行）"
                    result['issues'].append(issue)
                    print(f"    {issue}")
                else:
                    print(f"    ✅ 数据行数: {row_count}行（>= {min_required}行）")
                
                # 检查列完整性
                required_columns = ['open', 'high', 'low', 'close', 'volume']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    issue = f"❌ {timeframe}: 缺少列 {missing_columns}"
                    result['issues'].append(issue)
                    print(f"    {issue}")
                else:
                    print(f"    ✅ 列完整性: {required_columns}")
                
                # 检查数据类型
                for col in required_columns:
                    if col in df.columns:
                        dtype = df[col].dtype
                        if dtype not in [np.float64, np.int64, np.float32, np.int32]:
                            issue = f"⚠️  {timeframe}.{col}: 数据类型={dtype}（非数值）"
                            result['issues'].append(issue)
                            print(f"    {issue}")
                
                # 检查NaN值
                nan_counts = df[required_columns].isnull().sum()
                if nan_counts.any():
                    for col, count in nan_counts.items():
                        if count > 0:
                            issue = f"⚠️  {timeframe}.{col}: {count}个NaN值"
                            result['issues'].append(issue)
                            print(f"    {issue}")
                else:
                    print(f"    ✅ 无NaN值")
                
                # 检查异常值（价格<=0, 成交量<0）
                if 'close' in df.columns and (df['close'] <= 0).any():
                    issue = f"❌ {timeframe}: 检测到异常价格（<=0）"
                    result['issues'].append(issue)
                    print(f"    {issue}")
                
                if 'volume' in df.columns and (df['volume'] < 0).any():
                    issue = f"❌ {timeframe}: 检测到异常成交量（<0）"
                    result['issues'].append(issue)
                    print(f"    {issue}")
                
                # 存储数据
                result['data'][timeframe] = {
                    'rows': row_count,
                    'columns': list(df.columns),
                    'dtypes': {col: str(df[col].dtype) for col in df.columns},
                    'nan_counts': nan_counts.to_dict(),
                    'sample_close': float(df['close'].iloc[-1]) if 'close' in df.columns else None
                }
            
            result['success'] = len(result['issues']) == 0
            
            if result['success']:
                print(f"\n✅ **数据获取阶段：通过**")
            else:
                print(f"\n⚠️  **数据获取阶段：发现 {len(result['issues'])} 个问题**")
            
        except Exception as e:
            error_msg = f"❌ 数据获取异常: {str(e)}"
            result['issues'].append(error_msg)
            print(f"\n{error_msg}")
            print(f"详细错误:\n{traceback.format_exc()}")
        
        return result
    
    def debug_technical_indicators(self, symbol: str, data: Dict) -> Dict:
        """
        第二阶段：技术指标计算检查
        """
        print(f"\n{'='*60}")
        print(f"📊 **第二阶段：技术指标诊断** - {symbol}")
        print(f"{'='*60}\n")
        
        result = {
            'symbol': symbol,
            'success': False,
            'indicators': {},
            'issues': []
        }
        
        try:
            # 使用1h数据进行诊断
            if '1h' not in data or data['1h'] is None or data['1h'].empty:
                result['issues'].append("❌ 无法进行技术指标诊断：1h数据缺失")
                return result
            
            df = data['1h']
            close_prices = df['close']
            
            print(f"📈 数据长度: {len(close_prices)}行\n")
            
            # 检查EMA
            print("  🔹 EMA指标检查:")
            for period in [20, 50]:
                if len(close_prices) >= period:
                    try:
                        ema_result = self.tech_engine.calculate('ema', df, period=period)
                        ema_value = ema_result.value
                        
                        if ema_value is not None and not pd.isna(ema_value):
                            result['indicators'][f'EMA{period}'] = float(ema_value)
                            print(f"    ✅ EMA{period}: {ema_value:.2f}")
                        else:
                            issue = f"⚠️  EMA{period}: 计算结果为NaN"
                            result['issues'].append(issue)
                            print(f"    {issue}")
                    except Exception as e:
                        issue = f"❌ EMA{period}: 计算失败 - {str(e)}"
                        result['issues'].append(issue)
                        print(f"    {issue}")
                else:
                    issue = f"⚠️  EMA{period}: 数据不足（{len(close_prices)} < {period}）"
                    result['issues'].append(issue)
                    print(f"    {issue}")
            
            # 检查RSI
            print("\n  🔹 RSI指标检查:")
            if len(close_prices) >= 15:
                try:
                    rsi_result = self.tech_engine.calculate('rsi', df, period=14)
                    rsi_value = rsi_result.value
                    
                    if rsi_value is not None and not pd.isna(rsi_value):
                        result['indicators']['RSI14'] = float(rsi_value)
                        print(f"    ✅ RSI14: {rsi_value:.2f}")
                    else:
                        issue = "⚠️  RSI14: 计算结果为NaN"
                        result['issues'].append(issue)
                        print(f"    {issue}")
                except Exception as e:
                    issue = f"❌ RSI14: 计算失败 - {str(e)}"
                    result['issues'].append(issue)
                    print(f"    {issue}")
            else:
                issue = f"⚠️  RSI14: 数据不足（{len(close_prices)} < 15）"
                result['issues'].append(issue)
                print(f"    {issue}")
            
            # 检查MACD
            print("\n  🔹 MACD指标检查:")
            if len(close_prices) >= 26:
                try:
                    macd_result = self.tech_engine.calculate('macd', df)
                    macd_value = macd_result.value
                    
                    if macd_value is not None and isinstance(macd_value, dict):
                        result['indicators']['MACD'] = macd_value
                        print(f"    ✅ MACD: macd={macd_value.get('macd', 'N/A'):.2f}, "
                              f"signal={macd_value.get('signal', 'N/A'):.2f}, "
                              f"histogram={macd_value.get('histogram', 'N/A'):.2f}")
                    else:
                        issue = "⚠️  MACD: 计算结果异常"
                        result['issues'].append(issue)
                        print(f"    {issue}")
                except Exception as e:
                    issue = f"❌ MACD: 计算失败 - {str(e)}"
                    result['issues'].append(issue)
                    print(f"    {issue}")
            else:
                issue = f"⚠️  MACD: 数据不足（{len(close_prices)} < 26）"
                result['issues'].append(issue)
                print(f"    {issue}")
            
            # 检查ICT指标
            print("\n  🔹 ICT指标检查:")
            
            # Market Structure
            try:
                ms_result = self.tech_engine.calculate('market_structure', df, lookback=10)
                ms_value = ms_result.value
                result['indicators']['MarketStructure'] = ms_value
                print(f"    ✅ Market Structure: {ms_value}")
            except Exception as e:
                issue = f"❌ Market Structure: 计算失败 - {str(e)}"
                result['issues'].append(issue)
                print(f"    {issue}")
            
            # Order Blocks
            try:
                ob_result = self.tech_engine.calculate('order_blocks', df, lookback=20)
                ob_value = ob_result.value
                result['indicators']['OrderBlocks'] = f"{len(ob_value)} blocks"
                print(f"    ✅ Order Blocks: 检测到{len(ob_value)}个订单块")
            except Exception as e:
                issue = f"❌ Order Blocks: 计算失败 - {str(e)}"
                result['issues'].append(issue)
                print(f"    {issue}")
            
            # Fair Value Gaps
            try:
                fvg_result = self.tech_engine.calculate('fvg', df)
                fvg_value = fvg_result.value
                result['indicators']['FVG'] = f"{len(fvg_value)} gaps"
                print(f"    ✅ Fair Value Gaps: 检测到{len(fvg_value)}个缺口")
            except Exception as e:
                issue = f"❌ Fair Value Gaps: 计算失败 - {str(e)}"
                result['issues'].append(issue)
                print(f"    {issue}")
            
            result['success'] = len(result['issues']) == 0
            
            if result['success']:
                print(f"\n✅ **技术指标阶段：通过**")
            else:
                print(f"\n⚠️  **技术指标阶段：发现 {len(result['issues'])} 个问题**")
            
        except Exception as e:
            error_msg = f"❌ 技术指标诊断异常: {str(e)}"
            result['issues'].append(error_msg)
            print(f"\n{error_msg}")
            print(f"详细错误:\n{traceback.format_exc()}")
        
        return result
    
    async def debug_signal_generation(self, symbol: str, data: Dict) -> Dict:
        """
        第三阶段：信号生成逻辑检查
        """
        print(f"\n{'='*60}")
        print(f"🎯 **第三阶段：信号生成诊断** - {symbol}")
        print(f"{'='*60}\n")
        
        result = {
            'symbol': symbol,
            'success': False,
            'signal': None,
            'issues': []
        }
        
        try:
            # 生成信号
            print(f"🚀 开始信号生成...")
            signal = await self.signal_generator.generate_signal(symbol, data)
            
            if signal is None:
                result['issues'].append("⚠️  信号生成返回None")
                print(f"  ⚠️  信号生成返回None")
            else:
                result['signal'] = {
                    'direction': signal.get('direction'),
                    'confidence': signal.get('confidence'),
                    'leverage': signal.get('leverage'),
                    'entry_price': signal.get('entry_price'),
                    'stop_loss': signal.get('stop_loss'),
                    'take_profit': signal.get('take_profit')
                }
                
                print(f"\n  ✅ 信号生成成功:")
                print(f"    方向: {signal.get('direction')}")
                print(f"    信心值: {signal.get('confidence')}%")
                print(f"    杠杆: {signal.get('leverage')}x")
                print(f"    入场价: {signal.get('entry_price')}")
                print(f"    止损: {signal.get('stop_loss')}")
                print(f"    止盈: {signal.get('take_profit')}")
                
                result['success'] = True
            
        except Exception as e:
            error_msg = f"❌ 信号生成异常: {str(e)}"
            result['issues'].append(error_msg)
            print(f"\n{error_msg}")
            print(f"详细错误:\n{traceback.format_exc()}")
        
        return result
    
    async def comprehensive_symbol_test(self, symbol: str) -> Dict:
        """
        第四阶段：端到端完整测试单个Symbol
        """
        print(f"\n\n{'#'*70}")
        print(f"#  🚀 **完整测试开始**: {symbol}")
        print(f"{'#'*70}\n")
        
        test_result = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'stages': {}
        }
        
        # 阶段1：数据获取
        data_result = await self.debug_data_acquisition(symbol)
        test_result['stages']['data_acquisition'] = data_result
        
        if not data_result['success']:
            print(f"\n❌ **测试终止**: 数据获取失败")
            return test_result
        
        # 阶段2：技术指标
        indicator_result = self.debug_technical_indicators(symbol, data_result['data'])
        test_result['stages']['technical_indicators'] = indicator_result
        
        # 阶段3：信号生成
        # 需要重新获取完整的DataFrame数据
        data = await self.data_fetcher.get_multi_timeframe_data(symbol)
        signal_result = await self.debug_signal_generation(symbol, data)
        test_result['stages']['signal_generation'] = signal_result
        
        # 总结
        print(f"\n\n{'='*70}")
        print(f"📋 **诊断总结** - {symbol}")
        print(f"{'='*70}\n")
        
        total_issues = (
            len(data_result.get('issues', [])) +
            len(indicator_result.get('issues', [])) +
            len(signal_result.get('issues', []))
        )
        
        if total_issues == 0:
            print(f"✅ **所有阶段通过，无问题发现**")
        else:
            print(f"⚠️  **发现 {total_issues} 个问题**:")
            print(f"  - 数据获取: {len(data_result.get('issues', []))} 个问题")
            print(f"  - 技术指标: {len(indicator_result.get('issues', []))} 个问题")
            print(f"  - 信号生成: {len(signal_result.get('issues', []))} 个问题")
        
        if signal_result.get('signal'):
            print(f"\n🎯 **最终信号**: {signal_result['signal']['direction']} "
                  f"(信心值: {signal_result['signal']['confidence']}%)")
        else:
            print(f"\n⚠️  **最终信号**: 无信号生成")
        
        return test_result
    
    async def batch_test_symbols(self, symbols: List[str]) -> Dict:
        """批量测试多个交易对"""
        print(f"\n\n{'*'*70}")
        print(f"*  🔍 **批量诊断模式**")
        print(f"*  测试交易对: {', '.join(symbols)}")
        print(f"{'*'*70}\n")
        
        results = {}
        
        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] 正在测试: {symbol}")
            results[symbol] = await self.comprehensive_symbol_test(symbol)
            
            # 短暂延迟避免API限流
            if i < len(symbols):
                await asyncio.sleep(1)
        
        # 汇总报告
        print(f"\n\n{'*'*70}")
        print(f"*  📊 **批量诊断汇总报告**")
        print(f"{'*'*70}\n")
        
        signal_count = 0
        error_count = 0
        
        for symbol, result in results.items():
            signal = result.get('stages', {}).get('signal_generation', {}).get('signal')
            if signal:
                signal_count += 1
                print(f"  ✅ {symbol}: {signal['direction']} (信心值: {signal['confidence']}%)")
            else:
                error_count += 1
                print(f"  ❌ {symbol}: 无信号生成")
        
        print(f"\n**统计**:")
        print(f"  总测试数: {len(symbols)}")
        print(f"  成功生成信号: {signal_count}")
        print(f"  未生成信号: {error_count}")
        print(f"  成功率: {signal_count/len(symbols)*100:.1f}%")
        
        return results


async def main():
    """主函数：运行诊断"""
    diagnostics = SignalGenerationDiagnostics()
    
    # 测试关键交易对
    test_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    
    # 批量测试
    results = await diagnostics.batch_test_symbols(test_symbols)
    
    print(f"\n\n✅ 诊断完成！")
    print(f"详细结果已输出到控制台。")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
