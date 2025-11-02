"""
0信号问题诊断脚本 v3.18.10+
基于附件中的诊断方案
"""
import asyncio
import logging
from datetime import datetime
from src.config import Config
from src.clients.binance_client import BinanceClient
from src.services.data_service import DataService
from src.strategies.rule_based_signal_generator import RuleBasedSignalGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_diagnostic():
    """运行完整诊断"""
    print("=" * 80)
    print("🔍 0信号问题诊断脚本 v3.18.10+")
    print("=" * 80)
    
    # 第一步：检查配置
    print("\n【第1步】检查核心配置")
    print("-" * 80)
    print(f"当前信心度门槛: {Config.MIN_CONFIDENCE}")
    print(f"当前胜率门槛: {Config.MIN_WIN_PROBABILITY}")
    print(f"质量门槛: {Config.SIGNAL_QUALITY_THRESHOLD}")
    print(f"ADX硬拒绝门槛: {Config.ADX_HARD_REJECT_THRESHOLD}")
    print(f"ADX弱趋势门槛: {Config.ADX_WEAK_TREND_THRESHOLD}")
    print(f"宽松信号模式: {Config.RELAXED_SIGNAL_MODE}")
    
    # 豁免期配置
    print(f"\n豁免期配置:")
    print(f"  豁免期限制: {Config.BOOTSTRAP_TRADE_LIMIT}笔")
    print(f"  豁免期信心门槛: {Config.BOOTSTRAP_MIN_CONFIDENCE}")
    print(f"  豁免期胜率门槛: {Config.BOOTSTRAP_MIN_WIN_PROBABILITY}")
    print(f"  豁免期质量门槛: {Config.BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD}")
    
    # 第二步：初始化组件
    print("\n【第2步】初始化核心组件")
    print("-" * 80)
    
    try:
        binance_client = BinanceClient()
        print("✅ BinanceClient初始化成功")
    except Exception as e:
        print(f"❌ BinanceClient初始化失败: {e}")
        binance_client = None
    
    try:
        data_service = DataService(binance_client=binance_client, websocket_monitor=None)
        await data_service.initialize()
        print("✅ DataService初始化成功")
    except Exception as e:
        print(f"❌ DataService初始化失败: {e}")
        return
    
    signal_generator = RuleBasedSignalGenerator(Config)
    print("✅ RuleBasedSignalGenerator初始化成功")
    
    # 第三步：测试主要交易对
    print("\n【第3步】测试5个主要交易对")
    print("-" * 80)
    
    test_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]
    
    results = {
        'total_tested': 0,
        'data_fetch_failed': 0,
        'signals_generated': 0,
        'signals_rejected': 0,
        'rejection_reasons': {}
    }
    
    for symbol in test_symbols:
        results['total_tested'] += 1
        print(f"\n🔍 测试 {symbol}")
        print("-" * 40)
        
        try:
            # 获取数据
            data_1h = await data_service.get_klines(symbol, "1h", limit=100)
            data_15m = await data_service.get_klines(symbol, "15m", limit=100)
            data_5m = await data_service.get_klines(symbol, "5m", limit=100)
            
            print(f"  数据获取: 1h={len(data_1h)}根, 15m={len(data_15m)}根, 5m={len(data_5m)}根")
            
            if len(data_1h) < 50 or len(data_15m) < 50 or len(data_5m) < 50:
                print(f"  ❌ 数据不足（需要≥50根）")
                results['data_fetch_failed'] += 1
                continue
            
            # 生成信号
            signal = signal_generator.generate_signal(symbol, data_1h, data_15m, data_5m)
            
            if signal:
                print(f"  ✅ 产生信号!")
                print(f"     方向: {signal.get('direction')}")
                print(f"     信心度: {signal.get('confidence', 0):.3f}")
                print(f"     胜率: {signal.get('win_probability', 0):.3f}")
                print(f"     优先级: {signal.get('priority_level', 'N/A')}")
                results['signals_generated'] += 1
            else:
                print(f"  ❌ 无信号产生")
                results['signals_rejected'] += 1
                
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            results['data_fetch_failed'] += 1
            import traceback
            traceback.print_exc()
    
    # 第四步：查看Pipeline统计
    print("\n【第4步】Pipeline诊断统计")
    print("-" * 80)
    
    pipeline_stats = signal_generator.get_pipeline_stats()
    
    print(f"Stage0 - 总扫描: {pipeline_stats['stage0_total_symbols']}")
    print(f"Stage1 - 数据验证: 有效={pipeline_stats['stage1_valid_data']}, 拒绝={pipeline_stats['stage1_rejected_data']}")
    print(f"Stage2 - 趋势判断: {pipeline_stats['stage2_trend_ok']}")
    print(f"Stage3 - 信号方向: {pipeline_stats['stage3_signal_direction']}")
    print(f"  无方向: {pipeline_stats['stage3_no_direction']}")
    print(f"  优先级1: {pipeline_stats['stage3_priority1']}")
    print(f"  优先级2: {pipeline_stats['stage3_priority2']}")
    print(f"  优先级3: {pipeline_stats['stage3_priority3']}")
    if Config.RELAXED_SIGNAL_MODE:
        print(f"  优先级4(宽松): {pipeline_stats['stage3_priority4_relaxed']}")
        print(f"  优先级5(宽松): {pipeline_stats['stage3_priority5_relaxed']}")
    
    print(f"\nStage4 - ADX过滤:")
    print(f"  ADX<10(硬拒绝): {pipeline_stats['stage4_adx_rejected_lt10']}")
    print(f"  ADX 10-15(×0.6): {pipeline_stats['stage4_adx_penalty_10_15']}")
    print(f"  ADX 15-20(×0.8): {pipeline_stats['stage4_adx_penalty_15_20']}")
    print(f"  ADX≥20(通过): {pipeline_stats['stage4_adx_ok_gte20']}")
    
    print(f"\nADX分布:")
    print(f"  <10: {pipeline_stats['adx_distribution_lt10']}")
    print(f"  10-15: {pipeline_stats['adx_distribution_10_15']}")
    print(f"  15-20: {pipeline_stats['adx_distribution_15_20']}")
    print(f"  20-25: {pipeline_stats['adx_distribution_20_25']}")
    print(f"  ≥25: {pipeline_stats['adx_distribution_gte25']}")
    
    total_adx = (pipeline_stats['adx_distribution_lt10'] + 
                 pipeline_stats['adx_distribution_10_15'] + 
                 pipeline_stats['adx_distribution_15_20'] + 
                 pipeline_stats['adx_distribution_20_25'] + 
                 pipeline_stats['adx_distribution_gte25'])
    
    if total_adx > 0:
        lt10_pct = pipeline_stats['adx_distribution_lt10'] / total_adx * 100
        lt15_pct = (pipeline_stats['adx_distribution_lt10'] + pipeline_stats['adx_distribution_10_15']) / total_adx * 100
        print(f"\n  ADX<10占比: {lt10_pct:.1f}%")
        print(f"  ADX<15占比: {lt15_pct:.1f}%")
    
    print(f"\nStage5 - 信心度计算: {pipeline_stats['stage5_confidence_calculated']}")
    print(f"Stage6 - 胜率计算: {pipeline_stats['stage6_win_prob_calculated']}")
    
    # 第五步：总结
    print("\n【第5步】诊断总结")
    print("=" * 80)
    print(f"测试交易对数: {results['total_tested']}")
    print(f"数据获取失败: {results['data_fetch_failed']}")
    print(f"产生信号数: {results['signals_generated']}")
    print(f"拒绝信号数: {results['signals_rejected']}")
    
    if results['signals_generated'] == 0:
        print("\n🚨 问题确认: 0信号产生")
        print("\n可能原因分析:")
        
        # 分析Stage1
        if pipeline_stats['stage1_rejected_data'] > 0:
            reject_rate = pipeline_stats['stage1_rejected_data'] / max(pipeline_stats['stage0_total_symbols'], 1) * 100
            print(f"  1. 数据验证拒绝率: {reject_rate:.1f}% (Stage1)")
            if reject_rate > 50:
                print(f"     ⚠️ 数据源问题！大量交易对数据不足")
        
        # 分析Stage3
        if pipeline_stats['stage3_no_direction'] > 0:
            no_dir_rate = pipeline_stats['stage3_no_direction'] / max(pipeline_stats['stage2_trend_ok'], 1) * 100
            print(f"  2. 无法确定方向: {no_dir_rate:.1f}% (Stage3)")
            
            if Config.RELAXED_SIGNAL_MODE:
                total_relaxed = pipeline_stats['stage3_priority4_relaxed'] + pipeline_stats['stage3_priority5_relaxed']
                if total_relaxed == 0:
                    print(f"     ⚠️ 宽松模式未生效！优先级4-5都为0")
        
        # 分析Stage4
        if pipeline_stats['stage4_adx_rejected_lt10'] > 0:
            adx_reject_rate = pipeline_stats['stage4_adx_rejected_lt10'] / max(pipeline_stats['stage3_signal_direction'], 1) * 100
            print(f"  3. ADX<10硬拒绝率: {adx_reject_rate:.1f}% (Stage4)")
            
            if total_adx > 0 and lt10_pct > 60:
                print(f"     🔥 ADX<10占比{lt10_pct:.1f}%！主要过滤原因")
        
        print("\n建议解决方案:")
        if lt10_pct > 60:
            print("  ✅ 降低ADX_HARD_REJECT_THRESHOLD至8.0或更低")
        if not Config.RELAXED_SIGNAL_MODE:
            print("  ✅ 启用RELAXED_SIGNAL_MODE=true")
        if Config.MIN_CONFIDENCE > 0.5:
            print(f"  ✅ 降低MIN_CONFIDENCE至0.40-0.50（当前{Config.MIN_CONFIDENCE}）")
    
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
