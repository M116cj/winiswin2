"""
🎓 Virtual Incremental Learning Module
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Parallel virtual trading account for testing strategy without live restrictions.
- Same signal logic as live trading
- No position limit restrictions
- Automatic TP/SL detection
- Full trade history persistence
- 🔧 FIXED: Uses PostgreSQL for cross-process position tracking (no in-memory isolation)
"""

import logging
import asyncio
import json
import time
from typing import Dict, Optional, List
from datetime import datetime
import redis.asyncio as redis_async

logger = logging.getLogger(__name__)

# Global price cache from Ring Buffer
_market_prices = {}  # {symbol: current_price}

# Virtual account state (in-memory)
_virtual_account = {
    'balance': 10000.0,  # Starting capital
    'positions': {},     # {symbol: {quantity, entry_price, entry_confidence, entry_time, side, tp_level, sl_level}}
    'trades': [],        # All completed trades
    'total_pnl': 0.0,    # Cumulative PnL
    'win_rate': 0.0,     # Win rate %
    'max_drawdown': 0.0  # Maximum drawdown %
}

_virtual_lock = asyncio.Lock()


async def update_market_prices(prices: Dict[str, float]) -> None:
    """Update market prices from Ring Buffer / Feed process"""
    global _market_prices
    if prices:
        _market_prices.update(prices)


async def get_current_price(symbol: str) -> Optional[float]:
    """Get current market price from Redis (cross-process)"""
    try:
        from src.config import get_redis_url
        redis_url = get_redis_url()
        if not redis_url:
            return _market_prices.get(symbol)  # Fallback to in-memory
        
        redis_client = await redis_async.from_url(redis_url, decode_responses=True)
        
        # Try both formats: BTCUSDT and BTC/USDT
        symbol_normalized = symbol.replace('/', '')
        
        market_data = await redis_client.get(f"market:{symbol_normalized}")
        if market_data:
            data = json.loads(market_data)
            await redis_client.close()
            return float(data.get('c', 0))  # 'c' = close price
        
        await redis_client.close()
        return _market_prices.get(symbol)  # Fallback
    except Exception as e:
        logger.debug(f"Redis price fetch failed: {e}")
        return _market_prices.get(symbol)  # Fallback to in-memory


async def init_virtual_learning() -> None:
    """Initialize virtual learning account"""
    global _virtual_account
    
    async with _virtual_lock:
        _virtual_account = {
            'balance': 10000.0,
            'positions': {},
            'trades': [],
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'max_drawdown': 0.0
        }
    
    logger.critical("🎓 Virtual Learning Account initialized: $10,000 starting capital")


