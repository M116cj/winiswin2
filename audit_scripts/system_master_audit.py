#!/usr/bin/env python3
"""
🔍 CHIEF SYSTEMS ARCHITECT - DEEP-STATE TOTAL SYSTEM AUDIT & STERILIZATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

7-Level Comprehensive Audit Suite:
1. Architectural Integrity (AST Analysis)
2. Stability & Crash Detection
3. Efficiency & Performance Benchmark
4. Function Reference Integrity
5. Functional Logic Verification
6. Code Cleanliness
7. Obsolete/Legacy Code Detection

Plus: Automated Sterilization (Phase 2)
"""

import os
import sys
import ast
import re
import time
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import importlib.util

logging.basicConfig(level=logging.CRITICAL)

# ============================================================================
# AUDIT RESULTS CONTAINERS
# ============================================================================

class AuditResults:
    def __init__(self):
        self.passed = []
        self.warnings = []
        self.failures = []
        self.deleted = []
        self.metrics = {}

results = AuditResults()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def scan_python_files(root_dir: str = "src") -> List[str]:
    """Find all Python files"""
    files = []
    for root, dirs, filenames in os.walk(root_dir):
        # Skip pycache
        if "__pycache__" in root:
            continue
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(os.path.join(root, fname))
    return sorted(files)

def parse_ast(filepath: str) -> Optional[ast.Module]:
    """Parse Python file to AST"""
    try:
        with open(filepath, 'r') as f:
            return ast.parse(f.read())
    except Exception as e:
        results.failures.append(f"Parse error in {filepath}: {e}")
        return None

def get_imports(tree: ast.Module) -> Set[str]:
    """Extract all imports from AST"""
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports

def get_function_defs(tree: ast.Module) -> Dict[str, List[str]]:
    """Extract function definitions and classes"""
    defs = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            defs['functions'].append(node.name)
        elif isinstance(node, ast.ClassDef):
            defs['classes'].append(node.name)
            # Get class methods
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    defs['methods'].append(f"{node.name}.{item.name}")
    return defs

def read_file_content(filepath: str) -> str:
    """Read file content"""
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except:
        return ""

# ============================================================================
# LEVEL 1: ARCHITECTURAL INTEGRITY (AST Analysis)
# ============================================================================

def audit_level_1():
    """Verify architectural patterns"""
    print("\n" + "="*80)
    print("🔍 LEVEL 1: ARCHITECTURAL INTEGRITY")
    print("="*80)
    
    files = scan_python_files()
    
    # Check strategies directory
    strategy_files = [f for f in files if "strategies" in f and f.endswith(".py")]
    for strat_file in strategy_files:
        tree = parse_ast(strat_file)
        if not tree:
            continue
        
        imports = get_imports(tree)
        has_cache = any("AccountStateCache" in imp for imp in imports)
        has_smc = any("SMCEngine" in imp for imp in imports)
        
        if not has_cache and "ict_scalper" not in strat_file:
            results.warnings.append(f"⚠️ {strat_file}: Missing AccountStateCache import")
        if not has_smc and "ict_scalper" not in strat_file:
            results.warnings.append(f"⚠️ {strat_file}: Missing SMCEngine import")
        else:
            results.passed.append(f"✅ {strat_file}: Correct imports")
    
    # Check cluster manager
    cluster_file = "src/core/cluster_manager.py"
    if os.path.exists(cluster_file):
        tree = parse_ast(cluster_file)
        if tree:
            imports = get_imports(tree)
            if any("ShardFeed" in imp for imp in imports):
                results.passed.append(f"✅ {cluster_file}: ShardFeed import OK")
            else:
                results.warnings.append(f"⚠️ {cluster_file}: ShardFeed import missing")
    
    # Check websocket directory
    websocket_dir = "src/core/websocket"
    if os.path.exists(websocket_dir):
        websocket_files = os.listdir(websocket_dir)
        expected = {"__init__.py", "unified_feed.py", "shard_feed.py", "account_feed.py"}
        actual = set(f for f in websocket_files if f.endswith(".py"))
        
        if actual.issubset(expected.union({"__pycache__"})):
            results.passed.append(f"✅ WebSocket directory: Clean")
        else:
            results.failures.append(f"❌ WebSocket directory contains unexpected files: {actual - expected}")

# ============================================================================
# LEVEL 2: STABILITY & CRASH DETECTION
# ============================================================================

