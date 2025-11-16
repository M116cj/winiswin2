"""
订单验证器 - Binance API -4164 名义价值错误修复
职责：验证订单名义价值、自动调整数量、确保符合Binance要求
Created: 2025-11-11 v4.2.1
"""

from src.utils.logger_factory import get_logger
import time
from typing import Dict, Optional, Tuple, Any
from decimal import Decimal, ROUND_DOWN
import math

logger = get_logger(__name__)

class OrderValidator:
    """
    订单验证器 - 确保所有订单满足Binance最小名义价值要求
    
    Binance要求：
    - 所有合约订单的名义价值（quantity × price）必须 >= 5 USDT
    - 错误代码 -4164: "Order's notional must be no smaller than 5.0 (unless you choose reduce only)"
    """
    
    def __init__(self):
        self.MIN_NOTIONAL = 5.0  # Binance 最小名义价值（USDT）
        self.SAFETY_MARGIN = 1.02  # 安全边际：额外增加2%以确保通过
        logger.info(f"✅ OrderValidator 初始化完成 (最小名义价值: {self.MIN_NOTIONAL} USDT)")
    
    def validate_order(
        self,
        symbol: str,
        quantity: float,
        price: float,
        order_side: str,
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        严格验证订单参数
        
        Args:
            symbol: 交易对符号
            quantity: 订单数量
            price: 订单价格
            order_side: 订单方向 (BUY/SELL)
            reduce_only: 是否仅减仓（减仓订单豁免名义价值检查）
        
        Returns:
            {
                'valid': bool,              # 是否有效
                'adjusted_quantity': float,  # 调整后的数量
                'notional_value': float,    # 名义价值
                'reason': str               # 原因/说明
            }
        """
        # 计算名义价值
        notional_value = quantity * price
        
        # 减仓订单豁免检查
        if reduce_only:
            return {
                'valid': True,
                'adjusted_quantity': quantity,
                'notional_value': notional_value,
                'reason': 'Reduce-only order (豁免名义价值检查)'
            }
        
        # 检查名义价值是否满足要求
        if notional_value < self.MIN_NOTIONAL:
            # 计算满足最小名义价值所需的数量（含安全边际）
            min_quantity = (self.MIN_NOTIONAL * self.SAFETY_MARGIN) / price
            
            logger.warning(
                f"⚠️ 名义价值不足: {symbol} {order_side} | "
                f"数量: {quantity} × 价格: {price} = {notional_value:.4f} USDT < {self.MIN_NOTIONAL} USDT"
            )
            
            return {
                'valid': False,
                'adjusted_quantity': min_quantity,
                'notional_value': notional_value,
                'reason': (
                    f'名义价值 {notional_value:.4f} USDT < 最小要求 {self.MIN_NOTIONAL} USDT '
                    f'(需要数量: {min_quantity:.6f})'
                )
            }
        
        # 订单有效
        return {
            'valid': True,
            'adjusted_quantity': quantity,
            'notional_value': notional_value,
            'reason': f'名义价值 {notional_value:.4f} USDT ✅'
        }
    
    def calculate_min_quantity(self, price: float) -> float:
        """
        计算满足最小名义价值的最小数量
        
        Args:
            price: 订单价格
        
        Returns:
            最小有效数量（含安全边际）
        """
        if price <= 0:
            raise ValueError(f"价格必须大于0: {price}")
        
        min_qty = (self.MIN_NOTIONAL * self.SAFETY_MARGIN) / price
        return min_qty
    
    def round_quantity(self, quantity: float, step_size: float) -> float:
        """
        根据交易对精度调整数量（向上取整以确保满足最小名义价值）
        
        Args:
            quantity: 原始数量
            step_size: 最小变动单位（LOT_SIZE stepSize）
        
        Returns:
            调整后的数量（向上取整到stepSize的倍数）
        """
        if step_size == 0:
            return quantity
        
        # 使用Decimal避免浮点数精度问题
        qty_decimal = Decimal(str(quantity))
        step_decimal = Decimal(str(step_size))
        
        # 计算需要多少个step（向上取整）
        import math as _math
        steps_needed = _math.ceil(float(qty_decimal / step_decimal))
        rounded_decimal = step_decimal * Decimal(steps_needed)
        
        # 计算精度
        precision = int(round(-math.log(step_size, 10), 0))
        if precision < 0:
            precision = 0
        
        # 量化到正确精度（使用ROUND_DOWN确保不超出步长）
        quantize_str = '0.' + '0' * precision if precision > 0 else '1'
        rounded_decimal = rounded_decimal.quantize(Decimal(quantize_str), rounding=ROUND_DOWN)
        
        return float(rounded_decimal)


class SmartOrderManager:
    """
    智能订单管理器 - 自动调整订单以满足Binance要求
    
    功能：
    1. 自动验证名义价值
    2. 自动调整数量以满足最小要求
    3. 应用交易对精度规则
    4. 二次验证调整后的订单
    """
    
    def __init__(self, binance_client):
        self.validator = OrderValidator()
        self.binance_client = binance_client
        logger.info("✅ SmartOrderManager 初始化完成")
    
    async def prepare_order(
        self,
        symbol: str,
        quantity: float,
        price: float,
        side: str,
        reduce_only: bool = False
    ) -> Tuple[bool, float, str]:
        """
        准备订单 - 验证并调整以满足Binance要求
        
        Args:
            symbol: 交易对
            quantity: 原始数量
            price: 价格
            side: 方向 (BUY/SELL)
            reduce_only: 是否仅减仓
        
        Returns:
            (是否可执行, 最终数量, 状态信息)
        """
        # 第一步：验证订单
        validation = self.validator.validate_order(symbol, quantity, price, side, reduce_only)
        
        if not validation['valid']:
            logger.warning(f"📋 订单需要调整: {validation['reason']}")
            
            # 获取交易对信息
            symbol_info = await self.binance_client.get_symbol_info(symbol)
            if not symbol_info:
                error_msg = f"无法获取交易对信息: {symbol}"
                logger.error(f"❌ {error_msg}")
                return False, quantity, error_msg
            
            # 获取stepSize
            step_size = 1.0  # 默认值
            for f in symbol_info.get('filters', []):
                if f.get('filterType') == 'LOT_SIZE':
                    step_size = float(f.get('stepSize', 1.0))
                    break
            
            # 调整数量以符合精度
            adjusted_qty = self.validator.round_quantity(
                validation['adjusted_quantity'],
                step_size
            )
            
            # 二次验证调整后的订单
            final_validation = self.validator.validate_order(
                symbol, adjusted_qty, price, side, reduce_only
            )
            
            if not final_validation['valid']:
                error_msg = f"即使调整后仍不满足要求: {final_validation['reason']}"
                logger.error(f"❌ {error_msg}")
                return False, adjusted_qty, error_msg
            
            success_msg = (
                f"✅ 订单已调整: {quantity} → {adjusted_qty} | "
                f"名义价值: {final_validation['notional_value']:.4f} USDT"
            )
            logger.info(success_msg)
            return True, adjusted_qty, success_msg
        
        # 订单本身已满足要求
        logger.debug(f"✅ 订单有效: {symbol} {side} {quantity} @ {price} ({validation['notional_value']:.4f} USDT)")
        return True, quantity, validation['reason']


class NotionalMonitor:
    """
    名义价值监控器 - 实时监控和告警
    
    功能：
    1. 记录所有名义价值违规
    2. 统计违规频率
    3. 生成告警
    """
    
    def __init__(self):
        self.violations = []
        self.total_checks = 0
        self.violations_count = 0
        logger.info("✅ NotionalMonitor 初始化完成")
    
    async def check_and_log(
        self,
        symbol: str,
        quantity: float,
        price: float,
        side: str
    ):
        """
        检查并记录订单
        
        Args:
            symbol: 交易对
            quantity: 数量
            price: 价格
            side: 方向
        """
        self.total_checks += 1
        notional = quantity * price
        
        if notional < 5.0:
            self.violations_count += 1
            violation = {
                'symbol': symbol,
                'quantity': quantity,
                'price': price,
                'side': side,
                'notional': notional,
                'timestamp': time.time()
            }
            self.violations.append(violation)
            
            logger.warning(
                f"🚨 名义价值违规 #{self.violations_count}: "
                f"{symbol} {side} | "
                f"数量: {quantity} × 价格: {price} = {notional:.4f} USDT"
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_checks': self.total_checks,
            'violations_count': self.violations_count,
            'violation_rate': (
                self.violations_count / self.total_checks * 100
                if self.total_checks > 0 else 0
            )
        }
