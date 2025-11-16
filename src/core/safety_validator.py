"""
🛡️ v3.23+ 安全验证器 - 多层次防护体系
防止数学运算错误、无效输入、边界条件异常

新增功能：
- 集成 ExceptionHandler 统一异常处理
- 关键方法添加重试机制
- 更详细的错误日志
"""

import math
from src.utils.logger_factory import get_logger
from typing import Optional, Union
from src.core.exception_handler import ExceptionHandler

logger = get_logger(__name__)


class ValidationError(Exception):
    """验证错误异常"""
    pass


class SafetyValidator:
    """安全验证器 - 防护数学运算错误"""
    
    MIN_LEVERAGE = 0.5
    MAX_LEVERAGE = 100.0
    MIN_MARGIN_THRESHOLD = 0.01
    
    @staticmethod
    @ExceptionHandler.log_exceptions
    def validate_leverage(leverage: float, symbol: str = "unknown") -> float:
        """
        槓桿值多層驗證
        
        Args:
            leverage: 槓桿倍數
            symbol: 交易對符號
            
        Returns:
            驗證後的槓桿值
            
        Raises:
            ValidationError: 槓桿值無效
        """
        if leverage is None:
            raise ValidationError(f"槓桿值不能為None: {symbol}")
            
        if math.isnan(leverage) or math.isinf(leverage):
            raise ValidationError(f"無效槓桿值(NaN/Inf): {leverage} - {symbol}")
            
        if leverage <= 0:
            raise ValidationError(f"槓桿值必須大於0: {leverage} - {symbol}")
            
        if leverage < SafetyValidator.MIN_LEVERAGE:
            logger.warning(f"⚠️ 槓桿值過低: {leverage}x < {SafetyValidator.MIN_LEVERAGE}x，調整為最小值 - {symbol}")
            return SafetyValidator.MIN_LEVERAGE
            
        if leverage > SafetyValidator.MAX_LEVERAGE:
            logger.warning(f"⚠️ 異常高槓桿: {leverage}x > {SafetyValidator.MAX_LEVERAGE}x - {symbol}")
            
        return float(leverage)
    
    @staticmethod
    @ExceptionHandler.log_exceptions
    def safe_division(
        numerator: float, 
        denominator: float, 
        context: str = "",
        default: float = 0.0
    ) -> float:
        """
        安全的除法運算
        
        Args:
            numerator: 分子
            denominator: 分母
            context: 上下文描述（用於日誌）
            default: 除零時的默認返回值
            
        Returns:
            計算結果或默認值
        """
        if denominator == 0:
            logger.error(f"❌ 除零錯誤阻止: {context}")
            return default
            
        if abs(denominator) < 1e-10:
            logger.warning(f"⚠️ 除數過小: {denominator} - {context}")
            return default
            
        result = numerator / denominator
        
        if math.isnan(result) or math.isinf(result):
            logger.error(f"❌ 計算結果異常(NaN/Inf): {numerator}/{denominator} - {context}")
            return default
            
        return result
    
    @staticmethod
    @ExceptionHandler.log_exceptions
    def validate_total_score(total_score: float, num_signals: int = 0) -> float:
        """
        驗證總分數
        
        Args:
            total_score: 總分數
            num_signals: 信號數量
            
        Returns:
            驗證後的總分數
            
        Raises:
            ValidationError: 總分數為0或異常
        """
        if total_score is None or math.isnan(total_score) or math.isinf(total_score):
            raise ValidationError(f"總分數異常: {total_score}，信號數量: {num_signals}")
            
        if total_score == 0:
            raise ValidationError(
                f"致命錯誤：總分數為0，這不應該發生\n"
                f"   信號數量: {num_signals}\n"
                f"   所有信號的質量分數可能都為0"
            )
            
        if total_score < 0:
            raise ValidationError(f"總分數不能為負數: {total_score}")
            
        return total_score
    
    @staticmethod
    def validate_budget(budget: float, context: str = "") -> float:
        """
        驗證預算值
        
        Args:
            budget: 預算金額
            context: 上下文描述
            
        Returns:
            驗證後的預算
            
        Raises:
            ValidationError: 預算無效
        """
        if budget is None or math.isnan(budget) or math.isinf(budget):
            raise ValidationError(f"預算異常: {budget} - {context}")
            
        if budget < 0:
            logger.warning(f"⚠️ 預算為負數，調整為0: {budget} - {context}")
            return 0.0
            
        return budget
    
    @staticmethod
    def validate_pnl_percentage(
        pnl: float, 
        margin: float, 
        symbol: str = "unknown"
    ) -> float:
        """
        安全計算PnL百分比，防止margin過小導致結果爆炸
        
        Args:
            pnl: 盈虧金額
            margin: 保證金
            symbol: 交易對符號
            
        Returns:
            PnL百分比（限制在合理範圍內）
        """
        if margin < SafetyValidator.MIN_MARGIN_THRESHOLD:
            logger.warning(
                f"⚠️ 保證金過小: ${margin:.4f} < ${SafetyValidator.MIN_MARGIN_THRESHOLD} - {symbol}，"
                f"PnL%可能異常"
            )
            return 0.0
            
        pnl_pct = SafetyValidator.safe_division(
            pnl, 
            margin, 
            context=f"PnL% calculation for {symbol}"
        )
        
        pnl_pct = max(-10.0, min(10.0, pnl_pct))
        
        return pnl_pct
    
    @staticmethod
    def validate_positive_value(
        value: Union[int, float], 
        name: str, 
        min_value: float = 0.0,
        allow_zero: bool = False
    ) -> Union[int, float]:
        """
        驗證正數值
        
        Args:
            value: 要驗證的值
            name: 參數名稱
            min_value: 最小允許值
            allow_zero: 是否允許0
            
        Returns:
            驗證後的值
            
        Raises:
            ValidationError: 值無效
        """
        if value is None or math.isnan(float(value)) or math.isinf(float(value)):
            raise ValidationError(f"{name} 異常: {value}")
            
        if not allow_zero and value == 0:
            raise ValidationError(f"{name} 不能為0")
            
        if value < min_value:
            raise ValidationError(f"{name} 必須 >= {min_value}，當前值: {value}")
            
        return value
    
    @staticmethod
    def validate_ratio(
        value: float, 
        name: str, 
        min_val: float = 0.0, 
        max_val: float = 1.0,
        auto_clamp: bool = True
    ) -> float:
        """
        驗證比率配置值
        
        Args:
            value: 比率值
            name: 配置名稱
            min_val: 最小值
            max_val: 最大值
            auto_clamp: 是否自動調整到範圍內
            
        Returns:
            驗證後的比率值
            
        Raises:
            ValidationError: 值無效且auto_clamp=False時
        """
        if value is None or math.isnan(value) or math.isinf(value):
            raise ValidationError(f"{name} 異常: {value}")
            
        if not (min_val <= value <= max_val):
            if auto_clamp:
                clamped = max(min_val, min(value, max_val))
                logger.warning(
                    f"⚠️ 配置 {name} 超出範圍 [{min_val}, {max_val}]，"
                    f"已調整: {value} → {clamped}"
                )
                return clamped
            else:
                raise ValidationError(
                    f"{name} 超出範圍 [{min_val}, {max_val}]: {value}"
                )
                
        return value
