#!/usr/bin/env python3
"""
🧹 REPOSITORY CLEANUP & REORGANIZATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Deletes legacy files and reorganizes to target SMC-Quant Sharded Architecture
"""

import os
import shutil
from pathlib import Path

# ════════════════════════════════════════════════════════════════════════════
# LEGACY FILES TO DELETE (by category)
# ════════════════════════════════════════════════════════════════════════════

LEGACY_FILES = {
    "Old WebSocket Logic": [
        "src/core/websocket/advanced_feed_manager.py",
        "src/core/websocket/data_gap_handler.py",
        "src/core/websocket/data_quality_monitor.py",
        "src/core/websocket/railway_optimized_feed.py",
        "src/core/websocket/websocket_manager.py",
        "src/core/websocket/heartbeat_monitor.py",
    ],
    "Old Position/Cache Logic": [
        "src/core/cache_manager.py",
        "src/core/position_sizer.py",
        "src/core/position_controller.py",
        "src/core/virtual_position_monitor.py",
        "src/core/concurrent_dict_manager.py",
    ],
    "Old ML/Model Logic": [
        "src/core/model_evaluator.py",
        "src/core/model_rating_engine.py",
        "src/core/model_initializer.py",
        "src/core/evaluation_engine.py",
    ],
    "Old Strategy/Trading Logic": [
        "src/core/capital_allocator.py",
        "src/core/self_learning_trader_controller.py",
        "src/core/sltp_adjuster.py",
        "src/core/trend_monitor.py",
        "src/core/trading_state_machine.py",
        "src/core/symbol_selector.py",
    ],
    "Old Utilities & Config": [
        "src/core/async_decorators.py",
        "src/core/exception_handler.py",
        "src/core/circuit_breaker.py",
        "src/core/daily_reporter.py",
        "src/core/logging_config.py",
        "src/core/unified_scheduler.py",
        "src/core/lifecycle_manager.py",
        "src/core/startup_manager.py",
        "src/core/leverage_engine.py",
        "src/core/margin_safety_controller.py",
        "src/core/rate_limiter.py",
        "src/core/safety_validator.py",
        "src/core/data_models.py",
        "src/core/on_demand_cache_warmer.py",
    ],
    "Old Elite Folder": [
        "src/core/elite/",
    ],
    "Obsolete Directories": [
        "src/benchmark/",
        "src/diagnostics/",
        "src/features/",
        "src/integrations/",
        "src/risk/",
        "src/simulation/",
        "src/monitoring/",
        "src/managers/",
        "src/services/",
    ],
}

# ════════════════════════════════════════════════════════════════════════════
# FILES TO KEEP & ORGANIZE (Target Structure)
# ════════════════════════════════════════════════════════════════════════════

TARGET_STRUCTURE = {
    "src/core": [
        "cluster_manager.py",
        "smc_engine.py",
        "risk_manager.py",
        "market_universe.py",
        "account_state_cache.py",
        "unified_config_manager.py",
        "startup_prewarmer.py",
    ],
    "src/core/websocket": [
        "unified_feed.py",
        "shard_feed.py",
        "account_feed.py",
    ],
    "src/database": [
        "unified_database_manager.py",
    ],
    "src/strategies": [
        "ict_scalper.py",
    ],
    "src/ml": [
        "feature_engineer.py",
        "predictor.py",
        "trainer.py",
    ],
    "src/utils": [
        "smart_logger.py",
    ],
}

def delete_file(path):
    """Safely delete a file"""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
            return True, f"Deleted directory: {path}"
        elif os.path.isfile(path):
            os.remove(path)
            return True, f"Deleted file: {path}"
        else:
            return False, f"Not found: {path}"
    except Exception as e:
        return False, f"Error deleting {path}: {e}"

def main():
    print("🧹 REPOSITORY CLEANUP & REORGANIZATION")
    print("=" * 80)
    
    deleted_count = 0
    failed_count = 0
    
    # Delete legacy files
    for category, files in LEGACY_FILES.items():
        print(f"\n📋 {category}")
        print("-" * 80)
        
        for filepath in files:
            success, message = delete_file(filepath)
            
            if success:
                print(f"  ✅ {message}")
                deleted_count += 1
            else:
                print(f"  ⚠️  {message}")
                if "Not found" not in message:
                    failed_count += 1
    
    # Report
    print("\n" + "=" * 80)
    print("📊 CLEANUP SUMMARY")
    print("=" * 80)
    print(f"✅ Deleted: {deleted_count} files/folders")
    print(f"⚠️  Failed: {failed_count}")
    print(f"\n✅ Repository cleaned successfully!")
    
    # Check what remains
    print("\n" + "=" * 80)
    print("📂 REMAINING TARGET STRUCTURE")
    print("=" * 80)
    
    for directory, expected_files in TARGET_STRUCTURE.items():
        exists = os.path.isdir(directory)
        status = "✅" if exists else "❌"
        print(f"{status} {directory}")
        
        if exists:
            for filename in expected_files:
                filepath = os.path.join(directory, filename)
                file_exists = os.path.isfile(filepath)
                file_status = "✅" if file_exists else "❌"
                print(f"    {file_status} {filename}")

if __name__ == "__main__":
    main()
