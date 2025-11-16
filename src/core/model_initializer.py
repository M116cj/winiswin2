"""
v3.17+ 模型自動初始化系統
部署到 Railway 後立即訓練，無需手動干預

v4.0 Feature Unification:
- 使用统一的12个ICT/SMC特征（与预测保持一致）
- 训练和推理使用相同的feature_schema
"""

import os
import asyncio
from src.utils.logger_factory import get_logger
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
from src.config import Config
from src.ml.feature_schema import (
    CANONICAL_FEATURE_NAMES,
    extract_canonical_features,
    features_to_vector,
    FEATURE_DEFAULTS
)

logger = get_logger(__name__)


class ModelInitializer:
    """
    模型自動初始化器（v3.17+）
    
    職責：
    1. 檢測模型是否存在
    2. 若無模型，自動收集訓練數據
    3. 使用中性參數訓練初始模型
    4. 創建 initialized.flag 標記
    5. 零配置啟動，無人工干預
    """
    
    def __init__(
        self,
        binance_client=None,
        trade_recorder=None,
        config_profile=None,
        model_evaluator=None
    ):
        """
        初始化模型初始化器
        
        Args:
            binance_client: BinanceClient 實例（可選）
            trade_recorder: TradeRecorder 實例（可選）
            config_profile: ConfigProfile 實例（可選）
            model_evaluator: ModelEvaluator 實例（可選，v3.17.10+）
        """
        self.binance = binance_client
        self.trade_recorder = trade_recorder
        self.config = config_profile
        self.model_evaluator = model_evaluator  # 🔥 v3.17.10+
        
        # 模型目錄
        self.model_dir = Path("models")
        self.model_dir.mkdir(exist_ok=True)
        
        self.flag_file = self.model_dir / "initialized.flag"
        self.model_file = self.model_dir / "xgboost_model.json"
        
        # 🔥 v4.1+ 優化級 XGBoost 參數（降低過擬合風險）
        self.training_params = {
            # 🌱 樹結構（控制複雜度）- OPTIMIZED
            'n_estimators': int(os.getenv("XGBOOST_N_ESTIMATORS", "30")),        # 樹數量：100→30 (-70%)
            'max_depth': int(os.getenv("XGBOOST_MAX_DEPTH", "3")),               # 樹深度：6→3 (-50%)
            'min_child_weight': int(os.getenv("XGBOOST_MIN_CHILD_WEIGHT", "50")), # 葉節點最小樣本：10→50 (5x，兼容200樣本)
            
            # ⚖️ 正則化（提升泛化）- ENHANCED
            'gamma': float(os.getenv("XGBOOST_GAMMA", "0.2")),                   # 分裂最小損失：0.1→0.2
            'subsample': float(os.getenv("XGBOOST_SUBSAMPLE", "0.6")),           # 訓練樣本採樣：0.8→0.6
            'colsample_bytree': float(os.getenv("XGBOOST_COLSAMPLE", "0.6")),    # 特徵採樣：0.8→0.6
            
            # 🚀 學習率（穩定收斂）- MORE STABLE
            'learning_rate': float(os.getenv("XGBOOST_LEARNING_RATE", "0.05")),  # 學習步長：0.1→0.05
            
            # 🎯 目標函數（二分類）
            'objective': 'binary:logistic',     # 邏輯迴歸損失
            'eval_metric': 'logloss',           # 評估指標：對概率預測更敏感
            
            # 🧠 其他配置
            'random_state': 42,                 # 可重現性
            'n_jobs': -1,                       # 多核心加速
            'verbosity': 0,                     # 靜默模式（適合生產）
            
            # 訓練數據配置
            'min_samples': int(os.getenv("INITIAL_TRAINING_SAMPLES", "200")),
            'lookback_days': int(os.getenv("INITIAL_TRAINING_LOOKBACK_DAYS", "30")),
        }
        
        # ✅ STEP 1 VALIDATION
        logger.info("✅ XGBoost參數已優化（v4.1 修正版）:")
        logger.info(f"   樹數量: 100 → {self.training_params['n_estimators']}")
        logger.info(f"   樹深度: 6 → {self.training_params['max_depth']}")
        logger.info(f"   最小子節點權重: 10 → {self.training_params['min_child_weight']} (兼容200樣本)")
        
        logger.info("=" * 60)
        logger.info("✅ 模型自動初始化器已創建（v3.18.6+生產級）")
        logger.info(f"   📁 模型目錄: {self.model_dir}")
        logger.info(f"   🎯 訓練參數: n_estimators={self.training_params['n_estimators']}, "
                   f"max_depth={self.training_params['max_depth']}, "
                   f"min_child_weight={self.training_params['min_child_weight']}, "
                   f"gamma={self.training_params['gamma']}")
        logger.info(f"   🎯 目標函數: {self.training_params['objective']}, "
                   f"評估指標: {self.training_params['eval_metric']}")
        logger.info("=" * 60)
    
    async def check_and_initialize(self) -> bool:
        """
        檢查模型是否已初始化，若無則自動訓練
        
        Returns:
            是否已初始化（True=已存在或訓練成功，False=訓練失敗）
        """
        # 🔒 v3.18.7+：檢查模型訓練鎖定開關
        if getattr(Config, 'DISABLE_MODEL_TRAINING', False):
            logger.info("🔒 模型訓練已鎖定（DISABLE_MODEL_TRAINING=True）")
            logger.info("   ✅ 系統將使用現有模型，不進行初始訓練或重訓練")
            
            # 檢查是否已有模型文件
            if self.model_file.exists():
                logger.info(f"   ✅ 檢測到現有模型: {self.model_file}")
                # 即使沒有flag文件，也創建一個（防止下次檢查）
                if not self.flag_file.exists():
                    self._create_flag_file()
                return True
            else:
                logger.warning(f"   ⚠️ 未檢測到模型文件: {self.model_file}")
                logger.warning("   ⚠️ 請確保已有預訓練模型，或臨時關閉DISABLE_MODEL_TRAINING")
                return False
        
        # 檢查標記文件
        if self.flag_file.exists():
            logger.info("✅ 模型已初始化（檢測到 initialized.flag）")
            return True
        
        logger.warning("⚠️ 未檢測到初始化模型，開始自動訓練...")
        
        # 執行初始訓練
        success = await self._initial_training()
        
        if success:
            # 創建標記文件
            self._create_flag_file()
            logger.info("🎉 模型初始化完成！系統已就緒")
            return True
        else:
            logger.error("❌ 模型初始化失敗，請檢查日誌")
            return False
    
    async def _initial_training(self) -> bool:
        """
        執行初始訓練
        
        Returns:
            訓練是否成功
        """
        try:
            logger.info("🚀 開始收集訓練數據...")
            
            # 1. 收集高品質交易數據
            training_data = await self._collect_training_data()
            
            if not training_data or len(training_data) < self.training_params['min_samples']:
                logger.error(
                    f"❌ 訓練數據不足: {len(training_data) if training_data else 0} "
                    f"< {self.training_params['min_samples']}"
                )
                return False
            
            logger.info(f"✅ 收集到 {len(training_data)} 筆訓練數據")
            
            # 2. 訓練初始模型
            logger.info("🧠 開始訓練 XGBoost 模型...")
            model_success = await self._train_xgboost_model(training_data)
            
            if not model_success:
                logger.error("❌ XGBoost 模型訓練失敗")
                return False
            
            logger.info("✅ XGBoost 模型訓練完成")
            
            # 3. 初始化特徵權重（無先驗偏好）
            self._initialize_feature_weights()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 初始訓練失敗: {e}", exc_info=True)
            return False
    
    async def _collect_training_data(self) -> List[Dict[str, Any]]:
        """
        🔥 v3.18.6+ Critical Fix: 收集訓練數據（優先使用trades.jsonl）
        
        策略：
        1. 🔥 優先從 trades.jsonl 加載真實交易數據（44個特徵）
        2. 若數據不足，使用市場數據生成合成樣本
        
        Returns:
            訓練數據列表
        """
        training_data = []
        
        # 🔥 v4.0+: 從 PostgreSQL/JSONL 加載真實交易數據
        logger.info("📊 加載真實交易數據（PostgreSQL優先）...")
        real_trades = await self._load_training_data_from_trades()
        
        if real_trades:
            logger.info(f"✅ 加載 {len(real_trades)} 筆真實交易數據（12特徵）")
            training_data.extend(real_trades)
        else:
            logger.warning("⚠️ PostgreSQL/JSONL 無數據或不存在")
        
        # 策略 2: 若數據不足，生成合成樣本
        if len(training_data) < self.training_params['min_samples']:
            needed = self.training_params['min_samples'] - len(training_data)
            logger.info(f"📊 數據不足，從市場數據生成 {needed} 個合成樣本...")
            synthetic_samples = await self._generate_synthetic_samples(target_count=needed)
            training_data.extend(synthetic_samples)
        
        logger.info(f"✅ 總計收集 {len(training_data)} 筆訓練數據")
        logger.info(f"   真實交易: {len(real_trades)}")
        logger.info(f"   合成樣本: {len(training_data) - len(real_trades)}")
        
        return training_data
    
    async def _get_historical_trades(self) -> List[Dict[str, Any]]:
        """獲取歷史交易記錄"""
        try:
            if self.trade_recorder is None:
                return []
            
            if hasattr(self.trade_recorder, 'get_all_trades'):
                return await self.trade_recorder.get_all_trades()
            elif hasattr(self.trade_recorder, 'get_closed_trades'):
                return await self.trade_recorder.get_closed_trades()
            else:
                return []
        except Exception as e:
            logger.error(f"❌ 獲取歷史交易失敗: {e}")
            return []
    
    async def _generate_synthetic_samples(self, target_count: int) -> List[Dict[str, Any]]:
        """
        生成合成訓練樣本
        
        策略：從實時市場數據提取特徵，使用簡單規則標註
        
        Args:
            target_count: 目標樣本數量
            
        Returns:
            合成樣本列表
        """
        synthetic_samples = []
        
        if not self.binance:
            logger.warning("⚠️ 無 BinanceClient，無法生成合成樣本")
            return synthetic_samples
        
        try:
            # 獲取熱門交易對
            symbols = await self._get_top_symbols(limit=20)
            
            logger.info(f"📊 從 {len(symbols)} 個交易對生成合成樣本...")
            
            # 為每個交易對生成樣本
            samples_per_symbol = max(1, target_count // len(symbols))
            
            for symbol in symbols:
                try:
                    # 獲取 K 線數據（1 小時，最近 200 根）
                    klines = await self.binance.get_klines(
                        symbol=symbol,
                        interval='1h',
                        limit=200
                    )
                    
                    if not klines or len(klines) < 100:
                        continue
                    
                    # 生成特徵並標註
                    samples = self._extract_features_and_label(klines, samples_per_symbol)
                    synthetic_samples.extend(samples)
                    
                    if len(synthetic_samples) >= target_count:
                        break
                        
                except Exception as e:
                    logger.debug(f"⚠️ {symbol} 生成樣本失敗: {e}")
                    continue
            
            logger.info(f"✅ 生成 {len(synthetic_samples)} 筆合成樣本")
            
        except Exception as e:
            logger.error(f"❌ 生成合成樣本失敗: {e}")
        
        return synthetic_samples[:target_count]
    
    async def _get_top_symbols(self, limit: int = 20) -> List[str]:
        """獲取熱門交易對"""
        try:
            if self.binance is None:
                return ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
            
            # 獲取 24h 交易量排名
            tickers = await self.binance.get_24h_tickers()
            
            # 過濾 USDT 合約，按交易量排序
            usdt_tickers = [
                t for t in tickers
                if t['symbol'].endswith('USDT')
            ]
            
            sorted_tickers = sorted(
                usdt_tickers,
                key=lambda x: float(x.get('quoteVolume', 0)),
                reverse=True
            )
            
            return [t['symbol'] for t in sorted_tickers[:limit]]
            
        except Exception as e:
            logger.error(f"❌ 獲取熱門交易對失敗: {e}")
            # 返回默認列表
            return ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
    
    def _extract_features_and_label(
        self,
        klines: List[Dict],
        max_samples: int
    ) -> List[Dict[str, Any]]:
        """
        從 K 線提取特徵並標註
        
        簡單規則：
        - 上漲趨勢（20 EMA 上穿 50 EMA）→ 正樣本
        - 下跌趨勢（20 EMA 下穿 50 EMA）→ 負樣本
        
        Args:
            klines: K 線數據
            max_samples: 最大樣本數
            
        Returns:
            特徵樣本列表
        """
        samples = []
        
        try:
            import pandas as pd
            import numpy as np
            
            # 轉換為 DataFrame
            df = pd.DataFrame(klines)
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            # 計算 EMA
            df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
            
            # 計算 RSI
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # 計算 ATR
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            df['atr'] = ranges.max(axis=1).rolling(window=14).mean()
            
            # 生成樣本（選擇趨勢明確的點）
            for i in range(60, len(df) - 10, 10):  # 每 10 根 K 線取一個樣本
                if len(samples) >= max_samples:
                    break
                
                row = df.iloc[i]
                
                # 特徵
                features = {
                    'ema_20': row['ema_20'],
                    'ema_50': row['ema_50'],
                    'rsi': row['rsi'],
                    'atr': row['atr'],
                    'volume': row['volume'],
                    'close': row['close'],
                }
                
                # 標註（簡單規則）
                ema_diff = row['ema_20'] - row['ema_50']
                future_return = (df.iloc[i + 10]['close'] - row['close']) / row['close']
                
                # 正樣本：EMA 多頭排列 且 未來上漲
                # 負樣本：EMA 空頭排列 且 未來下跌
                if ema_diff > 0 and future_return > 0.01:
                    label = 1  # 勝利
                elif ema_diff < 0 and future_return < -0.01:
                    label = 1  # 勝利（空頭判斷正確）
                else:
                    label = 0  # 失敗
                
                samples.append({
                    'features': features,
                    'label': label,
                    'pnl': future_return,
                })
        
        except Exception as e:
            logger.error(f"❌ 提取特徵失敗: {e}")
        
        return samples
    
    async def _load_training_data_from_trades(self) -> List[Dict]:
        """
        🔥 v4.0 Feature Unification: 從 PostgreSQL 加載真實交易數據
        
        使用统一的12个ICT/SMC特征（与预测一致）
        
        Returns:
            訓練數據列表（每個元素包含12個標準特徵 + label）
        """
        training_data = []
        
        # v4.0: 优先从PostgreSQL读取
        if self.trade_recorder and hasattr(self.trade_recorder, 'data_service'):
            try:
                trades = await self.trade_recorder.data_service.get_all_trades()
                
                for trade in trades:
                    # 提取元数据中的特征
                    metadata = trade.get('metadata', {})
                    features_dict = metadata.get('features', {})
                    
                    # v4.0: 即使缺少features，也使用默认值（defensive）
                    if not features_dict:
                        logger.debug(f"⚠️ Trade {trade.get('id')} 缺少features，使用默认值")
                        features_dict = {}
                    
                    # 提取12个标准特征（缺失字段使用FEATURE_DEFAULTS）
                    canonical = extract_canonical_features(features_dict)
                    
                    # 确定标签（outcome: WIN=1, LOSS=0）
                    label = 1 if trade.get('outcome') == 'WIN' else 0
                    
                    training_data.append({
                        'features': canonical,
                        'label': label,
                        'pnl': float(trade.get('pnl', 0))
                    })
                
                if training_data:
                    logger.info(f"✅ 從 PostgreSQL 加載 {len(training_data)} 筆訓練數據（12特徵）")
                    return training_data
                else:
                    logger.warning("⚠️ PostgreSQL無可用訓練數據，嘗試JSONL備援")
                
            except Exception as e:
                logger.warning(f"⚠️ 從PostgreSQL加載失敗: {e}，嘗試JSONL備援")
        
        # Fallback: 从trades.jsonl读取（向后兼容 or PostgreSQL不足）
        trades_file = Path("data/trades.jsonl")
        
        if not trades_file.exists():
            logger.warning(f"⚠️ 訓練數據文件不存在: {trades_file}")
            return training_data  # 返回PostgreSQL数据（可能为空）
        
        try:
            with open(trades_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            trade = json.loads(line)
                            
                            # v4.0: 从旧格式提取12个标准特征
                            features_dict = trade.get('features', trade)
                            canonical = extract_canonical_features(features_dict)
                            
                            label = int(trade.get('label', trade.get('outcome') == 'WIN'))
                            
                            training_data.append({
                                'features': canonical,
                                'label': label,
                                'pnl': float(trade.get('pnl', 0))
                            })
                        except (json.JSONDecodeError, Exception) as e:
                            logger.debug(f"跳過無效數據行: {e}")
                            continue
            
            if training_data:
                logger.info(f"✅ 從 {trades_file} 加載 {len(training_data)} 筆訓練數據（12特徵）")
            
        except Exception as e:
            logger.error(f"❌ 加載訓練數據失敗: {e}")
        
        return training_data
    
    def _extract_44_features_DEPRECATED(self, trade: Dict) -> Optional[List[float]]:
        """
        ⚠️ DEPRECATED v4.0: This method is no longer used
        
        v4.0 now uses 12 canonical ICT/SMC features via feature_schema.py
        Kept for reference only
        """
        logger.warning("⚠️ _extract_44_features is deprecated, use feature_schema instead")
        return None  # No longer functional
        try:
            # 🔥 v3.18.6+ Critical Fix: 所有字段都使用默認值，確保歷史數據不被跳過
            features = [
                # 基本特徵 (8) - 核心字段優先從trade讀取
                float(trade.get('confidence', trade.get('confidence_score', 0.5))),
                float(trade.get('leverage', 1.0)),
                float(trade.get('position_value', 0.0)),
                float(trade.get('risk_reward_ratio', trade.get('rr_ratio', 1.5))),
                float(trade.get('order_blocks_count', trade.get('order_blocks', 0))),
                float(trade.get('liquidity_zones_count', trade.get('liquidity_zones', 0))),
                float(trade.get('entry_price', 0.0)),
                float(trade.get('win_probability', 0.5)),
                
                # 技術指標 (10) - 使用中性默認值
                float(trade.get('rsi', 50.0)),
                float(trade.get('macd', 0.0)),
                float(trade.get('macd_signal', 0.0)),
                float(trade.get('macd_histogram', 0.0)),
                float(trade.get('atr', 0.0)),
                float(trade.get('bb_width', 0.0)),
                float(trade.get('volume_sma_ratio', 1.0)),
                float(trade.get('ema50', 0.0)),
                float(trade.get('ema200', 0.0)),
                float(trade.get('volatility_24h', 0.0)),
                
                # 趨勢特徵 (6) - 使用中性默認值
                float(trade.get('trend_1h', 0)),
                float(trade.get('trend_15m', 0)),
                float(trade.get('trend_5m', 0)),
                float(trade.get('market_structure', 0)),
                float(trade.get('direction', 1)),  # LONG=1, SHORT=-1
                float(trade.get('trend_alignment', 0.0)),
                
                # 其他特徵 (14) - 所有可選字段使用默認值
                float(trade.get('ema50_slope', 0.0)),
                float(trade.get('ema200_slope', 0.0)),
                float(trade.get('higher_highs', 0)),
                float(trade.get('lower_lows', 0)),
                float(trade.get('support_strength', 0.5)),
                float(trade.get('resistance_strength', 0.5)),
                float(trade.get('fvg_count', 0)),
                float(trade.get('swing_high_distance', 0.0)),
                float(trade.get('swing_low_distance', 0.0)),
                float(trade.get('volume_profile', 0.5)),
                float(trade.get('price_momentum', 0.0)),
                float(trade.get('order_flow', 0.0)),
                float(trade.get('liquidity_grab', 0)),
                float(trade.get('institutional_candle', 0)),
                
                # 競價上下文特徵 (3) - 新字段使用默認值
                float(trade.get('competition_rank', 1)),
                float(trade.get('score_gap_to_best', 0.0)),
                float(trade.get('num_competing_signals', 1)),
                
                # WebSocket專屬特徵 (3) - 新字段使用默認值
                float(trade.get('latency_zscore', 0.0)),
                float(trade.get('shard_load', 0.0)),
                float(trade.get('timestamp_consistency', 1))
            ]
            
            # 驗證長度
            if len(features) != 44:
                logger.error(f"特徵數量錯誤: {len(features)} != 44")
                return None
            
            return features
            
        except (ValueError, TypeError) as e:
            # 只在類型轉換失敗時返回None
            logger.warning(f"特徵提取失敗（數據類型錯誤）: {e}")
            return None
        except Exception as e:
            logger.error(f"特徵提取異常: {e}")
            return None
    
    async def _train_xgboost_model(self, training_data: List[Dict]) -> bool:
        """
        🔥 v4.0 Feature Unification: 訓練 XGBoost 模型（使用12個ICT/SMC特徵）
        
        Args:
            training_data: 訓練數據（包含12個標準特徵 + label）
            
        Returns:
            訓練是否成功
        """
        try:
            import xgboost as xgb
            import numpy as np
            
            # 🔥 v4.0: 提取12個標準特徵
            X = []
            y = []
            
            for trade in training_data:
                # 提取12個特徵向量
                features_dict = trade.get('features', {})
                features_vector = features_to_vector(features_dict)
                
                # 提取標籤
                label = int(trade.get('label', 0))
                
                X.append(features_vector)
                y.append(label)
            
            if len(X) < 10:
                logger.error(f"❌ 特徵數據不足: {len(X)} < 10")
                return False
            
            X = np.array(X)
            y = np.array(y)
            
            logger.info(f"📊 訓練數據: X.shape={X.shape}, y.shape={y.shape}")
            logger.info(f"   ✅ 使用 {len(CANONICAL_FEATURE_NAMES)} 個ICT/SMC特徵（與預測一致）")
            logger.info(f"   📈 正樣本: {np.sum(y)} / {len(y)} ({np.mean(y)*100:.1f}%)")
            
            # 創建 DMatrix
            dtrain = xgb.DMatrix(X, label=y)
            
            # 🔥 v3.18.6+ 生產級訓練參數
            params = {
                # 目標函數與評估
                'objective': self.training_params['objective'],
                'eval_metric': self.training_params['eval_metric'],
                
                # 樹結構
                'max_depth': self.training_params['max_depth'],
                'min_child_weight': self.training_params['min_child_weight'],
                
                # 正則化
                'gamma': self.training_params['gamma'],
                'subsample': self.training_params['subsample'],
                'colsample_bytree': self.training_params['colsample_bytree'],
                
                # 學習率
                'learning_rate': self.training_params['learning_rate'],
                
                # 其他
                'seed': self.training_params['random_state'],
                'n_jobs': self.training_params['n_jobs'],
                'verbosity': self.training_params['verbosity'],
            }
            
            # 訓練模型
            logger.info(f"🧠 開始訓練: {self.training_params['n_estimators']} 棵樹...")
            
            model = xgb.train(
                params,
                dtrain,
                num_boost_round=self.training_params['n_estimators'],
                verbose_eval=False
            )
            
            # 保存模型
            model.save_model(str(self.model_file))
            
            # 檢查模型大小
            model_size = os.path.getsize(self.model_file) / 1024
            logger.info(f"💾 模型已保存: {self.model_file} ({model_size:.2f} KB)")
            
            if model_size > 100:
                logger.warning(f"⚠️ 模型較大 ({model_size:.2f} KB)，建議量化")
            
            # 🔥 v3.17.10+：訓練後分析特徵重要性（反饋循環）
            if self.model_evaluator:
                try:
                    logger.info("📊 分析模型特徵重要性...")
                    self.model_evaluator.analyze_feature_importance(model)
                except Exception as e:
                    logger.warning(f"⚠️ 特徵重要性分析失敗: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ XGBoost 訓練失敗: {e}", exc_info=True)
            return False
    
    def _initialize_feature_weights(self):
        """初始化特徵權重（無先驗偏好）"""
        weights_file = self.model_dir / "feature_weights.json"
        
        # 所有特徵權重設為 1.0（無偏好）
        default_weights = {
            'ema_20': 1.0,
            'ema_50': 1.0,
            'rsi': 1.0,
            'atr': 1.0,
            'volume': 1.0,
            'adx': 1.0,
            'macd': 1.0,
        }
        
        with open(weights_file, 'w') as f:
            json.dump(default_weights, f, indent=2)
        
        logger.info(f"✅ 特徵權重已初始化: {weights_file}")
    
    def _create_flag_file(self):
        """創建初始化標記文件"""
        flag_data = {
            'initialized_at': datetime.now().isoformat(),
            'training_params': self.training_params,
            'model_file': str(self.model_file),
            'version': 'v3.17+',
        }
        
        with open(self.flag_file, 'w') as f:
            json.dump(flag_data, f, indent=2)
        
        logger.info(f"✅ 初始化標記已創建: {self.flag_file}")
    
    async def force_retrain(self) -> bool:
        """
        強制重新訓練（刪除標記文件並重新初始化）
        
        Returns:
            重新訓練是否成功
        """
        logger.warning("⚠️ 強制重新訓練模型...")
        
        # 刪除標記文件
        if self.flag_file.exists():
            self.flag_file.unlink()
            logger.info("🗑️ 已刪除 initialized.flag")
        
        # 刪除舊模型
        if self.model_file.exists():
            self.model_file.unlink()
            logger.info("🗑️ 已刪除舊模型文件")
        
        # 重新初始化
        return await self.check_and_initialize()
    
    def should_retrain(self) -> bool:
        """
        動態重訓練觸發條件（v3.17.10+）
        
        解決「市場適應慢」問題：
        - 固定 50 筆觸發無法應對市場 regime shift
        - 從 trending → choppy 轉換時需要立即重訓練
        
        Returns:
            是否應該重訓練
        """
        try:
            # 條件 1：性能驟降（Sharpe 比率下降 50%）
            recent_trades = self._get_recent_trades(days=1)
            
            if len(recent_trades) >= 10:
                current_sharpe = self._calculate_sharpe(recent_trades)
                historical_sharpe = self._get_historical_sharpe()
                
                if historical_sharpe > 0 and current_sharpe < historical_sharpe * 0.5:
                    logger.warning(
                        f"⚠️ 性能驟降觸發重訓練: "
                        f"當前 Sharpe={current_sharpe:.2f} "
                        f"歷史 Sharpe={historical_sharpe:.2f} "
                        f"(下降 {(1 - current_sharpe/historical_sharpe)*100:.1f}%)"
                    )
                    return True
            
            # 條件 2：市場狀態劇變（regime shift）
            current_regime = self._get_current_market_regime()
            last_regime = self._get_last_market_regime()
            
            if current_regime != last_regime and last_regime is not None:
                logger.warning(
                    f"⚠️ 市場狀態劇變觸發重訓練: "
                    f"{last_regime} → {current_regime}"
                )
                self._update_last_market_regime(current_regime)
                return True
            
            # 條件 3：累積足夠樣本（原有邏輯）
            new_samples = self._count_new_samples()
            if new_samples >= 50:
                logger.info(
                    f"ℹ️ 累積樣本觸發重訓練: {new_samples} 筆新交易"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"檢查重訓練條件失敗: {e}", exc_info=True)
            return False
    
    def _get_recent_trades(self, days: int = 1) -> List[Dict]:
        """
        獲取最近 N 天的交易記錄
        
        Args:
            days: 天數
            
        Returns:
            交易記錄列表
        """
        try:
            if not self.trade_recorder:
                return []
            
            cutoff_time = datetime.now() - timedelta(days=days)
            all_trades = self.trade_recorder.completed_trades
            
            recent = [
                t for t in all_trades
                if datetime.fromisoformat(t.get('entry_timestamp', '1970-01-01')) > cutoff_time
            ]
            
            return recent
            
        except Exception as e:
            logger.error(f"獲取最近交易失敗: {e}")
            return []
    
    def _calculate_sharpe(self, trades: List[Dict]) -> float:
        """
        計算 Sharpe 比率
        
        Args:
            trades: 交易記錄列表
            
        Returns:
            Sharpe 比率
        """
        try:
            if not trades:
                return 0.0
            
            import numpy as np
            
            returns = [t.get('pnl_pct', 0.0) for t in trades]
            
            if not returns:
                return 0.0
            
            mean_return = float(np.mean(returns))
            std_return = float(np.std(returns))
            
            if std_return == 0:
                return 0.0
            
            sharpe = mean_return / std_return
            
            return float(sharpe)
            
        except Exception as e:
            logger.error(f"計算 Sharpe 失敗: {e}")
            return 0.0
    
    def _get_historical_sharpe(self) -> float:
        """
        獲取歷史 Sharpe 比率（過去 7 天）
        
        Returns:
            歷史 Sharpe 比率
        """
        try:
            historical_trades = self._get_recent_trades(days=7)
            return self._calculate_sharpe(historical_trades)
        except Exception as e:
            logger.error(f"獲取歷史 Sharpe 失敗: {e}")
            return 0.0
    
    def _get_current_market_regime(self) -> str:
        """
        獲取當前市場狀態
        
        Returns:
            'trending', 'choppy', 'volatile', 'calm'
        """
        try:
            # 簡化版：基於最近交易的勝率和波動性
            recent_trades = self._get_recent_trades(days=1)
            
            if len(recent_trades) < 5:
                return 'unknown'
            
            import numpy as np
            
            # 計算勝率
            winners = sum(1 for t in recent_trades if t.get('pnl_pct', 0) > 0)
            win_rate = winners / len(recent_trades)
            
            # 計算波動性
            returns = [t.get('pnl_pct', 0.0) for t in recent_trades]
            volatility = np.std(returns)
            
            # 簡單分類
            if volatility > 0.05:  # 高波動
                return 'volatile'
            elif win_rate > 0.6:  # 高勝率
                return 'trending'
            elif win_rate < 0.4:  # 低勝率
                return 'choppy'
            else:
                return 'calm'
                
        except Exception as e:
            logger.error(f"獲取市場狀態失敗: {e}")
            return 'unknown'
    
    def _get_last_market_regime(self) -> Optional[str]:
        """
        獲取上次記錄的市場狀態
        
        Returns:
            上次市場狀態或 None
        """
        try:
            regime_file = self.model_dir / "market_regime.json"
            
            if not regime_file.exists():
                return None
            
            with open(regime_file, 'r') as f:
                data = json.load(f)
                return data.get('regime')
                
        except Exception as e:
            logger.error(f"讀取市場狀態失敗: {e}")
            return None
    
    def _update_last_market_regime(self, regime: str):
        """
        更新市場狀態記錄
        
        Args:
            regime: 新的市場狀態
        """
        try:
            regime_file = self.model_dir / "market_regime.json"
            
            data = {
                'regime': regime,
                'updated_at': datetime.now().isoformat()
            }
            
            with open(regime_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"更新市場狀態失敗: {e}")
    
    def _count_new_samples(self) -> int:
        """
        計算自上次訓練以來的新樣本數
        
        Returns:
            新樣本數量
        """
        try:
            if not self.trade_recorder:
                return 0
            
            # 讀取上次訓練時間
            if not self.flag_file.exists():
                return 0
            
            with open(self.flag_file, 'r') as f:
                flag_data = json.load(f)
                last_trained = datetime.fromisoformat(flag_data.get('initialized_at', '1970-01-01'))
            
            # 計算新交易數
            all_trades = self.trade_recorder.completed_trades
            new_trades = [
                t for t in all_trades
                if datetime.fromisoformat(t.get('entry_timestamp', '1970-01-01')) > last_trained
            ]
            
            return len(new_trades)
            
        except Exception as e:
            logger.error(f"計算新樣本數失敗: {e}")
            return 0
