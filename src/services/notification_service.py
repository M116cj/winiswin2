"""
NotificationService v1.0 - Discord/Telegram通知服務
職責：發送交易事件通知到Discord或Telegram（非阻塞、Fire-and-Forget）
"""

import asyncio
import aiohttp
import os
from typing import Optional, Dict, Any
from datetime import datetime
from src.utils.logger_factory import get_logger

logger = get_logger(__name__)


class NotificationService:
    """
    通知服務 - 異步Fire-and-Forget模式
    
    特性：
    - ✅ 支援Discord Webhook
    - ✅ 支援Telegram Bot API
    - ✅ 完全異步（never blocks trading logic）
    - ✅ 自動錯誤恢復（失敗不影響交易）
    - ✅ 速率限制保護
    
    使用示例：
    ```python
    # 環境變量配置
    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
    # 或
    TELEGRAM_TOKEN=123456:ABC-DEF...
    TELEGRAM_CHAT_ID=-1001234567890
    
    # 使用
    notifier = NotificationService()
    await notifier.send_trade_open(symbol, side, price, confidence)
    await notifier.send_trade_close(symbol, pnl, pnl_pct, reason)
    ```
    """
    
    def __init__(self):
        """初始化通知服務"""
        # Discord配置
        self.discord_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
        
        # Telegram配置
        self.telegram_token = os.environ.get('TELEGRAM_TOKEN')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        # 服務狀態
        self.enabled = False
        self.service_type = None
        
        # 速率限制（避免被ban）
        self.last_send_time = 0
        self.min_interval = 1.0  # 最小發送間隔（秒）
        
        # HTTP會話（復用連接）
        self._session: Optional[aiohttp.ClientSession] = None
        
        # 初始化檢查
        self._initialize()
    
    def _initialize(self):
        """檢測並初始化通知服務"""
        if self.discord_webhook_url:
            self.enabled = True
            self.service_type = 'discord'
            logger.info("✅ 通知服務已啟用: Discord Webhook")
            logger.info(f"   🔗 Webhook: {self.discord_webhook_url[:50]}...")
            
        elif self.telegram_token and self.telegram_chat_id:
            self.enabled = True
            self.service_type = 'telegram'
            logger.info("✅ 通知服務已啟用: Telegram Bot")
            logger.info(f"   🤖 Bot Token: {self.telegram_token[:20]}...")
            logger.info(f"   💬 Chat ID: {self.telegram_chat_id}")
            
        else:
            self.enabled = False
            logger.info("ℹ️  通知服務未配置（可選功能）")
            logger.info("   提示: 設置 DISCORD_WEBHOOK_URL 或 TELEGRAM_TOKEN+TELEGRAM_CHAT_ID")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """獲取HTTP會話（延遲創建，復用連接）"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5.0),  # 5秒超時
                connector=aiohttp.TCPConnector(limit=10)
            )
        return self._session
    
    async def close(self):
        """關閉HTTP會話（清理資源）"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("✅ NotificationService HTTP會話已關閉")
    
    async def send_trade_open(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        leverage: int,
        confidence: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ):
        """
        發送開倉通知（Fire-and-Forget）
        
        Args:
            symbol: 交易對符號
            direction: 方向（LONG/SHORT）
            entry_price: 入場價格
            quantity: 數量
            leverage: 槓桿
            confidence: 模型信心度（0-1）
            stop_loss: 止損價格（可選）
            take_profit: 止盈價格（可選）
        """
        if not self.enabled:
            return
        
        # 構建消息
        emoji = "🟢" if direction == "LONG" else "🔴"
        confidence_stars = "⭐" * int(confidence * 5)
        
        title = f"{emoji} 開倉信號 - {symbol}"
        fields = [
            f"**方向**: {direction}",
            f"**入場價**: ${entry_price:,.2f}",
            f"**數量**: {quantity:.4f}",
            f"**槓桿**: {leverage}x",
            f"**信心度**: {confidence:.1%} {confidence_stars}",
        ]
        
        if stop_loss:
            sl_pct = abs(entry_price - stop_loss) / entry_price * 100
            fields.append(f"**止損**: ${stop_loss:,.2f} ({sl_pct:.2f}%)")
        
        if take_profit:
            tp_pct = abs(take_profit - entry_price) / entry_price * 100
            fields.append(f"**止盈**: ${take_profit:,.2f} ({tp_pct:.2f}%)")
        
        fields.append(f"**時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        message = f"{title}\n\n" + "\n".join(fields)
        
        # 異步發送（不等待結果）
        asyncio.create_task(self._send_message(message, color=0x00FF00 if direction == "LONG" else 0xFF0000))
    
    async def send_trade_close(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str,
        holding_time: Optional[str] = None
    ):
        """
        發送平倉通知（Fire-and-Forget）
        
        Args:
            symbol: 交易對符號
            direction: 方向（LONG/SHORT）
            entry_price: 入場價格
            exit_price: 出場價格
            pnl: 盈虧金額（USDT）
            pnl_pct: 盈虧百分比
            reason: 平倉原因
            holding_time: 持倉時間（可選）
        """
        if not self.enabled:
            return
        
        # 判斷盈虧
        is_profit = pnl > 0
        emoji = "✅" if is_profit else "❌"
        color = 0x00FF00 if is_profit else 0xFF0000
        
        title = f"{emoji} 平倉 - {symbol}"
        fields = [
            f"**方向**: {direction}",
            f"**入場價**: ${entry_price:,.2f}",
            f"**出場價**: ${exit_price:,.2f}",
            f"**盈虧**: {'🟢' if is_profit else '🔴'} ${pnl:+,.2f} ({pnl_pct:+.2f}%)",
            f"**原因**: {reason}",
        ]
        
        if holding_time:
            fields.append(f"**持倉時間**: {holding_time}")
        
        fields.append(f"**時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        message = f"{title}\n\n" + "\n".join(fields)
        
        # 異步發送（不等待結果）
        asyncio.create_task(self._send_message(message, color=color))
    
    async def send_daily_summary(
        self,
        total_trades: int,
        winning_trades: int,
        total_pnl: float,
        win_rate: float,
        best_trade: Optional[Dict[str, Any]] = None,
        worst_trade: Optional[Dict[str, Any]] = None
    ):
        """
        發送每日總結（Fire-and-Forget）
        
        Args:
            total_trades: 總交易數
            winning_trades: 獲勝交易數
            total_pnl: 總盈虧
            win_rate: 勝率
            best_trade: 最佳交易（可選）
            worst_trade: 最差交易（可選）
        """
        if not self.enabled:
            return
        
        # 構建消息
        emoji = "📊" 
        is_profitable = total_pnl > 0
        color = 0x00FF00 if is_profitable else 0xFF0000
        
        title = f"{emoji} 每日交易總結"
        fields = [
            f"**總交易數**: {total_trades}",
            f"**獲勝交易**: {winning_trades} / {total_trades}",
            f"**勝率**: {win_rate:.1%}",
            f"**總盈虧**: {'🟢' if is_profitable else '🔴'} ${total_pnl:+,.2f}",
        ]
        
        if best_trade:
            fields.append(f"\n**最佳交易**: {best_trade['symbol']} (+{best_trade['pnl_pct']:.2f}%)")
        
        if worst_trade:
            fields.append(f"**最差交易**: {worst_trade['symbol']} ({worst_trade['pnl_pct']:.2f}%)")
        
        fields.append(f"\n**日期**: {datetime.now().strftime('%Y-%m-%d')}")
        
        message = f"{title}\n\n" + "\n".join(fields)
        
        # 異步發送（不等待結果）
        asyncio.create_task(self._send_message(message, color=color))
    
    async def _send_message(self, message: str, color: int = 0x3498DB):
        """
        內部方法：實際發送消息（Fire-and-Forget）
        
        Args:
            message: 消息內容
            color: 顏色代碼（Discord embed）
        """
        if not self.enabled:
            return
        
        try:
            # 速率限制檢查
            now = asyncio.get_event_loop().time()
            if now - self.last_send_time < self.min_interval:
                logger.debug(f"⚠️ 速率限制：跳過通知（距離上次 {now - self.last_send_time:.1f}s）")
                return
            
            self.last_send_time = now
            
            # 根據服務類型發送
            if self.service_type == 'discord':
                await self._send_discord(message, color)
            elif self.service_type == 'telegram':
                await self._send_telegram(message)
            
        except Exception as e:
            # 捕獲所有錯誤，never crash trading logic
            logger.warning(f"⚠️ 通知發送失敗（不影響交易）: {e}")
    
    async def _send_discord(self, message: str, color: int):
        """發送Discord消息（Webhook）"""
        try:
            session = await self._get_session()
            
            # Discord Embed格式
            payload = {
                "embeds": [{
                    "description": message,
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            
            async with session.post(self.discord_webhook_url, json=payload) as resp:
                if resp.status == 204:
                    logger.debug("✅ Discord通知已發送")
                else:
                    logger.warning(f"⚠️ Discord通知失敗: HTTP {resp.status}")
                    
        except asyncio.TimeoutError:
            logger.warning("⚠️ Discord通知超時（5秒）")
        except Exception as e:
            logger.warning(f"⚠️ Discord發送錯誤: {e}")
    
    async def _send_telegram(self, message: str):
        """發送Telegram消息（Bot API）"""
        try:
            session = await self._get_session()
            
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    logger.debug("✅ Telegram通知已發送")
                else:
                    logger.warning(f"⚠️ Telegram通知失敗: HTTP {resp.status}")
                    
        except asyncio.TimeoutError:
            logger.warning("⚠️ Telegram通知超時（5秒）")
        except Exception as e:
            logger.warning(f"⚠️ Telegram發送錯誤: {e}")
    
    def __del__(self):
        """析構函數：確保資源清理"""
        if self._session and not self._session.closed:
            # 在事件循環中關閉會話
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
                else:
                    loop.run_until_complete(self.close())
            except:
                pass  # 忽略清理錯誤
