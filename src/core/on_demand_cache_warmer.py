"""
On-Demand Cache Warmer for SelfLearningTrader v4.6.0 Phase 1A5
事件驱动的缓存预热：无需async后台任务

Author: SelfLearningTrader Team
Version: 4.6.0
"""

import time
import threading
from typing import Dict, List, Set, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class OnDemandCacheWarmer:
    """
    事件驱动缓存预热器：利用现有系统事件触发预热
    
    策略：
    - 记录访问模式（哪些symbol/timeframe被频繁访问）
    - 在市场扫描后触发预热（同步调用）
    - 在交易信号生成后预热相关timeframe
    - 无需async后台任务
    
    性能目标：85% → 88% 缓存命中率
    """
    
    def __init__(
        self,
        cache_manager,
        warm_threshold: int = 5,
        cooldown_seconds: int = 300,
        top_n_warm: int = 3,
        enable_warming: bool = True
    ):
        """
        初始化事件驱动缓存预热器
        
        Args:
            cache_manager: 缓存管理器实例
            warm_threshold: 触发预热的访问次数阈值
            cooldown_seconds: 预热冷却时间（秒）
            top_n_warm: 每次最多预热N个候选
            enable_warming: 是否启用预热
        """
        self.cache = cache_manager
        self.warm_threshold = warm_threshold
        self.cooldown_seconds = cooldown_seconds
        self.top_n_warm = top_n_warm
        self.enable_warming = enable_warming
        
        # 访问模式记录：symbol_timeframe -> count
        self.access_patterns: Dict[str, int] = defaultdict(int)
        
        # 上次预热时间：symbol_timeframe -> timestamp
        self.last_warm_time: Dict[str, float] = {}
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            'warmings_triggered': 0,
            'items_warmed': 0,
            'warmings_skipped': 0
        }
        
        logger.info(
            f"✅ OnDemandCacheWarmer已初始化 (v4.6.0 Phase 1A5)\n"
            f"   预热阈值: {warm_threshold}次访问\n"
            f"   冷却时间: {cooldown_seconds}秒\n"
            f"   Top-N预热: {top_n_warm}\n"
            f"   预热功能: {'启用' if enable_warming else '禁用'}"
        )
    
    def record_market_scan(self, scanned_symbols: List[str], timeframe: str = "1m") -> None:
        """
        记录市场扫描事件并触发预热（主要集成点）
        
        在每次市场扫描完成后调用此方法
        
        Args:
            scanned_symbols: 扫描的交易对列表
            timeframe: 时间框架
        """
        if not self.enable_warming:
            return
        
        with self._lock:
            # 更新访问模式
            for symbol in scanned_symbols:
                key = f"{symbol}_{timeframe}"
                self.access_patterns[key] += 1
            
            # 识别需要预热的候选
            warm_candidates = self._identify_warm_candidates()
        
        # 预热top-N候选
        if warm_candidates:
            logger.debug(f"🔥 市场扫描后预热: {len(warm_candidates)}个候选")
            for key in warm_candidates[:self.top_n_warm]:
                self._warm_cache_sync(key)
    
    def record_trading_signal(self, symbol: str, timeframe: str = "1m") -> None:
        """
        记录交易信号生成事件并预热相关timeframe
        
        当生成交易信号时调用此方法
        
        Args:
            symbol: 交易对符号
            timeframe: 当前时间框架
        """
        if not self.enable_warming:
            return
        
        key = f"{symbol}_{timeframe}"
        
        with self._lock:
            # 交易信号权重更高
            self.access_patterns[key] += 5
            
            # 同时预热更高时间框架（用于上下文分析）
            for higher_tf in ["5m", "15m", "1h"]:
                if higher_tf != timeframe:
                    context_key = f"{symbol}_{higher_tf}"
                    self.access_patterns[context_key] += 2
        
        logger.debug(f"📈 交易信号触发预热: {symbol} ({timeframe})")
        
        # 立即预热当前symbol的相关数据
        self._warm_cache_sync(key)
    
    def record_cache_access(self, symbol: str, timeframe: str = "1m") -> None:
        """
        记录缓存访问（可选的额外追踪点）
        
        Args:
            symbol: 交易对符号
            timeframe: 时间框架
        """
        if not self.enable_warming:
            return
        
        key = f"{symbol}_{timeframe}"
        with self._lock:
            self.access_patterns[key] += 1
    
    def _identify_warm_candidates(self) -> List[str]:
        """
        识别需要预热的候选（基于访问模式和冷却时间）
        
        Returns:
            候选键列表（按优先级排序）
        """
        candidates = []
        current_time = time.time()
        
        for key, count in self.access_patterns.items():
            # 检查是否达到阈值
            if count < self.warm_threshold:
                continue
            
            # 检查冷却时间
            last_warm = self.last_warm_time.get(key, 0)
            if current_time - last_warm < self.cooldown_seconds:
                continue
            
            candidates.append((key, count))
        
        # 按访问次数排序（高频优先）
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return [key for key, _ in candidates]
    
    def _warm_cache_sync(self, key: str) -> None:
        """
        同步预热缓存（无需async）
        
        Args:
            key: 缓存键（格式：symbol_timeframe）
        """
        try:
            symbol, timeframe = key.split('_')
            
            # 预测下一步需要的数据
            future_data_points = self._predict_next_access(symbol, timeframe)
            
            if not future_data_points:
                self.stats['warmings_skipped'] += 1
                return
            
            # 预取数据（使用现有缓存接口）
            warmed_count = 0
            for data_point in future_data_points:
                if self._prefetch_data(data_point):
                    warmed_count += 1
            
            # 更新统计
            with self._lock:
                self.last_warm_time[key] = time.time()
                self.stats['warmings_triggered'] += 1
                self.stats['items_warmed'] += warmed_count
            
            logger.debug(
                f"✅ 缓存已预热: {key}, "
                f"预取={warmed_count}项"
            )
            
        except Exception as e:
            logger.warning(f"⚠️ 缓存预热失败 ({key}): {e}")
            self.stats['warmings_skipped'] += 1
    
    def _predict_next_access(self, symbol: str, timeframe: str) -> List[Dict]:
        """
        预测下一步可能访问的数据点
        
        策略：预取最近的K线数据
        
        Args:
            symbol: 交易对符号
            timeframe: 时间框架
            
        Returns:
            数据点列表
        """
        # 简单策略：预取接下来的K线数据
        # 实际实现需要根据缓存管理器的接口调整
        
        future_data = []
        
        # 根据timeframe预测需要的数据范围
        prefetch_count = {
            '1m': 10,   # 预取10分钟
            '5m': 6,    # 预取30分钟
            '15m': 4,   # 预取1小时
            '1h': 3     # 预取3小时
        }.get(timeframe, 5)
        
        for i in range(prefetch_count):
            future_data.append({
                'symbol': symbol,
                'timeframe': timeframe,
                'offset': i  # 相对当前的偏移
            })
        
        return future_data
    
    def _prefetch_data(self, data_point: Dict) -> bool:
        """
        预取数据到缓存
        
        Args:
            data_point: 数据点描述
            
        Returns:
            是否成功预取
        """
        try:
            # 这里需要调用缓存管理器的预取方法
            # 具体实现取决于缓存管理器的接口
            
            symbol = data_point['symbol']
            timeframe = data_point['timeframe']
            
            # 示例：如果缓存管理器有prefetch方法
            if hasattr(self.cache, 'prefetch'):
                self.cache.prefetch(symbol, timeframe)
                return True
            
            # 或者通过get触发加载
            if hasattr(self.cache, 'get'):
                self.cache.get(symbol, timeframe)
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"预取失败: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            统计字典
        """
        result = dict(self.stats)
        result['access_patterns_count'] = len(self.access_patterns)
        success_rate = (
            (self.stats['warmings_triggered'] / 
             (self.stats['warmings_triggered'] + self.stats['warmings_skipped']) * 100)
            if (self.stats['warmings_triggered'] + self.stats['warmings_skipped']) > 0 else 0.0
        )
        result['warm_success_rate'] = success_rate
        return result
    
    def log_stats(self) -> None:
        """记录统计信息"""
        stats = self.get_stats()
        logger.info(
            f"📊 OnDemandCacheWarmer统计:\n"
            f"   预热触发: {stats['warmings_triggered']}次\n"
            f"   预热项数: {stats['items_warmed']}\n"
            f"   跳过次数: {stats['warmings_skipped']}\n"
            f"   成功率: {stats['warm_success_rate']:.1f}%\n"
            f"   访问模式: {stats['access_patterns_count']}个"
        )
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            'warmings_triggered': 0,
            'items_warmed': 0,
            'warmings_skipped': 0
        }
        logger.info("📊 统计信息已重置")
    
    def clear_access_patterns(self) -> None:
        """清除访问模式（定期维护）"""
        with self._lock:
            self.access_patterns.clear()
            self.last_warm_time.clear()
        logger.info("🧹 访问模式已清除")
