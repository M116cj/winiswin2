"""
數據服務
職責：市場數據獲取、批量處理、多時間框架數據對齊
"""

import asyncio
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime, timedelta
import logging

from src.clients.binance_client import BinanceClient
from src.core.cache_manager import CacheManager
from src.config import Config

logger = logging.getLogger(__name__)


class DataService:
    """數據服務類"""
    
    def __init__(self, binance_client: BinanceClient):
        """
        初始化數據服務
        
        Args:
            binance_client: Binance 客戶端
        """
        self.client = binance_client
        self.cache = binance_client.cache
        # 使用 1h/15m/5m 三个时间框架
        # 1h: 趋势确认（每小时）
        # 15m: 趋势确认（每15分钟）
        # 5m: 趋势符合确认 + 入场信号
        self.timeframes = ["1h", "15m", "5m"]
        self.all_symbols: List[str] = []
    
    async def initialize(self):
        """初始化數據服務"""
        logger.info("初始化數據服務...")
        await self.load_all_symbols()
        logger.info(f"✅ 已加載 {len(self.all_symbols)} 個 USDT 永續合約")
    
    async def load_all_symbols(self):
        """加載所有 USDT 永續合約交易對"""
        try:
            exchange_info = await self.client.get_exchange_info()
            
            self.all_symbols = [
                symbol['symbol']
                for symbol in exchange_info.get('symbols', [])
                if symbol['symbol'].endswith('USDT') 
                and symbol['status'] == 'TRADING'
                and symbol.get('contractType') == 'PERPETUAL'
                and symbol['symbol'].isascii()  # 排除中文等非ASCII交易對（避免簽名錯誤）
            ]
            
            logger.info(f"成功加載 {len(self.all_symbols)} 個交易對")
            
        except Exception as e:
            logger.error(f"加載交易對失敗: {e}")
            self.all_symbols = []
    
    async def get_multi_timeframe_data(
        self,
        symbol: str,
        timeframes: Optional[List[str]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        獲取多時間框架數據
        
        Args:
            symbol: 交易對
            timeframes: 時間框架列表（默認使用所有時間框架）
        
        Returns:
            Dict[str, pd.DataFrame]: 時間框架到數據框的映射
        """
        if timeframes is None:
            timeframes = self.timeframes
        
        tasks = [
            self.get_klines(symbol, tf, limit=200)
            for tf in timeframes
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        data = {}
        for tf, result in zip(timeframes, results):
            if isinstance(result, Exception):
                logger.error(f"獲取 {symbol} {tf} 數據失敗: {result}")
                data[tf] = pd.DataFrame()
            else:
                data[tf] = result
        
        return data
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 200,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> pd.DataFrame:
        """
        獲取 K線數據（智能緩存）
        
        Args:
            symbol: 交易對
            interval: 時間間隔
            limit: 數據條數
            start_time: 開始時間戳
            end_time: 結束時間戳
        
        Returns:
            pd.DataFrame: K線數據框
        """
        # 簡化緩存策略：基於交易對和時間框架
        # 同一個時間框架的數據在TTL內都會使用緩存
        cache_key = f"klines_{symbol}_{interval}_{limit}"
        
        # 歷史請求或指定時間範圍時，不使用緩存
        if start_time is not None or end_time is not None:
            cache_key = None  # 跳過緩存
        
        # 嘗試從緩存獲取
        if cache_key:
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                logger.debug(f"緩存命中: {symbol} {interval}")
                return cached_data
        
        try:
            klines = await self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                start_time=start_time,
                end_time=end_time
            )
            
            if not klines:
                return pd.DataFrame()
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_volume',
                'taker_buy_quote_volume', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            # 根據時間框架使用不同的 TTL
            ttl_map = {
                '1h': Config.CACHE_TTL_KLINES_1H,
                '15m': Config.CACHE_TTL_KLINES_15M,
                '5m': Config.CACHE_TTL_KLINES_5M
            }
            ttl = ttl_map.get(interval, Config.CACHE_TTL_KLINES_DEFAULT)
            
            self.cache.set(cache_key, df, ttl=ttl)
            logger.debug(f"緩存 {symbol} {interval} 數據，TTL={ttl}秒")
            
            return df
            
        except Exception as e:
            logger.error(f"獲取 K線數據失敗 {symbol} {interval}: {e}")
            return pd.DataFrame()
    
    async def get_batch_tickers(self, symbols: List[str]) -> Dict[str, dict]:
        """
        批量獲取行情數據
        
        Args:
            symbols: 交易對列表
        
        Returns:
            Dict[str, dict]: 交易對到行情數據的映射
        """
        cache_key = "batch_tickers"
        cached_data = self.cache.get(cache_key)
        
        if cached_data is not None:
            return {s: cached_data.get(s, {}) for s in symbols}
        
        try:
            all_tickers = await self.client.get_ticker_price()
            
            ticker_dict = {
                ticker['symbol']: ticker
                for ticker in all_tickers
                if ticker['symbol'] in symbols
            }
            
            self.cache.set(cache_key, ticker_dict, ttl=Config.CACHE_TTL_TICKER)
            
            return ticker_dict
            
        except Exception as e:
            logger.error(f"批量獲取行情數據失敗: {e}")
            return {}
    
    async def get_market_data_batch(
        self,
        symbols: List[str],
        timeframe: str = "15m",
        limit: int = 200
    ) -> Dict[str, pd.DataFrame]:
        """
        批量獲取市場數據
        
        Args:
            symbols: 交易對列表
            timeframe: 時間框架
            limit: 數據條數
        
        Returns:
            Dict[str, pd.DataFrame]: 交易對到數據框的映射
        """
        batch_size = Config.BATCH_SIZE
        results = {}
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            
            tasks = [
                self.get_klines(symbol, timeframe, limit)
                for symbol in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for symbol, data in zip(batch, batch_results):
                if isinstance(data, Exception):
                    logger.error(f"獲取 {symbol} 數據失敗: {data}")
                    results[symbol] = pd.DataFrame()
                else:
                    results[symbol] = data
            
            if i + batch_size < len(symbols):
                await asyncio.sleep(0.1)
        
        return results
    
    async def scan_market(self, top_n: int = 200) -> List[Dict]:
        """
        掃描市場，按流動性排序，返回前N個交易對
        
        策略：優先監控流動性最高的前200個標的
        - 流動性指標：24h 交易額（quoteVolume，以 USDT 計）
        - 從 600+ 個 U本位合約中選擇最活躍的
        
        Args:
            top_n: 返回前N個交易對（默認200）
        
        Returns:
            List[Dict]: 按流動性排序的交易對列表
        """
        logger.info(f"開始掃描 {len(self.all_symbols)} 個交易對（流動性排序）...")
        
        # 獲取24h ticker數據（包含交易量數據）
        try:
            exchange_info_data = await self.client.get_24h_tickers()
            
            market_data = []
            for ticker in exchange_info_data:
                symbol = ticker.get('symbol')
                if symbol not in self.all_symbols:
                    continue
                
                # 流動性指標：24h 交易額（USDT）
                quote_volume = float(ticker.get('quoteVolume', 0))
                volume_24h = float(ticker.get('volume', 0))
                price_change_pct = float(ticker.get('priceChangePercent', 0))
                
                market_data.append({
                    'symbol': symbol,
                    'price': float(ticker.get('lastPrice', 0)),
                    'change_24h': price_change_pct,
                    'volume_24h': volume_24h,
                    'quote_volume': quote_volume,  # 流動性指標（USDT）
                    'liquidity': quote_volume,     # 用於排序
                    'timestamp': datetime.now()
                })
            
            # 按流動性排序（從高到低）
            market_data.sort(key=lambda x: x['liquidity'], reverse=True)
            
            # 取前N個
            top_liquidity = market_data[:top_n]
            
            avg_volume = sum(x['liquidity'] for x in top_liquidity) / len(top_liquidity) if top_liquidity else 0
            
            logger.info(
                f"✅ 市場掃描完成: 從 {len(market_data)} 個交易對中選擇 "
                f"流動性最高的前 {len(top_liquidity)} 個 "
                f"(平均24h交易額: ${avg_volume:,.0f} USDT)"
            )
            
            return top_liquidity
            
        except Exception as e:
            logger.error(f"市場掃描失敗: {e}", exc_info=True)
            # 降級：返回所有交易對
            return await self._fallback_scan_market()
    
    async def _fallback_scan_market(self) -> List[Dict]:
        """降級掃描：當24h ticker失敗時使用"""
        tickers = await self.get_batch_tickers(self.all_symbols)
        
        market_data = []
        for symbol in self.all_symbols:
            ticker = tickers.get(symbol, {})
            if ticker:
                market_data.append({
                    'symbol': symbol,
                    'price': float(ticker.get('price', 0)),
                    'liquidity': 0.0,
                    'quote_volume': 0.0,
                    'timestamp': datetime.now()
                })
        
        logger.warning(f"使用降級掃描，獲取 {len(market_data)} 個交易對")
        return market_data
    
    async def get_account_info(self) -> dict:
        """
        獲取賬戶信息
        
        Returns:
            dict: 賬戶信息
        """
        cache_key = "account_info"
        cached_data = self.cache.get(cache_key)
        
        if cached_data is not None:
            return cached_data
        
        try:
            account = await self.client.get_account_info()
            self.cache.set(cache_key, account, ttl=Config.CACHE_TTL_ACCOUNT)
            return account
        except Exception as e:
            logger.error(f"獲取賬戶信息失敗: {e}")
            return {}
    
    async def get_positions(self) -> List[dict]:
        """
        獲取當前持倉
        
        Returns:
            List[dict]: 持倉列表
        """
        try:
            account = await self.get_account_info()
            positions = account.get('positions', [])
            
            active_positions = [
                pos for pos in positions
                if float(pos.get('positionAmt', 0)) != 0
            ]
            
            return active_positions
        except Exception as e:
            logger.error(f"獲取持倉失敗: {e}")
            return []
    
    def align_timeframes(
        self,
        data: Dict[str, pd.DataFrame]
    ) -> Dict[str, pd.DataFrame]:
        """
        對齊多時間框架數據
        
        Args:
            data: 時間框架到數據框的映射
        
        Returns:
            Dict[str, pd.DataFrame]: 對齊後的數據
        """
        if not data:
            return data
        
        aligned_data = {}
        
        for tf, df in data.items():
            if df.empty:
                aligned_data[tf] = df
                continue
            
            df = df.copy()
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            
            aligned_data[tf] = df
        
        return aligned_data
