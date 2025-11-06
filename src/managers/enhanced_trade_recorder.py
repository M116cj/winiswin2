"""
Enhanced TradeRecorder v3.29+ - 完整并发保护实现
职责：线程安全的交易记录、三层锁机制、事务支持
"""

import json
import asyncio
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import asynccontextmanager
from dataclasses import dataclass, asdict
import logging
import aiofiles

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """交易记录数据类"""
    symbol: str
    direction: str
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    pnl: Optional[float]
    pnl_pct: Optional[float]
    entry_timestamp: str
    exit_timestamp: Optional[str]
    confidence: float
    win_probability: float
    leverage: int
    reason: Optional[str] = None
    

class EnhancedTradeRecorder:
    """
    增强版交易记录器 v3.29+
    
    特性：
    1. 三层锁保护：flush_lock, write_lock, db_lock
    2. 双重检查初始化机制
    3. 事务上下文管理器支持批量操作
    4. 错误恢复机制（写入失败时恢复缓冲区）
    5. 批量记录高性能操作
    6. 完整类型注解和错误处理
    """
    
    def __init__(
        self,
        trades_file: str = "data/trades.jsonl",
        pending_file: str = "data/pending_entries.json",
        buffer_size: int = 10
    ):
        """
        初始化增强版交易记录器
        
        Args:
            trades_file: 完成交易文件路径
            pending_file: 待配对交易文件路径
            buffer_size: 缓冲区大小
        """
        self.trades_file = trades_file
        self.pending_file = pending_file
        self.buffer_size = buffer_size
        
        # 数据存储
        self.pending_entries: List[Dict[str, Any]] = []
        self.completed_trades: List[Dict[str, Any]] = []
        self.write_buffer: List[str] = []
        
        # 🔥 三层锁机制
        self._flush_lock = asyncio.Lock()  # Flush操作锁（防止并发flush）
        self._write_lock = threading.RLock()  # 写入锁（保护缓冲区）
        self._db_lock = threading.RLock()  # 数据库操作锁（保护文件I/O）
        
        # 初始化标志（用于双重检查）
        self._initialized = False
        self._init_lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            'total_entries': 0,
            'total_exits': 0,
            'flush_count': 0,
            'error_count': 0,
            'recovered_count': 0
        }
        
        # 初始化
        self._ensure_initialized()
        
        logger.info("=" * 80)
        logger.info("✅ EnhancedTradeRecorder v3.29+ 初始化完成")
        logger.info(f"   📝 交易文件: {trades_file}")
        logger.info(f"   📋 待处理文件: {pending_file}")
        logger.info(f"   🔒 三层锁: flush_lock + write_lock + db_lock")
        logger.info(f"   📦 缓冲区大小: {buffer_size}")
        logger.info("=" * 80)
    
    def _ensure_initialized(self) -> None:
        """双重检查初始化机制（线程安全）"""
        if self._initialized:
            return
        
        with self._init_lock:
            # 再次检查（双重检查模式）
            if self._initialized:
                return
            
            try:
                # 创建数据目录
                import os
                os.makedirs("data", exist_ok=True)
                
                # 加载现有数据
                self._load_pending_entries()
                
                self._initialized = True
                logger.info("✅ 交易记录器初始化完成")
                
            except Exception as e:
                logger.error(f"❌ 初始化失败: {e}", exc_info=True)
                raise
    
    def _load_pending_entries(self) -> None:
        """加载待配对的开仓记录"""
        try:
            with self._db_lock:
                import os
                if os.path.exists(self.pending_file):
                    with open(self.pending_file, 'r', encoding='utf-8') as f:
                        self.pending_entries = json.load(f)
                    logger.info(f"📂 加载了 {len(self.pending_entries)} 条待配对记录")
        except Exception as e:
            logger.error(f"❌ 加载待配对记录失败: {e}")
            self.pending_entries = []
    
    def record_entry(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        confidence: float,
        win_probability: float,
        leverage: int,
        **kwargs
    ) -> str:
        """
        线程安全的记录开仓（使用write_lock保护）
        
        Args:
            symbol: 交易对
            direction: 方向（LONG/SHORT）
            entry_price: 入场价格
            quantity: 数量
            confidence: 信心度
            win_probability: 胜率
            leverage: 杠杆
            **kwargs: 其他参数
            
        Returns:
            entry_id: 开仓记录ID
        """
        with self._write_lock:
            try:
                entry_id = f"{symbol}_{datetime.now().timestamp()}"
                
                entry_data = {
                    'entry_id': entry_id,
                    'symbol': symbol,
                    'direction': direction,
                    'entry_price': entry_price,
                    'quantity': quantity,
                    'confidence': confidence,
                    'win_probability': win_probability,
                    'leverage': leverage,
                    'entry_timestamp': datetime.now().isoformat(),
                    **kwargs
                }
                
                self.pending_entries.append(entry_data)
                self.stats['total_entries'] += 1
                
                logger.debug(f"📝 记录开仓: {symbol} @ {entry_price}")
                
                # 立即保存待配对记录
                self._save_pending_entries()
                
                return entry_id
                
            except Exception as e:
                logger.error(f"❌ 记录开仓失败: {e}", exc_info=True)
                self.stats['error_count'] += 1
                raise
    
    def record_exit(
        self,
        symbol: str,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str = "unknown"
    ) -> Optional[Dict[str, Any]]:
        """
        线程安全的记录平仓（使用write_lock保护）
        
        Args:
            symbol: 交易对
            exit_price: 出场价格
            pnl: 盈亏金额
            pnl_pct: 盈亏百分比
            reason: 平仓原因
            
        Returns:
            完整的交易记录或None
        """
        with self._write_lock:
            try:
                # 查找配对的开仓记录
                entry_data = None
                for i, entry in enumerate(self.pending_entries):
                    if entry['symbol'] == symbol:
                        entry_data = self.pending_entries.pop(i)
                        break
                
                if not entry_data:
                    logger.warning(f"⚠️ 未找到 {symbol} 的开仓记录")
                    return None
                
                # 创建完整交易记录
                trade_record = {
                    **entry_data,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'exit_timestamp': datetime.now().isoformat(),
                    'reason': reason,
                    'hold_duration_seconds': self._calculate_duration(
                        entry_data['entry_timestamp']
                    )
                }
                
                self.completed_trades.append(trade_record)
                self.stats['total_exits'] += 1
                
                # 添加到写入缓冲区
                self._add_to_buffer(trade_record)
                
                logger.info(
                    f"📝 记录平仓: {symbol} PnL: {pnl_pct:+.2%} | {reason}"
                )
                
                return trade_record
                
            except Exception as e:
                logger.error(f"❌ 记录平仓失败: {e}", exc_info=True)
                self.stats['error_count'] += 1
                return None
    
    def _add_to_buffer(self, trade_record: Dict[str, Any]) -> None:
        """添加记录到缓冲区（已在write_lock保护下）"""
        try:
            json_line = json.dumps(trade_record, ensure_ascii=False)
            self.write_buffer.append(json_line)
            
            # 如果缓冲区满了，触发flush
            if len(self.write_buffer) >= self.buffer_size:
                asyncio.create_task(self.flush_to_disk())
                
        except Exception as e:
            logger.error(f"❌ 添加到缓冲区失败: {e}")
            raise
    
    async def flush_to_disk(self) -> bool:
        """
        线程安全的刷新到磁盘（使用flush_lock+db_lock保护）
        
        Returns:
            是否成功
        """
        async with self._flush_lock:
            with self._db_lock:
                try:
                    if not self.write_buffer:
                        return True
                    
                    # 复制缓冲区（错误恢复用）
                    buffer_snapshot = self.write_buffer.copy()
                    
                    # 清空缓冲区
                    with self._write_lock:
                        self.write_buffer.clear()
                    
                    # 写入文件
                    async with aiofiles.open(
                        self.trades_file,
                        'a',
                        encoding='utf-8'
                    ) as f:
                        for line in buffer_snapshot:
                            await f.write(line + '\n')
                    
                    self.stats['flush_count'] += 1
                    logger.debug(
                        f"💾 Flush成功: {len(buffer_snapshot)} 条记录"
                    )
                    
                    return True
                    
                except Exception as e:
                    logger.error(f"❌ Flush失败: {e}", exc_info=True)
                    
                    # 🔥 错误恢复：恢复缓冲区
                    with self._write_lock:
                        self.write_buffer = buffer_snapshot + self.write_buffer
                    
                    self.stats['error_count'] += 1
                    self.stats['recovered_count'] += 1
                    
                    logger.warning("⚠️ 缓冲区已恢复，数据未丢失")
                    return False
    
    def _save_pending_entries(self) -> None:
        """保存待配对记录（已在write_lock保护下）"""
        try:
            with self._db_lock:
                with open(self.pending_file, 'w', encoding='utf-8') as f:
                    json.dump(self.pending_entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存待配对记录失败: {e}")
    
    @asynccontextmanager
    async def transaction(self):
        """
        事务上下文管理器（支持批量操作）
        
        用法：
            async with recorder.transaction():
                recorder.record_entry(...)
                recorder.record_entry(...)
                # 批量flush
        """
        original_buffer_size = self.buffer_size
        
        try:
            # 事务期间禁用自动flush
            self.buffer_size = float('inf')
            yield self
            
            # 事务结束后统一flush
            await self.flush_to_disk()
            
        except Exception as e:
            logger.error(f"❌ 事务失败: {e}", exc_info=True)
            raise
        
        finally:
            # 恢复原始缓冲区大小
            self.buffer_size = original_buffer_size
    
    async def batch_record_entries(
        self,
        entries: List[Dict[str, Any]]
    ) -> List[str]:
        """
        批量记录开仓（高性能）
        
        Args:
            entries: 开仓记录列表
            
        Returns:
            entry_id 列表
        """
        async with self.transaction():
            entry_ids = []
            for entry in entries:
                try:
                    entry_id = self.record_entry(**entry)
                    entry_ids.append(entry_id)
                except Exception as e:
                    logger.error(f"❌ 批量记录失败: {e}")
                    entry_ids.append(None)
            
            logger.info(
                f"📦 批量记录完成: {len(entry_ids)}/{len(entries)} 成功"
            )
            return entry_ids
    
    def _calculate_duration(self, entry_timestamp: str) -> float:
        """计算持仓时长（秒）"""
        try:
            entry_time = datetime.fromisoformat(entry_timestamp)
            duration = (datetime.now() - entry_time).total_seconds()
            return duration
        except:
            return 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            'pending_count': len(self.pending_entries),
            'buffer_count': len(self.write_buffer),
            'completed_count': len(self.completed_trades)
        }
    
    def get_trades(self, days: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取交易记录
        
        Args:
            days: 可选，获取最近N天的交易记录
            
        Returns:
            交易记录列表（包含pending和completed trades）
        """
        all_trades = []
        
        # 添加待配对记录（open状态）
        for entry_id, entry_data in self.pending_entries.items():
            all_trades.append({
                'entry_id': entry_id,
                'status': 'open',
                **entry_data
            })
        
        # 添加已完成记录（closed状态）
        all_trades.extend(self.completed_trades)
        
        # 如果指定了days，过滤时间范围
        if days is not None:
            cutoff_time = datetime.now() - timedelta(days=days)
            all_trades = [
                t for t in all_trades 
                if datetime.fromisoformat(t.get('entry_timestamp', '1970-01-01')) >= cutoff_time
            ]
        
        return all_trades
    
    async def force_flush(self) -> bool:
        """强制刷新所有缓冲区"""
        success = await self.flush_to_disk()
        if success:
            logger.info("✅ 强制flush完成")
        return success
    
    async def shutdown(self) -> None:
        """优雅关闭（确保所有数据写入磁盘）"""
        logger.info("🔄 开始关闭交易记录器...")
        
        # 强制flush
        await self.force_flush()
        
        # 保存待配对记录
        with self._write_lock:
            self._save_pending_entries()
        
        logger.info("✅ 交易记录器已关闭")
