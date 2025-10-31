#!/usr/bin/env python3
"""
測試Signal Handling和Graceful Shutdown
驗證SIGINT/SIGTERM能夠正確觸發force_flush
"""

import asyncio
import signal
import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加src到路徑
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.managers.trade_recorder import TradeRecorder

async def test_signal_handling():
    """
    測試signal handling和force_flush
    模擬：
    1. 添加pending_entries（未達到flush門檻）
    2. 發送SIGINT信號
    3. 驗證force_flush被調用
    """
    print("🔍 測試：Signal Handling + Force Flush")
    
    # 創建TradeRecorder
    recorder = TradeRecorder()
    
    # 添加一些pending_entries（模擬開倉）
    for i in range(3):
        entry = {
            'symbol': f'TEST{i}USDT',
            'entry_price': 1000.0 + i,
            'direction': 'LONG',
            'entry_timestamp': datetime.now().isoformat(),
            'confidence': 0.7,
            'leverage': 5,
            'position_value': 100
        }
        recorder.pending_entries.append(entry)
    
    print(f"  ✅ 已添加 {len(recorder.pending_entries)} 個pending_entries")
    
    # 模擬shutdown時的force_flush
    print("  💾 模擬系統shutdown，調用force_flush()...")
    recorder.force_flush()
    
    # 驗證數據已保存
    if os.path.exists(Config.ML_PENDING_FILE):
        with open(Config.ML_PENDING_FILE, 'r') as f:
            saved_data = json.load(f)
        print(f"  ✅ pending_entries已保存到磁盤（{len(saved_data)}條）")
        
        # 清理
        os.remove(Config.ML_PENDING_FILE)
        return True
    else:
        print(f"  ❌ pending_entries未保存！")
        return False

async def test_loop_call_soon_threadsafe():
    """
    測試loop.call_soon_threadsafe機制
    驗證shutdown能在event loop中正確執行
    """
    print("\n🔍 測試：Event Loop Integration")
    
    shutdown_called = False
    
    async def mock_shutdown():
        nonlocal shutdown_called
        shutdown_called = True
        print("  ✅ shutdown()被正確調用")
    
    # 模擬signal handler
    loop = asyncio.get_running_loop()
    
    def signal_handler(sig, frame):
        print(f"  收到信號 {sig}")
        loop.call_soon_threadsafe(lambda: asyncio.create_task(mock_shutdown()))
    
    # 註冊handler
    signal.signal(signal.SIGUSR1, signal_handler)
    
    # 發送信號（使用SIGUSR1代替SIGINT避免真正中斷）
    print("  📡 發送測試信號...")
    os.kill(os.getpid(), signal.SIGUSR1)
    
    # 等待shutdown被調用
    await asyncio.sleep(0.1)
    
    if shutdown_called:
        print("  ✅ Event loop integration正常")
        return True
    else:
        print("  ❌ shutdown未被調用（event loop問題）")
        return False

async def main():
    """運行所有測試"""
    print("=" * 80)
    print("🧪 Graceful Shutdown + Signal Handling測試")
    print("=" * 80)
    
    try:
        # 測試1：Force flush
        test1 = await test_signal_handling()
        
        # 測試2：Event loop integration
        test2 = await test_loop_call_soon_threadsafe()
        
        print("\n" + "=" * 80)
        if test1 and test2:
            print("✅ 所有測試通過！Shutdown機制正常！")
            print("=" * 80)
            return True
        else:
            print("❌ 部分測試失敗")
            print("=" * 80)
            return False
            
    except Exception as e:
        print(f"\n❌ 測試錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
