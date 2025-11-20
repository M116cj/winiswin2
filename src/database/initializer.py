"""
Database Initializer - 数据表结构初始化
创建所有必要的数据表、索引和约束
"""

import logging
from typing import Optional
from .manager import DatabaseManager

logger = logging.getLogger(__name__)


def initialize_database(db_manager: DatabaseManager) -> bool:
    """
    初始化所有数据表
    
    Args:
        db_manager: 数据库管理器实例
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.debug("初始化数据库表结构...")
        
        # 创建所有表
        success = True
        success &= _create_trades_table(db_manager)
        success &= _create_ml_models_table(db_manager)
        success &= _create_market_data_table(db_manager)
        success &= _create_trading_signals_table(db_manager)
        success &= _create_position_entry_times_table(db_manager)
        
        if success:
            logger.debug("✅ 数据库表结构初始化完成")
        else:
            logger.error("❌ 部分表初始化失败")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
        logger.exception("详细错误:")
        return False


def _create_trades_table(db_manager: DatabaseManager) -> bool:
    """创建交易记录表"""
    try:
        logger.debug("创建 trades 表...")
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            direction VARCHAR(10) NOT NULL CHECK (direction IN ('LONG', 'SHORT', 'BUY', 'SELL')),
            entry_price DECIMAL(18, 8) NOT NULL,
            exit_price DECIMAL(18, 8),
            quantity DECIMAL(18, 8) NOT NULL,
            leverage INTEGER NOT NULL DEFAULT 1,
            
            -- 时间戳
            entry_timestamp TIMESTAMPTZ NOT NULL,
            exit_timestamp TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            
            -- 盈亏信息
            pnl DECIMAL(18, 8),
            pnl_pct DECIMAL(10, 4),
            
            -- 交易状态
            status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
            won BOOLEAN,
            
            -- 策略信息
            strategy VARCHAR(100),
            confidence DECIMAL(5, 4),
            win_probability DECIMAL(5, 4),
            
            -- 风险管理
            position_value DECIMAL(18, 8),
            risk_reward_ratio DECIMAL(10, 4),
            stop_loss DECIMAL(18, 8),
            take_profit DECIMAL(18, 8),
            
            -- 技术指标
            rsi DECIMAL(10, 4),
            macd DECIMAL(18, 8),
            macd_signal DECIMAL(18, 8),
            macd_histogram DECIMAL(18, 8),
            atr DECIMAL(18, 8),
            bb_width DECIMAL(10, 6),
            volume_sma_ratio DECIMAL(10, 4),
            ema50 DECIMAL(18, 8),
            ema200 DECIMAL(18, 8),
            volatility_24h DECIMAL(10, 6),
            
            -- 趋势特征
            trend_1h SMALLINT,
            trend_15m SMALLINT,
            trend_5m SMALLINT,
            market_structure SMALLINT,
            trend_alignment DECIMAL(5, 4),
            
            -- ICT/SMC特征
            order_blocks_count INTEGER,
            liquidity_zones_count INTEGER,
            fvg_count INTEGER,
            swing_high_distance DECIMAL(10, 6),
            swing_low_distance DECIMAL(10, 6),
            order_flow DECIMAL(5, 4),
            liquidity_grab SMALLINT,
            institutional_candle SMALLINT,
            
            -- EMA斜率
            ema50_slope DECIMAL(10, 6),
            ema200_slope DECIMAL(10, 6),
            
            -- 支撑/阻力
            support_strength DECIMAL(5, 4),
            resistance_strength DECIMAL(5, 4),
            higher_highs INTEGER,
            lower_lows INTEGER,
            
            -- 市场微观结构
            volume_profile DECIMAL(5, 4),
            price_momentum DECIMAL(10, 6),
            
            -- 竞价特征
            competition_rank INTEGER,
            score_gap_to_best DECIMAL(10, 6),
            num_competing_signals INTEGER,
            
            -- WebSocket特征
            latency_zscore DECIMAL(10, 4),
            shard_load DECIMAL(5, 4),
            timestamp_consistency SMALLINT,
            
            -- 其他信息
            reason TEXT,
            hold_duration_seconds INTEGER,
            entry_id VARCHAR(100) UNIQUE,
            metadata JSONB
        );
        """
        
        db_manager.execute_query(create_table_sql, fetch=False)
        
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);",
            "CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(entry_timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, entry_timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);",
            "CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);",
            "CREATE INDEX IF NOT EXISTS idx_trades_won ON trades(won) WHERE won IS NOT NULL;",
            "CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at DESC);",
        ]
        
        for index_sql in indices:
            db_manager.execute_query(index_sql, fetch=False)
        
        logger.info("✅ trades 表创建成功")
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建 trades 表失败: {e}")
        return False


