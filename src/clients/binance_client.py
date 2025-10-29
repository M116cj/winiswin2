"""
Binance API 客戶端（v3.9.2.2增強版）
職責：API 調用、認證、錯誤處理、統一API管理、重試元數據
"""

import asyncio
import aiohttp
import hmac
import hashlib
import time
from typing import Optional, Any
import logging

from src.config import Config
from src.core.rate_limiter import RateLimiter
from src.core.circuit_breaker import CircuitBreaker, GradedCircuitBreaker, Priority
from src.core.cache_manager import CacheManager
from src.clients.binance_errors import BinanceRequestError

logger = logging.getLogger(__name__)

class BinanceClient:
    """Binance USDT 永續合約 API 客戶端"""
    
    def __init__(self):
        self.api_key = Config.BINANCE_API_KEY
        self.api_secret = Config.BINANCE_API_SECRET
        
        if Config.BINANCE_TESTNET:
            self.base_url = "https://testnet.binancefuture.com"
        else:
            self.base_url = "https://fapi.binance.com"
        
        self.rate_limiter = RateLimiter(
            max_requests=Config.RATE_LIMIT_REQUESTS,
            time_window=Config.RATE_LIMIT_PERIOD
        )
        
        if Config.GRADED_CIRCUIT_BREAKER_ENABLED:
            self.circuit_breaker = GradedCircuitBreaker(
                warning_threshold=Config.CIRCUIT_BREAKER_WARNING_THRESHOLD,
                throttled_threshold=Config.CIRCUIT_BREAKER_THROTTLED_THRESHOLD,
                blocked_threshold=Config.CIRCUIT_BREAKER_BLOCKED_THRESHOLD,
                timeout=Config.CIRCUIT_BREAKER_TIMEOUT,
                throttle_delay=Config.CIRCUIT_BREAKER_THROTTLE_DELAY,
                bypass_whitelist=Config.CIRCUIT_BREAKER_BYPASS_OPERATIONS
            )
            logger.info("✅ 使用分級熔斷器 (GradedCircuitBreaker)")
        else:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=Config.CIRCUIT_BREAKER_THRESHOLD,
                timeout=Config.CIRCUIT_BREAKER_TIMEOUT
            )
            logger.info("✅ 使用傳統熔斷器 (CircuitBreaker)")
        
        self.cache = CacheManager()
        self.session: Optional[aiohttp.ClientSession] = None
        self._hedge_mode = None  # None = 未檢測，True = Hedge Mode，False = One-Way Mode
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """獲取或創建 aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def _generate_signature(self, params: dict) -> str:
        """
        生成請求簽名
        
        Args:
            params: 請求參數
        
        Returns:
            簽名字符串
        """
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        signed: bool = False
    ) -> Any:
        """
        執行 API 請求
        
        Args:
            method: HTTP 方法
            endpoint: API 端點
            params: 請求參數
            signed: 是否需要簽名
        
        Returns:
            API 響應
        """
        await self.rate_limiter.acquire()
        
        async def _do_request():
            if params is None:
                _params = {}
            else:
                _params = params.copy()
            
            headers = {'X-MBX-APIKEY': self.api_key} if self.api_key else {}
            
            if signed:
                # 添加時間戳
                _params['timestamp'] = int(time.time() * 1000)
                # 計算簽名（不包含 signature 本身）
                signature = self._generate_signature(_params)
                # 構建排序後的 query string（用於簽名計算）
                query_string = "&".join([f"{k}={v}" for k, v in sorted(_params.items())])
                # 簽名必須附加在最後
                query_string = f"{query_string}&signature={signature}"
            else:
                # 無需簽名時直接構建 query string
                query_string = "&".join([f"{k}={v}" for k, v in sorted(_params.items())])
            
            # 將 query string 附加到 URL（所有請求類型都使用 query string）
            url = f"{self.base_url}{endpoint}"
            if query_string:
                url = f"{url}?{query_string}"
            
            session = await self._get_session()
            
            # 所有請求都直接使用帶參數的 URL（確保順序與簽名一致）
            if method.upper() in ["POST", "DELETE"]:
                async with session.request(method, url, headers=headers) as response:
                    if response.status != 200:
                        # 獲取錯誤響應體
                        error_text = await response.text()
                        try:
                            error_json = await response.json()
                            error_msg = error_json.get('msg', error_text)
                            error_code = error_json.get('code', 'N/A')
                            
                            # 特殊處理：HTTP 451 地理位置限制
                            if response.status == 451:
                                logger.error(
                                    f"Binance API 錯誤 {response.status}: "
                                    f"code={error_code}, msg={error_msg}, "
                                    f"endpoint={endpoint}, params={_params}"
                                )
                                logger.error(
                                    "❌ Binance API 地理位置限制 (HTTP 451)\n"
                                    "📍 此錯誤表示當前IP地址被Binance限制\n"
                                    "✅ 解決方案：請將系統部署到Railway或其他支持的雲平台\n"
                                    "⚠️  Replit環境無法訪問Binance API"
                                )
                            else:
                                logger.error(
                                    f"Binance API 錯誤 {response.status}: "
                                    f"code={error_code}, msg={error_msg}, "
                                    f"endpoint={endpoint}, params={_params}"
                                )
                        except:
                            logger.error(f"Binance API 錯誤 {response.status}: {error_text}")
                        response.raise_for_status()
                    return await response.json()
            else:
                # GET 請求也使用帶參數的 URL
                async with session.request(method, url, headers=headers) as response:
                    if response.status != 200:
                        # 獲取錯誤響應體
                        error_text = await response.text()
                        try:
                            error_json = await response.json()
                            error_msg = error_json.get('msg', error_text)
                            error_code = error_json.get('code', 'N/A')
                            
                            # 特殊處理：HTTP 451 地理位置限制
                            if response.status == 451:
                                logger.error(
                                    f"Binance API 錯誤 {response.status}: "
                                    f"code={error_code}, msg={error_msg}, "
                                    f"endpoint={endpoint}, params={_params}"
                                )
                                logger.error(
                                    "❌ Binance API 地理位置限制 (HTTP 451)\n"
                                    "📍 此錯誤表示當前IP地址被Binance限制\n"
                                    "✅ 解決方案：請將系統部署到Railway或其他支持的雲平台\n"
                                    "⚠️  Replit環境無法訪問Binance API"
                                )
                            else:
                                logger.error(
                                    f"Binance API 錯誤 {response.status}: "
                                    f"code={error_code}, msg={error_msg}, "
                                    f"endpoint={endpoint}, params={_params}"
                                )
                        except:
                            logger.error(f"Binance API 錯誤 {response.status}: {error_text}")
                        response.raise_for_status()
                    return await response.json()
        
        try:
            result = await self.circuit_breaker.call_async(_do_request)
            return result
        except aiohttp.ClientResponseError as e:
            logger.error(f"API 請求失敗: {endpoint} - HTTP {e.status}: {e.message}")
            raise BinanceRequestError(
                message=f"HTTP {e.status}: {e.message}",
                endpoint=endpoint,
                original_error=e
            )
        except Exception as e:
            error_message = str(e)
            logger.error(f"API 請求失敗: {endpoint} - {error_message}")
            
            retry_after = BinanceRequestError.parse_retry_after(error_message)
            is_circuit_error = "熔斷器開啟" in error_message
            
            raise BinanceRequestError(
                message=error_message,
                endpoint=endpoint,
                retry_after_seconds=retry_after,
                is_circuit_breaker_error=is_circuit_error,
                original_error=e
            )
    
    async def get_exchange_info(self) -> dict:
        """獲取交易所信息"""
        cache_key = "exchange_info"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        result = await self._request("GET", "/fapi/v1/exchangeInfo")
        self.cache.set(cache_key, result, ttl=3600)
        return result
    
    async def get_all_usdt_symbols(self) -> list[str]:
        """獲取所有 USDT 永續合約交易對"""
        exchange_info = await self.get_exchange_info()
        symbols = [
            symbol['symbol']
            for symbol in exchange_info.get('symbols', [])
            if symbol.get('quoteAsset') == 'USDT' and symbol.get('status') == 'TRADING'
        ]
        logger.info(f"獲取到 {len(symbols)} 個 USDT 永續合約")
        return symbols
    
    async def get_symbol_info(self, symbol: str) -> Optional[dict]:
        """
        獲取交易對詳細信息
        
        Args:
            symbol: 交易對符號
        
        Returns:
            交易對信息字典，包含 filters 等
        """
        exchange_info = await self.get_exchange_info()
        for sym in exchange_info.get('symbols', []):
            if sym['symbol'] == symbol:
                return sym
        return None
    
    async def get_min_quantity(self, symbol: str) -> float:
        """
        獲取交易對最小數量
        
        Args:
            symbol: 交易對符號
        
        Returns:
            最小數量
        """
        symbol_info = await self.get_symbol_info(symbol)
        if not symbol_info:
            return 0.0
        
        # 從 LOT_SIZE filter 獲取 minQty
        for f in symbol_info.get('filters', []):
            if f.get('filterType') == 'LOT_SIZE':
                return float(f.get('minQty', 0.0))
        
        return 0.0
    
    def _format_quantity(self, quantity: float, step_size: float) -> float:
        """
        根據 stepSize 格式化數量（符合 Binance FUTURES LOT_SIZE 規則）
        使用 Decimal 向下取整避免精度超出
        
        Args:
            quantity: 原始數量
            step_size: 步進大小
        
        Returns:
            格式化後的數量（向下取整到 stepSize 倍數）
        """
        from decimal import Decimal, ROUND_DOWN
        import math
        
        if step_size == 0:
            return quantity
        
        # 轉換為 Decimal 避免浮點數精度問題
        qty_decimal = Decimal(str(quantity))
        step_decimal = Decimal(str(step_size))
        
        # 向下取整到 stepSize 的倍數（floor）
        steps = int(qty_decimal / step_decimal)
        formatted_decimal = step_decimal * Decimal(steps)
        
        # 計算精度（小數位數）
        precision = int(round(-math.log(step_size, 10), 0))
        if precision < 0:
            precision = 0
        
        # 量化到正確精度（向下取整）
        quantize_str = '0.' + '0' * precision if precision > 0 else '1'
        formatted_decimal = formatted_decimal.quantize(Decimal(quantize_str), rounding=ROUND_DOWN)
        
        return float(formatted_decimal)
    
    async def format_quantity(self, symbol: str, quantity: float) -> float:
        """
        根據交易對規則格式化數量
        
        Args:
            symbol: 交易對符號
            quantity: 原始數量
        
        Returns:
            格式化後的數量
        """
        symbol_info = await self.get_symbol_info(symbol)
        if not symbol_info:
            return quantity
        
        # 獲取 LOT_SIZE filter
        for f in symbol_info.get('filters', []):
            if f.get('filterType') == 'LOT_SIZE':
                step_size = float(f.get('stepSize', 0))
                return self._format_quantity(quantity, step_size)
        
        return quantity
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> list:
        """
        獲取 K 線數據
        
        Args:
            symbol: 交易對符號
            interval: 時間間隔 (1m, 5m, 15m, 1h, etc.)
            limit: 數據條數
            start_time: 開始時間戳（毫秒）
            end_time: 結束時間戳（毫秒）
        
        Returns:
            K 線數據列表
        """
        cache_key = f"klines_{symbol}_{interval}_{start_time}_{end_time}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        result = await self._request("GET", "/fapi/v1/klines", params=params)
        # 默認使用5分鐘緩存
        self.cache.set(cache_key, result, ttl=300)
        return result
    
    async def get_ticker_price(self, symbol: Optional[str] = None) -> Any:
        """
        獲取最新價格（v3.13.0：支持单个symbol返回float）
        
        Args:
            symbol: 交易對符號（None 表示所有）
        
        Returns:
            單個symbol: float (價格)
            所有symbols: dict/list (原始API響應)
        """
        params = {"symbol": symbol} if symbol else {}
        cache_key = f"ticker_{symbol or 'all'}"
        
        cached = self.cache.get(cache_key)
        if cached:
            # 单个symbol返回float
            if symbol and isinstance(cached, dict):
                return float(cached.get('price', 0.0))
            return cached
        
        result = await self._request("GET", "/fapi/v1/ticker/price", params=params)
        self.cache.set(cache_key, result, ttl=Config.CACHE_TTL_TICKER)
        
        # v3.13.0：单个symbol直接返回价格（float）
        if symbol and isinstance(result, dict):
            return float(result.get('price', 0.0))
        
        return result
    
    async def get_24h_tickers(self, symbol: Optional[str] = None) -> Any:
        """
        獲取24小時價格變動統計
        
        包含：
        - priceChange: 24h價格變化
        - priceChangePercent: 24h價格變化百分比
        - lastPrice: 最新價格
        - volume: 24h交易量
        - quoteVolume: 24h交易額
        等
        
        Args:
            symbol: 交易對符號（None 表示所有）
        
        Returns:
            24h ticker 數據
        """
        params = {"symbol": symbol} if symbol else {}
        cache_key = f"24h_ticker_{symbol or 'all'}"
        
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        result = await self._request("GET", "/fapi/v1/ticker/24hr", params=params)
        # 24h ticker 緩存時間短一些，因為需要實時波動率
        self.cache.set(cache_key, result, ttl=60)  # 60秒緩存
        return result
    
    async def get_account_info(self) -> dict:
        """獲取賬戶信息"""
        cache_key = "account_info"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        result = await self._request("GET", "/fapi/v2/account", signed=True)
        self.cache.set(cache_key, result, ttl=Config.CACHE_TTL_ACCOUNT)
        return result
    
    async def get_positions(self) -> list:
        """獲取當前持倉"""
        account_info = await self.get_account_info()
        positions = [
            pos for pos in account_info.get('positions', [])
            if float(pos.get('positionAmt', 0)) != 0
        ]
        return positions
    
    async def get_position_info_async(self) -> list:
        """
        獲取持倉信息（異步版本，position_controller 使用）
        
        Returns:
            持倉列表（包含所有持倉，包括零倉位）
        """
        account_info = await self.get_account_info()
        return account_info.get('positions', [])
    
    async def get_account_balance(self) -> dict:
        """
        獲取 U 本位合約賬戶餘額
        
        Returns:
            dict: {
                'total_balance': float,  # 總餘額（USDT）
                'available_balance': float,  # 可用餘額（USDT）
                'total_margin': float,  # 總保證金
                'unrealized_pnl': float,  # 未實現盈虧
                'total_wallet_balance': float  # 總錢包餘額（含未實現盈虧）
            }
        """
        account_info = await self.get_account_info()
        
        # 提取 USDT 資產信息
        total_balance = 0.0
        available_balance = 0.0
        
        for asset in account_info.get('assets', []):
            if asset.get('asset') == 'USDT':
                total_balance = float(asset.get('walletBalance', 0))
                available_balance = float(asset.get('availableBalance', 0))
                break
        
        total_margin = total_balance - available_balance
        unrealized_pnl = float(account_info.get('totalUnrealizedProfit', 0))
        
        result = {
            'total_balance': total_balance,
            'available_balance': available_balance,
            'total_margin': total_margin,
            'unrealized_pnl': unrealized_pnl,
            'total_wallet_balance': total_balance + unrealized_pnl
        }
        
        logger.info(
            f"💰 賬戶餘額: 總額 {total_balance:.2f} USDT, "
            f"可用 {available_balance:.2f} USDT, "
            f"保證金 {total_margin:.2f} USDT, "
            f"未實現盈虧 {unrealized_pnl:+.2f} USDT"
        )
        
        return result
    
    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        **kwargs
    ) -> dict:
        """
        創建訂單（自動格式化數量精度）
        
        Args:
            symbol: 交易對
            side: BUY / SELL
            order_type: MARKET / LIMIT / STOP_MARKET / TAKE_PROFIT_MARKET
            quantity: 數量
            price: 限價單價格
            stop_price: 止損/止盈價格
            **kwargs: 其他參數
        
        Returns:
            訂單信息
        """
        # 自動格式化數量以符合 Binance 精度要求
        formatted_quantity = await self.format_quantity(symbol, quantity)
        
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": formatted_quantity,
            **kwargs
        }
        
        if price:
            params['price'] = price
        if stop_price:
            params['stopPrice'] = stop_price
        
        logger.info(f"創建訂單: {symbol} {side} {order_type} {formatted_quantity}")
        if formatted_quantity != quantity:
            logger.debug(f"  數量已格式化: {quantity} → {formatted_quantity}")
        
        return await self._request("POST", "/fapi/v1/order", params=params, signed=True)
    
    async def get_position_mode(self) -> bool:
        """
        查詢當前 Position Mode（支持自動重試）
        
        Returns:
            True = Hedge Mode (雙向持倉)，False = One-Way Mode (單向持倉)
        """
        # 如果已成功查詢過，直接返回緩存
        if self._hedge_mode is not None:
            return self._hedge_mode
        
        try:
            result = await self._request("GET", "/fapi/v1/positionSide/dual", signed=True)
            # ✅ 只在成功時緩存結果
            self._hedge_mode = result.get('dualSidePosition', False)
            mode_name = "Hedge Mode (雙向持倉)" if self._hedge_mode else "One-Way Mode (單向持倉)"
            logger.info(f"📍 當前 Position Mode: {mode_name}")
            return self._hedge_mode
        except Exception as e:
            # ⚠️ 失敗時不緩存，允許後續重試
            logger.warning(f"⚠️ 查詢 Position Mode 失敗: {e}，默認使用 One-Way Mode（下次會重試）")
            return False  # 臨時返回 One-Way，不設置 self._hedge_mode
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        **kwargs
    ) -> dict:
        """
        下單（create_order 的別名，智能適配 Position Mode，自動重試）
        
        Args:
            symbol: 交易對
            side: BUY / SELL
            order_type: MARKET / LIMIT / STOP_MARKET / TAKE_PROFIT_MARKET
            quantity: 數量
            price: 限價單價格
            stop_price: 止損/止盈價格
            **kwargs: 其他參數
        
        Returns:
            訂單信息
        """
        # 自動適配 Position Mode
        is_hedge_mode = await self.get_position_mode()
        
        if is_hedge_mode and 'positionSide' not in kwargs:
            # Hedge Mode: 必須指定 positionSide
            # BUY → LONG, SELL → SHORT
            kwargs['positionSide'] = 'LONG' if side == 'BUY' else 'SHORT'
            logger.debug(f"  Hedge Mode: 添加 positionSide={kwargs['positionSide']}")
        elif not is_hedge_mode and 'positionSide' in kwargs:
            # One-Way Mode: 移除 positionSide
            del kwargs['positionSide']
            logger.debug("  One-Way Mode: 移除 positionSide")
        
        # 嘗試下單，如果遇到 -4061 錯誤則自動重試
        try:
            return await self.create_order(symbol, side, order_type, quantity, price, stop_price, **kwargs)
        except BinanceRequestError as e:
            # 檢查是否是 -4061 錯誤（Position Side 不匹配）
            if '-4061' in str(e):
                logger.warning(f"⚠️ Position Side 錯誤，嘗試切換模式並重試...")
                
                # 切換 Position Mode 猜測
                self._hedge_mode = not is_hedge_mode
                logger.info(f"📍 切換到 {'Hedge Mode' if self._hedge_mode else 'One-Way Mode'} 並重試")
                
                # 重新調整參數
                if self._hedge_mode and 'positionSide' not in kwargs:
                    kwargs['positionSide'] = 'LONG' if side == 'BUY' else 'SHORT'
                    logger.debug(f"  添加 positionSide={kwargs['positionSide']}")
                elif not self._hedge_mode and 'positionSide' in kwargs:
                    del kwargs['positionSide']
                    logger.debug("  移除 positionSide")
                
                # 重試
                return await self.create_order(symbol, side, order_type, quantity, price, stop_price, **kwargs)
            else:
                # 其他錯誤直接拋出
                raise
    
    async def get_order(self, symbol: str, order_id: int) -> dict:
        """
        查詢訂單狀態
        
        Args:
            symbol: 交易對
            order_id: 訂單ID
        
        Returns:
            訂單信息
        """
        params = {"symbol": symbol, "orderId": order_id}
        return await self._request("GET", "/fapi/v1/order", params=params, signed=True)
    
    async def cancel_order(self, symbol: str, order_id: int) -> dict:
        """
        取消訂單
        
        Args:
            symbol: 交易對
            order_id: 訂單ID
        
        Returns:
            取消結果
        """
        params = {"symbol": symbol, "orderId": order_id}
        return await self._request("DELETE", "/fapi/v1/order", params=params, signed=True)
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """
        獲取所有未成交訂單
        
        Args:
            symbol: 交易對（可選，不提供則返回所有交易對的未成交訂單）
        
        Returns:
            未成交訂單列表
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("GET", "/fapi/v1/openOrders", params=params, signed=True)
    
    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        """
        設置槓桿倍數
        
        Args:
            symbol: 交易對
            leverage: 槓桿倍數
        
        Returns:
            設置結果
        """
        params = {"symbol": symbol, "leverage": leverage}
        return await self._request("POST", "/fapi/v1/leverage", params=params, signed=True)
    
    async def test_connection(self) -> bool:
        """測試 API 連接並初始化 Position Mode"""
        try:
            await self._request("GET", "/fapi/v1/ping")
            logger.info("✅ Binance API 連接成功")
            
            # 立即檢測 Position Mode（Hedge 或 One-Way）
            await self.get_position_mode()
            
            return True
        except Exception as e:
            logger.error(f"❌ Binance API 連接失敗: {e}")
            return False
    
    async def get_listen_key(self) -> str:
        """
        獲取listenKey（用於UserData WebSocket）
        
        Returns:
            listenKey字符串
        
        注意：
        - listenKey有效期60分鐘
        - 需要每30分鐘續期一次
        """
        result = await self._request("POST", "/fapi/v1/listenKey", signed=True)
        listen_key = result.get('listenKey', '')
        logger.debug(f"✅ listenKey已創建: {listen_key[:8]}...")
        return listen_key
    
    async def renew_listen_key(self, listen_key: str) -> dict:
        """
        續期listenKey（延長60分鐘有效期）
        
        Args:
            listen_key: 要續期的listenKey
        
        Returns:
            續期結果
        """
        params = {'listenKey': listen_key}
        result = await self._request("PUT", "/fapi/v1/listenKey", params=params, signed=True)
        logger.debug(f"🔄 listenKey已續期: {listen_key[:8]}...")
        return result
    
    async def close_listen_key(self, listen_key: str) -> dict:
        """
        關閉listenKey
        
        Args:
            listen_key: 要關閉的listenKey
        
        Returns:
            關閉結果
        """
        params = {'listenKey': listen_key}
        result = await self._request("DELETE", "/fapi/v1/listenKey", params=params, signed=True)
        logger.debug(f"✅ listenKey已關閉: {listen_key[:8]}...")
        return result
    
    async def close(self):
        """關閉客戶端"""
        if self.session and not self.session.closed:
            await self.session.close()
