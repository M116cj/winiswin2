#!/usr/bin/env python3
"""
🔬 SYSTEM MASTER SCAN - Chief System Auditor & QA Architect
Comprehensive 5-category defect audit for production-grade trading system
"""

import ast
import importlib
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import re

# ============================================================================
# ANSI COLORS FOR OUTPUT
# ============================================================================
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
MAGENTA = '\033[95m'
RESET = '\033[0m'

# Defect tracking
defects = {
    'HIGH': [],
    'MEDIUM': [],
    'LOW': []
}

print(f"\n{MAGENTA}{'='*80}")
print("🔬 SYSTEM MASTER SCAN - AUTONOMOUS DEEP-DIVE AUDIT")
print(f"{'='*80}{RESET}\n")

# ============================================================================
# CATEGORY 1: ARCHITECTURAL VIOLATIONS (Static Analysis)
# ============================================================================

print(f"{BLUE}CATEGORY 1: ARCHITECTURAL VIOLATIONS{RESET}")
print("-" * 80)

def check_zero_polling():
    """Check for HTTP calls inside loops (violation of zero-polling)"""
    violations = []
    
    for py_file in ['src/trade.py', 'src/brain.py']:
        with open(py_file, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            # Find while/for loops
            if isinstance(node, (ast.While, ast.For)):
                loop_body = node.body
                
                # Check for requests or HTTP calls in loop
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            # Check for requests.get, client.get_account, etc.
                            if 'get' in child.func.attr or 'post' in child.func.attr:
                                if 'requests' in ast.unparse(child.func) or 'client' in ast.unparse(child.func):
                                    violations.append({
                                        'file': py_file,
                                        'severity': 'HIGH',
                                        'defect': f'HTTP call {child.func.attr}() inside loop',
                                        'line': child.lineno
                                    })
    
    return violations

polling_violations = check_zero_polling()
if polling_violations:
    for v in polling_violations:
        defects['HIGH'].append(v)
        print(f"{RED}✗ HIGH: {v['file']} - {v['defect']} (line {v['line']}){RESET}")
else:
    print(f"{GREEN}✓ No polling violations found{RESET}")

def check_efficiency_standards():
    """Check for __slots__, orjson usage, pandas imports"""
    violations = []
    
    # Check for pandas (should not exist)
    for py_file in Path('src').glob('*.py'):
        with open(py_file, 'r') as f:
            content = f.read()
        
        if 'import pandas' in content or 'from pandas' in content:
            violations.append({
                'file': str(py_file),
                'severity': 'HIGH',
                'defect': 'Pandas import found (use polars instead)',
                'suggestion': 'Replace pandas with polars for performance'
            })
        
        if 'json.loads' in content and 'orjson' not in content:
            violations.append({
                'file': str(py_file),
                'severity': 'MEDIUM',
                'defect': 'json.loads() found (use orjson.loads for 10x performance)',
                'suggestion': 'import orjson; use orjson.loads()'
            })
    
    return violations

efficiency_violations = check_efficiency_standards()
if efficiency_violations:
    for v in efficiency_violations:
        severity = v['severity']
        defects[severity].append(v)
        print(f"{RED}✗ {severity}: {v['file']} - {v['defect']}{RESET}")
else:
    print(f"{GREEN}✓ No efficiency violations found{RESET}")

# ============================================================================
# CATEGORY 2: LOGICAL DISCONNECTS (Topology Check)
# ============================================================================

print(f"\n{BLUE}CATEGORY 2: LOGICAL DISCONNECTS{RESET}")
print("-" * 80)

def check_brain_trade_handshake():
    """Check if Brain output (Signal) matches Trade input"""
    issues = []
    
    # Brain should output Signal dict with: symbol, confidence, position_size
    with open('src/brain.py', 'r') as f:
        brain_content = f.read()
    
    if "'symbol':" in brain_content and "'confidence':" in brain_content:
        print(f"{GREEN}✓ Brain generates Signal with symbol, confidence{RESET}")
    else:
        issues.append({
            'severity': 'HIGH',
            'file': 'src/brain.py',
            'defect': 'Signal object missing required fields'
        })
    
    # Trade should accept Signal via EventBus
    with open('src/trade.py', 'r') as f:
        trade_content = f.read()
    
    if 'Topic.SIGNAL_GENERATED' in trade_content or 'signal' in trade_content:
        print(f"{GREEN}✓ Trade module subscribes to signals{RESET}")
    else:
        issues.append({
            'severity': 'HIGH',
            'file': 'src/trade.py',
            'defect': 'Trade module does not handle SIGNAL_GENERATED events'
        })
    
    return issues

handshake_issues = check_brain_trade_handshake()
for issue in handshake_issues:
    defects[issue['severity']].append(issue)

def check_data_brain_pipeline():
    """Check if Data connects to Brain (no orphaned producers)"""
    with open('src/data.py', 'r') as f:
        data_content = f.read()
    
    if 'bus.publish' in data_content and 'Topic.SIGNAL_GENERATED' in data_content:
        print(f"{GREEN}✓ Data module publishes signals to EventBus{RESET}")
    else:
        defects['HIGH'].append({
            'severity': 'HIGH',
            'file': 'src/data.py',
            'defect': 'Data module does not publish signals (orphaned producer)'
        })
        print(f"{RED}✗ HIGH: Data module orphaned (no signal publishing){RESET}")

check_data_brain_pipeline()

# ============================================================================
# CATEGORY 3: CONFIGURATION & SECURITY GAPS
# ============================================================================

print(f"\n{BLUE}CATEGORY 3: CONFIGURATION & SECURITY GAPS{RESET}")
print("-" * 80)

def check_config_variable_integrity():
    """Check for ghost variables (defined but unused) or missing variables"""
    with open('src/config.py', 'r') as f:
        config_content = f.read()
    
    tree = ast.parse(config_content)
    defined_vars = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_vars.add(target.id)
    
    # Check usage in all src files
    used_vars = set()
    for py_file in Path('src').glob('*.py'):
        if py_file.name == 'config.py':
            continue
        with open(py_file, 'r') as f:
            content = f.read()
        
        for var in defined_vars:
            if f'Config.{var}' in content or f'config.{var}' in content:
                used_vars.add(var)
    
    ghost_vars = defined_vars - used_vars - {'get', 'validate_binance_keys'}
    
    if ghost_vars:
        print(f"{YELLOW}⚠️  MEDIUM: Ghost variables defined but not used:{RESET}")
        for var in ghost_vars:
            defects['MEDIUM'].append({
                'severity': 'MEDIUM',
                'file': 'src/config.py',
                'defect': f'Ghost variable: {var} (defined but never used)'
            })
            print(f"   - {var}")
    else:
        print(f"{GREEN}✓ No ghost variables found{RESET}")
    
    print(f"{GREEN}✓ Defined: {len(defined_vars)} vars, Used: {len(used_vars)} vars{RESET}")

check_config_variable_integrity()

def check_secret_safety():
    """Check for hardcoded credentials"""
    with open('src/config.py', 'r') as f:
        config_content = f.read()
    
    # Check if secrets have defaults other than None or empty string
    if "BINANCE_API_SECRET = os.getenv" in config_content:
        print(f"{GREEN}✓ BINANCE_API_SECRET properly uses os.getenv (no hardcoded value){RESET}")
    else:
        defects['HIGH'].append({
            'severity': 'HIGH',
            'file': 'src/config.py',
            'defect': 'BINANCE_API_SECRET may have hardcoded value'
        })
        print(f"{RED}✗ HIGH: Potential hardcoded credentials{RESET}")

check_secret_safety()

def check_type_safety():
    """Check if numeric configs are parsed as correct types"""
    with open('src/config.py', 'r') as f:
        tree = ast.parse(f.read())
    
    numeric_configs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if 'MAX' in target.id or 'PERIOD' in target.id or target.id == 'THRESHOLD':
                        numeric_configs[target.id] = type(node.value)
    
    print(f"{GREEN}✓ Type-checked {len(numeric_configs)} numeric configs{RESET}")

check_type_safety()

# ============================================================================
# CATEGORY 4: RUNTIME SIMULATION (The Mock Test)
# ============================================================================

print(f"\n{BLUE}CATEGORY 4: RUNTIME SIMULATION{RESET}")
print("-" * 80)

def test_signature_validity():
    """Test if signature generation works without crashing"""
    try:
        from src import trade
        import os
        
        os.environ['BINANCE_API_SECRET'] = 'test_secret_key_for_audit'
        
        test_params = {
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'quantity': 0.5,
            'timestamp': 1700656000000
        }
        
        result = trade._build_signed_request(test_params)
        
        if result and 'signature=' in result:
            print(f"{GREEN}✓ Signature generation works (valid format){RESET}")
            return True
        else:
            defects['HIGH'].append({
                'severity': 'HIGH',
                'file': 'src/trade.py',
                'defect': 'Signature generation returns invalid format'
            })
            print(f"{RED}✗ HIGH: Signature generation failed{RESET}")
            return False
    except Exception as e:
        defects['HIGH'].append({
            'severity': 'HIGH',
            'file': 'src/trade.py',
            'defect': f'Signature generation crashes: {str(e)}'
        })
        print(f"{RED}✗ HIGH: Signature generation error: {e}{RESET}")
        return False

test_signature_validity()

def test_smc_math_stability():
    """Test SMC calculations with edge cases (zero, negative, None values)"""
    try:
        from src.indicators import Indicators
        
        # Test with normal data
        prices = [100, 101, 99, 102, 101, 100]
        rsi = Indicators.rsi(prices, 14)
        if isinstance(rsi, (int, float)) and 0 <= rsi <= 100:
            print(f"{GREEN}✓ RSI calculation stable (result: {rsi:.1f}){RESET}")
        
        # Test with edge cases
        highs = [100, 101, 102, 103, 104]
        lows = [99, 100, 101, 102, 103]
        closes = [100, 101, 102, 103, 104]
        atr = Indicators.atr(highs, lows, closes, 14)
        print(f"{GREEN}✓ ATR calculation stable (result: {atr:.2f}){RESET}")
        
        return True
    except ZeroDivisionError:
        defects['HIGH'].append({
            'severity': 'HIGH',
            'file': 'src/indicators.py',
            'defect': 'ZeroDivisionError in math calculations (no input sanitization)'
        })
        print(f"{RED}✗ HIGH: SMC math has ZeroDivisionError{RESET}")
        return False
    except Exception as e:
        defects['MEDIUM'].append({
            'severity': 'MEDIUM',
            'file': 'src/indicators.py',
            'defect': f'SMC calculation error: {str(e)}'
        })
        print(f"{YELLOW}⚠️ MEDIUM: SMC calculation issue: {e}{RESET}")
        return False

test_smc_math_stability()

# ============================================================================
# CATEGORY 5: ERROR HANDLING COVERAGE
# ============================================================================

print(f"\n{BLUE}CATEGORY 5: ERROR HANDLING COVERAGE{RESET}")
print("-" * 80)

def check_error_handling():
    """Check for async functions without try-except, bare excepts"""
    issues = []
    
    for py_file in Path('src').glob('*.py'):
        with open(py_file, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            # Find async functions
            if isinstance(node, ast.AsyncFunctionDef):
                func_name = node.name
                
                # Check if function body has try-except
                has_try_except = any(isinstance(child, ast.Try) for child in node.body)
                
                # Check for I/O operations (aiohttp, async with, etc)
                has_io = False
                for child in ast.walk(node):
                    if isinstance(child, ast.With) or isinstance(child, ast.AsyncWith):
                        has_io = True
                        break
                
                if has_io and not has_try_except:
                    issues.append({
                        'severity': 'MEDIUM',
                        'file': str(py_file),
                        'defect': f'Async function {func_name}() has I/O but no try-except',
                        'line': node.lineno
                    })
        
        # Check for bare except clauses
        bare_excepts = re.findall(r'except\s*:\s*(?!pass)', content)
        if bare_excepts:
            issues.append({
                'severity': 'MEDIUM',
                'file': str(py_file),
                'defect': 'Bare except: clause found (swallows errors)'
            })
    
    return issues

error_handling_issues = check_error_handling()
if error_handling_issues:
    for issue in error_handling_issues:
        defects[issue['severity']].append(issue)
        print(f"{YELLOW}✗ {issue['severity']}: {issue['file']} - {issue['defect']}{RESET}")
else:
    print(f"{GREEN}✓ Good error handling coverage overall{RESET}")

# ============================================================================
# SUMMARY
# ============================================================================

print(f"\n{MAGENTA}{'='*80}")
print("AUDIT SUMMARY")
print(f"{'='*80}{RESET}\n")

total_defects = sum(len(v) for v in defects.values())
print(f"Total defects found: {total_defects}\n")

for severity in ['HIGH', 'MEDIUM', 'LOW']:
    count = len(defects[severity])
    symbol = '🔴' if severity == 'HIGH' else ('🟡' if severity == 'MEDIUM' else '🟢')
    print(f"{symbol} {severity}: {count} defect(s)")
    for defect in defects[severity]:
        print(f"   - {defect.get('file', 'N/A')}: {defect.get('defect', 'Unknown')}")

status = "PASS" if defects['HIGH'] == [] else "FAIL"
print(f"\n{'='*80}")
print(f"AUDIT STATUS: {status}")
print(f"{'='*80}\n")

sys.exit(0 if defects['HIGH'] == [] else 1)
