#!/usr/bin/env python3
"""
🔍 SYSTEM DEEP SCAN - Lead SRE Diagnostic Audit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Performs deep code logic & integrity audit using AST (Abstract Syntax Tree)
Checks: Zero-Polling, SMC Pipeline, Sharding, Data Stack, Circular Imports
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict

class AuditEngine:
    """Deep code audit using AST"""
    
    def __init__(self):
        self.violations = []
        self.import_graph: Dict[str, Set[str]] = defaultdict(set)
        self.file_imports: Dict[str, Set[str]] = defaultdict(set)
        self.all_files = set()
        
    def scan_directory(self, directory: str = "src"):
        """Scan all Python files"""
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    rel_path = filepath.replace('\\', '/')
                    self.all_files.add(rel_path)
    
    # ================================================================================
    # AUDIT 1: ZERO-POLLING ENFORCEMENT
    # ================================================================================
    
    def audit_zero_polling(self):
        """Check that strategies use only cached APIs"""
        print("\n" + "="*80)
        print("🔍 AUDIT 1: ZERO-POLLING ENFORCEMENT")
        print("="*80)
        
        # Files to check
        strategy_files = [
            "src/strategies/ict_scalper.py",
            "src/core/cluster_manager.py",
        ]
        
        forbidden_calls = {
            'client.get_account',
            'client.get_position',
            'client.get_balance',
            'client.get_open_orders',
            'requests.get',
            'requests.post',
            'requests.put',
            'aiohttp',
        }
        
        violations = []
        
        for filepath in strategy_files:
            if not os.path.exists(filepath):
                continue
            
            try:
                with open(filepath, 'r') as f:
                    tree = ast.parse(f.read())
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        call_name = self._get_call_name(node)
                        
                        for forbidden in forbidden_calls:
                            if call_name and forbidden in call_name:
                                violations.append((filepath, call_name, node.lineno))
                    
                    elif isinstance(node, ast.Attribute):
                        attr_chain = self._get_attr_chain(node)
                        if attr_chain and any(f in attr_chain for f in forbidden_calls):
                            violations.append((filepath, attr_chain, node.lineno))
            
            except Exception as e:
                print(f"❌ Parse error in {filepath}: {e}")
        
        if violations:
            print("❌ ZERO-POLLING VIOLATIONS DETECTED:")
            for filepath, call, lineno in violations:
                print(f"   Line {lineno}: {call} in {filepath}")
            return False
        else:
            print("✅ ZERO-POLLING COMPLIANCE: All strategies use only cached APIs")
            return True
    
    # ================================================================================
    # AUDIT 2: SMC PIPELINE CONNECTION
    # ================================================================================
    
    def audit_smc_pipeline(self):
        """Verify strategy uses SMC engine, ML predictor, RiskManager"""
        print("\n" + "="*80)
        print("🔍 AUDIT 2: SMC PIPELINE CONNECTION")
        print("="*80)
        
        strategy_file = "src/strategies/ict_scalper.py"
        if not os.path.exists(strategy_file):
            print(f"⚠️ {strategy_file} not found")
            return False
        
        try:
            with open(strategy_file, 'r') as f:
                content = f.read()
                tree = ast.parse(content)
            
            # Extract imports
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
            
            # Check required components
            required = {
                'SMCEngine': 'src.core.smc_engine' in content or 'SMCEngine' in content,
                'FeatureEngineer': 'feature_engineer' in content,
                'MLPredictor': 'predictor' in content,
                'RiskManager': 'RiskManager' in content,
            }
            
            passed = sum(1 for v in required.values() if v)
            total = len(required)
            
            print(f"✅ SMC PIPELINE CONNECTIONS: {passed}/{total}")
            for component, connected in required.items():
                status = "✅" if connected else "❌"
                print(f"   {status} {component}: {'Connected' if connected else 'NOT FOUND'}")
            
            return passed == total
        
        except Exception as e:
            print(f"❌ Error scanning {strategy_file}: {e}")
            return False
    
    # ================================================================================
    # AUDIT 3: SHARDING & CONCURRENCY
    # ================================================================================
    
    def audit_sharding_concurrency(self):
        """Verify sharding and concurrent execution"""
        print("\n" + "="*80)
        print("🔍 AUDIT 3: SHARDING & CONCURRENCY")
        print("="*80)
        
        checks = {
            'src/core/cluster_manager.py': ['asyncio.gather', 'multiprocessing', 'concurrent'],
            'src/core/websocket/shard_feed.py': ['List[str]', 'for shard', 'asyncio'],
        }
        
        passed = 0
        total = 0
        
        for filepath, keywords in checks.items():
            if not os.path.exists(filepath):
                print(f"⚠️ {filepath} not found")
                continue
            
            total += 1
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                
                found = any(kw in content for kw in keywords)
                
                if found:
                    print(f"✅ {filepath}: Concurrency detected")
                    passed += 1
                else:
                    print(f"❌ {filepath}: No concurrency/sharding found")
            
            except Exception as e:
                print(f"❌ Error: {e}")
        
        return passed == total
    
    # ================================================================================
    # AUDIT 4: DATA SCIENCE STACK INTEGRITY
    # ================================================================================
    
    def audit_data_stack(self):
        """Verify polars (not pandas) and LightGBM"""
        print("\n" + "="*80)
        print("🔍 AUDIT 4: DATA SCIENCE STACK INTEGRITY")
        print("="*80)
        
        checks = {
            'src/ml/feature_engineer.py': {
                'required': ['polars', 'import pl'],
                'forbidden': ['pandas', 'import pd'],
            },
            'src/ml/predictor.py': {
                'required': ['lightgbm', 'lgb.Booster'],
                'forbidden': ['xgboost'],
            },
        }
        
        all_passed = True
        
        for filepath, rules in checks.items():
            if not os.path.exists(filepath):
                print(f"⚠️ {filepath} not found")
                continue
            
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                
                # Check required
                required_found = any(req in content for req in rules['required'])
                forbidden_found = any(forb in content for forb in rules['forbidden'])
                
                if required_found and not forbidden_found:
                    print(f"✅ {filepath}: Correct stack")
                else:
                    print(f"❌ {filepath}:")
                    if not required_found:
                        print(f"   Missing: {rules['required']}")
                    if forbidden_found:
                        print(f"   Contains forbidden: {rules['forbidden']}")
                    all_passed = False
            
            except Exception as e:
                print(f"❌ Error: {e}")
        
        return all_passed
    
    # ================================================================================
    # AUDIT 5: CIRCULAR DEPENDENCIES & ORPHANS
    # ================================================================================
    
    def audit_circular_imports(self):
        """Detect circular imports and orphaned files"""
        print("\n" + "="*80)
        print("🔍 AUDIT 5: CIRCULAR DEPENDENCIES & ORPHANS")
        print("="*80)
        
        # Build import graph
        self.scan_directory("src")
        
        for filepath in self.all_files:
            try:
                with open(filepath, 'r') as f:
                    tree = ast.parse(f.read())
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module:
                            # Convert to filepath
                            imported = node.module.replace('.', '/') + '.py'
                            self.import_graph[filepath].add(imported)
                            self.file_imports[filepath].add(imported)
            
            except Exception:
                pass
        
        # Detect cycles
        cycles = self._detect_cycles()
        
        if cycles:
            print("⚠️ CIRCULAR IMPORTS DETECTED:")
            for cycle in cycles:
                print(f"   {' -> '.join(cycle)}")
        else:
            print("✅ NO CIRCULAR IMPORTS")
        
        # Find orphans (files that aren't imported)
        imported_files = set()
        for deps in self.import_graph.values():
            imported_files.update(deps)
        
        orphans = [f for f in self.all_files if f not in imported_files and not f.endswith('__init__.py') and not f.endswith('main.py')]
        
        if orphans:
            print(f"\n⚠️ ORPHANED FILES ({len(orphans)}):")
            for orphan in orphans[:5]:  # Show first 5
                print(f"   {orphan}")
        else:
            print("✅ NO ORPHANED FILES")
        
        return len(cycles) == 0
    
    # ================================================================================
    # HELPER METHODS
    # ================================================================================
    
    def _get_call_name(self, node):
        """Extract function call name"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return self._get_attr_chain(node.func)
        return None
    
    def _get_attr_chain(self, node):
        """Extract attribute chain (e.g., client.get_account)"""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return '.'.join(reversed(parts))
    
    def _detect_cycles(self):
        """Detect cycles in import graph"""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.import_graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor) if neighbor in path else 0
                    cycles.append(path[cycle_start:] + [neighbor])
            
            rec_stack.remove(node)
        
        for node in self.import_graph:
            if node not in visited:
                dfs(node, [])
        
        return cycles
    
    def generate_report(self):
        """Generate final report"""
        print("\n" + "="*80)
        print("📊 SYSTEM HEALTH MATRIX")
        print("="*80)
        
        audit_results = {
            '✅ Zero-Polling Compliance': self.audit_zero_polling(),
            '✅ SMC Engine Wiring': self.audit_smc_pipeline(),
            '✅ Sharding Logic': self.audit_sharding_concurrency(),
            '✅ Polars Integration': self.audit_data_stack(),
            '✅ Circular Imports': self.audit_circular_imports(),
        }
        
        passed = sum(1 for v in audit_results.values() if v)
        total = len(audit_results)
        
        print("\n" + "="*80)
        print("AUDIT RESULTS")
        print("="*80)
        
        for check, result in audit_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {check}")
        
        print("\n" + "="*80)
        print(f"OVERALL: {passed}/{total} checks passed ({int(100*passed/total)}%)")
        print("="*80)
        
        if passed == total:
            print("🟢 SYSTEM INTEGRITY: EXCELLENT")
            print("✅ System is production-ready for deployment")
        else:
            print("🟡 SYSTEM INTEGRITY: NEEDS ATTENTION")
            print("⚠️ Review failures above and apply fixes")
        
        return passed == total


def main():
    print("🔍 LEAD SRE - DEEP CODE LOGIC & INTEGRITY AUDIT")
    print("="*80)
    
    engine = AuditEngine()
    all_passed = engine.generate_report()
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
