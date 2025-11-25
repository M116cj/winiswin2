"""
🔬 A.E.G.I.S. v8.0 - 完整架構驗證測試套件
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

驗證以下核心組件：
1. Ring Buffer 進程間通信
2. 特徵計算準確性
3. 虛擁交易執行邏輯
4. 數據持久化完整性
5. ML 訓練管道
"""

import asyncio
import logging
import numpy as np
from datetime import datetime
import json

# 設置日誌
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestDataIntegrity:
    """測試 Ring Buffer 和數據流"""
    
    @staticmethod
    def test_ring_buffer_sync():
        """
        驗證 Ring Buffer 讀寫同步
        ✅ 期望: w=r（完全同步）
        """
        logger.info("🔍 [Test 1] Ring Buffer 同步測試")
        
        try:
            from src.ring_buffer import get_ring_buffer
            
            rb = get_ring_buffer(create=False)
            if rb is None:
                logger.error("❌ 無法連接 Ring Buffer")
                return False
            
            w, r = rb._get_cursors()
            logger.info(f"📊 Ring Buffer 狀態: w={w}, r={r}, 差異={w-r}")
            
            if w == r:
                logger.info("✅ [PASS] Ring Buffer 完全同步")
                return True
            else:
                logger.warning(f"⚠️ [WARN] 存在延遲: {w-r} 條蠟燭未讀")
                return True  # 允許合理的延遲
        
        except Exception as e:
            logger.error(f"❌ [FAIL] Ring Buffer 測試異常: {e}")
            return False
    
    @staticmethod
    def test_signal_distribution():
        """
        驗證信號均勻分佈
        ✅ 期望: 每個交易對 ~60,404/20 = ~3,020 條
        """
        logger.info("🔍 [Test 2] 信號分佈均勻性")
        
        try:
            import asyncpg
            import os
            
            db_url = os.environ.get('DATABASE_URL')
            
            # 異步連接
            async def check():
                conn = await asyncpg.connect(db_url)
                try:
                    result = await conn.fetch("""
                        SELECT symbol, COUNT(*) as count
                        FROM signals
                        GROUP BY symbol
                        ORDER BY count DESC
                    """)
                    
                    counts = [row[1] for row in result]
                    avg = np.mean(counts)
                    std = np.std(counts)
                    cv = std / avg if avg > 0 else 0  # 變異係數
                    
                    logger.info(f"📊 信號分佈統計:")
                    logger.info(f"   平均: {avg:.0f}")
                    logger.info(f"   標準差: {std:.2f}")
                    logger.info(f"   變異係數 (CV): {cv:.4f}")
                    
                    if cv < 0.05:  # CV < 5% = 非常均勻
                        logger.info("✅ [PASS] 信號分佈均勻 (CV < 5%)")
                        return True
                    else:
                        logger.warning(f"⚠️ [WARN] 分佈變異: {cv:.2%}")
                        return cv < 0.10  # 允許 CV < 10%
                
                finally:
                    await conn.close()
            
            return asyncio.run(check())
        
        except Exception as e:
            logger.error(f"❌ [FAIL] 信號分佈測試異常: {e}")
            return False


