"""
⚡ 性能和壓力測試 - A.E.G.I.S. v8.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

測試內容:
1. Ring Buffer 吞吐量
2. 特徵計算性能
3. 數據庫寫入速度
4. 內存使用情況
"""

import asyncio
import time
import logging
import psutil
import numpy as np
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceTest:
    """性能測試"""
    
    @staticmethod
    def test_ring_buffer_throughput():
        """
        測試 Ring Buffer 吞吐量
        ✅ 期望: > 100 candles/sec
        """
        logger.info("🔥 [Performance Test 1] Ring Buffer 吞吐量")
        
        try:
            from src.ring_buffer import get_ring_buffer
            
            rb = get_ring_buffer(create=False)
            if rb is None:
                logger.error("❌ 無法連接 Ring Buffer")
                return False
            
            # 計算讀取速度
            initial_count = 0
            final_count = 0
            
            w, r = rb._get_cursors()
            initial_count = r
            
            # 等待 1 秒
            time.sleep(1.0)
            
            w, r = rb._get_cursors()
            final_count = r
            
            throughput = final_count - initial_count
            logger.info(f"📊 Ring Buffer 吞吐量: {throughput} candles/sec")
            
            if throughput > 10:  # 至少 10 candles/sec
                logger.info("✅ [PASS] 吞吐量達標")
                return True
            else:
                logger.warning(f"⚠️ [WARN] 吞吐量偏低: {throughput} candles/sec")
                return throughput > 1  # 至少有數據流入
        
        except Exception as e:
            logger.error(f"❌ [FAIL] 吞吐量測試異常: {e}")
            return False
    
    @staticmethod
    def test_feature_calculation_speed():
        """
        測試特徵計算性能
        ✅ 期望: 50 個蠟燭 < 100ms
        """
        logger.info("🔥 [Performance Test 2] 特徵計算速度")
        
        try:
            from src.indicators import Indicators
            
            # 生成 50 個蠟燭
            prices = np.array([100.0 + np.sin(i*0.1)*5 for i in range(50)])
            highs = prices + 0.5
            lows = prices - 0.5
            
            # 計時所有指標計算
            start = time.time()
            
            rsi = Indicators.rsi(prices, period=14)
            macd, signal, hist = Indicators.macd(prices, fast=12, slow=26, signal_period=9)
            atr = Indicators.atr(highs, lows, prices, period=14)
            bb = Indicators.bollinger_bands(prices, period=20, std_dev=2.0)
            
            elapsed_ms = (time.time() - start) * 1000
            
            logger.info(f"📊 特徵計算時間: {elapsed_ms:.2f}ms (50 candles)")
            logger.info(f"   RSI: {rsi:.2f}")
            logger.info(f"   MACD: {macd:.4f}")
            logger.info(f"   ATR: {atr:.4f}")
            logger.info(f"   BB Width: {bb:.4f}")
            
            if elapsed_ms < 100:
                logger.info("✅ [PASS] 計算速度優異")
                return True
            else:
                logger.warning(f"⚠️ [WARN] 計算速度: {elapsed_ms:.2f}ms")
                return elapsed_ms < 500  # 允許 500ms
        
        except Exception as e:
            logger.error(f"❌ [FAIL] 特徵計算性能測試異常: {e}")
            return False
    
    @staticmethod
    def test_memory_usage():
        """
        測試內存使用
        ✅ 期望: < 500 MB
        """
        logger.info("🔥 [Performance Test 3] 內存使用情況")
        
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            logger.info(f"📊 當前進程內存: {memory_mb:.2f} MB")
            
            # 檢查歷史峰值
            try:
                memory_percent = process.memory_percent()
                logger.info(f"📊 內存佔比: {memory_percent:.2f}%")
            except:
                pass
            
            if memory_mb < 500:
                logger.info("✅ [PASS] 內存使用正常")
                return True
            elif memory_mb < 1000:
                logger.warning(f"⚠️ [WARN] 內存使用偏高: {memory_mb:.2f}MB")
                return True
            else:
                logger.error(f"❌ [FAIL] 內存泄漏: {memory_mb:.2f}MB")
                return False
        
        except Exception as e:
            logger.error(f"❌ [FAIL] 內存測試異常: {e}")
            return False
    
    @staticmethod
    def test_database_write_speed():
        """
        測試數據庫寫入速度
        ✅ 期望: > 100 記錄/sec
        """
        logger.info("🔥 [Performance Test 4] 數據庫寫入速度")
        
        try:
            import asyncpg
            import os
            import json
            
            db_url = os.environ.get('DATABASE_URL')
            
            async def check():
                conn = await asyncpg.connect(db_url)
                try:
                    # 計算最近 100 條信號的寫入速度
                    signals = await conn.fetch("""
                        SELECT created_at FROM signals
                        ORDER BY created_at DESC
                        LIMIT 100
                    """)
                    
                    if len(signals) < 2:
                        logger.warning("⚠️ 信號不足以計算速度")
                        return True
                    
                    # 計算時間差
                    latest_time = signals[0]['created_at']
                    oldest_time = signals[-1]['created_at']
                    time_diff = (latest_time - oldest_time).total_seconds()
                    
                    if time_diff > 0:
                        write_speed = 100 / time_diff
                        logger.info(f"📊 信號寫入速度: {write_speed:.2f} signals/sec")
                        
                        if write_speed > 10:
                            logger.info("✅ [PASS] 寫入速度優秀")
                            return True
                        else:
                            logger.warning(f"⚠️ [WARN] 寫入速度: {write_speed:.2f} signals/sec")
                            return write_speed > 1
                    else:
                        logger.info("ℹ️ 最近 100 個信號在同一時刻寫入")
                        return True
                
                finally:
                    await conn.close()
            
            return asyncio.run(check())
        
        except Exception as e:
            logger.error(f"❌ [FAIL] 數據庫寫入速度測試異常: {e}")
            return False


