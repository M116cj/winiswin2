"""
數據歸檔器 - 兼容層（v3.17+）
原始功能已整合到 TradeRecorder
此文件僅保留向後兼容接口
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DataArchiver:
    """數據歸檔器兼容層"""
    
    def __init__(self, data_dir: str = "ml_data"):
        """初始化數據歸檔器（兼容層）"""
        self.data_dir = data_dir
        logger.info(f"✅ 數據歸檔器（兼容層）已初始化: {data_dir}")
    
    def archive_signal(
        self,
        signal_data: Dict[str, Any],
        accepted: bool,
        rejection_reason: str = None
    ):
        """歸檔信號（兼容層）"""
        pass
    
    def archive_position_open(
        self,
        position_data: Dict[str, Any],
        is_virtual: bool = False
    ):
        """歸檔開倉（兼容層）"""
        pass
    
    def archive_position_close(
        self,
        position_data: Dict[str, Any],
        close_data: Dict[str, Any],
        is_virtual: bool = False
    ):
        """歸檔平倉（兼容層）"""
        pass
