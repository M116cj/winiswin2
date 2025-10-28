"""
v3.17+ 倉位計算器
計算倉位數量，並確保符合 Binance 交易對規格
"""

import logging
import time
from typing import Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)


class PositionSizer:
    """
    倉位計算器（v3.17+）
    
    職責：
    1. 根據槓桿、權益、止損計算倉位數量
    2. 確保符合 Binance 最小數量/名義價值
    3. 自動調整止損距離（≥0.3%）
    """
    
    def __init__(self, config_profile, binance_client=None):
        """
        初始化倉位計算器
        
        Args:
            config_profile: ConfigProfile 實例
            binance_client: BinanceClient 實例（可選，用於獲取交易對規格）
        """
        self.config = config_profile
        self.binance_client = binance_client
        
        # 交易對規格緩存（避免頻繁 API 調用）
        self._symbol_specs_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 3600  # 1小時
        self._cache_timestamp: Dict[str, float] = {}
        
        logger.info("✅ 倉位計算器初始化完成（v3.17+）")
        logger.info(f"   📊 權益使用率: {self.config.equity_usage_ratio:.1%}")
        logger.info(f"   📊 最小名義價值: ${self.config.min_notional_value:.2f}")
        logger.info(f"   📊 最小止損距離: {self.config.min_stop_distance_pct:.2%}")
    
    async def get_symbol_specs(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        獲取交易對規格（帶緩存）
        
        Args:
            symbol: 交易對符號
            
        Returns:
            交易對規格字典，包含：
            - min_quantity: 最小數量
            - step_size: 數量精度
            - min_notional: 最小名義價值
        """
        # 檢查緩存
        if symbol in self._symbol_specs_cache:
            cache_age = time.time() - self._cache_timestamp.get(symbol, 0)
            if cache_age < self._cache_ttl:
                return self._symbol_specs_cache[symbol]
        
        # 從 Binance 獲取（如果有客戶端）
        if self.binance_client:
            try:
                specs = await self.binance_client.get_exchange_info(symbol)
                if specs:
                    self._symbol_specs_cache[symbol] = specs
                    self._cache_timestamp[symbol] = time.time()
                    return specs
            except Exception as e:
                logger.warning(f"獲取 {symbol} 交易對規格失敗: {e}")
        
        # 使用默認值（保守估計）
        default_specs = {
            "min_quantity": 0.001,
            "step_size": 0.001,
            "min_notional": 10.0,
        }
        logger.debug(f"使用默認規格: {symbol} → {default_specs}")
        return default_specs
    
    def calculate_position_size(
        self,
        account_equity: float,
        entry_price: float,
        stop_loss: float,
        leverage: float,
        symbol: str = "BTCUSDT",
        verbose: bool = False
    ) -> tuple[float, float]:
        """
        計算倉位數量（同步版本）
        
        Args:
            account_equity: 賬戶權益（USDT）
            entry_price: 入場價格
            stop_loss: 止損價格
            leverage: 槓桿倍數
            symbol: 交易對符號
            verbose: 是否輸出詳細計算過程
            
        Returns:
            (position_size, adjusted_stop_loss)
        """
        # 使用事件循環執行異步版本
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.calculate_position_size_async(
                account_equity, entry_price, stop_loss, leverage, symbol, verbose
            )
        )
    
    async def calculate_position_size_async(
        self,
        account_equity: float,
        entry_price: float,
        stop_loss: float,
        leverage: float,
        symbol: str = "BTCUSDT",
        verbose: bool = False
    ) -> tuple[float, float]:
        """
        計算倉位數量（異步版本）
        
        Args:
            account_equity: 賬戶權益（USDT）
            entry_price: 入場價格
            stop_loss: 止損價格
            leverage: 槓桿倍數
            symbol: 交易對符號
            verbose: 是否輸出詳細計算過程
            
        Returns:
            (position_size, adjusted_stop_loss)
        """
        # 1. 調整止損距離（確保 ≥ 0.3%）
        adjusted_sl = self._adjust_stop_loss(entry_price, stop_loss)
        
        # 2. 計算保證金和名義價值
        margin = account_equity * self.config.equity_usage_ratio
        notional = leverage * margin
        
        # 3. 計算倉位數量
        position_size = notional / entry_price
        
        # 4. 確保符合 Binance 規格
        specs = await self.get_symbol_specs(symbol)
        if specs:
            position_size = self._apply_binance_filters(
                position_size, entry_price, specs
            )
        
        if verbose:
            logger.debug(f"倉位計算詳情:")
            logger.debug(f"  權益: ${account_equity:.2f} × {self.config.equity_usage_ratio:.1%} = ${margin:.2f}")
            logger.debug(f"  槓桿: {leverage:.2f}x → 名義價值: ${notional:.2f}")
            logger.debug(f"  入場價: ${entry_price:.2f} → 倉位數量: {position_size:.6f}")
            logger.debug(f"  止損: ${stop_loss:.2f} → 調整後: ${adjusted_sl:.2f} ({abs(entry_price-adjusted_sl)/entry_price:.2%})")
        
        return position_size, adjusted_sl
    
    def _adjust_stop_loss(self, entry_price: float, stop_loss: float) -> float:
        """
        調整止損距離（確保 ≥ 0.3%）
        
        Args:
            entry_price: 入場價格
            stop_loss: 原始止損價格
            
        Returns:
            調整後的止損價格
        """
        current_distance_pct = abs(entry_price - stop_loss) / entry_price
        
        if current_distance_pct < self.config.min_stop_distance_pct:
            # 自動調整止損距離
            direction = 1 if entry_price > stop_loss else -1
            adjusted_sl = entry_price * (1 - direction * self.config.min_stop_distance_pct)
            
            logger.debug(
                f"止損距離過小 ({current_distance_pct:.3%}), "
                f"自動調整: ${stop_loss:.2f} → ${adjusted_sl:.2f}"
            )
            return adjusted_sl
        
        return stop_loss
    
    def _apply_binance_filters(
        self, 
        position_size: float, 
        entry_price: float,
        specs: Dict[str, Any]
    ) -> float:
        """
        應用 Binance 交易對過濾器
        
        Args:
            position_size: 原始倉位數量
            entry_price: 入場價格
            specs: 交易對規格
            
        Returns:
            調整後的倉位數量
        """
        min_qty = specs.get("min_quantity", 0.001)
        step_size = specs.get("step_size", 0.001)
        min_notional = specs.get("min_notional", 10.0)
        
        # 1. 確保數量 ≥ 最小數量
        if position_size < min_qty:
            logger.debug(f"倉位數量 {position_size:.6f} < {min_qty:.6f}，調整到最小值")
            position_size = min_qty
        
        # 2. 確保符合數量精度
        position_size = round(position_size / step_size) * step_size
        
        # 3. 確保名義價值 ≥ 最小名義價值
        notional_value = position_size * entry_price
        if notional_value < min_notional:
            required_qty = min_notional / entry_price
            logger.debug(
                f"名義價值 ${notional_value:.2f} < ${min_notional:.2f}, "
                f"調整數量: {position_size:.6f} → {required_qty:.6f}"
            )
            position_size = round(required_qty / step_size) * step_size
        
        # 4. 確保 ≥ 系統配置的最小名義價值
        final_notional = position_size * entry_price
        if final_notional < self.config.min_notional_value:
            required_qty = self.config.min_notional_value / entry_price
            position_size = round(required_qty / step_size) * step_size
            logger.debug(
                f"最終倉位: {position_size:.6f} (名義價值: ${position_size * entry_price:.2f})"
            )
        
        return position_size
    
    def get_position_summary(self, position_size: float, entry_price: float, leverage: float) -> dict:
        """
        獲取倉位摘要信息
        
        Args:
            position_size: 倉位數量
            entry_price: 入場價格
            leverage: 槓桿倍數
            
        Returns:
            倉位摘要字典
        """
        notional_value = position_size * entry_price
        margin_required = notional_value / leverage
        
        return {
            "position_size": f"{position_size:.6f}",
            "entry_price": f"${entry_price:.2f}",
            "notional_value": f"${notional_value:.2f}",
            "leverage": f"{leverage:.2f}x",
            "margin_required": f"${margin_required:.2f}",
        }
