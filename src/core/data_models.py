"""
数据模型（v3.12.0 轻量化策略）

使用 __slots__ + dataclass 优化内存占用和访问速度
- 减少内存占用（避免 __dict__ 开销）
- 提高属性访问速度（直接槽位访问）
- 防止动态添加属性（更安全）

适用于频繁创建的数据结构：信号、持仓、交易记录
"""

from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime


@dataclass
class SignalRecord:
    """
    信号记录数据类（使用 __slots__ 优化）
    
    内存优化：
    - 无 __dict__：每个实例节省约 200-300 字节
    - 适用于高频信号生成场景
    """
    __slots__ = (
        'timestamp', 'symbol', 'direction', 'confidence',
        'accepted', 'rejection_reason',
        'trend_alignment_score', 'market_structure_score',
        'price_position_score', 'momentum_score', 'volatility_score',
        'h1_trend', 'm15_trend', 'm5_trend',
        'current_price', 'entry_price', 'stop_loss', 'take_profit',
        'rsi', 'macd', 'macd_signal', 'atr', 'bb_width_pct',
        'order_blocks_count', 'liquidity_zones_count'
    )
    
    timestamp: str
    symbol: str
    direction: str
    confidence: float
    accepted: bool
    rejection_reason: Optional[str]
    
    trend_alignment_score: float
    market_structure_score: float
    price_position_score: float
    momentum_score: float
    volatility_score: float
    
    h1_trend: str
    m15_trend: str
    m5_trend: str
    
    current_price: float
    entry_price: float
    stop_loss: float
    take_profit: float
    
    rsi: Optional[float]
    macd: Optional[float]
    macd_signal: Optional[float]
    atr: Optional[float]
    bb_width_pct: Optional[float]
    
    order_blocks_count: int
    liquidity_zones_count: int
    
    def to_dict(self) -> Dict:
        """转换为字典（用于序列化）"""
        return {slot: getattr(self, slot) for slot in self.__slots__}
    
    @classmethod
    def from_signal_data(cls, signal_data: Dict, accepted: bool, rejection_reason: Optional[str] = None):
        """从信号数据创建记录"""
        return cls(
            timestamp=signal_data.get('timestamp', datetime.now().isoformat()),
            symbol=signal_data.get('symbol', ''),
            direction=signal_data.get('direction', ''),
            confidence=signal_data.get('confidence', 0.0),
            accepted=accepted,
            rejection_reason=rejection_reason,
            
            trend_alignment_score=signal_data.get('scores', {}).get('trend_alignment', 0.0),
            market_structure_score=signal_data.get('scores', {}).get('market_structure', 0.0),
            price_position_score=signal_data.get('scores', {}).get('price_position', 0.0),
            momentum_score=signal_data.get('scores', {}).get('momentum', 0.0),
            volatility_score=signal_data.get('scores', {}).get('volatility', 0.0),
            
            h1_trend=signal_data.get('trends', {}).get('h1', 'neutral'),
            m15_trend=signal_data.get('trends', {}).get('m15', 'neutral'),
            m5_trend=signal_data.get('trends', {}).get('m5', 'neutral'),
            
            current_price=signal_data.get('current_price', 0.0),
            entry_price=signal_data.get('entry_price', 0.0),
            stop_loss=signal_data.get('stop_loss', 0.0),
            take_profit=signal_data.get('take_profit', 0.0),
            
            rsi=signal_data.get('indicators', {}).get('rsi'),
            macd=signal_data.get('indicators', {}).get('macd'),
            macd_signal=signal_data.get('indicators', {}).get('macd_signal'),
            atr=signal_data.get('indicators', {}).get('atr'),
            bb_width_pct=signal_data.get('indicators', {}).get('bb_width_pct'),
            
            order_blocks_count=len(signal_data.get('order_blocks', [])),
            liquidity_zones_count=len(signal_data.get('liquidity_zones', [])),
        )


