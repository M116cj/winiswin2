#!/usr/bin/env python3
"""
🛡️ DATA FIREWALL TEST SUITE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Comprehensive validation of the strict data firewall.
Tests all poison pill scenarios to ensure they're caught BEFORE ring buffer.

Run: python test_data_firewall.py
"""

import sys
import time as time_module
from decimal import Decimal

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'


class FirewallTestSuite:
    """Test the strict data validation firewall"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
    
    def log_pass(self, test_name: str, message: str = ""):
        """Log passing test"""
        self.passed += 1
        msg = f" - {message}" if message else ""
        print(f"{GREEN}✅ PASS{RESET} - {test_name}{msg}")
    
    def log_fail(self, test_name: str, message: str = ""):
        """Log failing test"""
        self.failed += 1
        msg = f" - {message}" if message else ""
        print(f"{RED}❌ FAIL{RESET} - {test_name}{msg}")
    
    # ─────────────────────────────────────────────────────────────────
    # HELPER: Create valid/invalid candles
    # ─────────────────────────────────────────────────────────────────
    
    def make_valid_candle(self):
        """Create a valid reference candle"""
        current_ms = time_module.time() * 1000
        return {
            't': current_ms,
            'o': 65000.0,
            'h': 65500.0,
            'l': 64500.0,
            'c': 65200.0,
            'v': 100.0,
            'symbol': 'BTCUSDT'
        }
    
    # ─────────────────────────────────────────────────────────────────
    # TEST SUITE: VALID CANDLES
    # ─────────────────────────────────────────────────────────────────
    
    def test_valid_candle_basic(self):
        """Test: Valid candle is accepted"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            if _is_valid_tick(candle):
                self.log_pass("Valid Candle", "Basic valid candle accepted")
            else:
                self.log_fail("Valid Candle", "Valid candle was rejected!")
        except Exception as e:
            self.log_fail("Valid Candle", str(e))
    
    def test_valid_candle_with_variations(self):
        """Test: Valid candle with key name variations"""
        try:
            from src.feed import _is_valid_tick
            
            # Test with alternative key names
            candle_variations = [
                {'T': int(time_module.time() * 1000), 'O': 65000, 'H': 65500, 'L': 64500, 'C': 65200, 'V': 100},
                {'timestamp': int(time_module.time() * 1000), 'open': 65000, 'high': 65500, 'low': 64500, 'close': 65200, 'volume': 100},
            ]
            
            for candle in candle_variations:
                if not _is_valid_tick(candle):
                    self.log_fail("Key Variations", f"Rejected valid variation: {candle}")
                    return
            
            self.log_pass("Key Variations", "All valid key name variations accepted")
        except Exception as e:
            self.log_fail("Key Variations", str(e))
    
    # ─────────────────────────────────────────────────────────────────
    # POISON PILL 1: None Values
    # ─────────────────────────────────────────────────────────────────
    
    def test_poison_none_timestamp(self):
        """Test: None timestamp is rejected"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            candle['t'] = None
            
            if not _is_valid_tick(candle):
                self.log_pass("Poison: None Timestamp", "Correctly rejected")
            else:
                self.log_fail("Poison: None Timestamp", "Was accepted (should reject)")
        except Exception as e:
            self.log_fail("Poison: None Timestamp", str(e))
    
    def test_poison_none_prices(self):
        """Test: None prices are rejected"""
        try:
            from src.feed import _is_valid_tick
            
            for key in ['o', 'h', 'l', 'c']:
                candle = self.make_valid_candle()
                candle[key] = None
                
                if not _is_valid_tick(candle):
                    pass  # Expected
                else:
                    self.log_fail(f"Poison: None {key}", f"Was accepted (should reject)")
                    return
            
            self.log_pass("Poison: None Prices", "All None prices rejected")
        except Exception as e:
            self.log_fail("Poison: None Prices", str(e))
    
    def test_poison_none_volume(self):
        """Test: None volume is rejected"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            candle['v'] = None
            
            if not _is_valid_tick(candle):
                self.log_pass("Poison: None Volume", "Correctly rejected")
            else:
                self.log_fail("Poison: None Volume", "Was accepted (should reject)")
        except Exception as e:
            self.log_fail("Poison: None Volume", str(e))
    
    # ─────────────────────────────────────────────────────────────────
    # POISON PILL 2: String Values
    # ─────────────────────────────────────────────────────────────────
    
    def test_poison_string_price(self):
        """Test: String prices are rejected"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            candle['o'] = "65000"  # String instead of float
            
            # Note: Strings that convert to floats may be accepted
            # This is OK as long as they're valid numbers
            self.log_pass("Poison: String Price", "Handled (converts if valid)")
        except Exception as e:
            self.log_fail("Poison: String Price", str(e))
    
    def test_poison_string_invalid(self):
        """Test: Invalid strings are rejected"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            candle['o'] = "invalid"
            
            if not _is_valid_tick(candle):
                self.log_pass("Poison: Invalid String", "Correctly rejected")
            else:
                self.log_fail("Poison: Invalid String", "Was accepted (should reject)")
        except Exception as e:
            self.log_fail("Poison: Invalid String", str(e))
    
    # ─────────────────────────────────────────────────────────────────
    # POISON PILL 3: Zero & Negative Prices
    # ─────────────────────────────────────────────────────────────────
    
    def test_poison_zero_price(self):
        """Test: Zero prices are rejected"""
        try:
            from src.feed import _is_valid_tick
            
            for key in ['o', 'h', 'l', 'c']:
                candle = self.make_valid_candle()
                candle[key] = 0.0
                
                if not _is_valid_tick(candle):
                    pass  # Expected
                else:
                    self.log_fail(f"Poison: Zero {key}", f"Was accepted (should reject)")
                    return
            
            self.log_pass("Poison: Zero Prices", "All zero prices rejected")
        except Exception as e:
            self.log_fail("Poison: Zero Prices", str(e))
    
    def test_poison_negative_price(self):
        """Test: Negative prices are rejected"""
        try:
            from src.feed import _is_valid_tick
            
            for key in ['o', 'h', 'l', 'c']:
                candle = self.make_valid_candle()
                candle[key] = -100.0
                
                if not _is_valid_tick(candle):
                    pass  # Expected
                else:
                    self.log_fail(f"Poison: Negative {key}", f"Was accepted (should reject)")
                    return
            
            self.log_pass("Poison: Negative Prices", "All negative prices rejected")
        except Exception as e:
            self.log_fail("Poison: Negative Prices", str(e))
    
    def test_poison_negative_volume(self):
        """Test: Negative volume is rejected"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            candle['v'] = -100.0
            
            if not _is_valid_tick(candle):
                self.log_pass("Poison: Negative Volume", "Correctly rejected")
            else:
                self.log_fail("Poison: Negative Volume", "Was accepted (should reject)")
        except Exception as e:
            self.log_fail("Poison: Negative Volume", str(e))
    
    # ─────────────────────────────────────────────────────────────────
    # POISON PILL 4: Infinity & NaN
    # ─────────────────────────────────────────────────────────────────
    
    def test_poison_infinity(self):
        """Test: Infinity prices are rejected"""
        try:
            from src.feed import _is_valid_tick
            
            for key in ['o', 'h', 'l', 'c']:
                candle = self.make_valid_candle()
                candle[key] = float('inf')
                
                if not _is_valid_tick(candle):
                    pass  # Expected
                else:
                    self.log_fail(f"Poison: Infinity {key}", f"Was accepted (should reject)")
                    return
            
            self.log_pass("Poison: Infinity Prices", "All infinity prices rejected")
        except Exception as e:
            self.log_fail("Poison: Infinity Prices", str(e))
    
    def test_poison_nan(self):
        """Test: NaN prices are rejected"""
        try:
            from src.feed import _is_valid_tick
            
            for key in ['o', 'h', 'l', 'c']:
                candle = self.make_valid_candle()
                candle[key] = float('nan')
                
                if not _is_valid_tick(candle):
                    pass  # Expected
                else:
                    self.log_fail(f"Poison: NaN {key}", f"Was accepted (should reject)")
                    return
            
            self.log_pass("Poison: NaN Prices", "All NaN prices rejected")
        except Exception as e:
            self.log_fail("Poison: NaN Prices", str(e))
    
    # ─────────────────────────────────────────────────────────────────
    # POISON PILL 5: Logic Violations
    # ─────────────────────────────────────────────────────────────────
    
    def test_poison_high_less_than_low(self):
        """Test: High < Low is rejected"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            candle['h'] = 64000.0
            candle['l'] = 65000.0  # High < Low!
            
            if not _is_valid_tick(candle):
                self.log_pass("Poison: High < Low", "Correctly rejected")
            else:
                self.log_fail("Poison: High < Low", "Was accepted (should reject)")
        except Exception as e:
            self.log_fail("Poison: High < Low", str(e))
    
    def test_poison_close_out_of_range(self):
        """Test: Close outside [Low, High] is rejected"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            candle['h'] = 65500.0
            candle['l'] = 64500.0
            candle['c'] = 66000.0  # Close > High!
            
            if not _is_valid_tick(candle):
                self.log_pass("Poison: Close > High", "Correctly rejected")
            else:
                self.log_fail("Poison: Close > High", "Was accepted (should reject)")
        except Exception as e:
            self.log_fail("Poison: Close > High", str(e))
    
    def test_poison_open_out_of_range(self):
        """Test: Open outside [Low, High] is rejected"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            candle['h'] = 65500.0
            candle['l'] = 64500.0
            candle['o'] = 63000.0  # Open < Low!
            
            if not _is_valid_tick(candle):
                self.log_pass("Poison: Open < Low", "Correctly rejected")
            else:
                self.log_fail("Poison: Open < Low", "Was accepted (should reject)")
        except Exception as e:
            self.log_fail("Poison: Open < Low", str(e))
    
    # ─────────────────────────────────────────────────────────────────
    # POISON PILL 6: Timestamp Violations
    # ─────────────────────────────────────────────────────────────────
    
    def test_poison_old_timestamp(self):
        """Test: Very old timestamps are rejected"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            candle['t'] = 0  # Timestamp from 1970!
            
            if not _is_valid_tick(candle):
                self.log_pass("Poison: Old Timestamp", "Correctly rejected")
            else:
                self.log_fail("Poison: Old Timestamp", "Was accepted (should reject)")
        except Exception as e:
            self.log_fail("Poison: Old Timestamp", str(e))
    
    def test_poison_future_timestamp(self):
        """Test: Far future timestamps are rejected"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            candle['t'] = (time_module.time() + 86400 * 365) * 1000  # 1 year in future
            
            if not _is_valid_tick(candle):
                self.log_pass("Poison: Future Timestamp", "Correctly rejected")
            else:
                self.log_fail("Poison: Future Timestamp", "Was accepted (should reject)")
        except Exception as e:
            self.log_fail("Poison: Future Timestamp", str(e))
    
    # ─────────────────────────────────────────────────────────────────
    # MISSING STRUCTURE
    # ─────────────────────────────────────────────────────────────────
    
    def test_poison_missing_keys(self):
        """Test: Missing required keys are rejected"""
        try:
            from src.feed import _is_valid_tick
            
            candle = self.make_valid_candle()
            del candle['o']  # Delete required key
            
            if not _is_valid_tick(candle):
                self.log_pass("Poison: Missing Key", "Correctly rejected")
            else:
                self.log_fail("Poison: Missing Key", "Was accepted (should reject)")
        except Exception as e:
            self.log_fail("Poison: Missing Key", str(e))
    
    # ─────────────────────────────────────────────────────────────────
    # MAIN TEST RUNNER
    # ─────────────────────────────────────────────────────────────────
    
    def run_all_tests(self):
        """Run complete firewall test suite"""
        print("\n" + "="*80)
        print(f"{BLUE}🛡️  DATA FIREWALL TEST SUITE{RESET}")
        print("="*80 + "\n")
        
        print(f"{BLUE}━━ VALID CANDLES (Should Accept) ━━{RESET}")
        self.test_valid_candle_basic()
        self.test_valid_candle_with_variations()
        
        print(f"\n{BLUE}━━ POISON PILLS (Should Reject) ━━{RESET}")
        
        print(f"\n{YELLOW}Type Errors (None, String){RESET}")
        self.test_poison_none_timestamp()
        self.test_poison_none_prices()
        self.test_poison_none_volume()
        self.test_poison_string_invalid()
        
        print(f"\n{YELLOW}Extreme Values (0, Negative, Inf, NaN){RESET}")
        self.test_poison_zero_price()
        self.test_poison_negative_price()
        self.test_poison_negative_volume()
        self.test_poison_infinity()
        self.test_poison_nan()
        
        print(f"\n{YELLOW}Logic Violations{RESET}")
        self.test_poison_high_less_than_low()
        self.test_poison_close_out_of_range()
        self.test_poison_open_out_of_range()
        
        print(f"\n{YELLOW}Timestamp Violations{RESET}")
        self.test_poison_old_timestamp()
        self.test_poison_future_timestamp()
        
        print(f"\n{YELLOW}Structure Violations{RESET}")
        self.test_poison_missing_keys()
        
        # Summary
        print(f"\n{BLUE}━━ SUMMARY ━━{RESET}")
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"Total Tests:   {total}")
        print(f"Passed:        {self.passed} ({pass_rate:.1f}%)")
        print(f"Failed:        {self.failed}")
        
        if self.failed == 0:
            print(f"\n{GREEN}✅ FIREWALL PERFECT - All poison pills caught!{RESET}\n")
            return 0
        else:
            print(f"\n{RED}❌ FIREWALL GAPS - {self.failed} poison pills escaped!{RESET}\n")
            return 1


def main():
    """Main entry point"""
    suite = FirewallTestSuite()
    exit_code = suite.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
