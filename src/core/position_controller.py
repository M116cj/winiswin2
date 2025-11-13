"""
PositionController v3.17.10+ - 24/7 倉位全權控制
職責：監控所有持倉、執行平倉決策、調整 SL/TP
整合：PositionMonitor24x7 處理進場失效和逆勢平倉
"""

import asyncio
from typing import List, Dict, Optional
import logging
from datetime import datetime
import os

import asyncpg  # 🔥 v4.4.1 P1: 異步數據庫操作（持久化持倉時間）

from src.core.position_monitor_24x7 import PositionMonitor24x7

logger = logging.getLogger(__name__)


class PositionController:
    """
    PositionController v3.17.2+ - 24/7 倉位全權控制
    
    職責：
    1. 每 60 秒監控所有持倉（v3.17.2+修改）
    2. 調用 SelfLearningTrader.evaluate_positions() 獲取決策
    3. 執行決策（平倉、調整 SL/TP 等）
    4. 記錄所有倉位操作
    
    核心原則：
    - 倉位操作使用 API 優先通道（priority=0）
    - 100% 虧損立即平倉（無條件）
    - 所有決策由 SelfLearningTrader 控制
    """
    
    def __init__(
        self,
        binance_client,
        self_learning_trader,
        monitor_interval: int = 60,  # v3.17.2+: 改為1分鐘
        config=None,
        trade_recorder=None,
        data_service=None,
        websocket_monitor=None  # 🔥 v3.17.11
    ):
        """
        初始化 PositionController
        
        Args:
            binance_client: Binance 客戶端
            self_learning_trader: SelfLearningTrader 實例
            monitor_interval: 監控間隔（秒），預設 60 秒（v3.17.2+）
            config: 配置對象
            trade_recorder: 交易記錄器（v3.17.10+）
            data_service: 數據服務（v3.17.10+）
            websocket_monitor: WebSocket監控器（v3.17.2+，優先使用WebSocket數據）
        """
        self.binance_client = binance_client
        self.trader = self_learning_trader
        self.monitor_interval = monitor_interval
        self.config = config
        self.trade_recorder = trade_recorder
        self.data_service = data_service
        self.websocket_monitor = websocket_monitor  # 🔥 v3.17.11
        
        # 🔥 v3.17.10+：整合 PositionMonitor24x7（進場失效 + 逆勢平倉）
        self.monitor_24x7 = PositionMonitor24x7(
            config_profile=config,
            binance_client=binance_client,
            trade_recorder=trade_recorder,
            data_service=data_service
        )
        
        # 控制器狀態
        self.is_running = False
        self.last_check_time = None
        
        # 統計數據
        self.stats = {
            'total_checks': 0,
            'total_closes': 0,
            'total_adjustments': 0,
            'emergency_closes': 0,  # 100% 虧損緊急平倉
            'cross_margin_protections': 0,  # 🔥 v3.18+：全倉保護平倉次數
            'time_based_stops': 0  # 🔥 v3.28+：時間基礎止損次數
        }
        
        # 🔥 v3.18+：全倉保護狀態追蹤
        self.last_cross_margin_protection_time = 0  # 上次觸發時間戳
        
        # 🔥 v3.28+：時間基礎止損追蹤
        self.position_entry_times = {}  # symbol -> entry_timestamp
        self.liquidating_symbols = set()  # 正在平倉的symbol集合（避免重複平倉）
        self.last_time_stop_check = 0  # 上次檢查時間戳
        
        # 🔥 v4.4.1 P1：數據庫連接（持久化持倉時間）
        self.db_pool: Optional[asyncpg.Pool] = None
        self._db_initialized = False
        
        logger.info("=" * 80)
        logger.info("✅ PositionController v3.28+ 初始化完成（全倉保護 + 時間止損）")
        logger.info(f"   ⏱️  監控間隔: {monitor_interval} 秒")
        logger.info("   🛡️  優先級: 0（最高優先級）")
        logger.info("   🚨 緊急平倉: PnL ≤ -99%")
        logger.info("   📡 WebSocket: {}".format("已啟用（優先使用）" if websocket_monitor else "未啟用（僅REST）"))
        logger.info("   🔥 整合 PositionMonitor24x7（進場失效 + 逆勢自動平倉）")
        if config and hasattr(config, 'CROSS_MARGIN_PROTECTOR_ENABLED') and config.CROSS_MARGIN_PROTECTOR_ENABLED:
            logger.info(f"   🛡️ 全倉保護: 啟用（{getattr(config, 'CROSS_MARGIN_PROTECTOR_THRESHOLD', 0.85):.0%} 閾值，{getattr(config, 'CROSS_MARGIN_PROTECTOR_COOLDOWN', 120)}秒冷卻）")
        else:
            logger.info("   🛡️ 全倉保護: 停用")
        if config and hasattr(config, 'TIME_BASED_STOP_LOSS_ENABLED') and config.TIME_BASED_STOP_LOSS_ENABLED:
            time_threshold_hours = getattr(config, 'TIME_BASED_STOP_LOSS_HOURS', 2.0)
            logger.info(f"   ⏰ 時間止損: v4.3.1 嚴格模式（持倉>{time_threshold_hours}小時→強制平倉，無論盈虧）")
        else:
            logger.info("   ⏰ 時間止損: 停用")
        logger.info("=" * 80)
    
    async def start_monitoring(self):
        """啟動 24/7 倉位監控（整合 PositionMonitor24x7，共享API調用）"""
        self.is_running = True
        logger.info("🚀 PositionController 24/7 監控已啟動（整合進場失效+逆勢檢測）")
        
        # 🔥 v4.4.1 P1：初始化數據庫連接並恢復持倉時間
        await self._initialize_database()
        await self._restore_position_entry_times()
        
        # 🔥 v3.17.10+：不再獨立啟動PositionMonitor24x7，改為共享API調用
        # 避免重複調用導致 HTTP 429 速率限制
        
        while self.is_running:
            try:
                await self._monitoring_cycle()
                await asyncio.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"❌ 監控週期失敗: {e}", exc_info=True)
                await asyncio.sleep(self.monitor_interval)
    
    async def stop_monitoring(self):
        """停止監控"""
        self.is_running = False
        
        logger.info("⏸️  PositionController 監控已停止")
        logger.info(f"   📊 統計: 檢查={self.stats['total_checks']}, "
                   f"平倉={self.stats['total_closes']}, "
                   f"調整={self.stats['total_adjustments']}, "
                   f"緊急平倉={self.stats['emergency_closes']}")
        
        # 🔥 v3.17.10+：顯示進場失效+逆勢平倉統計
        monitor_stats = self.monitor_24x7.get_monitor_stats()
        logger.info(f"   📊 自動平倉: 進場失效={monitor_stats.get('entry_reason_expired_closures', 0)}, "
                   f"逆勢無反彈={monitor_stats.get('counter_trend_closures', 0)}")
        
        # 🔥 v3.18+：顯示全倉保護統計
        if self.stats['cross_margin_protections'] > 0:
            logger.info(f"   🛡️ 全倉保護平倉: {self.stats['cross_margin_protections']} 次")
        
        # 🔥 v3.28+：顯示時間止損統計
        if self.stats['time_based_stops'] > 0:
            logger.info(f"   ⏰ 時間止損平倉: {self.stats['time_based_stops']} 次")
        
        # 🔥 v4.4.1 P1：關閉數據庫連接
        await self._close_database()
    
    async def _initialize_database(self):
        """
        🔥 v4.4.1 P1：初始化數據庫連接池
        """
        if self._db_initialized:
            return
        
        try:
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                logger.warning("⚠️ DATABASE_URL 未設置，持倉時間持久化功能禁用")
                return
            
            # 創建連接池（最小1個，最大5個連接）
            self.db_pool = await asyncpg.create_pool(
                database_url,
                min_size=1,
                max_size=5,
                timeout=30,
                command_timeout=10
            )
            
            self._db_initialized = True
            logger.info("✅ 數據庫連接池初始化成功（持倉時間持久化）")
            
        except Exception as e:
            logger.error(f"❌ 數據庫連接池初始化失敗: {e}，持倉時間持久化功能禁用")
            self.db_pool = None
            self._db_initialized = False
    
    async def _close_database(self):
        """
        🔥 v4.4.1 P1：關閉數據庫連接池
        """
        if self.db_pool:
            try:
                await self.db_pool.close()
                logger.info("✅ 數據庫連接池已關閉")
            except Exception as e:
                logger.error(f"❌ 關閉數據庫連接池失敗: {e}")
            finally:
                self.db_pool = None
                self._db_initialized = False
    
    async def _restore_position_entry_times(self):
        """
        🔥 v4.4.1 P1：從數據庫恢復持倉開仓時間（防止系統重啟計時重置）
        """
        if not self._db_initialized or not self.db_pool:
            logger.debug("數據庫未初始化，跳過持倉時間恢復")
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT symbol, entry_time FROM position_entry_times"
                )
                
                if rows:
                    for row in rows:
                        self.position_entry_times[row['symbol']] = row['entry_time']
                    
                    logger.info(
                        f"✅ 從數據庫恢復 {len(rows)} 個持倉開倉時間 "
                        f"(symbols: {', '.join([r['symbol'] for r in rows])})"
                    )
                else:
                    logger.debug("數據庫中無持倉時間記錄")
                    
        except Exception as e:
            logger.error(f"❌ 恢復持倉時間失敗: {e}", exc_info=True)
    
    async def _persist_entry_time(self, symbol: str, entry_time: float):
        """
        🔥 v4.4.1 P1：持久化持倉開倉時間到數據庫
        
        Args:
            symbol: 交易對符號
            entry_time: 開倉時間戳（Unix秒）
        """
        if not self._db_initialized or not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO position_entry_times (symbol, entry_time, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP)
                    ON CONFLICT (symbol)
                    DO UPDATE SET entry_time = $2, updated_at = CURRENT_TIMESTAMP
                    """,
                    symbol, entry_time
                )
                logger.debug(f"💾 持倉時間已持久化: {symbol} @ {entry_time}")
                
        except Exception as e:
            logger.error(f"❌ 持久化持倉時間失敗 ({symbol}): {e}")
    
    async def _delete_entry_time(self, symbol: str):
        """
        🔥 v4.4.1 P1：從數據庫刪除持倉開倉時間（平倉後清理）
        
        Args:
            symbol: 交易對符號
        """
        if not self._db_initialized or not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM position_entry_times WHERE symbol = $1",
                    symbol
                )
                logger.debug(f"🗑️  持倉時間已刪除: {symbol}")
                
        except Exception as e:
            logger.error(f"❌ 刪除持倉時間失敗 ({symbol}): {e}")
    
    async def _monitoring_cycle(self):
        """單次監控週期（整合PositionMonitor24x7檢測，共享API調用）"""
        try:
            self.stats['total_checks'] += 1
            self.last_check_time = datetime.now()
            
            # 步驟 1：獲取所有持倉（優先級 0）- 共享給兩個監控器
            positions = await self._fetch_all_positions()
            
            if not positions:
                logger.info("   📭 當前無持倉")
                return
            
            logger.info(f"   📊 監控 {len(positions)} 個持倉")
            
            # 🔥 v3.17.10+：優先執行PositionMonitor24x7檢測（進場失效+逆勢平倉）
            # 共享同一次API調用結果，避免HTTP 429速率限制
            await self.monitor_24x7.check_positions_with_data(positions)
            
            # 🔥 v3.18+：全倉保護檢查（在trader評估之前執行，Priority 0）
            # 防止虧損稀釋10%預留緩衝，立即市價平倉虧損最大倉位
            cross_margin_protected = await self._check_cross_margin_protection(positions)
            
            # 🔥 v3.28+ / v4.3.1：時間基礎止損檢查（每1分鐘檢查一次）
            # 持倉超過閾值時間（默認2小時），自動市價平倉（v4.3.1: 無論盈虧都平倉）
            time_based_closes = await self._check_time_based_stop_loss(positions)
            if cross_margin_protected:
                # 如果執行了全倉保護平倉，重新獲取倉位列表
                logger.info("🛡️ 全倉保護已執行，重新獲取倉位列表")
                positions = await self._fetch_all_positions()
                if not positions:
                    logger.debug("   📭 平倉後無剩餘持倉")
                    return
            
            # 步驟 2：調用 SelfLearningTrader 評估持倉
            decisions = await self.trader.evaluate_positions(positions)
            
            # 步驟 3：執行決策
            for position_id, decision in decisions.items():
                await self._execute_decision(position_id, decision, positions)
            
        except Exception as e:
            logger.error(f"❌ 監控週期執行失敗: {e}", exc_info=True)
    
    async def _fetch_all_positions(self) -> List[Dict]:
        """
        獲取所有持倉（v3.17.2+：WebSocket優先，REST備援）
        
        Returns:
            持倉列表，每個持倉包含：
            - symbol: 交易對
            - side: 方向（'LONG' 或 'SHORT'）
            - size: 數量
            - entry_price: 入場價格
            - current_price: 當前價格
            - pnl: 盈虧（USDT）
            - pnl_pct: 盈虧百分比
            - leverage: 槓桿
        """
        try:
            raw_positions = []
            
            # 🔥 v3.17.2+：優先使用WebSocket帳戶Feed
            if self.websocket_monitor:
                ws_positions = self.websocket_monitor.get_all_positions()
                if ws_positions:
                    logger.info(f"📡 從WebSocket獲取 {len(ws_positions)} 個倉位")
                    # 將WebSocket格式轉換為標準格式
                    for symbol, pos_data in ws_positions.items():
                        raw_positions.append({
                            'symbol': pos_data['symbol'],
                            'positionAmt': str(pos_data['size']),
                            'entryPrice': str(pos_data['entry_price']),
                            'unRealizedProfit': str(pos_data.get('unrealized_pnl', 0)),
                            'leverage': '1',
                            'is_websocket_data': True
                        })
            
            # 🔥 v3.17.2+：備援 - 使用REST API
            if not raw_positions:
                logger.info("📡 WebSocket無倉位數據，使用REST API備援")
                raw_positions = await self.binance_client.get_position_info_async()
            
            positions = []
            for pos in raw_positions:
                # 過濾空倉位
                position_amt = float(pos.get('positionAmt', 0))
                if abs(position_amt) < 0.0001:
                    continue
                
                symbol = pos.get('symbol', 'UNKNOWN')
                entry_price = float(pos.get('entryPrice', 0))
                leverage = float(pos.get('leverage', 1))
                
                # 🔥 v3.23+ 修復：優先使用API直接提供的unrealized PnL（準確且高效）
                # 但確保PnL值合理，避免WebSocket數據未更新導致PnL=0的問題
                if 'unRealizedProfit' in pos:
                    pnl = float(pos.get('unRealizedProfit', 0))
                    # 從倉位金額判斷方向
                    side = 'LONG' if position_amt > 0 else 'SHORT'
                    
                    # 🔥 v3.23+ 修復：如果PnL=0但倉位存在，使用markPrice重新計算
                    # 避免WebSocket數據未更新導致虧損倉位被誤判為盈虧平衡
                    if pnl == 0 and 'markPrice' in pos:
                        current_price = float(pos.get('markPrice', entry_price))
                        if position_amt > 0:  # LONG
                            pnl = (current_price - entry_price) * position_amt
                        else:  # SHORT
                            pnl = (entry_price - current_price) * abs(position_amt)
                        logger.debug(
                            f"🔄 {symbol} WebSocket PnL=0，使用markPrice重新計算: ${pnl:+.2f}"
                        )
                    
                    # 使用unrealizedPnL時，current_price需反推（僅用於顯示）
                    if position_amt > 0:  # LONG
                        current_price = entry_price + (pnl / position_amt) if position_amt != 0 else entry_price
                    else:  # SHORT
                        current_price = entry_price - (pnl / abs(position_amt)) if position_amt != 0 else entry_price
                else:
                    # 備援：使用markPrice計算PnL（REST API fallback）
                    current_price = float(pos.get('markPrice') or pos.get('entryPrice', 0))
                    if position_amt > 0:  # LONG
                        pnl = (current_price - entry_price) * position_amt
                        side = 'LONG'
                    else:  # SHORT
                        pnl = (entry_price - current_price) * abs(position_amt)
                        side = 'SHORT'
                
                # 計算 PnL 百分比（基於初始保證金）
                notional = abs(position_amt) * entry_price
                margin = notional / leverage
                pnl_pct = pnl / margin if margin > 0 else 0.0
                
                positions.append({
                    'id': f"{symbol}_{side}",
                    'symbol': symbol,
                    'side': side,
                    'size': abs(position_amt),
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'leverage': leverage,
                    'raw_data': pos
                })
            
            return positions
            
        except Exception as e:
            logger.error(f"❌ 獲取持倉失敗: {e}", exc_info=True)
            return []
    
    async def _check_cross_margin_protection(self, positions: List[Dict]) -> bool:
        """
        🔥 v3.18+ 全倉保護檢查（防止虧損稀釋10%預留緩衝）
        
        檢查邏輯：
        1. 獲取帳戶總金額（total_balance）和總保證金（total_margin）
        2. 計算保證金使用率 = total_margin / total_balance
        3. 如果使用率 > 85%（90%上限前5%預警）且存在虧損倉位：
           - 找出虧損最大的倉位
           - 立即市價平倉（Priority 0）
           - 記錄冷卻時間戳，防止重複觸發
        
        Args:
            positions: 當前所有持倉列表
        
        Returns:
            bool: 是否執行了平倉操作
        """
        # 檢查配置是否啟用
        if not self.config or not getattr(self.config, 'CROSS_MARGIN_PROTECTOR_ENABLED', False):
            return False
        
        try:
            import time
            
            # 步驟1：檢查冷卻時間
            cooldown = getattr(self.config, 'CROSS_MARGIN_PROTECTOR_COOLDOWN', 120)
            current_time = time.time()
            if current_time - self.last_cross_margin_protection_time < cooldown:
                time_left = int(cooldown - (current_time - self.last_cross_margin_protection_time))
                logger.info(f"🛡️ 全倉保護冷卻中，剩餘 {time_left} 秒")
                return False
            
            # 步驟2：獲取帳戶餘額（🔥 v3.18.4：優先使用REST API，確保數據準確性）
            # WebSocket的cw字段可能不等於available_balance，導致保證金計算錯誤
            account_info = None
            data_source = "REST"
            
            try:
                # 優先使用REST API（確保準確性）
                account_info = await self.binance_client.get_account_balance()
                
                # 備援：如果REST失敗，嘗試WebSocket（但可能不準確）
                if not account_info and self.websocket_monitor:
                    account_info = self.websocket_monitor.get_account_balance()
                    data_source = "WebSocket（備援）"
                    logger.debug("⚠️ REST API失敗，使用WebSocket備援數據")
                
            except Exception as e:
                logger.warning(f"⚠️ 獲取REST帳戶信息失敗: {e}")
                # 最後備援：使用WebSocket
                if self.websocket_monitor:
                    account_info = self.websocket_monitor.get_account_balance()
                    data_source = "WebSocket（備援）"
            
            if not account_info:
                logger.warning("⚠️ 無法獲取帳戶信息（REST和WebSocket都失敗），跳過全倉保護檢查")
                return False
            
            # 步驟3：計算總金額和總保證金
            total_balance = float(account_info.get('total_balance', 0))
            total_margin = float(account_info.get('total_margin', 0))
            
            # 🔥 v3.18.4：記錄數據來源和原始數據（用於調試）
            logger.debug(
                f"🔍 帳戶數據來源: {data_source} | "
                f"total_balance={total_balance:.2f}, "
                f"total_margin={total_margin:.2f}"
            )
            
            if total_balance <= 0:
                logger.warning(f"⚠️ 帳戶總金額異常: ${total_balance:.2f}")
                return False
            
            # 步驟4：計算保證金使用率
            margin_usage_ratio = total_margin / total_balance
            threshold = getattr(self.config, 'CROSS_MARGIN_PROTECTOR_THRESHOLD', 0.85)
            
            # 🔥 v3.18.4：計算每個倉位的保證金使用（用於詳細日誌）
            position_margins = []
            for p in positions:
                # 計算倉位保證金 = abs(size × entry_price / leverage)
                try:
                    size = abs(float(p.get('size', 0)))
                    entry_price = float(p.get('entry_price', 0))
                    leverage = float(p.get('leverage', 1))
                    position_margin = (size * entry_price) / leverage if leverage > 0 else 0
                    position_margins.append({
                        'symbol': p.get('symbol', 'UNKNOWN'),
                        'margin': position_margin,
                        'pnl': float(p.get('pnl', 0))
                    })
                except Exception as e:
                    logger.debug(f"⚠️ 計算倉位保證金失敗 {p.get('symbol')}: {e}")
            
            # 排序（保證金最大的在前）
            position_margins.sort(key=lambda x: x['margin'], reverse=True)
            
            logger.info(
                f"🛡️ 全倉保護檢查 | "
                f"保證金使用率: {margin_usage_ratio:.1%} | "
                f"閾值: {threshold:.0%} | "
                f"總金額: ${total_balance:.2f} | "
                f"總保證金: ${total_margin:.2f}"
            )
            
            # 🔥 v3.18.4：詳細日誌（顯示前5個最大保證金倉位）
            if position_margins and len(positions) > 0:
                logger.debug(f"📊 倉位保證金分布（前5）：")
                for pm in position_margins[:5]:
                    logger.debug(
                        f"   • {pm['symbol']}: ${pm['margin']:.2f} "
                        f"(PnL: ${pm['pnl']:+.2f})"
                    )
            
            # 步驟5：判斷是否觸發保護條件
            if margin_usage_ratio <= threshold:
                return False
            
            # 步驟6：篩選虧損倉位（🔥 v3.23+ 修復：使用pnl_pct檢測）
            # 🔥 修復：同時檢查pnl和pnl_pct，確保捕獲所有虧損倉位
            losing_positions = [
                p for p in positions 
                if p.get('pnl', 0) < 0 or p.get('pnl_pct', 0) < 0
            ]
            
            if not losing_positions:
                # 🔥 v3.23+ 修復：詳細日誌，幫助診斷
                logger.info(
                    f"🛡️ 保證金使用率 {margin_usage_ratio:.1%} > {threshold:.0%} "
                    f"但無虧損倉位，無需保護"
                )
                logger.debug(f"📊 當前倉位PnL詳情：")
                for p in positions[:5]:  # 只顯示前5個
                    logger.debug(
                        f"   • {p['symbol']} {p['side']}: "
                        f"PnL=${p.get('pnl', 0):+.2f} ({p.get('pnl_pct', 0):+.2%})"
                    )
                return False
            
            # 步驟7：找出虧損最大的倉位（絕對金額）
            worst_position = min(losing_positions, key=lambda p: p['pnl'])
            
            logger.critical(
                f"🚨🛡️ 全倉保護觸發！保證金使用率 {margin_usage_ratio:.1%} > {threshold:.0%}"
            )
            logger.critical(
                f"   📊 帳戶狀態: 總金額=${total_balance:.2f}, "
                f"總保證金=${total_margin:.2f} ({margin_usage_ratio:.1%})"
            )
            logger.critical(
                f"   🎯 目標倉位: {worst_position['symbol']} {worst_position['side']} | "
                f"虧損=${worst_position['pnl']:.2f} ({worst_position['pnl_pct']:.1%})"
            )
            logger.critical(
                f"   ⚡ 執行動作: 立即市價平倉保護10%預留緩衝"
            )
            
            # 步驟8：執行市價平倉（Priority 0，最高優先級）
            success = await self._force_close_for_cross_margin_protection(worst_position)
            
            if success:
                # 記錄成功平倉
                self.stats['cross_margin_protections'] += 1
                self.last_cross_margin_protection_time = current_time
                
                logger.critical(
                    f"✅ 全倉保護平倉成功 | "
                    f"{worst_position['symbol']} 虧損${worst_position['pnl']:.2f} 已清除 | "
                    f"冷卻{cooldown}秒"
                )
                return True
            else:
                logger.error(
                    f"❌ 全倉保護平倉失敗: {worst_position['symbol']}"
                )
                return False
                
        except Exception as e:
            logger.error(f"❌ 全倉保護檢查異常: {e}", exc_info=True)
            return False
    
    async def _force_close_for_cross_margin_protection(self, position: Dict) -> bool:
        """
        全倉保護強制平倉（市價單，Priority 0）
        
        依照Binance API官方協議：
        - Hedge Mode: 使用 positionSide 參數（reduceOnly不能用）
        - One-Way Mode: 使用 reduceOnly="true" 參數
        
        Args:
            position: 要平倉的倉位信息
        
        Returns:
            bool: 是否成功平倉
        """
        symbol = position.get('symbol', 'UNKNOWN')
        try:
            # 平倉方向：LONG倉用SELL平，SHORT倉用BUY平
            side = "SELL" if position['side'] == "LONG" else "BUY"
            quantity = position['size']
            position_side = position['side']  # "LONG" 或 "SHORT"
            
            logger.critical(
                f"🚨 執行全倉保護平倉: {symbol} {side} {quantity} (倉位方向: {position_side}) | "
                f"原因: 保證金使用率過高+虧損稀釋預留緩衝"
            )
            
            # 檢測Position Mode
            is_hedge_mode = await self.binance_client.get_position_mode()
            
            # 依照Binance API協議構建參數
            order_params = {}
            if is_hedge_mode:
                # Hedge Mode: 必須使用positionSide，不能用reduceOnly
                # 平LONG倉: side=SELL + positionSide=LONG
                # 平SHORT倉: side=BUY + positionSide=SHORT
                order_params['positionSide'] = position_side
                logger.info(f"  Hedge Mode: positionSide={position_side}")
            else:
                # One-Way Mode: 使用reduceOnly="true"（字符串，不是Boolean）
                order_params['reduceOnly'] = "true"
                logger.info("  One-Way Mode: reduceOnly=\"true\"")
            
            # 🔥 v3.18.4-Critical: 使用CRITICAL優先級，確保即使熔斷器阻斷也能平倉
            from src.core.circuit_breaker import Priority
            
            # 使用市價單立即平倉（CRITICAL優先級 + 白名單操作）
            result = await self.binance_client.place_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
                priority=Priority.CRITICAL,
                operation_type="close_position",
                **order_params
            )
            
            if result:
                logger.critical(
                    f"✅ 全倉保護平倉訂單提交成功: {symbol} (訂單ID: {result.get('orderId')})"
                )
                
                # 🔥 v3.18.4+：記錄到TradeRecorder（使用record_exit）
                if self.trade_recorder:
                    try:
                        trade_result = {
                            'symbol': symbol,
                            'direction': side,
                            'entry_price': position.get('entry_price'),
                            'exit_price': position.get('current_price'),
                            'pnl': position.get('pnl', 0),
                            'pnl_pct': position.get('pnl_pct', 0),
                            'close_reason': f"cross_margin_protection (loss ${position['pnl']:.2f})",
                            'close_timestamp': datetime.now(),
                            'order_id': result.get('orderId')
                        }
                        
                        self.trade_recorder.record_exit(trade_result)
                        logger.info(
                            f"📝 全倉保護平倉已記錄: {symbol} {side} {quantity} @ "
                            f"{position['current_price']} | 虧損${position['pnl']:.2f}"
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ 記錄全倉保護平倉失敗: {e}")
                
                # 🔥 v4.4.1 P1：從開倉時間記錄和數據庫中移除（清理持久化記錄）
                if symbol in self.position_entry_times:
                    del self.position_entry_times[symbol]
                    await self._delete_entry_time(symbol)
                
                return True
            else:
                return False
                
        except Exception as e:
            logger.critical(f"❌ 全倉保護平倉異常: {symbol} - {e}", exc_info=True)
            return False
    
    async def _check_time_based_stop_loss(self, positions: List[Dict]) -> int:
        """
        🔥 v3.28+ / v4.3.1 基於時間的強制止損檢查（嚴格模式）
        
        檢查邏輯：
        1. 遍歷所有持倉，記錄/更新開倉時間
        2. 檢查持倉時間是否超過閾值（默認2小時）
        3. 🔥 v4.3.1: 無論盈虧，只要超時就觸發市價平倉（移除盈利豁免）
        
        Args:
            positions: 當前所有持倉列表
        
        Returns:
            int: 執行平倉的數量
        """
        # 檢查配置是否啟用
        if not self.config or not getattr(self.config, 'TIME_BASED_STOP_LOSS_ENABLED', False):
            return 0
        
        try:
            import time
            
            # 步驟1：檢查是否需要執行檢查（避免過於頻繁）
            check_interval = getattr(self.config, 'TIME_BASED_STOP_LOSS_CHECK_INTERVAL', 300)
            current_time = time.time()
            
            if current_time - self.last_time_stop_check < check_interval:
                return 0
            
            self.last_time_stop_check = current_time
            
            # 步驟2：獲取時間閾值（小時）
            time_threshold_hours = getattr(self.config, 'TIME_BASED_STOP_LOSS_HOURS', 2.0)
            time_threshold_seconds = time_threshold_hours * 3600
            
            closed_count = 0
            
            # 步驟3：遍歷所有持倉
            for position in positions:
                symbol = position.get('symbol', 'UNKNOWN')
                
                # 跳過已在平倉中的symbol
                if symbol in self.liquidating_symbols:
                    continue
                
                # 🔥 Critical: 檢查持倉數量，跳過已平倉位
                size = abs(float(position.get('size', 0)))
                if size < 0.00001:  # 考慮浮點誤差
                    # 如果持倉已平倉，從記錄中移除
                    if symbol in self.position_entry_times:
                        del self.position_entry_times[symbol]
                    continue
                
                # 步驟4：記錄或獲取開倉時間
                if symbol not in self.position_entry_times:
                    # 首次發現此持倉，記錄當前時間為開倉時間
                    self.position_entry_times[symbol] = current_time
                    logger.debug(f"⏰ 記錄持倉開倉時間: {symbol} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # 🔥 v4.4.1 P1：持久化到數據庫（防止重啟計時重置）
                    await self._persist_entry_time(symbol, current_time)
                    
                    continue  # 剛開倉，無需檢查
                
                entry_time = self.position_entry_times[symbol]
                holding_time = current_time - entry_time
                
                # 步驟5：檢查持倉時間是否超過閾值
                if holding_time < time_threshold_seconds:
                    continue  # 未超時
                
                # 步驟6：獲取當前價格並計算未實現盈虧
                current_price = position.get('current_price')
                entry_price = position.get('entry_price')
                side = position.get('side', 'UNKNOWN')
                
                # 計算未實現盈虧
                unrealized_pnl = position.get('pnl', 0)
                
                # 如果pnl不可用，嘗試手動計算
                if unrealized_pnl == 0 and current_price and entry_price:
                    if side == 'LONG':
                        unrealized_pnl = (float(current_price) - float(entry_price)) * size
                    elif side == 'SHORT':
                        unrealized_pnl = (float(entry_price) - float(current_price)) * size
                
                # 🔥 v4.3.1 修复：移除盈利豁免逻辑
                # 原逻辑Bug：盈利仓位可以无限期持有（违背2小时严格限制）
                # 新逻辑：超过2小时，无论盈亏都强制平仓
                
                # 步驟7：觸發時間基礎強制止損（无论盈亏）
                holding_hours = holding_time / 3600
                pnl_status = "盈利" if unrealized_pnl >= 0 else "虧損"
                logger.warning(
                    f"🔴⏰ 時間止損觸發: {symbol} {side} | "
                    f"持倉時間 {holding_hours:.2f} 小時 > {time_threshold_hours} 小時 | "
                    f"{pnl_status} ${unrealized_pnl:.2f}"
                )
                
                # 異步執行平倉（不阻塞其他檢查）
                success = await self._force_close_time_based(position, holding_hours)
                if success:
                    closed_count += 1
            
            return closed_count
            
        except Exception as e:
            logger.error(f"❌ 時間止損檢查異常: {e}", exc_info=True)
            return 0
    
    async def _force_close_time_based(self, position: Dict, holding_hours: float) -> bool:
        """
        🔥 v4.4.1 P2: 時間基礎強制平倉（市價單，Priority CRITICAL，帶重試機制）
        
        Args:
            position: 要平倉的倉位信息
            holding_hours: 持倉時間（小時）
        
        Returns:
            bool: 是否成功平倉
        """
        symbol = position.get('symbol', 'UNKNOWN')
        
        # 防止重複平倉
        if symbol in self.liquidating_symbols:
            return False
        
        self.liquidating_symbols.add(symbol)
        
        try:
            # 平倉方向：LONG倉用SELL平，SHORT倉用BUY平
            side = "SELL" if position['side'] == "LONG" else "BUY"
            quantity = position['size']
            position_side = position['side']  # "LONG" 或 "SHORT"
            
            # 獲取盈虧狀態
            pnl = position.get('pnl', 0)
            pnl_status = "盈利" if pnl >= 0 else "虧損"
            
            logger.warning(
                f"🚨⏰ 執行時間止損平倉: {symbol} {side} {quantity} (倉位方向: {position_side}) | "
                f"原因: 持倉{holding_hours:.2f}小時（{pnl_status}${pnl:.2f}）"
            )
            
            # 檢測Position Mode
            is_hedge_mode = await self.binance_client.get_position_mode()
            
            # 依照Binance API協議構建參數
            order_params = {}
            if is_hedge_mode:
                order_params['positionSide'] = position_side
                logger.info(f"  Hedge Mode: positionSide={position_side}")
            else:
                order_params['reduceOnly'] = "true"
                logger.info("  One-Way Mode: reduceOnly=\"true\"")
            
            # 🔥 v4.4.1 Critical Fix: 使用CRITICAL優先級確保bypass熔斷器
            # Bug: HIGH優先級在熔斷器BLOCKED時會被阻斷，導致時間止損失效
            # Fix: 改用CRITICAL優先級（與全倉保護一致），確保任何情況下都能平倉
            from src.core.circuit_breaker import Priority
            
            # 🔥 v4.4.1 P2：添加重試機制（最多3次，指數退避）
            max_retries = 3
            result = None
            
            for attempt in range(max_retries):
                try:
                    # 使用市價單立即平倉（CRITICAL優先級 + 白名單操作）
                    result = await self.binance_client.place_order(
                        symbol=symbol,
                        side=side,
                        order_type="MARKET",
                        quantity=quantity,
                        priority=Priority.CRITICAL,  # ✅ v4.4.1: HIGH→CRITICAL（确保bypass熔断器BLOCKED）
                        operation_type="close_position",
                        **order_params
                    )
                    
                    if result:
                        # 成功，跳出重試循環
                        break
                    else:
                        # 失敗但無異常，等待後重試
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt  # 1s, 2s, 4s (指數退避)
                            logger.warning(
                                f"⚠️ 時間止損平倉失敗（{symbol}），{wait_time}秒後重試 "
                                f"({attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(wait_time)
                        else:
                            logger.error(f"❌ 時間止損平倉重試{max_retries}次後仍失敗: {symbol}")
                            
                except Exception as e:
                    logger.error(f"❌ 時間止損平倉異常 ({symbol}, 嘗試{attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 指數退避
                        logger.warning(f"⚠️ {wait_time}秒後重試...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.critical(f"🔴 時間止損平倉重試{max_retries}次後仍異常: {symbol}")
                        raise  # 重新拋出最後一次異常
            
            if result:
                logger.warning(
                    f"✅⏰ 時間止損平倉訂單提交成功: {symbol} (訂單ID: {result.get('orderId')})"
                )
                
                # 記錄到TradeRecorder
                if self.trade_recorder:
                    try:
                        trade_result = {
                            'symbol': symbol,
                            'direction': side,
                            'entry_price': position.get('entry_price'),
                            'exit_price': position.get('current_price'),
                            'pnl': position.get('pnl', 0),
                            'pnl_pct': position.get('pnl_pct', 0),
                            'close_reason': f"time_based_stop_loss_v4.3.1 ({holding_hours:.2f}h, {pnl_status} ${pnl:.2f})",
                            'close_timestamp': datetime.now(),
                            'order_id': result.get('orderId')
                        }
                        
                        self.trade_recorder.record_exit(trade_result)
                        logger.info(
                            f"📝 時間止損平倉已記錄: {symbol} {side} {quantity} | "
                            f"持倉{holding_hours:.2f}h | 虧損${position['pnl']:.2f}"
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ 記錄時間止損平倉失敗: {e}")
                
                # 統計
                self.stats['time_based_stops'] += 1
                
                # 從開倉時間記錄中移除
                if symbol in self.position_entry_times:
                    del self.position_entry_times[symbol]
                    
                    # 🔥 v4.4.1 P1：從數據庫刪除（清理持久化記錄）
                    await self._delete_entry_time(symbol)
                
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ 時間止損平倉異常: {symbol} - {e}", exc_info=True)
            return False
        finally:
            # 無論成功失敗，都從liquidating集合中移除
            self.liquidating_symbols.discard(symbol)
    
    async def _execute_decision(
        self,
        position_id: str,
        decision: str,
        positions: List[Dict]
    ):
        """
        執行決策
        
        Args:
            position_id: 持倉 ID
            decision: 決策（'HOLD', 'CLOSE', 'ADJUST_SL', 'ADJUST_TP'）
            positions: 所有持倉列表
        """
        try:
            # 查找對應持倉
            position = next((p for p in positions if p['id'] == position_id), None)
            if not position:
                logger.warning(f"⚠️ 持倉 {position_id} 未找到")
                return
            
            if decision == 'HOLD':
                # 持續持有
                pass
            
            elif decision == 'CLOSE':
                # 平倉
                decision_info = {
                    'reason': 'auto_close',
                    'decision_type': decision
                }
                await self._close_position(position, decision=decision_info)
                self.stats['total_closes'] += 1
                
                # 檢查是否為緊急平倉
                if position['pnl_pct'] <= -0.99:
                    self.stats['emergency_closes'] += 1
            
            elif decision == 'ADJUST_SL':
                # 調整止損
                await self._adjust_stop_loss(position)
                self.stats['total_adjustments'] += 1
            
            elif decision == 'ADJUST_TP':
                # 調整止盈
                await self._adjust_take_profit(position)
                self.stats['total_adjustments'] += 1
            
            else:
                logger.warning(f"⚠️ 未知決策: {decision}")
        
        except Exception as e:
            logger.error(f"❌ 執行決策失敗 ({position_id}): {e}", exc_info=True)
    
    async def _close_position(self, position: Dict, decision: Optional[Dict] = None):
        """
        平倉（使用優先通道，符合Binance API協議）
        
        依照Binance API官方協議：
        - Hedge Mode: 使用 positionSide 參數
        - One-Way Mode: 使用 reduceOnly="true" 參數
        
        Args:
            position: 持倉信息
            decision: 決策信息（包含close_reason等）
        """
        try:
            symbol = position['symbol']
            side = position['side']  # "LONG" 或 "SHORT"
            size = position['size']
            
            # 確定平倉方向：LONG用SELL平，SHORT用BUY平
            close_side = 'SELL' if side == 'LONG' else 'BUY'
            
            logger.info(
                f"🔴 平倉: {symbol} {side} | 數量={size:.6f} | "
                f"PnL={position['pnl']:.2f} USDT ({position['pnl_pct']:.2%})"
            )
            
            # 檢測Position Mode
            is_hedge_mode = await self.binance_client.get_position_mode()
            
            # 依照Binance API協議構建參數
            order_params = {}
            if is_hedge_mode:
                # Hedge Mode: 使用positionSide
                order_params['positionSide'] = side
                logger.info(f"  📍 Hedge Mode: side={close_side}, positionSide={side}")
            else:
                # One-Way Mode: 使用reduceOnly="true"（字符串）
                order_params['reduceOnly'] = "true"
                logger.info(f"  📍 One-Way Mode: side={close_side}, reduceOnly=\"true\"")
            
            # 使用市價單平倉
            result = await self.binance_client.place_order(
                symbol=symbol,
                side=close_side,
                order_type='MARKET',
                quantity=size,
                **order_params
            )
            
            logger.info(f"✅ 平倉成功: {symbol} | 訂單 ID={result.get('orderId')}")
            
            # 🔥 v4.4.1 P1：從開倉時間記錄和數據庫中移除（清理持久化記錄）
            if symbol in self.position_entry_times:
                del self.position_entry_times[symbol]
                await self._delete_entry_time(symbol)
            
            # 🔥 v3.27+ 診斷日誌：檢查trade_recorder狀態
            logger.info(f"🔍 [DIAG] trade_recorder存在: {self.trade_recorder is not None}")
            logger.info(f"🔍 [DIAG] result存在: {result is not None}")
            
            # 🔥 v3.18.4+：記錄平倉數據到TradeRecorder（ML學習關鍵）
            if self.trade_recorder and result:
                try:
                    logger.info(f"🔍 [DIAG] 準備調用record_exit: {symbol}")
                    trade_result = {
                        'symbol': symbol,
                        'direction': side,
                        'entry_price': position.get('entry_price'),
                        'exit_price': position.get('current_price'),
                        'pnl': position.get('pnl', 0),
                        'pnl_pct': position.get('pnl_pct', 0),
                        'close_reason': decision.get('reason', 'manual_close') if decision else 'manual_close',
                        'close_timestamp': datetime.now(),
                        'order_id': result.get('orderId')
                    }
                    
                    logger.info(f"🔍 [DIAG] 調用record_exit: trade_result={trade_result}")
                    self.trade_recorder.record_exit(trade_result)
                    logger.info(f"📝 已記錄平倉: {symbol} | PnL: {position.get('pnl', 0):+.2f} USDT ({position.get('pnl_pct', 0):+.2%})")
                except Exception as e:
                    logger.error(f"❌ 記錄平倉數據失敗: {e}", exc_info=True)
                    logger.error(f"🔍 [DIAG] 異常堆棧已記錄")
            else:
                if not self.trade_recorder:
                    logger.warning(f"⚠️ trade_recorder為None，無法記錄交易")
                if not result:
                    logger.warning(f"⚠️ 平倉result為None，無法記錄交易")
            
        except Exception as e:
            logger.error(f"❌ 平倉失敗 ({position['symbol']}): {e}", exc_info=True)
    
    async def _adjust_stop_loss(self, position: Dict):
        """
        調整止損
        
        Args:
            position: 持倉信息
        """
        try:
            symbol = position['symbol']
            logger.info(f"🔧 調整止損: {symbol}")
            
            # TODO: 實現止損調整邏輯
            # 例如：移動止損、追蹤止損等
            
        except Exception as e:
            logger.error(f"❌ 調整止損失敗 ({position['symbol']}): {e}", exc_info=True)
    
    async def _get_current_price(self, symbol: str) -> float:
        """
        獲取當前價格（優先使用WebSocket，失敗時回退到REST API）
        
        Args:
            symbol: 交易對
        
        Returns:
            當前價格
        """
        # 🔥 v3.17.11：優先使用WebSocket數據
        if self.websocket_monitor:
            price = self.websocket_monitor.get_price(symbol)
            if price is not None:
                logger.debug(f"💡 {symbol} WebSocket價格: ${price:.2f}")
                return price
            else:
                logger.debug(f"⚠️ {symbol} WebSocket無數據，使用REST備援")
        
        # 備援：REST API
        try:
            ticker = await self.binance_client.get_ticker(symbol)
            price = float(ticker.get('lastPrice', 0))
            if price > 0:
                logger.debug(f"📡 {symbol} REST API價格: ${price:.2f}")
                return price
            else:
                # ⚠️ 0.0不是合法價格，拋出異常
                raise ValueError(f"{symbol} REST API返回無效價格: {price}")
        except Exception as e:
            # 🔥 v3.17.11：價格獲取失敗時拋出異常，不返回0.0
            logger.error(f"❌ 獲取{symbol}價格失敗（WebSocket+REST均失敗）: {e}")
            raise  # 向上傳播異常，讓調用者處理
    
    async def _adjust_take_profit(self, position: Dict):
        """
        調整止盈
        
        Args:
            position: 持倉信息
        """
        try:
            symbol = position['symbol']
            logger.info(f"🔧 調整止盈: {symbol}")
            
            # TODO: 實現止盈調整邏輯
            # 例如：部分止盈、移動止盈等
            
        except Exception as e:
            logger.error(f"❌ 調整止盈失敗 ({position['symbol']}): {e}", exc_info=True)
    
    def get_stats(self) -> Dict:
        """獲取控制器統計數據"""
        return {
            **self.stats,
            'is_running': self.is_running,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None
        }