@dataclass
class PositionOpenRecord:
    """
    开仓记录数据类（使用 __slots__ 优化）
    
    内存优化：
    - 每个实例节省约 200-300 字节
    - 适用于高频持仓创建场景
    """
    __slots__ = (
        'event', 'timestamp', 'position_id', 'is_virtual',
        'symbol', 'direction', 'entry_price', 'stop_loss', 'take_profit',
        'quantity', 'leverage', 'confidence',
        'trend_alignment_score', 'market_structure_score',
        'price_position_score', 'momentum_score', 'volatility_score',
        'rsi', 'macd', 'atr', 'bb_width_pct'
    )
    
    event: str  # 'open'
    timestamp: str
    position_id: Optional[str]
    is_virtual: bool
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    quantity: Optional[float]
    leverage: Optional[int]
    confidence: float
    
    trend_alignment_score: Optional[float]
    market_structure_score: Optional[float]
    price_position_score: Optional[float]
    momentum_score: Optional[float]
    volatility_score: Optional[float]
    
    rsi: Optional[float]
    macd: Optional[float]
    atr: Optional[float]
    bb_width_pct: Optional[float]
    
    def to_dict(self) -> Dict:
        """转换为字典（用于序列化）"""
        return {slot: getattr(self, slot) for slot in self.__slots__}
    
    @classmethod
    def from_position_data(cls, position_data: Dict, is_virtual: bool = False):
        """从持仓数据创建记录"""
        return cls(
            event='open',
            timestamp=position_data.get('timestamp', datetime.now().isoformat()),
            position_id=position_data.get('id'),
            is_virtual=is_virtual,
            symbol=position_data.get('symbol', ''),
            direction=position_data.get('direction', ''),
            entry_price=position_data.get('entry_price', 0.0),
            stop_loss=position_data.get('stop_loss', 0.0),
            take_profit=position_data.get('take_profit', 0.0),
            quantity=position_data.get('quantity'),
            leverage=position_data.get('leverage'),
            confidence=position_data.get('confidence', 0.0),
            
            trend_alignment_score=position_data.get('scores', {}).get('trend_alignment'),
            market_structure_score=position_data.get('scores', {}).get('market_structure'),
            price_position_score=position_data.get('scores', {}).get('price_position'),
            momentum_score=position_data.get('scores', {}).get('momentum'),
            volatility_score=position_data.get('scores', {}).get('volatility'),
            
            rsi=position_data.get('indicators', {}).get('rsi'),
            macd=position_data.get('indicators', {}).get('macd'),
            atr=position_data.get('indicators', {}).get('atr'),
            bb_width_pct=position_data.get('indicators', {}).get('bb_width_pct'),
        )


@dataclass
class PositionCloseRecord:
    """
    平仓记录数据类（使用 __slots__ 优化）
    
    内存优化：
    - 每个实例节省约 200-300 字节
    - 适用于高频平仓记录场景
    """
    __slots__ = (
        'event', 'timestamp', 'position_id', 'is_virtual',
        'symbol', 'direction', 'entry_price', 'exit_price',
        'pnl', 'pnl_pct', 'close_reason',
        'hold_duration', 'confidence',
        'final_rsi', 'final_macd', 'final_atr'
    )
    
    event: str  # 'close'
    timestamp: str
    position_id: Optional[str]
    is_virtual: bool
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    close_reason: str
    hold_duration: Optional[float]  # seconds
    confidence: float
    
    final_rsi: Optional[float]
    final_macd: Optional[float]
    final_atr: Optional[float]
    
    def to_dict(self) -> Dict:
        """转换为字典（用于序列化）"""
        return {slot: getattr(self, slot) for slot in self.__slots__}
    
    @classmethod
    def from_position_and_close_data(
        cls,
        position_data: Dict,
        close_data: Dict,
        is_virtual: bool = False
    ):
        """从持仓数据和平仓数据创建记录"""
        # 计算持仓时长
        entry_time = position_data.get('entry_timestamp') or position_data.get('timestamp')
        close_time = close_data.get('timestamp', datetime.now().isoformat())
        
        hold_duration = None
        if entry_time:
            try:
                entry_dt = datetime.fromisoformat(entry_time) if isinstance(entry_time, str) else entry_time
                close_dt = datetime.fromisoformat(close_time) if isinstance(close_time, str) else close_time
                hold_duration = (close_dt - entry_dt).total_seconds()
            except:
                pass
        
        return cls(
            event='close',
            timestamp=close_time,
            position_id=position_data.get('id'),
            is_virtual=is_virtual,
            symbol=position_data.get('symbol', ''),
            direction=position_data.get('direction', ''),
            entry_price=position_data.get('entry_price', 0.0),
            exit_price=close_data.get('close_price') or close_data.get('exit_price', 0.0),
            pnl=close_data.get('pnl', 0.0),
            pnl_pct=close_data.get('pnl_pct', 0.0),
            close_reason=close_data.get('close_reason', 'unknown'),
            hold_duration=hold_duration,
            confidence=position_data.get('confidence', 0.0),
            
            final_rsi=close_data.get('final_rsi'),
            final_macd=close_data.get('final_macd'),
            final_atr=close_data.get('final_atr'),
        )


