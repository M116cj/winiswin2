"""
特征缓存系统（v3.4.0）
职责：缓存计算好的特征，加速预测过程
"""

import os
import pickle
import hashlib
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


class FeatureCache:
    """特征缓存管理器"""
    
    def __init__(self, cache_dir: str = 'data/feature_cache', ttl: int = 3600):
        """
        初始化特征缓存
        
        Args:
            cache_dir: 缓存目录
            ttl: 缓存有效期（秒），默认1小时
        """
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.hit_count = 0
        self.miss_count = 0
        
        os.makedirs(cache_dir, exist_ok=True)
        
        # 启动时清理过期缓存
        self._cleanup_expired()
    
    def _get_cache_key(self, signal: Dict) -> str:
        """
        生成缓存键
        
        Args:
            signal: 交易信号
        
        Returns:
            str: 缓存键（MD5哈希）
        """
        # 使用symbol + timestamp作为唯一标识
        key_data = {
            'symbol': signal.get('symbol', ''),
            'timestamp': signal.get('timestamp', ''),
            'direction': signal.get('direction', ''),
            'entry_price': signal.get('entry_price', 0)
        }
        
        key_str = str(sorted(key_data.items()))
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, signal: Dict) -> Optional[Any]:
        """
        获取缓存的特征
        
        Args:
            signal: 交易信号
        
        Returns:
            Optional[Any]: 缓存的特征，如果不存在或过期则返回None
        """
        cache_key = self._get_cache_key(signal)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pkl")
        
        try:
            if not os.path.exists(cache_file):
                self.miss_count += 1
                return None
            
            # 检查是否过期
            file_mtime = os.path.getmtime(cache_file)
            age = time.time() - file_mtime
            
            if age > self.ttl:
                # 过期，删除并返回None
                os.remove(cache_file)
                self.miss_count += 1
                logger.debug(f"缓存过期: {cache_key}")
                return None
            
            # 读取缓存
            with open(cache_file, 'rb') as f:
                features = pickle.load(f)
            
            self.hit_count += 1
            logger.debug(f"✅ 缓存命中: {signal.get('symbol')}")
            return features
            
        except Exception as e:
            logger.warning(f"读取缓存失败: {e}")
            self.miss_count += 1
            return None
    
    def set(self, signal: Dict, features: Any):
        """
        缓存特征
        
        Args:
            signal: 交易信号
            features: 计算好的特征
        """
        cache_key = self._get_cache_key(signal)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pkl")
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(features, f)
            logger.debug(f"💾 特征已缓存: {signal.get('symbol')}")
        except Exception as e:
            logger.warning(f"缓存特征失败: {e}")
    
    def get_hit_rate(self) -> float:
        """
        获取缓存命中率
        
        Returns:
            float: 命中率（0.0-1.0）
        """
        total = self.hit_count + self.miss_count
        if total == 0:
            return 0.0
        return self.hit_count / total
    
    def get_stats(self) -> Dict:
        """
        获取缓存统计信息
        
        Returns:
            Dict: 统计信息
        """
        return {
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'hit_rate': self.get_hit_rate(),
            'cache_size': self._get_cache_size()
        }
    
    def _get_cache_size(self) -> int:
        """获取缓存文件数量"""
        try:
            return len([f for f in os.listdir(self.cache_dir) if f.endswith('.pkl')])
        except:
            return 0
    
    def _cleanup_expired(self):
        """清理过期缓存"""
        try:
            cleaned = 0
            current_time = time.time()
            
            for filename in os.listdir(self.cache_dir):
                if not filename.endswith('.pkl'):
                    continue
                
                filepath = os.path.join(self.cache_dir, filename)
                file_mtime = os.path.getmtime(filepath)
                age = current_time - file_mtime
                
                if age > self.ttl:
                    os.remove(filepath)
                    cleaned += 1
            
            if cleaned > 0:
                logger.info(f"清理过期缓存: {cleaned} 个文件")
        except Exception as e:
            logger.warning(f"清理缓存失败: {e}")
    
    def clear(self):
        """清空所有缓存"""
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.pkl'):
                    os.remove(os.path.join(self.cache_dir, filename))
            
            self.hit_count = 0
            self.miss_count = 0
            logger.info("缓存已清空")
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
