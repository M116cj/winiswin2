"""
SQLite-based Trade Recorder for SelfLearningTrader
Records all trades to database for historical analysis and performance tracking
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)

class TradeRecorder:
    """SQLite数据库交易记录器（v3.20.7+ 兼容原有JSON TradeRecorder接口）"""
    
    def __init__(self, config):
        self.config = config
        self.db_path = 'trading_data.db'
        
        self.completed_trades = []
        
        self._init_database()
        
    def _init_database(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    position_size REAL NOT NULL,
                    pnl REAL,
                    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    exit_time TIMESTAMP,
                    confidence REAL,
                    win_probability REAL,
                    status TEXT DEFAULT 'OPEN',
                    risk_reward_ratio REAL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_trades INTEGER,
                    winning_trades INTEGER,
                    total_pnl REAL,
                    win_rate REAL
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("✅ 交易記錄數據庫初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 交易記錄數據庫初始化失敗: {e}")
    
    async def get_trade_count(self, timeframe: str = '24h') -> int:
        """獲取交易數量"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if timeframe == '24h':
                twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
                cursor.execute(
                    "SELECT COUNT(*) FROM trade_history WHERE entry_time >= ?",
                    (twenty_four_hours_ago,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM trade_history")
                
            result = cursor.fetchone()
            count = result[0] if result else 0
            conn.close()
            
            logger.debug(f"📊 交易數量查詢: {timeframe} = {count}")
            return count
            
        except Exception as e:
            logger.error(f"❌ 獲取交易數量失敗: {e}")
            return 0
    
    async def record_trade(self, trade_data: Dict) -> bool:
        """記錄交易到數據庫"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trade_history 
                (symbol, direction, entry_price, position_size, confidence, win_probability, status, risk_reward_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data.get('symbol'),
                trade_data.get('direction'), 
                trade_data.get('entry_price', 0),
                trade_data.get('position_size', 0),
                trade_data.get('confidence', 0),
                trade_data.get('win_probability', 0),
                trade_data.get('status', 'OPEN'),
                trade_data.get('risk_reward_ratio', 0)
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ 交易記錄成功: {trade_data.get('symbol')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 交易記錄失敗: {e}")
            return False
    
    async def get_recent_performance(self, hours: int = 24) -> Dict:
        """獲取近期交易表現"""
        try:
            since_time = datetime.now() - timedelta(hours=hours)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                    AVG(pnl) as avg_pnl,
                    SUM(pnl) as total_pnl
                FROM trade_history 
                WHERE entry_time >= ?
            ''', (since_time,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0] > 0:
                total_trades, winning_trades, losing_trades, avg_pnl, total_pnl = result
                win_rate = (winning_trades / total_trades) * 100
            else:
                total_trades = winning_trades = losing_trades = avg_pnl = total_pnl = win_rate = 0
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'avg_pnl': avg_pnl or 0,
                'total_pnl': total_pnl or 0
            }
            
        except Exception as e:
            logger.error(f"❌ 獲取交易表現失敗: {e}")
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'avg_pnl': 0,
                'total_pnl': 0
            }
    
    def record_entry(
        self, 
        signal: Dict, 
        position_info: Dict, 
        competition_context: Optional[Dict] = None,
        websocket_metadata: Optional[Dict] = None
    ):
        """
        記錄開倉信號（兼容原有接口）
        
        Args:
            signal: 交易信號
            position_info: 倉位信息
            competition_context: 競價上下文
            websocket_metadata: WebSocket元數據
        """
        try:
            entry_record = {
                'symbol': signal.get('symbol'),
                'direction': signal.get('direction'),
                'entry_price': signal.get('current_price', 0),
                'position_size': position_info.get('size', 0),
                'confidence': signal.get('confidence', 0),
                'win_probability': signal.get('win_probability', 0),
                'status': 'OPEN',
                'risk_reward_ratio': signal.get('risk_reward_ratio', 0)
            }
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trade_history 
                (symbol, direction, entry_price, position_size, confidence, win_probability, status, risk_reward_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry_record['symbol'],
                entry_record['direction'],
                entry_record['entry_price'],
                entry_record['position_size'],
                entry_record['confidence'],
                entry_record['win_probability'],
                entry_record['status'],
                entry_record['risk_reward_ratio']
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"📝 記錄開倉: {entry_record['symbol']}")
            
        except Exception as e:
            logger.error(f"❌ 記錄開倉失敗: {e}")
    
    async def save_competition_log(self, competition_log: Dict):
        """
        保存多信號競價記錄（兼容原有接口）
        
        Args:
            competition_log: 競價記錄數據
        """
        try:
            competition_file = 'data/signal_competitions.jsonl'
            
            import os
            os.makedirs(os.path.dirname(competition_file), exist_ok=True)
            
            with open(competition_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(competition_log, ensure_ascii=False, default=str) + '\n')
            
            logger.debug("📝 競價記錄已保存")
            
        except Exception as e:
            logger.error(f"❌ 保存競價記錄失敗: {e}")
