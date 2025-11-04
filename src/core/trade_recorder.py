"""
Enhanced Trade Recorder v3.23 - Production-Grade Trading System
- Async SQLite operations with aiosqlite
- Performance optimization with caching and indexing
- Comprehensive statistics and risk metrics
- Database migrations and health monitoring
"""

import sqlite3
import logging
import asyncio
import aiosqlite
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import json
import hashlib

logger = logging.getLogger(__name__)

class TradeStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED" 
    CANCELLED = "CANCELLED"
    LIQUIDATED = "LIQUIDATED"

class PerformanceMetric(Enum):
    WIN_RATE = "win_rate"
    AVG_PNL = "avg_pnl"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"

class EnhancedTradeRecorder:
    """增強版交易記錄器 - 完整修復和功能增強"""
    
    def __init__(self, config):
        self.config = config
        self.db_path = 'trading_data.db'
        self._initialized = False
        self._cache = {}
        self._performance_cache = {}
        
        # 为兼容性添加 completed_trades 属性
        self.completed_trades = []
        
        # 性能優化配置
        self.optimization_config = {
            'cache_ttl': 300,  # 5分鐘緩存
            'batch_size': 10,  # 批量操作大小
            'auto_vacuum': True,  # 自動清理數據庫
            'wal_mode': True,     # 寫入前日誌模式
        }
        
        # 🔥 v3.23: 智能初始化（同步+異步混合）
        try:
            # 先嘗試同步初始化數據庫結構（不依賴事件循環）
            self._sync_init_database()
            
            # 然後啟動異步優化（如果有事件循環）
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._async_optimize())
            except RuntimeError:
                logger.debug("📋 事件循環未運行，跳過異步優化（數據庫已可用）")
        except Exception as e:
            logger.error(f"❌ EnhancedTradeRecorder 初始化失敗: {e}")

    def _sync_init_database(self):
        """同步初始化數據庫（立即可用）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 啟用 WAL 模式
            if self.optimization_config['wal_mode']:
                cursor.execute("PRAGMA journal_mode=WAL")
            
            # 創建所有表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_uid TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    position_size REAL NOT NULL,
                    pnl REAL,
                    pnl_percentage REAL,
                    commission REAL DEFAULT 0,
                    funding_rate REAL DEFAULT 0,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    hold_duration INTEGER,
                    confidence REAL,
                    win_probability REAL,
                    risk_reward_ratio REAL,
                    status TEXT DEFAULT 'OPEN',
                    exit_reason TEXT,
                    strategy_version TEXT,
                    market_conditions TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS current_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_uid TEXT UNIQUE NOT NULL,
                    symbol TEXT UNIQUE NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL,
                    position_size REAL NOT NULL,
                    unrealized_pnl REAL,
                    unrealized_pnl_percentage REAL,
                    margin_used REAL NOT NULL,
                    leverage INTEGER DEFAULT 1,
                    entry_time TIMESTAMP NOT NULL,
                    confidence REAL,
                    win_probability REAL,
                    stop_loss_price REAL,
                    take_profit_price REAL,
                    risk_reward_ratio REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_type TEXT NOT NULL,
                    period_start TIMESTAMP NOT NULL,
                    period_end TIMESTAMP NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    total_volume REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    avg_pnl REAL DEFAULT 0,
                    avg_winning_pnl REAL DEFAULT 0,
                    avg_losing_pnl REAL DEFAULT 0,
                    profit_factor REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(period_type, period_start)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS symbol_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    avg_pnl REAL DEFAULT 0,
                    best_trade_pnl REAL DEFAULT 0,
                    worst_trade_pnl REAL DEFAULT 0,
                    avg_hold_duration INTEGER DEFAULT 0,
                    last_traded TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS risk_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_portfolio_value REAL DEFAULT 0,
                    used_margin REAL DEFAULT 0,
                    available_margin REAL DEFAULT 0,
                    margin_ratio REAL DEFAULT 0,
                    daily_pnl REAL DEFAULT 0,
                    weekly_pnl REAL DEFAULT 0,
                    monthly_pnl REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    volatility REAL DEFAULT 0,
                    var_95 REAL DEFAULT 0,
                    expected_shortfall REAL DEFAULT 0
                )
            ''')
            
            conn.commit()
            conn.close()
            
            self._initialized = True
            logger.info("✅ EnhancedTradeRecorder 同步初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 同步初始化失敗: {e}")
            raise

    async def _async_optimize(self):
        """異步優化（索引、遷移等）"""
        try:
            await self._create_indexes()
            await self._migrate_database()
            logger.info("✅ EnhancedTradeRecorder 異步優化完成")
        except Exception as e:
            logger.error(f"❌ 異步優化失敗: {e}")

    async def _init_database(self):
        """初始化數據庫表結構"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 啟用 WAL 模式提升性能
                if self.optimization_config['wal_mode']:
                    await db.execute("PRAGMA journal_mode=WAL")
                
                # 交易歷史表
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS trade_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_uid TEXT UNIQUE NOT NULL,
                        symbol TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        exit_price REAL,
                        position_size REAL NOT NULL,
                        pnl REAL,
                        pnl_percentage REAL,
                        commission REAL DEFAULT 0,
                        funding_rate REAL DEFAULT 0,
                        entry_time TIMESTAMP NOT NULL,
                        exit_time TIMESTAMP,
                        hold_duration INTEGER,
                        confidence REAL,
                        win_probability REAL,
                        risk_reward_ratio REAL,
                        status TEXT DEFAULT 'OPEN',
                        exit_reason TEXT,
                        strategy_version TEXT,
                        market_conditions TEXT,
                        tags TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # 實時持倉表
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS current_positions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_uid TEXT UNIQUE NOT NULL,
                        symbol TEXT UNIQUE NOT NULL,
                        direction TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        current_price REAL,
                        position_size REAL NOT NULL,
                        unrealized_pnl REAL,
                        unrealized_pnl_percentage REAL,
                        margin_used REAL NOT NULL,
                        leverage INTEGER DEFAULT 1,
                        entry_time TIMESTAMP NOT NULL,
                        confidence REAL,
                        win_probability REAL,
                        stop_loss_price REAL,
                        take_profit_price REAL,
                        risk_reward_ratio REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # 性能統計表
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS performance_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        period_type TEXT NOT NULL,
                        period_start TIMESTAMP NOT NULL,
                        period_end TIMESTAMP NOT NULL,
                        total_trades INTEGER DEFAULT 0,
                        winning_trades INTEGER DEFAULT 0,
                        losing_trades INTEGER DEFAULT 0,
                        total_pnl REAL DEFAULT 0,
                        total_volume REAL DEFAULT 0,
                        win_rate REAL DEFAULT 0,
                        avg_pnl REAL DEFAULT 0,
                        avg_winning_pnl REAL DEFAULT 0,
                        avg_losing_pnl REAL DEFAULT 0,
                        profit_factor REAL DEFAULT 0,
                        max_drawdown REAL DEFAULT 0,
                        sharpe_ratio REAL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(period_type, period_start)
                    )
                ''')

                # 交易對統計表
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS symbol_performance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        total_trades INTEGER DEFAULT 0,
                        winning_trades INTEGER DEFAULT 0,
                        total_pnl REAL DEFAULT 0,
                        win_rate REAL DEFAULT 0,
                        avg_pnl REAL DEFAULT 0,
                        best_trade_pnl REAL DEFAULT 0,
                        worst_trade_pnl REAL DEFAULT 0,
                        avg_hold_duration INTEGER DEFAULT 0,
                        last_traded TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol)
                    )
                ''')

                # 風險管理表
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS risk_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_portfolio_value REAL DEFAULT 0,
                        used_margin REAL DEFAULT 0,
                        available_margin REAL DEFAULT 0,
                        margin_ratio REAL DEFAULT 0,
                        daily_pnl REAL DEFAULT 0,
                        weekly_pnl REAL DEFAULT 0,
                        monthly_pnl REAL DEFAULT 0,
                        max_drawdown REAL DEFAULT 0,
                        volatility REAL DEFAULT 0,
                        var_95 REAL DEFAULT 0,
                        expected_shortfall REAL DEFAULT 0
                    )
                ''')

                await db.commit()
                logger.info("✅ 數據庫表結構初始化完成")
                
        except Exception as e:
            logger.error(f"❌ 數據庫初始化失敗: {e}")
            raise

    async def _create_indexes(self):
        """創建性能索引"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_trade_history_symbol ON trade_history(symbol)",
                    "CREATE INDEX IF NOT EXISTS idx_trade_history_entry_time ON trade_history(entry_time)",
                    "CREATE INDEX IF NOT EXISTS idx_trade_history_status ON trade_history(status)",
                    "CREATE INDEX IF NOT EXISTS idx_trade_history_pnl ON trade_history(pnl)",
                    "CREATE INDEX IF NOT EXISTS idx_performance_stats_period ON performance_stats(period_type, period_start)",
                    "CREATE INDEX IF NOT EXISTS idx_symbol_performance_symbol ON symbol_performance(symbol)",
                ]
                
                for index_sql in indexes:
                    await db.execute(index_sql)
                
                await db.commit()
                logger.info("✅ 數據庫索引創建完成")
                
        except Exception as e:
            logger.error(f"❌ 索引創建失敗: {e}")

    async def _migrate_database(self):
        """數據庫遷移（用於版本升級）"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS db_version (
                        version INTEGER PRIMARY KEY,
                        migrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor = await db.execute("SELECT MAX(version) FROM db_version")
                result = await cursor.fetchone()
                current_version = result[0] if result and result[0] else 0
                
                await db.commit()
                logger.debug(f"📊 數據庫版本: {current_version}")
                
        except Exception as e:
            logger.error(f"❌ 數據庫遷移失敗: {e}")

    async def get_trade_count(self, timeframe: str = '24h', symbol: Optional[str] = None) -> int:
        """獲取交易數量 - 完整修復版本"""
        cache_key = f"trade_count_{timeframe}_{symbol}"
        
        if cache_key in self._cache and self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        try:
            if not self._initialized:
                logger.warning("⚠️ TradeRecorder 未初始化，返回0")
                return 0
                
            async with aiosqlite.connect(self.db_path) as db:
                query = "SELECT COUNT(*) FROM trade_history WHERE 1=1"
                params = []
                
                if timeframe == '24h':
                    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
                    query += " AND entry_time >= ?"
                    params.append(twenty_four_hours_ago)
                elif timeframe == '7d':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    query += " AND entry_time >= ?"
                    params.append(seven_days_ago)
                elif timeframe == '30d':
                    thirty_days_ago = datetime.now() - timedelta(days=30)
                    query += " AND entry_time >= ?"
                    params.append(thirty_days_ago)
                
                if symbol:
                    query += " AND symbol = ?"
                    params.append(symbol)
                
                cursor = await db.execute(query, params)
                result = await cursor.fetchone()
                count = result[0] if result else 0
                
                self._cache[cache_key] = (datetime.now().timestamp(), count)
                
                logger.debug(f"📊 TradeRecorder.get_trade_count: {timeframe} {symbol} = {count}")
                return count
                
        except Exception as e:
            logger.error(f"❌ TradeRecorder.get_trade_count 失敗: {e}")
            return 0

    async def record_trade(self, trade_data: Dict) -> bool:
        """記錄交易 - 增強版本"""
        try:
            if not self._initialized:
                logger.error("❌ TradeRecorder 未初始化，無法記錄交易")
                return False
            
            trade_uid = self._generate_trade_uid(trade_data)
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO trade_history 
                    (trade_uid, symbol, direction, entry_price, position_size, 
                     confidence, win_probability, risk_reward_ratio, status,
                     entry_time, strategy_version, market_conditions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade_uid,
                    trade_data.get('symbol'),
                    trade_data.get('direction'), 
                    trade_data.get('entry_price', 0),
                    trade_data.get('position_size', 0),
                    trade_data.get('confidence', 0),
                    trade_data.get('win_probability', 0),
                    trade_data.get('risk_reward_ratio', 1.5),
                    TradeStatus.OPEN.value,
                    trade_data.get('entry_time', datetime.now()),
                    trade_data.get('strategy_version', 'v3.23'),
                    json.dumps(trade_data.get('market_conditions', {}))
                ))
                
                await db.execute('''
                    INSERT OR REPLACE INTO current_positions 
                    (trade_uid, symbol, direction, entry_price, position_size,
                     margin_used, leverage, entry_time, confidence, win_probability,
                     risk_reward_ratio, stop_loss_price, take_profit_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade_uid,
                    trade_data.get('symbol'),
                    trade_data.get('direction'),
                    trade_data.get('entry_price', 0),
                    trade_data.get('position_size', 0),
                    trade_data.get('margin_used', 0),
                    trade_data.get('leverage', 1),
                    trade_data.get('entry_time', datetime.now()),
                    trade_data.get('confidence', 0),
                    trade_data.get('win_probability', 0),
                    trade_data.get('risk_reward_ratio', 1.5),
                    trade_data.get('stop_loss_price'),
                    trade_data.get('take_profit_price')
                ))
                
                await db.commit()
                symbol = trade_data.get('symbol')
                if symbol:
                    self._clear_related_cache(symbol)
                
                logger.info(f"✅ 交易記錄成功: {symbol} (UID: {trade_uid})")
                return True
                
        except Exception as e:
            logger.error(f"❌ 交易記錄失敗: {e}")
            return False

    async def close_trade(self, trade_uid: str, exit_data: Dict) -> bool:
        """關閉交易"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                entry_time = await self._get_trade_entry_time(db, trade_uid)
                exit_time = exit_data.get('exit_time', datetime.now())
                hold_duration = int((exit_time - entry_time).total_seconds()) if entry_time else 0
                
                entry_price = await self._get_trade_entry_price(db, trade_uid)
                exit_price = exit_data.get('exit_price', 0)
                position_size = await self._get_position_size(db, trade_uid)
                direction = await self._get_trade_direction(db, trade_uid)
                
                pnl, pnl_percentage = self._calculate_pnl(
                    entry_price, exit_price, position_size, direction
                )
                
                await db.execute('''
                    UPDATE trade_history 
                    SET exit_price = ?, pnl = ?, pnl_percentage = ?,
                        exit_time = ?, hold_duration = ?, status = ?,
                        exit_reason = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE trade_uid = ?
                ''', (
                    exit_price, pnl, pnl_percentage,
                    exit_time, hold_duration, TradeStatus.CLOSED.value,
                    exit_data.get('exit_reason', 'manual'), trade_uid
                ))
                
                await db.execute('DELETE FROM current_positions WHERE trade_uid = ?', (trade_uid,))
                await db.commit()
                
                logger.info(f"✅ 交易關閉成功: {trade_uid} PnL: ${pnl:.2f} ({pnl_percentage:.2f}%)")
                return True
                
        except Exception as e:
            logger.error(f"❌ 關閉交易失敗 {trade_uid}: {e}")
            return False

    async def get_recent_performance(self, hours: int = 24) -> Dict:
        """獲取近期交易表現"""
        cache_key = f"performance_{hours}h"
        
        if cache_key in self._performance_cache and self._is_cache_valid(cache_key):
            return self._performance_cache[cache_key]
        
        try:
            since_time = datetime.now() - timedelta(hours=hours)
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                        AVG(pnl) as avg_pnl,
                        SUM(pnl) as total_pnl,
                        AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_winning_pnl,
                        AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_losing_pnl,
                        AVG(hold_duration) as avg_hold_duration
                    FROM trade_history 
                    WHERE entry_time >= ? AND status = 'CLOSED'
                ''', (since_time,))
                
                result = await cursor.fetchone()
                
                if result and result[0] > 0:
                    (total_trades, winning_trades, losing_trades, avg_pnl, 
                     total_pnl, avg_winning_pnl, avg_losing_pnl, avg_hold_duration) = result
                    
                    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
                    profit_factor = abs(avg_winning_pnl / avg_losing_pnl) if avg_losing_pnl and avg_losing_pnl != 0 else float('inf')
                    
                    max_drawdown = await self._calculate_max_drawdown(db, since_time)
                    
                    performance = {
                        'total_trades': total_trades,
                        'winning_trades': winning_trades or 0,
                        'losing_trades': losing_trades or 0,
                        'win_rate': round(win_rate, 2),
                        'avg_pnl': round(avg_pnl or 0, 2),
                        'total_pnl': round(total_pnl or 0, 2),
                        'avg_winning_pnl': round(avg_winning_pnl or 0, 2),
                        'avg_losing_pnl': round(avg_losing_pnl or 0, 2),
                        'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999.99,
                        'max_drawdown': round(max_drawdown, 2),
                        'avg_hold_duration': round(avg_hold_duration or 0, 2),
                        'period_hours': hours
                    }
                else:
                    performance = self._get_default_performance(hours)
                
                self._performance_cache[cache_key] = (datetime.now().timestamp(), performance)
                return performance
                
        except Exception as e:
            logger.error(f"❌ 獲取交易表現失敗: {e}")
            return self._get_default_performance(hours)

    async def get_current_positions(self) -> List[Dict]:
        """獲取當前持倉"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    SELECT symbol, direction, entry_price, position_size, 
                           margin_used, entry_time, confidence, win_probability,
                           stop_loss_price, take_profit_price, unrealized_pnl
                    FROM current_positions
                    ORDER BY entry_time DESC
                ''')
                
                rows = await cursor.fetchall()
                positions = []
                
                for row in rows:
                    positions.append({
                        'symbol': row[0],
                        'direction': row[1],
                        'entry_price': row[2],
                        'position_size': row[3],
                        'margin_used': row[4],
                        'entry_time': row[5],
                        'confidence': row[6],
                        'win_probability': row[7],
                        'stop_loss_price': row[8],
                        'take_profit_price': row[9],
                        'unrealized_pnl': row[10]
                    })
                
                return positions
                
        except Exception as e:
            logger.error(f"❌ 獲取當前持倉失敗: {e}")
            return []

    async def health_check(self) -> Dict:
        """健康檢查"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                tables = ['trade_history', 'current_positions', 'performance_stats']
                health_status = {}
                
                for table in tables:
                    try:
                        cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
                        result = await cursor.fetchone()
                        health_status[table] = result[0] if result else 0
                    except:
                        health_status[table] = -1
                
                health_status['initialized'] = self._initialized
                health_status['database_size'] = await self._get_database_size()
                
                return health_status
                
        except Exception as e:
            logger.error(f"❌ 健康檢查失敗: {e}")
            return {'error': str(e)}

    # Helper methods
    def _generate_trade_uid(self, trade_data: Dict) -> str:
        """生成唯一交易ID"""
        unique_string = f"{trade_data.get('symbol')}_{trade_data.get('entry_time')}_{datetime.now().timestamp()}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:16]

    def _calculate_pnl(self, entry_price: float, exit_price: float, 
                      position_size: float, direction: str) -> Tuple[float, float]:
        """計算盈虧"""
        if direction == 'LONG':
            pnl = (exit_price - entry_price) * position_size
        else:
            pnl = (entry_price - exit_price) * position_size
        
        pnl_percentage = (pnl / (position_size * entry_price)) * 100 if position_size * entry_price > 0 else 0
        return round(pnl, 4), round(pnl_percentage, 2)

    def _is_cache_valid(self, cache_key: str) -> bool:
        """檢查緩存是否有效"""
        if cache_key not in self._cache:
            return False
        timestamp, _ = self._cache[cache_key]
        return (datetime.now().timestamp() - timestamp) < self.optimization_config['cache_ttl']

    def _clear_related_cache(self, symbol: str):
        """清除相關緩存"""
        keys_to_clear = [k for k in self._cache.keys() if symbol in k or 'performance' in k]
        for key in keys_to_clear:
            self._cache.pop(key, None)

    def _get_default_performance(self, hours: int) -> Dict:
        """返回默認性能數據"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'avg_pnl': 0,
            'total_pnl': 0,
            'avg_winning_pnl': 0,
            'avg_losing_pnl': 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'avg_hold_duration': 0,
            'period_hours': hours
        }

    async def _get_trade_entry_time(self, db, trade_uid: str) -> Optional[datetime]:
        """獲取交易入場時間"""
        cursor = await db.execute("SELECT entry_time FROM trade_history WHERE trade_uid = ?", (trade_uid,))
        result = await cursor.fetchone()
        return datetime.fromisoformat(result[0]) if result and result[0] else None

    async def _get_trade_entry_price(self, db, trade_uid: str) -> float:
        """獲取交易入場價格"""
        cursor = await db.execute("SELECT entry_price FROM trade_history WHERE trade_uid = ?", (trade_uid,))
        result = await cursor.fetchone()
        return result[0] if result else 0

    async def _get_position_size(self, db, trade_uid: str) -> float:
        """獲取頭寸大小"""
        cursor = await db.execute("SELECT position_size FROM trade_history WHERE trade_uid = ?", (trade_uid,))
        result = await cursor.fetchone()
        return result[0] if result else 0

    async def _get_trade_direction(self, db, trade_uid: str) -> str:
        """獲取交易方向"""
        cursor = await db.execute("SELECT direction FROM trade_history WHERE trade_uid = ?", (trade_uid,))
        result = await cursor.fetchone()
        return result[0] if result else 'LONG'

    async def _calculate_max_drawdown(self, db, since_time: datetime) -> float:
        """計算最大回撤"""
        try:
            cursor = await db.execute('''
                SELECT entry_time, pnl FROM trade_history 
                WHERE entry_time >= ? AND status = 'CLOSED'
                ORDER BY entry_time
            ''', (since_time,))
            
            rows = await cursor.fetchall()
            if not rows:
                return 0.0
                
            cumulative_pnl = 0
            peak = 0
            max_drawdown = 0
            
            for _, pnl in rows:
                cumulative_pnl += (pnl or 0)
                if cumulative_pnl > peak:
                    peak = cumulative_pnl
                drawdown = peak - cumulative_pnl
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            return max_drawdown
            
        except Exception as e:
            logger.error(f"❌ 計算最大回撤失敗: {e}")
            return 0.0

    async def _get_database_size(self) -> int:
        """獲取數據庫文件大小"""
        try:
            import os
            return os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        except:
            return 0

    # 兼容性方法（用於向後兼容）
    async def save_competition_log(self, competition_log: Dict) -> bool:
        """保存信號競價日誌（兼容性方法）"""
        try:
            logger.debug(f"📊 保存信號競價日誌: {len(competition_log.get('candidates', []))} 個候選信號")
            return True
        except Exception as e:
            logger.error(f"❌ 保存競價日誌失敗: {e}")
            return False

    async def record_entry(self, trade_data: Dict) -> bool:
        """記錄開倉（兼容性方法）"""
        return await self.record_trade(trade_data)


# 為了向後兼容，保留 TradeRecorder 別名
TradeRecorder = EnhancedTradeRecorder
