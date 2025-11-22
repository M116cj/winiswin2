#!/usr/bin/env python3
"""
🧪 PHASE 3: FUNCTIONAL DRY-RUN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tests core SMC logic without requiring live Binance connection
"""

import sys
import numpy as np
from datetime import datetime

def test_smc_engine():
    """Test SMC pattern detection"""
    print("\n🧠 1. SMC Engine Functional Test:")
    
    try:
        from src.core.smc_engine import SMCEngine
        
        engine = SMCEngine()
        print("✅ SMCEngine initialized")
        
        # Generate synthetic OHLCV data
        np.random.seed(42)
        closes = 100 + np.cumsum(np.random.randn(20) * 0.5)  # Random walk
        highs = closes + np.abs(np.random.randn(20) * 0.3)
        lows = closes - np.abs(np.random.randn(20) * 0.3)
        
        klines = []
        for i in range(len(closes)):
            klines.append({
                'open': float(closes[i-1] if i > 0 else closes[i]),
                'high': float(highs[i]),
                'low': float(lows[i]),
                'close': float(closes[i]),
                'volume': 1000.0,
                'symbol': 'BTCUSDT'
            })
        
        # Test FVG detection
        fvg = engine.detect_fvg(klines[-5:])
        print(f"✅ FVG detection: {fvg}")
        assert isinstance(fvg, dict), "FVG should return dict"
        
        # Test Order Block detection
        ob = engine.detect_order_block(klines)
        print(f"✅ Order Block detection: {ob}")
        assert isinstance(ob, dict), "OB should return dict"
        
        # Test Liquidity Sweep detection
        ls = engine.detect_liquidity_sweep(klines)
        print(f"✅ Liquidity Sweep detection: {ls}")
        assert isinstance(ls, dict), "LS should return dict"
        
        # Test Structure detection
        struct = engine.detect_structure(klines)
        print(f"✅ Structure detection: {struct}")
        assert isinstance(struct, dict), "Structure should return dict"
        
        print("✅ SMCEngine functional test PASSED")
        return True
    
    except Exception as e:
        print(f"❌ SMCEngine test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_risk_manager():
    """Test risk manager"""
    print("\n🛡️ 2. Risk Manager Functional Test:")
    
    try:
        from src.core.risk_manager import get_risk_manager
        
        risk_manager = get_risk_manager()
        print("✅ RiskManager initialized")
        
        # Test position sizing
        size_high_conf = risk_manager.calculate_size(0.90, 10000)
        print(f"✅ Size at 90% confidence: {size_high_conf} (expected ~200)")
        assert size_high_conf > 100, "High confidence should give larger position"
        
        size_med_conf = risk_manager.calculate_size(0.70, 10000)
        print(f"✅ Size at 70% confidence: {size_med_conf} (expected ~100)")
        assert size_med_conf > 0, "Medium confidence should give position"
        
        size_low_conf = risk_manager.calculate_size(0.50, 10000)
        print(f"✅ Size at 50% confidence: {size_low_conf} (expected ~50)")
        assert size_low_conf >= 0, "Low confidence should give small/no position"
        
        assert size_high_conf > size_med_conf, "Higher confidence should mean larger size"
        assert size_med_conf > size_low_conf, "Size should scale with confidence"
        
        print("✅ RiskManager functional test PASSED")
        return True
    
    except Exception as e:
        print(f"❌ RiskManager test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feature_engineer():
    """Test feature engineering"""
    print("\n⚙️ 3. Feature Engineer Functional Test:")
    
    try:
        from src.ml.feature_engineer import get_feature_engineer
        
        engineer = get_feature_engineer()
        print("✅ FeatureEngineer initialized")
        
        # Generate synthetic data
        np.random.seed(42)
        closes = 100 + np.cumsum(np.random.randn(30) * 0.5)
        highs = closes + np.abs(np.random.randn(30) * 0.3)
        lows = closes - np.abs(np.random.randn(30) * 0.3)
        
        ohlcv = []
        for i in range(len(closes)):
            ohlcv.append({
                'open': float(closes[i-1] if i > 0 else closes[i]),
                'high': float(highs[i]),
                'low': float(lows[i]),
                'close': float(closes[i]),
                'volume': 1000.0,
            })
        
        # Mock SMC results (matching SMCEngine output format)
        smc_results = {
            'fvg': {
                'fvg_type': 'bullish',
                'fvg_start': 99.0,
                'fvg_end': 100.0,
                'fvg_size_atr': 1.5
            },
            'order_block': {
                'ob_type': 'bullish',
                'ob_price': 99.5,
                'ob_strength_atr': 2.0
            },
            'liquidity_sweep': {
                'ls_type': 'bullish',
                'ls_level': 99.0,
                'distance_atr': 1.0
            },
            'structure': {
                'bos_type': 'bullish',
                'bos_level': 100.0
            },
        }
        
        # Test feature computation
        features = engineer.compute_features(ohlcv, smc_results, min_size=5)
        print(f"✅ Computed features: {len(features)} features")
        assert len(features) == 12, "Should have 12 features"
        assert isinstance(features['rsi_14'], float), "Features should be floats"
        assert -1 <= features['market_structure'] <= 1, "market_structure normalized"
        
        print("✅ FeatureEngineer functional test PASSED")
        return True
    
    except Exception as e:
        print(f"❌ FeatureEngineer test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ml_predictor():
    """Test ML predictor"""
    print("\n🤖 4. ML Predictor Functional Test:")
    
    try:
        from src.ml.predictor import get_predictor
        
        predictor = get_predictor()
        print(f"✅ MLPredictor initialized (model loaded: {predictor.loaded})")
        
        # Test prediction with dummy features
        dummy_features = {
            'market_structure': 1.0,
            'order_blocks_count': 1.0,
            'institutional_candle': 0.8,
            'liquidity_grab': 1.0,
            'fvg_size_atr': 2.0,
            'fvg_proximity': 0.5,
            'ob_proximity': 0.3,
            'atr_normalized_volume': 1.0,
            'rsi_14': 0.3,  # Oversold
            'momentum_atr': 0.5,
            'time_to_next_level': 0.5,
            'confidence_ensemble': 0.8,
        }
        
        confidence = predictor.predict_confidence(dummy_features)
        print(f"✅ Prediction: {confidence:.3f} confidence")
        assert 0.0 <= confidence <= 1.0, "Confidence should be [0, 1]"
        
        # Test heuristic fallback
        if not predictor.loaded:
            print("   (using heuristic scoring - model file not found)")
        
        print("✅ MLPredictor functional test PASSED")
        return True
    
    except Exception as e:
        print(f"❌ MLPredictor test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ict_scalper():
    """Test ICT Scalper strategy"""
    print("\n🎯 5. ICT Scalper Functional Test:")
    
    try:
        from src.strategies.ict_scalper import ICTScalper
        
        scalper = ICTScalper()
        print("✅ ICTScalper initialized")
        
        # Test signal processing
        signal = {
            'symbol': 'BTCUSDT',
            'confidence': 0.75,
            'position_size': 0.002,
        }
        
        order = scalper.on_signal(signal)
        print(f"✅ Order generated: {order}")
        assert order is not None, "Should generate order"
        assert order['symbol'] == 'BTCUSDT', "Symbol should match"
        
        # Test strategy info
        info = scalper.get_info()
        print(f"✅ Strategy info: {info}")
        assert info['name'] == 'ICT Scalper v1.0', "Name should match"
        
        print("✅ ICTScalper functional test PASSED")
        return True
    
    except Exception as e:
        print(f"❌ ICTScalper test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("🧪 PHASE 3: FUNCTIONAL DRY-RUN")
    print("=" * 80)
    
    results = []
    
    # Run all tests
    results.append(("SMCEngine", test_smc_engine()))
    results.append(("RiskManager", test_risk_manager()))
    results.append(("FeatureEngineer", test_feature_engineer()))
    results.append(("MLPredictor", test_ml_predictor()))
    results.append(("ICTScalper", test_ict_scalper()))
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for component, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {component}")
    
    print("\n" + "=" * 80)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("🚀 System is ready for deployment!")
    else:
        print(f"❌ {total - passed}/{total} tests failed")
    print("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
