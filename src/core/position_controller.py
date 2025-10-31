"""
PositionController v3.17.10+ - 24/7 倉位全權控制
職責：監控所有持倉、執行平倉決策、調整 SL/TP
整合：PositionMonitor24x7 處理進場失效和逆勢平倉
"""

import asyncio
from typing import List, Dict, Optional
import logging
from datetime import datetime

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
            'cross_margin_protections': 0  # 🔥 v3.18+：全倉保護平倉次數
        }
        
        # 🔥 v3.18+：全倉保護狀態追蹤
        self.last_cross_margin_protection_time = 0  # 上次觸發時間戳
        
        logger.info("=" * 80)
        logger.info("✅ PositionController v3.18+ 初始化完成（全倉保護）")
        logger.info(f"   ⏱️  監控間隔: {monitor_interval} 秒")
        logger.info("   🛡️  優先級: 0（最高優先級）")
        logger.info("   🚨 緊急平倉: PnL ≤ -99%")
        logger.info("   📡 WebSocket: {}".format("已啟用（優先使用）" if websocket_monitor else "未啟用（僅REST）"))
        logger.info("   🔥 整合 PositionMonitor24x7（進場失效 + 逆勢自動平倉）")
        if config and hasattr(config, 'CROSS_MARGIN_PROTECTOR_ENABLED') and config.CROSS_MARGIN_PROTECTOR_ENABLED:
            logger.info(f"   🛡️ 全倉保護: 啟用（{getattr(config, 'CROSS_MARGIN_PROTECTOR_THRESHOLD', 0.85):.0%} 閾值，{getattr(config, 'CROSS_MARGIN_PROTECTOR_COOLDOWN', 120)}秒冷卻）")
        else:
            logger.info("   🛡️ 全倉保護: 停用")
        logger.info("=" * 80)
    
    async def start_monitoring(self):
        """啟動 24/7 倉位監控（整合 PositionMonitor24x7，共享API調用）"""
        self.is_running = True
        logger.info("🚀 PositionController 24/7 監控已啟動（整合進場失效+逆勢檢測）")
        
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
                
                # 🔥 v3.18.1+：優先使用API直接提供的unrealized PnL（準確且高效）
                if 'unRealizedProfit' in pos:
                    pnl = float(pos.get('unRealizedProfit', 0))
                    # 從倉位金額判斷方向
                    side = 'LONG' if position_amt > 0 else 'SHORT'
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
            
            # 步驟6：篩選虧損倉位
            losing_positions = [p for p in positions if p['pnl'] < 0]
            
            if not losing_positions:
                logger.info(
                    f"🛡️ 保證金使用率 {margin_usage_ratio:.1%} > {threshold:.0%} "
                    f"但無虧損倉位，無需保護"
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
            
            # 使用市價單立即平倉
            result = await self.binance_client.place_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
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
                
                return True
            else:
                return False
                
        except Exception as e:
            logger.critical(f"❌ 全倉保護平倉異常: {symbol} - {e}", exc_info=True)
            return False
    
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
            
            # 🔥 v3.18.4+：記錄平倉數據到TradeRecorder（ML學習關鍵）
            if self.trade_recorder and result:
                try:
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
                    
                    self.trade_recorder.record_exit(trade_result)
                    logger.info(f"📝 已記錄平倉: {symbol} | PnL: {position.get('pnl', 0):+.2f} USDT ({position.get('pnl_pct', 0):+.2%})")
                except Exception as e:
                    logger.warning(f"⚠️ 記錄平倉數據失敗: {e}")
            
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
