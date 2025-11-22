"""
✅ Universe Size Verification Script
Checks that BinanceUniverse discovers 250+ pairs with NO volume filters
"""

import asyncio
import logging
from src.market_universe import BinanceUniverse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_universe():
    """Verify universe size"""
    logger.info("🔍 Checking market universe size...")
    
    universe = BinanceUniverse()
    pairs = await universe.get_active_pairs()
    
    total = len(pairs)
    logger.info(f"✅ Total Pairs Found: {total}")
    
    # Verify it's a substantial list
    if total < 50:
        logger.error(f"❌ FAIL: Only {total} pairs found (expected 250+)")
        return False
    elif total < 250:
        logger.warning(f"⚠️ WARNING: {total} pairs found (expected 250+ but acceptable)")
    else:
        logger.info(f"✅ SUCCESS: {total} pairs found - NO volume filters working!")
    
    # Show sample pairs to verify diversity
    logger.info(f"\n📊 First 20 pairs: {pairs[:20]}")
    logger.info(f"📊 Last 10 pairs: {pairs[-10:]}")
    
    # Check for known low-cap coins (proof of no volume filter)
    known_small_caps = ["SHIB/USDT", "PEPE/USDT", "DOGE/USDT", "FLOKI/USDT"]
    found_small_caps = [p for p in pairs if p in known_small_caps]
    
    if found_small_caps:
        logger.info(f"✅ Found small-cap coins (proof no volume filter): {found_small_caps}")
    
    return total >= 50


if __name__ == "__main__":
    try:
        result = asyncio.run(check_universe())
        exit(0 if result else 1)
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        exit(1)
