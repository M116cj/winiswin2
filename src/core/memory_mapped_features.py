"""
记忆体映射特征存储
优化4：记忆体映射特征存储
"""
import numpy as np
import tempfile
import os
import logging
import time
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class MemoryMappedFeatureStore:
    """记忆体映射特征存储"""
    
    def __init__(self, max_positions: int = 1000, feature_dim: int = 32):
        """
        初始化记忆体映射特征存储
        
        Args:
            max_positions: 最大仓位数
            feature_dim: 特征维度
        """
        self.max_positions = max_positions
        self.feature_dim = feature_dim
        self.temp_dir = tempfile.mkdtemp()
        self.feature_file = os.path.join(self.temp_dir, "features.dat")
        self.position_file = os.path.join(self.temp_dir, "positions.dat")
        
        # 创建记忆体映射文件
        self.features = np.memmap(
            self.feature_file, 
            dtype='float32', 
            mode='w+', 
            shape=(max_positions, feature_dim)
        )
        self.positions = np.memmap(
            self.position_file,
            dtype=[('id', 'U20'), ('active', '?'), ('timestamp', 'f8')],
            mode='w+',
            shape=(max_positions,)
        )
        
        self.next_slot = 0
        self.slot_map: Dict[str, int] = {}  # position_id -> slot_index
        
        logger.info(f"✅ 记忆体映射特征存储初始化")
        logger.info(f"  最大仓位: {max_positions}")
        logger.info(f"  特征维度: {feature_dim}")
        logger.info(f"  临时目录: {self.temp_dir}")
    
    def store_features(self, position_id: str, features):
        """
        存储特征到记忆体映射
        
        Args:
            position_id: 仓位ID
            features: 特征向量
        """
        if position_id in self.slot_map:
            slot = self.slot_map[position_id]
        else:
            if self.next_slot >= self.max_positions:
                # 覆盖最旧的非活跃仓位
                slot = self._find_oldest_inactive_slot()
            else:
                slot = self.next_slot
                self.next_slot += 1
            self.slot_map[position_id] = slot
        
        self.features[slot] = features
        self.positions[slot] = (position_id, True, time.time())
        
        logger.debug(f"💾 存储特征: {position_id} -> slot {slot}")
    
    def get_features(self, position_id: str) -> Optional[np.ndarray]:
        """
        获取特征
        
        Args:
            position_id: 仓位ID
        
        Returns:
            特征向量（副本）或 None
        """
        if position_id not in self.slot_map:
            return None
        slot = self.slot_map[position_id]
        return self.features[slot].copy()
    
    def mark_inactive(self, position_id: str):
        """
        标记仓位为非活跃
        
        Args:
            position_id: 仓位ID
        """
        if position_id in self.slot_map:
            slot = self.slot_map[position_id]
            self.positions[slot]['active'] = False
            logger.debug(f"🔒 标记为非活跃: {position_id}")
    
    def _find_oldest_inactive_slot(self) -> int:
        """
        查找最旧的非活跃槽位
        
        Returns:
            槽位索引
        """
        inactive_positions = []
        for i in range(self.next_slot):
            if not self.positions[i]['active']:
                inactive_positions.append((i, self.positions[i]['timestamp']))
        
        if inactive_positions:
            # 找到最旧的非活跃仓位
            oldest_slot = min(inactive_positions, key=lambda x: x[1])[0]
            # 从映射中移除旧仓位
            old_position_id = self.positions[oldest_slot]['id']
            if old_position_id in self.slot_map:
                del self.slot_map[old_position_id]
            logger.debug(f"🔄 重用槽位 {oldest_slot}（覆盖 {old_position_id}）")
            return oldest_slot
        else:
            # 所有仓位都活跃，重用第一个
            logger.warning(f"⚠️ 所有槽位都活跃，强制重用槽位 0")
            old_position_id = self.positions[0]['id']
            if old_position_id in self.slot_map:
                del self.slot_map[old_position_id]
            return 0
    
    def get_active_count(self) -> int:
        """获取活跃仓位数量"""
        return sum(1 for i in range(self.next_slot) if self.positions[i]['active'])
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        active_count = self.get_active_count()
        return {
            "max_positions": self.max_positions,
            "feature_dim": self.feature_dim,
            "next_slot": self.next_slot,
            "active_positions": active_count,
            "utilization": active_count / self.max_positions if self.max_positions > 0 else 0,
            "temp_dir": self.temp_dir
        }
    
    def cleanup(self):
        """清理临时文件"""
        try:
            # 删除映射
            del self.features
            del self.positions
            
            # 删除文件
            if os.path.exists(self.feature_file):
                os.remove(self.feature_file)
            if os.path.exists(self.position_file):
                os.remove(self.position_file)
            if os.path.exists(self.temp_dir):
                os.rmdir(self.temp_dir)
            
            logger.info(f"🗑️ 临时文件已清理: {self.temp_dir}")
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")
    
    def __del__(self):
        """析构函数"""
        self.cleanup()
