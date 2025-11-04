"""
OptimizedTradeRecorder 使用示例
展示批量I/O优化、异步写入、文件轮转等功能
"""

import asyncio
import logging
from datetime import datetime
from src.managers.optimized_trade_recorder import OptimizedTradeRecorder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def demo_single_writes():
    """演示单条写入（自动缓冲）"""
    logger.info("\n" + "=" * 80)
    logger.info("📝 演示1: 单条写入（自动缓冲+定时flush）")
    logger.info("=" * 80)
    
    recorder = OptimizedTradeRecorder(
        trades_file="data/demo_trades.jsonl",
        buffer_size=5,  # 小缓冲区用于演示
        rotation_size_mb=1,  # 1MB轮转用于演示
        enable_compression=True
    )
    
    # 🔥 v3.24.1+ 启动定时flush（实时保存）
    await recorder.start_auto_flush()
    
    # 写入10条交易（会触发2次自动flush）
    for i in range(10):
        trade = {
            'trade_id': f'DEMO_{i}',
            'symbol': 'BTCUSDT',
            'direction': 'LONG' if i % 2 == 0 else 'SHORT',
            'entry_price': 50000 + i * 100,
            'exit_price': 50100 + i * 100,
            'pnl': 100 + i * 10,
            'timestamp': datetime.now().isoformat()
        }
        
        await recorder.write_trade(trade)
        logger.info(f"✅ 已写入交易 #{i}")
        await asyncio.sleep(0.1)  # 模拟交易间隔
    
    # 最终flush
    await recorder.flush()
    
    # 获取统计
    stats = await recorder.get_stats()
    logger.info(f"\n📊 统计数据: {stats}")
    
    await recorder.close()


async def demo_batch_writes():
    """演示批量写入（高性能）"""
    logger.info("\n" + "=" * 80)
    logger.info("⚡ 演示2: 批量写入（高性能）")
    logger.info("=" * 80)
    
    recorder = OptimizedTradeRecorder(
        trades_file="data/demo_batch_trades.jsonl",
        buffer_size=50,
        rotation_size_mb=1,
        enable_compression=True
    )
    
    # 生成100条交易
    trades = []
    for i in range(100):
        trade = {
            'trade_id': f'BATCH_{i}',
            'symbol': 'ETHUSDT',
            'direction': 'LONG' if i % 3 == 0 else 'SHORT',
            'entry_price': 3000 + i * 10,
            'exit_price': 3010 + i * 10,
            'pnl': 10 + i,
            'timestamp': datetime.now().isoformat()
        }
        trades.append(trade)
    
    # 批量写入
    start = datetime.now()
    await recorder.write_trades_batch(trades)
    duration_ms = (datetime.now() - start).total_seconds() * 1000
    
    logger.info(f"✅ 批量写入100条交易完成，耗时: {duration_ms:.2f}ms")
    
    # 获取统计
    stats = await recorder.get_stats()
    logger.info(f"\n📊 统计数据:")
    logger.info(f"   总写入: {stats['total_writes']} 条")
    logger.info(f"   总字节数: {stats['total_bytes_written']} bytes")
    logger.info(f"   平均flush时间: {stats['avg_flush_duration_ms']:.2f} ms")
    
    await recorder.close()


async def demo_file_rotation():
    """演示文件轮转和压缩"""
    logger.info("\n" + "=" * 80)
    logger.info("🔄 演示3: 文件轮转和压缩")
    logger.info("=" * 80)
    
    recorder = OptimizedTradeRecorder(
        trades_file="data/demo_rotation.jsonl",
        buffer_size=10,
        rotation_size_mb=0.001,  # 1KB轮转阈值（用于快速演示）
        enable_compression=True
    )
    
    # 写入大量数据触发轮转
    for batch in range(5):
        trades = []
        for i in range(20):
            trade = {
                'trade_id': f'ROT_B{batch}_T{i}',
                'symbol': 'BNBUSDT',
                'direction': 'LONG',
                'entry_price': 500 + i,
                'exit_price': 510 + i,
                'pnl': 10,
                'timestamp': datetime.now().isoformat(),
                # 添加一些填充数据以快速达到文件大小
                'metadata': {
                    'notes': 'x' * 500,  # 500字符填充
                    'tags': ['demo', 'rotation', 'test']
                }
            }
            trades.append(trade)
        
        await recorder.write_trades_batch(trades)
        logger.info(f"✅ 已写入批次 #{batch}")
        await asyncio.sleep(0.5)  # 等待可能的后台压缩
    
    # 获取统计
    stats = await recorder.get_stats()
    logger.info(f"\n📊 轮转统计:")
    logger.info(f"   文件轮转次数: {stats['total_rotations']}")
    logger.info(f"   压缩次数: {stats['total_compressions']}")
    
    await recorder.close()
    
    # 等待后台压缩完成
    await asyncio.sleep(2)


async def demo_concurrent_writes():
    """演示并发写入（多协程）"""
    logger.info("\n" + "=" * 80)
    logger.info("🔀 演示4: 并发写入（多协程）")
    logger.info("=" * 80)
    
    recorder = OptimizedTradeRecorder(
        trades_file="data/demo_concurrent.jsonl",
        buffer_size=20,
        rotation_size_mb=1,
        enable_compression=False  # 禁用压缩以加快演示
    )
    
    async def write_worker(worker_id: int, num_trades: int):
        """工作协程"""
        for i in range(num_trades):
            trade = {
                'trade_id': f'W{worker_id}_T{i}',
                'symbol': f'SYMBOL{worker_id}',
                'direction': 'LONG',
                'entry_price': 1000 + i,
                'exit_price': 1010 + i,
                'pnl': 10,
                'timestamp': datetime.now().isoformat(),
                'worker_id': worker_id
            }
            await recorder.write_trade(trade)
        
        logger.info(f"✅ Worker {worker_id} 完成 {num_trades} 条写入")
    
    # 启动10个并发工作者
    start = datetime.now()
    tasks = [write_worker(i, 10) for i in range(10)]
    await asyncio.gather(*tasks)
    duration_ms = (datetime.now() - start).total_seconds() * 1000
    
    logger.info(f"✅ 并发写入完成，总耗时: {duration_ms:.2f}ms")
    
    # 获取统计
    stats = await recorder.get_stats()
    logger.info(f"\n📊 并发写入统计:")
    logger.info(f"   总写入: {stats['total_writes']} 条")
    logger.info(f"   总flush次数: {stats['total_flushes']}")
    logger.info(f"   平均flush时间: {stats['avg_flush_duration_ms']:.2f} ms")
    
    await recorder.close()


async def main():
    """运行所有演示"""
    logger.info("\n" + "🚀" * 40)
    logger.info("OptimizedTradeRecorder 功能演示")
    logger.info("🚀" * 40 + "\n")
    
    # 演示1: 单条写入
    await demo_single_writes()
    
    # 演示2: 批量写入
    await demo_batch_writes()
    
    # 演示3: 文件轮转
    await demo_file_rotation()
    
    # 演示4: 并发写入
    await demo_concurrent_writes()
    
    logger.info("\n" + "✅" * 40)
    logger.info("所有演示完成！")
    logger.info("✅" * 40 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