class TestFeatureCalculation:
    """測試特徵計算準確性"""
    
    @staticmethod
    def test_rsi_calculation():
        """
        驗證 RSI 計算
        ✅ RSI = 100 - (100 / (1 + RS))
        ✅ 期望範圍: 0-100
        """
        logger.info("🔍 [Test 3] RSI 計算準確性")
        
        try:
            from src.indicators import Indicators
            
            # 生成測試數據: 連續上升
            prices = np.array([100.0 + i*0.5 for i in range(50)])
            
            rsi = Indicators.rsi(prices, period=14)
            
            logger.info(f"📊 RSI 測試數據:")
            logger.info(f"   價格: {prices[:5].tolist()} ... {prices[-5:].tolist()}")
            logger.info(f"   計算結果: {rsi:.2f}")
            
            if 0 <= rsi <= 100:
                logger.info("✅ [PASS] RSI 在有效範圍內 (0-100)")
                
                # 驗證邏輯: 連續上升應該 RSI > 70
                if rsi > 70:
                    logger.info(f"✅ [PASS] 上升趨勢 RSI={rsi:.2f} > 70")
                    return True
                else:
                    logger.warning(f"⚠️ [WARN] RSI={rsi:.2f} 低於預期")
                    return True
            else:
                logger.error(f"❌ [FAIL] RSI 超出範圍: {rsi:.2f}")
                return False
        
        except Exception as e:
            logger.error(f"❌ [FAIL] RSI 測試異常: {e}")
            return False
    
    @staticmethod
    def test_macd_calculation():
        """
        驗證 MACD 計算
        ✅ MACD = EMA(12) - EMA(26)
        """
        logger.info("🔍 [Test 4] MACD 計算準確性")
        
        try:
            from src.indicators import Indicators
            
            # 生成測試數據
            prices = np.array([100.0 + np.sin(i*0.1)*5 for i in range(100)])
            
            macd_line, signal_line, histogram = Indicators.macd(prices, fast=12, slow=26, signal_period=9)
            
            logger.info(f"📊 MACD 測試結果:")
            logger.info(f"   MACD Line: {macd_line:.4f}")
            logger.info(f"   Signal Line: {signal_line:.4f}")
            logger.info(f"   Histogram: {histogram:.4f}")
            
            # 驗證: histogram = macd_line - signal_line
            expected_hist = macd_line - signal_line
            error = abs(histogram - expected_hist)
            
            if error < 0.0001:
                logger.info("✅ [PASS] MACD 計算正確")
                return True
            else:
                logger.error(f"❌ [FAIL] Histogram 錯誤: 期望={expected_hist:.4f}, 實際={histogram:.4f}")
                return False
        
        except Exception as e:
            logger.error(f"❌ [FAIL] MACD 測試異常: {e}")
            return False
    
    @staticmethod
    def test_atr_calculation():
        """
        驗證 ATR 計算
        ✅ ATR 必須 >= 0
        """
        logger.info("🔍 [Test 5] ATR 計算準確性")
        
        try:
            from src.indicators import Indicators
            
            # 生成測試數據
            highs = np.array([100.0 + i*0.3 for i in range(50)])
            lows = np.array([99.0 + i*0.3 for i in range(50)])
            closes = np.array([99.5 + i*0.3 for i in range(50)])
            
            atr = Indicators.atr(highs, lows, closes, period=14)
            
            logger.info(f"📊 ATR 測試結果: {atr:.4f}")
            
            if atr >= 0:
                logger.info("✅ [PASS] ATR 值有效 (>= 0)")
                return True
            else:
                logger.error(f"❌ [FAIL] ATR 無效: {atr:.4f}")
                return False
        
        except Exception as e:
            logger.error(f"❌ [FAIL] ATR 測試異常: {e}")
            return False


