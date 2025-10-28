"""
Discord 機器人
職責：實時通知、Slash 指令、狀態查詢
"""

import discord
from discord import app_commands
from typing import Optional, Dict
import logging
from datetime import datetime

from src.config import Config

logger = logging.getLogger(__name__)


class TradingDiscordBot:
    """交易 Discord 機器人"""
    
    def __init__(self):
        """初始化 Discord 機器人"""
        self.config = Config
        
        intents = discord.Intents.default()
        intents.message_content = True
        
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        
        self.target_channel_id = None
        if self.config.DISCORD_CHANNEL_ID:
            try:
                self.target_channel_id = int(self.config.DISCORD_CHANNEL_ID)
            except:
                logger.warning("DISCORD_CHANNEL_ID 格式錯誤")
        
        self.statistics = {}
        
        self._setup_events()
        self._setup_commands()
    
    def _setup_events(self):
        """設置事件處理"""
        
        @self.client.event
        async def on_ready():
            logger.info(f"✅ Discord 機器人已連接: {self.client.user}")
            try:
                await self.tree.sync()
                logger.info("✅ 指令已同步")
            except Exception as e:
                logger.error(f"同步指令失敗: {e}")
    
    def _setup_commands(self):
        """設置 Slash 指令"""
        
        @self.tree.command(name="status", description="查看交易系統狀態")
        async def status_command(interaction: discord.Interaction):
            """查看系統狀態"""
            embed = self._create_status_embed()
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="stats", description="查看交易統計")
        async def stats_command(interaction: discord.Interaction):
            """查看交易統計"""
            embed = self._create_stats_embed()
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="positions", description="查看當前持倉")
        async def positions_command(interaction: discord.Interaction):
            """查看當前持倉"""
            embed = self._create_positions_embed()
            await interaction.response.send_message(embed=embed)
    
    async def send_signal_notification(self, signal: Dict, rank: int):
        """
        發送交易信號通知
        
        Args:
            signal: 交易信號
            rank: 信號排名
        """
        try:
            embed = discord.Embed(
                title=f"🎯 交易信號 #{rank}",
                description=f"**{signal['symbol']}** {signal['direction']}",
                color=discord.Color.blue() if signal['direction'] == "LONG" else discord.Color.red(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="信心度",
                value=f"{signal['confidence']:.1%}",
                inline=True
            )
            
            embed.add_field(
                name="入場價",
                value=f"${signal['entry_price']:.4f}",
                inline=True
            )
            
            embed.add_field(
                name="排名",
                value=f"#{rank}",
                inline=True
            )
            
            embed.add_field(
                name="止損",
                value=f"${signal['stop_loss']:.4f}",
                inline=True
            )
            
            embed.add_field(
                name="止盈",
                value=f"${signal['take_profit']:.4f}",
                inline=True
            )
            
            risk_reward = abs(signal['take_profit'] - signal['entry_price']) / abs(signal['entry_price'] - signal['stop_loss'])
            embed.add_field(
                name="風險回報比",
                value=f"1:{risk_reward:.1f}",
                inline=True
            )
            
            if rank <= self.config.IMMEDIATE_EXECUTION_RANK:
                embed.add_field(
                    name="📌 狀態",
                    value="**即將執行**",
                    inline=False
                )
            else:
                embed.add_field(
                    name="👁️ 狀態",
                    value="虛擬追蹤",
                    inline=False
                )
            
            await self._send_to_channel(embed=embed)
            
        except Exception as e:
            logger.error(f"發送信號通知失敗: {e}")
    
    async def send_trade_notification(self, trade: Dict, action: str):
        """
        發送交易執行通知
        
        Args:
            trade: 交易信息
            action: 動作 ('open' 或 'close')
        """
        try:
            if action == "open":
                title = "✅ 開倉成功"
                color = discord.Color.green()
            else:
                pnl = trade.get('pnl', 0)
                if pnl > 0:
                    title = "💰 平倉獲利"
                    color = discord.Color.gold()
                else:
                    title = "📉 平倉止損"
                    color = discord.Color.orange()
            
            embed = discord.Embed(
                title=title,
                description=f"**{trade['symbol']}** {trade['direction']}",
                color=color,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="入場價",
                value=f"${trade['entry_price']:.4f}",
                inline=True
            )
            
            if action == "close":
                embed.add_field(
                    name="出場價",
                    value=f"${trade.get('exit_price', 0):.4f}",
                    inline=True
                )
                
                pnl_pct = trade.get('pnl_pct', 0)
                embed.add_field(
                    name="收益率",
                    value=f"{pnl_pct:+.2%}",
                    inline=True
                )
                
                embed.add_field(
                    name="PnL",
                    value=f"${trade.get('pnl', 0):+.2f}",
                    inline=True
                )
                
                embed.add_field(
                    name="平倉原因",
                    value=trade.get('close_reason', 'unknown'),
                    inline=True
                )
            else:
                embed.add_field(
                    name="槓桿",
                    value=f"{trade.get('leverage', 0)}x",
                    inline=True
                )
                
                embed.add_field(
                    name="倉位價值",
                    value=f"${trade.get('position_value', 0):.2f}",
                    inline=True
                )
            
            await self._send_to_channel(embed=embed)
            
        except Exception as e:
            logger.error(f"發送交易通知失敗: {e}")
    
    async def send_alert(self, message: str, alert_type: str = "info"):
        """
        發送系統提醒
        
        Args:
            message: 提醒內容
            alert_type: 提醒類型 ('info', 'warning', 'error')
        """
        try:
            color_map = {
                'info': discord.Color.blue(),
                'warning': discord.Color.orange(),
                'error': discord.Color.red()
            }
            
            icon_map = {
                'info': 'ℹ️',
                'warning': '⚠️',
                'error': '❌'
            }
            
            embed = discord.Embed(
                title=f"{icon_map.get(alert_type, 'ℹ️')} 系統提醒",
                description=message,
                color=color_map.get(alert_type, discord.Color.blue()),
                timestamp=datetime.now()
            )
            
            await self._send_to_channel(embed=embed)
            
        except Exception as e:
            logger.error(f"發送提醒失敗: {e}")
    
    def _create_status_embed(self) -> discord.Embed:
        """創建狀態 Embed"""
        stats = self.statistics
        
        embed = discord.Embed(
            title="📊 系統狀態",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="運行狀態",
            value="✅ 正常運行",
            inline=True
        )
        
        embed.add_field(
            name="交易模式",
            value="✅ 啟用" if self.config.TRADING_ENABLED else "⏸️ 模擬",
            inline=True
        )
        
        embed.add_field(
            name="測試網",
            value="✅ 是" if self.config.BINANCE_TESTNET else "❌ 否",
            inline=True
        )
        
        embed.add_field(
            name="活躍持倉",
            value=f"{stats.get('active_positions', 0)}",
            inline=True
        )
        
        embed.add_field(
            name="虛擬倉位",
            value=str(stats.get('virtual_positions', 0)),
            inline=True
        )
        
        return embed
    
    def _create_stats_embed(self) -> discord.Embed:
        """創建統計 Embed"""
        stats = self.statistics
        
        embed = discord.Embed(
            title="📈 交易統計",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        total_trades = stats.get('total_trades', 0)
        win_rate = stats.get('win_rate', 0)
        total_pnl = stats.get('total_pnl', 0)
        
        embed.add_field(
            name="總交易次數",
            value=str(total_trades),
            inline=True
        )
        
        embed.add_field(
            name="勝率",
            value=f"{win_rate:.1%}",
            inline=True
        )
        
        embed.add_field(
            name="總 PnL",
            value=f"${total_pnl:+.2f}",
            inline=True
        )
        
        return embed
    
    def _create_positions_embed(self) -> discord.Embed:
        """創建持倉 Embed"""
        positions = self.statistics.get('positions', [])
        
        embed = discord.Embed(
            title="📍 當前持倉",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        
        if not positions:
            embed.description = "暫無持倉"
        else:
            for pos in positions:
                field_value = (
                    f"方向: {pos['direction']}\n"
                    f"入場: ${pos['entry_price']:.4f}\n"
                    f"槓桿: {pos.get('leverage', 0)}x"
                )
                embed.add_field(
                    name=pos['symbol'],
                    value=field_value,
                    inline=True
                )
        
        return embed
    
    async def _send_to_channel(self, embed: discord.Embed):
        """發送消息到指定頻道"""
        try:
            if self.target_channel_id:
                channel = self.client.get_channel(self.target_channel_id)
                if channel:
                    await channel.send(embed=embed)  # type: ignore
                else:
                    logger.warning(f"未找到頻道 ID: {self.target_channel_id}")
            else:
                for guild in self.client.guilds:
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).send_messages:
                            await channel.send(embed=embed)
                            return
        except Exception as e:
            logger.error(f"發送消息到頻道失敗: {e}")
    
    def update_statistics(self, stats: Dict):
        """更新統計數據"""
        self.statistics = stats
    
    async def start(self):
        """啟動機器人"""
        try:
            await self.client.start(self.config.DISCORD_TOKEN)
        except Exception as e:
            logger.error(f"啟動 Discord 機器人失敗: {e}")
    
    async def close(self):
        """關閉機器人"""
        await self.client.close()
