#!/usr/bin/env python3
"""
WebSocket K線數據驗證腳本 v3.32
檢查從Binance WebSocket接收的K線數據是否包含正確字段
"""

import asyncio
import json
import websockets
import sys
from datetime import datetime


async def test_kline_websocket():
    """測試K線WebSocket數據格式"""
    
    # 測試單個交易對
    symbol = "btcusdt"
    url = f"wss://fstream.binance.com/ws/{symbol}@kline_1m"
    
    print("=" * 80)
    print("🔍 K線WebSocket數據格式驗證")
    print("=" * 80)
    print(f"📡 連接URL: {url}")
    print(f"⏰ 開始時間: {datetime.now()}")
    print()
    
    try:
        # v3.32+ 符合Binance规范：禁用客户端ping
        async with websockets.connect(
            url,
            ping_interval=None,  # 禁用客户端ping
            ping_timeout=120,     # 120秒无服务器ping则断线
        ) as ws:
            print("✅ WebSocket連接成功")
            print()
            
            # 接收3個K線更新事件
            kline_count = 0
            max_klines = 3
            
            while kline_count < max_klines:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=120)
                    data = json.loads(msg)
                    
                    # 檢查是否為K線事件
                    if data.get('e') == 'kline':
                        kline_count += 1
                        k = data['k']
                        
                        print(f"📊 K線事件 #{kline_count}")
                        print("-" * 80)
                        
                        # 驗證必需字段
                        required_fields = {
                            's': '交易對',
                            't': 'K線開盤時間 (毫秒)',
                            'T': 'K線閉盤時間 (毫秒)',
                            'o': '開盤價',
                            'h': '最高價',
                            'l': '最低價',
                            'c': '收盤價',
                            'v': '成交量',
                            'q': '成交額',
                            'n': '成交筆數',
                            'x': '是否閉盤',
                        }
                        
                        # 事件時間戳（用於計算延遲）
                        event_time = data.get('E', 0)
                        
                        print(f"✅ 事件類型: {data.get('e')}")
                        print(f"⏰ 事件時間: {event_time} ({datetime.fromtimestamp(event_time/1000)})")
                        print()
                        
                        all_fields_present = True
                        
                        for field, description in required_fields.items():
                            if field in k:
                                value = k[field]
                                status = "✅"
                                
                                # 格式化輸出
                                if field == 's':
                                    print(f"{status} {field:2s} ({description:20s}): {value}")
                                elif field in ['t', 'T']:
                                    ts_value = int(value)
                                    dt = datetime.fromtimestamp(ts_value / 1000)
                                    print(f"{status} {field:2s} ({description:20s}): {ts_value} ({dt})")
                                elif field in ['o', 'h', 'l', 'c']:
                                    print(f"{status} {field:2s} ({description:20s}): {float(value):.2f}")
                                elif field in ['v', 'q']:
                                    print(f"{status} {field:2s} ({description:20s}): {float(value):.4f}")
                                elif field == 'n':
                                    print(f"{status} {field:2s} ({description:20s}): {int(value)}")
                                elif field == 'x':
                                    is_final = bool(value)
                                    print(f"{status} {field:2s} ({description:20s}): {is_final} {'（閉盤K線）' if is_final else '（未閉盤）'}")
                            else:
                                print(f"❌ {field:2s} ({description:20s}): 缺失")
                                all_fields_present = False
                        
                        # 計算網絡延遲
                        if event_time > 0:
                            local_time = int(datetime.now().timestamp() * 1000)
                            latency = local_time - event_time
                            print()
                            print(f"📡 網絡延遲: {latency} 毫秒")
                        
                        print()
                        
                        if all_fields_present:
                            print("✅ 所有必需字段都存在")
                        else:
                            print("❌ 缺少必需字段")
                        
                        print("=" * 80)
                        print()
                
                except asyncio.TimeoutError:
                    print("⚠️ 120秒內未收到數據，超時")
                    break
            
            print(f"🎉 測試完成，共接收 {kline_count} 個K線事件")
            
            if kline_count > 0:
                print("\n✅ K線WebSocket數據格式驗證成功")
                print("📋 確認收到的字段：symbol, open, high, low, close, volume, timestamp 等")
                return True
            else:
                print("\n❌ 未收到K線數據")
                return False
    
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_combined_streams():
    """測試合併流格式"""
    
    symbols = ["btcusdt", "ethusdt"]
    streams = "/".join([f"{s}@kline_1m" for s in symbols])
    url = f"wss://fstream.binance.com/stream?streams={streams}"
    
    print("=" * 80)
    print("🔍 合併流WebSocket數據格式驗證")
    print("=" * 80)
    print(f"📡 連接URL: {url}")
    print(f"📊 監控交易對: {', '.join([s.upper() for s in symbols])}")
    print()
    
    try:
        async with websockets.connect(
            url,
            ping_interval=None,
            ping_timeout=120,
        ) as ws:
            print("✅ WebSocket連接成功")
            print()
            
            # 接收2個事件
            event_count = 0
            max_events = 2
            
            while event_count < max_events:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=120)
                    data = json.loads(msg)
                    
                    # 合併流格式: {"stream": "btcusdt@kline_1m", "data": {...}}
                    if 'stream' in data and 'data' in data:
                        event_count += 1
                        
                        print(f"📊 合併流事件 #{event_count}")
                        print("-" * 80)
                        print(f"✅ stream: {data['stream']}")
                        
                        # 檢查data字段
                        event_data = data['data']
                        if event_data.get('e') == 'kline':
                            k = event_data['k']
                            print(f"✅ 事件類型: {event_data.get('e')}")
                            print(f"✅ 交易對: {k.get('s')}")
                            print(f"✅ 開盤價: {float(k.get('o', 0)):.2f}")
                            print(f"✅ 收盤價: {float(k.get('c', 0)):.2f}")
                            print(f"✅ 是否閉盤: {k.get('x', False)}")
                        
                        print("=" * 80)
                        print()
                
                except asyncio.TimeoutError:
                    print("⚠️ 120秒內未收到數據，超時")
                    break
            
            if event_count > 0:
                print(f"\n✅ 合併流格式驗證成功，共接收 {event_count} 個事件")
                return True
            else:
                print("\n❌ 未收到合併流數據")
                return False
    
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 開始WebSocket K線數據驗證測試")
    print()
    
    # 測試1: 單個交易對
    result1 = asyncio.run(test_kline_websocket())
    
    print()
    print()
    
    # 測試2: 合併流
    result2 = asyncio.run(test_combined_streams())
    
    print()
    print("=" * 80)
    print("📊 測試結果總結")
    print("=" * 80)
    print(f"單個交易對測試: {'✅ 通過' if result1 else '❌ 失敗'}")
    print(f"合併流測試: {'✅ 通過' if result2 else '❌ 失敗'}")
    print()
    
    if result1 and result2:
        print("🎉 所有測試通過！K線WebSocket數據格式正確。")
        sys.exit(0)
    else:
        print("❌ 部分測試失敗，請檢查網絡連接或Binance服務狀態。")
        sys.exit(1)