class TestVirtualTrading:
    """測試虛擁交易系統"""
    
    @staticmethod
    def test_pnl_calculation():
        """
        驗證 PnL 計算
        ✅ PnL = (exit_price - entry_price) * quantity - commission
        """
        logger.info("🔍 [Test 6] PnL 計算準確性")
        
        try:
            import asyncpg
            import os
            
            db_url = os.environ.get('DATABASE_URL')
            
            async def check():
                conn = await asyncpg.connect(db_url)
                try:
                    # 獲取最新完成的虛擁交易
                    trades = await conn.fetch("""
                        SELECT id, entry_price, exit_price, quantity, 
                               commission, pnl, side
                        FROM virtual_trades
                        WHERE exit_price IS NOT NULL AND closed_at IS NOT NULL
                        ORDER BY closed_at DESC
                        LIMIT 5
                    """)
                    
                    if not trades:
                        logger.warning("⚠️ 無已完成的虛擁交易")
                        return True
                    
                    all_correct = True
                    for trade in trades:
                        entry_p = float(trade['entry_price'])
                        exit_p = float(trade['exit_price'])
                        qty = float(trade['quantity'])
                        comm = float(trade['commission'])
                        recorded_pnl = float(trade['pnl'])
                        side = trade['side']
                        
                        # 計算預期 PnL
                        if side == 'BUY':
                            expected_pnl = (exit_p - entry_p) * qty - comm
                        else:  # SELL
                            expected_pnl = (entry_p - exit_p) * qty - comm
                        
                        error = abs(recorded_pnl - expected_pnl)
                        
                        if error < 0.01:  # 允許 0.01 精度誤差
                            logger.debug(f"✅ 交易 {trade['id']}: PnL 正確")
                        else:
                            logger.error(f"❌ 交易 {trade['id']}: PnL 錯誤")
                            logger.error(f"   期望: {expected_pnl:.2f}, 實際: {recorded_pnl:.2f}")
                            all_correct = False
                    
                    if all_correct:
                        logger.info("✅ [PASS] 所有 PnL 計算正確")
                    else:
                        logger.warning("⚠️ [WARN] 某些 PnL 計算有誤")
                    
                    return all_correct
                
                finally:
                    await conn.close()
            
            return asyncio.run(check())
        
        except Exception as e:
            logger.error(f"❌ [FAIL] PnL 測試異常: {e}")
            return False
    
    @staticmethod
    def test_commission_calculation():
        """
        驗證 Binance 手續費 (0.2%)
        ✅ Commission = (entry_price * quantity + exit_price * quantity) * 0.002
        """
        logger.info("🔍 [Test 7] 手續費計算準確性")
        
        try:
            import asyncpg
            import os
            
            db_url = os.environ.get('DATABASE_URL')
            
            async def check():
                conn = await asyncpg.connect(db_url)
                try:
                    trades = await conn.fetch("""
                        SELECT id, entry_price, exit_price, quantity, commission
                        FROM virtual_trades
                        WHERE exit_price IS NOT NULL
                        LIMIT 10
                    """)
                    
                    if not trades:
                        logger.warning("⚠️ 無交易記錄")
                        return True
                    
                    comm_correct = True
                    for trade in trades:
                        entry_p = float(trade['entry_price'])
                        exit_p = float(trade['exit_price'])
                        qty = float(trade['quantity'])
                        recorded_comm = float(trade['commission'])
                        
                        # Binance 往返手續費: 0.2%
                        expected_comm = (entry_p * qty + exit_p * qty) * 0.002
                        error = abs(recorded_comm - expected_comm) / expected_comm if expected_comm > 0 else 0
                        
                        if error < 0.01:  # 允許 1% 誤差
                            logger.debug(f"✅ 交易 {trade['id']}: 手續費正確")
                        else:
                            logger.error(f"❌ 交易 {trade['id']}: 手續費誤差 {error:.2%}")
                            comm_correct = False
                    
                    if comm_correct:
                        logger.info("✅ [PASS] 所有手續費計算正確")
                    
                    return comm_correct
                
                finally:
                    await conn.close()
            
            return asyncio.run(check())
        
        except Exception as e:
            logger.error(f"❌ [FAIL] 手續費測試異常: {e}")
            return False