@dataclass
class VirtualPosition:
    """
    虚拟仓位数据类（使用 __slots__ 优化）
    
    内存优化：
    - 每个实例节省约 200-300 字节
    - 系统可能同时维护数十个虚拟仓位
    """
    __slots__ = (
        'symbol', 'direction', 'entry_price', 'stop_loss', 'take_profit',
        'confidence', 'rank', 'entry_timestamp', 'expiry', 'status',
        'current_price', 'current_pnl', 'max_pnl', 'min_pnl',
        'h1_trend', 'm15_trend', 'm5_trend', 'market_structure',
        'order_blocks', 'liquidity_zones',
        'rsi', 'macd', 'atr'
    )
    
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    rank: int
    entry_timestamp: str
    expiry: str
    status: str  # 'active' or 'closed'
    current_price: float
    current_pnl: float
    max_pnl: float
    min_pnl: float
    
    h1_trend: str
    m15_trend: str
    m5_trend: str
    market_structure: str
    order_blocks: int
    liquidity_zones: int
    
    rsi: Optional[float]
    macd: Optional[float]
    atr: Optional[float]
    
    def to_dict(self) -> Dict:
        """转换为字典（用于序列化/兼容性）"""
        result = {}
        for slot in self.__slots__:
            value = getattr(self, slot)
            result[slot] = value
        
        # 添加兼容字段
        result['timeframes'] = {
            '1h': self.h1_trend,
            '15m': self.m15_trend,
            '5m': self.m5_trend
        }
        result['indicators'] = {
            'rsi': self.rsi,
            'macd': self.macd,
            'atr': self.atr
        }
        
        return result
    
    @classmethod
    def from_signal(cls, signal: Dict, rank: int, expiry: str):
        """从信号创建虚拟仓位"""
        timeframes = signal.get('timeframes', {})
        indicators = signal.get('indicators', {})
        
        return cls(
            symbol=signal['symbol'],
            direction=signal['direction'],
            entry_price=signal['entry_price'],
            stop_loss=signal['stop_loss'],
            take_profit=signal['take_profit'],
            confidence=signal['confidence'],
            rank=rank,
            entry_timestamp=datetime.now().isoformat(),
            expiry=expiry,
            status='active',
            current_price=signal['entry_price'],
            current_pnl=0.0,
            max_pnl=0.0,
            min_pnl=0.0,
            h1_trend=timeframes.get('1h', 'neutral'),
            m15_trend=timeframes.get('15m', 'neutral'),
            m5_trend=timeframes.get('5m', 'neutral'),
            market_structure=signal.get('market_structure', 'neutral'),
            order_blocks=signal.get('order_blocks', 0),
            liquidity_zones=signal.get('liquidity_zones', 0),
            rsi=indicators.get('rsi'),
            macd=indicators.get('macd'),
            atr=indicators.get('atr')
        )
