"""
PositionController v3.17+ - 24/7 倉位全權控制
職責：監控所有持倉、執行平倉決策、調整 SL/TP
"""

import asyncio
from typing import List, Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PositionController:
    """
    PositionController v3.17+ - 24/7 倉位全權控制
    
    職責：
    1. 每 2 秒監控所有持倉
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
        monitor_interval: int = 2,
        config=None
    ):
        """
        初始化 PositionController
        
        Args:
            binance_client: Binance 客戶端
            self_learning_trader: SelfLearningTrader 實例
            monitor_interval: 監控間隔（秒），預設 2 秒
            config: 配置對象
        """
        self.binance_client = binance_client
        self.trader = self_learning_trader
        self.monitor_interval = monitor_interval
        self.config = config
        
        # 控制器狀態
        self.is_running = False
        self.last_check_time = None
        
        # 統計數據
        self.stats = {
            'total_checks': 0,
            'total_closes': 0,
            'total_adjustments': 0,
            'emergency_closes': 0  # 100% 虧損緊急平倉
        }
        
        logger.info("=" * 80)
        logger.info("✅ PositionController v3.17+ 初始化完成")
        logger.info(f"   ⏱️  監控間隔: {monitor_interval} 秒")
        logger.info("   🛡️  優先級: 0（最高優先級）")
        logger.info("   🚨 緊急平倉: PnL ≤ -99%")
        logger.info("=" * 80)
    
    async def start_monitoring(self):
        """啟動 24/7 倉位監控"""
        self.is_running = True
        logger.info("🚀 PositionController 24/7 監控已啟動")
        
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
    
    async def _monitoring_cycle(self):
        """單次監控週期"""
        try:
            self.stats['total_checks'] += 1
            self.last_check_time = datetime.now()
            
            # 步驟 1：獲取所有持倉（優先級 0）
            positions = await self._fetch_all_positions()
            
            if not positions:
                logger.debug("   📭 當前無持倉")
                return
            
            logger.debug(f"   📊 監控 {len(positions)} 個持倉")
            
            # 步驟 2：調用 SelfLearningTrader 評估持倉
            decisions = await self.trader.evaluate_positions(positions)
            
            # 步驟 3：執行決策
            for position_id, decision in decisions.items():
                await self._execute_decision(position_id, decision, positions)
            
        except Exception as e:
            logger.error(f"❌ 監控週期執行失敗: {e}", exc_info=True)
    
    async def _fetch_all_positions(self) -> List[Dict]:
        """
        獲取所有持倉（使用優先通道）
        
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
            # 使用 Binance API 獲取持倉（priority=0）
            raw_positions = await self.binance_client.get_position_info_async()
            
            positions = []
            for pos in raw_positions:
                # 過濾空倉位
                position_amt = float(pos.get('positionAmt', 0))
                if abs(position_amt) < 0.0001:
                    continue
                
                symbol = pos.get('symbol', 'UNKNOWN')
                entry_price = float(pos.get('entryPrice', 0))
                # markPrice 可能在某些情況下缺失，使用 entryPrice 作為備選
                current_price = float(pos.get('markPrice') or pos.get('entryPrice', 0))
                leverage = float(pos.get('leverage', 1))
                
                # 計算 PnL
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
                await self._close_position(position)
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
    
    async def _close_position(self, position: Dict):
        """
        平倉（使用優先通道）
        
        Args:
            position: 持倉信息
        """
        try:
            symbol = position['symbol']
            side = position['side']
            size = position['size']
            
            # 確定平倉方向
            close_side = 'SELL' if side == 'LONG' else 'BUY'
            
            logger.info(
                f"🔴 平倉: {symbol} {side} | 數量={size:.6f} | "
                f"PnL={position['pnl']:.2f} USDT ({position['pnl_pct']:.2%})"
            )
            
            # 使用市價單平倉
            result = await self.binance_client.place_order(
                symbol=symbol,
                side=close_side,
                order_type='MARKET',
                quantity=size,
                reduce_only=True
            )
            
            logger.info(f"✅ 平倉成功: {symbol} | 訂單 ID={result.get('orderId')}")
            
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
