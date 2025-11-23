#!/usr/bin/env python3
"""
🧹 PHASE 1: The Final Purge - Delete Obsolete Files
Removes all files NOT in the "Lean Core" whitelist
"""

import os
import shutil
from pathlib import Path

# STRICT ALLOWLIST - Keep ONLY these files
WHITELIST = {
    # Source code files
    "src/main.py",
    "src/config.py",
    "src/data.py",
    "src/brain.py",
    "src/trade.py",
    "src/utils/error_handler.py",
    
    # Project config/docs
    "requirements.txt",
    "README.md",
    ".gitignore",
    ".replit",
    "replit.md",
    ".env.example",
    ".python-version",
    "pyproject.toml",
    
    # Deployment config
    "railway.toml",
    "railway.json",
    "nixpacks.toml",
}

# Directories to keep
KEEP_DIRS = {"src/", "models/", "data/", ".git/"}

# Root-level files to DELETE
DELETE_FILES = [
    "audit_hidden_risks.py",
    "audit_results.json",
    "AUDIT_COMPLETION_REPORT.md",
    "BINANCE_PROTOCOL_AUDIT_REPORT.md",
    "CARPET_AUDIT_COMPLETE.md",
    "check_universe_size.py",
    "CRITICAL_FIXES_SUMMARY.md",
    "CURRENT_MODEL_FEATURES_SUMMARY.txt",
    "DBRE_AUDIT_REPORT.md",
    "debug_universe.py",
    "DEPLOYMENT_CHECKLIST.md",
    "FINAL_CLEANUP_SUMMARY.txt",
    "FINAL_REPOSITORY_CLASSIFICATION_REPORT.md",
    "FINAL_SYSTEM_AUDIT_REPORT.md",
    "HIDDEN_RISKS_AUDIT_REPORT.md",
    "LOGGING_REFACTOR_SUMMARY.md",
    "README_DEPLOYMENT.md",
    "REFACTOR_RECOMMENDATION.txt",
    "REPOSITORY_ADMINISTRATION_COMPLETE.md",
    "REPOSITORY_CLEANUP_FINAL_SUMMARY.md",
    "SESSION_SUMMARY_2025-11-23.md",
    "simulation_results.txt",
    "SYSTEM_AUDIT_REPORT.md",
    "SYSTEM_HEALTH_DASHBOARD.md",
    "SYSTEM_READY_FOR_DEPLOYMENT.txt",
    "TOTAL_REFACTOR_COMPLETE.md",
    "verify_binance_protocol.py",
    ".restart_count",
    ".railway-rebuild-trigger",
]

# src/ files to DELETE (not in whitelist)
SRC_DELETE = [
    "src/__init__.py",
    "src/bus.py",
    "src/dispatch.py",
    "src/feed.py",
    "src/indicators.py",
    "src/market_universe.py",
    "src/models.py",
    "src/reconciliation.py",
    "src/ring_buffer.py",
    "src/core/system_monitor.py",
]


def cleanup_phase_1():
    """Execute Phase 1: Delete obsolete files"""
    
    print("🧹 PHASE 1: THE FINAL PURGE")
    print("=" * 60)
    
    deleted_count = 0
    kept_count = 0
    
    # Delete root-level files
    print("\n📁 Root-level cleanup:")
    for file in DELETE_FILES:
        path = Path(file)
        if path.exists():
            path.unlink()
            print(f"  ❌ Deleted: {file}")
            deleted_count += 1
    
    # Delete src/ files not in whitelist
    print("\n📁 Source code cleanup (src/):")
    for file in SRC_DELETE:
        path = Path(file)
        if path.exists():
            path.unlink()
            print(f"  ❌ Deleted: {file}")
            deleted_count += 1
    
    # Clean empty directories
    print("\n📁 Removing empty directories:")
    for root, dirs, files in os.walk("src", topdown=False):
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            try:
                if not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    print(f"  ❌ Removed empty dir: {dir_path}")
            except:
                pass
    
    # Verify whitelist files still exist
    print("\n📁 Verifying Lean Core files:")
    for file in sorted(WHITELIST):
        path = Path(file)
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"  ✅ Kept: {file} ({size_kb:.1f} KB)")
            kept_count += 1
        elif "models/" in file or "data/" in file:
            pass  # Directories, skip
        else:
            print(f"  ⚠️  Missing: {file}")
    
    print("\n" + "=" * 60)
    print(f"✅ Cleanup complete: {deleted_count} deleted, {kept_count} kept")
    print("=" * 60)


if __name__ == "__main__":
    cleanup_phase_1()
