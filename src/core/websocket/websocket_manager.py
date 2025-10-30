"""
WebSocketManager v3.17.2+ - 統一WebSocket管理器（完整升級版）
職責：動態波動率交易對選擇、分片管理、統一數據接口
升級：波動率選擇器（前300高波動）、ShardFeed整合、PriceFeed支持
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any

from src.core.websocket.shard_feed import ShardFeed
from src.core.websocket.account_feed import AccountFeed
from src.core.symbol_selector import SymbolSelector
from src.config import Config

logger = logging.getLogger(__name__)

# 🔥 v3.18+ 修復：硬編碼的高流動性USDT永續合約列表（REST API失敗時的fallback）
FALLBACK_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "TRXUSDT", "AVAXUSDT", "LINKUSDT",
    "MATICUSDT", "DOTUSDT", "LTCUSDT", "UNIUSDT", "ETCUSDT",
    "ATOMUSDT", "NEARUSDT", "APTUSDT", "FILUSDT", "ARBUSDT",
    "INJUSDT", "SUIUSDT", "STXUSDT", "SEIUSDT", "OPUSDT",
    "PEPEUSDT", "AAVEUSDT", "MKRUSDT", "RUNEUSDT", "ORDIUSDT",
    "WLDUSDT", "TIAUSDT", "JUPUSDT", "PYTHUSDT", "RENDERUSDT",
    "FETUSDT", "GRTUSDT", "FTMUSDT", "ICPUSDT", "HBARUSDT",
    "IMXUSDT", "TAOUSDT", "LDOUSDT", "WIFUSDT", "FLOKIUSDT",
    "GALAUSDT", "BEAMXUSDT", "BLURUSDT", "JTOUSDT", "BONKUSDT"
]  # 50個主流交易對


class WebSocketManager:
    """
    WebSocketManager - 統一WebSocket管理器（v3.17.2+波動率優化版）
    
    職責：
    1. 動態選擇波動率最高的前300個USDT永續合約
    2. 使用ShardFeed進行分片管理（每片50個符號）
    3. 管理AccountFeed（帳戶/倉位監控）
    4. 提供統一的數據查詢接口
    5. 協調生命週期管理（start/stop）
    
    架構（v3.17.2+波動率優化）：
    ┌──────────────────────────────────────────┐
    │      WebSocketManager v3.17.2+           │
    ├──────────────────────────────────────────┤
    │ • SymbolSelector (波動率篩選器)         │
    │   └─ 前300個高波動交易對                │
    │ • ShardFeed (分片管理器)                 │
    │   ├─ Shard 0: K線Feed + 價格Feed (50)   │
    │   ├─ Shard 1: K線Feed + 價格Feed (50)   │
    │   ├─ Shard N: K線Feed + 價格Feed (N)    │
    │ • AccountFeed (即時倉位)                 │
    └──────────────────────────────────────────┘
    
    優勢：
    - 100% WebSocket驅動（API權重≈0）
    - 動態波動率選擇（精準篩選高波動）
    - PERPETUAL合約過濾（天然排除槓桿幣）
    - 過濾低流動性噪音（<1M USDT）
    - 分片防止單連線過載
    - 心跳監控 + 自動重連
    """
    
    def __init__(
        self,
        binance_client: Any,
        symbols: Optional[List[str]] = None,
        kline_interval: str = "1m",
        shard_size: int = 50,
        enable_kline_feed: bool = True,
        enable_price_feed: bool = True,
        enable_account_feed: bool = True,
        auto_fetch_symbols: bool = True
    ):
        """
        初始化WebSocketManager
        
        Args:
            binance_client: Binance客戶端
            symbols: 交易對列表（可選，如為None則自動獲取）
            kline_interval: K線週期（默認1m）
            shard_size: 分片大小（默認50）
            enable_kline_feed: 是否啟用K線Feed
            enable_price_feed: 是否啟用價格Feed（bookTicker）
            enable_account_feed: 是否啟用帳戶Feed
            auto_fetch_symbols: 是否自動獲取全市場交易對
        """
        self.binance_client = binance_client
        self.symbols = symbols or []
        self.kline_interval = kline_interval
        self.shard_size = shard_size
        self.enable_kline_feed = enable_kline_feed
        self.enable_price_feed = enable_price_feed
        self.enable_account_feed = enable_account_feed
        self.auto_fetch_symbols = auto_fetch_symbols
        self.running = False
        
        # Feed組件
        self.shard_feed: Optional[ShardFeed] = None
        self.account_feed: Optional[AccountFeed] = None
        
        # v3.17.2+ 波動率選擇器（動態篩選高波動交易對）
        self.symbol_selector = SymbolSelector(binance_client, Config)
        
        logger.info("=" * 80)
        logger.info("✅ WebSocketManager v3.17.2+ 初始化完成（流動性×波動率優化）")
        logger.info(f"   📊 交易對模式: {'綜合分數前{0}名'.format(Config.WEBSOCKET_SYMBOL_LIMIT) if auto_fetch_symbols else f'{len(symbols or [])}個'}")
        logger.info(f"   🎯 選擇策略: 流動性 × 波動率（過濾<1M + <0.5%）")
        logger.info(f"   🔀 分片大小: {shard_size}")
        logger.info(f"   📡 K線Feed: {'啟用' if enable_kline_feed else '停用'}")
        logger.info(f"   💰 價格Feed: {'啟用' if enable_price_feed else '停用'}")
        logger.info(f"   📡 帳戶Feed: {'啟用' if enable_account_feed else '停用'}")
        logger.info("=" * 80)
    
    async def _get_all_futures_symbols(self) -> List[str]:
        """
        動態獲取流動性×波動率綜合分數最高的USDT永續交易對（v3.18+ 強化版）
        
        使用 SymbolSelector 精準篩選：
        1. 獲取所有 USDT 永續合約（contractType=PERPETUAL，天然排除槓桿幣）
        2. 並行獲取 24h 統計數據
        3. 計算綜合分數（流動性 × 波動率）
        4. 過濾低流動性（<1M USDT）和低波動率（<0.5%）
        5. 綜合分數排序（優選高品質交易對）
        6. 返回前 N 個高品質交易對
        
        🔥 v3.18+ 修復：添加硬編碼fallback列表（REST API失敗時使用）
        
        Returns:
            綜合分數最高的交易對列表（默認前200個）
        """
        try:
            # 🔥 v3.17.2+ 優化：使用流動性×波動率綜合分數
            symbols = await self.symbol_selector.get_top_liquidity_volatility_symbols(
                limit=Config.WEBSOCKET_SYMBOL_LIMIT  # 默認200
            )
            
            if symbols:
                logger.info(f"✅ 綜合分數篩選成功：{len(symbols)} 個高品質交易對")
                logger.info(f"   前5名: {symbols[:5]}")
                return symbols
            else:
                logger.warning("⚠️ 綜合分數篩選未返回任何交易對，使用fallback列表")
                return FALLBACK_SYMBOLS
        
        except Exception as e:
            logger.error(f"❌ 綜合分數篩選失敗: {e}")
            logger.warning("⚠️ 降級使用全市場模式...")
            
            # 降級方案1：獲取所有 USDT 永續合約
            try:
                info = await self.binance_client._request("GET", "/fapi/v1/exchangeInfo")
                
                symbols = [
                    s['symbol'] for s in info['symbols']
                    if s.get('quoteAsset') == 'USDT'
                    and s.get('contractType') == 'PERPETUAL'  # 防禦性檢查
                    and s.get('status') == 'TRADING'
                ]
                
                if symbols:
                    logger.info(f"✅ 降級模式：{len(symbols)} 個USDT永續合約")
                    return symbols
                else:
                    logger.warning("⚠️ 降級模式未返回交易對，使用fallback列表")
                    return FALLBACK_SYMBOLS
                    
            except Exception as fallback_error:
                # 🔥 v3.18+ 修復：最終fallback到硬編碼列表
                logger.error(f"❌ 降級模式也失敗: {fallback_error}")
                logger.warning(f"⚠️ 使用硬編碼fallback列表（{len(FALLBACK_SYMBOLS)}個主流交易對）")
                return FALLBACK_SYMBOLS
    
    async def start(self):
        """啟動所有WebSocket Feed（非阻塞）+ 預熱緩存（v3.18+ 強化版）"""
        if self.running:
            logger.warning("⚠️ WebSocketManager 已在運行中")
            return
        
        self.running = True
        logger.info("=" * 80)
        logger.info("🚀 WebSocketManager v3.18+ 啟動中（冷啟動優化）...")
        logger.info("=" * 80)
        
        # 1. 動態獲取交易對（如果需要）
        if self.auto_fetch_symbols and not self.symbols:
            logger.info("📡 步驟1/4：獲取交易對列表...")
            self.symbols = await self._get_all_futures_symbols()
            logger.info(f"   ✅ 已獲取 {len(self.symbols)} 個交易對")
            logger.info(f"   前10名: {self.symbols[:10]}")
        else:
            logger.info(f"📡 步驟1/4：使用預設交易對列表（{len(self.symbols)}個）")
        
        tasks = []
        
        # 2. 啟動ShardFeed（K線+價格分片管理）
        logger.info("📡 步驟2/4：啟動ShardFeed（K線+價格）...")
        if self.symbols and (self.enable_kline_feed or self.enable_price_feed):
            shard_count = (len(self.symbols) + self.shard_size - 1) // self.shard_size
            logger.info(f"   創建 {shard_count} 個分片（每片{self.shard_size}個交易對）")
            
            self.shard_feed = ShardFeed(
                all_symbols=self.symbols,
                shard_size=self.shard_size,
                enable_kline=self.enable_kline_feed,
                enable_price=self.enable_price_feed,
                kline_interval=self.kline_interval
            )
            tasks.append(self.shard_feed.start())
            logger.info(f"   ✅ ShardFeed已創建")
        else:
            logger.warning("   ⚠️ 無交易對或Feed未啟用，跳過ShardFeed")
        
        # 3. 啟動AccountFeed（帳戶/倉位監控）
        logger.info("📡 步驟3/4：啟動AccountFeed（帳戶監控）...")
        if self.enable_account_feed:
            self.account_feed = AccountFeed(binance_client=self.binance_client)
            tasks.append(self.account_feed.start())
            logger.info("   ✅ AccountFeed已創建")
        else:
            logger.info("   ⏸️  AccountFeed未啟用")
        
        # 4. 並行啟動所有Feed
        if tasks:
            logger.info(f"📡 並行啟動 {len(tasks)} 個Feed...")
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("   ✅ 所有Feed已啟動")
        
        # 🔥 v3.18+：預熱K線緩存（解決冷啟動問題）
        logger.info("📡 步驟4/4：預熱K線緩存...")
        if self.enable_kline_feed and self.shard_feed:
            logger.info("   🔥 開始預熱（用REST API獲取歷史100根1m K線）...")
            await self._warmup_cache()
        else:
            logger.warning("   ⚠️ 預熱跳過（K線Feed未啟用或ShardFeed未創建）")
            logger.warning("   ⚠️ WebSocket將從實時接收開始，需60分鐘累積1h數據")
        
        logger.info("=" * 80)
        logger.info("✅ WebSocketManager啟動完成")
        logger.info(f"   K線Feed: {'✅' if self.shard_feed else '⏸️ '}")
        logger.info(f"   價格Feed: {'✅' if self.shard_feed and self.enable_price_feed else '⏸️ '}")
        logger.info(f"   帳戶Feed: {'✅' if self.account_feed else '⏸️ '}")
        logger.info(f"   監控交易對: {len(self.symbols)}個")
        logger.info("=" * 80)
    
    async def _warmup_cache(self, timeout: int = 60):
        """
        預熱K線緩存（v3.18+ 強化版：REST失敗不影響WebSocket）
        
        解決問題：
        - WebSocket啟動時緩存為空，導致立即fallback到REST
        - 需要60分鐘才能累積足夠的1m K線聚合成1h
        
        解決方案：
        - 啟動時用REST API獲取歷史100根1m K線
        - 填充到所有分片的KlineFeed緩存中
        - 立即可用於聚合5m/15m/1h
        - WebSocket繼續接收新K線並累積
        
        🔥 v3.18+ 修復：
        - 預熱失敗不影響WebSocket啟動
        - 即使所有REST請求失敗，WebSocket仍會接收實時數據
        - 實時累積60根1m K線後（約60分鐘）即可聚合1h
        
        Args:
            timeout: 預熱超時時間（秒），默認60秒
        """
        if not self.shard_feed or not self.shard_feed.kline_shards:
            logger.warning("   ⚠️ 無K線分片，跳過預熱")
            return
        
        logger.info(f"   預熱目標: {len(self.symbols)}個交易對")
        start_time = asyncio.get_event_loop().time()
        
        # 批量獲取歷史K線（避免速率限制）
        batch_size = 10  # 每批10個交易對
        warmed_count = 0
        failed_count = 0
        
        for i in range(0, len(self.symbols), batch_size):
            batch = self.symbols[i:i + batch_size]
            
            # 並行獲取這批交易對的K線
            tasks = [
                self._fetch_and_seed_kline_history(symbol)
                for symbol in batch
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for symbol, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.debug(f"      {symbol}: 異常失敗 ({str(result)[:50]})")
                    failed_count += 1
                elif result is False or result is None:
                    logger.debug(f"      {symbol}: 預熱失敗（REST API不可用）")
                    failed_count += 1
                elif result:
                    warmed_count += 1
            
            # 檢查超時
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.warning(f"   ⚠️ 預熱超時（{elapsed:.1f}s），已完成{warmed_count}/{len(self.symbols)}個交易對")
                break
            
            # 避免速率限制
            await asyncio.sleep(0.1)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        success_rate = (warmed_count / len(self.symbols) * 100) if self.symbols else 0
        
        logger.info("   " + "─" * 76)
        logger.info(f"   預熱結果:")
        logger.info(f"   ⏱️  耗時: {elapsed:.1f}秒")
        logger.info(f"   ✅ 成功: {warmed_count}/{len(self.symbols)} ({success_rate:.1f}%)")
        logger.info(f"   ❌ 失敗: {failed_count}/{len(self.symbols)}")
        
        if warmed_count > 0:
            logger.info(f"   ✅ 預熱成功！現在可以立即使用WebSocket聚合5m/15m/1h")
        elif warmed_count == 0 and len(self.symbols) > 0:
            logger.warning(f"   ⚠️ 預熱完全失敗（REST API不可用或熔斷器阻斷）")
            logger.warning(f"   ⚠️ WebSocket將從實時接收開始，需等待數據累積：")
            logger.warning(f"      • 5m數據將在5分鐘後可用")
            logger.warning(f"      • 15m數據將在15分鐘後可用")
            logger.warning(f"      • 1h數據將在60分鐘後可用")
        
        logger.info("   " + "─" * 76)
    
    async def _fetch_and_seed_kline_history(self, symbol: str) -> bool:
        """
        獲取並填充單個交易對的K線歷史
        
        Args:
            symbol: 交易對
        
        Returns:
            True如果成功，False如果失敗
        """
        try:
            # 使用binance_client獲取最近100根1m K線
            klines = await self.binance_client.get_klines(
                symbol=symbol,
                interval="1m",
                limit=100
            )
            
            if not klines or len(klines) == 0:
                logger.debug(f"⚠️ {symbol} 未獲取到歷史K線")
                return False
            
            # 轉換為標準格式（與WebSocket格式一致）
            formatted_klines = []
            for kline in klines:
                formatted_klines.append({
                    'symbol': symbol,
                    'timestamp': int(kline[0]),  # 開盤時間（毫秒）
                    'open': float(kline[1]),
                    'high': float(kline[2]),
                    'low': float(kline[3]),
                    'close': float(kline[4]),
                    'volume': float(kline[5]),
                    'close_time': int(kline[6]),
                    'quote_volume': float(kline[7]),
                    'trades': int(kline[8]),
                    'server_timestamp': int(kline[0]),
                    'local_timestamp': int(kline[0]),  # 歷史數據無法獲取真實local_timestamp
                    'latency_ms': 0,  # 歷史數據延遲設為0
                    'shard_id': -1  # 預熱數據標記為-1（後續WebSocket數據會覆蓋）
                })
            
            # 找到對應的KlineFeed並填充數據
            if self.shard_feed and self.shard_feed.kline_shards:
                for kline_feed in self.shard_feed.kline_shards:
                    if symbol.lower() in kline_feed.symbols:
                        kline_feed.seed_history(symbol, formatted_klines)
                        return True
            
            logger.debug(f"⚠️ {symbol} 未找到對應的KlineFeed分片")
            return False
            
        except Exception as e:
            logger.debug(f"⚠️ {symbol} 預熱異常: {e}")
            return False
    
    # ==================== K線數據接口 ====================
    
    def get_kline(self, symbol: str) -> Optional[Dict]:
        """
        獲取最新K線數據
        
        Args:
            symbol: 交易對
        
        Returns:
            K線數據（包含時間戳），或None
        """
        if not self.shard_feed:
            return None
        return self.shard_feed.get_kline(symbol)
    
    def get_all_klines(self) -> Dict[str, List[Dict]]:
        """
        獲取所有幣種的K線歷史
        
        Returns:
            所有K線數據的字典 {symbol: [kline1, kline2, ...]}
        """
        if not self.shard_feed:
            return {}
        return self.shard_feed.get_all_klines()
    
    # ==================== 價格數據接口 ====================
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        獲取最新價格（中間價）
        
        Args:
            symbol: 交易對
        
        Returns:
            最新價格，或None
        """
        # 優先使用PriceFeed的中間價
        if self.shard_feed:
            mid_price = self.shard_feed.get_mid_price(symbol)
            if mid_price is not None:
                return mid_price
        
        # 備援：使用K線的收盤價
        kline = self.get_kline(symbol)
        if kline:
            return kline.get('close')
        
        # 備援：使用帳戶Feed的倉位價格
        if self.account_feed:
            position = self.account_feed.get_position(symbol)
            if position:
                return position.get('entry_price')
        
        return None
    
    def get_price_data(self, symbol: str) -> Optional[Dict]:
        """
        獲取完整價格數據（bid/ask/spread）
        
        Args:
            symbol: 交易對
        
        Returns:
            價格數據，或None
        """
        if not self.shard_feed:
            return None
        return self.shard_feed.get_price(symbol)
    
    def get_spread_bps(self, symbol: str) -> Optional[float]:
        """
        獲取買賣價差（基點）
        
        Args:
            symbol: 交易對
        
        Returns:
            價差（基點），或None
        """
        if not self.shard_feed:
            return None
        return self.shard_feed.get_spread_bps(symbol)
    
    def get_liquidity_score(self, symbol: str) -> float:
        """
        計算流動性評分（基於成交量+價差）
        
        Args:
            symbol: 交易對
        
        Returns:
            流動性評分（0-100）
        """
        score = 0.0
        
        # 1. 基於K線成交量
        kline = self.get_kline(symbol)
        if kline:
            quote_volume = kline.get('quote_volume', 0)
            trades = kline.get('trades', 0)
            
            if quote_volume > 1000000:  # >100萬USDT成交量
                score += 40
            elif quote_volume > 100000:  # >10萬USDT
                score += 20
            
            if trades > 1000:  # >1000筆交易
                score += 20
            elif trades > 100:  # >100筆
                score += 10
        
        # 2. 基於價差（越小越好）
        spread_bps = self.get_spread_bps(symbol)
        if spread_bps is not None:
            if spread_bps < 5:  # 價差<5bps（非常緊密）
                score += 40
            elif spread_bps < 10:  # 價差<10bps
                score += 20
            elif spread_bps < 20:  # 價差<20bps
                score += 10
        
        return min(score, 100.0)
    
    # ==================== 帳戶/倉位數據接口 ====================
    
    def get_account_position(self, symbol: str) -> Optional[Dict]:
        """
        獲取即時倉位數據
        
        Args:
            symbol: 交易對
        
        Returns:
            倉位數據，或None
        """
        if not self.account_feed:
            return None
        return self.account_feed.get_position(symbol)
    
    def get_all_positions(self) -> Dict[str, Dict]:
        """
        獲取所有倉位
        
        Returns:
            所有倉位數據的字典
        """
        if not self.account_feed:
            return {}
        return self.account_feed.get_all_positions()
    
    def get_account_balance(self, asset: str = 'USDT') -> Optional[Dict]:
        """
        獲取帳戶餘額（v3.17.2+ 格式轉換）
        
        將AccountFeed的原始數據轉換為UnifiedScheduler期望的格式
        
        Args:
            asset: 資產名稱
        
        Returns:
            餘額數據（與REST API格式一致），或None
            {
                'total_balance': float,
                'available_balance': float,
                'total_margin': float,
                'unrealized_pnl': float,
                'total_wallet_balance': float
            }
        """
        if not self.account_feed:
            return None
        
        # 從AccountFeed獲取原始數據
        account_data = self.account_feed.get_account_balance(asset)
        
        if not account_data:
            return None
        
        # 格式轉換（匹配REST API格式）
        # AccountFeed: {'balance': wb, 'cross_un_pnl': cw, ...}
        # REST API: {'total_balance': ..., 'available_balance': ..., ...}
        
        wallet_balance = account_data.get('balance', 0.0)  # 錢包餘額
        unrealized_pnl = account_data.get('cross_un_pnl', 0.0)  # 未實現盈虧
        
        # 從所有倉位計算已用保證金
        positions = self.get_all_positions()
        total_margin = 0.0
        
        for pos in positions.values():
            # 簡化計算：使用倉位的未實現盈虧作為保證金估算
            # 實際保證金 = |倉位價值| / 槓桿，但WebSocket不提供槓桿信息
            # 因此我們使用近似值
            pos_value = abs(pos.get('size', 0) * pos.get('entry_price', 0))
            if pos_value > 0:
                # 假設平均槓桿為10x（保守估計）
                total_margin += pos_value / 10.0
        
        available_balance = wallet_balance - total_margin
        
        return {
            'total_balance': wallet_balance,
            'available_balance': max(0.0, available_balance),  # 確保非負
            'total_margin': total_margin,
            'unrealized_pnl': unrealized_pnl,
            'total_wallet_balance': wallet_balance + unrealized_pnl
        }
    
    # ==================== 統計數據接口 ====================
    
    def get_stats(self) -> Dict:
        """
        獲取所有Feed的統計數據
        
        Returns:
            統計數據字典
        """
        stats = {
            'running': self.running,
            'symbols_count': len(self.symbols),
            'shard_size': self.shard_size
        }
        
        if self.shard_feed:
            stats['shard_feed'] = self.shard_feed.get_stats()
        
        if self.account_feed:
            stats['account_feed'] = self.account_feed.get_stats()
        
        return stats
    
    # ==================== 生命週期管理 ====================
    
    async def stop(self):
        """停止所有WebSocket Feed"""
        logger.info("⏸️  WebSocketManager 停止中...")
        self.running = False
        
        tasks = []
        
        # 停止ShardFeed
        if self.shard_feed:
            tasks.append(self.shard_feed.stop())
        
        # 停止AccountFeed
        if self.account_feed:
            tasks.append(self.account_feed.stop())
        
        # 並行停止所有Feed
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("✅ WebSocketManager 已停止")
