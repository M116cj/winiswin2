"""
🔥 AccountFeed v5.0 - 即时账户/仓位数据流（统一架构版）
职责：使用listenKey监控仓位变动，取代REST /fapi/v1/account轮询

改进（v5.0）：
- 继承UnifiedWebSocketFeed - 单一心跳机制
- 删除自定义while循环和ping逻辑
- 使用父类的Producer-Consumer架构
"""

import asyncio
from typing import Dict, Optional, Any
from datetime import datetime

try:
    import orjson as json
except ImportError:
    import json

try:
    import websockets  # type: ignore
except ImportError:
    websockets = None  # type: ignore

import logging
from .unified_feed import UnifiedWebSocketFeed
from src.core.account_state_cache import account_state_cache

logger = logging.getLogger(__name__)


class AccountFeed(UnifiedWebSocketFeed):
    """
    🔥 AccountFeed v5.0 - Binance账户WebSocket监控器（统一架构版）
    
    职责：
    1. 管理listenKey（获取/自动续期/智能重试）
    2. 订阅ACCOUNT_UPDATE事件
    3. 缓存即时仓位数据
    4. 提供即时仓位查询
    
    优势：
    - 完全移除/fapi/v1/account轮询（零API请求）
    - 即时仓位更新（无延迟）
    - 自动账户变动通知
    - listenKey自动续期（每15分钟，比过期早一半）
    - 续期失败自动重试（最多3次）
    - 网络延迟追踪
    """
    
    def __init__(self, binance_client: Any):
        """
        初始化AccountFeed
        
        Args:
            binance_client: Binance客户端（用于获取listenKey）
        """
        self.binance_client = binance_client
        self.listen_key: Optional[str] = None
        self.position_cache: Dict[str, Dict] = {}  # {symbol: position_data}
        self.account_data: Dict[str, Any] = {}  # 账户余额等数据
        self.keep_alive_task: Optional[asyncio.Task] = None
        self.last_message_time = None  # 最后消息时间
        
        # 暂时设置占位符URL（在start()中获取listenKey后更新）
        super().__init__(url="wss://fstream.binance.com/ws/placeholder", feed_name="AccountFeed")
        
        logger.info("=" * 80)
        logger.info("✅ AccountFeed 初始化完成（v5.0 统一架构版）")
        logger.info("   📡 监控类型: ACCOUNT_UPDATE（即时仓位）")
        logger.info("   🔌 WebSocket URL: wss://fstream.binance.com/ws/")
        logger.info("   ⏱️  listenKey自动续期: 每15分钟（过期前提前续期）")
        logger.info("   💓 心跳监控: 统一心跳（20秒ping，20秒超时）")
        logger.info("   🔄 智能重连: 指数退避（5-60秒）")
        logger.info("=" * 80)
    
    async def start(self):
        """启动账户WebSocket监控"""
        if not websockets:
            logger.error("❌ AccountFeed: websockets模块未安装")
            return
        
        logger.info("🚀 AccountFeed 启动中...")
        
        try:
            # 1. 获取listenKey
            self.listen_key = await self.binance_client.get_listen_key()
            logger.info(f"✅ listenKey已获取: {self.listen_key[:8]}...")
            
            # 2. 更新URL
            self.url = f"wss://fstream.binance.com/ws/{self.listen_key}"
            
            # 3. 启动父类（连接+消费者）
            await super().start()
            
            # 4. 启动listenKey续期任务（每15分钟）
            self.keep_alive_task = asyncio.create_task(self._keep_alive())
            
            logger.info("✅ AccountFeed 已启动（统一心跳 + Producer-Consumer）")
        
        except Exception as e:
            logger.error(f"❌ AccountFeed 启动失败: {e}")
            self.running = False
            raise
    
    async def on_connect(self, ws) -> None:
        """连接成功后的回调"""
        logger.debug("✅ 账户WebSocket已连接")
    
    async def process_message(self, raw_msg: str) -> None:
        """
        处理单条账户消息
        
        Args:
            raw_msg: 原始WebSocket消息（JSON字符串）
        """
        try:
            # 检查消息有效性
            if not raw_msg:
                logger.debug("⚠️ 收到空消息，跳过")
                return
            
            data = json.loads(raw_msg)
            
            # 防御性检查
            if data is None:
                logger.debug("⚠️ JSON解析结果为None，跳过")
                return
            
            if not isinstance(data, dict):
                logger.warning(f"⚠️ 消息格式非字典: {type(data)}")
                return
            
            # 更新最后消息时间
            self.last_message_time = datetime.now()
            
            # 处理ACCOUNT_UPDATE事件
            if data.get('e') == 'ACCOUNT_UPDATE':
                self._update_account(data)
            
            # 处理ORDER_TRADE_UPDATE事件（订单状态）
            elif data.get('e') == 'ORDER_TRADE_UPDATE':
                self._update_order(data)
        
        except json.JSONDecodeError:
            logger.warning("⚠️ JSON解析失败")
        
        except TypeError as e:
            logger.warning(f"⚠️ 消息格式错误（NoneType）: {e}")
        
        except KeyError as e:
            logger.warning(f"⚠️ 消息格式错误（缺少字段）: {e}")
        
        except Exception as e:
            logger.error(f"❌ 消息处理异常: {e}")
    
    async def _keep_alive(self):
        """
        自动续期listenKey（优化版）
        
        改进：
        - 每15分钟续期（比30分钟过期时间提前一半，更安全）
        - 续期失败时立即重试（最多3次）
        - 记录续期成功率
        """
        while self.running:
            try:
                await asyncio.sleep(900)  # 15分钟（比30分钟过期早一半）
                
                if not self.listen_key:
                    logger.warning("⚠️ listenKey为空，跳过续期")
                    continue
                
                # 尝试续期（最多重试3次）
                success = False
                for attempt in range(3):
                    try:
                        await self.binance_client.renew_listen_key(self.listen_key)
                        self.stats['listen_key_renewals'] = \
                            self.stats.get('listen_key_renewals', 0) + 1
                        logger.info(f"✅ listenKey已续期: {self.listen_key[:8]}... (第{attempt+1}次尝试)")
                        success = True
                        break
                    except Exception as e:
                        logger.warning(f"⚠️ listenKey续期失败 (第{attempt+1}次): {e}")
                        if attempt < 2:  # 前2次失败后等待重试
                            await asyncio.sleep(5)
                
                if not success:
                    logger.error("❌ listenKey续期连续失败3次，可能需要重新获取")
                    self.stats['renew_failures'] = self.stats.get('renew_failures', 0) + 1
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ listenKey续期循环异常: {e}")
                await asyncio.sleep(5)
    
    def _update_account(self, data: dict):
        """
        更新账户数据（处理ACCOUNT_UPDATE事件）
        
        Args:
            data: ACCOUNT_UPDATE事件数据
        """
        try:
            account_data = data.get('a', {})
            
            # 获取时间戳
            server_ts = self.get_server_timestamp_ms(data, 'E')  # 事件时间
            local_ts = self.get_local_timestamp_ms()
            latency_ms = self.calculate_latency_ms(server_ts, local_ts)
            
            # 更新账户余额
            if 'B' in account_data:
                for balance in account_data['B']:
                    asset = balance['a']
                    wallet_balance = float(balance['wb'])  # 总钱包余额
                    cross_wallet_balance = float(balance['cw'])  # 跨仓余额（可用余额）
                    
                    # 计算保证金（与REST API格式一致）
                    total_margin = wallet_balance - cross_wallet_balance
                    
                    self.account_data[asset] = {
                        'total_balance': wallet_balance,  # 总余额（与REST API一致）
                        'available_balance': cross_wallet_balance,  # 可用余额
                        'total_margin': total_margin,  # 总保证金（与REST API一致）
                        'balance': wallet_balance,  # 兼容旧代码
                        'cross_un_pnl': float(balance.get('bc', 0)),  # cross unrealized PnL
                        'server_timestamp': server_ts,
                        'local_timestamp': local_ts,
                        'latency_ms': latency_ms
                    }
                    
                    # 🔥 写入AccountStateCache（本地优先架构）
                    account_state_cache.update_balance(
                        asset=asset,
                        free=cross_wallet_balance,
                        locked=total_margin
                    )
            
            # 更新仓位
            if 'P' in account_data:
                for position in account_data['P']:
                    symbol = position['s'].lower()
                    position_amt = float(position['pa'])
                    
                    if position_amt != 0:  # 非零仓位
                        self.position_cache[symbol] = {
                            'symbol': position['s'],
                            'size': position_amt,
                            'entry_price': float(position['ep']),
                            'unrealized_pnl': float(position['up']),
                            'margin_type': position.get('mt', 'cross'),
                            'position_side': position.get('ps', 'BOTH'),
                            'server_timestamp': server_ts,
                            'local_timestamp': local_ts,
                            'latency_ms': latency_ms,
                            'update_time': data.get('T', int(datetime.now().timestamp() * 1000))
                        }
                        logger.debug(
                            f"📊 {symbol.upper()} 仓位更新: "
                            f"size={position_amt}, pnl={position['up']}, "
                            f"latency={latency_ms}ms"
                        )
                        
                        # 🔥 写入AccountStateCache（本地优先架构）
                        account_state_cache.update_position(
                            symbol=symbol,
                            amount=position_amt,
                            entry_price=float(position['ep']),
                            unrealized_pnl=float(position['up']),
                            pnl_pct=float(position['up']) / (float(position['ep']) * abs(position_amt)) if position_amt != 0 else 0,
                            margin_type=position.get('mt', 'cross'),
                            leverage=float(position.get('lv', 1))
                        )
                    else:
                        # 仓位已平仓
                        if symbol in self.position_cache:
                            del self.position_cache[symbol]
                            logger.debug(f"🔄 {symbol.upper()} 仓位已清除")
                        
                        # 🔥 从AccountStateCache移除平仓
                        account_state_cache.remove_position(symbol)
        
        except Exception as e:
            logger.error(f"❌ 解析ACCOUNT_UPDATE失败: {e}")
    
    def _update_order(self, data: dict):
        """
        更新订单状态（处理ORDER_TRADE_UPDATE事件）
        
        Args:
            data: ORDER_TRADE_UPDATE事件数据
        """
        try:
            order_data = data.get('o', {})
            symbol = order_data.get('s', '').lower()
            order_status = order_data.get('X', '')
            
            logger.debug(
                f"📝 {symbol.upper()} 订单更新: "
                f"status={order_status}, side={order_data.get('S')}"
            )
        
        except Exception as e:
            logger.error(f"❌ 解析ORDER_TRADE_UPDATE失败: {e}")
    
    # ==================== 数据查询接口 ====================
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        获取即时仓位数据
        
        Args:
            symbol: 交易对
        
        Returns:
            仓位数据，或None
        """
        return self.position_cache.get(symbol.lower())
    
    def get_all_positions(self) -> Dict[str, Dict]:
        """
        获取所有仓位
        
        Returns:
            所有仓位数据的字典
        """
        return self.position_cache.copy()
    
    def get_account_balance(self, asset: str = 'USDT') -> Optional[Dict]:
        """
        获取账户余额
        
        Args:
            asset: 资产名称（默认USDT）
        
        Returns:
            余额数据，或None
        """
        return self.account_data.get(asset)
    
    def get_stats(self) -> Dict:
        """获取统计数据"""
        base_stats = super().get_stats()
        return {
            **base_stats,
            'cached_positions': len(self.position_cache),
            'listen_key_active': bool(self.listen_key),
            'listen_key_renewals': self.stats.get('listen_key_renewals', 0),
            'renew_failures': self.stats.get('renew_failures', 0)
        }
    
    async def stop(self):
        """停止账户WebSocket监控"""
        logger.info("⏸️  AccountFeed 停止中...")
        
        # 取消keep-alive任务
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass
        
        # 关闭listenKey
        if self.listen_key:
            try:
                await self.binance_client.close_listen_key(self.listen_key)
                logger.debug(f"✅ listenKey已关闭: {self.listen_key[:8]}...")
            except Exception as e:
                logger.warning(f"⚠️ listenKey关闭失败: {e}")
        
        # 调用父类stop()
        await super().stop()
        
        logger.info("✅ AccountFeed 已停止")
