"""
🔥 AccountStateCache v1.0 - 本地优先、零轮询缓存
职责：单例内存数据库，存储账户余额、持仓、订单状态
数据流：WebSocket -> Cache -> Strategy（永远不反向）
"""

import asyncio
from typing import Dict, Optional, List
from src.utils.logger_factory import get_logger

logger = get_logger(__name__)


class AccountStateCache:
    """
    🔥 AccountStateCache v1.0 - 单例内存数据库
    
    职责：
    1. 存储 WebSocket 推送的账户数据（balances, positions, orders）
    2. 提供零网络延迟的数据查询
    3. 替代所有 REST API 轮询调用
    
    架构：
    - WebSocket AccountFeed：写入器（通过 process_message 更新）
    - Strategies/Controllers：读取器（通过 get_* 方法查询）
    - 数据永不离开内存（无网络往返）
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化缓存（仅执行一次）"""
        if self._initialized:
            return
        
        # 数据存储
        self._balances: Dict[str, Dict] = {}  # {asset: {free, locked, total}}
        self._positions: Dict[str, Dict] = {}  # {symbol: {amount, entry_price, unrealizedProfit, ...}}
        self._open_orders: Dict[str, List[Dict]] = {}  # {symbol: [orders]}
        
        # 同步控制
        self._last_update_time = 0
        self._update_count = 0
        
        self._initialized = True
        logger.info("=" * 80)
        logger.info("✅ AccountStateCache v1.0 已初始化（单例模式）")
        logger.info("   📡 数据源: WebSocket -> Cache（零轮询）")
        logger.info("   ⚡ 响应时间: <1ms（纯内存查询）")
        logger.info("=" * 80)
    
    # ==================== 平衡数据管理 ====================
    
    def update_balance(self, asset: str, free: float, locked: float) -> None:
        """
        更新单个资产余额
        
        Args:
            asset: 资产代码（如 'USDT'）
            free: 可用余额
            locked: 冻结余额
        """
        total = free + locked
        
        # 仅在值改变时更新
        old_balance = self._balances.get(asset, {})
        if (old_balance.get('free') == free and 
            old_balance.get('locked') == locked):
            return
        
        self._balances[asset] = {
            'free': free,
            'locked': locked,
            'total': total
        }
        self._update_count += 1
        logger.debug(f"💰 余额更新: {asset} = {free} (锁定: {locked})")
    
    def get_balance(self, asset: str) -> Optional[Dict]:
        """
        获取单个资产余额（即时，无网络）
        
        Args:
            asset: 资产代码
        
        Returns:
            {free, locked, total} 或 None
        """
        return self._balances.get(asset)
    
    def get_all_balances(self) -> Dict[str, Dict]:
        """获取所有余额"""
        return self._balances.copy()
    
    # ==================== 持仓管理 ====================
    
    def update_position(
        self,
        symbol: str,
        amount: float,
        entry_price: float,
        unrealized_pnl: Optional[float] = None,
        pnl_pct: Optional[float] = None,
        liquidation_price: Optional[float] = None,
        margin_type: Optional[str] = None,
        leverage: Optional[float] = None
    ) -> None:
        """
        更新单个持仓
        
        Args:
            symbol: 交易对（如 'BTCUSDT'）
            amount: 持仓数量
            entry_price: 开仓价格
            unrealized_pnl: 未实现盈亏
            pnl_pct: 盈亏百分比
            liquidation_price: 清算价格
            margin_type: 保证金类型
            leverage: 杠杆倍数
        """
        self._positions[symbol] = {
            'amount': amount,
            'entry_price': entry_price,
            'unrealized_pnl': unrealized_pnl,
            'pnl_pct': pnl_pct,
            'liquidation_price': liquidation_price,
            'margin_type': margin_type,
            'leverage': leverage
        }
        self._update_count += 1
        logger.debug(f"📊 持仓更新: {symbol} = {amount} (入价: {entry_price})")
    
    def remove_position(self, symbol: str) -> None:
        """删除平仓的持仓"""
        if symbol in self._positions:
            del self._positions[symbol]
            self._update_count += 1
            logger.debug(f"✅ 持仓已平仓: {symbol}")
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        获取单个持仓（即时，无网络）
        
        Args:
            symbol: 交易对
        
        Returns:
            持仓数据或 None（未持仓）
        """
        return self._positions.get(symbol)
    
    def get_all_positions(self) -> Dict[str, Dict]:
        """获取所有持仓"""
        return self._positions.copy()
    
    def has_position(self, symbol: str) -> bool:
        """检查是否持仓"""
        return symbol in self._positions
    
    # ==================== 订单管理 ====================
    
    def update_orders(self, symbol: str, orders: List[Dict]) -> None:
        """
        更新交易对的开放订单
        
        Args:
            symbol: 交易对
            orders: 订单列表
        """
        if orders:
            self._open_orders[symbol] = orders
        else:
            if symbol in self._open_orders:
                del self._open_orders[symbol]
        
        self._update_count += 1
    
    def get_orders(self, symbol: str) -> List[Dict]:
        """获取交易对的开放订单"""
        return self._open_orders.get(symbol, [])
    
    def get_all_orders(self) -> Dict[str, List[Dict]]:
        """获取所有开放订单"""
        return self._open_orders.copy()
    
    # ==================== 统计和调试 ====================
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        return {
            'total_updates': self._update_count,
            'assets_count': len(self._balances),
            'positions_count': len(self._positions),
            'orders_count': sum(len(orders) for orders in self._open_orders.values()),
            'total_usdt_balance': sum(b['total'] for b in self._balances.values() if b['total'] > 0)
        }
    
    def clear_cache(self) -> None:
        """清空缓存（仅用于测试或重新初始化）"""
        self._balances.clear()
        self._positions.clear()
        self._open_orders.clear()
        self._update_count = 0
        logger.warning("⚠️  缓存已清空")


# 全局单例实例
account_state_cache = AccountStateCache()
