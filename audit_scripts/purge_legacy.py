#!/usr/bin/env python3
"""
🧨 PHASE 1: THE PURGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Safely delete ALL legacy code that has been replaced by new architecture
"""

import os
import shutil
import sys

def purge_legacy_files():
    """Delete old legacy files"""
    
    print("=" * 80)
    print("🧨 PHASE 1: LEGACY CODE PURGE")
    print("=" * 80)
    
    # Files to delete
    legacy_files = [
        # Old Feed Logic (replaced by UnifiedFeed + ShardFeed)
        "src/core/websocket/base_feed.py",
        "src/core/websocket/optimized_base_feed.py",
        "src/core/websocket/price_feed.py",
        "src/core/websocket/kline_feed.py",
        
        # Old Strategy/Monitors
        "src/core/position_monitor_24x7.py",
        "src/strategies/self_learning_trader.py",
        "src/strategies/base_strategy.py",
        
        # Old ML utilities
        "src/ml/model_wrapper.py",
    ]
    
    # Additional files/patterns to check
    legacy_patterns = {
        "data/": "CSV data files (using Polars + Parquet now)",
        "models/": "Old JSON models (using LightGBM .txt now)",
    }
    
    deleted_count = 0
    skipped_count = 0
    
    print("\n📋 Deleting Legacy Files:")
    print("-" * 80)
    
    # Delete specific files
    for file_path in legacy_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"✅ DELETED: {file_path}")
                deleted_count += 1
            except Exception as e:
                print(f"⚠️ FAILED: {file_path} - {e}")
        else:
            print(f"⏭️ SKIPPED: {file_path} (not found)")
            skipped_count += 1
    
    # Check directories
    print("\n📁 Checking Legacy Directories:")
    print("-" * 80)
    
    # Clean data/ directory
    data_dir = "data"
    if os.path.exists(data_dir):
        csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
        if csv_files:
            print(f"⚠️ FOUND: {len(csv_files)} CSV files in data/ (Polars prefers Parquet)")
            for csv_file in csv_files:
                csv_path = os.path.join(data_dir, csv_file)
                try:
                    os.remove(csv_path)
                    print(f"   ✅ DELETED: {csv_path}")
                    deleted_count += 1
                except Exception as e:
                    print(f"   ❌ FAILED: {csv_path} - {e}")
    
    # Clean models/ directory
    models_dir = "models"
    if os.path.exists(models_dir):
        json_files = [f for f in os.listdir(models_dir) if f.endswith('.json')]
        if json_files:
            print(f"⚠️ FOUND: {len(json_files)} JSON model files in models/ (using LightGBM .txt)")
            for json_file in json_files:
                json_path = os.path.join(models_dir, json_file)
                try:
                    os.remove(json_path)
                    print(f"   ✅ DELETED: {json_path}")
                    deleted_count += 1
                except Exception as e:
                    print(f"   ❌ FAILED: {json_path} - {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 PURGE SUMMARY")
    print("=" * 80)
    print(f"✅ Deleted: {deleted_count} files/artifacts")
    print(f"⏭️ Skipped: {skipped_count} files (not found - already clean)")
    print("\n✅ Legacy code purge COMPLETE")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        purge_legacy_files()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ PURGE FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
