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
        
        # 🔥 v3.18+：信心值/勝率歷史記錄（用於檢測變化）
        # 格式: {position_key: [(timestamp, confidence, win_probability), ...]}
        self.position_metrics_history: Dict[str, List[tuple]] = {}
        self.history_retention_seconds = 600  # 保留10分鐘歷史（5分鐘比較+5分鐘緩衝）
        logger.info("✅ 倉位指標歷史追蹤已啟用（v3.18+，用於強制止盈檢測）")
        
        self._load_data()
    
    def record_entry(
        self, 
        signal: Dict, 
        position_info: Dict, 
        competition_context: Optional[Dict] = None,
        websocket_metadata: Optional[Dict] = None
    ):
        """
        記錄開倉信號（待配對）
        
        Args:
            signal: 交易信號
            position_info: 倉位信息
            competition_context: 競價上下文（v3.17.10+）包含 rank, score_gap, num_signals
            websocket_metadata: WebSocket元數據（v3.17.2+）包含 latency_ms, server_timestamp, local_timestamp, shard_id
        """
        # 🔥 v3.18.4+ Critical Fix: 創建可JSON序列化的signal副本（移除datetime對象）
        signal_copy = {}
        for key, value in signal.items():
            if isinstance(value, datetime):
                signal_copy[key] = value.isoformat()
            elif isinstance(value, dict) or isinstance(value, list) or isinstance(value, (int, float, str, bool, type(None))):
                signal_copy[key] = value
            else:
                # 跳過不可序列化的對象
                logger.debug(f"跳過不可序列化字段: {key} ({type(value)})")
        
        entry_data = {
            'entry_id': f"{signal['symbol']}_{datetime.now().timestamp()}",
            'symbol': signal['symbol'],
            'direction': signal['direction'],
            'entry_price': signal['entry_price'],
            'entry_timestamp': signal['timestamp'].isoformat(),
            'confidence': signal['confidence'],
            'win_probability': signal.get('win_probability', 0.5),  # 🔥 v3.18.4+ Critical: 保存勝率
            'leverage': position_info['leverage'],
            'position_value': position_info['position_value'],
            'timeframes': signal.get('timeframes', {}),
            'market_structure': signal.get('market_structure'),
            'order_blocks': signal.get('order_blocks', 0),
            'liquidity_zones': signal.get('liquidity_zones', 0),
            'indicators': signal.get('indicators', {}),
            # 🔥 v3.18.4+ Critical Fix: 存儲可序列化的original_signal用於PositionMonitor即時評估
            'original_signal': signal.get('original_signal', signal_copy),  # fallback到可序列化副本
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
        
        # 🔥 v3.17.2+：添加WebSocket元數據（4個新字段）
        if websocket_metadata:
            entry_data['latency_ms'] = websocket_metadata.get('latency_ms', 0)
            entry_data['server_timestamp'] = websocket_metadata.get('server_timestamp', 0)
            entry_data['local_timestamp'] = websocket_metadata.get('local_timestamp', 0)
            entry_data['websocket_shard_id'] = websocket_metadata.get('shard_id', 0)
        else:
            # 默認值（向後兼容）
            entry_data['latency_ms'] = 0
            entry_data['server_timestamp'] = int(datetime.now().timestamp() * 1000)
            entry_data['local_timestamp'] = int(datetime.now().timestamp() * 1000)
            entry_data['websocket_shard_id'] = 0
        
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
            # 🔥 v3.18+: 舊倉位補救機制 - 從trade_result重建開倉記錄
            logger.warning(f"⚠️ {symbol} 未找到開倉記錄（可能是舊倉位），使用補救機制重建")
            entry_data = self._rebuild_entry_from_position(trade_result)
            if not entry_data:
                logger.error(f"❌ {symbol} 補救失敗：無法重建開倉記錄")
                return None
        
        ml_record = self._create_ml_record(entry_data, trade_result)
        
        # 🔥 v3.17.2+：數據品質過濾（僅保存高品質樣本）
        if not self._is_high_quality_sample(ml_record):
            logger.debug(f"⚠️ 低品質樣本已過濾: {symbol} (延遲/時間戳/流動性異常)")
            # 不保存到completed_trades，但仍返回給調用者（用於模型評分）
            return ml_record
        
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
        創建完整的 ML 訓練記錄（使用FeatureEngine）
        
        v3.17.10+：新增3個競價上下文特徵
        v3.17.2+：新增3個WebSocket專屬特徵（通過FeatureEngine計算）
        
        Args:
            entry: 開倉數據
            exit_data: 平倉數據
        
        Returns:
            Dict: 完整的ML記錄（兼容舊格式+新特徵）
        """
        pnl = exit_data.get('pnl', 0)
        pnl_pct = exit_data.get('pnl_pct', 0)
        
        entry_time = datetime.fromisoformat(entry['entry_timestamp'])
        exit_time = exit_data.get('close_timestamp', datetime.now())
        
        if isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time)
        
        hold_duration = (exit_time - entry_time).total_seconds()
        
        # 構建信號數據（用於FeatureEngine）
        signal_data = {
            'symbol': entry['symbol'],
            'direction': entry['direction'],
            'entry_price': entry['entry_price'],
            'confidence': entry['confidence'],
            'leverage': entry['leverage'],
            'position_value': entry['position_value'],
            'order_blocks': entry.get('order_blocks', 0),
            'liquidity_zones': entry.get('liquidity_zones', 0),
            'indicators': entry.get('indicators', {}),
            'timeframes': entry.get('timeframes', {}),
            'market_structure': entry.get('market_structure', 'neutral'),
            'rr_ratio': self._calculate_rr_ratio(
                entry['entry_price'],
                exit_data.get('stop_loss', 0),
                exit_data.get('take_profit', 0)
            ),
            'win_probability': entry.get('win_probability', 0.5)
        }
        
        # 競價上下文
        competition_context = {
            'rank': entry.get('competition_rank', 1),
            'my_score': entry.get('confidence', 0.5),
            'best_score': entry.get('confidence', 0.5),
            'total_signals': entry.get('num_competing_signals', 1)
        }
        
        # WebSocket元數據
        websocket_metadata = {
            'latency_ms': entry.get('latency_ms', 0),
            'server_timestamp': entry.get('server_timestamp', 0),
            'local_timestamp': entry.get('local_timestamp', 0),
            'shard_id': entry.get('websocket_shard_id', 0)
        }
        
        # 🔥 v3.17.2+：使用FeatureEngine構建完整特徵（包含WebSocket專屬特徵）
        try:
            enhanced_features = self.feature_engine.build_enhanced_features(
                signal=signal_data,
                competition_context=competition_context,
                websocket_metadata=websocket_metadata
            )
        except Exception as e:
            logger.error(f"構建增強特徵失敗: {e}，使用默認特徵")
            enhanced_features = {'confidence': signal_data['confidence']}
        
        # 🔥 協調schema：先展開features，然後用關鍵metadata覆蓋重複字段
        ml_record = {
            # Step 1: 展開所有特徵（44個）
            **enhanced_features,
            
            # Step 2: 覆蓋關鍵metadata（確保不被feature覆蓋）
            'symbol': entry['symbol'],
            'direction': entry['direction'],
            'entry_price': entry['entry_price'],
            'exit_price': exit_data.get('exit_price', 0),
            'entry_timestamp': entry['entry_timestamp'],
            'exit_timestamp': exit_time.isoformat(),
            'hold_duration_hours': hold_duration / 3600,
            'hold_duration_sec': hold_duration,
            'confidence_score': entry['confidence'],  # 保留原始信心度
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'is_winner': pnl > 0,
            'close_reason': exit_data.get('close_reason', 'unknown'),
            'trade_id': entry.get('entry_id'),
            'recorded_at': datetime.now().isoformat(),
            'label': 1 if pnl > 0 else 0,
            
            # 保留WebSocket原始元數據（用於品質過濾）
            'latency_ms': entry.get('latency_ms', 0),
            'server_timestamp': entry.get('server_timestamp', 0),
            'local_timestamp': entry.get('local_timestamp', 0),
            'websocket_shard_id': entry.get('websocket_shard_id', 0)
        }
        
        return ml_record
    
    def _rebuild_entry_from_position(self, trade_result: Dict) -> Optional[Dict]:
        """
        🔥 v3.18+ 舊倉位補救機制：從平倉數據重建開倉記錄
        
        當倉位缺少開倉記錄時（舊倉位），從trade_result中提取信息重建最小化開倉記錄。
        這確保即使是舊倉位，平倉後也能記錄特徵供模型學習。
        
        Args:
            trade_result: 平倉交易結果
            
        Returns:
            重建的開倉記錄，或None（如果關鍵信息缺失）
        """
        try:
            # 提取關鍵字段
            symbol = trade_result.get('symbol')
            direction = trade_result.get('direction')
            entry_price = trade_result.get('entry_price')
            
            if not all([symbol, direction, entry_price]):
                logger.error(f"❌ 補救失敗：缺少關鍵字段 symbol={symbol}, direction={direction}, entry_price={entry_price}")
                return None
            
            # 從trade_result推斷entry_timestamp
            entry_timestamp = trade_result.get('entry_timestamp')
            if not entry_timestamp:
                # 如果沒有entry_timestamp，使用close_timestamp往前推holding_duration
                close_time = trade_result.get('timestamp') or trade_result.get('close_timestamp')
                holding_minutes = trade_result.get('holding_duration_minutes', 0)
                if close_time and holding_minutes:
                    from datetime import timedelta
                    if isinstance(close_time, str):
                        close_time = datetime.fromisoformat(close_time)
                    entry_time = close_time - timedelta(minutes=holding_minutes)
                    entry_timestamp = entry_time.isoformat()
                else:
                    # 最後fallback：使用未知時間戳
                    entry_timestamp = datetime.now().isoformat()
                    logger.warning(f"⚠️ {symbol} 無法推斷entry_timestamp，使用當前時間")
            
            # 計算倉位價值（安全處理pnl_pct=0的情況）
            pnl = trade_result.get('pnl', 0)
            pnl_pct = trade_result.get('pnl_pct', 0)
            
            # 優先從trade_result獲取notional或position_value
            position_value = trade_result.get('position_value') or trade_result.get('notional')
            
            if not position_value:
                # 從pnl和pnl_pct反推（避免除以零）
                if abs(pnl_pct) > 0.0001:  # epsilon保護
                    position_value = abs(pnl) / abs(pnl_pct)
                else:
                    # pnl_pct≈0時，使用默認最小值
                    position_value = 10.0  # 最小倉位價值10 USDT
                    logger.warning(f"⚠️ {symbol} pnl_pct≈0，無法反推倉位價值，使用默認值${position_value}")
            
            # 重建開倉記錄（使用trade_result中可用的數據或默認值）
            entry_data = {
                'entry_id': f"REBUILT_{symbol}_{datetime.now().timestamp()}",
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'entry_timestamp': entry_timestamp if isinstance(entry_timestamp, str) else entry_timestamp.isoformat(),
                'confidence': trade_result.get('confidence', 0.5),  # 默認50%
                'leverage': trade_result.get('leverage', 1),
                'position_value': position_value,
                'timeframes': {},  # 舊倉位無多時框數據
                'market_structure': trade_result.get('market_structure', 'neutral'),
                'order_blocks': trade_result.get('order_blocks_count', 0),
                'liquidity_zones': trade_result.get('liquidity_zones_count', 0),
                'indicators': {
                    'rsi': trade_result.get('rsi', 50),
                    'macd': trade_result.get('macd', 0),
                    'atr': trade_result.get('atr', 0),
                    'bb_width_pct': trade_result.get('bb_width_pct', 0)
                },
                # 原始信號留空（舊倉位無此數據）
                'original_signal': None,
                # 競價上下文默認值
                'competition_rank': 1,
                'score_gap_to_best': 0.0,
                'num_competing_signals': 1,
                # WebSocket元數據默認值
                'latency_ms': 0,
                'server_timestamp': int(datetime.now().timestamp() * 1000),
                'local_timestamp': int(datetime.now().timestamp() * 1000),
                'websocket_shard_id': 0
            }
            
            logger.info(
                f"✅ {symbol} 開倉記錄重建成功 | "
                f"入場: ${entry_price:.2f} @ {entry_timestamp} | "
                f"方向: {direction} | 信心: {entry_data['confidence']:.1%}"
            )
            
            return entry_data
            
        except Exception as e:
            logger.error(f"❌ 重建開倉記錄失敗: {e}")
            return None
    
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
        """
        檢查並執行智能 Flush
        
        🔥 v3.18.4-Critical: 立即保存pending_entries到磁盤
        - 確保每次開倉/平倉後都寫入磁盤
        - 防止系統重啟時丟失original_signal
        """
        # 總是保存pending_entries（開倉記錄）到磁盤
        should_flush = (
            len(self.completed_trades) >= self.config.ML_FLUSH_COUNT or  # 有平倉交易
            len(self.pending_entries) > 0  # 🔥 Critical: 或有待配對的開倉記錄
        )
        
        if should_flush:
            self._flush_to_disk()
    
    def _flush_to_disk(self):
        """將數據寫入磁盤"""
        try:
            os.makedirs(os.path.dirname(self.trades_file), exist_ok=True)
            
            with open(self.trades_file, 'a', encoding='utf-8') as f:
                for trade in self.completed_trades:
                    f.write(json.dumps(trade, ensure_ascii=False, default=str) + '\n')
            
            logger.info(f"💾 保存 {len(self.completed_trades)} 條交易記錄到磁盤")
            
            self.completed_trades = []
            
            # 🔥 v3.18+ Critical Fix: 添加default=str處理original_signal中的datetime對象
            with open(self.ml_pending_file, 'w', encoding='utf-8') as f:
                json.dump(self.pending_entries, f, ensure_ascii=False, indent=2, default=str)
            
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
    
    def get_active_trades(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        🔥 v3.18+：獲取活躍交易記錄（未平倉的pending_entries）
        
        這是PositionMonitor24x7用來獲取original_signal的關鍵方法
        
        Args:
            symbol: 可選，過濾指定交易對（默認None=所有活躍交易）
        
        Returns:
            List[Dict]: 活躍交易記錄列表，每條記錄包含 original_signal, status='open'
        """
        active_trades = []
        
        for entry in self.pending_entries:
            # 如果指定了symbol，只返回該symbol的記錄
            if symbol is None or entry.get('symbol') == symbol:
                trade_record = entry.copy()
                trade_record['status'] = 'open'  # 標記為未平倉
                active_trades.append(trade_record)
        
        return active_trades
    
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
        """
        強制保存所有數據（v3.18.4-hotfix）
        
        即使completed_trades為空，也要保存pending_entries
        這確保系統關閉時不會丟失開倉記錄
        """
        # 總是調用_flush_to_disk，因為pending_entries可能有數據
        self._flush_to_disk()
        logger.info(f"✅ 強制保存完成: {len(self.completed_trades)} 條完成交易, {len(self.pending_entries)} 條待配對")
    
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
                f.write(json.dumps(competition_log, ensure_ascii=False, default=str) + '\n')
            
            logger.debug(
                f"💾 保存競價記錄: {competition_log['total_signals']} 個信號, "
                f"選中 {competition_log['best_signal']['symbol']}"
            )
            
        except Exception as e:
            logger.error(f"❌ 保存競價記錄失敗: {e}")
    
    # ==================== v3.17.2+ 數據品質過濾方法 ====================
    
    def _is_high_quality_sample(self, sample: dict) -> bool:
        """
        過濾低品質訓練數據（v3.17.2+）
        
        僅保留技術性過濾條件：
        1. 網路延遲過高（>500ms）
        2. 時間戳異常（本地 vs 伺服器差異 >10秒）
        3. 動態流動性過濾（交易量過低）
        
        ✅ 移除「非交易時段」過濾（加密貨幣 24/7 交易）
        
        Args:
            sample: ML訓練樣本（扁平格式，向後兼容）
        
        Returns:
            bool: True=高品質樣本，False=低品質樣本
        """
        # 🔥 v3.17.2+：支持扁平格式（向後兼容）
        # 1. 網路延遲過高（>500ms）
        latency_ms = sample.get('latency_ms', 0)
        if latency_ms > 500:
            logger.debug(f"過濾樣本：延遲過高 {latency_ms}ms > 500ms")
            return False
        
        # 2. 時間戳異常（本地 vs 伺服器差異 >10秒）
        server_ts = sample.get('server_timestamp', 0)
        local_ts = sample.get('local_timestamp', 0)
        if server_ts > 0 and local_ts > 0:
            timestamp_diff = abs(local_ts - server_ts)
            if timestamp_diff > 10000:  # 10秒 = 10000毫秒
                logger.debug(f"過濾樣本：時間戳異常 {timestamp_diff}ms > 10000ms")
                return False
        
        # 3. 動態流動性過濾（非固定時段）
        symbol = sample.get('symbol', '')
        volume = sample.get('volume', 0)
        volume_threshold = self._get_volume_threshold(symbol)
        
        if volume < volume_threshold:
            logger.debug(
                f"過濾樣本：{symbol} 交易量過低 {volume} < {volume_threshold}"
            )
            return False
        
        return True
    
    def _get_volume_threshold(self, symbol: str) -> float:
        """
        根據幣種動態計算最低交易量門檻（v3.17.2+）
        
        Args:
            symbol: 交易對符號（例如：BTCUSDT）
        
        Returns:
            float: 最低交易量門檻
        """
        # 主流幣種門檻（基於歷史數據統計）
        thresholds = {
            'BTCUSDT': 100,      # BTC 門檻 = 100 BTC
            'ETHUSDT': 1000,     # ETH 門檻 = 1000 ETH
            'BNBUSDT': 500,      # BNB 門檻 = 500 BNB
            'SOLUSDT': 10000,    # SOL 門檻 = 10000 SOL
            'ADAUSDT': 50000,    # ADA 門檻 = 50000 ADA
            'DOGEUSDT': 100000,  # DOGE 門檻 = 100000 DOGE
            'XRPUSDT': 50000,    # XRP 門檻 = 50000 XRP
            'DOTUSDT': 5000,     # DOT 門檻 = 5000 DOT
            'MATICUSDT': 20000,  # MATIC 門檻 = 20000 MATIC
            'AVAXUSDT': 2000,    # AVAX 門檻 = 2000 AVAX
        }
        
        # 獲取門檻（默認 1000 適用於大多數幣種）
        threshold = thresholds.get(symbol, 1000)
        
        return threshold
    
    # ==================== v3.18+ 倉位指標歷史追蹤方法 ====================
    
    def update_position_metrics(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        win_probability: float
    ):
        """
        更新倉位的信心值/勝率歷史記錄（v3.18+）
        
        用於強制止盈檢測：當信心值或勝率相較5分鐘前降低20%時平倉
        
        Args:
            symbol: 交易對
            direction: 方向（LONG/SHORT）
            confidence: 當前信心值（0-1）
            win_probability: 當前勝率（0-1）
        """
        position_key = f"{symbol}_{direction}"
        current_time = datetime.now().timestamp()
        
        # 初始化或獲取歷史記錄
        if position_key not in self.position_metrics_history:
            self.position_metrics_history[position_key] = []
        
        # 添加當前記錄
        self.position_metrics_history[position_key].append(
            (current_time, confidence, win_probability)
        )
        
        # 清理過期記錄（保留最近10分鐘）
        cutoff_time = current_time - self.history_retention_seconds
        self.position_metrics_history[position_key] = [
            record for record in self.position_metrics_history[position_key]
            if record[0] >= cutoff_time
        ]
    
    def get_metrics_5min_ago(
        self,
        symbol: str,
        direction: str
    ) -> Optional[tuple[float, float]]:
        """
        獲取5分鐘前的信心值和勝率（v3.18+）
        
        Args:
            symbol: 交易對
            direction: 方向（LONG/SHORT）
        
        Returns:
            Optional[tuple]: (confidence_5min_ago, win_probability_5min_ago)
            如果沒有5分鐘前的數據，返回None
        """
        position_key = f"{symbol}_{direction}"
        
        if position_key not in self.position_metrics_history:
            return None
        
        history = self.position_metrics_history[position_key]
        if not history:
            return None
        
        current_time = datetime.now().timestamp()
        target_time = current_time - 300  # 5分鐘前 = 300秒
        
        # 找到最接近5分鐘前的記錄
        closest_record = None
        min_time_diff = float('inf')
        
        for record in history:
            time_diff = abs(record[0] - target_time)
            if time_diff < min_time_diff:
                min_time_diff = time_diff
                closest_record = record
        
        # 如果最接近的記錄距離目標時間超過1分鐘，認為無效
        if closest_record and min_time_diff <= 60:
            return (closest_record[1], closest_record[2])  # (confidence, win_probability)
        
        return None
    
    def check_metrics_drop(
        self,
        symbol: str,
        direction: str,
        current_confidence: float,
        current_win_probability: float,
        drop_threshold: float = 0.20
    ) -> tuple[bool, Optional[str]]:
        """
        檢測信心值/勝率是否相較5分鐘前降低20%（v3.18+ 強制止盈）
        
        Args:
            symbol: 交易對
            direction: 方向
            current_confidence: 當前信心值（0-1）
            current_win_probability: 當前勝率（0-1）
            drop_threshold: 降低閾值（默認0.20=20%）
        
        Returns:
            tuple: (should_close, reason)
            - should_close: True表示應該平倉
            - reason: 平倉原因（如果should_close=True）
        """
        metrics_5min_ago = self.get_metrics_5min_ago(symbol, direction)
        
        if not metrics_5min_ago:
            # 沒有歷史數據，無法比較
            return False, None
        
        confidence_5min_ago, win_prob_5min_ago = metrics_5min_ago
        
        # 計算降幅
        if confidence_5min_ago > 0:
            conf_drop = (confidence_5min_ago - current_confidence) / confidence_5min_ago
        else:
            conf_drop = 0
        
        if win_prob_5min_ago > 0:
            win_prob_drop = (win_prob_5min_ago - current_win_probability) / win_prob_5min_ago
        else:
            win_prob_drop = 0
        
        # 檢查是否任一指標降低超過閾值
        if conf_drop >= drop_threshold:
            reason = (
                f"信心值降低{conf_drop:.1%}（5分鐘前：{confidence_5min_ago:.1%} → "
                f"現在：{current_confidence:.1%}）"
            )
            return True, reason
        
        if win_prob_drop >= drop_threshold:
            reason = (
                f"勝率降低{win_prob_drop:.1%}（5分鐘前：{win_prob_5min_ago:.1%} → "
                f"現在：{current_win_probability:.1%}）"
            )
            return True, reason
        
        return False, None
    
    def clear_position_metrics(self, symbol: str, direction: str):
        """
        清除倉位的歷史指標記錄（平倉後調用）
        
        Args:
            symbol: 交易對
            direction: 方向
        """
        position_key = f"{symbol}_{direction}"
        if position_key in self.position_metrics_history:
            del self.position_metrics_history[position_key]
            logger.debug(f"✅ 清除 {position_key} 的歷史指標記錄")
