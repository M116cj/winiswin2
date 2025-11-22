#!/usr/bin/env python3
"""
🏗️ PHASE 2: STRUCTURAL VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Verify that ONLY the new Sharded SMC-Quant Architecture exists and is complete
"""

import os
import sys

def verify_file_existence():
    """Verify all new files exist"""
    
    print("=" * 80)
    print("🏗️ PHASE 2: STRUCTURAL VERIFICATION")
    print("=" * 80)
    
    required_files = [
        # Core Infrastructure
        "src/core/market_universe.py",
        "src/core/smc_engine.py",
        "src/core/cluster_manager.py",
        "src/core/risk_manager.py",
        "src/core/startup_prewarmer.py",
        
        # WebSocket Layer
        "src/core/websocket/shard_feed.py",
        "src/core/websocket/account_feed.py",
        "src/core/websocket/unified_feed.py",
        
        # ML Pipeline
        "src/ml/feature_engineer.py",
        "src/ml/predictor.py",
        
        # Strategy
        "src/strategies/ict_scalper.py",
    ]
    
    print("\n📋 File Existence Check:")
    print("-" * 80)
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ FOUND: {file_path}")
        else:
            print(f"❌ MISSING: {file_path}")
            all_exist = False
    
    return all_exist


def verify_dependencies():
    """Verify all required dependencies are importable"""
    
    print("\n📦 Dependency Check:")
    print("-" * 80)
    
    required_deps = [
        ('polars', 'Polars (high-speed dataframes)'),
        ('lightgbm', 'LightGBM (ML model)'),
        ('numpy', 'NumPy (numerical computing)'),
        ('asyncpg', 'Asyncpg (async PostgreSQL)'),
        ('websockets', 'Websockets (WebSocket client)'),
    ]
    
    all_available = True
    for package, description in required_deps:
        try:
            __import__(package)
            print(f"✅ {description}: installed")
        except ImportError:
            print(f"❌ {description}: NOT INSTALLED")
            all_available = False
    
    return all_available


def verify_core_classes():
    """Verify all core classes exist and can be imported"""
    
    print("\n🧠 Core Classes Check:")
    print("-" * 80)
    
    class_imports = [
        ("src.core.market_universe", "BinanceUniverse"),
        ("src.core.smc_engine", "SMCEngine"),
        ("src.core.cluster_manager", "ClusterManager"),
        ("src.core.risk_manager", "RiskManager"),
        ("src.core.startup_prewarmer", "StartupPrewarmer"),
        ("src.ml.feature_engineer", "FeatureEngineer"),
        ("src.ml.predictor", "MLPredictor"),
        ("src.strategies.ict_scalper", "ICTScalper"),
    ]
    
    all_available = True
    for module_name, class_name in class_imports:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"✅ {class_name}: importable from {module_name}")
        except Exception as e:
            print(f"❌ {class_name}: FAILED - {e}")
            all_available = False
    
    return all_available


def verify_config_integrity():
    """Verify configuration system"""
    
    print("\n⚙️ Configuration Integrity Check:")
    print("-" * 80)
    
    try:
        # Try to load unified config
        from src.core.unified_config_manager import UnifiedConfigManager
        config = UnifiedConfigManager()
        print("✅ UnifiedConfigManager: loaded")
        
        # Check key configs
        if hasattr(config, 'RATE_LIMIT_REQUESTS'):
            print(f"✅ RATE_LIMIT_REQUESTS: {config.RATE_LIMIT_REQUESTS}")
        else:
            print("⚠️ RATE_LIMIT_REQUESTS: not found")
        
        return True
    except Exception as e:
        print(f"⚠️ UnifiedConfigManager: {e}")
        return False


def main():
    print("\n" + "=" * 80)
    
    checks = [
        ("File Existence", verify_file_existence()),
        ("Dependencies", verify_dependencies()),
        ("Core Classes", verify_core_classes()),
        ("Configuration", verify_config_integrity()),
    ]
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ VERIFICATION SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    print("\n" + "=" * 80)
    
    if passed == total:
        print("✅ NEW ARCHITECTURE VERIFIED - Ready for deployment!")
    else:
        print(f"⚠️ {total - passed}/{total} checks failed - Review above")
    
    print("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
