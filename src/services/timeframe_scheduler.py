"""
時間框架調度器
職責：實現差異化掃描頻率，優化 API 使用
"""

import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TimeframeScheduler:
    """
    時間框架調度器
    
    策略（僅 3 個時間框架）：
    - 1h：每小時掃描一次（趨勢確認）
    - 15m：每15分鐘掃描一次（趨勢確認）
    - 5m：每分鐘掃描（趨勢符合確認 + 入場信號）
    """
    
    def __init__(self):
        """初始化調度器"""
        # 僅使用 1h/15m/5m（取消 1m 監控）
        self.last_scan_times: Dict[str, float] = {
            "1h": 0,
            "15m": 0,
            "5m": 0
        }
        
        # 掃描間隔（秒）
        self.scan_intervals = {
            "1h": 3600,   # 每小時（趨勢確認）
            "15m": 900,   # 每15分鐘（趨勢確認）
            "5m": 60      # 每1分鐘（趨勢符合確認 + 入場信號）
        }
        
        logger.info(
            f"時間框架調度器初始化: "
            f"1h={self.scan_intervals['1h']}s, "
            f"15m={self.scan_intervals['15m']}s, "
            f"5m={self.scan_intervals['5m']}s"
        )
    
    def should_scan_timeframe(self, timeframe: str) -> bool:
        """
        判斷是否應該掃描特定時間框架
        
        Args:
            timeframe: 時間框架 (1h/15m/5m)
        
        Returns:
            bool: 是否應該掃描
        """
        current_time = time.time()
        last_scan = self.last_scan_times.get(timeframe, 0)
        interval = self.scan_intervals.get(timeframe, 60)
        
        should_scan = (current_time - last_scan) >= interval
        
        if should_scan:
            logger.debug(f"時間框架 {timeframe} 需要更新")
        
        return should_scan
    
    def mark_scanned(self, timeframe: str):
        """
        標記時間框架已掃描
        
        Args:
            timeframe: 時間框架
        """
        self.last_scan_times[timeframe] = time.time()
        logger.debug(f"標記 {timeframe} 已掃描")
    
    def get_required_timeframes(self) -> List[str]:
        """
        獲取需要掃描的時間框架列表
        
        Returns:
            List[str]: 需要掃描的時間框架
        """
        required = []
        for tf in ["1h", "15m", "5m"]:  # 僅 3 個時間框架
            if self.should_scan_timeframe(tf):
                required.append(tf)
        
        return required
    
    def get_next_scan_time(self, timeframe: str) -> Optional[datetime]:
        """
        獲取下次掃描時間
        
        Args:
            timeframe: 時間框架
        
        Returns:
            Optional[datetime]: 下次掃描時間
        """
        last_scan = self.last_scan_times.get(timeframe, 0)
        interval = self.scan_intervals.get(timeframe, 60)
        
        if last_scan == 0:
            return datetime.now()
        
        next_scan = datetime.fromtimestamp(last_scan + interval)
        return next_scan
    
    def get_status(self) -> Dict:
        """
        獲取調度器狀態
        
        Returns:
            Dict: 狀態信息
        """
        current_time = time.time()
        status = {}
        
        for tf in ["1h", "15m", "5m"]:  # 僅 3 個時間框架
            last_scan = self.last_scan_times.get(tf, 0)
            interval = self.scan_intervals.get(tf, 60)
            
            if last_scan == 0:
                time_since = "從未掃描"
                next_in = "立即"
            else:
                time_since = f"{int(current_time - last_scan)}秒前"
                next_scan_time = last_scan + interval - current_time
                next_in = f"{int(max(0, next_scan_time))}秒"
            
            status[tf] = {
                "interval": f"{interval}秒",
                "last_scan": time_since,
                "next_scan": next_in,
                "should_scan": self.should_scan_timeframe(tf)
            }
        
        return status
    
    def reset(self):
        """重置所有掃描時間"""
        for tf in self.last_scan_times:
            self.last_scan_times[tf] = 0
        logger.info("調度器已重置")


class SmartDataManager:
    """
    智能數據管理器
    職責：按需獲取不同時間框架數據，最小化 API 調用
    """
    
    def __init__(self, data_service):
        """
        初始化數據管理器
        
        Args:
            data_service: 數據服務實例
        """
        self.data_service = data_service
        self.scheduler = TimeframeScheduler()
        
        # 緩存的時間框架數據
        self.cached_trend_data: Dict[str, Dict] = {}  # 1h, 15m
        
        logger.info("智能數據管理器初始化完成")
    
    async def get_multi_timeframe_data(
        self,
        symbol: str,
        force_refresh: bool = False
    ) -> Dict:
        """
        智能獲取多時間框架數據
        
        策略：
        - 1h, 15m：使用緩存（除非到時間更新）
        - 5m, 1m：始終獲取最新數據
        
        Args:
            symbol: 交易對
            force_refresh: 強制刷新所有數據
        
        Returns:
            Dict: 多時間框架數據
        """
        result = {}
        
        # 獲取需要更新的時間框架
        required_tfs = self.scheduler.get_required_timeframes()
        
        # 1h - 趨勢確認（每小時更新一次）
        if force_refresh or "1h" in required_tfs or symbol not in self.cached_trend_data.get("1h", {}):
            result["1h"] = await self.data_service.get_klines(symbol, "1h", limit=100)
            if "1h" not in self.cached_trend_data:
                self.cached_trend_data["1h"] = {}
            self.cached_trend_data["1h"][symbol] = result["1h"]
            if "1h" in required_tfs:
                self.scheduler.mark_scanned("1h")
        else:
            # 使用緩存
            result["1h"] = self.cached_trend_data["1h"].get(symbol)
        
        # 15m - 趨勢確認（每15分鐘更新一次）
        if force_refresh or "15m" in required_tfs or symbol not in self.cached_trend_data.get("15m", {}):
            result["15m"] = await self.data_service.get_klines(symbol, "15m", limit=100)
            if "15m" not in self.cached_trend_data:
                self.cached_trend_data["15m"] = {}
            self.cached_trend_data["15m"][symbol] = result["15m"]
            if "15m" in required_tfs:
                self.scheduler.mark_scanned("15m")
        else:
            # 使用緩存
            result["15m"] = self.cached_trend_data["15m"].get(symbol)
        
        # 5m - 趨勢符合確認 + 入場信號（高頻，始終獲取最新）
        result["5m"] = await self.data_service.get_klines(symbol, "5m", limit=100)
        
        return result
    
    def get_scheduler_status(self) -> Dict:
        """
        獲取調度器狀態
        
        Returns:
            Dict: 狀態信息
        """
        return self.scheduler.get_status()
    
    def clear_cache(self):
        """清空緩存"""
        self.cached_trend_data = {}
        logger.info("數據緩存已清空")
