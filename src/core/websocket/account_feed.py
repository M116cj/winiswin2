"""
AccountFeed v3.17.2+ - 即時帳戶/倉位數據流
職責：使用listenKey監控倉位變動，取代REST /fapi/v1/account輪詢
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    import websockets  # type: ignore
except ImportError:
    websockets = None  # type: ignore

logger = logging.getLogger(__name__)


class AccountFeed:
    """
    AccountFeed - Binance帳戶WebSocket監控器
    
    職責：
    1. 管理listenKey（獲取/續期/30分鐘keep-alive）
    2. 訂閱ACCOUNT_UPDATE事件
    3. 緩存即時倉位數據
    4. 提供即時倉位查詢
    
    優勢：
    - 完全移除/fapi/v1/account輪詢（零API請求）
    - 即時倉位更新（無延遲）
    - 自動帳戶變動通知
    """
    
    def __init__(self, binance_client: Any):
        """
        初始化AccountFeed
        
        Args:
            binance_client: Binance客戶端（用於獲取listenKey）
        """
        self.binance_client = binance_client
        self.listen_key: Optional[str] = None
        self.position_cache: Dict[str, Dict] = {}  # {symbol: position_data}
        self.account_data: Dict[str, Any] = {}  # 帳戶餘額等數據
        self.running = False
        self.ws_task: Optional[asyncio.Task] = None
        self.keep_alive_task: Optional[asyncio.Task] = None
        
        # 統計數據
        self.stats = {
            'total_updates': 0,
            'reconnections': 0,
            'errors': 0,
            'listen_key_renewals': 0
        }
        
        logger.info("=" * 80)
        logger.info("✅ AccountFeed 初始化完成")
        logger.info("   📡 監控類型: ACCOUNT_UPDATE（即時倉位）")
        logger.info("   🔌 WebSocket URL: wss://fstream.binance.com/ws/")
        logger.info("   ⏱️  listenKey續期: 每30分鐘")
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
            
            # 3. 啟動listenKey續期任務（每30分鐘）
            self.keep_alive_task = asyncio.create_task(self._keep_alive())
            
            logger.info("✅ AccountFeed 已啟動")
            
        except Exception as e:
            logger.error(f"❌ AccountFeed 啟動失敗: {e}")
            self.running = False
            raise
    
    async def _keep_alive(self):
        """每30分鐘續期listenKey"""
        while self.running:
            try:
                await asyncio.sleep(1800)  # 30分鐘
                
                if self.listen_key:
                    await self.binance_client.renew_listen_key(self.listen_key)
                    self.stats['listen_key_renewals'] += 1
                    logger.debug(f"🔄 listenKey已續期: {self.listen_key[:8]}...")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ listenKey續期失敗: {e}")
                await asyncio.sleep(5)
    
    async def _listen_account(self):
        """
        監聽帳戶WebSocket流
        """
        if not self.listen_key:
            logger.error("❌ listenKey為空，無法啟動AccountFeed")
            return
        
        url = f"wss://fstream.binance.com/ws/{self.listen_key}"
        reconnect_delay = 5
        
        while self.running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:  # type: ignore
                    logger.debug("✅ 帳戶WebSocket已連接")
                    
                    while self.running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30)
                            data = json.loads(msg)
                            
                            # 處理ACCOUNT_UPDATE事件
                            if data.get('e') == 'ACCOUNT_UPDATE':
                                self._update_account(data)
                            
                            # 處理ORDER_TRADE_UPDATE事件（訂單狀態）
                            elif data.get('e') == 'ORDER_TRADE_UPDATE':
                                self._update_order(data)
                            
                        except asyncio.TimeoutError:
                            try:
                                await ws.ping()
                            except Exception:
                                logger.warning("⚠️ 帳戶WebSocket ping失敗，重連中...")
                                break
                        
                        except Exception as e:
                            logger.error(f"❌ 帳戶WebSocket接收失敗: {e}")
                            self.stats['errors'] += 1
                            break
            
            except Exception as e:
                self.stats['reconnections'] += 1
                logger.warning(f"🔄 帳戶WebSocket重連中... (錯誤: {e})")
                
                # 重新獲取listenKey
                try:
                    self.listen_key = await self.binance_client.get_listen_key()
                    url = f"wss://fstream.binance.com/ws/{self.listen_key}"
                    logger.info(f"✅ listenKey已重新獲取: {self.listen_key[:8]}...")
                except Exception as ke:
                    logger.error(f"❌ listenKey重新獲取失敗: {ke}")
                
                await asyncio.sleep(reconnect_delay)
    
    def _update_account(self, data: dict):
        """
        更新帳戶數據（處理ACCOUNT_UPDATE事件）
        
        Args:
            data: ACCOUNT_UPDATE事件數據
        """
        try:
            account_data = data.get('a', {})
            
            # 更新帳戶餘額
            if 'B' in account_data:
                for balance in account_data['B']:
                    asset = balance['a']
                    self.account_data[asset] = {
                        'balance': float(balance['wb']),  # wallet balance
                        'cross_un_pnl': float(balance['cw'])  # cross unrealized PnL
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
                            'update_time': data.get('T', int(datetime.now().timestamp() * 1000))
                        }
                        logger.debug(
                            f"📊 {symbol.upper()} 倉位更新: "
                            f"size={position_amt}, pnl={position['up']}"
                        )
                    else:
                        # 倉位已平倉
                        if symbol in self.position_cache:
                            del self.position_cache[symbol]
                            logger.debug(f"🔄 {symbol.upper()} 倉位已清除")
            
            self.stats['total_updates'] += 1
            
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
        return {
            **self.stats,
            'cached_positions': len(self.position_cache),
            'running': self.running,
            'listen_key_active': bool(self.listen_key)
        }
    
    async def stop(self):
        """停止帳戶WebSocket監控"""
        logger.info("⏸️  AccountFeed 停止中...")
        self.running = False
        
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
