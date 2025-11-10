"""
TradingDataService - 交易数据服务层
提供所有数据库操作的高级接口
"""

import logging
import pickle
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from psycopg2.extras import Json
from .manager import DatabaseManager

logger = logging.getLogger(__name__)


class TradingDataService:
    """
    交易数据服务
    
    提供：
    - 交易记录CRUD操作
    - ML模型管理
    - 市场数据存储
    - 交易信号管理
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初始化交易数据服务
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db = db_manager
    
    # ==================== 交易记录操作 ====================
    
    def save_trade(self, trade_data: Dict[str, Any]) -> Optional[int]:
        """
        保存交易记录
        
        Args:
            trade_data: 交易数据字典
            
        Returns:
            插入的交易ID，失败返回None
        """
        try:
            # 必需字段
            required_fields = ['symbol', 'direction', 'entry_price', 'quantity', 'entry_timestamp']
            for field in required_fields:
                if field not in trade_data:
                    logger.error(f"缺少必需字段: {field}")
                    return None
            
            # 构建INSERT语句
            query = """
                INSERT INTO trades (
                    symbol, direction, entry_price, quantity, entry_timestamp,
                    exit_price, exit_timestamp, leverage, pnl, pnl_pct,
                    status, won, strategy, confidence, win_probability,
                    position_value, risk_reward_ratio, stop_loss, take_profit,
                    rsi, macd, macd_signal, macd_histogram, atr, bb_width,
                    volume_sma_ratio, ema50, ema200, volatility_24h,
                    trend_1h, trend_15m, trend_5m, market_structure, trend_alignment,
                    order_blocks_count, liquidity_zones_count, fvg_count,
                    swing_high_distance, swing_low_distance, order_flow,
                    liquidity_grab, institutional_candle,
                    ema50_slope, ema200_slope, support_strength, resistance_strength,
                    higher_highs, lower_lows, volume_profile, price_momentum,
                    competition_rank, score_gap_to_best, num_competing_signals,
                    latency_zscore, shard_load, timestamp_consistency,
                    reason, hold_duration_seconds, entry_id, metadata
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id;
            """
            
            params = (
                trade_data.get('symbol'),
                trade_data.get('direction'),
                trade_data.get('entry_price'),
                trade_data.get('quantity'),
                trade_data.get('entry_timestamp'),
                trade_data.get('exit_price'),
                trade_data.get('exit_timestamp'),
                trade_data.get('leverage', 1),
                trade_data.get('pnl'),
                trade_data.get('pnl_pct'),
                trade_data.get('status', 'OPEN'),
                trade_data.get('won'),
                trade_data.get('strategy'),
                trade_data.get('confidence'),
                trade_data.get('win_probability'),
                trade_data.get('position_value'),
                trade_data.get('risk_reward_ratio'),
                trade_data.get('stop_loss'),
                trade_data.get('take_profit'),
                trade_data.get('rsi'),
                trade_data.get('macd'),
                trade_data.get('macd_signal'),
                trade_data.get('macd_histogram'),
                trade_data.get('atr'),
                trade_data.get('bb_width'),
                trade_data.get('volume_sma_ratio'),
                trade_data.get('ema50'),
                trade_data.get('ema200'),
                trade_data.get('volatility_24h'),
                trade_data.get('trend_1h'),
                trade_data.get('trend_15m'),
                trade_data.get('trend_5m'),
                trade_data.get('market_structure'),
                trade_data.get('trend_alignment'),
                trade_data.get('order_blocks_count'),
                trade_data.get('liquidity_zones_count'),
                trade_data.get('fvg_count'),
                trade_data.get('swing_high_distance'),
                trade_data.get('swing_low_distance'),
                trade_data.get('order_flow'),
                trade_data.get('liquidity_grab'),
                trade_data.get('institutional_candle'),
                trade_data.get('ema50_slope'),
                trade_data.get('ema200_slope'),
                trade_data.get('support_strength'),
                trade_data.get('resistance_strength'),
                trade_data.get('higher_highs'),
                trade_data.get('lower_lows'),
                trade_data.get('volume_profile'),
                trade_data.get('price_momentum'),
                trade_data.get('competition_rank'),
                trade_data.get('score_gap_to_best'),
                trade_data.get('num_competing_signals'),
                trade_data.get('latency_zscore'),
                trade_data.get('shard_load'),
                trade_data.get('timestamp_consistency'),
                trade_data.get('reason'),
                trade_data.get('hold_duration_seconds'),
                trade_data.get('entry_id'),
                Json(trade_data.get('metadata')) if trade_data.get('metadata') else None
            )
            
            # 🔥 v3.34+ 增强日志：追踪数据库写入
            logger.info(f"💾 准备保存交易: {trade_data.get('symbol')} {trade_data.get('direction')}")
            logger.debug(f"   SQL: INSERT INTO trades ... RETURNING id")
            
            result = self.db.execute_query(query, params, fetch=True)
            
            # 🔥 v3.34+ 修复：检测 RETURNING 是否返回结果
            logger.debug(f"   execute_query 返回值类型: {type(result)}, 内容: {result}")
            
            if result and len(result) > 0:
                trade_id = result[0]  # 🔥 修复：fetchone() 返回 tuple，不是 list of tuples
                logger.info(f"✅ 交易记录已保存，PostgreSQL ID: {trade_id}")
                return trade_id
            else:
                logger.error(f"❌ INSERT RETURNING 未返回 ID（result={result}）")
                logger.error("   可能原因：execute_query 未正确处理 RETURNING 子句")
                return None
            
        except Exception as e:
            logger.error(f"❌ 保存交易记录失败: {e}")
            logger.exception("详细错误:")
            return None
    
    def get_trade_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        获取交易历史
        
        Args:
            symbol: 交易对（可选）
            limit: 返回记录数限制
            status: 交易状态（可选）
            
        Returns:
            交易记录列表
        """
        try:
            conditions = []
            params = []
            
            if symbol:
                conditions.append("symbol = %s")
                params.append(symbol)
            
            if status:
                conditions.append("status = %s")
                params.append(status)
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT * FROM trades
                {where_clause}
                ORDER BY entry_timestamp DESC
                LIMIT %s;
            """
            
            params.append(limit)
            
            result = self.db.execute_query(query, tuple(params), fetch=True)
            
            if result:
                logger.info(f"✅ 获取到 {len(result)} 条交易记录")
                return [self._row_to_dict(row) for row in result]
            
            return []
            
        except Exception as e:
            logger.error(f"❌ 获取交易历史失败: {e}")
            return []
    
    def update_trade_status(
        self,
        trade_id: int,
        status: str,
        exit_price: Optional[float] = None,
        pnl: Optional[float] = None,
        pnl_pct: Optional[float] = None,
        exit_timestamp: Optional[str] = None,
        reason: Optional[str] = None
    ) -> bool:
        """
        更新交易状态
        
        Args:
            trade_id: 交易ID
            status: 新状态
            exit_price: 出场价格（可选）
            pnl: 盈亏金额（可选）
            pnl_pct: 盈亏百分比（可选）
            exit_timestamp: 出场时间（可选，默认当前时间）
            reason: 平仓原因（可选）
            
        Returns:
            是否成功
        """
        try:
            query = """
                UPDATE trades
                SET status = %s,
                    exit_price = COALESCE(%s, exit_price),
                    exit_timestamp = COALESCE(%s::timestamptz, CASE WHEN %s = 'CLOSED' THEN CURRENT_TIMESTAMP ELSE exit_timestamp END),
                    pnl = COALESCE(%s, pnl),
                    pnl_pct = COALESCE(%s, pnl_pct),
                    won = CASE WHEN %s IS NOT NULL THEN %s > 0 ELSE won END,
                    reason = COALESCE(%s, reason),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
            """
            
            params = (status, exit_price, exit_timestamp, status, pnl, pnl_pct, pnl, pnl, reason, trade_id)
            
            self.db.execute_query(query, params, fetch=False)
            logger.info(f"✅ 交易 {trade_id} 状态已更新为 {status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 更新交易状态失败: {e}")
            return False
    
    # ==================== ML模型操作 ====================
    
    def save_ml_model(
        self,
        model_name: str,
        model: Any,
        features: List[str],
        accuracy: float,
        parameters: Optional[Dict] = None,
        is_active: bool = False,
        version: Optional[int] = None
    ) -> Optional[int]:
        """
        保存ML模型
        
        Args:
            model_name: 模型名称
            model: 模型对象（会被序列化）
            features: 特征列表
            accuracy: 准确率
            parameters: 训练参数（可选）
            is_active: 是否激活
            version: 版本号（可选，默认自动递增）
            
        Returns:
            插入的模型ID，失败返回None
        """
        try:
            # 序列化模型
            model_binary = pickle.dumps(model)
            
            # 如果未指定版本，获取最新版本号并+1
            if version is None:
                version_query = """
                    SELECT COALESCE(MAX(version), 0) + 1
                    FROM ml_models
                    WHERE model_name = %s;
                """
                result = self.db.execute_query(version_query, (model_name,), fetch=True)
                version = result[0][0] if result else 1
            
            query = """
                INSERT INTO ml_models (
                    model_name, version, model_data, accuracy,
                    features, feature_count, parameters,
                    training_samples, is_active, description
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """
            
            params = (
                model_name,
                version,
                model_binary,
                accuracy,
                Json(features),
                len(features),
                Json(parameters or {}),
                parameters.get('training_samples') if parameters else None,
                is_active,
                parameters.get('description') if parameters else None
            )
            
            result = self.db.execute_query(query, params, fetch=True)
            
            if result and len(result) > 0:
                model_id = result[0][0]
                
                # 如果设置为活跃，停用其他同名模型
                if is_active:
                    deactivate_query = """
                        UPDATE ml_models
                        SET is_active = FALSE
                        WHERE model_name = %s AND id != %s;
                    """
                    self.db.execute_query(deactivate_query, (model_name, model_id), fetch=False)
                
                logger.info(f"✅ ML模型已保存: {model_name} v{version}, ID: {model_id}")
                return model_id
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 保存ML模型失败: {e}")
            logger.exception("详细错误:")
            return None
    
    def load_ml_model(
        self,
        model_name: str,
        version: Optional[int] = None
    ) -> Optional[Any]:
        """
        加载ML模型
        
        Args:
            model_name: 模型名称
            version: 版本号（可选，默认加载最新活跃版本）
            
        Returns:
            反序列化的模型对象，失败返回None
        """
        try:
            if version:
                query = """
                    SELECT model_data FROM ml_models
                    WHERE model_name = %s AND version = %s;
                """
                params = (model_name, version)
            else:
                query = """
                    SELECT model_data FROM ml_models
                    WHERE model_name = %s AND is_active = TRUE
                    ORDER BY version DESC
                    LIMIT 1;
                """
                params = (model_name,)
            
            result = self.db.execute_query(query, params, fetch=True)
            
            if result and len(result) > 0:
                model_data = result[0][0]
                model = pickle.loads(bytes(model_data))
                logger.info(f"✅ ML模型已加载: {model_name}")
                return model
            
            logger.warning(f"⚠️ 未找到模型: {model_name}")
            return None
            
        except Exception as e:
            logger.error(f"❌ 加载ML模型失败: {e}")
            return None
    
    # ==================== 辅助方法 ====================
    
    def _row_to_dict(self, row: tuple) -> Dict:
        """将数据库行转换为字典（简化版）"""
        # 这里应该根据实际列名映射
        # 暂时返回原始数据
        return {"raw_data": row}
    
    def get_trade_count(self, filter_type: str = 'all') -> int:
        """
        获取交易数量
        
        Args:
            filter_type: 过滤类型
                - 'all': 所有交易
                - 'closed': 已关闭交易
                - 'open': 开仓交易
                - 或者交易对符号（如 'BTCUSDT'）
        
        Returns:
            交易数量
        """
        try:
            if filter_type == 'all':
                query = "SELECT COUNT(*) FROM trades;"
                params = None
            elif filter_type == 'closed':
                query = "SELECT COUNT(*) FROM trades WHERE status = 'CLOSED';"
                params = None
            elif filter_type == 'open':
                query = "SELECT COUNT(*) FROM trades WHERE status = 'OPEN';"
                params = None
            else:
                query = "SELECT COUNT(*) FROM trades WHERE symbol = %s;"
                params = (filter_type,)
            
            result = self.db.execute_query(query, params, fetch=True)
            
            if result and len(result) > 0:
                count = result[0][0] or 0
                return count
            
            return 0
            
        except Exception as e:
            logger.error(f"❌ 获取交易数量失败: {e}")
            return 0
    
    def get_statistics(self) -> Dict:
        """获取交易统计数据"""
        try:
            query = """
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed_trades,
                    COUNT(CASE WHEN won = TRUE THEN 1 END) as winning_trades,
                    AVG(pnl_pct) as avg_pnl_pct,
                    SUM(pnl) as total_pnl
                FROM trades;
            """
            
            result = self.db.execute_query(query, fetch=True)
            
            if result:
                stats = {
                    'total_trades': result[0][0] or 0,
                    'closed_trades': result[0][1] or 0,
                    'winning_trades': result[0][2] or 0,
                    'avg_pnl_pct': float(result[0][3]) if result[0][3] else 0.0,
                    'total_pnl': float(result[0][4]) if result[0][4] else 0.0
                }
                
                if stats['closed_trades'] > 0:
                    stats['win_rate'] = stats['winning_trades'] / stats['closed_trades']
                else:
                    stats['win_rate'] = 0.0
                
                return stats
            
            return {}
            
        except Exception as e:
            logger.error(f"❌ 获取统计数据失败: {e}")
            return {}
