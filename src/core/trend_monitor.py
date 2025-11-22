"""
v3.17+ 實時趨勢監控器
每 30 秒更新市場狀態，觸發信號重評估
"""

import asyncio
from src.utils.logger_factory import get_logger
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import numpy as np

logger = get_logger(__name__)


class TrendState(Enum):
    """市場趨勢狀態"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    CHOPPY = "choppy"


class TrendMonitor:
    """
    實時趨勢監控器（v3.17+）
    
    職責：
    1. 每 30 秒更新市場趨勢狀態
    2. 使用雙時間框架 ADX（15m + 1h）
    3. 計算價格 vs EMA20 斜率
    4. LSTM 輕量版預測趨勢持續性
    5. 觸發 SelfLearningTrader 重新評估信號
    """
    
    def __init__(
        self,
        binance_client=None,
        config_profile=None,
        signal_callback=None
    ):
        """
        初始化趨勢監控器
        
        Args:
            binance_client: BinanceClient 實例（可選）
            config_profile: config manager instance（可選）
            signal_callback: 信號重評估回調函數（可選）
        """
        self.binance = binance_client
        self.config = config_profile
        self.signal_callback = signal_callback
        
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # 監控配置
        self.update_interval = int(
            self.config.cycle_interval if self.config else 30
        )
        self.symbols_to_monitor: List[str] = []
        
        # 趨勢狀態緩存
        self.trend_states: Dict[str, Dict] = {}
        
        # 統計數據
        self.total_updates = 0
        self.last_update_time: Optional[datetime] = None
        
        logger.info("=" * 60)
        logger.info("✅ 實時趨勢監控器初始化完成（v3.17+）")
        logger.info(f"   ⏱️  更新間隔: {self.update_interval} 秒")
        logger.info(f"   📊 監控技術: 雙時間框架 ADX + EMA 斜率 + LSTM")
        logger.info("=" * 60)
    
    async def start(self, symbols: List[str]):
        """
        啟動趨勢監控器
        
        Args:
            symbols: 要監控的交易對列表
        """
        if self.is_running:
            logger.warning("⚠️ 趨勢監控器已在運行")
            return
        
        self.symbols_to_monitor = symbols
        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info(f"🚀 趨勢監控器已啟動，監控 {len(symbols)} 個交易對")
    
    async def stop(self):
        """停止趨勢監控器"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info(
            f"⏸️  趨勢監控器已停止 "
            f"(總更新: {self.total_updates}, 監控交易對: {len(self.symbols_to_monitor)})"
        )
    
    async def _monitor_loop(self):
        """主監控循環"""
        logger.info("🔄 開始趨勢監控循環...")
        
        while self.is_running:
            try:
                # 更新所有交易對的趨勢狀態
                await self._update_all_trends()
                
                # 更新統計
                self.total_updates += 1
                self.last_update_time = datetime.now()
                
                # 觸發信號重評估（若有回調）
                if self.signal_callback:
                    await self.signal_callback(self.trend_states)
                
                # 等待下一次更新
                await asyncio.sleep(self.update_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 趨勢監控循環錯誤: {e}", exc_info=True)
                await asyncio.sleep(self.update_interval)
    
    async def _update_all_trends(self):
        """更新所有交易對的趨勢狀態"""
        if not self.binance:
            return
        
        logger.debug(f"📊 更新 {len(self.symbols_to_monitor)} 個交易對的趨勢狀態...")
        
        # 並行更新所有交易對
        tasks = [
            self._update_single_trend(symbol)
            for symbol in self.symbols_to_monitor
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _update_single_trend(self, symbol: str):
        """
        更新單個交易對的趨勢狀態
        
        Args:
            symbol: 交易對符號
        """
        try:
            # 1. 獲取雙時間框架數據
            data_15m = await self._get_klines(symbol, '15m', limit=100)
            data_1h = await self._get_klines(symbol, '1h', limit=100)
            
            if not data_15m or not data_1h:
                return
            
            # 2. 計算雙時間框架 ADX
            adx_15m = self._calculate_adx(data_15m)
            adx_1h = self._calculate_adx(data_1h)
            
            # 3. 計算 EMA 斜率
            ema_slope = self._calculate_ema_slope(data_15m)
            
            # 4. 預測趨勢持續性（LSTM 輕量版）
            continuation_prob = self._predict_continuation(data_15m, data_1h)
            
            # 5. 綜合判斷趨勢狀態
            trend_state = self._determine_trend_state(adx_15m, adx_1h, ema_slope)
            
            # 6. 計算趨勢強度
            trend_strength = self._calculate_trend_strength(adx_15m, adx_1h, ema_slope)
            
            # 7. 更新緩存
            self.trend_states[symbol] = {
                'state': trend_state,
                'strength': trend_strength,
                'continuation_prob': continuation_prob,
                'adx_15m': adx_15m,
                'adx_1h': adx_1h,
                'ema_slope': ema_slope,
                'updated_at': datetime.now().isoformat(),
            }
            
            logger.debug(
                f"📊 {symbol}: {trend_state.value}, "
                f"強度={trend_strength:.2f}, 持續性={continuation_prob:.2f}"
            )
            
        except Exception as e:
            logger.error(f"❌ {symbol} 更新趨勢失敗: {e}")
    
    async def _get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int
    ) -> Optional[np.ndarray]:
        """獲取 K 線數據"""
        try:
            if self.binance is None:
                return None
            
            klines = await self.binance.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            if not klines:
                return None
            
            # 提取收盤價、最高價、最低價
            closes = np.array([float(k['close']) for k in klines])
            highs = np.array([float(k['high']) for k in klines])
            lows = np.array([float(k['low']) for k in klines])
            
            return np.column_stack([closes, highs, lows])
            
        except Exception as e:
            logger.error(f"❌ {symbol} 獲取 K 線失敗 ({interval}): {e}")
            return None
    
    def _calculate_adx(self, data: np.ndarray, period: int = 14) -> float:
        """
        計算 ADX（平均趨向指標）
        
        Args:
            data: K 線數據 [close, high, low]
            period: 週期
            
        Returns:
            ADX 值（0-100）
        """
        try:
            closes = data[:, 0]
            highs = data[:, 1]
            lows = data[:, 2]
            
            # 計算 +DM 和 -DM
            high_diff = np.diff(highs)
            low_diff = -np.diff(lows)
            
            plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
            minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
            
            # 計算 TR（真實波幅）
            tr1 = highs[1:] - lows[1:]
            tr2 = np.abs(highs[1:] - closes[:-1])
            tr3 = np.abs(lows[1:] - closes[:-1])
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            
            # 平滑 +DM, -DM, TR
            atr = self._smooth(tr, period)
            plus_di = 100 * self._smooth(plus_dm, period) / atr
            minus_di = 100 * self._smooth(minus_dm, period) / atr
            
            # 計算 DX
            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
            
            # 計算 ADX
            adx = self._smooth(dx, period)
            
            return float(adx[-1]) if len(adx) > 0 else 0.0
            
        except Exception as e:
            logger.error(f"❌ 計算 ADX 失敗: {e}")
            return 0.0
    
    def _smooth(self, data: np.ndarray, period: int) -> np.ndarray:
        """平滑數據（EMA）"""
        alpha = 2 / (period + 1)
        smoothed = np.zeros_like(data)
        smoothed[0] = data[0]
        
        for i in range(1, len(data)):
            smoothed[i] = alpha * data[i] + (1 - alpha) * smoothed[i - 1]
        
        return smoothed
    
    def _calculate_ema_slope(self, data: np.ndarray, period: int = 20) -> float:
        """
        計算 EMA 斜率（趨勢方向指標）
        
        Args:
            data: K 線數據
            period: EMA 週期
            
        Returns:
            斜率值（正=上漲，負=下跌）
        """
        try:
            closes = data[:, 0]
            
            # 計算 EMA
            ema = self._calculate_ema(closes, period)
            
            # 計算最近 10 根 K 線的斜率
            recent_ema = ema[-10:]
            slope = (recent_ema[-1] - recent_ema[0]) / len(recent_ema)
            
            # 標準化（相對於價格）
            normalized_slope = slope / closes[-1]
            
            return float(normalized_slope)
            
        except Exception as e:
            logger.error(f"❌ 計算 EMA 斜率失敗: {e}")
            return 0.0
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """計算 EMA"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
        
        return ema
    
    def _predict_continuation(
        self,
        data_15m: np.ndarray,
        data_1h: np.ndarray
    ) -> float:
        """
        預測趨勢持續性（LSTM 輕量版）
        
        由於完整 LSTM 需要 TensorFlow（已移除），這裡使用簡化版本：
        - 動量指標
        - 波動率趨勢
        - 多時間框架一致性
        
        Args:
            data_15m: 15 分鐘 K 線
            data_1h: 1 小時 K 線
            
        Returns:
            持續性概率（0-1）
        """
        try:
            # 1. 計算動量（最近 vs 更早）
            closes_15m = data_15m[:, 0]
            momentum_15m = (closes_15m[-1] - closes_15m[-20]) / closes_15m[-20]
            
            closes_1h = data_1h[:, 0]
            momentum_1h = (closes_1h[-1] - closes_1h[-10]) / closes_1h[-10]
            
            # 2. 計算波動率趨勢
            volatility_15m = np.std(np.diff(closes_15m[-20:])) / closes_15m[-1]
            volatility_1h = np.std(np.diff(closes_1h[-10:])) / closes_1h[-1]
            
            # 3. 多時間框架一致性
            direction_consistent = (momentum_15m * momentum_1h) > 0
            
            # 4. 綜合評分
            score = 0.5  # 基準
            
            # 動量強度加分
            if abs(momentum_15m) > 0.01:
                score += 0.2
            if abs(momentum_1h) > 0.02:
                score += 0.2
            
            # 一致性加分
            if direction_consistent:
                score += 0.2
            
            # 低波動率加分（趨勢穩定）
            if volatility_15m < 0.02:
                score += 0.1
            
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"❌ 預測持續性失敗: {e}")
            return 0.5
    
    def _determine_trend_state(
        self,
        adx_15m: float,
        adx_1h: float,
        ema_slope: float
    ) -> TrendState:
        """
        判斷趨勢狀態
        
        Args:
            adx_15m: 15 分鐘 ADX
            adx_1h: 1 小時 ADX
            ema_slope: EMA 斜率
            
        Returns:
            趨勢狀態
        """
        # ADX 閾值
        ADX_TRENDING = 25.0
        ADX_RANGING = 20.0
        
        # 判斷邏輯
        avg_adx = (adx_15m + adx_1h) / 2
        
        if avg_adx >= ADX_TRENDING:
            # 強趨勢
            if ema_slope > 0.0001:
                return TrendState.TRENDING_UP
            elif ema_slope < -0.0001:
                return TrendState.TRENDING_DOWN
            else:
                return TrendState.CHOPPY
        elif avg_adx >= ADX_RANGING:
            # 弱趨勢/震盪
            return TrendState.RANGING
        else:
            # 無趨勢/震盪
            return TrendState.CHOPPY
    
    def _calculate_trend_strength(
        self,
        adx_15m: float,
        adx_1h: float,
        ema_slope: float
    ) -> float:
        """
        計算趨勢強度（0-1）
        
        Args:
            adx_15m: 15 分鐘 ADX
            adx_1h: 1 小時 ADX
            ema_slope: EMA 斜率
            
        Returns:
            趨勢強度（0-1）
        """
        # ADX 貢獻（0-0.6）
        avg_adx = (adx_15m + adx_1h) / 2
        adx_score = min(0.6, avg_adx / 50.0)
        
        # 斜率貢獻（0-0.4）
        slope_score = min(0.4, abs(ema_slope) * 1000)
        
        total_score = adx_score + slope_score
        
        return min(1.0, total_score)
    
    def get_trend_state(self, symbol: str) -> Optional[Dict]:
        """
        獲取交易對的趨勢狀態
        
        Args:
            symbol: 交易對符號
            
        Returns:
            趨勢狀態字典
        """
        return self.trend_states.get(symbol)
    
    def get_all_trending_symbols(self, min_strength: float = 0.5) -> List[str]:
        """
        獲取所有強趨勢交易對
        
        Args:
            min_strength: 最小趨勢強度
            
        Returns:
            交易對列表
        """
        trending_symbols = []
        
        for symbol, state in self.trend_states.items():
            if (state['state'] in [TrendState.TRENDING_UP, TrendState.TRENDING_DOWN] and
                state['strength'] >= min_strength):
                trending_symbols.append(symbol)
        
        return trending_symbols
