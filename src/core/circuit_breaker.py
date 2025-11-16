"""
熔斷器（v3.9.2.8.4新增：分級熔斷+Bypass機制）
職責：分級失敗檢測、智能熔斷、優先級bypass、審計日誌
"""

import time
import logging
from src.utils.logger_factory import get_logger
from enum import Enum
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = get_logger(__name__)
bypass_logger = logging.getLogger(f"{__name__}.bypass")  # 專用bypass審計日誌

class CircuitState(Enum):
    """熔斷器狀態（保留向後兼容）"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitLevel(Enum):
    """分級熔斷級別"""
    NORMAL = "normal"        # 正常運行
    WARNING = "warning"      # 警告級（1-2次失敗）
    THROTTLED = "throttled"  # 限流級（3-4次失敗）
    BLOCKED = "blocked"      # 阻斷級（5+次失敗）

class Priority(Enum):
    """操作優先級"""
    LOW = 1        # 可選操作（市場掃描、統計）
    NORMAL = 2     # 普通操作（數據查詢、信號生成）
    HIGH = 3       # 重要操作（下單、設置止損止盈）
    CRITICAL = 4   # 關鍵操作（平倉、緊急止損、持倉查詢）

@dataclass
class BypassInfo:
    """Bypass使用記錄"""
    timestamp: float
    priority: Priority
    operation_type: str
    level: CircuitLevel
    reason: str

@dataclass
class TemporaryBypass:
    """臨時Bypass配置"""
    enabled: bool
    expire_time: float
    reason: str
    enabled_at: float

class GradedCircuitBreaker:
    """
    分級熔斷器（v3.9.2.8.4）
    
    功能：
    1. 三級熔斷：WARNING(1-2) / THROTTLED(3-4) / BLOCKED(5+)
    2. 優先級系統：LOW/NORMAL/HIGH/CRITICAL
    3. Bypass機制：基於優先級+操作白名單
    4. 審計日誌：記錄所有bypass和級別變化
    5. 自動衰減：成功後逐漸降低失敗計數
    """
    
    def __init__(
        self,
        warning_threshold: int = 2,
        throttled_threshold: int = 4,
        blocked_threshold: int = 5,
        timeout: int = 60,
        throttle_delay: float = 2.0,
        bypass_whitelist: Optional[list] = None,
        auto_decay: bool = True
    ):
        """
        初始化分級熔斷器
        
        Args:
            warning_threshold: 警告級閾值（1-2次失敗）
            throttled_threshold: 限流級閾值（3-4次失敗）
            blocked_threshold: 阻斷級閾值（5+次失敗）
            timeout: 熔斷超時時間（秒）
            throttle_delay: 限流延遲時間（秒）
            bypass_whitelist: 可bypass的操作類型列表
            auto_decay: 是否自動衰減失敗計數
        """
        self.warning_threshold = warning_threshold
        self.throttled_threshold = throttled_threshold
        self.blocked_threshold = blocked_threshold
        self.timeout = timeout
        self.throttle_delay = throttle_delay
        self.auto_decay = auto_decay
        
        # 狀態
        self.failure_count = 0
        self.last_failure_time: float = 0
        self.level = CircuitLevel.NORMAL
        
        # Bypass配置
        self.bypass_whitelist = set(bypass_whitelist or [
            "close_position",
            "emergency_stop_loss",
            "adjust_stop_loss",
            "adjust_take_profit",
            "get_positions",
            "cancel_order"
        ])
        
        # 臨時bypass
        self.temp_bypass: Optional[TemporaryBypass] = None
        
        # 統計
        self.total_requests = 0
        self.bypassed_requests = 0
        self.throttled_requests = 0
        self.blocked_requests = 0
        self.bypass_history: list[BypassInfo] = []
        self.level_history: list[tuple[float, CircuitLevel]] = [(time.time(), CircuitLevel.NORMAL)]
        
    def _update_level(self):
        """根據失敗計數更新級別"""
        old_level = self.level
        
        if self.failure_count >= self.blocked_threshold:
            self.level = CircuitLevel.BLOCKED
        elif self.failure_count >= self.throttled_threshold:
            self.level = CircuitLevel.THROTTLED
        elif self.failure_count >= 1:
            self.level = CircuitLevel.WARNING
        else:
            self.level = CircuitLevel.NORMAL
        
        # 記錄級別變化
        if old_level != self.level:
            self.level_history.append((time.time(), self.level))
            logger.warning(
                f"🔄 熔斷器級別變化: {old_level.value} → {self.level.value} "
                f"(失敗次數: {self.failure_count})"
            )
    
    def _check_timeout_recovery(self):
        """檢查超時恢復"""
        if self.level in [CircuitLevel.THROTTLED, CircuitLevel.BLOCKED]:
            if time.time() - self.last_failure_time >= self.timeout:
                logger.info(
                    f"✅ 熔斷器超時恢復: {self.level.value} → NORMAL "
                    f"(超時{self.timeout}秒)"
                )
                self.failure_count = 0
                self.level = CircuitLevel.NORMAL
                self.level_history.append((time.time(), CircuitLevel.NORMAL))
    
    def _check_temporary_bypass(self) -> bool:
        """檢查臨時bypass是否有效"""
        if not self.temp_bypass or not self.temp_bypass.enabled:
            return False
        
        if time.time() >= self.temp_bypass.expire_time:
            logger.info(f"⏰ 臨時bypass已過期: {self.temp_bypass.reason}")
            self.temp_bypass = None
            return False
        
        return True
    
    def _should_bypass(
        self,
        priority: Priority,
        operation_type: str
    ) -> Tuple[bool, str]:
        """
        判斷是否應該bypass熔斷
        
        Returns:
            (是否bypass, bypass原因)
        """
        # 1. 檢查臨時bypass
        if self._check_temporary_bypass() and self.temp_bypass is not None:
            return True, f"臨時bypass生效({self.temp_bypass.reason})"
        
        # 2. 根據級別和優先級判斷
        if self.level == CircuitLevel.NORMAL:
            return False, ""  # 正常級別無需bypass
        
        elif self.level == CircuitLevel.WARNING:
            return False, ""  # 警告級別全部通過（僅記錄）
        
        elif self.level == CircuitLevel.THROTTLED:
            # 限流級：HIGH/CRITICAL優先級可bypass
            if priority in [Priority.HIGH, Priority.CRITICAL]:
                return True, f"高優先級({priority.name})bypass限流"
            return False, ""
        
        elif self.level == CircuitLevel.BLOCKED:
            # 阻斷級：僅CRITICAL + 白名單可bypass
            if priority == Priority.CRITICAL and operation_type in self.bypass_whitelist:
                return True, f"關鍵操作({operation_type})bypass阻斷"
            return False, ""
        
        return False, ""
    
    def can_proceed(
        self,
        priority: Priority = Priority.NORMAL,
        operation_type: str = "generic"
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        檢查是否可以繼續執行
        
        Args:
            priority: 操作優先級
            operation_type: 操作類型（如place_order, close_position）
        
        Returns:
            Tuple[bool, str, dict]: (是否允許, 拒絕原因, 附加信息)
            附加信息包含：level, bypass_used, delay_seconds, retry_after
        """
        self.total_requests += 1
        self._check_timeout_recovery()
        self._update_level()
        
        info = {
            "level": self.level.value,
            "failure_count": self.failure_count,
            "bypass_used": False,
            "delay_seconds": 0.0,
            "retry_after": 0.0
        }
        
        # WARNING級：僅記錄，全部通過
        if self.level == CircuitLevel.WARNING:
            logger.warning(
                f"⚠️  熔斷器警告級: 失敗{self.failure_count}次 "
                f"(操作: {operation_type}, 優先級: {priority.name})"
            )
            return True, None, info
        
        # 檢查是否應該bypass
        should_bypass, bypass_reason = self._should_bypass(priority, operation_type)
        
        if should_bypass:
            self.bypassed_requests += 1
            info["bypass_used"] = True
            
            # 記錄bypass
            bypass_info = BypassInfo(
                timestamp=time.time(),
                priority=priority,
                operation_type=operation_type,
                level=self.level,
                reason=bypass_reason
            )
            self.bypass_history.append(bypass_info)
            
            # 保留最近100條記錄
            if len(self.bypass_history) > 100:
                self.bypass_history = self.bypass_history[-100:]
            
            bypass_logger.warning(
                f"🔓 Bypass使用: {bypass_reason} | "
                f"級別: {self.level.value} | "
                f"操作: {operation_type} | "
                f"優先級: {priority.name}"
            )
            
            return True, None, info
        
        # THROTTLED級：增加延遲
        if self.level == CircuitLevel.THROTTLED:
            self.throttled_requests += 1
            info["delay_seconds"] = self.throttle_delay
            
            logger.warning(
                f"🔸 熔斷器限流: 增加{self.throttle_delay}秒延遲 "
                f"(失敗{self.failure_count}次, 操作: {operation_type})"
            )
            
            return True, None, info
        
        # BLOCKED級：完全阻止
        if self.level == CircuitLevel.BLOCKED:
            self.blocked_requests += 1
            retry_after = max(0, self.timeout - (time.time() - self.last_failure_time))
            info["retry_after"] = retry_after
            
            reason = (
                f"熔斷器阻斷(失敗{self.failure_count}次)，"
                f"請{retry_after:.0f}秒後重試"
            )
            
            logger.error(
                f"🔴 {reason} | 操作: {operation_type} | 優先級: {priority.name}"
            )
            
            return False, reason, info
        
        # 正常通過
        return True, None, info
    
    async def call_async(
        self,
        func,
        priority: Priority = Priority.NORMAL,
        operation_type: str = "generic",
        *args,
        **kwargs
    ):
        """
        通過熔斷器調用異步函數
        
        Args:
            func: 異步函數
            priority: 優先級
            operation_type: 操作類型
            *args, **kwargs: 函數參數
        
        Returns:
            函數返回值
        
        Raises:
            Exception: 熔斷器阻止時拋出
        """
        import asyncio
        
        can_run, reason, info = self.can_proceed(priority, operation_type)
        
        if not can_run:
            raise Exception(reason)
        
        # 如果需要延遲（THROTTLED級）
        if info["delay_seconds"] > 0:
            await asyncio.sleep(info["delay_seconds"])
        
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def on_success(self):
        """處理成功調用"""
        if self.auto_decay and self.failure_count > 0:
            self.failure_count = max(0, self.failure_count - 1)
            self._update_level()
    
    def on_failure(self):
        """處理失敗調用"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self._update_level()
    
    def reset(self):
        """重置熔斷器"""
        logger.info("🔄 熔斷器手動重置")
        self.failure_count = 0
        self.last_failure_time = 0
        self.level = CircuitLevel.NORMAL
        self.level_history.append((time.time(), CircuitLevel.NORMAL))
    
    def enable_temporary_bypass(self, duration_seconds: int, reason: str):
        """
        啟用臨時bypass
        
        Args:
            duration_seconds: 持續時間（秒）
            reason: 啟用原因
        """
        expire_time = time.time() + duration_seconds
        self.temp_bypass = TemporaryBypass(
            enabled=True,
            expire_time=expire_time,
            reason=reason,
            enabled_at=time.time()
        )
        
        expire_datetime = datetime.fromtimestamp(expire_time).strftime("%H:%M:%S")
        logger.warning(
            f"🔓 臨時bypass已啟用: {reason} | "
            f"持續{duration_seconds}秒 | "
            f"過期時間: {expire_datetime}"
        )
        bypass_logger.warning(
            f"TEMPORARY_BYPASS_ENABLED: {reason} | duration={duration_seconds}s"
        )
    
    def disable_temporary_bypass(self):
        """關閉臨時bypass"""
        if self.temp_bypass:
            logger.info(f"🔒 臨時bypass已關閉: {self.temp_bypass.reason}")
            bypass_logger.info(f"TEMPORARY_BYPASS_DISABLED: {self.temp_bypass.reason}")
            self.temp_bypass = None
    
    def get_level(self) -> CircuitLevel:
        """獲取當前級別"""
        self._check_timeout_recovery()
        self._update_level()
        return self.level
    
    def get_stats(self) -> dict:
        """獲取統計信息"""
        bypass_rate = (
            (self.bypassed_requests / self.total_requests * 100)
            if self.total_requests > 0 else 0
        )
        
        return {
            "level": self.level.value,
            "failure_count": self.failure_count,
            "thresholds": {
                "warning": self.warning_threshold,
                "throttled": self.throttled_threshold,
                "blocked": self.blocked_threshold
            },
            "timeout": self.timeout,
            "time_since_last_failure": (
                int(time.time() - self.last_failure_time)
                if self.last_failure_time > 0 else None
            ),
            "statistics": {
                "total_requests": self.total_requests,
                "bypassed_requests": self.bypassed_requests,
                "throttled_requests": self.throttled_requests,
                "blocked_requests": self.blocked_requests,
                "bypass_rate": f"{bypass_rate:.2f}%"
            },
            "temporary_bypass": {
                "enabled": self.temp_bypass.enabled if self.temp_bypass else False,
                "reason": self.temp_bypass.reason if self.temp_bypass else None,
                "expires_in": (
                    int(self.temp_bypass.expire_time - time.time())
                    if self.temp_bypass else None
                )
            }
        }
    
    def get_bypass_history(self, limit: int = 20) -> list:
        """獲取最近的bypass記錄"""
        recent = self.bypass_history[-limit:]
        return [
            {
                "timestamp": datetime.fromtimestamp(b.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                "priority": b.priority.name,
                "operation": b.operation_type,
                "level": b.level.value,
                "reason": b.reason
            }
            for b in recent
        ]


# ============ 保留舊版CircuitBreaker以保持向後兼容 ============

class CircuitBreaker:
    """
    API 調用熔斷器（舊版，保留向後兼容）
    
    ⚠️  建議使用新版 GradedCircuitBreaker
    """
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        """初始化熔斷器"""
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: float = 0
        self.state = CircuitState.CLOSED
        self.manual_open_reason: Optional[str] = None
    
    async def call_async(self, func, *args, **kwargs):
        """通過熔斷器調用異步函數"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.timeout:
                logger.info("熔斷器進入半開狀態，嘗試恢復")
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"熔斷器開啟，請 {self.timeout - (time.time() - self.last_failure_time):.0f} 秒後重試")
        
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def call(self, func, *args, **kwargs):
        """通過熔斷器調用同步函數"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.timeout:
                logger.info("熔斷器進入半開狀態，嘗試恢復")
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"熔斷器開啟，請 {self.timeout - (time.time() - self.last_failure_time):.0f} 秒後重試")
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def on_success(self):
        """處理成功調用"""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("熔斷器恢復正常")
            self.reset()
        
        if self.failure_count > 0:
            self.failure_count -= 1
    
    def on_failure(self):
        """處理失敗調用"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(f"熔斷器開啟：連續失敗 {self.failure_count} 次")
    
    def reset(self):
        """重置熔斷器"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = 0
    
    def get_stats(self) -> dict:
        """獲取熔斷器統計"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "timeout": self.timeout,
            "time_since_last_failure": int(time.time() - self.last_failure_time) if self.last_failure_time > 0 else None,
            "manual_open_reason": self.manual_open_reason
        }
    
    def is_open(self) -> bool:
        """檢查熔斷器是否開啟"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.timeout:
                return False
            return True
        return False
    
    def get_retry_after(self) -> float:
        """獲取剩餘等待時間"""
        if self.state != CircuitState.OPEN:
            return 0.0
        
        elapsed = time.time() - self.last_failure_time
        remaining = max(0, self.timeout - elapsed)
        return remaining
    
    def manual_open(self, reason: str, cooldown: Optional[int] = None):
        """手動開啟熔斷器"""
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        self.manual_open_reason = reason
        
        if cooldown is not None:
            original_timeout = self.timeout
            self.timeout = cooldown
            logger.warning(
                f"⚠️  熔斷器已手動開啟: {reason} "
                f"(冷卻{cooldown}秒)"
            )
            self.timeout = original_timeout
        else:
            logger.warning(
                f"⚠️  熔斷器已手動開啟: {reason} "
                f"(冷卻{self.timeout}秒)"
            )
    
    def can_proceed(self) -> tuple[bool, Optional[str]]:
        """檢查是否可以繼續執行"""
        if not self.is_open():
            return True, None
        
        retry_after = self.get_retry_after()
        reason = self.manual_open_reason or "連續失敗觸發"
        
        return False, f"熔斷器開啟({reason})，請{retry_after:.0f}秒後重試"
