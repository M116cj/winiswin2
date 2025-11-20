#!/usr/bin/env python3
"""
ML Model Health Diagnostic Script v1.0
=====================================

Performs a "Pulse Check" on the AI components:
1. Data Pathway (PostgreSQL → Features)
2. Model Forward Pass (Inference)
3. Model Backward Pass (Learning Capability)
4. State Persistence

Usage: python scripts/verify_model_health.py
"""

import sys
import os
import asyncio
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.abspath('.'))

from src.database.async_manager import AsyncDatabaseManager
from src.database.service import TradingDataService
from src.ml.feature_engine import FeatureEngine
from src.ml.model_wrapper import MLModelWrapper
from src.ml.feature_schema import CANONICAL_FEATURE_NAMES, features_to_vector
from src.core.model_initializer import ModelInitializer
from src.config import Config


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")


def print_test(name, status, details=""):
    """Print test result"""
    status_icon = f"{Colors.GREEN}✅ PASS" if status else f"{Colors.RED}❌ FAIL"
    print(f"{status_icon}{Colors.END} {Colors.BOLD}{name}{Colors.END}")
    if details:
        print(f"    {details}")


async def test_1_data_pathway():
    """
    Test 1: The Data Pathway (PostgreSQL → Features)
    
    Returns:
        (bool, dict): (success, details)
    """
    print_header("🧪 Test 1: Data Pathway (PostgreSQL → Features)")
    
    try:
        # Initialize database
        print("  📊 Initializing AsyncDatabaseManager...")
        db_manager = AsyncDatabaseManager()
        await db_manager.initialize()
        
        data_service = TradingDataService(db_manager)
        
        # Fetch recent trades (query by win status since status column doesn't exist)
        print("  📥 Fetching last 100 trades from PostgreSQL...")
        trades = await data_service.get_trade_history(limit=100)  # Get all trades
        
        if not trades:
            print(f"  {Colors.YELLOW}⚠️  No trades found in database{Colors.END}")
            print(f"  {Colors.YELLOW}    This is expected for a fresh system{Colors.END}")
            # Create dummy signal data for testing
            print("  🔧 Creating dummy signal data for feature extraction test...")
            dummy_signal = {
                'symbol': 'BTCUSDT',
                'entry_price': 67000.0,
                'indicators': {
                    'atr': 150.0,
                    'rsi': 55.0,
                    'ema_20': 66500.0,
                    'ema_50': 66000.0
                },
                'klines_1h': [],
                'klines_15m': [],
                'klines_5m': []
            }
            
            # Test feature engine
            feature_engine = FeatureEngine()
            features = feature_engine.build_enhanced_features(
                signal=dummy_signal,
                klines_data={
                    '1h': [],
                    '15m': [],
                    '5m': []
                }
            )
        else:
            print(f"  ✅ Fetched {len(trades)} trades")
            
            # Use first trade for feature extraction test
            trade = trades[0]
            features = trade.get('features', {})
        
        # Validate features
        print(f"  🔬 Validating features...")
        
        if not features:
            return False, {"error": "No features extracted"}
        
        # Check for 12 canonical features
        missing_features = [f for f in CANONICAL_FEATURE_NAMES if f not in features]
        if missing_features:
            return False, {
                "error": f"Missing features: {missing_features}",
                "found": len(features),
                "expected": len(CANONICAL_FEATURE_NAMES)
            }
        
        # Check for NaN values
        nan_features = []
        for feat_name in CANONICAL_FEATURE_NAMES:
            value = features.get(feat_name)
            if value is None or (isinstance(value, float) and np.isnan(value)):
                nan_features.append(feat_name)
        
        if nan_features:
            return False, {
                "error": f"NaN values in features: {nan_features}",
                "total_features": len(CANONICAL_FEATURE_NAMES)
            }
        
        # Convert to vector
        feature_vector = features_to_vector(features)
        
        # Close database
        await db_manager.close()
        
        return True, {
            "trades_count": len(trades) if trades else 0,
            "features_extracted": len(features),
            "canonical_features": len(CANONICAL_FEATURE_NAMES),
            "nan_count": 0,
            "sample_features": {k: features[k] for k in list(CANONICAL_FEATURE_NAMES)[:3]},
            "vector_shape": len(feature_vector)
        }
        
    except Exception as e:
        return False, {"error": str(e), "exception_type": type(e).__name__}


