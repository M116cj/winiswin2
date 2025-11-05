"""
OptimizedTradeRecorder - 批量I/O优化版本
🔥 v3.24+ 新增功能：
- 真正的异步I/O（aiofiles，避免阻塞）
- 写缓冲区优化（减少系统调用）
- 文件轮转和压缩（自动管理历史数据）
- 性能监控（I/O统计）
"""

import json
import os
import gzip
from typing import Dict, List, Optional, TYPE_CHECKING
from datetime import datetime
import logging
import asyncio
from pathlib import Path

if TYPE_CHECKING:
    import aiofiles

try:
    import aiofiles  # type: ignore
    AIOFILES_AVAILABLE = True
except ImportError:
    aiofiles = None  # type: ignore
    AIOFILES_AVAILABLE = False
    logging.warning("⚠️ aiofiles未安装，将使用同步I/O（性能较低）")

from src.config import Config

logger = logging.getLogger(__name__)


class OptimizedTradeRecorder:
    """
    优化的交易记录器（批量I/O + 异步写入 + 文件轮转）
    
    关键优化：
    1. 真正的异步I/O：使用aiofiles避免阻塞
    2. 写缓冲区：累积到一定大小再flush（减少系统调用）
    3. 文件轮转：自动轮转大文件并压缩（节省空间）
    4. 性能监控：跟踪I/O统计（writes, bytes_written等）
    """
    
    def __init__(
        self,
        trades_file: str = "data/trades.jsonl",
        pending_file: str = "data/ml_pending.json",
        buffer_size: int = 100,  # 缓冲区大小（条数）
        rotation_size_mb: float = 50,  # 文件轮转大小（MB）
        enable_compression: bool = True  # 启用压缩
    ):
        """
        初始化优化记录器
        
        Args:
            trades_file: 交易记录文件路径
            pending_file: 待配对记录文件路径
            buffer_size: 缓冲区大小（触发flush的交易数）
            rotation_size_mb: 文件轮转阈值（MB）
            enable_compression: 是否启用历史文件压缩
        """
        self.trades_file = trades_file
        self.pending_file = pending_file
        self.buffer_size = buffer_size
        self.rotation_size_bytes = rotation_size_mb * 1024 * 1024
        self.enable_compression = enable_compression
        
        # 🔥 v3.24+ 写缓冲区（内存缓存）
        self._write_buffer: List[str] = []
        self._buffer_lock = asyncio.Lock()
        
        # 🔥 v3.24.1+ 定时flush机制（实时保存）
        self._auto_flush_task: Optional[asyncio.Task] = None
        self._auto_flush_interval = 10.0  # 每10秒自动flush
        
        # 🔥 v3.24+ I/O性能统计
        self._stats = {
            'total_writes': 0,
            'total_bytes_written': 0,
            'total_flushes': 0,
            'total_rotations': 0,
            'total_compressions': 0,
            'last_flush_time': None,
            'avg_flush_duration_ms': 0.0
        }
        self._stats_lock = asyncio.Lock()
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.trades_file), exist_ok=True)
        
        logger.info("=" * 80)
        logger.info("🚀 OptimizedTradeRecorder 初始化完成")
        logger.info(f"   📁 交易文件: {self.trades_file}")
        logger.info(f"   📦 缓冲区大小: {buffer_size} 条")
        logger.info(f"   🔄 轮转阈值: {rotation_size_mb} MB")
        logger.info(f"   📦 压缩: {'启用' if enable_compression else '禁用'}")
        logger.info(f"   ⚡ 异步I/O: {'启用 (aiofiles)' if AIOFILES_AVAILABLE else '禁用 (同步fallback)'}")
        logger.info(f"   ⏰ 定时flush: {self._auto_flush_interval}秒（自动启动）")
        logger.info("=" * 80)
        
        # 🔥 v3.24.2 Critical Fix: 默认启动定时flush（实时保存保证）
        # 注意：在__init__中不能直接await，需要延迟到第一次使用时
        self._auto_flush_enabled = True  # 标记需要自动启动
    
    async def write_trade(self, trade_data: Dict):
        """
        写入单条交易（添加到缓冲区）
        
        Args:
            trade_data: 交易数据字典
        """
        # 🔥 v3.24.2 Critical Fix: 第一次写入时自动启动定时flush
        await self._ensure_auto_flush_started()
        
        # 序列化为JSONL格式
        line = json.dumps(trade_data, ensure_ascii=False, default=str) + "\n"
        
        async with self._buffer_lock:
            self._write_buffer.append(line)
            buffer_count = len(self._write_buffer)
        
        # 达到缓冲区大小时自动flush
        if buffer_count >= self.buffer_size:
            await self.flush()
    
    async def write_trades_batch(self, trades: List[Dict]):
        """
        批量写入交易（高效批量操作）
        
        Args:
            trades: 交易数据列表
        """
        if not trades:
            logger.info(f"🔍 [DIAG] OptimizedTradeRecorder.write_trades_batch: 空交易列表")
            return
        
        logger.info(f"🔍 [DIAG] OptimizedTradeRecorder.write_trades_batch: 收到{len(trades)}筆交易")
        
        # 🔥 v3.24.2 Critical Fix: 第一次写入时自动启动定时flush
        await self._ensure_auto_flush_started()
        
        # 批量序列化
        lines = [
            json.dumps(trade, ensure_ascii=False, default=str) + "\n"
            for trade in trades
        ]
        
        logger.info(f"🔍 [DIAG] OptimizedTradeRecorder: 序列化完成，{len(lines)}行")
        
        async with self._buffer_lock:
            self._write_buffer.extend(lines)
            buffer_count = len(self._write_buffer)
        
        logger.info(f"🔍 [DIAG] OptimizedTradeRecorder: 緩衝區大小={buffer_count}, 閾值={self.buffer_size}")
        
        # 批量写入后立即flush
        if buffer_count >= self.buffer_size:
            logger.info(f"🔍 [DIAG] OptimizedTradeRecorder: 觸發flush")
            await self.flush()
        else:
            logger.info(f"🔍 [DIAG] OptimizedTradeRecorder: 未觸發flush，等待更多數據")
    
    async def flush(self):
        """
        强制刷新缓冲区到磁盘（异步I/O）
        """
        logger.info(f"🔍 [DIAG] OptimizedTradeRecorder.flush: 開始flush")
        start_time = datetime.now()
        
        async with self._buffer_lock:
            if not self._write_buffer:
                logger.info(f"🔍 [DIAG] OptimizedTradeRecorder.flush: 緩衝區為空，跳過")
                return
            
            # 🔥 v3.24.1 Critical Fix: 保存原始lines列表用于失败恢复
            lines_snapshot = self._write_buffer.copy()
            data_to_write = "".join(self._write_buffer)
            num_lines = len(self._write_buffer)
            self._write_buffer = []
        
        logger.info(f"🔍 [DIAG] OptimizedTradeRecorder.flush: 準備寫入{num_lines}行到{self.trades_file}")
        
        # 🔥 检查文件轮转
        await self._maybe_rotate_file()
        
        # 🔥 异步写入磁盘
        try:
            if AIOFILES_AVAILABLE:
                logger.info(f"🔍 [DIAG] OptimizedTradeRecorder.flush: 使用aiofiles異步寫入")
                await self._async_append(data_to_write)
            else:
                logger.info(f"🔍 [DIAG] OptimizedTradeRecorder.flush: 使用同步fallback寫入")
                await self._sync_append_fallback(data_to_write)
            
            # 更新统计
            bytes_written = len(data_to_write.encode('utf-8'))
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            async with self._stats_lock:
                self._stats['total_writes'] += num_lines
                self._stats['total_bytes_written'] += bytes_written
                self._stats['total_flushes'] += 1
                self._stats['last_flush_time'] = datetime.now().isoformat()
                
                # 更新平均flush时间（移动平均）
                alpha = 0.3
                self._stats['avg_flush_duration_ms'] = (
                    alpha * duration_ms +
                    (1 - alpha) * self._stats['avg_flush_duration_ms']
                )
            
            logger.info(f"💾 Flush完成: {num_lines}条记录, {bytes_written}字节, {duration_ms:.2f}ms")
            logger.info(f"🔍 [DIAG] OptimizedTradeRecorder.flush: 成功完成")
        
        except Exception as e:
            logger.error(f"❌ Flush失败: {e}", exc_info=True)
            logger.error(f"🔍 [DIAG] OptimizedTradeRecorder.flush: 寫入失敗，恢復緩衝區")
            # 🔥 v3.24.1 Critical Fix: 恢复原始lines列表（保持缓冲区不变性）
            async with self._buffer_lock:
                self._write_buffer = lines_snapshot + self._write_buffer
            raise
    
    async def _async_append(self, data: str):
        """使用aiofiles异步追加数据"""
        if aiofiles is None:
            raise RuntimeError("aiofiles not available")
        async with aiofiles.open(self.trades_file, 'a', encoding='utf-8') as f:  # type: ignore
            await f.write(data)
    
    async def _sync_append_fallback(self, data: str):
        """同步I/O fallback（无aiofiles时）"""
        await asyncio.to_thread(self._sync_append, data)
    
    def _sync_append(self, data: str):
        """纯同步追加（在线程中运行）"""
        with open(self.trades_file, 'a', encoding='utf-8') as f:
            f.write(data)
    
    async def _maybe_rotate_file(self):
        """
        检查并执行文件轮转（大文件自动轮转）
        """
        try:
            file_size = os.path.getsize(self.trades_file) if os.path.exists(self.trades_file) else 0
            
            if file_size >= self.rotation_size_bytes:
                await self._rotate_file()
        
        except Exception as e:
            logger.error(f"❌ 文件轮转检查失败: {e}")
    
    async def _rotate_file(self):
        """
        轮转文件并可选压缩
        
        逻辑：
        1. 重命名当前文件为 trades_YYYYMMDD_HHMMSS.jsonl
        2. 如果启用压缩，压缩旧文件
        3. 创建新的空文件
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_file = self.trades_file.replace(".jsonl", f"_{timestamp}.jsonl")
            
            # 重命名当前文件
            if os.path.exists(self.trades_file):
                await asyncio.to_thread(os.rename, self.trades_file, rotated_file)
                
                async with self._stats_lock:
                    self._stats['total_rotations'] += 1
                
                logger.info(f"🔄 文件轮转: {self.trades_file} → {rotated_file}")
                
                # 压缩旧文件（如果启用）
                if self.enable_compression:
                    asyncio.create_task(self._compress_file(rotated_file))
        
        except Exception as e:
            logger.error(f"❌ 文件轮转失败: {e}")
    
    async def _compress_file(self, file_path: str):
        """
        压缩文件（后台任务）
        
        Args:
            file_path: 要压缩的文件路径
        """
        try:
            compressed_path = file_path + ".gz"
            
            # 异步压缩（在线程中执行）
            await asyncio.to_thread(self._sync_compress, file_path, compressed_path)
            
            # 删除原文件
            await asyncio.to_thread(os.remove, file_path)
            
            async with self._stats_lock:
                self._stats['total_compressions'] += 1
            
            original_size = os.path.getsize(compressed_path)
            logger.info(f"📦 压缩完成: {file_path} → {compressed_path} ({original_size / 1024 / 1024:.2f} MB)")
        
        except Exception as e:
            logger.error(f"❌ 文件压缩失败: {e}")
    
    def _sync_compress(self, source: str, dest: str):
        """同步压缩文件"""
        with open(source, 'rb') as f_in:
            with gzip.open(dest, 'wb', compresslevel=6) as f_out:
                f_out.writelines(f_in)
    
    async def save_pending_entries(self, pending_entries: List[Dict]):
        """
        保存待配对条目（覆盖写入）
        
        Args:
            pending_entries: 待配对条目列表
        """
        try:
            if AIOFILES_AVAILABLE and aiofiles is not None:
                async with aiofiles.open(self.pending_file, 'w', encoding='utf-8') as f:  # type: ignore
                    content = json.dumps(pending_entries, ensure_ascii=False, indent=2, default=str)
                    await f.write(content)
            else:
                await asyncio.to_thread(
                    self._sync_save_pending,
                    pending_entries
                )
            
            logger.debug(f"💾 保存 {len(pending_entries)} 条待配对记录")
        
        except Exception as e:
            logger.error(f"❌ 保存待配对记录失败: {e}")
    
    def _sync_save_pending(self, pending_entries: List[Dict]):
        """同步保存待配对记录"""
        with open(self.pending_file, 'w', encoding='utf-8') as f:
            json.dump(pending_entries, f, ensure_ascii=False, indent=2, default=str)
    
    async def _ensure_auto_flush_started(self):
        """
        🔥 v3.24.2 Critical Fix: 确保定时flush已启动（第一次写入时自动调用）
        """
        if self._auto_flush_enabled and self._auto_flush_task is None:
            await self.start_auto_flush()
    
    async def start_auto_flush(self):
        """
        🔥 v3.24.1+ 启动定时flush任务（实时保存）
        """
        if self._auto_flush_task is None:
            self._auto_flush_task = asyncio.create_task(self._auto_flush_loop())
            logger.info(f"🔄 定时flush已启动（间隔: {self._auto_flush_interval}秒）")
    
    async def stop_auto_flush(self):
        """
        🔥 v3.24.1+ 停止定时flush任务
        """
        if self._auto_flush_task:
            self._auto_flush_task.cancel()
            try:
                await self._auto_flush_task
            except asyncio.CancelledError:
                pass
            self._auto_flush_task = None
            logger.info("⏸️  定时flush已停止")
    
    async def _auto_flush_loop(self):
        """
        🔥 v3.24.1+ 定时flush循环（后台任务）
        """
        try:
            while True:
                await asyncio.sleep(self._auto_flush_interval)
                
                # 检查是否有待flush数据
                async with self._buffer_lock:
                    has_data = len(self._write_buffer) > 0
                
                if has_data:
                    try:
                        await self.flush()
                        logger.debug("🔄 定时flush完成")
                    except Exception as e:
                        logger.error(f"❌ 定时flush失败: {e}")
        
        except asyncio.CancelledError:
            logger.debug("🔄 定时flush任务已取消")
            raise
    
    async def get_stats(self) -> Dict:
        """
        获取I/O性能统计
        
        Returns:
            统计数据字典
        """
        async with self._stats_lock:
            return self._stats.copy()
    
    async def close(self):
        """
        关闭记录器（最终flush）
        """
        logger.info("⏸️  OptimizedTradeRecorder 关闭中...")
        
        # 停止定时flush
        await self.stop_auto_flush()
        
        # 最终flush
        await self.flush()
        
        # 打印统计
        stats = await self.get_stats()
        logger.info("=" * 80)
        logger.info("📊 OptimizedTradeRecorder 统计数据:")
        logger.info(f"   总写入: {stats['total_writes']} 条记录")
        logger.info(f"   总字节数: {stats['total_bytes_written'] / 1024 / 1024:.2f} MB")
        logger.info(f"   总flush次数: {stats['total_flushes']}")
        logger.info(f"   平均flush时间: {stats['avg_flush_duration_ms']:.2f} ms")
        logger.info(f"   文件轮转次数: {stats['total_rotations']}")
        logger.info(f"   压缩次数: {stats['total_compressions']}")
        logger.info("=" * 80)
        
        logger.info("✅ OptimizedTradeRecorder 已关闭")
