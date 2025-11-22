"""
测试 PositionSizer v4.1 Critical Fix
验证正确解析 Binance symbol filters
"""

import asyncio
import logging
from src.clients.binance_client import BinanceClient
from src.core.position_sizer import PositionSizer
from src.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_symbol_specs():
    """测试获取交易对规格"""
    
    # 初始化客户端
    binance_client = BinanceClient()
    
    # 初始化 PositionSizer
    sizer = PositionSizer(Config, binance_client)
    
    # 测试几个代表性交易对
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'DOGEUSDT']
    
    print("=" * 80)
    print("🔍 测试 PositionSizer v4.1 Critical Fix")
    print("=" * 80)
    
    for symbol in test_symbols:
        try:
            # 获取规格
            specs = await sizer.get_symbol_specs(symbol)
            
            # 同时直接从 BinanceClient 获取验证
            symbol_info = await binance_client.get_symbol_info(symbol)
            
            print(f"\n📊 {symbol}:")
            print(f"   minQty (LOT_SIZE):     {specs['min_quantity']}")
            print(f"   stepSize (LOT_SIZE):   {specs['step_size']}")
            print(f"   minNotional:           {specs['min_notional']}")
            print(f"   tickSize (PRICE):      {specs['tick_size']}")
            
            # 验证是否从默认值更新
            if specs['min_quantity'] == 0.001 and specs['step_size'] == 0.001:
                print(f"   ⚠️ 警告：可能使用默认值（未从Binance更新）")
            else:
                print(f"   ✅ 已从Binance更新")
                
        except Exception as e:
            print(f"   ❌ 错误: {e}")
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)
    
    await binance_client.close()


async def test_position_calculation():
    """测试倉位計算（使用真實規格）"""
    
    binance_client = BinanceClient()
    sizer = PositionSizer(Config, binance_client)
    
    print("\n" + "=" * 80)
    print("🧮 测试倉位計算（使用真實Binance規格）")
    print("=" * 80)
    
    # 测试参数
    test_params = {
        'account_equity': 1000.0,
        'entry_price': 50000.0,
        'stop_loss': 49500.0,
        'leverage': 2.0,
        'symbol': 'BTCUSDT'
    }
    
    try:
        size, adjusted_sl = await sizer.calculate_position_size_async(**test_params)
        
        print(f"\n📊 測試參數:")
        print(f"   帳戶權益: ${test_params['account_equity']}")
        print(f"   入場價格: ${test_params['entry_price']}")
        print(f"   止損價格: ${test_params['stop_loss']}")
        print(f"   槓桿: {test_params['leverage']}x")
        
        print(f"\n📊 計算結果:")
        print(f"   倉位大小: {size} BTC")
        print(f"   名義價值: ${size * test_params['entry_price']:.2f}")
        print(f"   調整後止損: ${adjusted_sl}")
        
        # 验证是否符合Binance规格
        specs = await sizer.get_symbol_specs('BTCUSDT')
        
        print(f"\n✅ Binance規格驗證:")
        print(f"   倉位 {size:.6f} >= 最小數量 {specs['min_quantity']} ? {size >= specs['min_quantity']}")
        print(f"   名義價值 ${size * test_params['entry_price']:.2f} >= 最小名義 ${specs['min_notional']} ? {size * test_params['entry_price'] >= specs['min_notional']}")
        
        # 检查步进大小合规
        from decimal import Decimal
        size_decimal = Decimal(str(size))
        step_decimal = Decimal(str(specs['step_size']))
        remainder = size_decimal % step_decimal
        
        print(f"   數量精度符合stepSize {specs['step_size']} ? {remainder == 0}")
        
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    
    await binance_client.close()


if __name__ == "__main__":
    print("🚀 啟動測試...")
    
    try:
        asyncio.run(test_symbol_specs())
        asyncio.run(test_position_calculation())
    except KeyboardInterrupt:
        print("\n⚠️ 測試中斷")
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
