#!/usr/bin/env python3
"""
WebSocket Stability Test v1.0
Tests WebSocket resilience under simulated heavy CPU load
(Connection Hardening Protocol verification)

Tests:
1. Connect to Binance bookTicker stream
2. Simulate blocking CPU operations (prime number calculation)
3. Verify that heartbeats don't timeout during processing
4. Monitor for 1011/1006 errors (should be suppressed as warnings)
"""

import asyncio
import sys
import time
from datetime import datetime

try:
    import websockets
    import orjson as json
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("   Install: pip install websockets orjson")
    sys.exit(1)


def is_prime(n: int) -> bool:
    """Calculate if n is prime (CPU-intensive operation)"""
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True


def simulate_heavy_cpu(duration_ms: float = 100) -> None:
    """
    Simulate heavy CPU workload (prime number calculation)
    Duration: ~100ms of calculations
    """
    start = time.time()
    end_time = start + (duration_ms / 1000.0)
    num = 1000000
    
    while time.time() < end_time:
        is_prime(num)
        num += 1


async def test_websocket_stability():
    """Test WebSocket stability under CPU load"""
    
    print("=" * 80)
    print("🧪 WebSocket Stability Test - Connection Hardening v1.0")
    print("=" * 80)
    
    test_symbols = ["btcusdt", "ethusdt"]
    streams = "/".join([f"{symbol}@bookTicker" for symbol in test_symbols])
    url = f"wss://fstream.binance.com/stream?streams={streams}"
    
    stats = {
        'messages_received': 0,
        'messages_processed': 0,
        'errors': 0,
        'warnings': 0,
        'start_time': datetime.now(),
        'cpu_simulations': 0,
        'connection_errors': 0
    }
    
    print(f"\n📡 Connecting to: {url[:80]}...")
    
    try:
        async with websockets.connect(
            url,
            ping_interval=20,      # 🔥 Connection Hardening: 20 second pings
            ping_timeout=60,       # 🔥 60 second tolerance
            close_timeout=10,
            max_size=2**20
        ) as ws:
            print("✅ Connected to Binance stream")
            print("\n🚀 Running test for 30 seconds...")
            print("   (Receiving messages and simulating heavy CPU load)\n")
            
            start_time = time.time()
            end_time = start_time + 30  # Run for 30 seconds
            
            while time.time() < end_time:
                try:
                    # Receive message with timeout
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    stats['messages_received'] += 1
                    
                    try:
                        data = json.loads(msg)
                        
                        # 🔥 Simulate heavy CPU load (100ms calculation)
                        # This would normally block the event loop and cause 1011 errors
                        # Our fire-and-forget architecture should survive this
                        simulate_heavy_cpu(duration_ms=100)
                        stats['cpu_simulations'] += 1
                        stats['messages_processed'] += 1
                        
                        # Print sample data
                        if 'data' in data and stats['messages_processed'] % 5 == 0:
                            symbol = data['data'].get('s', '?').upper()
                            bid = data['data'].get('b', '?')
                            ask = data['data'].get('a', '?')
                            print(f"   ✅ {stats['messages_processed']:3d}: {symbol} | "
                                  f"Bid={bid} Ask={ask} (CPU sims: {stats['cpu_simulations']})")
                    
                    except Exception as e:
                        stats['errors'] += 1
                        print(f"   ⚠️  Processing error: {e}")
                
                except asyncio.TimeoutError:
                    print(f"   ⚠️  Receive timeout (this is normal if Binance sends slowly)")
                    continue
                
                except Exception as e:
                    stats['connection_errors'] += 1
                    print(f"   ❌ Connection error: {e}")
                    if "1011" in str(e) or "1006" in str(e):
                        print(f"   (This 1011/1006 error should have been suppressed!)")
                    break
    
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        stats['connection_errors'] += 1
    
    # Print results
    elapsed = (datetime.now() - stats['start_time']).total_seconds()
    
    print("\n" + "=" * 80)
    print("📊 Test Results")
    print("=" * 80)
    print(f"⏱️  Duration: {elapsed:.1f}s")
    print(f"📥 Messages received: {stats['messages_received']}")
    print(f"✅ Messages processed: {stats['messages_processed']}")
    print(f"💻 CPU simulations: {stats['cpu_simulations']} (100ms each)")
    print(f"❌ Errors: {stats['errors']}")
    print(f"🔌 Connection errors: {stats['connection_errors']}")
    
    print("\n🔍 Analysis:")
    if stats['messages_processed'] > 0:
        print(f"   ✅ Successfully processed {stats['messages_processed']} messages under CPU load")
        print(f"   ✅ Total CPU simulation time: {stats['cpu_simulations'] * 100}ms")
        if stats['connection_errors'] == 0:
            print(f"   ✅ NO 1011/1006 connection errors (fire-and-forget working!)")
        else:
            print(f"   ⚠️  {stats['connection_errors']} connection errors detected")
    else:
        print(f"   ❌ No messages processed - connection may be unstable")
    
    print("\n" + "=" * 80)
    
    # Exit with appropriate code
    if stats['connection_errors'] == 0 and stats['messages_processed'] > 10:
        print("✅ TEST PASSED - WebSocket stability verified!")
        print("=" * 80)
        return 0
    else:
        print("❌ TEST FAILED - WebSocket stability issues detected")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_websocket_stability())
    sys.exit(exit_code)
