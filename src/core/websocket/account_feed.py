"""
AccountFeed v3.17.2+ - 即時帳戶/倉位數據流（升級版）
職責：使用listenKey監控倉位變動，取代REST /fapi/v1/account輪詢
升級：心跳監控、REST智慧冷卻、時間戳標準化、listenKey自動續期優化
"""

import asyncio
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime

try:
    import websockets  # type: ignore
except ImportError:
    websockets = None  # type: ignore

from src.core.websocket.base_feed import BaseFeed

logger = logging.getLogger(__name__)


class AccountFeed(BaseFeed):
    """
    AccountFeed - Binance帳戶WebSocket監控器（v3.17.2+升級版）
    
    職責：
    1. 管理listenKey（獲取/自動續期/智能重試）
    2. 訂閱ACCOUNT_UPDATE事件
    3. 緩存即時倉位數據
    4. 提供即時倉位查詢
    5. 心跳監控（30秒無訊息→重連）
    6. REST備援智慧冷卻（指數退避）
    
    優勢：
    - 完全移除/fapi/v1/account輪詢（零API請求）
    - 即時倉位更新（無延遲）
    - 自動帳戶變動通知
    - listenKey自動續期（每15分鐘，比過期早一半）
    - 續期失敗自動重試（最多3次）
    - 網路延遲追蹤
    """
    
    def __init__(self, binance_client: Any, recv_timeout: int = 120):
        """
        初始化AccountFeed
        
        Args:
            binance_client: Binance客戶端（用於獲取listenKey）
            recv_timeout: WebSocket接收超時（秒，默認120）
        """
        super().__init__(name="AccountFeed")
        
        self.binance_client = binance_client
        self.listen_key: Optional[str] = None
        self.position_cache: Dict[str, Dict] = {}  # {symbol: position_data}
        self.account_data: Dict[str, Any] = {}  # 帳戶餘額等數據
        self.ws_task: Optional[asyncio.Task] = None
        self.keep_alive_task: Optional[asyncio.Task] = None
        self.health_check_task: Optional[asyncio.Task] = None  # 健康檢查任務
        self.recv_timeout = recv_timeout  # 可配置的接收超時
        self.ws_connection = None  # 當前WebSocket連接
        self.last_message_time = None  # 最後消息時間
        
        logger.info("=" * 80)
        logger.info("✅ AccountFeed 初始化完成")
        logger.info("   📡 監控類型: ACCOUNT_UPDATE（即時倉位）")
        logger.info("   🔌 WebSocket URL: wss://fstream.binance.com/ws/")
        logger.info("   ⏱️  listenKey自動續期: 每15分鐘（過期前提前續期）")
        logger.info(f"   ⏱️  接收超時: {recv_timeout}秒（可配置）")
        logger.info("   💓 健康檢查: 每30秒主動ping")
        logger.info("   🔄 智能重連: 指數退避（5-60秒）")
        logger.info("=" * 80)
    
    async def start(self):
        """啟動帳戶WebSocket監控"""
        if not websockets:
            logger.error("❌ AccountFeed: websockets模塊未安裝")
            return
        
        self.running = True
        logger.info("🚀 AccountFeed 啟動中...")
        
        try:
            # 1. 獲取listenKey
            self.listen_key = await self.binance_client.get_listen_key()
            logger.info(f"✅ listenKey已獲取: {self.listen_key[:8]}...")
            
            # 2. 啟動WebSocket監聽
            self.ws_task = asyncio.create_task(self._listen_account())
            
            # 3. 啟動listenKey續期任務（每15分鐘）
            self.keep_alive_task = asyncio.create_task(self._keep_alive())
            
            # 4. 啟動健康檢查任務（每30秒主動ping，取代舊的heartbeat monitor）
            self.health_check_task = asyncio.create_task(self._health_check_loop())
            
            logger.info("✅ AccountFeed 已啟動（使用主動健康檢查，120秒空閒容忍）")
            
        except Exception as e:
            logger.error(f"❌ AccountFeed 啟動失敗: {e}")
            self.running = False
            raise
    
    async def _keep_alive(self):
        """
        自動續期listenKey（優化版）
        
        改進：
        - 每15分鐘續期（比30分鐘過期時間提前一半，更安全）
        - 續期失敗時立即重試（最多3次）
        - 記錄續期成功率
        """
        while self.running:
            try:
                await asyncio.sleep(900)  # 15分鐘（比30分鐘過期早一半）
                
                if not self.listen_key:
                    logger.warning("⚠️ listenKey為空，跳過續期")
                    continue
                
                # 嘗試續期（最多重試3次）
                success = False
                for attempt in range(3):
                    try:
                        await self.binance_client.renew_listen_key(self.listen_key)
                        self.stats['listen_key_renewals'] = \
                            self.stats.get('listen_key_renewals', 0) + 1
                        logger.info(f"✅ listenKey已續期: {self.listen_key[:8]}... (第{attempt+1}次嘗試)")
                        success = True
                        break
                    except Exception as e:
                        logger.warning(f"⚠️ listenKey續期失敗 (第{attempt+1}次): {e}")
                        if attempt < 2:  # 前2次失敗後等待重試
                            await asyncio.sleep(5)
                
                if not success:
                    logger.error("❌ listenKey續期連續失敗3次，可能需要重新獲取")
                    # 標記需要重連（WebSocket循環會自動處理）
                    self.stats['renew_failures'] = self.stats.get('renew_failures', 0) + 1
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ listenKey續期循環異常: {e}")
                await asyncio.sleep(5)
    
    async def _health_check_loop(self):
        """
        健康檢查循環（v3.17.2+ 主動ping避免誤判超時）
        
        改進：
        - 每30秒主動ping一次WebSocket連接
        - 避免在空閒期誤判為超時
        - 提前發現連接死亡並觸發重連
        """
        while self.running:
            try:
                await asyncio.sleep(30)  # 每30秒檢查一次
                
                if self.ws_connection:
                    try:
                        # 主動ping測試連接（websockets.ping()返回awaitable，直接await即可）
                        pong_waiter = self.ws_connection.ping()
                        await asyncio.wait_for(pong_waiter, timeout=10)
                        logger.debug("💓 AccountFeed健康檢查通過")
                    except Exception as e:
                        logger.warning(f"⚠️ AccountFeed健康檢查失敗: {e}，關閉連接觸發重連")
                        self.stats['health_check_failures'] = \
                            self.stats.get('health_check_failures', 0) + 1
                        
                        # 主動關閉連接，觸發_listen_account()的重連邏輯
                        try:
                            await self.ws_connection.close()
                        except Exception:
                            pass  # 忽略關閉錯誤
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 健康檢查循環異常: {e}")
                await asyncio.sleep(5)
    
    async def _listen_account(self):
        """
        監聽帳戶WebSocket流（v3.17.2+ 改進超時處理）
        """
        if not self.listen_key:
            logger.error("❌ listenKey為空，無法啟動AccountFeed")
            return
        
        url = f"wss://fstream.binance.com/ws/{self.listen_key}"
        reconnect_delay = 5
        max_reconnect_delay = 60  # 最大重連延遲
        
        while self.running:
            try:
                # v3.20.7 Railway環境優化：增加ping_timeout容忍網絡延遲
                async with websockets.connect(
                    url, 
                    ping_interval=15,      # 每15秒發送ping
                    ping_timeout=60,       # 60秒等待pong回應（Railway環境網絡延遲優化）
                    close_timeout=10,      # 10秒關閉超時
                    max_size=2**20         # 1MB消息緩衝區
                ) as ws:  # type: ignore
                    logger.info("✅ 帳戶WebSocket已連接")
                    self.ws_connection = ws  # 保存連接供健康檢查使用
                    reconnect_delay = 5  # 重置重連延遲
                    self.last_message_time = datetime.now()
                    
                    try:
                        while self.running:
                            try:
                                msg = await asyncio.wait_for(
                                    ws.recv(), 
                                    timeout=self.recv_timeout
                                )
                                data = json.loads(msg)
                                
                                # 更新最後消息時間
                                self.last_message_time = datetime.now()
                                
                                # 更新心跳
                                self._update_heartbeat()
                                
                                # 處理ACCOUNT_UPDATE事件
                                if data.get('e') == 'ACCOUNT_UPDATE':
                                    self._update_account(data)
                                
                                # 處理ORDER_TRADE_UPDATE事件（訂單狀態）
                                elif data.get('e') == 'ORDER_TRADE_UPDATE':
                                    self._update_order(data)
                            
                            except asyncio.TimeoutError:
                                # 120秒無消息（正常，帳戶可能無變動）
                                time_since_last = (datetime.now() - self.last_message_time).total_seconds()
                                logger.debug(
                                    f"⏱️  AccountFeed空閒 {time_since_last:.0f}秒 "
                                    f"(最大: {self.recv_timeout}秒)"
                                )
                                
                                # 檢查連接是否仍然健康（由健康檢查任務處理）
                                # 如果連接真的死了，健康檢查會檢測到
                                continue
                            
                            except Exception as e:
                                logger.error(f"❌ 帳戶WebSocket接收失敗: {e}")
                                self.stats['errors'] += 1
                                break
                    finally:
                        # 清除連接引用，避免健康檢查使用過期連接
                        self.ws_connection = None
            
            except Exception as e:
                self.stats['reconnections'] += 1
                logger.warning(
                    f"🔄 帳戶WebSocket重連中... "
                    f"(錯誤: {e}, 延遲: {reconnect_delay}秒)"
                )
                
                # 重新獲取listenKey
                try:
                    self.listen_key = await self.binance_client.get_listen_key()
                    url = f"wss://fstream.binance.com/ws/{self.listen_key}"
                    logger.info(f"✅ listenKey已重新獲取: {self.listen_key[:8]}...")
                except Exception as ke:
                    logger.error(f"❌ listenKey重新獲取失敗: {ke}")
                    # 增加重連延遲（指數退避）
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                
                await asyncio.sleep(reconnect_delay)
    
    def _update_account(self, data: dict):
        """
        更新帳戶數據（處理ACCOUNT_UPDATE事件）
        
        Args:
            data: ACCOUNT_UPDATE事件數據
        """
        try:
            account_data = data.get('a', {})
            
            # 獲取時間戳
            server_ts = self.get_server_timestamp_ms(data, 'E')  # 事件時間
            local_ts = self.get_local_timestamp_ms()
            latency_ms = self.calculate_latency_ms(server_ts, local_ts)
            
            # 更新帳戶餘額
            if 'B' in account_data:
                for balance in account_data['B']:
                    asset = balance['a']
                    wallet_balance = float(balance['wb'])  # 總錢包餘額
                    cross_wallet_balance = float(balance['cw'])  # 跨倉餘額（可用餘額）
                    
                    # 🔥 v3.18.4：計算保證金（與REST API格式一致）
                    # 保證金 = 總錢包餘額 - 跨倉餘額
                    total_margin = wallet_balance - cross_wallet_balance
                    
                    self.account_data[asset] = {
                        'total_balance': wallet_balance,  # 總餘額（與REST API一致）
                        'available_balance': cross_wallet_balance,  # 可用餘額
                        'total_margin': total_margin,  # 🔥 新增：總保證金（與REST API一致）
                        'balance': wallet_balance,  # 兼容舊代碼
                        'cross_un_pnl': float(balance.get('bc', 0)),  # cross unrealized PnL
                        'server_timestamp': server_ts,
                        'local_timestamp': local_ts,
                        'latency_ms': latency_ms
                    }
            
            # 更新倉位
            if 'P' in account_data:
                for position in account_data['P']:
                    symbol = position['s'].lower()
                    position_amt = float(position['pa'])
                    
                    if position_amt != 0:  # 非零倉位
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
                            f"📊 {symbol.upper()} 倉位更新: "
                            f"size={position_amt}, pnl={position['up']}, "
                            f"latency={latency_ms}ms"
                        )
                    else:
                        # 倉位已平倉
                        if symbol in self.position_cache:
                            del self.position_cache[symbol]
                            logger.debug(f"🔄 {symbol.upper()} 倉位已清除")
            
        except Exception as e:
            logger.error(f"❌ 解析ACCOUNT_UPDATE失敗: {e}", exc_info=True)
    
    def _update_order(self, data: dict):
        """
        更新訂單狀態（處理ORDER_TRADE_UPDATE事件）
        
        Args:
            data: ORDER_TRADE_UPDATE事件數據
        """
        try:
            order_data = data.get('o', {})
            symbol = order_data.get('s', '').lower()
            order_status = order_data.get('X', '')
            
            logger.debug(
                f"📝 {symbol.upper()} 訂單更新: "
                f"status={order_status}, side={order_data.get('S')}"
            )
            
        except Exception as e:
            logger.error(f"❌ 解析ORDER_TRADE_UPDATE失敗: {e}")
    
    async def _on_heartbeat_timeout(self):
        """心跳超時處理（觸發重連）"""
        logger.warning("⚠️ AccountFeed 心跳超時，正在等待自動重連...")
        # WebSocket會自動重連（_listen_account的while循環）
    
    # ==================== 數據查詢接口 ====================
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        獲取即時倉位數據
        
        Args:
            symbol: 交易對
        
        Returns:
            倉位數據，或None（如果無倉位）
        """
        return self.position_cache.get(symbol.lower())
    
    def get_all_positions(self) -> Dict[str, Dict]:
        """
        獲取所有倉位
        
        Returns:
            所有倉位數據的字典
        """
        return self.position_cache.copy()
    
    def get_account_balance(self, asset: str = 'USDT') -> Optional[Dict]:
        """
        獲取帳戶餘額
        
        Args:
            asset: 資產名稱（默認USDT）
        
        Returns:
            餘額數據，或None
        """
        return self.account_data.get(asset)
    
    def get_stats(self) -> Dict:
        """
        獲取統計數據
        
        Returns:
            統計數據字典
        """
        base_stats = super().get_stats()
        return {
            **base_stats,
            'cached_positions': len(self.position_cache),
            'listen_key_active': bool(self.listen_key),
            'listen_key_renewals': self.stats.get('listen_key_renewals', 0),
            'renew_failures': self.stats.get('renew_failures', 0)
        }
    
    async def stop(self):
        """停止帳戶WebSocket監控"""
        logger.info("⏸️  AccountFeed 停止中...")
        self.running = False
        
        # 取消健康檢查任務
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        
        # 取消keep-alive任務
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass
        
        # 取消WebSocket任務
        if self.ws_task:
            self.ws_task.cancel()
            try:
                await self.ws_task
            except asyncio.CancelledError:
                pass
        
        # 關閉listenKey
        if self.listen_key:
            try:
                await self.binance_client.close_listen_key(self.listen_key)
                logger.debug(f"✅ listenKey已關閉: {self.listen_key[:8]}...")
            except Exception as e:
                logger.warning(f"⚠️ listenKey關閉失敗: {e}")
        
        logger.info("✅ AccountFeed 已停止")