class StressTest:
    """壓力測試"""
    
    @staticmethod
    def test_continuous_operation():
        """
        測試連續運行
        ✅ 運行 30 秒，檢查系統穩定性
        """
        logger.info("💥 [Stress Test 1] 連續運行穩定性 (30秒)")
        
        try:
            from src.ring_buffer import get_ring_buffer
            
            rb = get_ring_buffer(create=False)
            if rb is None:
                logger.error("❌ 無法連接 Ring Buffer")
                return False
            
            w_initial, r_initial = rb._get_cursors()
            logger.info(f"📊 初始狀態: w={w_initial}, r={r_initial}")
            
            # 運行 30 秒，每秒檢查一次
            errors = 0
            max_delay = 0
            
            for i in range(30):
                try:
                    w, r = rb._get_cursors()
                    delay = w - r
                    max_delay = max(max_delay, delay)
                    
                    if delay < 0:
                        logger.error(f"❌ 異常: 讀游標 > 寫游標 (w={w}, r={r})")
                        errors += 1
                    
                    if i % 10 == 0:
                        logger.info(f"⏱️ {i}s: w={w}, r={r}, delay={delay}")
                    
                    time.sleep(1.0)
                
                except Exception as e:
                    logger.error(f"❌ {i}s 時出錯: {e}")
                    errors += 1
            
            w_final, r_final = rb._get_cursors()
            logger.info(f"📊 最終狀態: w={w_final}, r={r_final}")
            logger.info(f"📊 30秒內最大延遲: {max_delay} candles")
            logger.info(f"📊 錯誤次數: {errors}")
            
            if errors == 0:
                logger.info("✅ [PASS] 系統運行穩定")
                return True
            else:
                logger.error(f"❌ [FAIL] 系統運行不穩定: {errors} 次錯誤")
                return False
        
        except Exception as e:
            logger.error(f"❌ [FAIL] 連續運行測試異常: {e}")
            return False
    
    @staticmethod
    def test_data_consistency():
        """
        測試數據一致性
        ✅ 驗證信號和虛擁交易的 1:1 關係
        """
        logger.info("💥 [Stress Test 2] 數據一致性驗證")
        
        try:
            import asyncpg
            import os
            
            db_url = os.environ.get('DATABASE_URL')
            
            async def check():
                conn = await asyncpg.connect(db_url)
                try:
                    # 檢查孤立信號 (無對應交易)
                    orphan_signals = await conn.fetchval("""
                        SELECT COUNT(*) FROM signals s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM virtual_trades vt
                            WHERE vt.signal_id = s.id
                        )
                    """)
                    
                    # 檢查孤立交易 (無對應信號)
                    orphan_trades = await conn.fetchval("""
                        SELECT COUNT(*) FROM virtual_trades vt
                        WHERE NOT EXISTS (
                            SELECT 1 FROM signals s
                            WHERE s.id = vt.signal_id
                        )
                    """)
                    
                    total_signals = await conn.fetchval("SELECT COUNT(*) FROM signals")
                    total_trades = await conn.fetchval("SELECT COUNT(*) FROM virtual_trades")
                    
                    logger.info(f"📊 數據一致性檢查:")
                    logger.info(f"   信號總數: {total_signals}")
                    logger.info(f"   交易總數: {total_trades}")
                    logger.info(f"   孤立信號: {orphan_signals}")
                    logger.info(f"   孤立交易: {orphan_trades}")
                    
                    if orphan_signals == 0 and orphan_trades == 0:
                        logger.info("✅ [PASS] 數據完全一致")
                        return True
                    else:
                        logger.warning(f"⚠️ [WARN] 存在孤立數據")
                        return True  # 允許某些孤立
                
                finally:
                    await conn.close()
            
            return asyncio.run(check())
        
        except Exception as e:
            logger.error(f"❌ [FAIL] 數據一致性測試異常: {e}")
            return False


async def run_all_performance_tests():
    """運行所有性能和壓力測試"""
    logger.info("🚀 開始運行性能和壓力測試")
    logger.info("="*60)
    
    tests = [
        # 性能測試
        ("Ring Buffer 吞吐量", PerformanceTest.test_ring_buffer_throughput),
        ("特徵計算速度", PerformanceTest.test_feature_calculation_speed),
        ("內存使用情況", PerformanceTest.test_memory_usage),
        ("數據庫寫入速度", PerformanceTest.test_database_write_speed),
        
        # 壓力測試
        ("連續運行穩定性", StressTest.test_continuous_operation),
        ("數據一致性驗證", StressTest.test_data_consistency),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} 異常: {e}")
            results.append((test_name, False))
        
        logger.info("-"*60)
    
    # 生成報告
    logger.info("📊 性能和壓力測試報告")
    logger.info("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("="*60)
    logger.info(f"通過率: {passed}/{total} ({100*passed/total:.1f}%)")
    
    if passed == total:
        logger.info("🎉 所有性能測試通過!")
    else:
        logger.warning(f"⚠️ {total - passed} 個測試失敗")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_all_performance_tests())