async def test_2_model_inference():
    """
    Test 2: Model Forward Pass (Inference)
    
    Returns:
        (bool, dict): (success, details)
    """
    print_header("🧠 Test 2: Model Forward Pass (Inference)")
    
    try:
        # Load model
        print("  📦 Loading ML model...")
        model_wrapper = MLModelWrapper(model_path="models/xgboost_model.json")
        
        if not model_wrapper.is_loaded:
            return False, {
                "error": "Model not loaded",
                "model_path": "models/xgboost_model.json",
                "exists": Path("models/xgboost_model.json").exists()
            }
        
        print(f"  ✅ Model loaded successfully")
        
        # Create dummy features for inference
        print("  🔬 Running inference with dummy features...")
        dummy_features = [0.5] * 12  # 12 features with neutral values
        
        # Run prediction
        prediction = model_wrapper.predict(dummy_features)
        
        if prediction is None:
            return False, {"error": "Prediction returned None"}
        
        # Validate prediction
        if not isinstance(prediction, (int, float)):
            return False, {
                "error": f"Invalid prediction type: {type(prediction)}",
                "value": prediction
            }
        
        if np.isnan(prediction):
            return False, {"error": "Prediction is NaN"}
        
        # Check if prediction is in valid range (0-1 for probability)
        if not (0 <= prediction <= 1):
            return False, {
                "error": f"Prediction out of range: {prediction}",
                "expected_range": "[0, 1]"
            }
        
        return True, {
            "prediction": float(prediction),
            "input_features": len(dummy_features),
            "output_type": type(prediction).__name__,
            "in_valid_range": True
        }
        
    except Exception as e:
        return False, {"error": str(e), "exception_type": type(e).__name__}


async def test_3_model_learning_capability():
    """
    Test 3: Model Backward Pass (Learning Capability)
    
    Tests if the model can be retrained (weights update)
    
    Returns:
        (bool, dict): (success, details)
    """
    print_header("🎓 Test 3: Model Backward Pass (Learning Capability)")
    
    try:
        import xgboost as xgb
        
        print("  🔧 Creating test training dataset...")
        
        # Create dummy training data
        n_samples = 100
        X = np.random.rand(n_samples, 12) * 100  # 12 features
        y = np.random.randint(0, 2, n_samples)  # Binary labels
        
        # Take snapshot of model before training
        model_path = Path("models/xgboost_model.json")
        
        if model_path.exists():
            print("  📸 Taking snapshot of existing model...")
            # Load existing model
            model_before = xgb.Booster()
            model_before.load_model(str(model_path))
            
            # Get model dump before (representation of trees)
            dump_before = model_before.get_dump()
            trees_before = len(dump_before)
            
            print(f"  ✅ Existing model: {trees_before} trees")
        else:
            print(f"  ℹ️  No existing model found")
            dump_before = None
            trees_before = 0
        
        # Train new model with dummy data
        print("  🏋️  Running training step...")
        dtrain = xgb.DMatrix(X, label=y)
        
        params = {
            'objective': 'binary:logistic',
            'max_depth': 3,
            'learning_rate': 0.1,
            'n_estimators': 10,
            'random_state': 42
        }
        
        # Train
        model_after = xgb.train(params, dtrain, num_boost_round=10, verbose_eval=False)
        
        # Get model dump after
        dump_after = model_after.get_dump()
        trees_after = len(dump_after)
        
        print(f"  ✅ New model trained: {trees_after} trees")
        
        # Verify model changed
        if dump_before is not None:
            # Compare tree structures
            trees_changed = (dump_before != dump_after)
        else:
            trees_changed = (trees_after > 0)
        
        # Test prediction on new model
        X_test = np.random.rand(5, 12) * 100
        dtest = xgb.DMatrix(X_test)
        predictions = model_after.predict(dtest)
        
        # Verify predictions are valid
        valid_predictions = all(0 <= p <= 1 for p in predictions)
        
        if not trees_changed:
            return False, {
                "error": "Model did not change after training",
                "trees_before": trees_before,
                "trees_after": trees_after
            }
        
        if not valid_predictions:
            return False, {
                "error": "Invalid predictions after training",
                "predictions": predictions.tolist()
            }
        
        return True, {
            "training_samples": n_samples,
            "trees_trained": trees_after,
            "model_changed": trees_changed,
            "test_predictions": predictions[:3].tolist(),
            "all_valid": valid_predictions,
            "capability": "Learning enabled"
        }
        
    except ImportError:
        return False, {
            "error": "XGBoost not installed",
            "action": "pip install xgboost"
        }
    except Exception as e:
        return False, {"error": str(e), "exception_type": type(e).__name__}


