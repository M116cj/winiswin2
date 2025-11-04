"""
🛡️ v3.23+ 保證金安全控制器
實現多級保證金保護機制：80%警告、90%緊急、95%鎖定

新增功能：
- 集成 ExceptionHandler 統一異常處理
- 關鍵方法添加安全執行保護
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass
from src.core.exception_handler import ExceptionHandler

logger = logging.getLogger(__name__)


@dataclass
class MarginHealthStatus:
    """保證金健康狀態"""
    status: str
    action: str
    usage_ratio: float
    current_margin: float
    max_margin: float
    message: str
    budget_multiplier: float = 1.0


class MarginSafetyController:
    """保證金安全控制器"""
    
    STATUS_HEALTHY = "HEALTHY"
    STATUS_WARNING = "WARNING"
    STATUS_CRITICAL = "CRITICAL"
    STATUS_LOCKED = "LOCKED"
    
    ACTION_NORMAL = "NORMAL"
    ACTION_REDUCE_50_PERCENT = "REDUCE_50_PERCENT"
    ACTION_REDUCE_90_PERCENT = "REDUCE_90_PERCENT"
    ACTION_REJECT_ALL = "REJECT_ALL"
    
    def __init__(
        self,
        warning_threshold: float = 0.80,
        critical_threshold: float = 0.90,
        lock_threshold: float = 0.95
    ):
        """
        初始化保證金安全控制器
        
        Args:
            warning_threshold: 警告閾值（默認80%）
            critical_threshold: 緊急閾值（默認90%）
            lock_threshold: 鎖定閾值（默認95%）
        """
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.lock_threshold = lock_threshold
        
        logger.info(
            f"✅ 保證金安全控制器已啟用\n"
            f"   警告閾值: {warning_threshold:.0%}\n"
            f"   緊急閾值: {critical_threshold:.0%}\n"
            f"   鎖定閾值: {lock_threshold:.0%}"
        )
    
    @ExceptionHandler.log_exceptions
    def check_margin_health(
        self, 
        current_margin: float, 
        max_margin: float
    ) -> MarginHealthStatus:
        """
        檢查保證金健康狀態
        
        Args:
            current_margin: 當前已使用保證金
            max_margin: 最大允許保證金
            
        Returns:
            保證金健康狀態
        """
        if max_margin <= 0:
            logger.error("❌ 最大保證金為0或負數，拒絕所有新倉位")
            return MarginHealthStatus(
                status=self.STATUS_LOCKED,
                action=self.ACTION_REJECT_ALL,
                usage_ratio=1.0,
                current_margin=current_margin,
                max_margin=max_margin,
                message="最大保證金異常，停止所有新開倉",
                budget_multiplier=0.0
            )
        
        usage_ratio = current_margin / max_margin
        
        if usage_ratio >= self.lock_threshold:
            return MarginHealthStatus(
                status=self.STATUS_LOCKED,
                action=self.ACTION_REJECT_ALL,
                usage_ratio=usage_ratio,
                current_margin=current_margin,
                max_margin=max_margin,
                message=(
                    f"保證金使用率超過{self.lock_threshold:.0%}，"
                    f"停止所有新開倉"
                ),
                budget_multiplier=0.0
            )
        
        elif usage_ratio >= self.critical_threshold:
            return MarginHealthStatus(
                status=self.STATUS_CRITICAL,
                action=self.ACTION_REDUCE_90_PERCENT,
                usage_ratio=usage_ratio,
                current_margin=current_margin,
                max_margin=max_margin,
                message=(
                    f"保證金使用率超過{self.critical_threshold:.0%}，"
                    f"新開倉預算減少90%"
                ),
                budget_multiplier=0.1
            )
        
        elif usage_ratio >= self.warning_threshold:
            return MarginHealthStatus(
                status=self.STATUS_WARNING,
                action=self.ACTION_REDUCE_50_PERCENT,
                usage_ratio=usage_ratio,
                current_margin=current_margin,
                max_margin=max_margin,
                message=(
                    f"保證金使用率超過{self.warning_threshold:.0%}，"
                    f"新開倉預算減少50%"
                ),
                budget_multiplier=0.5
            )
        
        else:
            return MarginHealthStatus(
                status=self.STATUS_HEALTHY,
                action=self.ACTION_NORMAL,
                usage_ratio=usage_ratio,
                current_margin=current_margin,
                max_margin=max_margin,
                message="保證金使用率正常",
                budget_multiplier=1.0
            )
    
    def apply_budget_protection(
        self, 
        total_budget: float, 
        margin_health: MarginHealthStatus
    ) -> float:
        """
        應用預算保護機制
        
        Args:
            total_budget: 原始總預算
            margin_health: 保證金健康狀態
            
        Returns:
            調整後的預算
        """
        if margin_health.status == self.STATUS_LOCKED:
            logger.warning(
                f"🚨 保證金鎖定 | "
                f"使用率: {margin_health.usage_ratio:.1%} >= {self.lock_threshold:.0%} | "
                f"已使用: ${margin_health.current_margin:.2f} / "
                f"上限: ${margin_health.max_margin:.2f} | "
                f"拒絕所有新倉位"
            )
            return 0.0
        
        elif margin_health.status == self.STATUS_CRITICAL:
            adjusted_budget = total_budget * margin_health.budget_multiplier
            logger.warning(
                f"🔴 保證金緊急狀態 | "
                f"使用率: {margin_health.usage_ratio:.1%} >= {self.critical_threshold:.0%} | "
                f"已使用: ${margin_health.current_margin:.2f} / "
                f"上限: ${margin_health.max_margin:.2f} | "
                f"預算削減90%: ${total_budget:.2f} → ${adjusted_budget:.2f}"
            )
            return adjusted_budget
        
        elif margin_health.status == self.STATUS_WARNING:
            adjusted_budget = total_budget * margin_health.budget_multiplier
            logger.warning(
                f"🟡 保證金警告 | "
                f"使用率: {margin_health.usage_ratio:.1%} >= {self.warning_threshold:.0%} | "
                f"已使用: ${margin_health.current_margin:.2f} / "
                f"上限: ${margin_health.max_margin:.2f} | "
                f"預算削減50%: ${total_budget:.2f} → ${adjusted_budget:.2f}"
            )
            return adjusted_budget
        
        else:
            logger.debug(
                f"✅ 保證金健康 | "
                f"使用率: {margin_health.usage_ratio:.1%} | "
                f"已使用: ${margin_health.current_margin:.2f} / "
                f"上限: ${margin_health.max_margin:.2f}"
            )
            return total_budget
    
    def get_remaining_margin_space(
        self, 
        current_margin: float, 
        max_margin: float
    ) -> float:
        """
        獲取剩餘保證金空間
        
        Args:
            current_margin: 當前已使用保證金
            max_margin: 最大允許保證金
            
        Returns:
            剩餘保證金空間
        """
        remaining = max(0, max_margin - current_margin)
        
        if remaining == 0:
            logger.warning(
                f"⚠️ 保證金已滿 | "
                f"已使用: ${current_margin:.2f} >= "
                f"上限: ${max_margin:.2f}"
            )
        
        return remaining
    
    def format_margin_report(self, margin_health: MarginHealthStatus) -> str:
        """
        格式化保證金報告
        
        Args:
            margin_health: 保證金健康狀態
            
        Returns:
            格式化的報告字符串
        """
        status_emoji = {
            self.STATUS_HEALTHY: "✅",
            self.STATUS_WARNING: "🟡",
            self.STATUS_CRITICAL: "🔴",
            self.STATUS_LOCKED: "🚨"
        }
        
        emoji = status_emoji.get(margin_health.status, "❓")
        
        return (
            f"{emoji} 保證金狀態報告\n"
            f"   狀態: {margin_health.status}\n"
            f"   使用率: {margin_health.usage_ratio:.1%}\n"
            f"   已使用: ${margin_health.current_margin:.2f}\n"
            f"   上限: ${margin_health.max_margin:.2f}\n"
            f"   剩餘: ${margin_health.max_margin - margin_health.current_margin:.2f}\n"
            f"   行動: {margin_health.action}\n"
            f"   預算乘數: {margin_health.budget_multiplier:.0%}\n"
            f"   信息: {margin_health.message}"
        )
