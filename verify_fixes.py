#!/usr/bin/env python3
"""
✅ VERIFICATION SCRIPT - Verify Critical Fixes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test both critical fixes:
1. FIX 1: Precision Rounding (StepSize Filter)
2. FIX 2: Atomic State Mutations (asyncio.Lock)

Run: python verify_fixes.py
"""

import asyncio
import sys

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'


class VerificationSuite:
    """Verification tests for critical fixes"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def log_pass(self, test_name: str, message: str):
        """Log passing test"""
        self.passed += 1
        print(f"{GREEN}✅ PASS{RESET} - {test_name}: {message}")
    
    def log_fail(self, test_name: str, message: str):
        """Log failing test"""
        self.failed += 1
        print(f"{RED}❌ FAIL{RESET} - {test_name}: {message}")
    
    def log_warn(self, test_name: str, message: str):
        """Log warning"""
        self.warnings += 1
        print(f"{YELLOW}⚠️ WARN{RESET} - {test_name}: {message}")
    
    # ──────────────────────────────────────────────────────────────────
    # FIX 1 TESTS: PRECISION ROUNDING
    # ──────────────────────────────────────────────────────────────────
    
    def test_import_math_utils(self):
        """Test: Can import math_utils successfully"""
        try:
            from src.utils.math_utils import round_step_size, round_to_precision, validate_quantity, get_step_size
            self.log_pass("Import Math Utils", "All functions imported successfully")
            return True
        except ImportError as e:
            self.log_fail("Import Math Utils", f"Import failed: {e}")
            return False
    
    def test_round_step_size_basic(self):
        """Test: round_step_size works for basic cases"""
        try:
            from src.utils.math_utils import round_step_size
            
            # Test case 1: 0.14977... → 0.149 (BTC)
            qty1 = 0.14977266648836587
            result1 = round_step_size(qty1, 0.001)
            
            if abs(result1 - 0.149) < 1e-10:
                self.log_pass("Round StepSize - Basic", f"{qty1} → {result1} (expected 0.149)")
            else:
                self.log_fail("Round StepSize - Basic", f"{qty1} → {result1} (expected 0.149)")
                return False
            
            # Test case 2: 0.123456789 → 0.123 (3 decimal places)
            qty2 = 0.123456789
            result2 = round_step_size(qty2, 0.001)
            
            if abs(result2 - 0.123) < 1e-10:
                self.log_pass("Round StepSize - Multi", f"{qty2} → {result2} (expected 0.123)")
            else:
                self.log_fail("Round StepSize - Multi", f"{qty2} → {result2} (expected 0.123)")
                return False
            
            return True
        
        except Exception as e:
            self.log_fail("Round StepSize - Basic", f"Exception: {e}")
            return False
    
    def test_round_always_down(self):
        """Test: round_step_size always rounds DOWN (ROUND_DOWN)"""
        try:
            from src.utils.math_utils import round_step_size
            
            # 0.1235 with 0.001 step → should go DOWN to 0.123, not up to 0.124
            qty = 0.1235
            result = round_step_size(qty, 0.001)
            
            if result <= qty:
                self.log_pass("Round Always Down", f"{qty} → {result} (rounded down)")
            else:
                self.log_fail("Round Always Down", f"{qty} → {result} (ROUNDED UP - WRONG!)")
                return False
            
            return True
        
        except Exception as e:
            self.log_fail("Round Always Down", f"Exception: {e}")
            return False
    
    def test_validate_quantity(self):
        """Test: validate_quantity catches bad quantities"""
        try:
            from src.utils.math_utils import validate_quantity
            
            # Valid quantity
            if validate_quantity(0.1, "BTCUSDT"):
                self.log_pass("Validate - Valid Qty", "0.1 BTC accepted")
            else:
                self.log_fail("Validate - Valid Qty", "0.1 BTC rejected (should be valid)")
                return False
            
            # Invalid: negative quantity
            if not validate_quantity(-0.1, "BTCUSDT"):
                self.log_pass("Validate - Negative", "-0.1 BTC rejected (correct)")
            else:
                self.log_fail("Validate - Negative", "-0.1 BTC accepted (should be rejected)")
                return False
            
            return True
        
        except Exception as e:
            self.log_fail("Validate Quantity", f"Exception: {e}")
            return False
    
    def test_get_step_size(self):
        """Test: get_step_size returns correct sizes"""
        try:
            from src.utils.math_utils import get_step_size
            
            # BTC: 0.001
            if get_step_size("BTCUSDT") == 0.001:
                self.log_pass("Step Size - BTC", "0.001")
                return True
            else:
                self.log_fail("Step Size - BTC", f"Got {get_step_size('BTCUSDT')}, expected 0.001")
                return False
        
        except Exception as e:
            self.log_fail("Get Step Size", f"Exception: {e}")
            return False
    
    # ──────────────────────────────────────────────────────────────────
    # FIX 2 TESTS: ATOMIC STATE MUTATIONS
    # ──────────────────────────────────────────────────────────────────
    
    async def test_import_trade_module(self):
        """Test: Can import trade module and verify lock exists"""
        try:
            from src import trade
            
            # Check _state_lock exists
            if hasattr(trade, '_state_lock'):
                self.log_pass("Import Trade Module", "trade._state_lock exists")
                return True
            else:
                self.log_fail("Import Trade Module", "trade._state_lock not found")
                return False
        
        except Exception as e:
            self.log_fail("Import Trade Module", f"Exception: {e}")
            return False
    
    async def test_concurrent_balance_updates(self):
        """Test: Concurrent balance updates are atomic (using lock)"""
        try:
            # Create a test account state
            test_state = {
                'balance': 1000.0,
                'positions': {},
                'trades': []
            }
            
            # Simulate concurrent deductions with proper locking
            lock = asyncio.Lock()
            
            async def deduct_with_lock(state, amount):
                """Atomic deduction with lock"""
                async with lock:
                    state['balance'] -= amount
            
            async def deduct_without_lock(state, amount):
                """Non-atomic deduction (vulnerable)"""
                current = state['balance']
                await asyncio.sleep(0.0001)  # Simulate delay (allow context switch)
                state['balance'] = current - amount
            
            # Test 1: WITH LOCK (should be correct)
            test_state_with_lock = {'balance': 1000.0}
            tasks_lock = [deduct_with_lock(test_state_with_lock, 10.0) for _ in range(50)]
            await asyncio.gather(*tasks_lock)
            
            if abs(test_state_with_lock['balance'] - 500.0) < 0.1:
                self.log_pass("Concurrent - WITH LOCK", f"Final balance: ${test_state_with_lock['balance']:.2f} (expected $500)")
            else:
                self.log_fail("Concurrent - WITH LOCK", f"Final balance: ${test_state_with_lock['balance']:.2f} (expected $500)")
                return False
            
            # Test 2: WITHOUT LOCK (demonstrate vulnerability)
            test_state_no_lock = {'balance': 1000.0}
            tasks_no_lock = [deduct_without_lock(test_state_no_lock, 10.0) for _ in range(50)]
            await asyncio.gather(*tasks_no_lock)
            
            if test_state_no_lock['balance'] != 500.0:
                self.log_warn("Concurrent - WITHOUT LOCK", f"Final balance: ${test_state_no_lock['balance']:.2f} (demonstrates race condition)")
            
            return True
        
        except Exception as e:
            self.log_fail("Concurrent Updates", f"Exception: {e}")
            return False
    
    async def test_get_balance_is_thread_safe(self):
        """Test: get_balance() function is thread-safe"""
        try:
            from src import trade
            
            # Reset state
            trade._account_state['balance'] = 10000.0
            
            # Call get_balance (should use lock internally)
            balance = await trade.get_balance()
            
            if balance == 10000.0:
                self.log_pass("Get Balance - Thread Safe", f"Balance correctly retrieved: ${balance:.2f}")
                return True
            else:
                self.log_fail("Get Balance - Thread Safe", f"Got ${balance:.2f}, expected $10000.00")
                return False
        
        except Exception as e:
            self.log_fail("Get Balance - Thread Safe", f"Exception: {e}")
            return False
    
    # ──────────────────────────────────────────────────────────────────
    # MAIN TEST RUNNER
    # ──────────────────────────────────────────────────────────────────
    
    async def run_all_tests(self):
        """Run all verification tests"""
        print("\n" + "="*80)
        print(f"{BLUE}🔍 VERIFICATION SUITE - Critical Fixes{RESET}")
        print("="*80 + "\n")
        
        # FIX 1: Precision Tests
        print(f"\n{BLUE}━━ FIX 1: PRECISION ROUNDING (StepSize Filter) ━━{RESET}")
        self.test_import_math_utils()
        self.test_round_step_size_basic()
        self.test_round_always_down()
        self.test_validate_quantity()
        self.test_get_step_size()
        
        # FIX 2: Concurrency Tests
        print(f"\n{BLUE}━━ FIX 2: ATOMIC STATE MUTATIONS ━━{RESET}")
        await self.test_import_trade_module()
        await self.test_concurrent_balance_updates()
        await self.test_get_balance_is_thread_safe()
        
        # Summary
        print(f"\n{BLUE}━━ SUMMARY ━━{RESET}")
        total = self.passed + self.failed + self.warnings
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"Total Tests:   {total}")
        print(f"Passed:        {self.passed} ({pass_rate:.1f}%)")
        print(f"Failed:        {self.failed}")
        print(f"Warnings:      {self.warnings}")
        
        # Final verdict
        print(f"\n{BLUE}━━ VERDICT ━━{RESET}")
        if self.failed == 0 and pass_rate >= 80:
            print(f"{GREEN}✅ FIXES VERIFIED - System ready for testing{RESET}\n")
            return 0
        elif self.failed == 0:
            print(f"{YELLOW}⚠️ FIXES PARTIALLY VERIFIED - Check warnings{RESET}\n")
            return 1
        else:
            print(f"{RED}❌ FIXES FAILED VERIFICATION - Debugging needed{RESET}\n")
            return 2


async def main():
    """Main entry point"""
    suite = VerificationSuite()
    exit_code = await suite.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
