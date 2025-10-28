"""
v3.17+ 24/7 倉位監控器
每 2 秒檢查所有倉位，-99% 風險立即平倉
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PositionMonitor24x7:
    """
    24/7 倉位監控器（v3.17+）
    
    職責：
    1. 每 2 秒檢查所有倉位
    2. 計算實時 PnL
    3. PnL ≤ -99% 初始風險 → 立即市價平倉
    4. 使用優先級 0 API 通道（倉位操作最高優先級）
    """
    
    def __init__(
        self,
        config_profile,
        binance_client=None,
        trade_recorder=None
    ):
        """
        初始化監控器
        
        Args:
            config_profile: ConfigProfile 實例
            binance_client: BinanceClient 實例（可選）
            trade_recorder: TradeRecorder 實例（可選）
        """
        self.config = config_profile
        self.binance_client = binance_client
        self.trade_recorder = trade_recorder
        
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # 統計數據
        self.total_checks = 0
        self.forced_closures = 0
        self.last_check_time: Optional[datetime] = None
        
        logger.info("=" * 60)
        logger.info("✅ 24/7 倉位監控器初始化完成（v3.17+）")
        logger.info(f"   ⏱️  檢查間隔: {self.config.position_monitor_interval} 秒")
        logger.info(f"   🚨 風險熔斷閾值: {self.config.risk_kill_threshold:.1%}")
        logger.info(f"   🎯 優先級: 0 (最高)")
        logger.info("=" * 60)
    
    async def start(self):
        """啟動監控器"""
        if self.is_running:
            logger.warning("⚠️ 監控器已在運行")
            return
        
        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("🚀 24/7 倉位監控器已啟動")
    
    async def stop(self):
        """停止監控器"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"⏸️  24/7 倉位監控器已停止 (總檢查: {self.total_checks}, 強制平倉: {self.forced_closures})")
    
    async def _monitor_loop(self):
        """主監控循環"""
        logger.info("🔄 開始監控循環...")
        
        while self.is_running:
            try:
                # 檢查所有倉位
                await self._check_all_positions()
                
                # 更新統計
                self.total_checks += 1
                self.last_check_time = datetime.now()
                
                # 等待下一次檢查
                await asyncio.sleep(self.config.position_monitor_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 監控循環錯誤: {e}", exc_info=True)
                await asyncio.sleep(self.config.position_monitor_interval)
    
    async def _check_all_positions(self):
        """檢查所有倉位"""
        if not self.binance_client:
            return
        
        try:
            # 獲取所有倉位
            positions = await self.binance_client.get_position_info_async()
            
            if not positions:
                return
            
            # 過濾有效倉位（數量 > 0）
            active_positions = [p for p in positions if abs(float(p.get('positionAmt', 0))) > 0]
            
            if not active_positions:
                return
            
            logger.debug(f"📊 檢查 {len(active_positions)} 個活躍倉位")
            
            # 檢查每個倉位
            for position in active_positions:
                await self._check_single_position(position)
                
        except Exception as e:
            logger.error(f"❌ 獲取倉位失敗: {e}")
    
    async def _check_single_position(self, position: Dict[str, Any]):
        """
        檢查單個倉位
        
        Args:
            position: 倉位數據（來自 Binance API）
        """
        try:
            symbol = position.get('symbol')
            if not symbol:
                logger.warning("⚠️ 持倉數據缺少 symbol，跳過")
                return
                
            position_amt = float(position.get('positionAmt', 0))
            entry_price = float(position.get('entryPrice', 0))
            # markPrice 可能缺失，使用 entryPrice 作為備選
            mark_price = float(position.get('markPrice') or position.get('entryPrice', 0))
            unrealized_pnl = float(position.get('unRealizedProfit', 0))
            
            if position_amt == 0:
                return
            
            # 獲取原始風險金額（從交易記錄）
            risk_amount = await self._get_risk_amount(symbol)
            
            if risk_amount is None or risk_amount <= 0:
                logger.warning(f"⚠️ {symbol} 無法獲取風險金額，跳過檢查")
                return
            
            # 計算 PnL 百分比（相對於初始風險）
            pnl_pct = unrealized_pnl / risk_amount if risk_amount > 0 else 0
            
            # 檢查是否觸發熔斷
            if pnl_pct <= -self.config.risk_kill_threshold:
                logger.critical(
                    f"🚨🚨🚨 {symbol} 觸發 100% 虧損熔斷！"
                    f"PnL: ${unrealized_pnl:.2f} ({pnl_pct:.1%}) "
                    f"風險: ${risk_amount:.2f}"
                )
                
                # 立即市價平倉（優先級 0）
                await self._force_close_position(symbol, position_amt, mark_price)
            
            else:
                # 正常監控日誌（僅在虧損 >50% 時警告）
                if pnl_pct < -0.5:
                    logger.warning(
                        f"⚠️ {symbol} 虧損 {pnl_pct:.1%} "
                        f"(PnL: ${unrealized_pnl:.2f} / 風險: ${risk_amount:.2f})"
                    )
                    
        except Exception as e:
            logger.error(f"❌ 檢查倉位失敗: {e}")
    
    async def _get_risk_amount(self, symbol: str) -> Optional[float]:
        """
        獲取倉位的初始風險金額
        
        Args:
            symbol: 交易對符號
            
        Returns:
            風險金額（USDT），或 None
        """
        if not self.trade_recorder:
            return None
        
        try:
            # 從交易記錄獲取最近的開倉記錄
            trades = self.trade_recorder.get_active_trades(symbol)
            if trades:
                return trades[0].get('risk_amount', 0)
        except Exception as e:
            logger.debug(f"獲取 {symbol} 風險金額失敗: {e}")
        
        return None
    
    async def _force_close_position(
        self,
        symbol: str,
        position_amt: float,
        current_price: float
    ):
        """
        強制平倉（市價單）
        
        Args:
            symbol: 交易對符號
            position_amt: 倉位數量（正數=多倉，負數=空倉）
            current_price: 當前價格
        """
        if not self.binance_client:
            logger.error("❌ 無 Binance 客戶端，無法平倉")
            return
        
        try:
            # 計算平倉方向和數量
            side = "SELL" if position_amt > 0 else "BUY"
            quantity = abs(position_amt)
            
            logger.critical(
                f"🚨 執行強制平倉: {symbol} {side} {quantity:.6f} @ ${current_price:.2f}"
            )
            
            # 市價平倉（優先級 0，最高優先級）
            # ⚠️ One-Way Mode: 不使用 positionSide，reduce_only 也移除
            result = await self.binance_client.place_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity
            )
            
            if result:
                self.forced_closures += 1
                logger.critical(f"✅ 強制平倉成功: {symbol} (訂單: {result.get('orderId')})")
                
                # 記錄到交易記錄
                if self.trade_recorder:
                    self.trade_recorder.record_forced_closure(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=current_price,
                        reason="100% 虧損熔斷",
                        order_id=result.get('orderId')
                    )
            else:
                logger.error(f"❌ 強制平倉失敗: {symbol}")
                
        except Exception as e:
            logger.critical(f"❌ 強制平倉異常: {symbol} - {e}", exc_info=True)
    
    def get_monitor_stats(self) -> Dict[str, Any]:
        """
        獲取監控器統計信息
        
        Returns:
            統計字典
        """
        return {
            "is_running": self.is_running,
            "total_checks": self.total_checks,
            "forced_closures": self.forced_closures,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "check_interval_seconds": self.config.position_monitor_interval,
            "risk_kill_threshold": f"{self.config.risk_kill_threshold:.1%}",
        }