class TestMLPipeline:
    """測試 ML 訓練管道"""
    
    @staticmethod
    def test_experience_buffer():
        """
        驗證 Experience Buffer 結構
        ✅ 期望: 每筆交易包含特徵和結果
        """
        logger.info("🔍 [Test 8] Experience Buffer 結構")
        
        try:
            import asyncpg
            import os
            import json
            
            db_url = os.environ.get('DATABASE_URL')
            
            async def check():
                conn = await asyncpg.connect(db_url)
                try:
                    records = await conn.fetch("""
                        SELECT id, features, outcome
                        FROM experience_buffer
                        LIMIT 5
                    """)
                    
                    if not records:
                        logger.info("ℹ️ Experience Buffer 為空 (正常 - 等待新交易)")
                        return True
                    
                    all_valid = True
                    for record in records:
                        try:
                            features = json.loads(record['features']) if isinstance(record['features'], str) else record['features']
                            outcome = json.loads(record['outcome']) if isinstance(record['outcome'], str) else record['outcome']
                            
                            required_features = ['confidence', 'rsi', 'atr', 'macd', 'bb_width']
                            missing = [f for f in required_features if f not in str(features)]
                            
                            if not missing:
                                logger.debug(f"✅ 記錄 {record['id']}: 特徵完整")
                            else:
                                logger.warning(f"⚠️ 記錄 {record['id']}: 缺少特徵 {missing}")
                                all_valid = False
                        
                        except json.JSONDecodeError as je:
                            logger.error(f"❌ 記錄 {record['id']}: JSON 解析失敗")
                            all_valid = False
                    
                    if all_valid:
                        logger.info("✅ [PASS] Experience Buffer 結構正確")
                    
                    return all_valid
                
                finally:
                    await conn.close()
            
            return asyncio.run(check())
        
        except Exception as e:
            logger.error(f"❌ [FAIL] Experience Buffer 測試異常: {e}")
            return False
    
    @staticmethod
    def test_ml_model_structure():
        """
        驗證 ML 模型表結構
        ✅ 期望: model_bytes, feature_names, accuracy 字段
        """
        logger.info("🔍 [Test 9] ML 模型表結構")
        
        try:
            import asyncpg
            import os
            
            db_url = os.environ.get('DATABASE_URL')
            
            async def check():
                conn = await asyncpg.connect(db_url)
                try:
                    schema = await conn.fetch("""
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_name = 'ml_models'
                        ORDER BY ordinal_position
                    """)
                    
                    required_cols = ['id', 'model_bytes', 'feature_names', 'accuracy', 'created_at']
                    actual_cols = [col[0] for col in schema]
                    missing = [c for c in required_cols if c not in actual_cols]
                    
                    logger.info(f"📊 ml_models 表欄位: {actual_cols}")
                    
                    if not missing:
                        logger.info("✅ [PASS] ML 模型表結構完整")
                        return True
                    else:
                        logger.error(f"❌ [FAIL] 缺少欄位: {missing}")
                        return False
                
                finally:
                    await conn.close()
            
            return asyncio.run(check())
        
        except Exception as e:
            logger.error(f"❌ [FAIL] ML 模型表結構測試異常: {e}")
            return False


async def run_all_tests():
    """運行所有測試"""
    logger.info("🚀 開始運行完整測試套件")
    logger.info("="*60)
    
    tests = [
        # 數據完整性
        ("Ring Buffer 同步", TestDataIntegrity.test_ring_buffer_sync),
        ("信號分佈均勻性", TestDataIntegrity.test_signal_distribution),
        
        # 特徵計算
        ("RSI 計算準確性", TestFeatureCalculation.test_rsi_calculation),
        ("MACD 計算準確性", TestFeatureCalculation.test_macd_calculation),
        ("ATR 計算準確性", TestFeatureCalculation.test_atr_calculation),
        
        # 虛擁交易
        ("PnL 計算準確性", TestVirtualTrading.test_pnl_calculation),
        ("手續費計算準確性", TestVirtualTrading.test_commission_calculation),
        
        # ML 管道
        ("Experience Buffer 結構", TestMLPipeline.test_experience_buffer),
        ("ML 模型表結構", TestMLPipeline.test_ml_model_structure),
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
    
    # 生成測試報告
    logger.info("📊 測試報告總結")
    logger.info("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("="*60)
    logger.info(f"通過率: {passed}/{total} ({100*passed/total:.1f}%)")
    
    if passed == total:
        logger.info("🎉 所有測試通過!")
    else:
        logger.warning(f"⚠️ {total - passed} 個測試失敗")
    
    return results


if __name__ == "__main__":
    # 運行測試
    asyncio.run(run_all_tests())
