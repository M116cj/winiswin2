"""
UnifiedTradeRecorder v4.0 - 统一PostgreSQL交易记录器

🎯 职责：
1. 所有交易数据存储到PostgreSQL（唯一数据源）
2. ML特征收集和管理
3. 模型重训练触发
4. 性能指标追踪

🔥 替代以下文件：
- src/managers/trade_recorder.py (800行，JSONL版)
- src/managers/optimized_trade_recorder.py (400行，异步I/O版)
- src/core/trade_recorder.py (600行，SQLite版)
- src/managers/enhanced_trade_recorder.py (300行)

✨ 核心改进：
- 单一数据源（PostgreSQL）
- 异步批量操作
- 自动ML特征提取
- 智能重训练管理
- 线程安全设计
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.database.service import TradingDataService
from src.ml.feature_engine import FeatureEngine
from src.utils.logger_factory import get_logger

logger = get_logger(__name__)


@dataclass
class RecorderStats:
    """记录器统计信息"""
    total_entries: int = 0
    total_exits: int = 0
    total_features_collected: int = 0
    total_retrains_triggered: int = 0
    last_retrain_time: Optional[datetime] = None
    db_saves_success: int = 0
    db_saves_failed: int = 0


class UnifiedTradeRecorder:
    """
    统一交易记录器 v4.0
    
    核心特性：
    - ✅ 单一数据源（PostgreSQL）
    - ✅ 异步批量操作
    - ✅ 自动ML特征收集
    - ✅ 智能模型重训练
    - ✅ 完整统计信息
    - ✅ 线程安全设计
    
    使用示例：
    ```python
    recorder = UnifiedTradeRecorder(
        db_service=db_service,
        model_initializer=model_initializer
    )
    
    # 记录开仓
    trade_id = recorder.record_entry(
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=67000.0,
        quantity=0.01,
        leverage=10,
        signal_data={...},
        klines_data={...}
    )
    
    # 记录平仓
    success = recorder.record_exit(
        trade_id=trade_id,
        exit_price=67500.0,
        pnl=50.0,
        pnl_pct=0.75,
        reason="TP_HIT"
    )
    ```
    """
    
    def __init__(
        self,
        db_service: TradingDataService,
        model_scorer=None,
        model_initializer=None,
        retrain_interval: int = 50
    ):
        """
        初始化统一交易记录器
        
        Args:
            db_service: PostgreSQL数据服务（必需）
            model_scorer: 模型评分器（可选）
            model_initializer: 模型初始化器（用于重训练，可选）
            retrain_interval: 重训练间隔（交易数）
        """
        self.db_service = db_service
        self.model_scorer = model_scorer
        self.model_initializer = model_initializer
        self.retrain_interval = retrain_interval
        
        # ML特征引擎
        try:
            self.feature_engine = FeatureEngine()
            logger.info("✅ FeatureEngine初始化完成（用于ML特征收集）")
        except Exception as e:
            logger.warning(f"⚠️ FeatureEngine初始化失败: {e}，将跳过特征收集")
            self.feature_engine = None
        
        # 统计信息
        self.stats = RecorderStats()
        
        # 倉位指標歷史追蹤（用於強制止盈檢測）
        self.position_metrics_history: Dict[str, List[tuple]] = {}
        self.history_retention_seconds = 600  # 保留10分钟
        
        # 部分平倉記錄
        self.partial_exits: List[Dict] = []
        
        logger.info("=" * 70)
        logger.info("✅ UnifiedTradeRecorder v4.0 初始化完成")
        logger.info("   📊 数据源: PostgreSQL（唯一）")
        logger.info(f"   🔄 重训练间隔: {retrain_interval}笔交易")
        logger.info(f"   🧪 特征引擎: {'启用' if self.feature_engine else '禁用'}")
        logger.info("=" * 70)
    
    def record_entry(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        leverage: int,
        signal_data: Dict,
        klines_data: Optional[Dict] = None,
        **kwargs
    ) -> Optional[int]:
        """
        记录开仓
        
        Args:
            symbol: 交易对（如 BTCUSDT）
            direction: 方向（LONG/SHORT）
            entry_price: 入场价格
            quantity: 数量
            leverage: 杠杆倍数
            signal_data: 信号数据（包含策略信息）
            klines_data: K线数据（用于ML特征提取）
            **kwargs: 其他交易参数
            
        Returns:
            交易ID（PostgreSQL主键），失败返回None
        """
        try:
            # 提取ML特征（如果可用）
            ml_features = {}
            if self.feature_engine and klines_data:
                try:
                    ml_features = self.feature_engine.build_enhanced_features(
                        signal_data,
                        klines_data=klines_data
                    ) or {}
                    self.stats.total_features_collected += 1
                except Exception as e:
                    logger.warning(f"⚠️ ML特征提取失败: {e}，继续记录交易")
            
            # 构建交易记录
            trade_data = {
                # 基础信息
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'quantity': quantity,
                'leverage': leverage,
                'entry_timestamp': datetime.utcnow().isoformat() + 'Z',
                'status': 'OPEN',
                
                # 策略信息
                'strategy': signal_data.get('strategy', 'ICT_SMC'),
                'confidence': signal_data.get('confidence'),
                'win_probability': signal_data.get('win_probability'),
                
                # 风险管理
                'stop_loss': kwargs.get('stop_loss'),
                'take_profit': kwargs.get('take_profit'),
                'position_value': kwargs.get('position_value'),
                'risk_reward_ratio': kwargs.get('risk_reward_ratio'),
                
                # ML特征（如果提取成功）
                **ml_features,
                
                # 元数据
                'metadata': {
                    'signal': signal_data,
                    'collected_at': datetime.utcnow().isoformat(),
                    'recorder_version': '4.0'
                }
            }
            
            # 🔥 v3.34+ 增强日志：追踪数据库写入流程
            logger.info(f"📝 UnifiedTradeRecorder 开始记录开仓: {symbol} {direction}")
            logger.debug(f"   交易数据: confidence={signal_data.get('confidence')}, win_prob={signal_data.get('win_probability')}")
            logger.debug(f"   ML特征数量: {len(ml_features)}")
            
            # 保存到PostgreSQL
            trade_id = self.db_service.save_trade(trade_data)
            
            if trade_id:
                self.stats.total_entries += 1
                self.stats.db_saves_success += 1
                
                logger.info(
                    f"✅ 开仓记录已保存 | PostgreSQL ID: {trade_id} | "
                    f"{symbol} {direction} @{entry_price:.2f} | "
                    f"杠杆: {leverage}x | 数量: {quantity}"
                )
                logger.info(f"📊 统计: 成功={self.stats.db_saves_success}, 失败={self.stats.db_saves_failed}")
                
                return trade_id
            else:
                self.stats.db_saves_failed += 1
                logger.error(f"❌ PostgreSQL保存失败: {symbol} {direction}")
                logger.error(f"   save_trade() 返回 None - 检查 TradingDataService 日志")
                logger.error(f"📊 统计: 成功={self.stats.db_saves_success}, 失败={self.stats.db_saves_failed}")
                return None
                
        except Exception as e:
            self.stats.db_saves_failed += 1
            logger.error(f"❌ 记录开仓失败: {e}", exc_info=True)
            return None
    
    def record_exit(
        self,
        trade_id: int,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str = "MANUAL",
        exit_timestamp: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        记录平仓
        
        Args:
            trade_id: 交易ID（PostgreSQL主键）
            exit_price: 出场价格
            pnl: 盈亏金额（USDT）
            pnl_pct: 盈亏百分比
            reason: 平仓原因（TP_HIT, SL_HIT, MANUAL等）
            exit_timestamp: 出场时间（可选，默认当前时间）
            **kwargs: 其他参数
            
        Returns:
            是否成功
        """
        try:
            # 更新交易状态（包含完整信息）
            exit_time = exit_timestamp or (datetime.utcnow().isoformat() + 'Z')
            
            # 🔥 v3.34+ 增强日志：追踪平仓更新
            logger.info(f"📝 UnifiedTradeRecorder 开始记录平仓: trade_id={trade_id}, PnL={pnl:.2f}")
            
            success = self.db_service.update_trade_status(
                trade_id=trade_id,
                status='CLOSED',
                exit_price=exit_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                exit_timestamp=exit_time,
                reason=reason
            )
            
            if success:
                self.stats.total_exits += 1
                self.stats.db_saves_success += 1
                
                # 判断胜负
                won = pnl > 0
                
                logger.info(
                    f"{'🟢' if won else '🔴'} 平仓记录已更新（PostgreSQL UPDATE成功）| "
                    f"ID: {trade_id} | PnL: {pnl:.2f} USDT ({pnl_pct:+.2f}%) | "
                    f"原因: {reason}"
                )
                
                # 检查是否需要重训练
                self._check_retrain()
                
                # 通知model_scorer（如果有）
                if self.model_scorer:
                    try:
                        self.model_scorer.update_model_performance(
                            model_name="current",
                            pnl=pnl,
                            won=won
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ 更新model_scorer失败: {e}")
                
                return True
            else:
                self.stats.db_saves_failed += 1
                logger.error(f"❌ 更新平仓记录失败，ID: {trade_id}")
                return False
                
        except Exception as e:
            self.stats.db_saves_failed += 1
            logger.error(f"❌ 记录平仓失败: {e}", exc_info=True)
            return False
    
    def _check_retrain(self):
        """检查是否需要触发模型重训练"""
        trades_count = self.stats.total_exits
        
        if trades_count % self.retrain_interval == 0 and trades_count > 0:
            if self.model_initializer:
                logger.info(
                    f"🔄 触发模型重训练 | "
                    f"已完成 {trades_count} 笔交易 | "
                    f"间隔: {self.retrain_interval}"
                )
                
                # 异步触发重训练（不阻塞主流程）
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._async_retrain())
                except RuntimeError:
                    # 如果没有运行的事件循环，同步触发
                    logger.warning("⚠️ 事件循环未运行，跳过异步重训练")
            else:
                logger.debug(f"ℹ️  已完成 {trades_count} 笔交易，但model_initializer未配置")
    
    async def _async_retrain(self):
        """异步执行模型重训练"""
        try:
            if self.model_initializer and hasattr(self.model_initializer, 'retrain_if_needed'):
                await self.model_initializer.retrain_if_needed()
                self.stats.total_retrains_triggered += 1
                self.stats.last_retrain_time = datetime.utcnow()
                logger.info("✅ 模型重训练完成")
            else:
                logger.warning("⚠️ model_initializer未配置或没有retrain_if_needed方法")
        except Exception as e:
            logger.error(f"❌ 模型重训练失败: {e}", exc_info=True)
    
    def record_partial_exit(
        self,
        trade_id: int,
        exit_quantity: float,
        exit_price: float,
        remaining_quantity: float,
        reason: str = "PARTIAL_TP"
    ) -> bool:
        """
        记录部分平仓
        
        Args:
            trade_id: 原交易ID
            exit_quantity: 平仓数量
            exit_price: 平仓价格
            remaining_quantity: 剩余数量
            reason: 原因
            
        Returns:
            是否成功
        """
        try:
            partial_exit = {
                'trade_id': trade_id,
                'exit_quantity': exit_quantity,
                'exit_price': exit_price,
                'remaining_quantity': remaining_quantity,
                'reason': reason,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
            
            self.partial_exits.append(partial_exit)
            
            logger.info(
                f"📊 部分平仓记录 | ID: {trade_id} | "
                f"平仓: {exit_quantity} @{exit_price:.2f} | "
                f"剩余: {remaining_quantity}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 记录部分平仓失败: {e}")
            return False
    
    def update_position_metrics(
        self,
        symbol: str,
        unrealized_pnl_pct: float,
        timestamp: Optional[datetime] = None
    ):
        """
        更新倉位指標歷史（用於強制止盈檢測）
        
        Args:
            symbol: 交易对
            unrealized_pnl_pct: 未实现盈亏百分比
            timestamp: 时间戳
        """
        try:
            ts = timestamp or datetime.utcnow()
            
            if symbol not in self.position_metrics_history:
                self.position_metrics_history[symbol] = []
            
            # 添加新记录
            self.position_metrics_history[symbol].append((ts, unrealized_pnl_pct))
            
            # 清理过期记录
            cutoff_time = datetime.utcnow() - timedelta(seconds=self.history_retention_seconds)
            self.position_metrics_history[symbol] = [
                (t, pnl) for t, pnl in self.position_metrics_history[symbol]
                if t > cutoff_time
            ]
            
        except Exception as e:
            logger.warning(f"⚠️ 更新倉位指標歷史失敗: {e}")
    
    def get_position_metrics_history(self, symbol: str) -> List[tuple]:
        """获取倉位指標歷史"""
        return self.position_metrics_history.get(symbol, [])
    
    async def get_trade_count(self, filter_type: str = 'all') -> int:
        """
        获取交易数量（异步接口）
        
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
            loop = asyncio.get_event_loop()
            count = await loop.run_in_executor(
                None, 
                self.db_service.get_trade_count, 
                filter_type
            )
            return count
        except Exception as e:
            logger.error(f"❌ 获取交易数量失败: {e}")
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            完整的统计数据
        """
        try:
            db_stats = self.db_service.get_statistics()
        except Exception as e:
            logger.warning(f"⚠️ 获取数据库统计失败: {e}")
            db_stats = {}
        
        return {
            'recorder_stats': {
                'total_entries': self.stats.total_entries,
                'total_exits': self.stats.total_exits,
                'total_features_collected': self.stats.total_features_collected,
                'total_retrains_triggered': self.stats.total_retrains_triggered,
                'last_retrain_time': self.stats.last_retrain_time.isoformat() if self.stats.last_retrain_time else None,
                'db_saves_success': self.stats.db_saves_success,
                'db_saves_failed': self.stats.db_saves_failed,
                'partial_exits_count': len(self.partial_exits),
                'position_metrics_tracked': len(self.position_metrics_history)
            },
            'database_stats': db_stats
        }
    
    def get_completed_trades(self, limit: int = 100) -> List[Dict]:
        """
        获取已完成的交易记录（用于兼容性）
        
        Args:
            limit: 返回数量限制
            
        Returns:
            交易记录列表
        """
        try:
            trades = self.db_service.get_trade_history(limit=limit, status='CLOSED')
            return trades or []
        except Exception as e:
            logger.error(f"❌ 获取已完成交易失败: {e}")
            return []
    
    @property
    def completed_trades(self) -> List[Dict]:
        """兼容性属性：返回已完成的交易"""
        return self.get_completed_trades()
    
    def __repr__(self) -> str:
        return (
            f"UnifiedTradeRecorder(v4.0, "
            f"entries={self.stats.total_entries}, "
            f"exits={self.stats.total_exits}, "
            f"success_rate={self.stats.db_saves_success/(self.stats.db_saves_success+self.stats.db_saves_failed)*100:.1f}%)"
        )
