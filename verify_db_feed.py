#!/usr/bin/env python3
"""
🔍 Market Data Feed Health & Integrity Check
Diagnostic script to verify PostgreSQL market_data table ingestion
Uses optimized SQL queries for health monitoring without dumping raw data
"""

import asyncio
import asyncpg
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from src.config import get_database_url


class MarketDataHealthCheck:
    """Health check for market_data table feed ingestion"""
    
    def __init__(self):
        self.db_url = get_database_url()
        self.conn = None
        self.health_status = {
            'total_symbols': 0,
            'total_records': 0,
            'symbols_data': {},
            'latency_issues': [],
            'data_quality_issues': [],
            'throughput_info': {}
        }
    
    async def connect(self):
        """Connect to PostgreSQL"""
        try:
            self.conn = await asyncpg.connect(self.db_url)
            print("✅ Connected to PostgreSQL\n")
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            sys.exit(1)
    
    async def disconnect(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()
    
    async def get_data_freshness(self) -> Dict:
        """
        Calculate data freshness (latency) for each symbol
        Returns: Dict with max_timestamp, lag_seconds, status
        """
        try:
            result = await self.conn.fetch("""
                SELECT 
                    symbol,
                    MAX(timestamp) as max_timestamp,
                    COUNT(*) as row_count,
                    MAX(created_at) as created_at
                FROM market_data
                GROUP BY symbol
                ORDER BY MAX(timestamp) DESC
            """)
            
            now_ms = int(datetime.now().timestamp() * 1000)
            freshness_data = {}
            
            for row in result:
                symbol = row['symbol']
                max_ts = row['max_timestamp']
                lag_ms = now_ms - max_ts
                lag_seconds = lag_ms / 1000.0
                
                # Determine status
                if lag_seconds > 2:
                    status = "⚠️ STALE"
                    self.health_status['latency_issues'].append(
                        f"{symbol}: Lag {lag_seconds:.1f}s (> 2s threshold)"
                    )
                elif lag_seconds > 1:
                    status = "⚡ SLOW"
                else:
                    status = "✅ FRESH"
                
                # Convert timestamp to readable format
                ts_dt = datetime.fromtimestamp(max_ts / 1000)
                timestamp_str = ts_dt.strftime("%H:%M:%S")
                
                freshness_data[symbol] = {
                    'max_timestamp': max_ts,
                    'timestamp_str': timestamp_str,
                    'lag_seconds': lag_seconds,
                    'status': status,
                    'row_count': row['row_count']
                }
            
            return freshness_data
        
        except Exception as e:
            print(f"❌ Error in get_data_freshness: {e}")
            return {}
    
    async def get_ingestion_rate(self) -> Dict:
        """
        Calculate ingestion rate (throughput) for last 1 min and 5 min
        Returns: Dict with rates per symbol
        """
        try:
            now_ms = int(datetime.now().timestamp() * 1000)
            one_min_ago_ms = now_ms - (60 * 1000)
            five_min_ago_ms = now_ms - (5 * 60 * 1000)
            
            result = await self.conn.fetch("""
                SELECT 
                    symbol,
                    SUM(CASE WHEN timestamp >= $1 THEN 1 ELSE 0 END) as count_1min,
                    SUM(CASE WHEN timestamp >= $2 THEN 1 ELSE 0 END) as count_5min
                FROM market_data
                GROUP BY symbol
                ORDER BY symbol
            """, one_min_ago_ms, five_min_ago_ms)
            
            rate_data = {}
            for row in result:
                symbol = row['symbol']
                count_1min = row['count_1min'] or 0
                count_5min = row['count_5min'] or 0
                
                rate_data[symbol] = {
                    'count_1min': count_1min,
                    'count_5min': count_5min,
                    'rate_per_sec_1min': count_1min / 60.0 if count_1min > 0 else 0
                }
            
            return rate_data
        
        except Exception as e:
            print(f"❌ Error in get_ingestion_rate: {e}")
            return {}
    
    async def get_data_integrity(self) -> Dict:
        """
        Check for NULL or 0 values in critical columns
        Critical columns: open_price, close_price, volume
        """
        try:
            # Check for NULL values
            null_check = await self.conn.fetch("""
                SELECT 
                    symbol,
                    SUM(CASE WHEN open_price IS NULL THEN 1 ELSE 0 END) as null_open,
                    SUM(CASE WHEN close_price IS NULL THEN 1 ELSE 0 END) as null_close,
                    SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) as null_volume,
                    SUM(CASE WHEN open_price = 0 THEN 1 ELSE 0 END) as zero_open,
                    SUM(CASE WHEN close_price = 0 THEN 1 ELSE 0 END) as zero_close,
                    SUM(CASE WHEN volume = 0 THEN 1 ELSE 0 END) as zero_volume,
                    COUNT(*) as total_rows
                FROM market_data
                GROUP BY symbol
                ORDER BY symbol
            """)
            
            integrity_data = {}
            total_bad_rows = 0
            
            for row in null_check:
                symbol = row['symbol']
                null_count = (row['null_open'] or 0) + (row['null_close'] or 0) + (row['null_volume'] or 0)
                zero_count = (row['zero_open'] or 0) + (row['zero_close'] or 0) + (row['zero_volume'] or 0)
                bad_count = null_count + zero_count
                
                if bad_count > 0:
                    self.health_status['data_quality_issues'].append(
                        f"{symbol}: {bad_count} bad records (NULL: {null_count}, ZERO: {zero_count})"
                    )
                    total_bad_rows += bad_count
                
                integrity_data[symbol] = {
                    'null_count': null_count,
                    'zero_count': zero_count,
                    'bad_count': bad_count,
                    'total_rows': row['total_rows'],
                    'data_quality_pct': ((row['total_rows'] - bad_count) / row['total_rows'] * 100) if row['total_rows'] > 0 else 0
                }
            
            return integrity_data
        
        except Exception as e:
            print(f"❌ Error in get_data_integrity: {e}")
            return {}
    
    async def get_symbol_coverage(self) -> List[str]:
        """
        Get all distinct symbols currently being updated
        """
        try:
            result = await self.conn.fetch("""
                SELECT DISTINCT symbol 
                FROM market_data
                ORDER BY symbol
            """)
            
            symbols = [row['symbol'] for row in result]
            self.health_status['total_symbols'] = len(symbols)
            return symbols
        
        except Exception as e:
            print(f"❌ Error in get_symbol_coverage: {e}")
            return []
    
    async def get_total_records(self) -> int:
        """Get total record count"""
        try:
            result = await self.conn.fetchval("SELECT COUNT(*) FROM market_data")
            return result or 0
        except Exception as e:
            print(f"❌ Error in get_total_records: {e}")
            return 0
    
    async def run_health_check(self) -> None:
        """Run complete health check"""
        await self.connect()
        
        print("=" * 120)
        print("🔍 MARKET DATA FEED HEALTH & INTEGRITY CHECK")
        print("=" * 120)
        print()
        
        # Get data
        symbols = await self.get_symbol_coverage()
        total_records = await self.get_total_records()
        freshness_data = await self.get_data_freshness()
        rate_data = await self.get_ingestion_rate()
        integrity_data = await self.get_data_integrity()
        
        self.health_status['total_records'] = total_records
        
        # Print dashboard header
        print(f"📊 System Statistics")
        print(f"  • Total Symbols: {len(symbols)}")
        print(f"  • Total Records: {total_records:,}")
        print()
        
        # Print symbol coverage
        print(f"🎯 Symbol Coverage ({len(symbols)} symbols):")
        for symbol in symbols:
            print(f"   {symbol}")
        print()
        
        # Print per-symbol dashboard
        print("=" * 120)
        print("SYMBOL HEALTH DASHBOARD")
        print("=" * 120)
        print()
        
        # Header
        header = f"{'Symbol':<15} {'Latest':<12} {'Lag(s)':<10} {'1min':<8} {'5min':<8} {'Bad Data':<12} {'Quality':<10} {'Status':<12}"
        print(header)
        print("-" * 120)
        
        # Per-symbol metrics
        for symbol in sorted(symbols):
            freshness = freshness_data.get(symbol, {})
            rate = rate_data.get(symbol, {})
            integrity = integrity_data.get(symbol, {})
            
            timestamp_str = freshness.get('timestamp_str', 'N/A')
            lag_s = freshness.get('lag_seconds', 0)
            status = freshness.get('status', '?')
            count_1min = rate.get('count_1min', 0)
            count_5min = rate.get('count_5min', 0)
            bad_count = integrity.get('bad_count', 0)
            quality_pct = integrity.get('data_quality_pct', 0)
            
            # Format row
            row = f"{symbol:<15} {timestamp_str:<12} {lag_s:<10.2f} {count_1min:<8} {count_5min:<8} {bad_count:<12} {quality_pct:<10.1f}% {status:<12}"
            print(row)
        
        print()
        print("=" * 120)
        print("📋 ISSUES & ALERTS")
        print("=" * 120)
        print()
        
        # Print issues
        if self.health_status['latency_issues']:
            print("⚠️ LATENCY ISSUES (lag > 2s):")
            for issue in self.health_status['latency_issues']:
                print(f"   • {issue}")
            print()
        
        if self.health_status['data_quality_issues']:
            print("❌ DATA QUALITY ISSUES:")
            for issue in self.health_status['data_quality_issues']:
                print(f"   • {issue}")
            print()
        
        if not self.health_status['latency_issues'] and not self.health_status['data_quality_issues']:
            print("✅ NO CRITICAL ISSUES DETECTED")
            print()
        
        # Print summary
        print("=" * 120)
        print("📈 SUMMARY")
        print("=" * 120)
        print()
        print(f"✅ Data Freshness: {'HEALTHY' if not self.health_status['latency_issues'] else 'DEGRADED'}")
        print(f"✅ Data Quality: {'HEALTHY' if not self.health_status['data_quality_issues'] else 'DEGRADED'}")
        print(f"✅ Ingestion Rate: ACTIVE ({total_records:,} records tracked)")
        print()
        
        await self.disconnect()


async def main():
    """Main entry point"""
    health_check = MarketDataHealthCheck()
    await health_check.run_health_check()


if __name__ == "__main__":
    asyncio.run(main())
