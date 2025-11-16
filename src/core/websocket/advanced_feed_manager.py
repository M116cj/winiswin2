"""
高级WebSocket管理器
整合数据质量监控、缺口处理和优化的连接管理
"""

import asyncio
from src.utils.logger_factory import get_logger
from typing import Set, Callable, Dict, List, Optional
from datetime import datetime, timedelta

from .data_quality_monitor import DataQualityMonitor
from .data_gap_handler import DataGapHandler

logger = get_logger(__name__)

class AdvancedWebSocketManager:
    """
    高级WebSocket管理器
    
    功能：
    - 数据质量实时监控
    - 数据缺口自动检测和修复
    - 优化的批次管理
    - 健康检查和统计报告
    """
    
    def __init__(self, config, binance_client=None):
        """
        初始化高级WebSocket管理器
        
        Args:
            config: 配置对象
            binance_client: Binance客户端（可选，用于缺口修复）
        """
        self.config = config
        self.binance_client = binance_client
        self.feeds = {}
        self.data_buffers = {}
        
        # 初始化监控组件
        self.quality_monitor = DataQualityMonitor()
        self.gap_handler = DataGapHandler(binance_client)
        
        # Railway优化配置（v3.20.7 增加ping_timeout容忍网络延迟）
        self.ws_config = {
            'max_symbols_per_connection': 150,
            'ping_interval': 15,
            'ping_timeout': 60,
            'reconnect_base_delay': 1,
            'max_reconnect_delay': 30,
            'connection_timeout': 180,
            'health_check_interval': 30,
            'heartbeat_interval': 180,
        }
        
        # 统计信息
        self.stats = {
            'total_messages': 0,
            'successful_reconnects': 0,
            'data_gaps_fixed': 0,
            'quality_issues': 0,
            'start_time': datetime.now()
        }
        
        # 监控任务
        self._monitoring_task = None
        self._is_monitoring = False

    def initialize_data_buffers(self, all_symbols: Set[str]):
        """
        初始化数据缓冲区
        
        Args:
            all_symbols: 所有交易对集合
        """
        try:
            logger.info(f"📦 初始化数据缓冲区: {len(all_symbols)}个交易对")
            
            for symbol in all_symbols:
                self.data_buffers[symbol] = {
                    'kline_1m': [],
                    'kline_5m': [],
                    'kline_15m': [],
                    'kline_1h': [],
                    'last_update': None,
                    'message_count': 0,
                    'last_price': None
                }
            
            logger.info(f"✅ 数据缓冲区初始化完成: {len(self.data_buffers)}个")
            
        except Exception as e:
            logger.error(f"❌ 数据缓冲区初始化失败: {e}")
            raise

    def create_wrapped_callback(self, original_callback: Callable) -> Callable:
        """
        创建包装的回调函数，整合数据处理逻辑
        
        Args:
            original_callback: 原始回调函数
            
        Returns:
            Callable: 包装后的回调函数
        """
        async def wrapped_callback(data: Dict):
            try:
                # 1. 数据质量检查
                if not self.quality_monitor.validate_message(data):
                    self.stats['quality_issues'] += 1
                    logger.debug("⚠️ 消息未通过质量检查，已拒绝")
                    return
                
                # 2. 提取交易对
                symbol = self._extract_symbol(data)
                if not symbol:
                    logger.debug("⚠️ 无法从消息中提取交易对")
                    return
                
                # 3. 更新数据缓冲区
                await self._update_data_buffers(symbol, data)
                
                # 4. 连续性检查
                self.quality_monitor.check_continuity(symbol, data)
                
                # 5. 调用原始回调
                await original_callback(data)
                
                # 6. 更新统计
                self.stats['total_messages'] += 1
                
            except Exception as e:
                logger.error(f"❌ 回调处理失败: {e}")
                import traceback
                logger.error(f"详细错误: {traceback.format_exc()}")
                
        return wrapped_callback

    async def _update_data_buffers(self, symbol: str, data: Dict):
        """
        更新数据缓冲区
        
        Args:
            symbol: 交易对
            data: WebSocket消息数据
        """
        try:
            if symbol not in self.data_buffers:
                # 动态添加新交易对缓冲区
                self.data_buffers[symbol] = {
                    'kline_1m': [],
                    'kline_5m': [],
                    'kline_15m': [],
                    'kline_1h': [],
                    'last_update': None,
                    'message_count': 0,
                    'last_price': None
                }
                logger.debug(f"📦 为 {symbol} 创建新的数据缓冲区")
                
            buffer = self.data_buffers[symbol]
            buffer['last_update'] = datetime.now()
            buffer['message_count'] += 1
            
            # 根据数据类型存储到相应缓冲区
            stream_type = data.get('stream', '')
            
            if 'kline_1m' in stream_type:
                self._add_to_kline_buffer(buffer['kline_1m'], data)
            elif 'kline_5m' in stream_type:
                self._add_to_kline_buffer(buffer['kline_5m'], data)
            elif 'kline_15m' in stream_type:
                self._add_to_kline_buffer(buffer['kline_15m'], data)
            elif 'kline_1h' in stream_type:
                self._add_to_kline_buffer(buffer['kline_1h'], data)
            elif 'bookTicker' in stream_type or 'ticker' in stream_type:
                # 价格数据
                price_data = data.get('data', {})
                buffer['last_price'] = float(price_data.get('c', 0) or price_data.get('p', 0))
                
            # 限制缓冲区大小
            self._trim_buffers(buffer)
            
        except Exception as e:
            logger.error(f"❌ 更新数据缓冲区失败 {symbol}: {e}")

    def _add_to_kline_buffer(self, buffer: List, data: Dict):
        """
        添加数据到K线缓冲区
        
        Args:
            buffer: K线缓冲区列表
            data: WebSocket消息数据
        """
        try:
            kline_data = data.get('data', {})
            kline = kline_data.get('k', {})
            
            if not kline:
                return
                
            kline_entry = {
                'timestamp': kline_data.get('t') or kline.get('t'),
                'open': float(kline.get('o', 0)),
                'high': float(kline.get('h', 0)),
                'low': float(kline.get('l', 0)),
                'close': float(kline.get('c', 0)),
                'volume': float(kline.get('v', 0)),
                'is_final': kline.get('x', False)
            }
            
            # 只保留最终K线（避免重复）
            if kline_entry['is_final']:
                buffer.append(kline_entry)
            
        except Exception as e:
            logger.error(f"❌ 添加K线数据失败: {e}")

    async def start_monitoring_tasks(self):
        """启动监控任务"""
        if self._is_monitoring:
            logger.warning("⚠️ 监控任务已在运行")
            return
            
        try:
            self._is_monitoring = True
            logger.info("🔍 启动高级WebSocket监控任务")
            
            while self._is_monitoring:
                # 1. 数据质量报告
                await self._log_quality_report()
                
                # 2. 检查数据缺口
                await self._check_data_gaps()
                
                # 3. 统计报告
                await self._log_statistics_report()
                
                # 每分钟检查一次
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            logger.info("🛑 监控任务已取消")
        except Exception as e:
            logger.error(f"❌ 监控任务失败: {e}")
        finally:
            self._is_monitoring = False

    async def _log_quality_report(self):
        """记录质量报告"""
        try:
            quality_report = self.quality_monitor.get_quality_report()
            
            logger.info(
                f"📈 数据质量报告: "
                f"验证={quality_report['total_validated']}, "
                f"拒绝={quality_report['total_rejected']}, "
                f"接受率={quality_report['acceptance_rate']:.1f}%, "
                f"缺口={quality_report['message_gaps']}, "
                f"乱序={quality_report['out_of_order']}, "
                f"无效价格={quality_report['invalid_prices']}"
            )
            
        except Exception as e:
            logger.error(f"❌ 质量报告失败: {e}")

    async def _check_data_gaps(self):
        """检查数据缺口"""
        try:
            current_time = datetime.now()
            gaps_found = 0
            
            for symbol, buffer in self.data_buffers.items():
                if not buffer['last_update']:
                    continue
                    
                time_since_update = (current_time - buffer['last_update']).total_seconds()
                
                # 超过2分钟无数据更新
                if time_since_update > 120:
                    gaps_found += 1
                    logger.warning(
                        f"⚠️ {symbol} 数据缺口: {time_since_update:.1f}秒无更新"
                    )
                    await self.gap_handler.handle_gap(symbol, buffer)
                    self.stats['data_gaps_fixed'] += 1
            
            if gaps_found > 0:
                logger.warning(f"⚠️ 本次检查发现 {gaps_found} 个数据缺口")
                    
        except Exception as e:
            logger.error(f"❌ 数据缺口检查失败: {e}")

    async def _log_statistics_report(self):
        """记录统计报告"""
        try:
            active_symbols = sum(
                1 for buf in self.data_buffers.values()
                if buf['last_update'] and
                (datetime.now() - buf['last_update']).total_seconds() < 300
            )
            
            uptime = (datetime.now() - self.stats['start_time']).total_seconds()
            uptime_hours = uptime / 3600
            
            gap_stats = self.gap_handler.get_gap_statistics()
            
            logger.info(
                f"📊 WebSocket统计报告: "
                f"运行时间={uptime_hours:.1f}h, "
                f"总消息={self.stats['total_messages']}, "
                f"活跃交易对={active_symbols}/{len(self.data_buffers)}, "
                f"重连成功={self.stats['successful_reconnects']}, "
                f"缺口修复={gap_stats['total_gaps_fixed']}/{gap_stats['total_gaps_detected']}, "
                f"质量问题={self.stats['quality_issues']}"
            )
            
        except Exception as e:
            logger.error(f"❌ 统计报告失败: {e}")

    def _extract_symbol(self, data: Dict) -> Optional[str]:
        """
        从数据中提取交易对
        
        Args:
            data: WebSocket消息数据
            
        Returns:
            Optional[str]: 交易对（大写）
        """
        try:
            stream = data.get('stream', '')
            if not stream:
                # 尝试从data中获取
                symbol = data.get('data', {}).get('s')
                if symbol:
                    return symbol.upper()
                return None
                
            # 格式: btcusdt@kline_1m
            symbol = stream.split('@')[0]
            return symbol.upper()
        except Exception as e:
            logger.debug(f"⚠️ 提取交易对失败: {e}")
            return None

    def _trim_buffers(self, buffer: Dict):
        """
        修剪缓冲区大小
        
        Args:
            buffer: 数据缓冲区
        """
        max_kline_size = 1000  # 保留最近1000条K线
        
        for key in ['kline_1m', 'kline_5m', 'kline_15m', 'kline_1h']:
            if len(buffer[key]) > max_kline_size:
                buffer[key] = buffer[key][-max_kline_size:]

    def get_symbol_data(self, symbol: str, timeframe: str = '1m') -> List:
        """
        获取指定交易对和时间框架的数据
        
        Args:
            symbol: 交易对
            timeframe: 时间框架 ('1m', '5m', '15m', '1h')
            
        Returns:
            List: K线数据列表
        """
        try:
            if symbol not in self.data_buffers:
                logger.debug(f"⚠️ {symbol} 不在数据缓冲区中")
                return []
                
            buffer_key = f'kline_{timeframe}'
            return self.data_buffers[symbol].get(buffer_key, [])
            
        except Exception as e:
            logger.error(f"❌ 获取交易对数据失败 {symbol}: {e}")
            return []
    
    def get_buffer_status(self) -> Dict:
        """
        获取缓冲区状态
        
        Returns:
            Dict: 缓冲区状态统计
        """
        try:
            current_time = datetime.now()
            
            status = {
                'total_symbols': len(self.data_buffers),
                'active_symbols': 0,
                'inactive_symbols': 0,
                'symbols_with_data': 0,
                'total_klines': 0
            }
            
            for symbol, buffer in self.data_buffers.items():
                # 统计活跃交易对（5分钟内有更新）
                if buffer['last_update']:
                    time_since_update = (current_time - buffer['last_update']).total_seconds()
                    if time_since_update < 300:
                        status['active_symbols'] += 1
                    else:
                        status['inactive_symbols'] += 1
                else:
                    status['inactive_symbols'] += 1
                
                # 统计有数据的交易对
                has_data = any(
                    len(buffer[key]) > 0
                    for key in ['kline_1m', 'kline_5m', 'kline_15m', 'kline_1h']
                )
                if has_data:
                    status['symbols_with_data'] += 1
                
                # 统计总K线数
                status['total_klines'] += sum(
                    len(buffer[key])
                    for key in ['kline_1m', 'kline_5m', 'kline_15m', 'kline_1h']
                )
            
            return status
            
        except Exception as e:
            logger.error(f"❌ 获取缓冲区状态失败: {e}")
            return {}
    
    def stop_monitoring(self):
        """停止监控任务"""
        self._is_monitoring = False
        logger.info("🛑 正在停止监控任务...")
    
    def get_comprehensive_report(self) -> Dict:
        """
        获取综合报告
        
        Returns:
            Dict: 包含所有统计信息的综合报告
        """
        return {
            'quality': self.quality_monitor.get_quality_report(),
            'gaps': self.gap_handler.get_gap_statistics(),
            'buffer_status': self.get_buffer_status(),
            'general_stats': self.stats
        }
