"""
🔍 Data Integrity Check - Verify Cache Quality
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: Verify that cached parquet files are readable and have correct schema
"""

import os
import logging
from typing import Tuple, List
import polars as pl

logger = logging.getLogger(__name__)


class IntegrityChecker:
    """Verify data/ folder and parquet files"""
    
    EXPECTED_SCHEMA = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
    @staticmethod
    def check_data_folder(data_dir: str = "data") -> Tuple[bool, List[str]]:
        """
        Check if data folder exists and is accessible
        
        Returns:
            (success: bool, errors: list[str])
        """
        errors = []
        
        if not os.path.exists(data_dir):
            logger.warning(f"⚠️ Data folder does not exist: {data_dir}")
            errors.append(f"Missing data folder: {data_dir}")
            return False, errors
        
        if not os.path.isdir(data_dir):
            logger.error(f"❌ Path is not a directory: {data_dir}")
            errors.append(f"Path is not a directory: {data_dir}")
            return False, errors
        
        logger.info(f"✅ Data folder exists: {data_dir}")
        return True, errors
    
    @staticmethod
    def check_parquet_file(filepath: str) -> Tuple[bool, List[str]]:
        """
        Check if parquet file is readable and has correct schema
        
        Returns:
            (success: bool, errors: list[str])
        """
        errors = []
        
        if not os.path.exists(filepath):
            errors.append(f"File not found: {filepath}")
            return False, errors
        
        try:
            # Try to read parquet
            df = pl.read_parquet(filepath)
            logger.debug(f"✅ Parquet readable: {filepath}")
        except Exception as e:
            errors.append(f"Cannot read parquet: {filepath} - {str(e)}")
            return False, errors
        
        # Check schema
        actual_columns = df.columns
        for expected_col in IntegrityChecker.EXPECTED_SCHEMA:
            if expected_col not in actual_columns:
                errors.append(f"Missing column '{expected_col}' in {filepath}")
        
        if errors:
            return False, errors
        
        logger.info(f"✅ Parquet valid: {filepath} ({len(df)} rows)")
        return True, errors
    
    @staticmethod
    def check_all_parquets(data_dir: str = "data") -> Tuple[int, int, List[str]]:
        """
        Check all parquet files in data folder
        
        Returns:
            (total_files: int, valid_files: int, errors: list[str])
        """
        errors = []
        
        # Check folder first
        folder_ok, folder_errors = IntegrityChecker.check_data_folder(data_dir)
        if not folder_ok:
            return 0, 0, folder_errors
        
        # List all parquet files
        parquet_files = [
            os.path.join(data_dir, f) for f in os.listdir(data_dir)
            if f.endswith('.parquet')
        ]
        
        total = len(parquet_files)
        valid = 0
        
        for filepath in parquet_files:
            success, file_errors = IntegrityChecker.check_parquet_file(filepath)
            if success:
                valid += 1
            else:
                errors.extend(file_errors)
        
        return total, valid, errors


def run_integrity_check():
    """Run complete integrity check"""
    print("\n" + "="*80)
    print("🔍 DATA INTEGRITY CHECK")
    print("="*80 + "\n")
    
    checker = IntegrityChecker()
    
    # Check folder
    folder_ok, folder_errors = checker.check_data_folder()
    if folder_ok:
        print("✅ Data folder: OK\n")
    else:
        print("❌ Data folder issues:")
        for error in folder_errors:
            print(f"   - {error}")
        print()
    
    # Check parquet files
    total, valid, errors = checker.check_all_parquets()
    
    print(f"📊 Parquet files: {valid}/{total} valid")
    
    if errors:
        print("\n⚠️ Issues found:")
        for error in errors:
            print(f"   - {error}")
    else:
        print("✅ All parquet files valid\n")
    
    print("="*80)
    if folder_ok and len(errors) == 0:
        print("✅ INTEGRITY CHECK PASSED")
    else:
        print("❌ INTEGRITY CHECK FAILED")
    print("="*80 + "\n")
    
    return folder_ok and len(errors) == 0


if __name__ == "__main__":
    import sys
    success = run_integrity_check()
    sys.exit(0 if success else 1)
