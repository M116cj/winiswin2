"""
🔍 DEBUG UNIVERSE - Deep Symbol Discovery Analysis
Step-by-step filtering analysis to find where 300+ pairs are lost
"""

import asyncio
import logging
import ccxt.async_support as ccxt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def debug_universe():
    """Analyze filtering at each step"""
    logger.info("=" * 80)
    logger.info("🔍 DEEP UNIVERSE ANALYSIS - Finding Symbol Discovery Issue")
    logger.info("=" * 80)
    
    try:
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'rateLimit': 50,
        })
        
        logger.info("\n📡 Step 1: Loading ALL markets from Binance...")
        await exchange.load_markets()
        
        # Step 1: Get all symbols
        logger.info("\n📊 Step 1: Raw symbols from exchange.symbols")
        all_symbols = exchange.symbols or []
        logger.info(f"   Total symbols: {len(all_symbols)}")
        if all_symbols:
            logger.info(f"   First 5: {all_symbols[:5]}")
            logger.info(f"   Last 5: {all_symbols[-5:]}")
        
        # Step 2: Filter /USDT pairs
        logger.info("\n📊 Step 2: Filter by /USDT (USDT-margined)")
        usdt_pairs = [s for s in all_symbols if s.endswith('/USDT')]
        logger.info(f"   /USDT pairs: {len(usdt_pairs)}")
        if usdt_pairs:
            logger.info(f"   First 10: {usdt_pairs[:10]}")
            if len(usdt_pairs) > 10:
                logger.info(f"   Last 10: {usdt_pairs[-10:]}")
        
        # Step 3: Check for known altcoins
        logger.info("\n🔎 Step 3: Checking for known small-cap coins")
        small_caps_to_check = ["PEPE/USDT", "SHIB/USDT", "FLOKI/USDT", "DOGE/USDT", 
                               "BONK/USDT", "WIF/USDT", "MOG/USDT"]
        found = [s for s in usdt_pairs if s in small_caps_to_check]
        logger.info(f"   Small-caps found: {len(found)}")
        if found:
            logger.info(f"   Examples: {found}")
        else:
            logger.warning("   ❌ No small-caps found - API might be restricted")
        
        # Step 4: Look for other patterns
        logger.info("\n🔎 Step 4: Checking for futures-specific patterns")
        logger.info(f"   Sample symbols: {usdt_pairs[:20] if usdt_pairs else 'NONE'}")
        
        # Step 5: Fallback list comparison
        logger.info("\n📋 Step 5: Fallback list comparison")
        fallback = [
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "SOL/USDT",
            "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "MATIC/USDT",
        ]
        found_fallback = [s for s in fallback if s in usdt_pairs]
        logger.info(f"   Fallback pairs found: {len(found_fallback)}/{len(fallback)}")
        
        # Final Result
        logger.info("\n" + "=" * 80)
        logger.info("📊 DIAGNOSTIC RESULT")
        logger.info("=" * 80)
        logger.info(f"✅ Total /USDT pairs discovered: {len(usdt_pairs)}")
        logger.info(f"✅ Status: {'PASS - 250+ pairs found!' if len(usdt_pairs) > 250 else 'WARNING - Check API access'}")
        
        if len(usdt_pairs) == 0:
            logger.error("❌ CRITICAL: No pairs discovered - API likely blocked or failing")
            return False
        elif len(usdt_pairs) < 50:
            logger.warning(f"⚠️  Only {len(usdt_pairs)} pairs (expected 250+)")
            logger.warning("   This suggests API is returning limited data or geo-blocking")
            return False
        else:
            logger.info(f"✅ Discovery working! {len(usdt_pairs)} USDT perpetuals available")
            return True
    
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        if "451" in str(e):
            logger.error("API Blocking: HTTP 451 - Service unavailable from restricted location")
        elif "418" in str(e):
            logger.error("API Rate Limit: HTTP 418 - Too many requests")
        elif "429" in str(e):
            logger.error("API Rate Limit: HTTP 429 - Rate limited")
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(debug_universe())
        exit(0 if result else 1)
    except Exception as e:
        logger.error(f"Fatal: {e}", exc_info=True)
        exit(1)
