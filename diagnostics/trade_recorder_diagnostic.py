"""
TradeRecorder 診斷工具
測試 TradeRecorder 所有核心功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.core.trade_recorder import TradeRecorder
import logging
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def diagnose_trade_recorder():
    """診斷 TradeRecorder 問題"""
    logger.info("=" * 80)
    logger.info("🔧 開始 TradeRecorder 診斷")
    logger.info("=" * 80)
    
    class MockConfig:
        pass
    
    config = MockConfig()
    
    try:
        # 1. 測試初始化
        logger.info("\n1️⃣ 測試 TradeRecorder 初始化...")
        recorder = TradeRecorder(config)
        logger.info(f"✅ TradeRecorder 初始化成功 | _initialized: {recorder._initialized}")
        
        # 2. 測試健康檢查
        logger.info("\n2️⃣ 測試健康檢查...")
        health = await recorder.health_check()
        logger.info(f"✅ 健康檢查結果: {health}")
        
        # 3. 測試 get_trade_count (初始狀態)
        logger.info("\n3️⃣ 測試 get_trade_count (初始狀態)...")
        count = await recorder.get_trade_count()
        logger.info(f"✅ get_trade_count: {count} 筆交易")
        
        # 4. 測試 record_trade
        logger.info("\n4️⃣ 測試 record_trade...")
        test_trades = [
            {
                'symbol': 'BTCUSDT',
                'direction': 'LONG',
                'entry_price': 50000.0,
                'position_size': 0.01,
                'confidence': 65.0,
                'win_probability': 60.0,
                'risk_reward_ratio': 2.5
            },
            {
                'symbol': 'ETHUSDT',
                'direction': 'SHORT',
                'entry_price': 3000.0,
                'position_size': 0.1,
                'confidence': 70.0,
                'win_probability': 65.0,
                'risk_reward_ratio': 3.0
            }
        ]
        
        for trade in test_trades:
            success = await recorder.record_trade(trade)
            logger.info(f"✅ record_trade: {trade['symbol']} | 成功: {success}")
        
        # 5. 再次測試 get_trade_count
        logger.info("\n5️⃣ 測試 get_trade_count (記錄後)...")
        count_after = await recorder.get_trade_count()
        logger.info(f"✅ 交易後 count: {count_after} 筆交易")
        
        # 6. 測試 get_recent_performance
        logger.info("\n6️⃣ 測試 get_recent_performance...")
        performance = await recorder.get_recent_performance(hours=24)
        logger.info(f"✅ 近期表現:")
        logger.info(f"   總交易數: {performance['total_trades']}")
        logger.info(f"   勝率: {performance['win_rate']:.2f}%")
        logger.info(f"   總盈虧: {performance['total_pnl']}")
        
        # 7. 測試 record_entry (兼容性方法)
        logger.info("\n7️⃣ 測試 record_entry (兼容性方法)...")
        test_signal = {
            'symbol': 'ADAUSDT',
            'direction': 'LONG',
            'current_price': 0.5,
            'confidence': 75.0,
            'win_probability': 70.0,
            'risk_reward_ratio': 2.8
        }
        position_info = {'size': 100.0}
        recorder.record_entry(test_signal, position_info)
        logger.info(f"✅ record_entry: {test_signal['symbol']} 完成")
        
        # 8. 最終狀態檢查
        logger.info("\n8️⃣ 最終狀態檢查...")
        final_count = await recorder.get_trade_count()
        final_health = await recorder.health_check()
        logger.info(f"✅ 最終交易數: {final_count} 筆")
        logger.info(f"✅ 最終健康狀態: {final_health}")
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 TradeRecorder 診斷完成 - 所有測試通過 ✅")
        logger.info("=" * 80)
        return True
        
    except Exception as e:
        logger.error(f"\n❌ TradeRecorder 診斷失敗: {e}")
        import traceback
        logger.error(f"詳細錯誤:\n{traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(diagnose_trade_recorder())
    sys.exit(0 if success else 1)
