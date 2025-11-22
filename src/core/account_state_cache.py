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
    
    # ==================== 数据一致性 ====================
    
    def reconcile(self, api_data: Dict) -> Dict:
        """
        🔥 数据一致性校验（防止WebSocket包丢失）
        
        与REST API数据对比，检测WebSocket丢包问题
        
        Args:
            api_data: 来自REST API的账户数据
        
        Returns:
            {
                'status': 'ok' | 'warning' | 'error',
                'balance_mismatches': [...],
                'position_mismatches': [...],
                'reconciled': bool
            }
        """
        result = {
            'status': 'ok',
            'balance_mismatches': [],
            'position_mismatches': [],
            'reconciled': False
        }
        
        try:
            # 解析API数据中的余额
            api_balances = {}
            if 'balances' in api_data:
                for b in api_data['balances']:
                    asset = b.get('asset', '')
                    free = float(b.get('free', 0))
                    locked = float(b.get('locked', 0))
                    if free > 0 or locked > 0:
                        api_balances[asset] = {'free': free, 'locked': locked, 'total': free + locked}
            
            # 比较缓存余额
            for asset, api_balance in api_balances.items():
                cache_balance = self._balances.get(asset)
                
                if not cache_balance:
                    result['balance_mismatches'].append({
                        'asset': asset,
                        'issue': 'missing_in_cache',
                        'api': api_balance,
                        'cache': None
                    })
                    # 更新缓存
                    self._balances[asset] = api_balance
                    result['reconciled'] = True
                    logger.warning(f"⚠️ 缓存漂移: {asset} 在WebSocket中缺失，已从API恢复")
                
                elif abs(cache_balance['total'] - api_balance['total']) > 0.0001:
                    result['balance_mismatches'].append({
                        'asset': asset,
                        'issue': 'amount_mismatch',
                        'api': api_balance,
                        'cache': cache_balance
                    })
                    # 更新缓存为API值（API是真实来源）
                    old_total = cache_balance['total']
                    self._balances[asset] = api_balance
                    result['reconciled'] = True
                    logger.warning(
                        f"⚠️ 缓存漂移: {asset} 数额不匹配 "
                        f"(缓存: {old_total:.8f}, API: {api_balance['total']:.8f}), "
                        f"已更新缓存"
                    )
            
            # 解析API数据中的持仓
            api_positions = {}
            if 'positions' in api_data:
                for p in api_data['positions']:
                    symbol = p.get('symbol', '').lower()
                    amt = float(p.get('positionAmt', 0))
                    if abs(amt) > 0.0001:
                        api_positions[symbol] = {
                            'amount': amt,
                            'entry_price': float(p.get('entryPrice', 0)),
                            'unrealized_pnl': float(p.get('unrealizedProfit', 0))
                        }
            
            # 比较缓存持仓
            for symbol, api_pos in api_positions.items():
                cache_pos = self._positions.get(symbol)
                
                if not cache_pos:
                    result['position_mismatches'].append({
                        'symbol': symbol,
                        'issue': 'missing_in_cache',
                        'api': api_pos,
                        'cache': None
                    })
                    self._positions[symbol] = api_pos
                    result['reconciled'] = True
                    logger.warning(f"⚠️ 缓存漂移: {symbol} 持仓在WebSocket中缺失，已从API恢复")
                
                elif abs(cache_pos['amount'] - api_pos['amount']) > 0.0001:
                    result['position_mismatches'].append({
                        'symbol': symbol,
                        'issue': 'amount_mismatch',
                        'api': api_pos,
                        'cache': cache_pos
                    })
                    old_amount = cache_pos['amount']
                    self._positions[symbol] = api_pos
                    result['reconciled'] = True
                    logger.warning(
                        f"⚠️ 缓存漂移: {symbol} 持仓不匹配 "
                        f"(缓存: {old_amount}, API: {api_pos['amount']}), "
                        f"已更新缓存"
                    )
            
            # 检查缓存中存在但API中不存在的持仓（已平仓）
            for symbol in list(self._positions.keys()):
                if symbol not in api_positions:
                    result['position_mismatches'].append({
                        'symbol': symbol,
                        'issue': 'closed_in_api',
                        'api': None,
                        'cache': self._positions[symbol]
                    })
                    del self._positions[symbol]
                    result['reconciled'] = True
                    logger.warning(f"⚠️ 缓存漂移: {symbol} 已平仓但缓存中仍存在，已清除")
            
            # 设置状态
            if result['reconciled']:
                if result['balance_mismatches'] or result['position_mismatches']:
                    result['status'] = 'warning'
                    logger.warning(
                        f"⚠️ 检测到缓存漂移: {len(result['balance_mismatches'])} 个余额问题, "
                        f"{len(result['position_mismatches'])} 个持仓问题。"
                        f"已自动修复。这表明WebSocket可能丢失了部分包。"
                    )
            else:
                result['status'] = 'ok'
                logger.debug("✅ 缓存一致性验证: 无漂移")
            
            return result
        
        except Exception as e:
            logger.error(f"❌ 缓存一致性校验失败: {e}")
            result['status'] = 'error'
            return result


# 全局单例实例
account_state_cache = AccountStateCache()