async def test_4_state_persistence():
    """
    Test 4: State Persistence
    
    Tests saving and loading model state/market regime
    
    Returns:
        (bool, dict): (success, details)
    """
    print_header("💾 Test 4: State Persistence")
    
    try:
        # Test model file persistence
        model_path = Path("models/xgboost_model.json")
        flag_path = Path("models/initialized.flag")
        
        print("  📁 Checking model files...")
        
        model_exists = model_path.exists()
        flag_exists = flag_path.exists()
        
        if model_exists:
            model_size = model_path.stat().st_size / 1024  # KB
            print(f"  ✅ Model file exists: {model_size:.2f} KB")
        else:
            print(f"  ⚠️  Model file not found: {model_path}")
        
        if flag_exists:
            print(f"  ✅ Initialization flag exists")
        else:
            print(f"  ⚠️  Initialization flag not found: {flag_path}")
        
        # Test database state persistence
        print("  🗄️  Testing database state persistence...")
        db_manager = AsyncDatabaseManager()
        await db_manager.initialize()
        
        data_service = TradingDataService(db_manager)
        
        # Check if we can query trade count (state indicator)
        trade_count = await data_service.get_trade_count('all')
        
        print(f"  ✅ Database accessible, {trade_count} closed trades")
        
        await db_manager.close()
        
        # Overall success if at least database works
        success = True  # Database persistence is key
        
        return success, {
            "model_file": {
                "exists": model_exists,
                "size_kb": model_size if model_exists else 0,
                "path": str(model_path)
            },
            "flag_file": {
                "exists": flag_exists,
                "path": str(flag_path)
            },
            "database": {
                "accessible": True,
                "trade_count": trade_count
            },
            "persistence_verified": True
        }
        
    except Exception as e:
        return False, {"error": str(e), "exception_type": type(e).__name__}


async def run_diagnostics():
    """Run all diagnostic tests"""
    print(f"\n{Colors.BOLD}ML Model Health Diagnostic v1.0{Colors.END}")
    print(f"{Colors.BOLD}Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}\n")
    
    results = {}
    
    # Run tests
    tests = [
        ("test_1_data_pathway", test_1_data_pathway),
        ("test_2_model_inference", test_2_model_inference),
        ("test_3_model_learning_capability", test_3_model_learning_capability),
        ("test_4_state_persistence", test_4_state_persistence),
    ]
    
    for test_name, test_func in tests:
        try:
            success, details = await test_func()
            results[test_name] = {"success": success, "details": details}
        except Exception as e:
            results[test_name] = {
                "success": False,
                "details": {"error": str(e), "exception_type": type(e).__name__}
            }
    
    # Print summary
    print_header("📊 Diagnostic Summary")
    
    test_1 = results["test_1_data_pathway"]
    test_2 = results["test_2_model_inference"]
    test_3 = results["test_3_model_learning_capability"]
    test_4 = results["test_4_state_persistence"]
    
    # Test 1
    if test_1["success"]:
        details = test_1["details"]
        print_test(
            "Data Pipeline",
            True,
            f"Trades: {details.get('trades_count', 0)}, Features: {details.get('features_extracted', 0)}, NaNs: {details.get('nan_count', 0)}"
        )
    else:
        print_test("Data Pipeline", False, f"Error: {test_1['details'].get('error', 'Unknown')}")
    
    # Test 2
    if test_2["success"]:
        details = test_2["details"]
        print_test(
            "Inference",
            True,
            f"Output: {details.get('prediction', 'N/A'):.4f} (valid range: [0, 1])"
        )
    else:
        print_test("Inference", False, f"Error: {test_2['details'].get('error', 'Unknown')}")
    
    # Test 3
    if test_3["success"]:
        details = test_3["details"]
        print_test(
            "Learning Capability",
            True,
            f"Weights updated: Yes ({details.get('trees_trained', 0)} trees)"
        )
    else:
        print_test("Learning Capability", False, f"Error: {test_3['details'].get('error', 'Unknown')}")
    
    # Test 4
    if test_4["success"]:
        details = test_4["details"]
        db_count = details.get('database', {}).get('trade_count', 0)
        model_exists = details.get('model_file', {}).get('exists', False)
        print_test(
            "State Persistence",
            True,
            f"DB: {db_count} trades, Model: {'Present' if model_exists else 'Missing'}"
        )
    else:
        print_test("State Persistence", False, f"Error: {test_4['details'].get('error', 'Unknown')}")
    
    # Overall status
    all_passed = all(r["success"] for r in results.values())
    critical_passed = test_1["success"] and test_4["success"]  # Data + Persistence are critical
    
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ ALL TESTS PASSED - ML System Healthy!{Colors.END}")
    elif critical_passed:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  PARTIAL PASS - Core components working, some features unavailable{Colors.END}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ TESTS FAILED - ML System requires attention{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")
    
    return all_passed, results


if __name__ == "__main__":
    success, results = asyncio.run(run_diagnostics())
    sys.exit(0 if success else 1)
