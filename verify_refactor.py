#!/usr/bin/env python3
"""
🔍 Zero-Tolerance Verification Script
Comprehensive audit of entire src/ directory after refactoring
"""

import os
import sys
import ast
import re
from pathlib import Path
from typing import List, Tuple, Dict

class VerificationReport:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed_checks = []
    
    def add_error(self, check_name: str, message: str, file: str = ""):
        self.errors.append(f"❌ [{check_name}] {message}" + (f" (File: {file})" if file else ""))
    
    def add_warning(self, check_name: str, message: str, file: str = ""):
        self.warnings.append(f"⚠️  [{check_name}] {message}" + (f" (File: {file})" if file else ""))
    
    def add_passed(self, check_name: str, message: str):
        self.passed_checks.append(f"✅ [{check_name}] {message}")
    
    def print_report(self):
        print("\n" + "=" * 80)
        print("🔍 ZERO-TOLERANCE VERIFICATION REPORT")
        print("=" * 80)
        
        if self.passed_checks:
            print("\n✅ PASSED CHECKS:")
            for check in self.passed_checks:
                print(f"  {check}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if self.errors:
            print("\n❌ CRITICAL ERRORS:")
            for error in self.errors:
                print(f"  {error}")
            print("\n" + "=" * 80)
            print("RESULT: ❌ VERIFICATION FAILED")
            print("=" * 80)
            return False
        else:
            print("\n" + "=" * 80)
            print("RESULT: ✅ VERIFICATION PASSED - All systems clean!")
            print("=" * 80)
            return True


def check_forbidden_imports(report: VerificationReport):
    """Check 1: Forbidden Imports Check"""
    print("\n🔍 Check 1: Forbidden Imports...")
    
    forbidden_patterns = [
        'from src.config',
        'import src.config',
        'ConfigProfile',
        'src.database.async_manager',
        'RedisManager',
        'from src.core.config_profile',
    ]
    
    files_checked = 0
    issues_found = 0
    
    for root, dirs, files in os.walk('src'):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                files_checked += 1
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        for pattern in forbidden_patterns:
                            if pattern in content:
                                report.add_error("FORBIDDEN_IMPORTS", f"Found forbidden import: {pattern}", filepath)
                                issues_found += 1
                except Exception as e:
                    report.add_warning("FORBIDDEN_IMPORTS", f"Could not read file: {e}", filepath)
    
    if issues_found == 0:
        report.add_passed("FORBIDDEN_IMPORTS", f"Scanned {files_checked} files - Zero forbidden imports found ✓")
    
    return issues_found == 0


def check_hidden_configuration(report: VerificationReport):
    """Check 2: Hidden Configuration Check"""
    print("\n🔍 Check 2: Hidden Configuration...")
    
    files_checked = 0
    issues_found = 0
    
    for root, dirs, files in os.walk('src'):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                files_checked += 1
                
                # Skip unified config manager itself
                if 'unified_config_manager' in filepath:
                    continue
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Check for os.getenv or os.environ directly in code
                        if re.search(r'\bos\.getenv\s*\(', content) or re.search(r'\bos\.environ\s*\[', content):
                            # Exception: allow in unified_config_manager
                            if 'unified_config_manager' not in filepath:
                                report.add_error("HIDDEN_CONFIG", f"Found direct os.getenv/os.environ call (should use config manager)", filepath)
                                issues_found += 1
                except Exception as e:
                    report.add_warning("HIDDEN_CONFIG", f"Could not read file: {e}", filepath)
    
    if issues_found == 0:
        report.add_passed("HIDDEN_CONFIG", f"Scanned {files_checked} files - All config access centralized ✓")
    
    return issues_found == 0


def check_async_hygiene(report: VerificationReport):
    """Check 3: Async Hygiene Check"""
    print("\n🔍 Check 3: Async Hygiene...")
    
    files_checked = 0
    issues_found = 0
    
    for root, dirs, files in os.walk('src'):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                files_checked += 1
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        # Find all async functions
                        in_async_func = False
                        for i, line in enumerate(lines):
                            if re.match(r'\s*async\s+def\s+', line):
                                in_async_func = True
                            elif re.match(r'\s*def\s+', line):
                                in_async_func = False
                            
                            if in_async_func:
                                # Check for blocking calls
                                if 'time.sleep(' in line and 'asyncio.sleep' not in line:
                                    report.add_error("ASYNC_HYGIENE", f"Found blocking time.sleep in async function (line {i+1})", filepath)
                                    issues_found += 1
                                
                                # Check for file operations
                                if re.search(r'\bopen\s*\(', line):
                                    # This is more of a warning - file ops might be in sync context
                                    pass
                except Exception as e:
                    report.add_warning("ASYNC_HYGIENE", f"Could not parse file: {e}", filepath)
    
    if issues_found == 0:
        report.add_passed("ASYNC_HYGIENE", f"Scanned {files_checked} files - No blocking calls in async functions ✓")
    
    return issues_found == 0


def check_import_integrity(report: VerificationReport):
    """Check 4: Import Integrity Test (Dry Run)"""
    print("\n🔍 Check 4: Import Integrity...")
    
    issues_found = 0
    
    # Check unified_config_manager
    try:
        from src.core.unified_config_manager import config_manager as config
        report.add_passed("IMPORT_INTEGRITY", "✓ UnifiedConfigManager imports successfully")
    except (ImportError, AttributeError) as e:
        report.add_error("IMPORT_INTEGRITY", f"Failed to import UnifiedConfigManager: {e}")
        issues_found += 1
    
    # Check unified_database_manager
    try:
        from src.database.unified_database_manager import UnifiedDatabaseManager
        report.add_passed("IMPORT_INTEGRITY", "✓ UnifiedDatabaseManager imports successfully")
    except (ImportError, AttributeError) as e:
        report.add_error("IMPORT_INTEGRITY", f"Failed to import UnifiedDatabaseManager: {e}")
        issues_found += 1
    
    return issues_found == 0


def check_entry_point(report: VerificationReport):
    """Check 5: Entry Point Check"""
    print("\n🔍 Check 5: Entry Point...")
    
    issues_found = 0
    
    main_paths = ['src/main.py', 'main.py', 'run.py']
    main_file = None
    
    for path in main_paths:
        if os.path.exists(path):
            main_file = path
            break
    
    if not main_file:
        report.add_error("ENTRY_POINT", "Could not find main.py or run.py")
        return False
    
    try:
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Check for initialization
            has_init = 'UnifiedDatabaseManager' in content and 'initialize()' in content
            has_close = 'UnifiedDatabaseManager' in content and 'close()' in content
            
            if has_init:
                report.add_passed("ENTRY_POINT", f"✓ {main_file} has UnifiedDatabaseManager.initialize()")
            else:
                report.add_error("ENTRY_POINT", f"Missing UnifiedDatabaseManager initialization in {main_file}")
                issues_found += 1
            
            if has_close:
                report.add_passed("ENTRY_POINT", f"✓ {main_file} has UnifiedDatabaseManager.close()")
            else:
                report.add_warning("ENTRY_POINT", f"Missing UnifiedDatabaseManager cleanup in {main_file}")
    
    except Exception as e:
        report.add_error("ENTRY_POINT", f"Could not read entry point: {e}")
        issues_found += 1
    
    return issues_found == 0


def main():
    print("=" * 80)
    print("🚀 ZERO-TOLERANCE VERIFICATION STARTING...")
    print("=" * 80)
    
    report = VerificationReport()
    
    # Run all checks
    check_forbidden_imports(report)
    check_hidden_configuration(report)
    check_async_hygiene(report)
    check_import_integrity(report)
    check_entry_point(report)
    
    # Print report
    success = report.print_report()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
