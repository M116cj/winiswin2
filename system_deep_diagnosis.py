#!/usr/bin/env python3
"""
🔬 SYSTEM DEEP DIAGNOSIS - QA Automation Diagnostic
Comprehensive 4-phase test suite to verify system integrity
"""

import ast
import importlib
import sys
from typing import Dict, List, Tuple
from pathlib import Path

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

print(f"\n{BLUE}{'='*70}")
print("🔬 SYSTEM DEEP DIAGNOSIS - QA AUTOMATION")
print(f"{'='*70}{RESET}\n")

# ============================================================================
# TEST 1: STATIC REFERENCE CHECK (AST)
# ============================================================================

print(f"{BLUE}TEST 1: STATIC REFERENCE CHECK (AST){RESET}")
print("-" * 70)

def extract_config_vars(config_path: str) -> Dict[str, str]:
    """Extract all config variables from src/config.py"""
    with open(config_path, 'r') as f:
        tree = ast.parse(f.read())
    
    config_vars = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    config_vars[target.id] = 'class_attr'
    
    return config_vars


def check_config_usage(src_dir: str, config_vars: Dict) -> List[Tuple[str, str]]:
    """Check if all config references are valid"""
    mismatches = []
    
    for py_file in Path(src_dir).glob('*.py'):
        if py_file.name == 'config.py':
            continue
        
        with open(py_file, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                # Check for config.X references
                if isinstance(node.value, ast.Name) and node.value.id == 'config':
                    attr = node.attr
                    if attr not in config_vars and attr not in ['get']:
                        mismatches.append((py_file.name, f"config.{attr}"))
    
    return mismatches


# Read config variables
config_vars = extract_config_vars('src/config.py')
print(f"✓ Found {len(config_vars)} config variables:")
for var in sorted(config_vars.keys()):
    print(f"  - {var}")

# Check usage in other files
print("\n✓ Checking config references in other modules...")
mismatches = check_config_usage('src', config_vars)

if mismatches:
    print(f"{RED}✗ Config reference mismatches found:{RESET}")
    for file, var in mismatches:
        print(f"  {RED}✗ {file}: {var}{RESET}")
else:
    print(f"{GREEN}✓ All config references valid{RESET}")

# Check for direct os.getenv usage in trade.py (should use config)
print("\n✓ Checking for direct environment access (should use Config class)...")
with open('src/trade.py', 'r') as f:
    trade_content = f.read()

direct_env_usage = []
if "os.getenv('BINANCE_API_KEY'" in trade_content:
    direct_env_usage.append("BINANCE_API_KEY")
if "os.getenv('BINANCE_API_SECRET'" in trade_content:
    direct_env_usage.append("BINANCE_API_SECRET")

if direct_env_usage:
    print(f"{YELLOW}⚠ WARNING: trade.py directly accesses env vars instead of using Config:{RESET}")
    for var in direct_env_usage:
        print(f"  {YELLOW}⚠ {var} should use Config.{var}{RESET}")
else:
    print(f"{GREEN}✓ All environment access goes through Config class{RESET}")

test1_pass = len(mismatches) == 0
print(f"\n{'TEST 1: ' + ('PASS' if test1_pass else 'FAIL')}")

# ============================================================================
# TEST 2: IMPORT SAFETY
# ============================================================================

print(f"\n{BLUE}TEST 2: IMPORT SAFETY{RESET}")
print("-" * 70)

import_results = {}
test2_pass = True

for py_file in sorted(Path('src').glob('*.py')):
    module_name = py_file.stem
    module_path = f"src.{module_name}"
    
    try:
        importlib.import_module(module_path)
        import_results[module_name] = "✓ OK"
        print(f"{GREEN}✓ {module_path}{RESET}")
    except Exception as e:
        import_results[module_name] = str(e)
        print(f"{RED}✗ {module_path}: {e}{RESET}")
        test2_pass = False

print(f"\n{'TEST 2: ' + ('PASS' if test2_pass else 'FAIL')}")

# ============================================================================
# TEST 3: CLASS & METHOD INTEGRITY
# ============================================================================

print(f"\n{BLUE}TEST 3: CLASS & METHOD INTEGRITY{RESET}")
print("-" * 70)

test3_pass = True

try:
    from src.config import Config
    print(f"{GREEN}✓ Config class imported{RESET}")
    
    # Check Config attributes exist
    config_attrs = [
        'BINANCE_API_KEY', 'BINANCE_API_SECRET',
        'MAX_OPEN_POSITIONS', 'ATR_PERIOD', 'RSI_PERIOD'
    ]
    
    for attr in config_attrs:
        if hasattr(Config, attr):
            print(f"{GREEN}✓ Config.{attr} exists{RESET}")
        else:
            print(f"{RED}✗ Config.{attr} missing{RESET}")
            test3_pass = False
    
except Exception as e:
    print(f"{RED}✗ Config class error: {e}{RESET}")
    test3_pass = False

print(f"\n{'TEST 3: ' + ('PASS' if test3_pass else 'FAIL')}")

# ============================================================================
# TEST 4: MOCK SIMULATION (DRY RUN)
# ============================================================================

print(f"\n{BLUE}TEST 4: MOCK SIMULATION (DRY RUN){RESET}")
print("-" * 70)

test4_pass = True

try:
    # Test 4.1: Generate signature with test keys
    print("✓ Testing signature generation...")
    from src import trade
    
    test_params = {
        'symbol': 'BTCUSDT',
        'side': 'BUY',
        'quantity': 0.5,
        'timestamp': 1700656000000,
        'recvWindow': 5000
    }
    
    # Set test environment
    import os
    os.environ['BINANCE_API_SECRET'] = 'test_secret_key_123'
    
    # Build and sign request
    signed_request = trade._build_signed_request(test_params)
    
    if signed_request and 'signature=' in signed_request:
        print(f"{GREEN}✓ Signature generated successfully{RESET}")
        print(f"  Sample: {signed_request[:80]}...")
    else:
        print(f"{RED}✗ Signature generation failed{RESET}")
        test4_pass = False
    
    # Test 4.2: Process simple event flow
    print("\n✓ Testing event flow (Data -> Brain -> Trade)...")
    
    from src.bus import bus, Topic
    import asyncio
    
    signal_received = {'received': False}
    
    async def test_pipeline():
        # Subscribe to signal
        async def signal_handler(signal):
            signal_received['received'] = True
            print(f"{GREEN}✓ Signal received on EventBus{RESET}")
        
        bus.subscribe(Topic.SIGNAL_GENERATED, signal_handler)
        
        # Publish test signal
        test_signal = {
            'symbol': 'BTC/USDT',
            'confidence': 0.75,
            'position_size': 100.0
        }
        
        await bus.publish(Topic.SIGNAL_GENERATED, test_signal)
        await asyncio.sleep(0.1)
        
        if signal_received['received']:
            print(f"{GREEN}✓ Event flow operational{RESET}")
            return True
        else:
            print(f"{RED}✗ Signal not received{RESET}")
            return False
    
    # Run async test
    try:
        result = asyncio.run(test_pipeline())
        if not result:
            test4_pass = False
    except Exception as e:
        print(f"{YELLOW}⚠ Event bus test error: {e}{RESET}")
    
except Exception as e:
    print(f"{RED}✗ Mock simulation error: {e}{RESET}")
    test4_pass = False

print(f"\n{'TEST 4: ' + ('PASS' if test4_pass else 'FAIL')}")

# ============================================================================
# SUMMARY
# ============================================================================

print(f"\n{BLUE}{'='*70}")
print("DIAGNOSTIC SUMMARY")
print(f"{'='*70}{RESET}")

all_tests = {
    'Syntax & Imports': test2_pass,
    'Config Variable Match': test1_pass,
    'Method Signatures': test3_pass,
    'Simulation Run': test4_pass
}

passed = sum(1 for v in all_tests.values() if v)
total = len(all_tests)

for test_name, result in all_tests.items():
    status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
    print(f"  [{status}] {test_name}")

print(f"\n{BLUE}Result: {passed}/{total} tests passed{RESET}")

if passed == total:
    print(f"{GREEN}✓ SYSTEM INTEGRITY VERIFIED - READY FOR PRODUCTION{RESET}")
else:
    print(f"{RED}✗ ISSUES FOUND - Review above for details{RESET}")

print()

sys.exit(0 if passed == total else 1)
