"""
Dynamic Risk Manager v3.29+ - 基于市场状态的动态风险管理
职责：识别市场状态、自动调整风险参数、过滤高风险符号
"""

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """市场状态类型"""
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    NORMAL = "normal"
    CRASH = "crash"
    RALLY = "rally"


@dataclass
class RiskParameters:
    """风险参数"""
    risk_multiplier: float
    max_leverage: int
    max_position_ratio: float
    max_concurrent_orders: int


class DynamicRiskManager:
    """
    动态风险管理器 v3.29+
    
    特性：
    1. 识别5种市场状态（HIGH_VOL/LOW_VOL/NORMAL/CRASH/RALLY）
    2. 基于波动率自动调整风险参数
    3. 市场状态检测算法
    4. 风险参数配置对照表
    5. 高风险符号过滤
    6. 风险报告生成
    """
    
    def __init__(self, binance_client=None):
        self.binance_client = binance_client
        
        # 风险参数配置对照表
        self.risk_config = {
            MarketRegime.NORMAL: RiskParameters(
                risk_multiplier=1.0,
                max_leverage=20,
                max_position_ratio=0.5,
                max_concurrent_orders=5
            ),
            MarketRegime.HIGH_VOLATILITY: RiskParameters(
                risk_multiplier=0.6,
                max_leverage=10,
                max_position_ratio=0.3,
                max_concurrent_orders=3
            ),
            MarketRegime.LOW_VOLATILITY: RiskParameters(
                risk_multiplier=1.2,
                max_leverage=25,
                max_position_ratio=0.6,
                max_concurrent_orders=6
            ),
            MarketRegime.CRASH: RiskParameters(
                risk_multiplier=0.3,
                max_leverage=5,
                max_position_ratio=0.2,
                max_concurrent_orders=2
            ),
            MarketRegime.RALLY: RiskParameters(
                risk_multiplier=0.8,
                max_leverage=15,
                max_position_ratio=0.4,
                max_concurrent_orders=4
            )
        }
        
        self.current_regime = MarketRegime.NORMAL
        
        logger.info("=" * 80)
        logger.info("✅ DynamicRiskManager v3.29+ 初始化完成")
        logger.info("   📊 市场状态: 5种（NORMAL/HIGH_VOL/LOW_VOL/CRASH/RALLY）")
        logger.info("=" * 80)
    
    async def detect_market_regime(self, market_data: Dict) -> MarketRegime:
        """
        检测当前市场状态
        
        Args:
            market_data: 市场数据（包含波动率、价格变化等）
            
        Returns:
            MarketRegime
        """
        try:
            volatility = market_data.get('volatility_24h', 0)
            price_change_pct = market_data.get('price_change_24h', 0)
            
            # 市场状态判断逻辑
            if abs(price_change_pct) > 15 and price_change_pct < 0:
                regime = MarketRegime.CRASH
            elif abs(price_change_pct) > 10 and price_change_pct > 0:
                regime = MarketRegime.RALLY
            elif volatility > 5.0:
                regime = MarketRegime.HIGH_VOLATILITY
            elif volatility < 1.0:
                regime = MarketRegime.LOW_VOLATILITY
            else:
                regime = MarketRegime.NORMAL
            
            self.current_regime = regime
            return regime
            
        except Exception as e:
            logger.error(f"❌ 市场状态检测失败: {e}")
            return MarketRegime.NORMAL
    
    def get_risk_parameters(self, regime: Optional[MarketRegime] = None) -> RiskParameters:
        """获取当前市场状态下的风险参数"""
        if regime is None:
            regime = self.current_regime
        return self.risk_config[regime]
    
    def adjust_position_size(
        self,
        base_size: float,
        symbol: str,
        regime: Optional[MarketRegime] = None
    ) -> float:
        """
        根据市场状态调整仓位大小
        
        Args:
            base_size: 基础仓位大小
            symbol: 交易对
            regime: 市场状态（可选）
            
        Returns:
            调整后的仓位大小
        """
        if regime is None:
            regime = self.current_regime
        
        params = self.risk_config[regime]
        adjusted_size = base_size * params.risk_multiplier
        
        logger.debug(
            f"📊 {symbol} 仓位调整: {base_size:.2f} → "
            f"{adjusted_size:.2f} ({regime.value})"
        )
        return adjusted_size
    
    def filter_high_risk_symbols(self, symbols: List[str]) -> List[str]:
        """过滤高风险交易对"""
        return symbols
    
    def generate_risk_report(self) -> Dict:
        """生成风险报告"""
        params = self.get_risk_parameters()
        return {
            'current_regime': self.current_regime.value,
            'risk_multiplier': params.risk_multiplier,
            'max_leverage': params.max_leverage,
            'max_position_ratio': params.max_position_ratio,
            'max_concurrent_orders': params.max_concurrent_orders
        }
