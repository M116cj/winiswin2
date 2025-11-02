import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, List, Optional, Any
import threading

logger = logging.getLogger(__name__)

class TradingDatabase:
    """高性能交易数据库系统（v3.20+）"""
    
    def __init__(self, db_path: str = "trading_data.db", enabled: bool = False):
        self.db_path = db_path
        self.enabled = enabled
        self._cache_lock = threading.Lock()
        self.feature_cache = {}
        self.cache_ttl = 300
        
        if enabled:
            self._init_database()
            logger.info("✅ 交易数据库系统已启用")
        else:
            logger.info("📦 数据库系统已就绪（等待启用）")
    
    def _init_database(self):
        """初始化数据库结构"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS realtime_features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    market_structure REAL,
                    order_blocks_count INTEGER,
                    structure_integrity REAL,
                    liquidity_context REAL,
                    institutional_participation REAL,
                    timeframe_convergence REAL,
                    institutional_candle INTEGER,
                    liquidity_grab INTEGER,
                    order_flow REAL,
                    fvg_count INTEGER,
                    trend_alignment_enhanced REAL,
                    swing_high_distance REAL,
                    confidence_score REAL,
                    win_probability REAL,
                    calculation_mode TEXT,
                    has_signal BOOLEAN,
                    signal_direction TEXT,
                    UNIQUE(symbol, timestamp)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS symbol_performance (
                    symbol TEXT PRIMARY KEY,
                    total_scans INTEGER DEFAULT 0,
                    total_signals INTEGER DEFAULT 0,
                    successful_signals INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.5,
                    avg_confidence REAL DEFAULT 50.0,
                    avg_win_probability REAL DEFAULT 0.5,
                    last_signal_time DATETIME,
                    volatility_24h REAL DEFAULT 0.0,
                    trend_consistency REAL DEFAULT 0.0,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS market_regimes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    regime_type TEXT,
                    description TEXT,
                    volatility_score REAL DEFAULT 0.5,
                    trend_strength REAL DEFAULT 0.5,
                    success_rate_24h REAL DEFAULT 0.5,
                    signal_density REAL DEFAULT 0.0,
                    avg_confidence REAL DEFAULT 50.0,
                    symbol_count INTEGER DEFAULT 0,
                    metadata TEXT
                )
            ''')
            
            conn.execute('CREATE INDEX IF NOT EXISTS idx_features_symbol_time ON realtime_features(symbol, timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_performance_symbol ON symbol_performance(symbol)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_regime_time ON market_regimes(timestamp)')
            
            conn.commit()
            conn.close()
            logger.info("✅ 数据库初始化完成（3个核心表 + 索引）")
            
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
    
    def record_feature_analysis(self, symbol: str, features: Dict, confidence: float, 
                              win_probability: float, has_signal: bool, signal_direction: str = None):
        """记录特征分析结果（仅在启用时）"""
        if not self.enabled:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            
            conn.execute('''
                INSERT OR REPLACE INTO realtime_features 
                (symbol, timestamp, market_structure, order_blocks_count, structure_integrity,
                 liquidity_context, institutional_participation, timeframe_convergence,
                 institutional_candle, liquidity_grab, order_flow, fvg_count,
                 trend_alignment_enhanced, swing_high_distance, confidence_score,
                 win_probability, calculation_mode, has_signal, signal_direction)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, datetime.now(),
                features.get('market_structure'),
                features.get('order_blocks_count'),
                features.get('structure_integrity'),
                features.get('liquidity_context'),
                features.get('institutional_participation'),
                features.get('timeframe_convergence'),
                features.get('institutional_candle'),
                features.get('liquidity_grab'),
                features.get('order_flow'),
                features.get('fvg_count'),
                features.get('trend_alignment_enhanced'),
                features.get('swing_high_distance'),
                confidence,
                win_probability,
                'pure_ict',
                has_signal,
                signal_direction
            ))
            
            conn.commit()
            conn.close()
            
            with self._cache_lock:
                self.feature_cache[symbol] = {
                    'timestamp': datetime.now(),
                    'features': features,
                    'confidence': confidence,
                    'win_probability': win_probability
                }
                
        except Exception as e:
            logger.error(f"❌ 记录特征分析失败 {symbol}: {e}")
    
    def get_symbol_performance(self, symbol: str, lookback_hours: int = 24) -> Optional[Dict]:
        """获取符号性能指标"""
        if not self.enabled:
            return None
            
        try:
            conn = sqlite3.connect(self.db_path)
            
            cursor = conn.execute(
                'SELECT * FROM symbol_performance WHERE symbol = ?', (symbol,)
            )
            performance = cursor.fetchone()
            
            if performance:
                cols = [desc[0] for desc in cursor.description]
                performance_dict = dict(zip(cols, performance))
                
                recent_features = self.get_recent_features(symbol, lookback_hours)
                if recent_features:
                    confidences = [f['confidence_score'] for f in recent_features if f.get('confidence_score')]
                    performance_dict['recent_avg_confidence'] = np.mean(confidences) if confidences else 50.0
                    performance_dict['recent_signal_count'] = len([f for f in recent_features if f.get('has_signal')])
                
                conn.close()
                return performance_dict
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取符号性能失败 {symbol}: {e}")
            return None
    
    def get_recent_features(self, symbol: str, lookback_hours: int = 1) -> List[Dict]:
        """获取最近的特征记录"""
        if not self.enabled:
            return []
            
        try:
            conn = sqlite3.connect(self.db_path)
            since_time = datetime.now() - timedelta(hours=lookback_hours)
            
            cursor = conn.execute('''
                SELECT * FROM realtime_features 
                WHERE symbol = ? AND timestamp > ?
                ORDER BY timestamp DESC
                LIMIT 100
            ''', (symbol, since_time))
            
            features = []
            for row in cursor.fetchall():
                cols = [desc[0] for desc in cursor.description]
                features.append(dict(zip(cols, row)))
            
            conn.close()
            return features
            
        except Exception as e:
            logger.error(f"❌ 获取最近特征失败 {symbol}: {e}")
            return []
    
    def update_market_regime(self, regime_type: str, metrics: Dict):
        """更新市场状态"""
        if not self.enabled:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            
            conn.execute('''
                INSERT INTO market_regimes 
                (regime_type, volatility_score, trend_strength, success_rate_24h, 
                 signal_density, avg_confidence, symbol_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                regime_type,
                metrics.get('volatility_score', 0.5),
                metrics.get('trend_strength', 0.5),
                metrics.get('success_rate_24h', 0.5),
                metrics.get('signal_density', 0.0),
                metrics.get('avg_confidence', 50.0),
                metrics.get('symbol_count', 0),
                json.dumps(metrics.get('metadata', {}))
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"📊 市场状态更新: {regime_type}")
            
        except Exception as e:
            logger.error(f"❌ 更新市场状态失败: {e}")
    
    def get_current_market_regime(self) -> Optional[Dict]:
        """获取当前市场状态"""
        if not self.enabled:
            return None
            
        try:
            conn = sqlite3.connect(self.db_path)
            
            cursor = conn.execute('''
                SELECT * FROM market_regimes 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''')
            
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                regime = dict(zip(cols, row))
                if regime.get('metadata'):
                    regime['metadata'] = json.loads(regime['metadata'])
                conn.close()
                return regime
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取市场状态失败: {e}")
            return None
    
    def cleanup_old_data(self, days_to_keep: int = 7):
        """清理旧数据"""
        if not self.enabled:
            return
            
        try:
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)
            
            conn = sqlite3.connect(self.db_path)
            
            conn.execute('DELETE FROM realtime_features WHERE timestamp < ?', (cutoff_time,))
            conn.execute('DELETE FROM market_regimes WHERE timestamp < ?', (cutoff_time,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"🧹 清理了 {days_to_keep} 天前的数据")
            
        except Exception as e:
            logger.error(f"❌ 数据清理失败: {e}")
