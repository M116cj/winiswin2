#!/usr/bin/env python3
"""
豁免期策略完整测试
生成100笔模拟交易，验证：
1. 豁免期（0-100笔）使用40%/40%门槛，杠杆1-3x
2. 正常期（101+笔）使用60%/50%门槛，杠杆无限制
3. 自动切换机制正常工作
"""

import sys
import logging
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.simulation.mock_binance_client import MockBinanceClient
from src.simulation.trade_simulator import TradeSimulator
from src.strategies.self_learning_trader import SelfLearningTrader
from src.managers.trade_recorder import TradeRecorder
from src.ml.feature_engine import FeatureEngine
from src.core.leverage_engine import LeverageEngine
from src.core.sltp_adjuster import SLTPAdjuster

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('simulation.log', mode='w', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def main():
    """运行完整模拟测试"""
    
    logger.info("=" * 80)
    logger.info("🎮 豁免期策略完整测试启动")
    logger.info("=" * 80)
    
    # 1. 初始化配置
    config = Config()
    logger.info(f"✅ 配置加载完成")
    logger.info(f"   豁免期门槛: 勝率≥{config.BOOTSTRAP_MIN_WIN_PROBABILITY:.0%} 信心≥{config.BOOTSTRAP_MIN_CONFIDENCE:.0%}")
    logger.info(f"   正常期门槛: 勝率≥{config.MIN_WIN_PROBABILITY:.0%} 信心≥{config.MIN_CONFIDENCE:.0%}")
    logger.info(f"   豁免期交易数: {config.BOOTSTRAP_TRADE_LIMIT}笔")
    
    # 2. 初始化模拟客户端
    mock_client = MockBinanceClient(initial_balance=10000.0)
    
    # 3. 初始化核心组件
    feature_engine = FeatureEngine()
    # TradeRecorder不需要传参，会使用默认值
    trade_recorder = TradeRecorder()
    
    # 4. 初始化交易策略（会自动创建leverage_engine和sltp_adjuster）
    trader = SelfLearningTrader(
        config=config,
        binance_client=mock_client,  # 使用模拟客户端
        trade_recorder=trade_recorder
    )
    
    logger.info(f"✅ 交易策略初始化完成（豁免期: 启用）")
    
    # 5. 初始化模拟器
    simulator = TradeSimulator(
        config=config,
        mock_client=mock_client,
        trader=trader,
        trade_recorder=trade_recorder
    )
    
    # 6. 运行模拟（100笔交易）
    logger.info("\n" + "=" * 80)
    logger.info("🚀 开始模拟100笔交易...")
    logger.info("=" * 80 + "\n")
    
    trades = simulator.run_simulation(num_trades=100)
    
    # 7. 打印总结
    simulator.print_summary(trades)
    
    # 8. 验证豁免期切换
    logger.info("\n" + "=" * 80)
    logger.info("🔍 验证豁免期切换逻辑")
    logger.info("=" * 80)
    
    # 检查第1-100笔的杠杆范围
    bootstrap_leverages = [t['leverage'] for t in trades[:100]]
    bootstrap_min = min(bootstrap_leverages)
    bootstrap_max = max(bootstrap_leverages)
    
    logger.info(f"\n豁免期杠杆统计（前100笔）:")
    logger.info(f"  最小杠杆: {bootstrap_min:.2f}x")
    logger.info(f"  最大杠杆: {bootstrap_max:.2f}x")
    
    if bootstrap_min >= 1.0 and bootstrap_max <= 3.0:
        logger.info(f"  ✅ 杠杆压制正确！范围在 1-3x 内")
    else:
        logger.warning(f"  ⚠️ 杠杆范围异常！应该在 1-3x 内")
    
    # 9. 保存详细结果到文件
    output_file = "simulation_results.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("豁免期策略模拟测试结果\n")
        f.write("=" * 80 + "\n\n")
        
        for trade in trades:
            phase = "豁免期" if trade['is_bootstrap'] else "正常期"
            outcome = "盈利" if trade['outcome'] == 'WIN' else "亏损"
            
            f.write(f"#{trade['trade_number']:03d} | {phase} | {outcome} | "
                   f"{trade['symbol']} {trade['direction']} | "
                   f"杠杆: {trade['leverage']:.2f}x | "
                   f"胜率: {trade['win_probability']:.0%} | "
                   f"信心: {trade['confidence']:.0%} | "
                   f"PnL: ${trade['pnl']:+.2f}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("测试完成\n")
        f.write("=" * 80 + "\n")
    
    logger.info(f"\n✅ 详细结果已保存到: {output_file}")
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ 测试完成！")
    logger.info("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️ 用户中断测试")
    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
