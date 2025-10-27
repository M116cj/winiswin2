"""
XGBoost 数据归档系统
记录所有交易信号特征、实际仓位和虚拟仓位数据供机器学习训练使用
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import pandas as pd
from threading import Lock

logger = logging.getLogger(__name__)


class DataArchiver:
    """
    数据归档管理器
    
    功能：
    1. 记录所有信号特征（包括被拒绝的信号）
    2. 记录实际仓位的完整生命周期
    3. 记录虚拟仓位的完整生命周期
    4. 支持增量写入和批量刷新
    5. 提供 CSV 和 Parquet 两种格式
    """
    
    def __init__(self, data_dir: str = "ml_data"):
        """
        初始化数据归档器
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.signals_buffer: List[Dict] = []
        self.positions_buffer: List[Dict] = []
        self.adjustments_buffer: List[Dict] = []  # 新增：止损止盈调整记录
        self.lock = Lock()
        
        # 内存优化：减少缓冲区大小从100到50
        self.buffer_size = 50
        
        logger.info(f"数据归档器已初始化，数据目录: {self.data_dir}")
    
    def archive_signal(
        self,
        signal_data: Dict,
        accepted: bool,
        rejection_reason: Optional[str] = None
    ):
        """
        归档交易信号
        
        Args:
            signal_data: 信号数据字典，包含：
                - symbol: 交易对
                - direction: 方向
                - confidence: 信心度
                - scores: 五大子指标评分
                - indicators: 技术指标
                - timestamp: 时间戳
            accepted: 是否被接受
            rejection_reason: 拒绝原因
        """
        with self.lock:
            record = {
                'timestamp': signal_data.get('timestamp', datetime.now().isoformat()),
                'symbol': signal_data.get('symbol'),
                'direction': signal_data.get('direction'),
                'confidence': signal_data.get('confidence'),
                'accepted': accepted,
                'rejection_reason': rejection_reason,
                
                'trend_alignment_score': signal_data.get('scores', {}).get('trend_alignment', 0),
                'market_structure_score': signal_data.get('scores', {}).get('market_structure', 0),
                'price_position_score': signal_data.get('scores', {}).get('price_position', 0),
                'momentum_score': signal_data.get('scores', {}).get('momentum', 0),
                'volatility_score': signal_data.get('scores', {}).get('volatility', 0),
                
                'h1_trend': signal_data.get('trends', {}).get('h1', 'neutral'),
                'm15_trend': signal_data.get('trends', {}).get('m15', 'neutral'),
                'm5_trend': signal_data.get('trends', {}).get('m5', 'neutral'),
                
                'current_price': signal_data.get('current_price'),
                'entry_price': signal_data.get('entry_price'),
                'stop_loss': signal_data.get('stop_loss'),
                'take_profit': signal_data.get('take_profit'),
                
                'rsi': signal_data.get('indicators', {}).get('rsi'),
                'macd': signal_data.get('indicators', {}).get('macd'),
                'macd_signal': signal_data.get('indicators', {}).get('macd_signal'),
                'atr': signal_data.get('indicators', {}).get('atr'),
                'bb_width_pct': signal_data.get('indicators', {}).get('bb_width_pct'),
                
                'order_blocks_count': len(signal_data.get('order_blocks', [])),
                'liquidity_zones_count': len(signal_data.get('liquidity_zones', [])),
            }
            
            self.signals_buffer.append(record)
            
            if len(self.signals_buffer) >= self.buffer_size:
                self._flush_signals()
    
    def archive_position_open(
        self,
        position_data: Dict,
        is_virtual: bool = False
    ):
        """
        归档开仓事件
        
        Args:
            position_data: 仓位数据
            is_virtual: 是否为虚拟仓位
        """
        with self.lock:
            record = {
                'event': 'open',
                'timestamp': position_data.get('timestamp', datetime.now().isoformat()),
                'position_id': position_data.get('id'),
                'is_virtual': is_virtual,
                'symbol': position_data.get('symbol'),
                'direction': position_data.get('direction'),
                'entry_price': position_data.get('entry_price'),
                'stop_loss': position_data.get('stop_loss'),
                'take_profit': position_data.get('take_profit'),
                'quantity': position_data.get('quantity'),
                'leverage': position_data.get('leverage'),
                'confidence': position_data.get('confidence'),
                
                'trend_alignment_score': position_data.get('scores', {}).get('trend_alignment'),
                'market_structure_score': position_data.get('scores', {}).get('market_structure'),
                'price_position_score': position_data.get('scores', {}).get('price_position'),
                'momentum_score': position_data.get('scores', {}).get('momentum'),
                'volatility_score': position_data.get('scores', {}).get('volatility'),
                
                'rsi': position_data.get('indicators', {}).get('rsi'),
                'macd': position_data.get('indicators', {}).get('macd'),
                'atr': position_data.get('indicators', {}).get('atr'),
                'bb_width_pct': position_data.get('indicators', {}).get('bb_width_pct'),
            }
            
            self.positions_buffer.append(record)
            
            if len(self.positions_buffer) >= self.buffer_size:
                self._flush_positions()
    
    def archive_position_close(
        self,
        position_data: Dict,
        close_data: Dict,
        is_virtual: bool = False
    ):
        """
        归档平仓事件
        
        Args:
            position_data: 仓位数据
            close_data: 平仓数据（包含 pnl, close_price, close_reason）
            is_virtual: 是否为虚拟仓位
        """
        with self.lock:
            record = {
                'event': 'close',
                'timestamp': close_data.get('timestamp', datetime.now().isoformat()),
                'position_id': position_data.get('id'),
                'is_virtual': is_virtual,
                'symbol': position_data.get('symbol'),
                'direction': position_data.get('direction'),
                'entry_price': position_data.get('entry_price'),
                'exit_price': close_data.get('close_price'),
                'stop_loss': position_data.get('stop_loss'),
                'take_profit': position_data.get('take_profit'),
                'quantity': position_data.get('quantity'),
                'leverage': position_data.get('leverage'),
                'confidence': position_data.get('confidence'),
                
                'pnl': close_data.get('pnl'),
                'pnl_pct': close_data.get('pnl_pct'),
                'close_reason': close_data.get('close_reason'),
                'won': close_data.get('pnl', 0) > 0,
                
                'trend_alignment_score': position_data.get('scores', {}).get('trend_alignment'),
                'market_structure_score': position_data.get('scores', {}).get('market_structure'),
                'price_position_score': position_data.get('scores', {}).get('price_position'),
                'momentum_score': position_data.get('scores', {}).get('momentum'),
                'volatility_score': position_data.get('scores', {}).get('volatility'),
                
                'holding_duration_minutes': (
                    (datetime.fromisoformat(close_data.get('timestamp', datetime.now().isoformat())) -
                     datetime.fromisoformat(position_data.get('timestamp', datetime.now().isoformat()))).total_seconds() / 60
                    if 'timestamp' in position_data and 'timestamp' in close_data else None
                ),
            }
            
            self.positions_buffer.append(record)
            
            if len(self.positions_buffer) >= self.buffer_size:
                self._flush_positions()
    
    def archive_adjustment(
        self,
        adjustment_data: Dict
    ):
        """
        归档止损止盈调整记录（用于XGBoost特征学习）
        
        Args:
            adjustment_data: 调整数据字典，包含：
                - timestamp: 调整时间
                - symbol: 交易对
                - direction: 方向
                - current_pnl_pct: 当前盈亏
                - max_profit_pct: 最大盈利
                - new_stop_loss: 新止损价
                - new_take_profit: 新止盈价
                - trailing_stop_active: 追踪止损是否激活
                - adjustment_count: 调整次数
        """
        with self.lock:
            self.adjustments_buffer.append(adjustment_data)
            
            if len(self.adjustments_buffer) >= self.buffer_size:
                self._flush_adjustments()
    
    def _flush_signals(self):
        """刷新信号缓冲区到磁盘"""
        if not self.signals_buffer:
            return
        
        try:
            df = pd.DataFrame(self.signals_buffer)
            
            signals_file = self.data_dir / 'signals.csv'
            
            if signals_file.exists():
                df.to_csv(signals_file, mode='a', header=False, index=False)
            else:
                df.to_csv(signals_file, index=False)
            
            logger.info(f"已归档 {len(self.signals_buffer)} 条信号记录到 {signals_file}")
            
            self.signals_buffer.clear()
            
        except Exception as e:
            logger.error(f"刷新信号缓冲区失败: {e}", exc_info=True)
    
    def _flush_positions(self):
        """刷新仓位缓冲区到磁盘"""
        if not self.positions_buffer:
            return
        
        try:
            df = pd.DataFrame(self.positions_buffer)
            
            positions_file = self.data_dir / 'positions.csv'
            
            if positions_file.exists():
                df.to_csv(positions_file, mode='a', header=False, index=False)
            else:
                df.to_csv(positions_file, index=False)
            
            logger.info(f"已归档 {len(self.positions_buffer)} 条仓位记录到 {positions_file}")
            
            self.positions_buffer.clear()
            
        except Exception as e:
            logger.error(f"刷新仓位缓冲区失败: {e}", exc_info=True)
    
    def _flush_adjustments(self):
        """刷新止损止盈调整缓冲区到磁盘"""
        if not self.adjustments_buffer:
            return
        
        try:
            df = pd.DataFrame(self.adjustments_buffer)
            
            adjustments_file = self.data_dir / 'adjustments.csv'
            
            if adjustments_file.exists():
                df.to_csv(adjustments_file, mode='a', header=False, index=False)
            else:
                df.to_csv(adjustments_file, index=False)
            
            logger.info(f"已归档 {len(self.adjustments_buffer)} 条调整记录到 {adjustments_file}")
            
            self.adjustments_buffer.clear()
            
        except Exception as e:
            logger.error(f"刷新调整缓冲区失败: {e}", exc_info=True)
    
    def flush_all(self):
        """强制刷新所有缓冲区"""
        with self.lock:
            self._flush_signals()
            self._flush_positions()
            self._flush_adjustments()
            logger.info("所有缓冲区已刷新")
    
    def get_training_data(
        self,
        min_samples: int = 100,
        include_rejected: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        获取用于 XGBoost 训练的数据集
        
        Args:
            min_samples: 最小样本数
            include_rejected: 是否包含被拒绝的信号
        
        Returns:
            DataFrame 或 None（如果数据不足）
        """
        try:
            signals_file = self.data_dir / 'signals.csv'
            positions_file = self.data_dir / 'positions.csv'
            
            if not signals_file.exists() or not positions_file.exists():
                logger.warning("数据文件不存在，无法生成训练数据")
                return None
            
            signals_df = pd.read_csv(signals_file)
            positions_df = pd.read_csv(positions_file)
            
            closed_positions = positions_df[positions_df['event'] == 'close'].copy()
            
            if len(closed_positions) < min_samples:
                logger.warning(f"训练数据不足: {len(closed_positions)} < {min_samples}")
                return None
            
            if not include_rejected:
                signals_df = signals_df[signals_df['accepted'] == True]
            
            training_data = pd.merge(
                signals_df,
                closed_positions,
                on=['symbol', 'direction'],
                how='inner',
                suffixes=('_signal', '_close')
            )
            
            logger.info(f"生成训练数据集: {len(training_data)} 条记录")
            
            return training_data
            
        except Exception as e:
            logger.error(f"获取训练数据失败: {e}", exc_info=True)
            return None
    
    def get_statistics(self) -> Dict:
        """获取归档统计信息"""
        try:
            stats = {
                'signals_buffered': len(self.signals_buffer),
                'positions_buffered': len(self.positions_buffer),
                'signals_total': 0,
                'positions_total': 0,
            }
            
            signals_file = self.data_dir / 'signals.csv'
            if signals_file.exists():
                stats['signals_total'] = len(pd.read_csv(signals_file))
            
            positions_file = self.data_dir / 'positions.csv'
            if positions_file.exists():
                stats['positions_total'] = len(pd.read_csv(positions_file))
            
            return stats
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}", exc_info=True)
            return {}
