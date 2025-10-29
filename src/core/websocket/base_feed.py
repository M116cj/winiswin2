"""
BaseFeed v3.17.2+ - WebSocket Feed基類
職責：提供統一的心跳監控、REST備援智慧冷卻、時間戳管理
"""

import asyncio
import time
import logging
from typing import Dict, Optional, Callable, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseFeed(ABC):
    """
    BaseFeed - WebSocket Feed抽象基類
    
    職責：
    1. 統一心跳監控（檢測連線活躍度）
    2. REST備援智慧冷卻（指數退避策略）
    3. 時間戳標準化管理
    4. 連線狀態追蹤
    
    設計原則：
    - 所有Feed（KlineFeed、AccountFeed、PriceFeed等）繼承此基類
    - 提供通用的穩定性保障機制
    - 避免代碼重複
    """
    
    def __init__(self, name: str):
        """
        初始化BaseFeed
        
        Args:
            name: Feed名稱（用於日誌標識）
        """
        self.name = name
        self.running = False
        
        # 心跳監控
        self._last_message_time = time.time()
        self._heartbeat_interval = 10  # 每10秒檢查一次
        self._heartbeat_timeout = 30   # 30秒無訊息判定為超時
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # REST備援冷卻（智慧指數退避）
        self._rest_failure_count: Dict[str, int] = {}  # {symbol: failure_count}
        self._last_rest_call: Dict[str, float] = {}    # {symbol: last_call_timestamp}
        self._rest_min_cooldown = 60    # 最小冷卻時間：60秒
        self._rest_max_cooldown = 300   # 最大冷卻時間：300秒（5分鐘）
        
        # 統計數據
        self.stats = {
            'total_messages': 0,
            'reconnections': 0,
            'errors': 0,
            'heartbeat_timeouts': 0,
            'rest_fallback_calls': 0,
            'rest_fallback_failures': 0
        }
    
    # ==================== 心跳監控 ====================
    
    def _update_heartbeat(self):
        """更新心跳時間戳（每收到訊息時調用）"""
        self._last_message_time = time.time()
        self.stats['total_messages'] += 1
    
    async def _start_heartbeat_monitor(self):
        """
        啟動心跳監控任務
        
        功能：
        - 每10秒檢查一次最後訊息時間
        - 超過30秒無訊息 → 觸發重連
        """
        self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        logger.debug(f"✅ {self.name} 心跳監控已啟動")
    
    async def _heartbeat_monitor(self):
        """心跳監控循環"""
        while self.running:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                
                elapsed = time.time() - self._last_message_time
                
                if elapsed > self._heartbeat_timeout:
                    self.stats['heartbeat_timeouts'] += 1
                    logger.warning(
                        f"⚠️ {self.name} 心跳超時 "
                        f"({elapsed:.1f}秒無訊息，閾值{self._heartbeat_timeout}秒）"
                    )
                    
                    # 觸發重連（由子類實現）
                    await self._on_heartbeat_timeout()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ {self.name} 心跳監控錯誤: {e}")
                await asyncio.sleep(5)
    
    async def _stop_heartbeat_monitor(self):
        """停止心跳監控任務"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            logger.debug(f"✅ {self.name} 心跳監控已停止")
    
    @abstractmethod
    async def _on_heartbeat_timeout(self):
        """
        心跳超時回調（由子類實現）
        
        子類應該：
        - 嘗試重連WebSocket
        - 或觸發告警
        """
        pass
    
    # ==================== REST備援智慧冷卻 ====================
    
    def _calculate_rest_cooldown(self, symbol: str) -> float:
        """
        計算REST備援冷卻時間（指數退避）
        
        策略：
        - 第1次失敗: 60秒
        - 第2次失敗: 120秒 (60 × 2^1)
        - 第3次失敗: 240秒 (60 × 2^2)
        - 第4次失敗: 300秒 (達到上限)
        
        Args:
            symbol: 交易對
        
        Returns:
            冷卻時間（秒）
        """
        failure_count = self._rest_failure_count.get(symbol, 0)
        cooldown = min(
            self._rest_max_cooldown,
            self._rest_min_cooldown * (2 ** failure_count)
        )
        return cooldown
    
    async def _safe_rest_fallback(
        self,
        symbol: str,
        fallback_func: Callable,
        *args,
        **kwargs
    ) -> Optional[Any]:
        """
        安全的REST備援調用（帶智慧冷卻）
        
        特性：
        - 指數退避冷卻
        - 成功重置失敗計數
        - 統計追蹤
        
        Args:
            symbol: 交易對
            fallback_func: REST備援函數
            *args: 位置參數
            **kwargs: 關鍵字參數
        
        Returns:
            REST響應數據，或None（如果冷卻中/失敗）
        """
        # 1. 檢查冷卻時間
        cooldown = self._calculate_rest_cooldown(symbol)
        last_call_time = self._last_rest_call.get(symbol, 0)
        elapsed = time.time() - last_call_time
        
        if elapsed < cooldown:
            remaining = cooldown - elapsed
            logger.debug(
                f"⏳ {self.name} REST冷卻中 "
                f"(symbol={symbol}, 剩餘{remaining:.1f}秒)"
            )
            return None
        
        # 2. 執行REST備援調用
        try:
            self.stats['rest_fallback_calls'] += 1
            self._last_rest_call[symbol] = time.time()
            
            result = await fallback_func(*args, **kwargs)
            
            # 成功 → 重置失敗計數
            if symbol in self._rest_failure_count:
                del self._rest_failure_count[symbol]
            
            logger.debug(
                f"✅ {self.name} REST備援成功 (symbol={symbol})"
            )
            return result
        
        except Exception as e:
            # 失敗 → 增加失敗計數
            self.stats['rest_fallback_failures'] += 1
            self._rest_failure_count[symbol] = \
                self._rest_failure_count.get(symbol, 0) + 1
            
            failure_count = self._rest_failure_count[symbol]
            next_cooldown = self._calculate_rest_cooldown(symbol)
            
            logger.warning(
                f"⚠️ {self.name} REST備援失敗 "
                f"(symbol={symbol}, 失敗{failure_count}次, "
                f"下次冷卻{next_cooldown}秒): {e}"
            )
            return None
    
    # ==================== 時間戳工具 ====================
    
    @staticmethod
    def get_server_timestamp_ms(data: dict, key: str = 't') -> int:
        """
        獲取伺服器時間戳（毫秒）
        
        Args:
            data: WebSocket數據
            key: 時間戳字段名（默認't'）
        
        Returns:
            伺服器時間戳（毫秒）
        """
        return int(data.get(key, 0))
    
    @staticmethod
    def get_local_timestamp_ms() -> int:
        """
        獲取本地時間戳（毫秒）
        
        Returns:
            本地時間戳（毫秒）
        """
        return int(time.time() * 1000)
    
    @staticmethod
    def calculate_latency_ms(server_ts: int, local_ts: int) -> int:
        """
        計算網路延遲（毫秒）
        
        Args:
            server_ts: 伺服器時間戳（毫秒）
            local_ts: 本地接收時間戳（毫秒）
        
        Returns:
            延遲時間（毫秒）
        """
        return abs(local_ts - server_ts)
    
    # ==================== 統計與生命週期 ====================
    
    def get_stats(self) -> Dict:
        """
        獲取統計數據
        
        Returns:
            統計數據字典
        """
        return {
            **self.stats,
            'running': self.running,
            'last_message_elapsed': time.time() - self._last_message_time,
            'rest_failure_symbols': len(self._rest_failure_count)
        }
    
    @abstractmethod
    async def start(self):
        """啟動Feed（由子類實現）"""
        pass
    
    @abstractmethod
    async def stop(self):
        """停止Feed（由子類實現）"""
        pass
