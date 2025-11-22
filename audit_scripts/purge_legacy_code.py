#!/usr/bin/env python3
"""
🧹 Legacy Code Purger - Remove all files not in the Golden Allowlist
Keeps only the current SMC-Quant Sharded Architecture
"""

import os
import shutil
from pathlib import Path

class LegacyPurger:
    # Golden Allowlist - ONLY these files should remain
    ALLOWLIST = {
        'src/main.py',
        'src/core/unified_config_manager.py',
        'src/core/account_state_cache.py',
        'src/core/cluster_manager.py',
        'src/core/market_universe.py',
        'src/core/smc_engine.py',
        'src/core/risk_manager.py',
        'src/core/data_manager.py',
        'src/core/websocket/unified_feed.py',
        'src/core/websocket/shard_feed.py',
        'src/core/websocket/account_feed.py',
        'src/database/unified_database_manager.py',
        'src/strategies/ict_scalper.py',
        'src/ml/feature_engineer.py',
        'src/ml/trainer.py',
        'src/ml/predictor.py',
        'src/clients/binance_client.py',
        'src/utils/smart_logger.py',
        'src/utils/logger_factory.py',
        'src/utils/railway_logger.py',
        'src/utils/integrity_check.py',
        'requirements.txt',
        'pyproject.toml',
        'README.md',
        'replit.md',
    }
    
    def __init__(self):
        self.deleted_files = []
        self.deleted_dirs = []
        self.kept_files = []
    
    def is_allowed(self, filepath: str) -> bool:
        """Check if file is in allowlist or is __init__.py"""
        # Normalize path
        filepath = filepath.replace('./src/', 'src/').replace('./', '')
        
        # Allow __init__.py files
        if filepath.endswith('__init__.py'):
            return True
        
        # Check allowlist
        for allowed in self.ALLOWLIST:
            if filepath == allowed or filepath.endswith(allowed):
                return True
        
        return False
    
    def purge_legacy_code(self):
        """Walk through src/ and delete files not in allowlist"""
        src_dir = Path('src')
        
        if not src_dir.exists():
            print("⚠️ src/ directory not found")
            return
        
        # Walk and collect files to delete
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                filepath = os.path.join(root, file)
                rel_path = filepath.replace('./src/', 'src/').replace('./', '')
                
                if not self.is_allowed(rel_path):
                    try:
                        os.remove(filepath)
                        self.deleted_files.append(rel_path)
                        print(f"🗑️ Deleted: {rel_path}")
                    except Exception as e:
                        print(f"❌ Failed to delete {rel_path}: {e}")
                else:
                    self.kept_files.append(rel_path)
    
    def clean_empty_dirs(self):
        """Remove empty directories"""
        src_dir = Path('src')
        
        for root, dirs, files in os.walk(src_dir, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                
                # Check if directory is empty
                if not os.listdir(dir_path):
                    try:
                        os.rmdir(dir_path)
                        rel_path = dir_path.replace('./src/', 'src/').replace('./', '')
                        self.deleted_dirs.append(rel_path)
                        print(f"🗑️ Removed dir: {rel_path}")
                    except Exception as e:
                        pass  # Directory might have been removed already
    
    def print_report(self):
        """Print purge report"""
        print("\n" + "="*80)
        print("🧹 LEGACY CODE PURGE REPORT")
        print("="*80)
        
        if self.deleted_files:
            print(f"\n🗑️ DELETED FILES ({len(self.deleted_files)}):")
            for f in sorted(self.deleted_files)[:20]:  # Show first 20
                print(f"   - {f}")
            if len(self.deleted_files) > 20:
                print(f"   ... and {len(self.deleted_files) - 20} more")
        
        if self.deleted_dirs:
            print(f"\n🗑️ REMOVED DIRECTORIES ({len(self.deleted_dirs)}):")
            for d in sorted(self.deleted_dirs)[:10]:  # Show first 10
                print(f"   - {d}")
            if len(self.deleted_dirs) > 10:
                print(f"   ... and {len(self.deleted_dirs) - 10} more")
        
        print(f"\n✅ KEPT FILES ({len(self.kept_files)}):")
        for f in sorted(self.kept_files):
            print(f"   - {f}")
        
        print("\n" + "="*80)
        print(f"Summary: Deleted {len(self.deleted_files)} files, {len(self.deleted_dirs)} dirs")
        print(f"Remaining: {len(self.kept_files)} core architecture files")
        print("="*80)

if __name__ == "__main__":
    purger = LegacyPurger()
    
    print("🧹 Starting legacy code purge...\n")
    purger.purge_legacy_code()
    print("\nCleaning empty directories...")
    purger.clean_empty_dirs()
    purger.print_report()
