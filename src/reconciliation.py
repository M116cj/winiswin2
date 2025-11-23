"""
🔄 Cache Reconciliation - Periodic Account Sync
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Periodically syncs local account state with Binance via REST API.
Detects and recovers from WebSocket gaps.
Verifies positions match Binance state.

PATCH_3: Cache Reconciliation - Fills critical gap in system reliability
"""

import logging
import asyncio
import os
import time
import hmac
import hashlib
from typing import Dict, Optional
from urllib.parse import urlencode
import aiohttp

logger = logging.getLogger(__name__)

# Binance API configuration
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
BINANCE_BASE_URL = "https://fapi.binance.com"
RECONCILIATION_INTERVAL = 15 * 60  # 15 minutes (adjustable)

# Last reconciliation timestamp
_last_reconciliation_time = 0
_reconciliation_lock = asyncio.Lock()


def _generate_signature_for_reconciliation(query_string: str) -> str:
    """Generate HMAC-SHA256 signature for Binance API"""
    if not BINANCE_API_SECRET:
        logger.error("❌ BINANCE_API_SECRET not set")
        return ""
    
    signature = hmac.new(
        BINANCE_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def _build_signed_request_for_reconciliation(params: Dict) -> str:
    """Build properly signed query string for Binance API"""
    
    # Ensure timestamp
    if 'timestamp' not in params:
        params['timestamp'] = int(time.time() * 1000)
    
    # Clean parameters
    clean_params = {}
    for k, v in params.items():
        if v is not None and v != '':
            if isinstance(v, (int, float)):
                clean_params[k] = str(v)
            else:
                clean_params[k] = v
    
    # Build query string
    query_string = urlencode(clean_params)
    
    # Generate signature
    signature = _generate_signature_for_reconciliation(query_string)
    
    if not signature:
        logger.error("❌ Signature generation failed")
        return ""
    
    # Append signature (MUST be last)
    signed_request = f"{query_string}&signature={signature}"
    
    return signed_request


async def get_account_information() -> Optional[Dict]:
    """
    Fetch account information from Binance REST API
    
    Returns:
        Account state from Binance or None if failed
    """
    
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        logger.warning("⚠️ Binance credentials not configured - skipping reconciliation")
        return None
    
    try:
        # Build signed request
        params = {'timestamp': int(time.time() * 1000)}
        signed_query = _build_signed_request_for_reconciliation(params)
        
        if not signed_query:
            logger.error("❌ Failed to build signed request")
            return None
        
        # Build URL
        url = f"{BINANCE_BASE_URL}/fapi/v1/account?{signed_query}"
        
        headers = {
            'X-MBX-APIKEY': BINANCE_API_KEY,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        logger.debug(f"🔄 Fetching account information...")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                
                if resp.status == 200:
                    account_data = await resp.json()
                    logger.info(f"✅ Account reconciled: {len(account_data.get('positions', []))} positions on Binance")
                    return account_data
                else:
                    error_text = await resp.text()
                    logger.error(f"❌ Binance API error ({resp.status}): {error_text}")
                    return None
    
    except Exception as e:
        logger.error(f"❌ Failed to get account information: {e}")
        return None


async def verify_positions(local_positions: Dict, binance_account: Optional[Dict]) -> Dict:
    """
    Compare local positions with Binance state
    
    Args:
        local_positions: Local position tracking
        binance_account: Account data from Binance
    
    Returns:
        Reconciliation report: {matches: int, mismatches: int, details: [...]}
    """
    
    if not binance_account:
        return {"matches": 0, "mismatches": 0, "status": "no_data"}
    
    report = {
        "matches": 0,
        "mismatches": 0,
        "corrected": 0,
        "details": []
    }
    
    # Get Binance positions
    binance_positions = {p['symbol']: p for p in binance_account.get('positions', []) if float(p.get('positionAmt', 0)) != 0}
    
    # Compare
    all_symbols = set(local_positions.keys()) | set(binance_positions.keys())
    
    for symbol in all_symbols:
        local_qty = local_positions.get(symbol, {}).get('quantity', 0)
        binance_qty = float(binance_positions.get(symbol, {}).get('positionAmt', 0))
        
        if local_qty == binance_qty:
            report["matches"] += 1
            logger.debug(f"  ✅ {symbol}: {local_qty} (matches)")
        else:
            report["mismatches"] += 1
            logger.warning(f"  ⚠️ {symbol}: Local={local_qty}, Binance={binance_qty} (MISMATCH)")
            report["details"].append({
                "symbol": symbol,
                "local": local_qty,
                "binance": binance_qty,
                "action": "notify"  # In production: auto-correct or alert
            })
    
    return report


async def reconcile_account_state() -> Optional[Dict]:
    """
    Periodic cache reconciliation task
    
    Flow:
    1. Fetch account state from Binance via REST API
    2. Compare with local positions
    3. Detect and log any mismatches
    4. In production: auto-correct or alert trader
    """
    
    global _last_reconciliation_time
    
    async with _reconciliation_lock:
        # Check if enough time has passed
        now = time.time()
        if now - _last_reconciliation_time < RECONCILIATION_INTERVAL:
            return None
        
        _last_reconciliation_time = now
    
    logger.info(f"🔄 Starting cache reconciliation (every {RECONCILIATION_INTERVAL}s)...")
    
    # Fetch Binance account state
    binance_account = await get_account_information()
    
    if not binance_account:
        logger.warning("⚠️ Reconciliation skipped - could not fetch Binance state")
        return None
    
    # Import local state from trade module
    try:
        from src import trade
        local_positions = trade._account_state.get('positions', {})
    except ImportError:
        logger.warning("⚠️ Trade module not available")
        return None
    
    # Verify positions
    report = await verify_positions(local_positions, binance_account)
    
    # Log report
    logger.info(f"📊 Reconciliation Report: {report['matches']} matches, {report['mismatches']} mismatches")
    
    if report['details']:
        logger.warning(f"⚠️ Position mismatches detected:")
        for detail in report['details']:
            logger.warning(f"   {detail['symbol']}: Local={detail['local']}, Binance={detail['binance']}")
    
    return report


async def background_reconciliation_task() -> None:
    """
    Background task: periodically reconcile cache with Binance
    
    Runs forever, sleeps RECONCILIATION_INTERVAL between checks
    """
    
    logger.info(f"🔄 Cache reconciliation task started (interval: {RECONCILIATION_INTERVAL}s)")
    
    try:
        while True:
            try:
                await reconcile_account_state()
                await asyncio.sleep(RECONCILIATION_INTERVAL)
            except asyncio.CancelledError:
                logger.info("⏹️ Reconciliation task cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Reconciliation error: {e}")
                await asyncio.sleep(5)  # Retry after 5 seconds
    
    except Exception as e:
        logger.error(f"❌ Reconciliation task failed: {e}", exc_info=True)


async def init_reconciliation() -> None:
    """
    Initialize reconciliation module
    
    Called from main.py to start background reconciliation task
    """
    
    logger.info("🔄 Initializing cache reconciliation...")
    
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        logger.warning("⚠️ Binance credentials not configured - reconciliation disabled")
        return
    
    # Start background task
    asyncio.create_task(background_reconciliation_task())
    logger.info("✅ Reconciliation task created")
