#!/usr/bin/env python3
"""
检查ML训练数据的LONG/SHORT平衡性
"""

import pandas as pd
import json
from pathlib import Path

def check_data_balance():
    """检查训练数据的方向分布"""
    
    print("=" * 60)
    print("📊 检查ML训练数据的LONG/SHORT平衡性")
    print("=" * 60)
    
    # 检查 trades.jsonl
    trades_file = Path("ml_data/trades.jsonl")
    
    if not trades_file.exists():
        print(f"\n❌ 训练数据文件不存在: {trades_file}")
        print("   这可能是因为系统还没有收集到足够的交易数据")
        return
    
    # 读取数据
    trades = []
    with open(trades_file, 'r') as f:
        for line in f:
            try:
                trades.append(json.loads(line))
            except:
                pass
    
    if not trades:
        print(f"\n⚠️  训练数据为空")
        return
    
    # 统计
    total = len(trades)
    long_trades = [t for t in trades if t.get('direction') == 'LONG']
    short_trades = [t for t in trades if t.get('direction') == 'SHORT']
    
    long_count = len(long_trades)
    short_count = len(short_trades)
    
    # 胜率统计
    long_wins = sum(1 for t in long_trades if t.get('pnl_pct', 0) > 0)
    short_wins = sum(1 for t in short_trades if t.get('pnl_pct', 0) > 0)
    
    long_winrate = long_wins / long_count if long_count > 0 else 0
    short_winrate = short_wins / short_count if short_count > 0 else 0
    
    # 平均PnL
    long_avg_pnl = sum(t.get('pnl_pct', 0) for t in long_trades) / long_count if long_count > 0 else 0
    short_avg_pnl = sum(t.get('pnl_pct', 0) for t in short_trades) / short_count if short_count > 0 else 0
    
    # 虚拟 vs 真实
    virtual_trades = [t for t in trades if t.get('is_virtual', False)]
    real_trades = [t for t in trades if not t.get('is_virtual', False)]
    
    print(f"\n📈 总体统计:")
    print(f"  总交易数: {total}")
    print(f"  真实交易: {len(real_trades)}")
    print(f"  虚拟交易: {len(virtual_trades)}")
    
    print(f"\n📊 方向分布:")
    print(f"  LONG:  {long_count:4d} ({long_count/total*100:5.1f}%)")
    print(f"  SHORT: {short_count:4d} ({short_count/total*100:5.1f}%)")
    
    # 警告不平衡
    ratio = 1.0
    if long_count > 0 and short_count > 0:
        ratio = max(long_count, short_count) / min(long_count, short_count)
        if ratio > 2.0:
            print(f"\n⚠️  警告: 数据不平衡! LONG/SHORT比例 = {ratio:.1f}:1")
            print(f"   这会导致模型偏向数量更多的方向")
    
    print(f"\n🎯 胜率对比:")
    print(f"  LONG胜率:  {long_winrate*100:5.1f}% ({long_wins}/{long_count})")
    print(f"  SHORT胜率: {short_winrate*100:5.1f}% ({short_wins}/{short_count})")
    
    print(f"\n💰 平均PnL对比:")
    print(f"  LONG平均:  {long_avg_pnl:+.2f}%")
    print(f"  SHORT平均: {short_avg_pnl:+.2f}%")
    
    # 结论
    print(f"\n" + "=" * 60)
    print("📝 诊断结论:")
    print("=" * 60)
    
    if long_count == 0 and short_count == 0:
        print("❌ 没有训练数据，模型无法学习")
    elif short_count == 0:
        print("❌ 只有LONG交易，没有SHORT数据！")
        print("   → 模型无法学习SHORT交易模式")
    elif long_count == 0:
        print("❌ 只有SHORT交易，没有LONG数据！")
        print("   → 模型无法学习LONG交易模式")
    elif ratio > 2.0:
        dominant = "LONG" if long_count > short_count else "SHORT"
        print(f"⚠️  数据严重不平衡，{dominant}样本是另一方的{ratio:.1f}倍")
        print(f"   → 模型会偏向{dominant}交易")
        print(f"\n💡 建议:")
        print(f"   1. 等待系统累积更多数据")
        print(f"   2. 检查信号生成逻辑是否有偏向")
        print(f"   3. 考虑使用class_weight平衡训练")
    elif abs(long_winrate - short_winrate) > 0.2:
        better = "LONG" if long_winrate > short_winrate else "SHORT"
        print(f"⚠️  {better}胜率明显更高 ({max(long_winrate, short_winrate)*100:.1f}% vs {min(long_winrate, short_winrate)*100:.1f}%)")
        print(f"   → 模型会学习到{better}更安全，偏向{better}交易")
        print(f"\n💡 这可能反映了真实的市场环境")
    else:
        print("✅ 数据分布相对平衡")
        print(f"   LONG/SHORT比例: {long_count}:{short_count}")
        print(f"   胜率差异: {abs(long_winrate - short_winrate)*100:.1f}%")
    
    print("=" * 60)

if __name__ == "__main__":
    check_data_balance()
