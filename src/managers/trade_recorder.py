"""
交易記錄器
職責：記錄交易數據、收集 ML 特徵、智能 Flush 機制
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
import logging

from src.config import Config
from src.ml.feature_engine import FeatureEngine

logger = logging.getLogger(__name__)


class TradeRecorder:
    """交易記錄器"""
    
    def __init__(self, model_scorer=None):
        """
        初始化交易記錄器
        
        Args:
            model_scorer: ModelScorer实例（可选）
        """
        self.config = Config
        self.trades_file = self.config.TRADES_FILE
        self.ml_pending_file = self.config.ML_PENDING_FILE
        self.model_scorer = model_scorer
        
        self.pending_entries: List[Dict] = []
        self.completed_trades: List[Dict] = []
        
        # 🔥 v3.17.10+：特徵工程引擎（競價上下文特徵）
        self.feature_engine = FeatureEngine()
        logger.info("✅ 特徵工程引擎已啟用（v3.17.10+）")
        
        self._load_data()
    
    def record_entry(self, signal: Dict, position_info: Dict, competition_context: Optional[Dict] = None):
        """
        記錄開倉信號（待配對）
        
        Args:
            signal: 交易信號
            position_info: 倉位信息
            competition_context: 競價上下文（v3.17.10+）包含 rank, score_gap, num_signals
        """
        entry_data = {
            'entry_id': f"{signal['symbol']}_{datetime.now().timestamp()}",
            'symbol': signal['symbol'],
            'direction': signal['direction'],
            'entry_price': signal['entry_price'],
            'entry_timestamp': signal['timestamp'].isoformat(),
            'confidence': signal['confidence'],
            'leverage': position_info['leverage'],
            'position_value': position_info['position_value'],
            'timeframes': signal.get('timeframes', {}),
            'market_structure': signal.get('market_structure'),
            'order_blocks': signal.get('order_blocks', 0),
            'liquidity_zones': signal.get('liquidity_zones', 0),
            'indicators': signal.get('indicators', {}),
        }
        
        # 🔥 v3.17.10+：添加競價上下文特徵（3個新特徵）
        if competition_context:
            entry_data['competition_rank'] = competition_context.get('rank', 1)
            entry_data['score_gap_to_best'] = competition_context.get('score_gap', 0.0)
            entry_data['num_competing_signals'] = competition_context.get('num_signals', 1)
        else:
            # 默認值（向後兼容）
            entry_data['competition_rank'] = 1
            entry_data['score_gap_to_best'] = 0.0
            entry_data['num_competing_signals'] = 1
        
        self.pending_entries.append(entry_data)
        
        self._check_and_flush()
    
    def record_exit(self, trade_result: Dict, current_winrate: Optional[float] = None) -> Optional[Dict]:
        """
        記錄平倉並配對開倉數據
        
        Args:
            trade_result: 交易結果
            current_winrate: 平仓时的当前胜率（0-100），可选
        
        Returns:
            Optional[Dict]: 完整的 ML 數據記錄
        """
        symbol = trade_result['symbol']
        
        entry_data = None
        for i, entry in enumerate(self.pending_entries):
            if entry['symbol'] == symbol:
                entry_data = self.pending_entries.pop(i)
                break
        
        if not entry_data:
            logger.warning(f"未找到 {symbol} 的開倉記錄")
            return None
        
        ml_record = self._create_ml_record(entry_data, trade_result)
        
        self.completed_trades.append(ml_record)
        
        logger.info(f"📝 記錄交易: {symbol} PnL: {ml_record['pnl']:+.2%}")
        
        # 🎯 v3.9.2.8.5: 模型评分系统
        if self.model_scorer:
            try:
                self.model_scorer.score_trade(
                    pnl_pct=ml_record['pnl'] * 100,  # 转换为百分比
                    confidence=entry_data['confidence'],
                    winrate=current_winrate,
                    symbol=symbol,
                    direction=entry_data['direction'],
                    entry_price=entry_data['entry_price'],
                    exit_price=ml_record['exit_price']
                )
            except Exception as e:
                logger.error(f"模型评分失败: {e}")
        
        self._check_and_flush()
        
        return ml_record
    
    def _create_ml_record(self, entry: Dict, exit_data: Dict) -> Dict:
        """
        創建完整的 ML 訓練記錄（41 個特徵）
        
        v3.17.10+：新增3個競價上下文特徵
        - competition_rank: 信號排名（1=最優）
        - score_gap_to_best: 與最優信號的評分差距
        - num_competing_signals: 當時競爭的信號數量
        
        Args:
            entry: 開倉數據
            exit_data: 平倉數據
        
        Returns:
            Dict: ML 記錄
        """
        pnl = exit_data.get('pnl', 0)
        pnl_pct = exit_data.get('pnl_pct', 0)
        
        entry_time = datetime.fromisoformat(entry['entry_timestamp'])
        exit_time = exit_data.get('close_timestamp', datetime.now())
        
        if isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time)
        
        hold_duration = (exit_time - entry_time).total_seconds() / 3600
        
        indicators = entry.get('indicators', {})
        
        ml_record = {
            'symbol': entry['symbol'],
            'direction': entry['direction'],
            'entry_price': entry['entry_price'],
            'exit_price': exit_data.get('exit_price', 0),
            'entry_timestamp': entry['entry_timestamp'],
            'exit_timestamp': exit_time.isoformat(),
            'hold_duration_hours': hold_duration,
            'confidence_score': entry['confidence'],
            'leverage': entry['leverage'],
            'position_value': entry['position_value'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'is_winner': pnl > 0,
            'close_reason': exit_data.get('close_reason', 'unknown'),
            'trend_1h': entry['timeframes'].get('1h', 'neutral'),
            'trend_15m': entry['timeframes'].get('15m', 'neutral'),
            'trend_5m': entry['timeframes'].get('5m', 'neutral'),
            'market_structure': entry.get('market_structure', 'neutral'),
            'order_blocks_count': entry.get('order_blocks', 0),
            'liquidity_zones_count': entry.get('liquidity_zones', 0),
            'stop_loss': exit_data.get('stop_loss', 0),
            'take_profit': exit_data.get('take_profit', 0),
            'risk_reward_ratio': self._calculate_rr_ratio(
                entry['entry_price'],
                exit_data.get('stop_loss', 0),
                exit_data.get('take_profit', 0)
            ),
            'max_favorable_excursion': 0,
            'max_adverse_excursion': 0,
            'trade_id': entry.get('entry_id'),
            'recorded_at': datetime.now().isoformat(),
            'rsi_entry': indicators.get('rsi', 0),
            'macd_entry': indicators.get('macd', 0),
            'macd_signal_entry': indicators.get('macd_signal', 0),
            'macd_histogram_entry': indicators.get('macd_histogram', 0),
            'atr_entry': indicators.get('atr', 0),
            'bb_upper_entry': indicators.get('bb_upper', 0),
            'bb_middle_entry': indicators.get('bb_middle', 0),
            'bb_lower_entry': indicators.get('bb_lower', 0),
            'bb_width_pct': indicators.get('bb_width_pct', 0),
            'volume_sma_ratio': indicators.get('volume_sma_ratio', 0),
            'price_vs_ema50': indicators.get('price_vs_ema50', 0),
            'price_vs_ema200': indicators.get('price_vs_ema200', 0),
            # 🔥 v3.17.10+：競價上下文特徵（3個新特徵）
            'competition_rank': entry.get('competition_rank', 1),
            'score_gap_to_best': entry.get('score_gap_to_best', 0.0),
            'num_competing_signals': entry.get('num_competing_signals', 1)
        }
        
        return ml_record
    
    def _calculate_rr_ratio(
        self,
        entry: float,
        stop_loss: float,
        take_profit: float
    ) -> float:
        """計算風險回報比"""
        if entry == 0 or stop_loss == 0 or take_profit == 0:
            return 0.0
        
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        
        return reward / risk if risk > 0 else 0.0
    
    def _check_and_flush(self):
        """檢查並執行智能 Flush"""
        if len(self.completed_trades) >= self.config.ML_FLUSH_COUNT:
            self._flush_to_disk()
    
    def _flush_to_disk(self):
        """將數據寫入磁盤"""
        try:
            os.makedirs(os.path.dirname(self.trades_file), exist_ok=True)
            
            with open(self.trades_file, 'a', encoding='utf-8') as f:
                for trade in self.completed_trades:
                    f.write(json.dumps(trade, ensure_ascii=False) + '\n')
            
            logger.info(f"💾 保存 {len(self.completed_trades)} 條交易記錄到磁盤")
            
            self.completed_trades = []
            
            with open(self.ml_pending_file, 'w', encoding='utf-8') as f:
                json.dump(self.pending_entries, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"保存交易記錄失敗: {e}")
    
    def _load_data(self):
        """從文件加載數據"""
        if os.path.exists(self.ml_pending_file):
            try:
                with open(self.ml_pending_file, 'r', encoding='utf-8') as f:
                    self.pending_entries = json.load(f)
                logger.info(f"加載 {len(self.pending_entries)} 條待配對記錄")
            except Exception as e:
                logger.error(f"加載待配對記錄失敗: {e}")
                self.pending_entries = []
    
    def get_statistics(self) -> Dict:
        """獲取記錄統計"""
        all_trades = []
        
        if os.path.exists(self.trades_file):
            try:
                with open(self.trades_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            all_trades.append(json.loads(line))
            except Exception as e:
                logger.error(f"讀取交易記錄失敗: {e}")
        
        all_trades.extend(self.completed_trades)
        
        if not all_trades:
            return {
                'total_trades': 0,
                'pending_entries': len(self.pending_entries),
                'in_memory': len(self.completed_trades)
            }
        
        winning_trades = sum(1 for t in all_trades if t.get('is_winner', False))
        
        return {
            'total_trades': len(all_trades),
            'winning_trades': winning_trades,
            'losing_trades': len(all_trades) - winning_trades,
            'win_rate': winning_trades / len(all_trades) if all_trades else 0.0,
            'pending_entries': len(self.pending_entries),
            'in_memory': len(self.completed_trades)
        }
    
    def get_all_completed_trades(self) -> List[Dict]:
        """
        獲取所有完成的交易記錄（內存+磁盤）
        
        Returns:
            List[Dict]: 所有完成的交易記錄
        """
        all_trades = []
        
        # 從文件讀取
        if os.path.exists(self.trades_file):
            try:
                with open(self.trades_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            all_trades.append(json.loads(line))
            except Exception as e:
                logger.error(f"讀取交易記錄失敗: {e}")
        
        # 添加內存中的記錄
        all_trades.extend(self.completed_trades)
        
        return all_trades
    
    def get_trades(self, days: Optional[int] = None) -> List[Dict]:
        """
        獲取所有交易記錄（包括開倉pending和已平倉）
        
        Args:
            days: 可選，過濾最近N天的交易（默認None=所有交易）
        
        Returns:
            List[Dict]: 所有交易記錄，每條記錄包含 status 字段
        """
        all_trades = []
        
        # 🔥 步驟1：添加待配對的開倉記錄（status='open'）
        for entry in self.pending_entries:
            trade_record = entry.copy()
            trade_record['status'] = 'open'  # 標記為未平倉
            all_trades.append(trade_record)
        
        # 🔥 步驟2：添加已完成的交易記錄（status='closed'）
        completed = self.get_all_completed_trades()
        for trade in completed:
            if 'status' not in trade:
                trade['status'] = 'closed'  # 確保有status字段
            all_trades.append(trade)
        
        # 🔥 步驟3：如果指定了days參數，過濾最近N天的交易
        if days is not None:
            from datetime import datetime, timedelta
            cutoff_time = datetime.now() - timedelta(days=days)
            
            filtered_trades = []
            for trade in all_trades:
                # 檢查entry_timestamp或recorded_at字段
                timestamp_str = trade.get('entry_timestamp') or trade.get('recorded_at')
                if timestamp_str:
                    try:
                        trade_time = datetime.fromisoformat(timestamp_str)
                        if trade_time >= cutoff_time:
                            filtered_trades.append(trade)
                    except:
                        # 如果時間戳格式有問題，保留這條記錄
                        filtered_trades.append(trade)
                else:
                    # 沒有時間戳的記錄也保留
                    filtered_trades.append(trade)
            
            return filtered_trades
        
        return all_trades
    
    def force_flush(self):
        """強制保存所有數據"""
        if self.completed_trades:
            self._flush_to_disk()
            logger.info("強制保存完成")
    
    async def save_competition_log(self, competition_log: Dict):
        """
        保存多信號競價記錄（用於模型改進和審計）
        
        Args:
            competition_log: 競價記錄數據
        """
        try:
            # 構建競價記錄文件路徑
            competition_file = os.path.join(
                os.path.dirname(self.trades_file),
                'signal_competitions.jsonl'
            )
            
            # 確保目錄存在
            os.makedirs(os.path.dirname(competition_file), exist_ok=True)
            
            # 追加寫入競價記錄
            with open(competition_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(competition_log, ensure_ascii=False) + '\n')
            
            logger.debug(
                f"💾 保存競價記錄: {competition_log['total_signals']} 個信號, "
                f"選中 {competition_log['best_signal']['symbol']}"
            )
            
        except Exception as e:
            logger.error(f"❌ 保存競價記錄失敗: {e}")
