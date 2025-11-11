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
        
        🔥 v4.1+ Critical Fix: 正確調用 get_symbol_info() 並解析 Binance filters
        
        Args:
            symbol: 交易對符號
            
        Returns:
            交易對規格字典，包含：
            - min_quantity: 最小數量
            - step_size: 數量精度
            - min_notional: 最小名義價值
            - tick_size: 價格精度
        """
        # 檢查緩存
        if symbol in self._symbol_specs_cache:
            cache_age = time.time() - self._cache_timestamp.get(symbol, 0)
            if cache_age < self._cache_ttl:
                return self._symbol_specs_cache[symbol]
        
        # 從 Binance 獲取（如果有客戶端）
        if self.binance_client:
            try:
                # 🔥 Critical Fix: 使用 get_symbol_info(symbol) 而非 get_exchange_info(symbol)
                symbol_info = await self.binance_client.get_symbol_info(symbol)
                
                if symbol_info:
                    # ✅ 解析 Binance filters
                    specs = self._parse_symbol_filters(symbol_info)
                    
                    # 緩存結果
                    self._symbol_specs_cache[symbol] = specs
                    self._cache_timestamp[symbol] = time.time()
                    
                    logger.debug(
                        f"✅ 已獲取 {symbol} 規格: "
                        f"minQty={specs['min_quantity']}, "
                        f"stepSize={specs['step_size']}, "
                        f"minNotional={specs['min_notional']}"
                    )
                    return specs
                    
            except Exception as e:
                logger.warning(f"⚠️ 獲取 {symbol} 交易對規格失敗: {e}")
        
        # 使用默認值（保守估計）
        default_specs = {
            "min_quantity": 0.001,
            "step_size": 0.001,
            "min_notional": 10.0,
            "tick_size": 0.01,
        }
        logger.warning(
            f"⚠️ 使用默認規格（可能不準確）: {symbol} → {default_specs}"
        )
        return default_specs
    
    def _parse_symbol_filters(self, symbol_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        🔥 v4.1+ 解析 Binance symbol filters
        
        Args:
            symbol_info: Binance exchangeInfo 中的 symbol 信息
            
        Returns:
            解析後的規格字典
        """
        specs = {
            "min_quantity": 0.001,
            "step_size": 0.001,
            "min_notional": 10.0,
            "tick_size": 0.01,
        }
        
        filters = symbol_info.get('filters', [])
        
        for f in filters:
            filter_type = f.get('filterType')
            
            # LOT_SIZE: 數量過濾器
            if filter_type == 'LOT_SIZE':
                specs['min_quantity'] = float(f.get('minQty', 0.001))
                specs['step_size'] = float(f.get('stepSize', 0.001))
            
            # MARKET_LOT_SIZE: 市價單數量過濾器（優先級更高）
            elif filter_type == 'MARKET_LOT_SIZE':
                specs['min_quantity'] = max(
                    specs['min_quantity'], 
                    float(f.get('minQty', 0.001))
                )
                specs['step_size'] = max(
                    specs['step_size'], 
                    float(f.get('stepSize', 0.001))
                )
            
            # MIN_NOTIONAL: 最小名義價值
            elif filter_type == 'MIN_NOTIONAL':
                specs['min_notional'] = float(f.get('notional', 10.0))
            
            # PRICE_FILTER: 價格過濾器
            elif filter_type == 'PRICE_FILTER':
                specs['tick_size'] = float(f.get('tickSize', 0.01))
        
        return specs
    
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
        計算倉位數量（異步版本）- v3.18+ 硬性上限50%帳戶權益
        
        Args:
            account_equity: 賬戶權益（USDT）
            entry_price: 入場價格
            stop_loss: 止損價格
            leverage: 槓桿倍數（無上限，最小0.5x）
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
        
        # 🔥 v3.18+ 新增：強制50%帳戶權益硬性上限（唯一限制）
        max_notional = account_equity * 0.50  # 單倉不得超過50%帳戶總權益
        
        # 3. 先獲取Binance規格以檢查最小值
        specs = await self.get_symbol_specs(symbol)
        min_notional = specs.get("min_notional", 10.0) if specs else 10.0
        
        # 🔥 關鍵檢查：如果50%上限低於Binance最小值，拒絕下單
        if max_notional < min_notional:
            error_msg = (
                f"❌ 帳戶權益過低無法開倉！"
                f"50%上限=${max_notional:.2f} < Binance最小倉位${min_notional:.2f} | "
                f"需要至少${min_notional * 2:.2f} USDT帳戶權益"
            )
            logger.error(error_msg)
            # 返回0表示無法開倉（調用方應檢查並跳過）
            return 0, adjusted_sl
        
        # 4. 應用50%上限
        original_notional = notional
        if notional > max_notional:
            notional = max_notional
            if verbose:
                logger.info(f"🚨 倉位價值超限：${original_notional:.2f} → ${notional:.2f} (50%上限)")
        
        # 5. 計算倉位數量
        position_size = notional / entry_price
        
        # 6. 應用Binance過濾器（但不允許超過50%上限）
        if specs:
            original_position_size = position_size
            position_size = self._apply_binance_filters_with_cap(
                position_size, entry_price, specs, max_notional
            )
            
            # 如果Binance過濾器要求的最小倉位超過50%上限，拒絕下單
            if position_size <= 0:
                error_msg = (
                    f"❌ 50%上限與Binance最小倉位衝突！"
                    f"上限=${max_notional:.2f} 但最小倉位需${min_notional:.2f}"
                )
                logger.error(error_msg)
                return 0, adjusted_sl
        
        if verbose:
            logger.debug(f"倉位計算詳情:")
            logger.debug(f"  權益: ${account_equity:.2f} × {self.config.equity_usage_ratio:.1%} = ${margin:.2f}")
            logger.debug(f"  槓桿: {leverage:.2f}x → 名義價值: ${notional:.2f}")
            logger.debug(f"  🔒 50%上限: ${max_notional:.2f} (帳戶總權益的唯一硬性限制)")
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
        應用 Binance 交易對過濾器（舊版本，保留兼容性）
        
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
    
    def _apply_binance_filters_with_cap(
        self, 
        position_size: float, 
        entry_price: float,
        specs: Dict[str, Any],
        max_notional: float
    ) -> float:
        """
        應用Binance過濾器 + 50%上限檢查（v3.18+）
        
        Args:
            position_size: 原始倉位數量
            entry_price: 入場價格
            specs: 交易對規格
            max_notional: 最大名義價值（50%上限）
            
        Returns:
            調整後的倉位數量，如果無法滿足Binance+上限要求則返回0
        """
        min_qty = specs.get("min_quantity", 0.001)
        step_size = specs.get("step_size", 0.001)
        min_notional = specs.get("min_notional", 10.0)
        
        # 1. 確保符合數量精度
        position_size = round(position_size / step_size) * step_size
        
        # 2. 確保數量 ≥ 最小數量
        if position_size < min_qty:
            position_size = min_qty
        
        # 3. 檢查最小名義價值
        notional_value = position_size * entry_price
        if notional_value < min_notional:
            required_qty = min_notional / entry_price
            position_size = round(required_qty / step_size) * step_size
            notional_value = position_size * entry_price
        
        # 4. 關鍵檢查：Binance最小值是否超過50%上限
        if notional_value > max_notional:
            logger.warning(
                f"⚠️ Binance最小倉位${notional_value:.2f} > 50%上限${max_notional:.2f}，"
                f"無法開倉（帳戶權益過低）"
            )
            return 0  # 返回0表示無法開倉
        
        # 5. 確保 ≥ 系統配置的最小名義價值（但不超過上限）
        if notional_value < self.config.min_notional_value:
            required_qty = self.config.min_notional_value / entry_price
            position_size = round(required_qty / step_size) * step_size
            notional_value = position_size * entry_price
            
            if notional_value > max_notional:
                logger.warning(
                    f"⚠️ 系統最小倉位${notional_value:.2f} > 50%上限${max_notional:.2f}"
                )
                return 0
        
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