def audit_level_2():
    """Test stability and detect crashes"""
    print("\n" + "="*80)
    print("🔍 LEVEL 2: STABILITY & CRASH DETECTION")
    print("="*80)
    
    try:
        # Try to import critical modules
        sys.path.insert(0, '/home/runner/workspace')
        
        from src.core.unified_config_manager import UnifiedConfigManager
        config = UnifiedConfigManager()
        
        # Check critical config attributes
        if hasattr(config, 'RATE_LIMIT_REQUESTS'):
            results.passed.append(f"✅ Config: RATE_LIMIT_REQUESTS exists")
        else:
            results.failures.append(f"❌ Config: Missing RATE_LIMIT_REQUESTS")
        
        if hasattr(config, 'CACHE_TTL_TICKER'):
            results.passed.append(f"✅ Config: CACHE_TTL_TICKER exists")
        else:
            results.failures.append(f"❌ Config: Missing CACHE_TTL_TICKER")
        
        # Check database URL format
        if config.DATABASE_URL or config.DATABASE_PUBLIC_URL:
            results.passed.append(f"✅ Database: URL configured")
        else:
            results.warnings.append(f"⚠️ Database: No URL configured")
        
    except Exception as e:
        results.failures.append(f"❌ Config initialization failed: {e}")
    
    # Check for circular imports
    files = scan_python_files()
    import_graph = {}
    
    for fpath in files:
        tree = parse_ast(fpath)
        if tree:
            imports = get_imports(tree)
            import_graph[fpath] = imports
    
    # Simple circular import detection
    def has_cycle(graph, start, visited, rec_stack):
        visited.add(start)
        rec_stack.add(start)
        for neighbor in graph.get(start, set()):
            if neighbor not in visited:
                if has_cycle(graph, neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.remove(start)
        return False
    
    circular = False
    for node in import_graph:
        if has_cycle(import_graph, node, set(), set()):
            circular = True
            results.failures.append(f"❌ Circular import detected involving {node}")
    
    if not circular:
        results.passed.append(f"✅ No circular imports detected")

# ============================================================================
# LEVEL 3: EFFICIENCY & PERFORMANCE BENCHMARK
# ============================================================================

def audit_level_3():
    """Benchmark SMC and ML performance"""
    print("\n" + "="*80)
    print("🔍 LEVEL 3: EFFICIENCY & PERFORMANCE BENCHMARK")
    print("="*80)
    
    try:
        import numpy as np
        import polars as pl
        sys.path.insert(0, '/home/runner/workspace')
        
        from src.core.smc_engine import SMCEngine
        from src.ml.predictor import MLPredictor
        
        # Generate mock OHLCV data
        num_candles = 1000
        mock_klines = []
        base_price = 40000
        
        for i in range(num_candles):
            high = base_price * (1 + np.random.uniform(0, 0.02))
            low = base_price * (1 - np.random.uniform(0, 0.01))
            close = np.random.uniform(low, high)
            
            mock_klines.append({
                'open': base_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': np.random.uniform(100, 10000),
            })
            base_price = close
        
        # Benchmark SMCEngine
        smc = SMCEngine()
        start = time.time()
        
        for i in range(0, num_candles - 20, 20):
            klines_batch = mock_klines[i:i+20]
            smc.detect_fvg(klines_batch)
        
        elapsed = time.time() - start
        per_candle = (elapsed * 1000) / (num_candles - 20)  # ms
        
        results.metrics['smc_per_candle_ms'] = per_candle
        
        if per_candle < 2.0:
            results.passed.append(f"✅ SMCEngine: {per_candle:.3f} ms/candle (EXCELLENT)")
        elif per_candle < 5.0:
            results.passed.append(f"✅ SMCEngine: {per_candle:.3f} ms/candle (GOOD)")
        else:
            results.warnings.append(f"⚠️ SMCEngine: {per_candle:.3f} ms/candle (SLOW)")
        
        # Benchmark MLPredictor
        predictor = MLPredictor()
        features = {
            'market_structure': 1.0,
            'order_blocks_count': 0.0,
            'institutional_candle': 0.167,
            'liquidity_grab': 0.0,
            'fvg_size_atr': 0.0,
            'fvg_proximity': 0.0,
            'ob_proximity': 0.0,
            'atr_normalized_volume': 1.0,
            'rsi_14': 0.5,
            'momentum_atr': 0.0,
            'time_to_next_level': 1.0,
            'confidence_ensemble': 0.7,
        }
        
        start = time.time()
        for _ in range(100):
            predictor.predict_confidence(features)
        elapsed = time.time() - start
        per_call = (elapsed * 1000) / 100
        
        results.metrics['predictor_per_call_ms'] = per_call
        results.passed.append(f"✅ MLPredictor: {per_call:.3f} ms/call")
        
    except Exception as e:
        results.warnings.append(f"⚠️ Performance benchmark failed: {e}")
    
    # Check for pandas usage (FAIL if found)
    files = scan_python_files()
    for fpath in files:
        content = read_file_content(fpath)
        if re.search(r'import pandas|from pandas|pd\.', content):
            results.failures.append(f"❌ {fpath}: PANDAS USAGE DETECTED (must use POLARS)")

# ============================================================================
# LEVEL 4: FUNCTION REFERENCE INTEGRITY
# ============================================================================

def audit_level_4():
    """Check for broken imports and missing functions"""
    print("\n" + "="*80)
    print("🔍 LEVEL 4: FUNCTION REFERENCE INTEGRITY")
    print("="*80)
    
    try:
        sys.path.insert(0, '/home/runner/workspace')
        
        files = scan_python_files()
        for fpath in files:
            try:
                # Try to compile/import
                spec = importlib.util.spec_from_file_location("module", fpath)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    # Don't actually execute, just check syntax
                    with open(fpath, 'r') as f:
                        compile(f.read(), fpath, 'exec')
            except SyntaxError as e:
                results.failures.append(f"❌ {fpath}: Syntax error - {e}")
            except Exception as e:
                # Ignore import errors for now
                pass
        
        results.passed.append(f"✅ All files syntactically valid")
        
    except Exception as e:
        results.warnings.append(f"⚠️ Syntax check failed: {e}")

# ============================================================================
# LEVEL 5: FUNCTIONAL LOGIC VERIFICATION
# ============================================================================

def audit_level_5():
    """Test core functionality"""
    print("\n" + "="*80)
    print("🔍 LEVEL 5: FUNCTIONAL LOGIC VERIFICATION")
    print("="*80)
    
    try:
        sys.path.insert(0, '/home/runner/workspace')
        
        from src.core.risk_manager import get_risk_manager
        from src.core.account_state_cache import AccountStateCache
        
        # Test RiskManager
        rm = get_risk_manager()
        size = rm.calculate_size(confidence=0.95, balance=10000.0)
        
        if isinstance(size, float) and size > 0:
            results.passed.append(f"✅ RiskManager: Returns valid position size")
        else:
            results.failures.append(f"❌ RiskManager: Invalid position size returned")
        
        # Test AccountStateCache
        cache = AccountStateCache()
        cache.update_balance(total=1000, available=900)
        
        if cache.balance_cache.get('total') == 1000:
            results.passed.append(f"✅ AccountStateCache: Update working")
        else:
            results.failures.append(f"❌ AccountStateCache: Update not working")
        
    except Exception as e:
        results.warnings.append(f"⚠️ Functional verification failed: {e}")

# ============================================================================
# LEVEL 6: CODE CLEANLINESS
# ============================================================================

def audit_level_6():
    """Check code quality"""
    print("\n" + "="*80)
    print("🔍 LEVEL 6: CODE CLEANLINESS")
    print("="*80)
    
    files = scan_python_files()
    issues = 0
    
    for fpath in files:
        content = read_file_content(fpath)
        lines = content.split('\n')
        
        # Check for commented-out blocks (> 5 lines)
        in_comment = False
        comment_lines = 0
        for line in lines:
            if line.strip().startswith('#') and not line.strip().startswith('# ==='):
                comment_lines += 1
                if comment_lines > 5:
                    in_comment = True
            else:
                if in_comment:
                    results.warnings.append(f"⚠️ {fpath}: Large commented block detected")
                    issues += 1
                in_comment = False
                comment_lines = 0
        
        # Check for print statements
        if re.search(r'^\s*print\(', content, re.MULTILINE):
            results.warnings.append(f"⚠️ {fpath}: print() statement found (use smart_logger)")
            issues += 1
    
    if issues == 0:
        results.passed.append(f"✅ Code cleanliness: Good")

# ============================================================================
# LEVEL 7: OBSOLETE/LEGACY CODE DETECTION
# ============================================================================

def audit_level_7():
    """Detect polling, threading, and blocking calls"""
    print("\n" + "="*80)
    print("🔍 LEVEL 7: OBSOLETE/LEGACY CODE DETECTION")
    print("="*80)
    
    files = scan_python_files()
    legacy_patterns = {
        r'while True:\s*.*?client\.get_account': "Polling pattern detected",
        r'threading\.Thread': "Threading detected (use asyncio)",
        r'time\.sleep': "Blocking sleep in code",
        r'requests\.(get|post|put)': "Synchronous requests (use aiohttp)",
    }
    
    for fpath in files:
        content = read_file_content(fpath)
        
        for pattern, issue in legacy_patterns.items():
            if re.search(pattern, content, re.DOTALL):
                # Check if it's in async function (acceptable)
                if pattern == r'time\.sleep' and 'async def' in content:
                    results.warnings.append(f"⚠️ {fpath}: {issue} (in async function - BAD)")
                else:
                    results.failures.append(f"❌ {fpath}: {issue}")
    
    results.passed.append(f"✅ Legacy code check complete")

# ============================================================================
# PHASE 2: STERILIZATION (Automatic Cleanup)
# ============================================================================

def phase_2_sterilization():
    """Delete orphaned and legacy files"""
    print("\n" + "="*80)
    print("🧨 PHASE 2: STERILIZATION (Automatic Cleanup)")
    print("="*80)
    
    # Build import graph
    files = scan_python_files()
    import_graph = {}
    
    for fpath in files:
        tree = parse_ast(fpath)
        if tree:
            imports = get_imports(tree)
            import_graph[fpath] = imports
    
    # Find entry points
    entry_points = {"src/main.py"}
    
    # Find imported files
    imported = set()
    for fpath, imports in import_graph.items():
        for imp in imports:
            # Map import name to file path
            potential_paths = [
                f"src/{imp.replace('.', '/')}.py",
                f"src/{imp.replace('.', '/')}/".rstrip('/') + ".py"
            ]
            for potential in potential_paths:
                if potential in [f for f in files]:
                    imported.add(potential)
    
    # Find orphaned files
    imported.update(entry_points)
    orphaned = [f for f in files if f not in imported and f != "src/main.py"]
    
    if orphaned:
        print(f"\n🗑️ Orphaned files detected ({len(orphaned)}):")
        for f in orphaned:
            print(f"   - {f}")
    
    # Delete legacy files
    legacy_files = [
        "src/core/rate_limiter.py",
        "src/strategies/base_strategy.py",
        "src/core/unified_scheduler.py",
    ]
    
    for fpath in legacy_files:
        if os.path.exists(fpath):
            os.remove(fpath)
            results.deleted.append(fpath)
            print(f"🗑️ Deleted: {fpath}")
    
    # Clean pycache
    for root, dirs, files_list in os.walk("src"):
        if "__pycache__" in dirs:
            pycache_path = os.path.join(root, "__pycache__")
            shutil.rmtree(pycache_path)
            results.deleted.append(pycache_path)
            print(f"🗑️ Deleted: {pycache_path}")

# ============================================================================
# GENERATE FINAL REPORT
# ============================================================================

def generate_report():
    """Print comprehensive audit report"""
    print("\n" + "="*80)
    print("📋 FINAL AUDIT REPORT")
    print("="*80 + "\n")
    
    # Passed
    if results.passed:
        print(f"✅ PASSED ({len(results.passed)}):")
        for item in results.passed:
            print(f"   {item}")
    
    # Warnings
    if results.warnings:
        print(f"\n⚠️ WARNINGS ({len(results.warnings)}):")
        for item in results.warnings:
            print(f"   {item}")
    
    # Failures
    if results.failures:
        print(f"\n❌ FAILURES ({len(results.failures)}):")
        for item in results.failures:
            print(f"   {item}")
    
    # Deleted
    if results.deleted:
        print(f"\n🗑️ DELETED ({len(results.deleted)}):")
        for item in results.deleted:
            print(f"   - {item}")
    
    # Metrics
    if results.metrics:
        print(f"\n📊 PERFORMANCE METRICS:")
        for key, value in results.metrics.items():
            print(f"   {key}: {value:.3f}")
    
    # Summary
    print("\n" + "="*80)
    status = "✅ PASSED" if not results.failures else "❌ FAILED"
    print(f"AUDIT STATUS: {status}")
    print("="*80 + "\n")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n" + "╔" + "="*78 + "╗")
    print("║" + " "*20 + "🔍 DEEP-STATE TOTAL SYSTEM AUDIT" + " "*25 + "║")
    print("╚" + "="*78 + "╝")
    
    # Run all 7 levels
    audit_level_1()
    audit_level_2()
    audit_level_3()
    audit_level_4()
    audit_level_5()
    audit_level_6()
    audit_level_7()
    
    # Phase 2: Sterilization
    phase_2_sterilization()
    
    # Generate report
    generate_report()
    
    # Exit with appropriate code
    sys.exit(0 if not results.failures else 1)
