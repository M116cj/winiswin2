"""
虛擬倉位真實性監控器 v3.17.10+
職責：模擬真實交易條件（滑點、流動性、強平）

解決「模擬偏誤」問題：
- 虛擬倉位使用理想價格，忽略真實市場摩擦
- 導致模型過度樂觀，實盤表現差於虛擬倉位
"""

import logging
from typing import Dict, Optional
from src.core.data_models import VirtualPosition

logger = logging.getLogger(__name__)


class VirtualPositionMonitor:
    """
    虛擬倉位真實性監控器
    
    核心功能：
    1. 加入滑點（基於流動性分數）
    2. 調整成交價（模擬真實成交）
    3. 模擬強平（基於保證金比率）
    """
    
    def __init__(self, binance_client=None):
        """
        初始化虛擬倉位監控器
        
        Args:
            binance_client: Binance 客戶端（用於獲取流動性數據）
        """
        self.binance_client = binance_client
        
        # 流動性緩存（symbol -> liquidity_score）
        self.liquidity_cache: Dict[str, float] = {}
        
        logger.info("=" * 60)
        logger.info("✅ 虛擬倉位真實性監控器已創建 v3.17.10+")
        logger.info("   🎯 功能：滑點 + 流動性 + 強平模擬")
        logger.info("=" * 60)
    
    def _simulate_realistic_pnl(
        self, 
        virtual_pos: VirtualPosition, 
        current_price: float
    ) -> Dict[str, float]:
        """
        模擬真實交易條件
        
        Args:
            virtual_pos: 虛擬倉位對象
            current_price: 當前市場價格
            
        Returns:
            包含 effective_price, pnl, pnl_pct, is_liquidated 的字典
        """
        try:
            # 1. 加入滑點（基於流動性分數）
            liquidity_score = self._get_liquidity_score(virtual_pos.symbol)
            slippage = max(0.001, 0.003 * (1 - liquidity_score))  # 0.1%~0.3%
            
            # 2. 調整成交價
            if virtual_pos.direction == "LONG":
                effective_price = current_price * (1 + slippage)
            else:  # SHORT
                effective_price = current_price * (1 - slippage)
            
            # 3. 模擬強平（基於保證金比率）
            margin_ratio = self._calculate_margin_ratio(virtual_pos, effective_price)
            
            # Binance 強平線 ≈100%，80% 安全邊際
            if margin_ratio >= 0.8:
                return self._simulate_liquidation(virtual_pos, effective_price)
            
            # 4. 計算 PnL
            return self._calculate_pnl(virtual_pos, effective_price)
            
        except Exception as e:
            logger.error(f"模擬真實 PnL 失敗 {virtual_pos.symbol}: {e}", exc_info=True)
            # 降級到簡單計算
            return self._calculate_pnl(virtual_pos, current_price)
    
    def _get_liquidity_score(self, symbol: str) -> float:
        """
        獲取流動性分數（0~1）
        
        邏輯：
        - 主流幣（BTC/ETH/BNB）: 0.9+
        - 中流動性幣: 0.6~0.9
        - 低流動性幣: 0.3~0.6
        
        Args:
            symbol: 交易對
            
        Returns:
            流動性分數 (0~1)
        """
        # 檢查緩存
        if symbol in self.liquidity_cache:
            return self.liquidity_cache[symbol]
        
        # 主流幣映射
        high_liquidity_symbols = {
            'BTCUSDT': 0.95,
            'ETHUSDT': 0.92,
            'BNBUSDT': 0.90,
            'SOLUSDT': 0.88,
            'ADAUSDT': 0.85,
            'XRPUSDT': 0.85,
            'DOGEUSDT': 0.82,
            'MATICUSDT': 0.80
        }
        
        if symbol in high_liquidity_symbols:
            score = high_liquidity_symbols[symbol]
        else:
            # 默認中等流動性
            score = 0.70
        
        # 緩存
        self.liquidity_cache[symbol] = score
        
        return score
    
    def _calculate_margin_ratio(
        self, 
        virtual_pos: VirtualPosition, 
        current_price: float
    ) -> float:
        """
        計算保證金比率
        
        保證金比率 = 虧損 / 初始保證金
        
        Args:
            virtual_pos: 虛擬倉位
            current_price: 當前價格
            
        Returns:
            保證金比率 (0~1+)
        """
        try:
            entry_price = virtual_pos.entry_price
            leverage = virtual_pos.leverage
            direction = virtual_pos.direction
            
            # 計算價格變化百分比
            if direction == "LONG":
                price_change_pct = (current_price - entry_price) / entry_price
            else:  # SHORT
                price_change_pct = (entry_price - current_price) / entry_price
            
            # 槓桿化虧損百分比
            leveraged_pnl_pct = price_change_pct * leverage
            
            # 保證金比率（虧損佔初始保證金的比例）
            # 虧損 = -leveraged_pnl_pct（負數表示虧損）
            margin_ratio = -leveraged_pnl_pct if leveraged_pnl_pct < 0 else 0
            
            return margin_ratio
            
        except Exception as e:
            logger.error(f"計算保證金比率失敗: {e}")
            return 0.0
    
    def _simulate_liquidation(
        self, 
        virtual_pos: VirtualPosition, 
        liquidation_price: float
    ) -> Dict[str, float]:
        """
        模擬強平事件
        
        Args:
            virtual_pos: 虛擬倉位
            liquidation_price: 強平價格
            
        Returns:
            強平結果字典
        """
        logger.warning(
            f"⚠️ 虛擬倉位強平: {virtual_pos.symbol} {virtual_pos.direction} "
            f"入場={virtual_pos.entry_price:.2f} 強平={liquidation_price:.2f} "
            f"槓桿={virtual_pos.leverage:.1f}x"
        )
        
        return {
            'effective_price': liquidation_price,
            'pnl': -100.0,  # 100% 虧損
            'pnl_pct': -1.0,  # -100%
            'is_liquidated': True,
            'close_reason': 'liquidation'
        }
    
    def _calculate_pnl(
        self, 
        virtual_pos: VirtualPosition, 
        effective_price: float
    ) -> Dict[str, float]:
        """
        計算 PnL（正常情況）
        
        Args:
            virtual_pos: 虛擬倉位
            effective_price: 有效成交價格
            
        Returns:
            PnL 結果字典
        """
        try:
            entry_price = virtual_pos.entry_price
            leverage = virtual_pos.leverage
            direction = virtual_pos.direction
            
            # 計算價格變化百分比
            if direction == "LONG":
                price_change_pct = (effective_price - entry_price) / entry_price
            else:  # SHORT
                price_change_pct = (entry_price - effective_price) / entry_price
            
            # 槓桿化 PnL
            pnl_pct = price_change_pct * leverage
            
            # 限制最大虧損為 100%（避免負數保證金）
            pnl_pct = max(-1.0, pnl_pct)
            
            # 轉換為百分比（0.05 -> 5.0）
            pnl = pnl_pct * 100
            
            return {
                'effective_price': effective_price,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'is_liquidated': False,
                'close_reason': None
            }
            
        except Exception as e:
            logger.error(f"計算 PnL 失敗: {e}")
            return {
                'effective_price': effective_price,
                'pnl': 0.0,
                'pnl_pct': 0.0,
                'is_liquidated': False,
                'close_reason': 'error'
            }
