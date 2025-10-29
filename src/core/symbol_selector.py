"""
SymbolSelector v3.17.2+ - 動態波動率交易對選擇器
職責：精準篩選高波動交易對，過濾低流動性噪音，動態更新交易對列表
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class SymbolSelector:
    """
    動態交易對選擇器（波動率優先策略）
    
    職責：
    1. 獲取所有 USDT 永續合約
    2. 並行獲取 24h 統計數據
    3. 計算波動率分數（價格波動 × 流動性）
    4. 過濾低流動性噪音（<1M USDT）
    5. 排除槓桿幣（BTCUP/DOWN等）
    6. 返回前 N 個高波動交易對
    
    波動率分數計算：
    - 價格波動率 = (high - low) / open
    - 流動性分數 = 成交額 / 1,000,000（百萬USDT）
    - 綜合分數 = 波動率 × (1 + ln(流動性))
    
    過濾規則：
    - 流動性 < 1M USDT → 排除
    - 包含 'UP' 或 'DOWN' → 排除（槓桿幣）
    - status != 'TRADING' → 排除
    """
    
    def __init__(self, binance_client: Any, config: Any):
        """
        初始化SymbolSelector
        
        Args:
            binance_client: Binance客戶端
            config: 配置對象
        """
        self.client = binance_client
        self.config = config
        
        logger.info("=" * 80)
        logger.info("✅ SymbolSelector v3.17.2+ 初始化完成")
        logger.info("   🎯 策略: 波動率 × 流動性綜合評分")
        logger.info("   🚫 過濾: 低流動性(<1M) + 槓桿幣(UP/DOWN)")
        logger.info("=" * 80)
    
    async def get_top_volatility_symbols(self, limit: int = 300) -> List[str]:
        """
        獲取波動率最高的前 N 個 USDT 永續交易對
        
        Args:
            limit: 返回的交易對數量（默認300）
        
        Returns:
            按波動率排序的交易對列表
        """
        logger.info(f"🔍 開始篩選波動率最高的前 {limit} 個交易對...")
        
        # 步驟1：獲取所有 USDT 永續合約
        all_symbols = await self._get_all_futures_symbols()
        if not all_symbols:
            logger.warning("⚠️ 未獲取到任何交易對")
            return []
        
        logger.info(f"📊 獲取到 {len(all_symbols)} 個USDT永續合約")
        
        # 步驟2：並行獲取 24h 統計數據
        logger.info("📡 並行獲取24h統計數據...")
        tasks = [self._fetch_ticker(symbol) for symbol in all_symbols]
        tickers = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 步驟3：計算波動率分數並過濾
        logger.info("📈 計算波動率分數...")
        symbol_scores = []
        filtered_count = 0
        low_liquidity_count = 0
        
        for symbol, ticker in zip(all_symbols, tickers):
            if isinstance(ticker, Exception) or not ticker:
                filtered_count += 1
                continue
            
            score = self._calculate_volatility_score(ticker)
            if score > 0:
                symbol_scores.append((symbol, score, ticker))
            else:
                low_liquidity_count += 1
        
        logger.info(f"✅ 有效交易對: {len(symbol_scores)}")
        logger.info(f"❌ API錯誤過濾: {filtered_count}")
        logger.info(f"❌ 低流動性過濾: {low_liquidity_count}")
        
        # 步驟4：按分數排序並返回前 N 個
        symbol_scores.sort(key=lambda x: x[1], reverse=True)
        top_symbols = [symbol for symbol, _, _ in symbol_scores[:limit]]
        
        # 步驟5：記錄前10名詳細信息
        logger.info("=" * 80)
        logger.info(f"📊 前10名高波動交易對詳細信息:")
        for i, (symbol, score, ticker) in enumerate(symbol_scores[:10], 1):
            high = float(ticker['highPrice'])
            low = float(ticker['lowPrice'])
            open_price = float(ticker['openPrice'])
            quote_volume = float(ticker['quoteVolume']) / 1_000_000  # 轉為百萬USDT
            
            price_volatility = (high - low) / open_price if open_price > 0 else 0
            
            logger.info(
                f"   {i:2d}. {symbol:12s} | "
                f"分數: {score:6.3f} | "
                f"波動率: {price_volatility*100:5.2f}% | "
                f"成交額: ${quote_volume:7.2f}M"
            )
        logger.info("=" * 80)
        
        logger.info(f"✅ 選擇完成：{len(top_symbols)} 個高波動交易對")
        return top_symbols
    
    async def _get_all_futures_symbols(self) -> List[str]:
        """
        獲取所有 USDT 永續交易對（過濾槓桿幣）
        
        Returns:
            所有符合條件的交易對列表
        """
        try:
            info = await self.client._request("GET", "/fapi/v1/exchangeInfo")
            
            symbols = [
                s['symbol'] for s in info['symbols']
                if s['quoteAsset'] == 'USDT'
                and s['status'] == 'TRADING'
                and 'UP' not in s['symbol']    # 排除槓桿幣（BTCUP等）
                and 'DOWN' not in s['symbol']  # 排除槓桿幣（BTCDOWN等）
            ]
            
            return symbols
        
        except Exception as e:
            logger.error(f"❌ 獲取交易對失敗: {e}")
            return []
    
    async def _fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """
        獲取單一交易對 24h 統計數據
        
        Args:
            symbol: 交易對符號
        
        Returns:
            24h統計數據，或None（失敗時）
        """
        try:
            result = await self.client._request("GET", f"/fapi/v1/ticker/24hr?symbol={symbol}")
            return result
        except Exception as e:
            logger.debug(f"⚠️ 獲取 {symbol} 24h統計失敗: {e}")
            return None
    
    def _calculate_volatility_score(self, ticker: Dict) -> float:
        """
        計算波動率分數（結合價格波動 + 流動性）
        
        算法：
        1. 價格波動率 = (high - low) / open
        2. 流動性分數 = 成交額(USDT) / 1,000,000
        3. 綜合分數 = 波動率 × (1 + ln(流動性))
        
        過濾條件：
        - 流動性 < 1M USDT → 返回 0.0（無效）
        - open_price = 0 → 返回 0.0（無效）
        
        Args:
            ticker: 24h統計數據
        
        Returns:
            波動率分數（0.0表示無效）
        """
        if not ticker:
            return 0.0
        
        try:
            # 步驟1：提取價格數據
            high = float(ticker.get('highPrice', 0))
            low = float(ticker.get('lowPrice', 0))
            open_price = float(ticker.get('openPrice', 0))
            quote_volume = float(ticker.get('quoteVolume', 0))
            
            # 步驟2：驗證數據有效性
            if open_price == 0:
                return 0.0
            
            # 步驟3：計算價格波動率
            price_volatility = (high - low) / open_price
            
            # 步驟4：計算流動性分數（轉為百萬USDT）
            liquidity_score = quote_volume / 1_000_000
            
            # 步驟5：過濾低流動性（<1M USDT）
            if liquidity_score < 1.0:
                return 0.0
            
            # 步驟6：綜合分數（波動率 × ln對數增強的流動性）
            # 使用 ln 避免流動性過度主導評分
            composite_score = price_volatility * (1 + np.log(liquidity_score))
            
            return composite_score
        
        except (ValueError, TypeError, KeyError) as e:
            logger.debug(f"⚠️ 計算波動率分數失敗: {e}")
            return 0.0
