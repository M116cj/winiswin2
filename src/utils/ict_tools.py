"""
ICT/SMC 工具类 v3.19
提供订单块、FVG、摆动点等识别功能
"""

import logging
from typing import List, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class ICTTools:
    """ICT/SMC策略工具类"""
    
    @staticmethod
    def find_swing_highs_lows(klines: List[Dict], lookback: int = 5) -> Dict:
        """
        识别摆动高低点
        
        Args:
            klines: K线数据列表
            lookback: 回看窗口
        
        Returns:
            {
                'swing_highs': [(index, price), ...],
                'swing_lows': [(index, price), ...]
            }
        """
        swing_highs = []
        swing_lows = []
        
        for i in range(lookback, len(klines) - lookback):
            current_high = klines[i]['high']
            current_low = klines[i]['low']
            
            # 检查是否为摆动高点
            is_swing_high = all(
                current_high > klines[j]['high'] 
                for j in range(i - lookback, i + lookback + 1) 
                if j != i
            )
            
            if is_swing_high:
                swing_highs.append((i, current_high))
            
            # 检查是否为摆动低点
            is_swing_low = all(
                current_low < klines[j]['low'] 
                for j in range(i - lookback, i + lookback + 1) 
                if j != i
            )
            
            if is_swing_low:
                swing_lows.append((i, current_low))
        
        return {
            'swing_highs': swing_highs,
            'swing_lows': swing_lows
        }
    
    @staticmethod
    def calculate_market_structure(klines: List[Dict], lookback: int = 5) -> int:
        """
        计算市场结构
        
        Returns:
            1: 多头结构（Higher Highs & Higher Lows）
            -1: 空头结构（Lower Highs & Lower Lows）
            0: 中性结构
        """
        if len(klines) < 10:
            return 0
        
        swings = ICTTools.find_swing_highs_lows(klines, lookback)
        
        swing_highs = swings['swing_highs']
        swing_lows = swings['swing_lows']
        
        # 需要至少2个摆动点才能判断趋势
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 0
        
        # 检查最近的摆动高点和低点
        recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
        recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows
        
        # 判断是否为上升趋势（Higher Highs & Higher Lows）
        highs_rising = all(
            recent_highs[i][1] < recent_highs[i+1][1] 
            for i in range(len(recent_highs) - 1)
        )
        lows_rising = all(
            recent_lows[i][1] < recent_lows[i+1][1] 
            for i in range(len(recent_lows) - 1)
        )
        
        if highs_rising and lows_rising:
            return 1  # 多头结构
        
        # 判断是否为下降趋势（Lower Highs & Lower Lows）
        highs_falling = all(
            recent_highs[i][1] > recent_highs[i+1][1] 
            for i in range(len(recent_highs) - 1)
        )
        lows_falling = all(
            recent_lows[i][1] > recent_lows[i+1][1] 
            for i in range(len(recent_lows) - 1)
        )
        
        if highs_falling and lows_falling:
            return -1  # 空头结构
        
        return 0  # 中性结构
    
    @staticmethod
    def detect_order_blocks(klines: List[Dict], window: int = 50) -> int:
        """
        检测订单块数量
        
        订单块识别条件:
        - 看涨订单块: 价格创新低后，出现阴线，随后突破该阴线高点
        - 看跌订单块: 价格创新高后，出现阳线，随后跌破该阳线低点
        
        Returns:
            已验证的订单块数量
        """
        if len(klines) < 10:
            return 0
        
        order_blocks = []
        
        for i in range(2, min(len(klines) - 1, window)):
            current = klines[i]
            next_candle = klines[i + 1]
            
            # 检查是否创新低（最近5根K线）
            recent_lows = [klines[j]['low'] for j in range(max(0, i-5), i)]
            is_new_low = current['low'] < min(recent_lows) if recent_lows else False
            
            # 检查是否创新高
            recent_highs = [klines[j]['high'] for j in range(max(0, i-5), i)]
            is_new_high = current['high'] > max(recent_highs) if recent_highs else False
            
            # 看涨订单块
            if is_new_low and current['close'] < current['open']:
                if next_candle['high'] > current['high']:
                    order_blocks.append({
                        'type': 'bullish',
                        'index': i,
                        'zone': (current['low'], current['high'])
                    })
            
            # 看跌订单块
            if is_new_high and current['close'] > current['open']:
                if next_candle['low'] < current['low']:
                    order_blocks.append({
                        'type': 'bearish',
                        'index': i,
                        'zone': (current['low'], current['high'])
                    })
        
        # 验证订单块（检查价格是否回测并反转）
        verified_count = 0
        for ob in order_blocks:
            if ICTTools._is_order_block_verified(ob, klines):
                verified_count += 1
        
        return verified_count
    
    @staticmethod
    def _is_order_block_verified(order_block: Dict, klines: List[Dict]) -> bool:
        """验证订单块是否被价格回测"""
        ob_index = order_block['index']
        ob_zone = order_block['zone']
        
        # 检查后续K线是否回测该区域
        for i in range(ob_index + 2, min(ob_index + 20, len(klines))):
            kline = klines[i]
            # 价格进入订单块区域
            if kline['low'] <= ob_zone[1] and kline['high'] >= ob_zone[0]:
                return True
        
        return False
    
    @staticmethod
    def detect_institutional_candle(kline: Dict, recent_klines: List[Dict]) -> int:
        """
        检测机构K线
        
        条件:
        1. 实体比率 > 0.7
        2. 成交量Z值 > 2
        3. 影线比率 < 0.3
        
        Returns:
            1: 是机构K线
            0: 不是
        """
        if not kline or not recent_klines:
            return 0
        
        # 计算实体比率
        body = abs(kline['close'] - kline['open'])
        range_size = kline['high'] - kline['low']
        body_ratio = body / range_size if range_size > 0 else 0
        
        # 计算成交量Z值
        volumes = [k.get('volume', 0) for k in recent_klines[-20:]]
        if len(volumes) < 2:
            return 0
        
        mean_vol = np.mean(volumes)
        std_vol = np.std(volumes)
        volume_z = (kline.get('volume', 0) - mean_vol) / std_vol if std_vol > 0 else 0
        
        # 计算影线比率
        upper_wick = kline['high'] - max(kline['open'], kline['close'])
        lower_wick = min(kline['open'], kline['close']) - kline['low']
        wick_ratio = (upper_wick + lower_wick) / range_size if range_size > 0 else 0
        
        # 判断
        if body_ratio > 0.7 and volume_z > 2 and wick_ratio < 0.3:
            return 1
        else:
            return 0
    
    @staticmethod
    def detect_liquidity_grab(klines: List[Dict], atr: float) -> int:
        """
        检测流动性抓取
        
        条件:
        1. 价格突破最近摆动点 > 0.5 ATR
        2. 下一根K线迅速反转
        
        Returns:
            1: 检测到流动性抓取
            0: 未检测到
        """
        if len(klines) < 10 or atr == 0:
            return 0
        
        swings = ICTTools.find_swing_highs_lows(klines[:-2], lookback=5)
        
        if not swings['swing_highs'] or not swings['swing_lows']:
            return 0
        
        swing_high = swings['swing_highs'][-1][1]
        swing_low = swings['swing_lows'][-1][1]
        
        current = klines[-1]
        previous = klines[-2]
        
        # 检测向上突破后反转
        if current['high'] > swing_high + 0.5 * atr:
            if current['close'] < swing_high:
                return 1
        
        # 检测向下突破后反转
        if current['low'] < swing_low - 0.5 * atr:
            if current['close'] > swing_low:
                return 1
        
        return 0
    
    @staticmethod
    def detect_fvg(klines: List[Dict], window: int = 30) -> int:
        """
        检测公允价值缺口（FVG）数量
        
        条件:
        - 看涨FVG: K1最低价 > K3最高价
        - 看跌FVG: K1最高价 < K3最低价
        
        Returns:
            未回填的FVG数量
        """
        if len(klines) < 3:
            return 0
        
        fvgs = []
        
        for i in range(len(klines) - 2):
            k1 = klines[i]
            k2 = klines[i + 1]
            k3 = klines[i + 2]
            
            # 看涨FVG
            if k1['low'] > k3['high']:
                fvgs.append({
                    'type': 'bullish',
                    'gap': (k3['high'], k1['low']),
                    'index': i
                })
            
            # 看跌FVG
            if k1['high'] < k3['low']:
                fvgs.append({
                    'type': 'bearish',
                    'gap': (k1['high'], k3['low']),
                    'index': i
                })
        
        # 统计未回填的FVG
        unfilled_count = 0
        for fvg in fvgs:
            if not ICTTools._is_fvg_filled(fvg, klines):
                unfilled_count += 1
        
        return unfilled_count
    
    @staticmethod
    def _is_fvg_filled(fvg: Dict, klines: List[Dict]) -> bool:
        """检查FVG是否被回填"""
        fvg_index = fvg['index']
        gap = fvg['gap']
        
        # 检查后续K线是否回填缺口
        for i in range(fvg_index + 3, len(klines)):
            kline = klines[i]
            # 价格进入缺口区域
            if kline['low'] <= gap[1] and kline['high'] >= gap[0]:
                return True
        
        return False
    
    @staticmethod
    def calculate_swing_distance(klines: List[Dict], current_price: float, atr: float, 
                                 distance_type: str = 'high') -> float:
        """
        计算到摆动点的标准化距离
        
        Args:
            klines: K线数据
            current_price: 当前价格
            atr: ATR值
            distance_type: 'high'或'low'
        
        Returns:
            标准化距离（使用ATR）
        """
        if len(klines) < 10 or atr == 0:
            return 0.0
        
        swings = ICTTools.find_swing_highs_lows(klines, lookback=5)
        
        if distance_type == 'high' and swings['swing_highs']:
            swing_price = swings['swing_highs'][-1][1]
        elif distance_type == 'low' and swings['swing_lows']:
            swing_price = swings['swing_lows'][-1][1]
        else:
            return 0.0
        
        distance = (current_price - swing_price) / atr
        
        return distance
