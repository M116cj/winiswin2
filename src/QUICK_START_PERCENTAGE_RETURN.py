"""
🚀 快速開始 - 百分比收益率 + 部位規模計算系統

完整的端到端工作流示例，展示新架構如何運作
"""

from src.percentage_return_model import PercentageReturnModel
from src.position_sizing import PositionSizingFactory
from src.capital_tracker import init_capital_tracker, get_capital_tracker, get_total_equity


def demo_complete_workflow():
    """完整的交易工作流演示"""
    
    print("=" * 80)
    print("🚀 百分比收益率 + 部位規模計算 - 完整演示")
    print("=" * 80)
    
    # ===== 1️⃣ 初始化帳戶 =====
    print("\n1️⃣ 初始化虛擬帳戶")
    print("-" * 80)
    
    initial_balance = 10000
    tracker = init_capital_tracker(initial_balance=initial_balance)
    print(f"✅ 虛擬帳戶已初始化: ${initial_balance:,.2f}")
    
    # ===== 2️⃣ 交易配置 =====
    print("\n2️⃣ 交易配置")
    print("-" * 80)
    
    config = {
        'version': 'B',  # 使用 V2 (凱利 + ATR)
        'historical_winrate': 0.70,  # 70% 歷史勝率
        'use_kelly': True
    }
    print(f"部位規模版本: {config['version']}")
    print(f"歷史勝率: {config['historical_winrate']:.1%}")
    print(f"使用凱利公式: {config['use_kelly']}")
    
    # ===== 3️⃣ 第一筆交易 =====
    print("\n3️⃣ 交易 #1: BTCUSDT 看漲信號")
    print("-" * 80)
    
    signal_1 = {
        'symbol': 'BTCUSDT',
        'direction': 'UP',
        'confidence': 0.80,
        'current_price': 42000,
        'atr': 0.015
    }
    
    print(f"信號: {signal_1['symbol']} {signal_1['direction']}")
    print(f"信心度: {signal_1['confidence']:.1%}")
    print(f"當前價格: ${signal_1['current_price']:,.2f}")
    print(f"ATR: {signal_1['atr']:.2%}")
    
    # 步驟 A: 預測收益率
    print("\n  📊 步驟 A: ML 模型預測收益率")
    ml_model = PercentageReturnModel()
    prediction = ml_model.predict_signal(
        signal_data=signal_1,
        historical_stats={
            'win_rate': config['historical_winrate'],
            'atr': signal_1['atr'],
            'market_volatility': 1.0
        }
    )
    
    predicted_return_pct = prediction['predicted_return_pct']
    print(f"  → 預測收益率: {predicted_return_pct:.2%}")
    print(f"  → 信心度: {prediction['confidence']:.1%}")
    
    # 步驟 B: 計算部位規模
    print("\n  💰 步驟 B: 計算部位規模 (V2 - 凱利 + ATR)")
    total_capital = get_total_equity()
    
    sizing = PositionSizingFactory.calculate(
        version=config['version'],
        total_capital=total_capital,
        predicted_return_pct=predicted_return_pct,
        confidence=signal_1['confidence'],
        win_rate=config['historical_winrate'],
        atr_pct=signal_1['atr'],
        current_price=signal_1['current_price'],
        symbol=signal_1['symbol'],
        use_kelly=config['use_kelly']
    )
    
    print(f"  → 下單金額: ${sizing['order_amount']:,.2f}")
    print(f"  → 下單數量: {sizing['quantity']:.6f} BTC")
    print(f"  → 風險金額: ${sizing['risk_amount']:,.2f}")
    print(f"  → Kelly %: {sizing['kelly_pct']:.2%}")
    print(f"  → ATR Weight: {sizing['atr_weight']:.2f}x")
    print(f"  → 信心度因子: {sizing['confidence_factor']:.2f}x")
    print(f"  → 停損: {sizing['sl_pct']:.2%}")
    print(f"  → 止盈: {sizing['tp_pct']:.2%}")
    
    # 步驟 C: 執行下單
    print("\n  🎯 步驟 C: 執行下單 (虛擬)")
    cap_tracker = get_capital_tracker()
    
    entry_price = signal_1['current_price']
    quantity = sizing['quantity']
    
    cap_tracker.open_position(
        symbol=signal_1['symbol'],
        side='BUY',
        quantity=quantity,
        entry_price=entry_price,
        order_amount=sizing['order_amount']
    )
    
    print(f"  ✅ 開倉成功")
    print(f"     進場價: ${entry_price:,.2f}")
    print(f"     進場量: {quantity:.6f} BTC")
    
    # 步驟 D: 模擬行情波動
    print("\n  📈 步驟 D: 模擬行情波動 (+5%)")
    new_price = entry_price * (1 + predicted_return_pct)
    print(f"  → 新價格: ${new_price:,.2f}")
    
    cap_tracker.update_position_price(signal_1['symbol'], new_price)
    unrealized = cap_tracker.get_unrealized_pnl()
    
    print(f"  → 未實現 PnL: ${unrealized:,.2f}")
    print(f"  → 未實現回報: {unrealized / sizing['order_amount']:.2%}")
    
    # 步驟 E: 平倉
    print("\n  🏁 步驟 E: 平倉成功")
    cap_tracker.close_position(
        symbol=signal_1['symbol'],
        exit_price=new_price,
        realized_pnl=unrealized
    )
    
    print(f"  ✅ 出場成功")
    print(f"     出場價: ${new_price:,.2f}")
    print(f"     實現 PnL: ${unrealized:,.2f}")
    
    # 帳戶狀態
    status = cap_tracker.get_account_status()
    print(f"\n  📊 帳戶狀態 (交易 #1 後)")
    print(f"     總權益: ${status['total_equity']:,.2f}")
    print(f"     回報率: {status['total_return_pct']:.2f}%")
    
    # ===== 4️⃣ 第二筆交易（高波動） =====
    print("\n4️⃣ 交易 #2: ETHUSDT 看漲信號 (高波動環境)")
    print("-" * 80)
    
    signal_2 = {
        'symbol': 'ETHUSDT',
        'direction': 'UP',
        'confidence': 0.75,
        'current_price': 2200,
        'atr': 0.035  # 高波動 (3.5%)
    }
    
    print(f"信號: {signal_2['symbol']} {signal_2['direction']}")
    print(f"信心度: {signal_2['confidence']:.1%}")
    print(f"當前價格: ${signal_2['current_price']:,.2f}")
    print(f"ATR: {signal_2['atr']:.2%} (高波動！)")
    
    # 預測和計算
    prediction_2 = ml_model.predict_signal(
        signal_data=signal_2,
        historical_stats={'win_rate': 0.68, 'atr': signal_2['atr']}
    )
    
    sizing_2 = PositionSizingFactory.calculate(
        version=config['version'],
        total_capital=get_total_equity(),
        predicted_return_pct=prediction_2['predicted_return_pct'],
        confidence=signal_2['confidence'],
        win_rate=0.68,
        atr_pct=signal_2['atr'],
        current_price=signal_2['current_price'],
        symbol=signal_2['symbol']
    )
    
    print(f"\n  預測收益率: {prediction_2['predicted_return_pct']:.2%}")
    print(f"  下單金額: ${sizing_2['order_amount']:,.2f}")
    print(f"  ATR Weight: {sizing_2['atr_weight']:.2f}x (縮小部位，因為波動高)")
    print(f"  停損: {sizing_2['sl_pct']:.2%}")
    print(f"  止盈: {sizing_2['tp_pct']:.2%}")
    
    # 開倉
    cap_tracker.open_position(
        symbol=signal_2['symbol'],
        side='BUY',
        quantity=sizing_2['quantity'],
        entry_price=signal_2['current_price'],
        order_amount=sizing_2['order_amount']
    )
    
    print(f"\n  ✅ 開倉成功: {sizing_2['quantity']:.6f} ETH @ ${signal_2['current_price']:,.2f}")
    
    # 行情反向 (-2%)
    print(f"\n  📉 行情反向 (-2%)")
    loss_price = signal_2['current_price'] * 0.98
    cap_tracker.update_position_price(signal_2['symbol'], loss_price)
    unrealized_2 = cap_tracker.get_unrealized_pnl()
    
    print(f"  → 新價格: ${loss_price:,.2f}")
    print(f"  → 未實現 PnL: ${unrealized_2:,.2f}")
    
    # 觸發停損平倉
    cap_tracker.close_position(
        symbol=signal_2['symbol'],
        exit_price=loss_price,
        realized_pnl=unrealized_2
    )
    
    print(f"  🏁 觸發停損平倉")
    print(f"     實現 PnL: ${unrealized_2:,.2f}")
    
    # ===== 5️⃣ 最終帳戶狀態 =====
    print("\n5️⃣ 最終帳戶狀態")
    print("-" * 80)
    
    final_status = cap_tracker.get_account_status()
    
    print(f"初始資金: ${initial_balance:,.2f}")
    print(f"總權益: ${final_status['total_equity']:,.2f}")
    print(f"已實現 PnL: ${final_status['realized_pnl']:,.2f}")
    print(f"完成交易數: {final_status['trade_count']}")
    print(f"勝率: {final_status['win_rate']:.1%} ({int(final_status['trade_count'] * final_status['win_rate'])}/{final_status['trade_count']})")
    print(f"總回報率: {final_status['total_return_pct']:.2f}%")
    
    # ===== 6️⃣ 架構對比 =====
    print("\n6️⃣ V1 vs V2 比較 (同一筆交易)")
    print("-" * 80)
    
    # V1 計算
    sizing_v1 = PositionSizingFactory.calculate(
        version='A',
        total_capital=10000,
        predicted_return_pct=0.05,
        stop_loss_pct=0.02,
        current_price=42000,
        symbol='BTCUSDT'
    )
    
    # V2 計算
    sizing_v2 = PositionSizingFactory.calculate(
        version='B',
        total_capital=10000,
        predicted_return_pct=0.05,
        confidence=0.80,
        win_rate=0.70,
        atr_pct=0.015,
        current_price=42000,
        symbol='BTCUSDT'
    )
    
    print(f"\n版本 A (固定風險 2%):")
    print(f"  下單金額: ${sizing_v1['order_amount']:,.2f}")
    print(f"  理由: 固定風險策略")
    
    print(f"\n版本 B (凱利 + ATR + 信心度):")
    print(f"  下單金額: ${sizing_v2['order_amount']:,.2f}")
    print(f"  Kelly: {sizing_v2['kelly_pct']:.2%}")
    print(f"  ATR Weight: {sizing_v2['atr_weight']:.2f}x (低波動 → 擴大)")
    print(f"  Confidence: {sizing_v2['confidence_factor']:.2f}x (高信心 → 擴大)")
    print(f"  理由: 動態調整，低波動 × 高信心 → 更大部位")
    
    print(f"\n💡 V2 比 V1 多投 ${sizing_v2['order_amount'] - sizing_v1['order_amount']:,.2f}")
    print(f"   (在低波動 + 高信心的市場環境中抓住機會)")
    
    print("\n" + "=" * 80)
    print("✅ 演示完成！")
    print("=" * 80)


if __name__ == '__main__':
    demo_complete_workflow()
