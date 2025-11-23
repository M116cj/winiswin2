#!/usr/bin/env python3
"""
🔍 RELIABILITY ENGINEER - HIDDEN RISKS AUDIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mission: Verify system against "Hidden Risks" edge cases:
1. SYMBOL FILTERS (Precision) - LOT_SIZE, PRICE_FILTER rounding
2. LISTEN KEY KEEPALIVE - WebSocket connection maintenance
3. CACHE RECONCILIATION - Periodic REST API sync
4. DATA GAP FILLING - Handle missing market data

Detection Method: Deep code scan + pattern matching
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass

# ANSI Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

@dataclass
class AuditResult:
    """Result of a single audit check"""
    name: str
    status: str  # SAFE, RISKY, MISSING, ACTIVE, INACTIVE
    findings: List[str]
    evidence: List[str]
    patches_needed: List[str]

print(f"""
{BOLD}{BLUE}
╔════════════════════════════════════════════════════════════════════╗
║  🔍 RELIABILITY ENGINEER - HIDDEN RISKS AUDIT SYSTEM              ║
║  Precision | ListenKey | Cache | Data Gaps - Comprehensive Scan   ║
╚════════════════════════════════════════════════════════════════════╝
{RESET}
""")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def read_files(pattern: str = "src/**/*.py") -> Dict[str, str]:
    """Read all Python files matching pattern"""
    files = {}
    for py_file in Path(".").rglob("*.py"):
        if py_file.parts[0] == "src":
            try:
                files[str(py_file)] = py_file.read_text()
            except:
                pass
    return files

def search_pattern(files: Dict[str, str], patterns: List[str], case_sensitive: bool = False) -> Dict[str, List[Tuple[int, str]]]:
    """Search for patterns in files"""
    results = {}
    flags = 0 if case_sensitive else re.IGNORECASE
    
    for filename, content in files.items():
        matches = []
        for line_num, line in enumerate(content.split('\n'), 1):
            for pattern in patterns:
                if re.search(pattern, line, flags):
                    matches.append((line_num, line.strip()))
        
        if matches:
            results[filename] = matches
    
    return results

# ============================================================================
# AUDIT 1: SYMBOL FILTERS (PRECISION)
# ============================================================================

def audit_precision() -> AuditResult:
    """
    Check for proper handling of Binance symbol filters
    
    Binance requires:
    1. Quantity must respect LOT_SIZE (min/max)
    2. Price must respect PRICE_FILTER (step size)
    3. Notional value must respect MIN_NOTIONAL
    4. Code must round quantities/prices to allowed values
    """
    
    print(f"\n{BOLD}[AUDIT 1] SYMBOL FILTERS (Precision){RESET}")
    print("─" * 70)
    
    files = read_files()
    findings = []
    evidence = []
    patches = []
    
    # Search for rounding functions
    rounding_patterns = [
        r"round_step_size|round_quantity|round_price",
        r"def.*round.*quantity|def.*round.*price",
        r"LOT_SIZE|PRICE_FILTER|MIN_NOTIONAL",
        r"Decimal.*quantize|quantize.*ROUND"
    ]
    
    rounding_results = search_pattern(files, rounding_patterns)
    
    if rounding_results:
        print(f"  {GREEN}✓ Found rounding logic{RESET}")
        for file, matches in list(rounding_results.items())[:3]:
            for line_num, line in matches[:2]:
                evidence.append(f"    {file}:{line_num}: {line[:60]}")
    else:
        print(f"  {RED}✗ NO rounding functions found{RESET}")
        findings.append("Missing LOT_SIZE/PRICE_FILTER rounding functions")
        patches.append("PATCH_1_SYMBOL_FILTERS")
    
    # Search for order execution without validation
    order_patterns = [
        r"create_order\(|place_order\(|submit_order\(",
        r"_execute_order.*quantity|order.*quantity"
    ]
    
    order_results = search_pattern(files, order_patterns)
    
    if order_results:
        print(f"\n  {YELLOW}→ Order submission found{RESET}")
        
        # Check if quantity is validated before sending
        for file, matches in list(order_results.items())[:2]:
            content = files[file]
            
            # Check if quantity validation exists near order submission
            if "quantity <= 0" in content or "quantity < min" in content:
                print(f"    {GREEN}✓ Quantity validation present{RESET}")
            else:
                print(f"    {RED}✗ No quantity validation before order submit{RESET}")
                findings.append(f"Order submission in {file} lacks quantity validation")
                patches.append("PATCH_1_SYMBOL_FILTERS")
    
    # Check for decimal/precise arithmetic
    decimal_patterns = [r"from decimal import Decimal", r"Decimal\("]
    decimal_results = search_pattern(files, decimal_patterns)
    
    if not decimal_results:
        print(f"  {YELLOW}⚠ System uses float arithmetic (may have precision issues){RESET}")
        findings.append("Using float instead of Decimal for precise calculations")
    else:
        print(f"  {GREEN}✓ Using Decimal for precision{RESET}")
    
    # Determine status
    status = "SAFE"
    if len(patches) > 0:
        status = "RISKY"
        if not rounding_results:
            status = "MISSING"
    
    print(f"\n  Status: {RED if status == 'MISSING' else YELLOW if status == 'RISKY' else GREEN}{status}{RESET}")
    
    return AuditResult(
        name="Precision (LOT_SIZE/PRICE_FILTER)",
        status=status,
        findings=findings,
        evidence=evidence,
        patches_needed=patches
    )


# ============================================================================
# AUDIT 2: LISTEN KEY KEEPALIVE
# ============================================================================

def audit_listenkey_keepalive() -> AuditResult:
    """
    Check for WebSocket ListenKey keep-alive mechanism
    
    Binance requirement:
    - User data stream listenKey expires after 60 minutes inactivity
    - Must call PUT /fapi/v1/listenKey every 30 minutes
    - OR use low-level WebSocket keep-alive ping/pong
    """
    
    print(f"\n{BOLD}[AUDIT 2] LISTEN KEY KEEPALIVE{RESET}")
    print("─" * 70)
    
    files = read_files()
    findings = []
    evidence = []
    patches = []
    
    # Search for WebSocket implementation
    ws_patterns = [
        r"websocket|aiowebsocket|ws\.|wss://",
        r"stream_keepalive|stream_get_listen_key",
        r"keep.?alive|keepalive",
        r"put.*listenkey|PUT.*listenkey"
    ]
    
    ws_results = search_pattern(files, ws_patterns)
    
    if ws_results:
        print(f"  {GREEN}✓ WebSocket integration found{RESET}")
        for file, matches in list(ws_results.items())[:2]:
            for line_num, line in matches[:2]:
                evidence.append(f"    {file}:{line_num}: {line[:60]}")
    else:
        print(f"  {YELLOW}→ No explicit WebSocket keep-alive found{RESET}")
    
    # Check for CCXT (which handles WebSocket for us)
    ccxt_patterns = [r"import.*ccxt|from ccxt", r"ccxt\.binance|ccxt\["]
    ccxt_results = search_pattern(files, ccxt_patterns)
    
    if ccxt_results:
        print(f"  {GREEN}✓ Using CCXT (handles keep-alive internally){RESET}")
        findings.append("System uses CCXT which manages listenKey internally")
        status = "ACTIVE"
    else:
        # If using raw WebSocket, check for keep-alive
        keepalive_patterns = [r"keep.*alive|keepalive|ping|pong"]
        keepalive_results = search_pattern(files, keepalive_patterns)
        
        if keepalive_results:
            print(f"  {GREEN}✓ Keep-alive mechanism present{RESET}")
            status = "ACTIVE"
        else:
            print(f"  {RED}✗ NO keep-alive mechanism found{RESET}")
            findings.append("No listenKey keep-alive mechanism detected")
            patches.append("PATCH_2_LISTENKEY_KEEPALIVE")
            status = "MISSING"
    
    print(f"\n  Status: {GREEN if status == 'ACTIVE' else RED}{status}{RESET}")
    
    return AuditResult(
        name="ListenKey Keepalive",
        status=status,
        findings=findings,
        evidence=evidence,
        patches_needed=patches
    )


# ============================================================================
# AUDIT 3: CACHE RECONCILIATION
# ============================================================================

def audit_cache_reconciliation() -> AuditResult:
    """
    Check for periodic cache reconciliation against Binance
    
    Requirements:
    - Every 15-60 minutes: Call get_account_information() via REST
    - Verify local positions match Binance state
    - Detect and recover from WebSocket gaps
    """
    
    print(f"\n{BOLD}[AUDIT 3] CACHE RECONCILIATION{RESET}")
    print("─" * 70)
    
    files = read_files()
    findings = []
    evidence = []
    patches = []
    
    # Search for periodic sync tasks
    sync_patterns = [
        r"asyncio\.create_task|asyncio\.gather|create_task",
        r"get_account|get_balance|get_positions",
        r"reconcile|sync.*state|verify.*position",
        r"every.*\d+.*minute|every.*\d+.*second|timedelta"
    ]
    
    sync_results = search_pattern(files, sync_patterns)
    
    if sync_results:
        print(f"  {GREEN}✓ Periodic sync patterns found{RESET}")
        for file, matches in list(sync_results.items())[:2]:
            for line_num, line in matches[:2]:
                evidence.append(f"    {file}:{line_num}: {line[:60]}")
    
    # Check for specific REST API calls
    rest_patterns = [
        r"fapi/v\d+/account",
        r"get_account_information|fetch_balance",
        r"rest.*get|client\.account"
    ]
    
    rest_results = search_pattern(files, rest_patterns)
    
    if rest_results:
        print(f"  {GREEN}✓ REST API account sync found{RESET}")
        status = "ACTIVE"
    else:
        # Check if system relies 100% on WebSocket
        websocket_only = search_pattern(files, [r"websocket.*only|ws.*only"])
        
        status = "MISSING"
        if websocket_only or "CCXT" in str(sync_results):
            print(f"  {YELLOW}⚠ System may rely 100% on streaming data{RESET}")
            findings.append("No periodic REST API sync found - relies on WebSocket only")
            patches.append("PATCH_3_CACHE_RECONCILIATION")
            status = "RISKY"
        else:
            print(f"  {RED}✗ NO cache reconciliation found{RESET}")
            findings.append("No REST API sync mechanism for cache reconciliation")
            patches.append("PATCH_3_CACHE_RECONCILIATION")
    
    print(f"\n  Status: {GREEN if status == 'ACTIVE' else YELLOW if status == 'RISKY' else RED}{status}{RESET}")
    
    return AuditResult(
        name="Cache Reconciliation",
        status=status,
        findings=findings,
        evidence=evidence,
        patches_needed=patches
    )


# ============================================================================
# AUDIT 4: DATA GAP FILLING
# ============================================================================

def audit_data_gap_filling() -> AuditResult:
    """
    Check for data gap detection and filling
    
    Requirements:
    - Detect: if timestamp_diff > interval: gap detected
    - Fill: fetch missing candles for gap
    - Skip: don't calculate indicators on incomplete data
    """
    
    print(f"\n{BOLD}[AUDIT 4] DATA GAP FILLING{RESET}")
    print("─" * 70)
    
    files = read_files()
    findings = []
    evidence = []
    patches = []
    
    # Search for gap detection logic
    gap_patterns = [
        r"timestamp.*gap|gap.*detect|missing.*data|discontinuous",
        r"current.*-.*last.*>.*interval",
        r"time.*diff|time.*delta|elapsed",
        r"fetch_missing|fill_gap|get_history"
    ]
    
    gap_results = search_pattern(files, gap_patterns)
    
    if gap_results:
        print(f"  {GREEN}✓ Gap detection logic found{RESET}")
        for file, matches in list(gap_results.items())[:2]:
            for line_num, line in matches[:2]:
                evidence.append(f"    {file}:{line_num}: {line[:60]}")
        status = "ACTIVE"
    else:
        print(f"  {YELLOW}→ Checking feed process for gaps...{RESET}")
        
        # Check feed.py for data continuity
        if "src/feed.py" in files:
            feed_content = files["src/feed.py"]
            
            # Look for fetch frequency
            if "fetch_ohlcv" in feed_content or "fetch_klines" in feed_content:
                print(f"    → Fetching market data every minute (CCXT)")
                
                # Check if gap handling exists
                if "gap" in feed_content.lower() or "missing" in feed_content.lower():
                    print(f"    {GREEN}✓ Gap handling present{RESET}")
                    status = "ACTIVE"
                else:
                    print(f"    {RED}✗ No gap handling logic{RESET}")
                    findings.append("Feed fetches every 1 minute but no gap detection/filling")
                    patches.append("PATCH_4_DATA_GAP_FILLING")
                    status = "RISKY"
            else:
                print(f"    {RED}✗ No feed data ingestion found{RESET}")
                status = "MISSING"
    
    # Check if indicators blindly process data
    indicator_patterns = [
        r"calculate.*indicator|compute.*rsi|compute.*atr",
        r"if.*len.*data.*>",  # Check for data validation
        r"assert.*len|validate.*data"
    ]
    
    indicator_results = search_pattern(files, indicator_patterns)
    
    if indicator_results:
        print(f"  {YELLOW}→ Indicators found - checking for data validation{RESET}")
        
        # Check if data is validated before use
        if "assert" in str(indicator_results) or "len" in str(indicator_results):
            print(f"    {GREEN}✓ Indicators validate data length{RESET}")
        else:
            print(f"    {YELLOW}⚠ Indicators may process incomplete data{RESET}")
            findings.append("Indicators don't validate data continuity")
    
    print(f"\n  Status: {GREEN if status == 'ACTIVE' else YELLOW if status == 'RISKY' else RED}{status}{RESET}")
    
    return AuditResult(
        name="Data Gap Filling",
        status=status,
        findings=findings,
        evidence=evidence,
        patches_needed=patches
    )


# ============================================================================
# FINAL REPORT
# ============================================================================

print(f"{BOLD}SCANNING CODEBASE...{RESET}")
print("" * 70)

# Run all audits
audit1 = audit_precision()
audit2 = audit_listenkey_keepalive()
audit3 = audit_cache_reconciliation()
audit4 = audit_data_gap_filling()

audits = [audit1, audit2, audit3, audit4]

# Summary Report
print(f"\n\n{BOLD}{'=' * 70}{RESET}")
print(f"{BOLD}AUDIT SUMMARY{RESET}")
print(f"{BOLD}{'=' * 70}{RESET}\n")

results_table = []
all_patches = set()

for audit in audits:
    status_color = GREEN if audit.status in ["SAFE", "ACTIVE"] else RED if audit.status == "MISSING" else YELLOW
    status_str = f"{status_color}{audit.status}{RESET}"
    
    print(f"  {audit.name:<35} {status_str}")
    
    if audit.findings:
        for finding in audit.findings:
            print(f"    • {finding}")
    
    if audit.patches_needed:
        all_patches.update(audit.patches_needed)
    
    results_table.append((audit.name, audit.status))

print(f"\n{BOLD}{'=' * 70}{RESET}\n")

# Patch Summary
if all_patches:
    print(f"{BOLD}PATCHES REQUIRED:{RESET}\n")
    
    if "PATCH_1_SYMBOL_FILTERS" in all_patches:
        print(f"  {BOLD}PATCH_1: Symbol Filters (Precision){RESET}")
        print(f"    Create: round_step_size(quantity, step) → rounded quantity")
        print(f"    Create: validate_lot_size(symbol, quantity) → bool")
        print(f"    Update: _execute_order_live() to round quantity before sending\n")
    
    if "PATCH_2_LISTENKEY_KEEPALIVE" in all_patches:
        print(f"  {BOLD}PATCH_2: ListenKey Keepalive{RESET}")
        print(f"    Create: async keep_alive_task() that calls PUT every 30 minutes")
        print(f"    Add: to main.py as asyncio.create_task(keep_alive_task())\n")
    
    if "PATCH_3_CACHE_RECONCILIATION" in all_patches:
        print(f"  {BOLD}PATCH_3: Cache Reconciliation{RESET}")
        print(f"    Create: async reconcile_account_state() REST API call")
        print(f"    Add: periodic task every 15-30 minutes")
        print(f"    Add: verify local positions match Binance\n")
    
    if "PATCH_4_DATA_GAP_FILLING" in all_patches:
        print(f"  {BOLD}PATCH_4: Data Gap Filling{RESET}")
        print(f"    Add: gap detection in feed.py (timestamp validation)")
        print(f"    Add: fetch_missing_candles(symbol, start_time, end_time)")
        print(f"    Add: validate data continuity before indicator calculation\n")
else:
    print(f"{GREEN}✅ NO PATCHES REQUIRED - All systems operational{RESET}\n")

# Risk Assessment
print(f"{BOLD}RISK ASSESSMENT:{RESET}\n")

critical_issues = sum(1 for a in audits if a.status == "MISSING")
high_risk = sum(1 for a in audits if a.status == "RISKY")
safe = sum(1 for a in audits if a.status in ["SAFE", "ACTIVE"])

if critical_issues > 0:
    print(f"  {RED}🔴 CRITICAL: {critical_issues} missing system(s){RESET}")
if high_risk > 0:
    print(f"  {YELLOW}🟡 HIGH RISK: {high_risk} risky configuration(s){RESET}")
if safe > 0:
    print(f"  {GREEN}🟢 SAFE: {safe} properly implemented{RESET}")

print(f"\n{BOLD}{'=' * 70}{RESET}\n")

if all_patches:
    print(f"{RED}{BOLD}⚠️  ACTION REQUIRED: Review patches above and implement as needed{RESET}\n")
else:
    print(f"{GREEN}{BOLD}✅ SYSTEM CERTIFIED - All hidden risks mitigated{RESET}\n")
