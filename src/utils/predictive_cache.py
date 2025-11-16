"""
🚀 v4.6.0: 预测性缓存预热系统
职责：提前计算高概率需要的技术指标，提升缓存命中率

性能目标：
- 缓存命中率：85% → 92%+
- 减少实时计算延迟
- 智能预测下一轮扫描需要的数据
"""

import logging
import asyncio
from typing import List, Dict, Optional, Set
from collections import deque
import time

logger = logging.getLogger(__name__)


class PredictiveCacheWarmer:
    """
    预测性缓存预热器
    
    策略：
    1. 基于历史访问模式预测
    2. 预加载高频交易对的指标
    3. 后台异步预热，不阻塞主流程
    """
    
    def __init__(
        self,
        elite_engine,
        top_n_symbols: int = 50,
        preheat_interval: int = 240
    ):
        """
        初始化预热器
        
        Args:
            elite_engine: EliteTechnicalEngine实例
            top_n_symbols: 预热前N个高频交易对
            preheat_interval: 预热间隔（秒）
        """
        self.elite_engine = elite_engine
        self.top_n_symbols = top_n_symbols
        self.preheat_interval = preheat_interval
        
        # 访问模式追踪
        self.symbol_access_count: Dict[str, int] = {}
        self.indicator_access_count: Dict[str, int] = {}
        self.recent_symbols: deque = deque(maxlen=200)
        
        # 预热统计
        self.stats = {
            'preheat_rounds': 0,
            'indicators_preheated': 0,
            'preheat_duration_total': 0.0,
            'last_preheat_time': 0.0
        }
        
        # 后台任务
        self._preheat_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("=" * 60)
        logger.info("✅ 预测性缓存预热器已创建 (v4.6.0)")
        logger.info(f"   🎯 预热前 {top_n_symbols} 个高频交易对")
        logger.info(f"   ⏰ 预热间隔: {preheat_interval}秒")
        logger.info("=" * 60)
    
    def track_access(self, symbol: str, indicator: str) -> None:
        """
        追踪访问模式
        
        Args:
            symbol: 交易对
            indicator: 指标名称
        """
        # 记录symbol访问
        self.symbol_access_count[symbol] = self.symbol_access_count.get(symbol, 0) + 1
        self.recent_symbols.append(symbol)
        
        # 记录indicator访问
        self.indicator_access_count[indicator] = self.indicator_access_count.get(indicator, 0) + 1
    
    def get_top_symbols(self) -> List[str]:
        """
        获取访问频率最高的交易对
        
        Returns:
            Top N交易对列表
        """
        if not self.symbol_access_count:
            return []
        
        # 按访问次数排序
        sorted_symbols = sorted(
            self.symbol_access_count.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [symbol for symbol, _ in sorted_symbols[:self.top_n_symbols]]
    
    def get_top_indicators(self) -> List[str]:
        """
        获取访问频率最高的指标
        
        Returns:
            Top指标列表
        """
        if not self.indicator_access_count:
            # 默认预热常用指标
            return ['ema_20', 'ema_50', 'rsi_14', 'atr_14']
        
        # 按访问次数排序
        sorted_indicators = sorted(
            self.indicator_access_count.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [ind for ind, _ in sorted_indicators[:10]]
    
    async def preheat_symbol_indicators(
        self,
        symbol: str,
        klines_data: Dict,
        indicators: List[str]
    ) -> int:
        """
        预热单个交易对的指标
        
        Args:
            symbol: 交易对
            klines_data: K线数据字典
            indicators: 要预热的指标列表
        
        Returns:
            成功预热的指标数量
        """
        if not klines_data:
            return 0
        
        preheated = 0
        
        for indicator_spec in indicators:
            try:
                # 解析指标规格
                indicator, params = self.elite_engine._parse_indicator_spec(indicator_spec)
                
                # 选择合适的时间框架数据
                data = klines_data.get('15m') or klines_data.get('5m') or klines_data.get('1h')
                
                if data is None or (hasattr(data, 'empty') and data.empty):
                    continue
                
                # 计算指标（会自动缓存）
                self.elite_engine.calculate(indicator, data, **params)
                preheated += 1
                
            except Exception as e:
                logger.debug(f"预热指标失败 {symbol} {indicator_spec}: {e}")
        
        return preheated
    
    async def preheat_batch(
        self,
        symbols_data: Dict[str, Dict]
    ) -> None:
        """
        批量预热指标
        
        Args:
            symbols_data: {symbol: {timeframe: klines_data}}
        """
        start_time = time.time()
        
        # 获取Top交易对和指标
        top_symbols = self.get_top_symbols()
        top_indicators = self.get_top_indicators()
        
        if not top_symbols or not top_indicators:
            logger.debug("无足够访问数据，跳过预热")
            return
        
        # 过滤出需要预热的交易对
        symbols_to_preheat = [s for s in top_symbols if s in symbols_data]
        
        if not symbols_to_preheat:
            logger.debug("无可预热交易对")
            return
        
        logger.info(f"🔥 开始预热 {len(symbols_to_preheat)} 个交易对的 {len(top_indicators)} 个指标")
        
        # 并发预热
        tasks = []
        for symbol in symbols_to_preheat:
            task = self.preheat_symbol_indicators(
                symbol,
                symbols_data[symbol],
                top_indicators
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计
        total_preheated = sum(r for r in results if isinstance(r, int))
        duration = time.time() - start_time
        
        self.stats['preheat_rounds'] += 1
        self.stats['indicators_preheated'] += total_preheated
        self.stats['preheat_duration_total'] += duration
        self.stats['last_preheat_time'] = time.time()
        
        logger.info(
            f"✅ 预热完成: {total_preheated} 个指标 "
            f"耗时 {duration:.2f}s "
            f"(平均 {duration/max(1, len(symbols_to_preheat)):.3f}s/交易对)"
        )
    
    async def start_background_preheating(
        self,
        data_provider
    ) -> None:
        """
        启动后台预热任务
        
        Args:
            data_provider: 数据提供函数，返回 Dict[str, Dict]
        """
        self._running = True
        
        logger.info("🚀 后台预热任务已启动")
        
        while self._running:
            try:
                # 等待预热间隔
                await asyncio.sleep(self.preheat_interval)
                
                # 获取数据
                symbols_data = await data_provider()
                
                # 执行预热
                await self.preheat_batch(symbols_data)
                
            except Exception as e:
                logger.error(f"❌ 后台预热失败: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    def stop_background_preheating(self) -> None:
        """停止后台预热任务"""
        self._running = False
        logger.info("⏹️ 后台预热任务已停止")
    
    def get_stats(self) -> dict:
        """获取预热统计"""
        avg_duration = (
            self.stats['preheat_duration_total'] / max(1, self.stats['preheat_rounds'])
        )
        
        return {
            **self.stats,
            'avg_preheat_duration': avg_duration,
            'top_symbols_count': len(self.get_top_symbols()),
            'tracked_symbols_count': len(self.symbol_access_count)
        }
    
    def log_stats(self) -> None:
        """记录预热统计"""
        stats = self.get_stats()
        logger.info("📊 预热统计:")
        logger.info(f"   预热轮次: {stats['preheat_rounds']}")
        logger.info(f"   已预热指标: {stats['indicators_preheated']}")
        logger.info(f"   平均耗时: {stats['avg_preheat_duration']:.2f}s")
        logger.info(f"   追踪交易对: {stats['tracked_symbols_count']}")