def _create_ml_models_table(db_manager: DatabaseManager) -> bool:
    """创建ML模型存储表"""
    try:
        logger.info("📝 创建 ml_models 表...")
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS ml_models (
            id SERIAL PRIMARY KEY,
            model_name VARCHAR(100) NOT NULL,
            version INTEGER DEFAULT 1,
            
            -- 模型数据（二进制）
            model_data BYTEA NOT NULL,
            
            -- 模型元数据
            accuracy DECIMAL(5, 4),
            precision_score DECIMAL(5, 4),
            recall DECIMAL(5, 4),
            f1_score DECIMAL(5, 4),
            
            -- 特征信息（JSON）
            features JSONB NOT NULL,
            feature_count INTEGER,
            
            -- 训练参数（JSON）
            parameters JSONB,
            training_samples INTEGER,
            
            -- 状态
            is_active BOOLEAN DEFAULT FALSE,
            
            -- 时间戳
            trained_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            
            -- 备注
            description TEXT,
            metadata JSONB,
            
            UNIQUE(model_name, version)
        );
        """
        
        db_manager.execute_query(create_table_sql, fetch=False)
        
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_ml_models_name ON ml_models(model_name);",
            "CREATE INDEX IF NOT EXISTS idx_ml_models_active ON ml_models(is_active) WHERE is_active = TRUE;",
            "CREATE INDEX IF NOT EXISTS idx_ml_models_version ON ml_models(model_name, version DESC);",
        ]
        
        for index_sql in indices:
            db_manager.execute_query(index_sql, fetch=False)
        
        logger.info("✅ ml_models 表创建成功")
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建 ml_models 表失败: {e}")
        return False


def _create_market_data_table(db_manager: DatabaseManager) -> bool:
    """创建市场数据表"""
    try:
        logger.info("📝 创建 market_data 表...")
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS market_data (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            timeframe VARCHAR(10) NOT NULL,
            
            -- OHLCV数据
            timestamp TIMESTAMPTZ NOT NULL,
            open DECIMAL(18, 8) NOT NULL,
            high DECIMAL(18, 8) NOT NULL,
            low DECIMAL(18, 8) NOT NULL,
            close DECIMAL(18, 8) NOT NULL,
            volume DECIMAL(18, 8) NOT NULL,
            
            -- 技术指标
            rsi DECIMAL(10, 4),
            macd DECIMAL(18, 8),
            macd_signal DECIMAL(18, 8),
            bb_upper DECIMAL(18, 8),
            bb_middle DECIMAL(18, 8),
            bb_lower DECIMAL(18, 8),
            
            -- 其他指标
            atr DECIMAL(18, 8),
            ema20 DECIMAL(18, 8),
            ema50 DECIMAL(18, 8),
            ema200 DECIMAL(18, 8),
            
            -- 时间戳
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            
            -- 元数据
            metadata JSONB,
            
            UNIQUE(symbol, timeframe, timestamp)
        );
        """
        
        db_manager.execute_query(create_table_sql, fetch=False)
        
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data(symbol, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_market_data_timeframe ON market_data(timeframe, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_market_data_timestamp ON market_data(timestamp DESC);",
        ]
        
        for index_sql in indices:
            db_manager.execute_query(index_sql, fetch=False)
        
        logger.info("✅ market_data 表创建成功")
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建 market_data 表失败: {e}")
        return False


def _create_trading_signals_table(db_manager: DatabaseManager) -> bool:
    """创建交易信号表"""
    try:
        logger.info("📝 创建 trading_signals 表...")
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS trading_signals (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            direction VARCHAR(10) NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
            
            -- 信号信息
            confidence DECIMAL(5, 4) NOT NULL,
            win_probability DECIMAL(5, 4),
            signal_strength DECIMAL(5, 4),
            
            -- 价格信息
            entry_price DECIMAL(18, 8) NOT NULL,
            stop_loss DECIMAL(18, 8),
            take_profit DECIMAL(18, 8),
            
            -- 策略信息
            strategy VARCHAR(100),
            timeframe VARCHAR(10),
            
            -- 状态
            status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'EXECUTED', 'CANCELLED', 'EXPIRED')),
            executed BOOLEAN DEFAULT FALSE,
            
            -- 时间戳
            signal_timestamp TIMESTAMPTZ NOT NULL,
            execution_timestamp TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            
            -- 关联交易ID
            trade_id INTEGER REFERENCES trades(id),
            
            -- 信号特征（JSON）
            features JSONB,
            
            -- 备注
            reason TEXT,
            metadata JSONB
        );
        """
        
        db_manager.execute_query(create_table_sql, fetch=False)
        
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_signals_symbol ON trading_signals(symbol);",
            "CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON trading_signals(signal_timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_signals_status ON trading_signals(status);",
            "CREATE INDEX IF NOT EXISTS idx_signals_executed ON trading_signals(executed);",
            "CREATE INDEX IF NOT EXISTS idx_signals_strategy ON trading_signals(strategy);",
        ]
        
        for index_sql in indices:
            db_manager.execute_query(index_sql, fetch=False)
        
        logger.info("✅ trading_signals 表创建成功")
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建 trading_signals 表失败: {e}")
        return False


def _create_position_entry_times_table(db_manager: DatabaseManager) -> bool:
    """
    创建持仓开仓时间表
    用于持久化持仓进入时间，防止系统重启后时间基础止损计时重置
    """
    try:
        logger.debug("创建 position_entry_times 表...")
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS position_entry_times (
            symbol VARCHAR(20) PRIMARY KEY,
            entry_time TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        db_manager.execute_query(create_table_sql, fetch=False)
        
        # 创建索引
        index_sql = "CREATE INDEX IF NOT EXISTS idx_position_entry_times_entry_time ON position_entry_times(entry_time DESC);"
        db_manager.execute_query(index_sql, fetch=False)
        
        logger.info("✅ position_entry_times 表创建成功")
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建 position_entry_times 表失败: {e}")
        return False