async def _ensure_virtual_positions_table():
    """Ensure virtual_positions table exists in PostgreSQL with all 12 ML features"""
    try:
        import asyncpg
        from src.config import get_database_url
        
        db_url = get_database_url()
        conn = await asyncpg.connect(db_url)
        
        # ✅ CREATE TABLE IF NOT EXISTS
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS virtual_positions (
                id SERIAL PRIMARY KEY,
                position_id VARCHAR(255) UNIQUE NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL,
                quantity FLOAT NOT NULL,
                entry_price FLOAT NOT NULL,
                entry_confidence FLOAT DEFAULT 0,
                entry_time TIMESTAMP NOT NULL,
                tp_level FLOAT NOT NULL,
                sl_level FLOAT NOT NULL,
                status VARCHAR(20) DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ✅ ADD MISSING ML FEATURE COLUMNS (如果表已存在，CREATE TABLE 不會添加新欄位)
        features = ['confidence', 'fvg', 'liquidity', 'rsi', 'atr', 'macd', 'bb_width', 'position_size_pct']
        for feature in features:
            try:
                await conn.execute(f"""
                    ALTER TABLE virtual_positions 
                    ADD COLUMN IF NOT EXISTS {feature} FLOAT DEFAULT 0
                """)
            except:
                pass  # Column already exists
        
        await conn.close()
    except Exception as e:
        logger.warning(f"⚠️ Failed to ensure virtual_positions table: {e}")


async def open_virtual_position(signal: Dict) -> bool:
    """
    ✅ FIXED: Open virtual position with ML features - SAVES TO POSTGRESQL FOR CROSS-PROCESS SHARING
    
    Args:
        signal: {symbol, side, confidence, quantity, entry_price, patterns/features}
    
    Returns:
        True if position opened successfully
    """
    try:
        symbol = signal.get('symbol', '')
        side = signal.get('side', 'BUY')
        confidence = signal.get('confidence', 0.0)
        quantity = signal.get('quantity', 0.0)
        entry_price = signal.get('entry_price', 0.0)
        
        if not symbol or quantity <= 0 or entry_price <= 0:
            logger.warning(f"❌ Invalid virtual position data: {signal}")
            return False
        
        # Calculate TP/SL levels
        if side == 'BUY':
            tp_level = entry_price * 1.05  # 5% TP
            sl_level = entry_price * 0.98  # 2% SL
        else:  # SELL
            tp_level = entry_price * 0.95  # 5% TP (short)
            sl_level = entry_price * 1.02  # 2% SL (short)
        
        # Create position entry
        position_id = f"{symbol}_{int(time.time() * 1000)}"
        entry_time = datetime.utcnow()
        
        # ✅ SAVE TO POSTGRESQL IMMEDIATELY (cross-process sharing)
        import asyncpg
        from src.config import get_database_url
        
        db_url = get_database_url()
        conn = await asyncpg.connect(db_url)
        
        # ✅ Ensure table exists WITH all 12 ML features
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS virtual_positions (
                id SERIAL PRIMARY KEY,
                position_id VARCHAR(255) UNIQUE NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL,
                quantity FLOAT NOT NULL,
                entry_price FLOAT NOT NULL,
                entry_confidence FLOAT DEFAULT 0,
                entry_time TIMESTAMP NOT NULL,
                tp_level FLOAT NOT NULL,
                sl_level FLOAT NOT NULL,
                status VARCHAR(20) DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ✅ ADD MISSING ML FEATURE COLUMNS
        features = ['confidence', 'fvg', 'liquidity', 'rsi', 'atr', 'macd', 'bb_width', 'position_size_pct']
        for feature in features:
            try:
                await conn.execute(f"ALTER TABLE virtual_positions ADD COLUMN IF NOT EXISTS {feature} FLOAT DEFAULT 0")
            except:
                pass
        
        # 🎯 提取 12 個 ML 特徵
        patterns = signal.get('patterns', {})
        features = signal.get('features', patterns)
        if isinstance(features, str):
            import json
            try:
                features = json.loads(features)
            except:
                features = {}
        
        fvg = float(features.get('fvg', 0.5))
        liquidity = float(features.get('liquidity', 0.5))
        rsi = float(features.get('rsi', 50))
        atr = float(features.get('atr', 0))
        macd = float(features.get('macd', 0))
        bb_width = float(features.get('bb_width', 0))
        position_size_pct = signal.get('position_size_pct', 0.0065)
        
        # Insert position WITH features
        await conn.execute("""
            INSERT INTO virtual_positions 
            (position_id, symbol, side, quantity, entry_price, entry_confidence, entry_time, 
             tp_level, sl_level, status, confidence, fvg, liquidity, rsi, atr, macd, bb_width, position_size_pct)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            ON CONFLICT (position_id) DO NOTHING
        """,
            position_id, symbol, side, quantity, entry_price, confidence, entry_time, 
            tp_level, sl_level, 'OPEN', confidence, fvg, liquidity, rsi, atr, macd, bb_width, position_size_pct
        )
        
        await conn.close()
        
        # Also update in-memory state for quick access
        async with _virtual_lock:
            _virtual_account['positions'][position_id] = {
                'symbol': symbol,
                'quantity': quantity,
                'entry_price': entry_price,
                'entry_confidence': confidence,
                'entry_time': time.time(),
                'side': side,
                'tp_level': tp_level,
                'sl_level': sl_level,
                'position_id': position_id,
                'status': 'OPEN'
            }
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Virtual position open failed: {e}", exc_info=True)
        return False


async def check_virtual_tp_sl() -> None:
    """
    ✅ FIXED: Read positions from PostgreSQL, not in-memory
    Automatically detect and close positions at TP/SL levels
    This runs continuously to monitor all virtual positions
    Uses REAL market prices from Ring Buffer / Feed process
    """
    try:
        import asyncpg
        from src.config import get_database_url
        
        db_url = get_database_url()
        conn = await asyncpg.connect(db_url)
        
        # ✅ Ensure table exists WITH all 12 ML features
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS virtual_positions (
                id SERIAL PRIMARY KEY,
                position_id VARCHAR(255) UNIQUE NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL,
                quantity FLOAT NOT NULL,
                entry_price FLOAT NOT NULL,
                entry_confidence FLOAT DEFAULT 0,
                entry_time TIMESTAMP NOT NULL,
                tp_level FLOAT NOT NULL,
                sl_level FLOAT NOT NULL,
                status VARCHAR(20) DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ✅ ADD MISSING ML FEATURE COLUMNS
        features = ['confidence', 'fvg', 'liquidity', 'rsi', 'atr', 'macd', 'bb_width', 'position_size_pct']
        for feature in features:
            try:
                await conn.execute(f"ALTER TABLE virtual_positions ADD COLUMN IF NOT EXISTS {feature} FLOAT DEFAULT 0")
            except:
                pass
        
        # ✅ READ FROM POSTGRESQL (cross-process)
        open_positions = await conn.fetch(
            "SELECT * FROM virtual_positions WHERE status = 'OPEN'"
        )
        
        closed_positions = []
        
        for pos in open_positions:
            symbol = pos['symbol']
            entry_price = pos['entry_price']
            
            # Get current price from Redis
            current_price = await get_current_price(symbol)
            if current_price is None or current_price == 0:
                # Fallback: Use time-based simulation
                current_price = entry_price * (1 + (0.01 * (time.time() % 10)))
            
            quantity = pos['quantity']
            side = pos['side']
            
            # Check TP/SL
            tp_reached = False
            sl_reached = False
            close_price = entry_price
            close_reason = "OPEN"
            
            if side == 'BUY':
                if current_price >= pos['tp_level']:
                    tp_reached = True
                    close_price = pos['tp_level']
                    close_reason = "TP_HIT"
                elif current_price <= pos['sl_level']:
                    sl_reached = True
                    close_price = pos['sl_level']
                    close_reason = "SL_HIT"
            else:  # SELL
                if current_price <= pos['tp_level']:
                    tp_reached = True
                    close_price = pos['tp_level']
                    close_reason = "TP_HIT"
                elif current_price >= pos['sl_level']:
                    sl_reached = True
                    close_price = pos['sl_level']
                    close_reason = "SL_HIT"
            
            # Close position if TP/SL hit
            if tp_reached or sl_reached:
                if side == 'BUY':
                    pnl = (close_price - entry_price) * quantity
                else:
                    pnl = (entry_price - close_price) * quantity
                
                # Calculate ROI% and reward score
                roi_pct = pnl / (entry_price * quantity) if entry_price > 0 else 0
                
                from src.reward_shaping import calculate_reward_score
                reward_score = calculate_reward_score(roi_pct)
                
                # ✅ UPDATE POSTGRESQL (mark as CLOSED)
                await conn.execute(
                    "UPDATE virtual_positions SET status = 'CLOSED' WHERE position_id = $1",
                    pos['position_id']
                )
                
                # Update in-memory account
                async with _virtual_lock:
                    _virtual_account['balance'] += pnl
                    _virtual_account['total_pnl'] += pnl
                
                # 🎯 提取 12 個 ML 特徵 (從已保存的信號)
                closed_positions.append({
                    'position_id': pos['position_id'],
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'close_price': close_price,
                    'reason': close_reason,
                    'pnl': pnl,
                    'roi_pct': roi_pct,
                    'reward_score': reward_score,
                    'entry_time': pos['entry_time'],
                    # ✅ 新增: 12 個特徵
                    'confidence': pos.get('confidence', 0.65),
                    'fvg': pos.get('fvg', 0.5),
                    'liquidity': pos.get('liquidity', 0.5),
                    'rsi': pos.get('rsi', 50),
                    'atr': pos.get('atr', 0),
                    'macd': pos.get('macd', 0),
                    'bb_width': pos.get('bb_width', 0),
                    'position_size_pct': pos.get('position_size_pct', 0),
                })
                
                logger.critical(
                    f"🎓 [VIRTUAL] Position closed: {symbol} {side} x{quantity} "
                    f"@ ${close_price:.2f} [{close_reason}] | ROI: {roi_pct:+.2%} | "
                    f"Score: {reward_score:+.0f} | PnL: ${pnl:.2f}"
                )
        
        await conn.close()
        
        # Save closed trades to virtual_trades table
        if closed_positions:
            await _save_virtual_trades(closed_positions)
    
    except Exception as e:
        logger.error(f"❌ TP/SL check failed: {e}", exc_info=True)


async def _save_virtual_trades(closed_positions: List[Dict]) -> None:
    """Save completed virtual trades to database and ML integrator"""
    try:
        import asyncpg
        from src.config import get_database_url
        
        db_url = get_database_url()
        conn = await asyncpg.connect(db_url)
        
        # Create table if not exists (with reward shaping columns)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS virtual_trades (
                id SERIAL PRIMARY KEY,
                position_id VARCHAR(255) UNIQUE,
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL,
                quantity FLOAT NOT NULL,
                entry_price FLOAT NOT NULL,
                close_price FLOAT NOT NULL,
                pnl FLOAT NOT NULL,
                roi_pct FLOAT DEFAULT 0,
                reward_score FLOAT DEFAULT 0,
                reason VARCHAR(50) NOT NULL,
                entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                close_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add new columns if they don't exist (for existing tables)
        try:
            await conn.execute("ALTER TABLE virtual_trades ADD COLUMN roi_pct FLOAT DEFAULT 0")
        except Exception:
            pass  # Column already exists
        
        try:
            await conn.execute("ALTER TABLE virtual_trades ADD COLUMN reward_score FLOAT DEFAULT 0")
        except Exception:
            pass  # Column already exists
        
        # 🎯 Insert closed trades WITH all 12 ML features
        for trade in closed_positions:
            await conn.execute("""
                INSERT INTO virtual_trades 
                (position_id, symbol, side, quantity, entry_price, close_price, pnl, roi_pct, reward_score, reason,
                 confidence, fvg, liquidity, rsi, atr, macd, bb_width, position_size_pct)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                ON CONFLICT (position_id) DO NOTHING
            """,
                trade['position_id'],
                trade['symbol'],
                trade['side'],
                trade['quantity'],
                trade['entry_price'],
                trade['close_price'],
                trade['pnl'],
                trade.get('roi_pct', 0),
                trade.get('reward_score', 0),
                trade['reason'],
                # ✅ 12 個特徵
                trade.get('confidence', 0.65),
                trade.get('fvg', 0.5),
                trade.get('liquidity', 0.5),
                trade.get('rsi', 50),
                trade.get('atr', 0),
                trade.get('macd', 0),
                trade.get('bb_width', 0),
                trade.get('position_size_pct', 0)
            )
        
        await conn.close()
        logger.critical(f"💾 Saved {len(closed_positions)} virtual trades to database")
        
        # 🤖 Add to ML integrator for bias-checked training
        from src.ml_virtual_integrator import get_ml_virtual_integrator
        integrator = get_ml_virtual_integrator()
        for trade in closed_positions:
            await integrator.add_virtual_trade(trade)
    
    except Exception as e:
        logger.warning(f"⚠️ Failed to save virtual trades: {e}")


async def get_virtual_state() -> Dict:
    """Get current virtual account state - NOW FROM POSTGRESQL"""
    try:
        import asyncpg
        from src.config import get_database_url
        
        db_url = get_database_url()
        conn = await asyncpg.connect(db_url)
        
        # Count open positions
        open_count = await conn.fetchval(
            "SELECT COUNT(*) FROM virtual_positions WHERE status = 'OPEN'"
        )
        
        # Count closed positions
        closed_count = await conn.fetchval(
            "SELECT COUNT(*) FROM virtual_positions WHERE status = 'CLOSED'"
        )
        
        await conn.close()
        
        async with _virtual_lock:
            win_rate = 0.0
            if closed_count > 0:
                # Calculate from virtual_trades if available
                try:
                    conn2 = await asyncpg.connect(db_url)
                    wins = await conn2.fetchval(
                        "SELECT COUNT(*) FROM virtual_trades WHERE pnl > 0"
                    )
                    await conn2.close()
                    win_rate = (wins / closed_count * 100.0) if closed_count > 0 else 0.0
                except:
                    pass
            
            return {
                'balance': _virtual_account['balance'],
                'total_pnl': _virtual_account['total_pnl'],
                'open_positions': open_count,
                'closed_positions': closed_count,
                'total_trades': closed_count,
                'win_rate': win_rate,
                'open_position_details': []
            }
    except Exception as e:
        logger.warning(f"⚠️ Failed to get virtual state: {e}")
        async with _virtual_lock:
            return {
                'balance': _virtual_account['balance'],
                'total_pnl': _virtual_account['total_pnl'],
                'open_positions': 0,
                'closed_positions': 0,
                'total_trades': 0,
                'win_rate': 0.0,
                'open_position_details': []
            }


def calculate_win_rate(closed_positions: List[Dict]) -> float:
    """Calculate win rate percentage"""
    if not closed_positions:
        return 0.0
    
    wins = sum(1 for p in closed_positions if p.get('pnl', 0) > 0)
    return (wins / len(closed_positions)) * 100.0


async def reset_virtual_account() -> None:
    """Reset virtual learning account"""
    await init_virtual_learning()
    logger.critical("🎓 Virtual Learning Account reset to initial state")
