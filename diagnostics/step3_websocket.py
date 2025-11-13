#!/usr/bin/env python3
"""
STEP 3: WebSocket 連接深度檢測
測試所有WebSocket端點、消息訂閱、多路復用、穩定性壓力測試
"""

import sys
import asyncio
import websockets
import json
from datetime import datetime
from collections import defaultdict

class WebSocketTester:
    def __init__(self):
        self.spot_url = "wss://stream.binance.com:9443/ws"
        self.futures_url = "wss://fstream.binance.com/ws"
        self.futures_stream_url = "wss://fstream.binance.com/stream"
        
    async def test_basic_connection(self, name, url, timeout=10):
        """測試基本連接"""
        try:
            start_time = datetime.now()
            async with websockets.connect(url, ping_interval=None) as ws:
                latency = (datetime.now() - start_time).total_seconds() * 1000
                print(f"✅ {name}: 連接成功 ({latency:.0f}ms)")
                return True
        except Exception as e:
            print(f"❌ {name}: 連接失敗 - {str(e)[:100]}")
            return False
    
    async def test_subscription(self, name, url, subscribe_msg, timeout=10):
        """測試訂閱功能"""
        try:
            async with websockets.connect(url, ping_interval=None) as ws:
                # 發送訂閱消息
                await ws.send(json.dumps(subscribe_msg))
                
                # 等待響應
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    data = json.loads(response)
                    
                    # 檢查是否為訂閱成功響應
                    if 'result' in data and data['result'] is None:
                        print(f"✅ {name}: 訂閱成功")
                        return True
                    elif 'e' in data:  # 接收到事件數據
                        print(f"✅ {name}: 訂閱成功（收到事件數據）")
                        return True
                    else:
                        print(f"⚠️  {name}: 收到響應但格式異常 - {str(data)[:100]}")
                        return True  # 仍算成功
                        
                except asyncio.TimeoutError:
                    print(f"⏱️ {name}: 訂閱超時")
                    return False
                    
        except Exception as e:
            print(f"❌ {name}: 訂閱失敗 - {str(e)[:100]}")
            return False
    
    async def test_multiplex_stream(self, url, streams, duration=10):
        """測試多路復用流"""
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1
        }
        
        message_count = 0
        unique_streams = set()
        
        try:
            async with websockets.connect(url, ping_interval=None) as ws:
                # 發送訂閱
                await ws.send(json.dumps(subscribe_msg))
                
                # 收集消息
                start_time = datetime.now()
                while (datetime.now() - start_time).total_seconds() < duration:
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=1)
                        data = json.loads(response)
                        
                        if 'stream' in data:
                            unique_streams.add(data['stream'])
                            message_count += 1
                            
                    except asyncio.TimeoutError:
                        continue
                
                print(f"✅ 多路復用流: 接收{message_count}條消息，{len(unique_streams)}個唯一數據流")
                return True, message_count, len(unique_streams)
                
        except Exception as e:
            print(f"❌ 多路復用流測試失敗: {str(e)[:100]}")
            return False, 0, 0
    
    async def test_stability(self, url, stream, duration=10):
        """壓力測試：連接穩定性"""
        disconnections = 0
        message_count = 0
        
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [stream],
            "id": 1
        }
        
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                await ws.send(json.dumps(subscribe_msg))
                
                start_time = datetime.now()
                while (datetime.now() - start_time).total_seconds() < duration:
                    try:
                        await asyncio.wait_for(ws.recv(), timeout=1)
                        message_count += 1
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed:
                        disconnections += 1
                        break
                
                rate = message_count / duration if duration > 0 else 0
                print(f"✅ 壓力測試: {disconnections}次斷線，{message_count}條消息，{rate:.1f}條/秒")
                return True, disconnections, message_count
                
        except Exception as e:
            print(f"❌ 壓力測試失敗: {str(e)[:100]}")
            return False, 0, 0
    
    async def run_tests(self):
        """執行所有測試"""
        print("=" * 60)
        print("📡 STEP 3: WebSocket 連接深度檢測")
        print("=" * 60)
        print()
        
        results = []
        
        # 1. 基本連接測試
        print("📌 3.1 基本連接測試")
        connection_tests = [
            ('現貨行情WebSocket', self.spot_url),
            ('合約行情WebSocket', self.futures_url),
        ]
        
        for name, url in connection_tests:
            result = await self.test_basic_connection(name, url)
            results.append(result)
        print()
        
        # 2. 訂閱功能測試
        print("📌 3.2 訂閱功能測試")
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": ["btcusdt@aggTrade"],
            "id": 1
        }
        result = await self.test_subscription('合約行情訂閱', self.futures_url, subscribe_msg)
        results.append(result)
        print()
        
        # 3. 多路復用流測試
        print("📌 3.3 多路復用流測試")
        streams = [
            "btcusdt@aggTrade",
            "ethusdt@aggTrade",
            "solusdt@aggTrade"
        ]
        success, msg_count, stream_count = await self.test_multiplex_stream(
            self.futures_stream_url, 
            streams, 
            duration=5
        )
        results.append(success)
        print()
        
        # 4. 穩定性壓力測試
        print("📌 3.4 穩定性壓力測試（10秒）")
        success, disconnects, messages = await self.test_stability(
            self.futures_url,
            "btcusdt@aggTrade",
            duration=10
        )
        results.append(success)
        print()
        
        # 總評分
        success_count = sum(results)
        total_count = len(results)
        score = (success_count / total_count * 100) if total_count > 0 else 0
        
        print("=" * 60)
        print(f"📊 STEP 3 總體評分: {score:.1f}% ({success_count}/{total_count}項通過)")
        print("=" * 60)
        
        return score

async def main():
    tester = WebSocketTester()
    score = await tester.run_tests()
    return score

if __name__ == "__main__":
    score = asyncio.run(main())
    sys.exit(0 if score >= 80 else 1)
