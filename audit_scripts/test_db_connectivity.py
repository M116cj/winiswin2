#!/usr/bin/env python3
"""
🧪 Database Reliability Engineer (DBRE) - Connectivity & Functional Test
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 2: CONNECTION & FUNCTIONAL TEST (Dry Run)
Tests actual database connectivity and measures latency
"""

import asyncio
import sys
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_db_connectivity():
    """Test database connectivity"""
    print("\n" + "╔" + "="*78 + "╗")
    print("║" + " "*10 + "🧪 DATABASE RELIABILITY ENGINEER - FUNCTIONAL TEST PHASE 2" + " "*9 + "║")
    print("╚" + "="*78 + "╝")
    
    results = {
        'postgres_available': False,
        'redis_available': False,
        'postgres_latency_ms': None,
        'redis_latency_ms': None,
    }
    
    try:
        sys.path.insert(0, '/home/runner/workspace')
        from src.database.unified_database_manager import UnifiedDatabaseManager
        
        print("\n" + "="*80)
        print("TEST 1: Initialize UnifiedDatabaseManager")
        print("="*80)
        
        try:
            db_manager = UnifiedDatabaseManager()
            print("✅ Database manager instantiated")
        except Exception as e:
            print(f"❌ Failed to instantiate: {e}")
            return results
        
        # Initialize PostgreSQL
        print("\n" + "="*80)
        print("TEST 2: PostgreSQL Connection")
        print("="*80)
        
        try:
            await db_manager.initialize_postgres()
            results['postgres_available'] = True
            print("✅ PostgreSQL pool initialized")
            
            # Test latency
            start = time.time()
            async with db_manager.pg_pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            latency = (time.time() - start) * 1000
            results['postgres_latency_ms'] = latency
            
            if latency < 10:
                print(f"✅ PostgreSQL latency: {latency:.2f} ms (EXCELLENT)")
            elif latency < 50:
                print(f"✅ PostgreSQL latency: {latency:.2f} ms (GOOD)")
            else:
                print(f"⚠️ PostgreSQL latency: {latency:.2f} ms (SLOW)")
        
        except Exception as e:
            print(f"⚠️ PostgreSQL connection failed: {e}")
            print("   (This is expected if no database is configured)")
            results['postgres_available'] = False
        
        # Initialize Redis (optional)
        print("\n" + "="*80)
        print("TEST 3: Redis Connection")
        print("="*80)
        
        try:
            await db_manager.initialize_redis()
            
            if db_manager.redis_client:
                results['redis_available'] = True
                print("✅ Redis client initialized")
                
                # Test latency
                start = time.time()
                await db_manager.redis_client.ping()
                latency = (time.time() - start) * 1000
                results['redis_latency_ms'] = latency
                
                if latency < 10:
                    print(f"✅ Redis latency: {latency:.2f} ms (EXCELLENT)")
                elif latency < 50:
                    print(f"✅ Redis latency: {latency:.2f} ms (GOOD)")
                else:
                    print(f"⚠️ Redis latency: {latency:.2f} ms (SLOW)")
            else:
                print("ℹ️ Redis not configured (optional)")
                results['redis_available'] = False
        
        except Exception as e:
            print(f"ℹ️ Redis connection not available: {e}")
            results['redis_available'] = False
        
        # Test AccountStateCache
        print("\n" + "="*80)
        print("TEST 4: AccountStateCache Functionality")
        print("="*80)
        
        try:
            from src.core.account_state_cache import AccountStateCache
            
            cache = AccountStateCache()
            
            # Test update
            cache.update_balance('USDT', 1000.0, 100.0)
            balance = cache.get_balance('USDT')
            
            if balance and balance['total'] == 1100.0:
                print("✅ AccountStateCache working correctly")
            else:
                print(f"⚠️ AccountStateCache returned: {balance}")
        
        except Exception as e:
            print(f"⚠️ AccountStateCache test failed: {e}")
        
        # Cleanup
        print("\n" + "="*80)
        print("TEST 5: Cleanup")
        print("="*80)
        
        try:
            if db_manager.pg_pool:
                await db_manager.pg_pool.close()
                print("✅ PostgreSQL pool closed")
            
            if db_manager.redis_client:
                await db_manager.redis_client.close()
                print("✅ Redis client closed")
        
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Print results
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    print(f"\nPostgreSQL Available: {'✅ YES' if results['postgres_available'] else '⚠️ NO'}")
    if results['postgres_latency_ms']:
        print(f"PostgreSQL Latency: {results['postgres_latency_ms']:.2f} ms")
    
    print(f"\nRedis Available: {'✅ YES' if results['redis_available'] else '⚠️ NO'}")
    if results['redis_latency_ms']:
        print(f"Redis Latency: {results['redis_latency_ms']:.2f} ms")
    
    print("\n" + "="*80)
    print("✅ CONNECTIVITY TEST COMPLETE")
    print("="*80 + "\n")
    
    return results

if __name__ == "__main__":
    asyncio.run(test_db_connectivity())
