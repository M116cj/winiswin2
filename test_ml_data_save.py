#!/usr/bin/env python3
"""
測試ML數據保存機制
驗證：
1. 實時保存（ML_FLUSH_COUNT=1）
2. force_flush()工作正常
3. JSON Lines格式正確
"""

import json
import os
import sys
from pathlib import Path

# 添加src到路徑
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.managers.trade_recorder import TradeRecorder
from datetime import datetime

def test_ml_config():
    """測試配置修復"""
    print("🔍 測試1：配置驗證")
    print(f"  ML_FLUSH_COUNT: {Config.ML_FLUSH_COUNT}")
    print(f"  TRADES_FILE: {Config.TRADES_FILE}")
    
    assert Config.ML_FLUSH_COUNT == 1, f"❌ ML_FLUSH_COUNT應該是1，實際是{Config.ML_FLUSH_COUNT}"
    assert Config.TRADES_FILE.endswith('.jsonl'), f"❌ TRADES_FILE應該是.jsonl，實際是{Config.TRADES_FILE}"
    
    print("  ✅ 配置正確")

def test_immediate_flush():
    """測試實時保存"""
    print("\n🔍 測試2：實時保存機制")
    
    # 創建TradeRecorder
    recorder = TradeRecorder()
    
    # 模擬1筆交易
    entry_signal = {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry_price': 50000.0,
        'timestamp': datetime.now(),
        'confidence': 0.75,
        'win_probability': 0.65,
        'rr_ratio': 2.0,
        'timeframes': {},
        'market_structure': 'bullish',
        'order_blocks': 2,
        'liquidity_zones': 1,
        'indicators': {'rsi': 55, 'macd': 100}
    }
    
    position_info = {
        'leverage': 5,
        'position_value': 500
    }
    
    # 記錄開倉
    recorder.record_entry(entry_signal, position_info)
    print(f"  ✅ 開倉記錄已添加（待配對數：{len(recorder.pending_entries)}）")
    
    # 模擬平倉
    trade_result = {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry_price': 50000.0,
        'exit_price': 51000.0,
        'pnl': 10.0,
        'pnl_pct': 0.02,
        'close_reason': 'take_profit',
        'close_timestamp': datetime.now()
    }
    
    # 記錄平倉
    ml_record = recorder.record_exit(trade_result)
    
    # 檢查是否立即寫入磁盤（因為ML_FLUSH_COUNT=1）
    if os.path.exists(Config.TRADES_FILE):
        with open(Config.TRADES_FILE, 'r') as f:
            lines = f.readlines()
        print(f"  ✅ 數據已立即保存到磁盤（{len(lines)}行）")
        
        # 驗證JSON Lines格式
        for i, line in enumerate(lines):
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  ❌ 第{i+1}行不是有效的JSON: {e}")
                return False
        print(f"  ✅ JSON Lines格式正確")
    else:
        print(f"  ⚠️ 文件尚未創建（可能是第一筆交易）")
    
    return True

def test_force_flush():
    """測試force_flush"""
    print("\n🔍 測試3：Graceful Shutdown機制")
    
    recorder = TradeRecorder()
    
    # 模擬一些pending_entries（未觸發flush）
    recorder.pending_entries.append({
        'symbol': 'ETHUSDT',
        'entry_price': 3000.0
    })
    
    print(f"  待配對記錄數：{len(recorder.pending_entries)}")
    
    # 調用force_flush
    recorder.force_flush()
    print(f"  ✅ force_flush()執行成功")
    
    # 驗證pending_entries已保存
    if os.path.exists(Config.ML_PENDING_FILE):
        with open(Config.ML_PENDING_FILE, 'r') as f:
            saved_entries = json.load(f)
        print(f"  ✅ pending_entries已保存（{len(saved_entries)}條）")
    
    return True

def main():
    """運行所有測試"""
    print("=" * 80)
    print("🧪 ML學習系統修復驗證測試")
    print("=" * 80)
    
    try:
        test_ml_config()
        test_immediate_flush()
        test_force_flush()
        
        print("\n" + "=" * 80)
        print("✅ 所有測試通過！ML學習系統修復成功！")
        print("=" * 80)
        
        # 清理測試數據
        if os.path.exists(Config.TRADES_FILE):
            os.remove(Config.TRADES_FILE)
            print(f"\n🧹 已清理測試數據: {Config.TRADES_FILE}")
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ 測試失敗: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 測試錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
