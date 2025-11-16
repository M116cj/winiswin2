"""
数据质量监控器
监控WebSocket消息的有效性、价格合理性和数据连续性
"""

from src.utils.logger_factory import get_logger
from typing import Dict, Optional
from datetime import datetime

logger = get_logger(__name__)

class DataQualityMonitor:
    """数据质量监控器 - 实时验证WebSocket消息质量"""
    
    def __init__(self):
        self.metrics = {
            'message_gaps': 0,
            'out_of_order': 0,
            'invalid_prices': 0,
            'missing_fields': 0,
            'total_validated': 0,
            'total_rejected': 0
        }
        self.last_timestamps = {}
        
    def validate_message(self, data: Dict) -> bool:
        """
        验证消息有效性
        
        Args:
            data: WebSocket消息数据
            
        Returns:
            bool: 消息是否有效
        """
        try:
            self.metrics['total_validated'] += 1
            
            # 检查必要字段
            required_fields = ['stream', 'data']
            if not all(field in data for field in required_fields):
                self.metrics['missing_fields'] += 1
                self.metrics['total_rejected'] += 1
                logger.debug(f"⚠️ 消息缺少必要字段: {data.keys()}")
                return False
            
            kline_data = data.get('data', {})
            
            # 如果是K线流，检查K线数据
            if 'kline' in data.get('stream', ''):
                kline = kline_data.get('k', {})
                
                if not kline:
                    self.metrics['missing_fields'] += 1
                    self.metrics['total_rejected'] += 1
                    logger.debug(f"⚠️ K线流缺少K线数据")
                    return False
            else:
                # 非K线数据（价格、账户等），只验证基本字段即可
                return True
            
            kline = kline_data.get('k', {})
            
            # 检查K线字段
            kline_fields = ['t', 'o', 'h', 'l', 'c', 'v', 'x']
            if not all(field in kline for field in kline_fields):
                self.metrics['missing_fields'] += 1
                self.metrics['total_rejected'] += 1
                logger.debug(f"⚠️ K线数据缺少字段: {kline.keys()}")
                return False
            
            # 检查价格合理性
            if not self._validate_prices(kline):
                self.metrics['invalid_prices'] += 1
                self.metrics['total_rejected'] += 1
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 消息验证失败: {e}")
            self.metrics['total_rejected'] += 1
            return False

    def _validate_prices(self, kline: Dict) -> bool:
        """
        验证价格合理性
        
        Args:
            kline: K线数据
            
        Returns:
            bool: 价格是否合理
        """
        try:
            open_price = float(kline.get('o', 0))
            high_price = float(kline.get('h', 0))
            low_price = float(kline.get('l', 0))
            close_price = float(kline.get('c', 0))
            
            # 检查价格是否为正数
            if any(price <= 0 for price in [open_price, high_price, low_price, close_price]):
                logger.debug(f"⚠️ 检测到非正数价格: O={open_price}, H={high_price}, L={low_price}, C={close_price}")
                return False
            
            # 检查价格关系：low <= open/close <= high
            if not (low_price <= open_price <= high_price):
                logger.debug(f"⚠️ 开盘价异常: L={low_price}, O={open_price}, H={high_price}")
                return False
            if not (low_price <= close_price <= high_price):
                logger.debug(f"⚠️ 收盘价异常: L={low_price}, C={close_price}, H={high_price}")
                return False
            if high_price < low_price:
                logger.debug(f"⚠️ 高低价反转: H={high_price}, L={low_price}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 价格验证失败: {e}")
            return False

    def check_continuity(self, symbol: str, data: Dict):
        """
        检查数据连续性（时间戳顺序）
        
        Args:
            symbol: 交易对
            data: WebSocket消息数据
        """
        try:
            kline_data = data.get('data', {})
            
            # 优先从K线数据中获取时间戳 data['k']['t']
            kline = kline_data.get('k', {})
            current_timestamp = kline.get('t')
            
            # 如果K线中没有，尝试从data层获取
            if not current_timestamp:
                current_timestamp = kline_data.get('t')
            
            if not current_timestamp:
                return
                
            # 检查时间戳顺序
            if symbol in self.last_timestamps:
                last_timestamp = self.last_timestamps[symbol]
                if current_timestamp <= last_timestamp:
                    self.metrics['out_of_order'] += 1
                    logger.warning(
                        f"⚠️ {symbol} 时间戳乱序: "
                        f"当前={current_timestamp}, 上次={last_timestamp}"
                    )
                elif current_timestamp - last_timestamp > 60000:  # 超过1分钟
                    gap_seconds = (current_timestamp - last_timestamp) / 1000
                    self.metrics['message_gaps'] += 1
                    logger.warning(
                        f"⚠️ {symbol} 检测到消息缺口: {gap_seconds:.1f}秒"
                    )
            
            self.last_timestamps[symbol] = current_timestamp
            
        except Exception as e:
            logger.error(f"❌ 连续性检查失败 {symbol}: {e}")
    
    def get_quality_report(self) -> Dict:
        """
        获取质量报告
        
        Returns:
            Dict: 质量指标统计
        """
        total = self.metrics['total_validated']
        if total == 0:
            acceptance_rate = 0
        else:
            acceptance_rate = ((total - self.metrics['total_rejected']) / total) * 100
        
        return {
            'total_validated': total,
            'total_rejected': self.metrics['total_rejected'],
            'acceptance_rate': acceptance_rate,
            'message_gaps': self.metrics['message_gaps'],
            'out_of_order': self.metrics['out_of_order'],
            'invalid_prices': self.metrics['invalid_prices'],
            'missing_fields': self.metrics['missing_fields'],
            'monitored_symbols': len(self.last_timestamps)
        }
    
    def reset_metrics(self):
        """重置统计指标"""
        self.metrics = {
            'message_gaps': 0,
            'out_of_order': 0,
            'invalid_prices': 0,
            'missing_fields': 0,
            'total_validated': 0,
            'total_rejected': 0
        }
        logger.info("📊 数据质量指标已重置")
