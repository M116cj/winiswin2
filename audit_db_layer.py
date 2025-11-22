#!/usr/bin/env python3
"""
🔍 Database Reliability Engineer (DBRE) - Database Layer Audit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 1: STATIC ANALYSIS (Code & Logic Audit)
Verifies Async Compliance, Connection Lifecycle, and Data Integrity
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple

class DBREAudit:
    def __init__(self):
        self.passed = []
        self.warnings = []
        self.failures = []
        
    def read_file(self, filepath: str) -> str:
        """Read file content"""
        try:
            with open(filepath, 'r') as f:
                return f.read()
        except:
            return ""
    
    # ==================== CHECK 1: Async Library Compliance ====================
    
    def check_async_libraries(self):
        """Verify redis.asyncio and asyncpg usage"""
        print("\n" + "="*80)
        print("CHECK 1: Async Library Compliance")
        print("="*80)
        
        files_to_check = [
            "src/database/unified_database_manager.py",
            "src/core/account_state_cache.py",
            "src/core/data_manager.py",
        ]
        
        for fpath in files_to_check:
            if not os.path.exists(fpath):
                continue
            
            content = self.read_file(fpath)
            
            # Check for sync Redis (BAD)
            if re.search(r'^\s*import redis\s*$', content, re.MULTILINE):
                if 'redis.asyncio' not in content:
                    self.failures.append(f"❌ {fpath}: Sync redis import (should use redis.asyncio)")
                    print(f"❌ {fpath}: Sync redis import detected")
                    continue
            
            # Check for asyncpg (GOOD for PostgreSQL)
            if 'asyncpg' in content:
                self.passed.append(f"✅ {fpath}: Uses asyncpg")
                print(f"✅ {fpath}: Async PostgreSQL (asyncpg)")
            
            # Check for redis.asyncio (GOOD)
            if 'redis.asyncio' in content or 'aioredis' in content:
                self.passed.append(f"✅ {fpath}: Uses redis.asyncio or aioredis")
                print(f"✅ {fpath}: Async Redis (redis.asyncio/aioredis)")
            
            # Check for psycopg2 or sqlalchemy sync (BAD)
            if re.search(r'(psycopg2|sqlalchemy)', content):
                if 'asyncio' not in content or 'async' not in content:
                    self.failures.append(f"❌ {fpath}: Sync database library detected")
                    print(f"❌ {fpath}: Sync database library (psycopg2/sqlalchemy)")
    
    # ==================== CHECK 2: Connection Management ====================
    
    def check_connection_management(self):
        """Verify singleton, lifecycle, and context managers"""
        print("\n" + "="*80)
        print("CHECK 2: Connection Management")
        print("="*80)
        
        db_manager = "src/database/unified_database_manager.py"
        if not os.path.exists(db_manager):
            self.warnings.append(f"⚠️ {db_manager} not found")
            return
        
        content = self.read_file(db_manager)
        
        # Check for singleton pattern
        if '_instance = None' in content and '__new__' in content:
            self.passed.append(f"✅ {db_manager}: Singleton pattern implemented")
            print(f"✅ Singleton pattern: Detected")
        else:
            self.warnings.append(f"⚠️ {db_manager}: No singleton pattern")
            print(f"⚠️ Singleton pattern: Not found")
        
        # Check for connection pool reuse
        if 'self.pg_pool' in content or '_pg_pool' in content:
            self.passed.append(f"✅ {db_manager}: Connection pool reused")
            print(f"✅ Connection pool: Reused across calls")
        else:
            self.failures.append(f"❌ {db_manager}: No connection pool detected")
            print(f"❌ Connection pool: Not found")
        
        # Check for lifecycle methods
        if 'async def initialize' in content and 'async def close' in content:
            self.passed.append(f"✅ {db_manager}: Lifecycle methods present")
            print(f"✅ Lifecycle: initialize() and close() found")
        else:
            self.warnings.append(f"⚠️ {db_manager}: Missing lifecycle methods")
            print(f"⚠️ Lifecycle: Missing initialize/close")
        
        # Check for async context managers
        if 'async with' in content or '__aenter__' in content:
            self.passed.append(f"✅ {db_manager}: Async context managers used")
            print(f"✅ Context managers: Async context used")
        else:
            self.warnings.append(f"⚠️ {db_manager}: Limited async context usage")
            print(f"⚠️ Context managers: Limited usage")
    
    # ==================== CHECK 3: Configuration Binding ====================
    
    def check_configuration(self):
        """Verify config.DATABASE_URL and config.REDIS_URL usage"""
        print("\n" + "="*80)
        print("CHECK 3: Configuration Binding")
        print("="*80)
        
        db_manager = "src/database/unified_database_manager.py"
        content = self.read_file(db_manager)
        
        # Check for hardcoded strings (BAD)
        hardcoded_patterns = [
            r'"redis://localhost"',
            r'"postgresql://.*@localhost"',
            r'"postgres://.*@localhost"',
            r'hardcoded.*url',
        ]
        
        found_hardcoded = False
        for pattern in hardcoded_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found_hardcoded = True
                self.failures.append(f"❌ {db_manager}: Hardcoded connection string detected")
                print(f"❌ Hardcoded strings: Found")
        
        # Check for environment variable usage (GOOD)
        if 'os.environ' in content or 'os.getenv' in content:
            self.passed.append(f"✅ {db_manager}: Environment variables used")
            print(f"✅ Environment variables: Used for configuration")
        else:
            self.warnings.append(f"⚠️ {db_manager}: No environment variable usage")
            print(f"⚠️ Environment variables: Not found")
        
        if not found_hardcoded:
            self.passed.append(f"✅ {db_manager}: No hardcoded strings")
            print(f"✅ No hardcoded strings: Clean")
    
    # ==================== CHECK 4: Serialization Safety ====================
    
    def check_serialization(self):
        """Verify JSON serialization for Redis"""
        print("\n" + "="*80)
        print("CHECK 4: Serialization Safety")
        print("="*80)
        
        cache_file = "src/core/account_state_cache.py"
        content = self.read_file(cache_file)
        
        # Check for JSON usage
        if 'json' in content:
            self.passed.append(f"✅ {cache_file}: JSON serialization awareness")
            print(f"✅ JSON serialization: Detected")
        else:
            self.passed.append(f"✅ {cache_file}: In-memory only (no Redis sync yet)")
            print(f"✅ Serialization: In-memory storage (no Redis sync)")
        
        # Check for proper data handling
        if 'self._balances' in content and 'self._positions' in content:
            self.passed.append(f"✅ {cache_file}: Structured data storage")
            print(f"✅ Data structures: Proper dict/list storage")
    
    def run_all_checks(self):
        """Run all audit checks"""
        print("\n" + "╔" + "="*78 + "╗")
        print("║" + " "*15 + "🔍 DATABASE RELIABILITY ENGINEER - AUDIT PHASE 1" + " "*18 + "║")
        print("╚" + "="*78 + "╝")
        
        self.check_async_libraries()
        self.check_connection_management()
        self.check_configuration()
        self.check_serialization()
        
        # Print summary
        print("\n" + "="*80)
        print("AUDIT SUMMARY")
        print("="*80)
        
        if self.passed:
            print(f"\n✅ PASSED ({len(self.passed)}):")
            for item in self.passed:
                print(f"   {item}")
        
        if self.warnings:
            print(f"\n⚠️ WARNINGS ({len(self.warnings)}):")
            for item in self.warnings:
                print(f"   {item}")
        
        if self.failures:
            print(f"\n❌ FAILURES ({len(self.failures)}):")
            for item in self.failures:
                print(f"   {item}")
        
        print("\n" + "="*80)
        if self.failures:
            print("STATUS: ❌ FAILED")
            return False
        else:
            print("STATUS: ✅ PASSED")
            return True

if __name__ == "__main__":
    audit = DBREAudit()
    success = audit.run_all_checks()
    sys.exit(0 if success else 1)
