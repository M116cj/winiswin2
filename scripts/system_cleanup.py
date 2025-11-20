#!/usr/bin/env python3
"""
System Cleanup Script v1.0
Deep Clean and Optimization - Post-Migration Cleanup

This script removes legacy files from the File-based/SQLite era after
the successful migration to PostgreSQL + UnifiedTradeRecorder.

Files to be deleted:
1. src/core/trading_database.py (SQLite implementation)
2. src/managers/trade_recorder.py (JSONL version)
3. src/managers/optimized_trade_recorder.py (async I/O version)
4. src/core/trade_recorder.py (SQLite version)
5. src/managers/enhanced_trade_recorder.py (enhanced version)
6. src/utils/indicators.py (deprecated - replaced by EliteTechnicalEngine)
7. src/utils/core_calculations.py (deprecated - replaced by EliteTechnicalEngine)

Safety:
- Asks for user confirmation before deletion
- Checks if files exist before attempting deletion
- Cleans up empty directories after deletion
- Provides detailed deletion report
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")

def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

def print_info(text: str):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.ENDC}")

def get_project_root() -> Path:
    """Get project root directory (where this script is located)"""
    return Path(__file__).parent.parent

def get_legacy_files() -> List[Tuple[str, str]]:
    """
    Get list of legacy files to delete
    
    Returns:
        List of (file_path, description) tuples
    """
    return [
        ('src/core/trading_database.py', 'SQLite database implementation (~500 lines)'),
        ('src/managers/trade_recorder.py', 'JSONL trade recorder (~800 lines)'),
        ('src/managers/optimized_trade_recorder.py', 'Async I/O trade recorder (~400 lines)'),
        ('src/core/trade_recorder.py', 'SQLite trade recorder (~600 lines)'),
        ('src/managers/enhanced_trade_recorder.py', 'Enhanced trade recorder (~300 lines)'),
        ('src/utils/indicators.py', 'Deprecated indicators (replaced by EliteTechnicalEngine)'),
        ('src/utils/core_calculations.py', 'Deprecated calculations (replaced by EliteTechnicalEngine)'),
    ]

def check_file_exists(file_path: Path) -> Tuple[bool, int]:
    """
    Check if file exists and get its size
    
    Returns:
        (exists, size_in_bytes)
    """
    if file_path.exists():
        return True, file_path.stat().st_size
    return False, 0

def delete_file_safely(file_path: Path) -> bool:
    """
    Delete file with error handling
    
    Returns:
        True if successful, False otherwise
    """
    try:
        file_path.unlink()
        return True
    except Exception as e:
        print_error(f"Failed to delete {file_path}: {e}")
        return False

def clean_empty_directories(directories: List[Path]) -> int:
    """
    Remove empty directories
    
    Returns:
        Number of directories removed
    """
    removed_count = 0
    
    for directory in directories:
        if directory.exists() and directory.is_dir():
            try:
                # Check if directory is empty
                if not any(directory.iterdir()):
                    directory.rmdir()
                    print_success(f"Removed empty directory: {directory}")
                    removed_count += 1
            except Exception as e:
                print_warning(f"Could not remove directory {directory}: {e}")
    
    return removed_count

def main():
    """Main cleanup execution"""
    print_header("🧹 SelfLearningTrader - System Cleanup Script v1.0")
    
    print(f"{Colors.BOLD}Purpose:{Colors.ENDC} Remove legacy files from SQLite/File-based era")
    print(f"{Colors.BOLD}Migration:{Colors.ENDC} PostgreSQL + UnifiedTradeRecorder is now active\n")
    
    # Get project root
    project_root = get_project_root()
    print_info(f"Project root: {project_root}")
    
    # Get legacy files
    legacy_files = get_legacy_files()
    
    # Check which files exist
    print_header("📋 Files Scheduled for Deletion")
    
    existing_files = []
    missing_files = []
    total_size = 0
    
    for file_path, description in legacy_files:
        full_path = project_root / file_path
        exists, size = check_file_exists(full_path)
        
        if exists:
            existing_files.append((full_path, file_path, description, size))
            total_size += size
            print(f"{Colors.CYAN}[EXISTS]{Colors.ENDC} {file_path}")
            print(f"         └─ {description} ({size:,} bytes)")
        else:
            missing_files.append((file_path, description))
            print(f"{Colors.YELLOW}[MISSING]{Colors.ENDC} {file_path}")
            print(f"          └─ {description} (already deleted)")
    
    print(f"\n{Colors.BOLD}Summary:{Colors.ENDC}")
    print(f"  • Files to delete: {len(existing_files)}")
    print(f"  • Already deleted: {len(missing_files)}")
    print(f"  • Total size to reclaim: {total_size:,} bytes ({total_size / 1024:.2f} KB)")
    
    if not existing_files:
        print_success("\n✨ All legacy files already removed! Nothing to do.")
        return 0
    
    # Ask for confirmation
    print_header("⚠️  Confirmation Required")
    print(f"{Colors.RED}{Colors.BOLD}WARNING:{Colors.ENDC} This will permanently delete {len(existing_files)} files!")
    print(f"Make sure you have a backup or can rollback via git if needed.\n")
    
    response = input(f"{Colors.BOLD}Proceed with deletion? (yes/no): {Colors.ENDC}").strip().lower()
    
    if response not in ('yes', 'y'):
        print_warning("Cleanup cancelled by user.")
        return 1
    
    # Execute deletion
    print_header("🗑️  Deleting Files")
    
    deleted_files = []
    failed_files = []
    reclaimed_size = 0
    
    for full_path, file_path, description, size in existing_files:
        print(f"\n{Colors.CYAN}Deleting:{Colors.ENDC} {file_path}")
        
        if delete_file_safely(full_path):
            deleted_files.append((file_path, size))
            reclaimed_size += size
            print_success(f"Deleted successfully ({size:,} bytes freed)")
        else:
            failed_files.append(file_path)
    
    # Clean empty directories
    print_header("📁 Cleaning Empty Directories")
    
    directories_to_check = [
        project_root / 'src' / 'managers',
        project_root / 'src' / 'utils',
        project_root / 'src' / 'core',
    ]
    
    removed_dirs = clean_empty_directories(directories_to_check)
    
    # Final report
    print_header("📊 Cleanup Report")
    
    print(f"{Colors.BOLD}Files Deleted:{Colors.ENDC}")
    for file_path, size in deleted_files:
        print(f"  ✅ {file_path} ({size:,} bytes)")
    
    if failed_files:
        print(f"\n{Colors.BOLD}Failed Deletions:{Colors.ENDC}")
        for file_path in failed_files:
            print(f"  ❌ {file_path}")
    
    print(f"\n{Colors.BOLD}Statistics:{Colors.ENDC}")
    print(f"  • Files deleted: {len(deleted_files)}/{len(existing_files)}")
    print(f"  • Directories removed: {removed_dirs}")
    print(f"  • Space reclaimed: {reclaimed_size:,} bytes ({reclaimed_size / 1024:.2f} KB)")
    print(f"  • Estimated code reduction: ~{sum(size for _, size in deleted_files) / 80:.0f} lines")
    
    if failed_files:
        print_error(f"\n⚠️  {len(failed_files)} file(s) failed to delete. Please review manually.")
        return 1
    else:
        print_success("\n✨ Cleanup completed successfully!")
        print_info("Next steps:")
        print_info("  1. Review OPTIMIZATION_REPORT.md for remaining optimizations")
        print_info("  2. Run tests to ensure system stability")
        print_info("  3. Commit changes: git add -A && git commit -m 'chore: remove legacy files'")
        return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print_warning("\n\nCleanup interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print_error(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
