"""
v3.17+ 模型自動初始化系統
部署到 Railway 後立即訓練，無需手動干預
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


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
        config_profile=None
    ):
        """
        初始化模型初始化器
        
        Args:
            binance_client: BinanceClient 實例（可選）
            trade_recorder: TradeRecorder 實例（可選）
            config_profile: ConfigProfile 實例（可選）
        """
        self.binance = binance_client
        self.trade_recorder = trade_recorder
        self.config = config_profile
        
        # 模型目錄
        self.model_dir = Path("models")
        self.model_dir.mkdir(exist_ok=True)
        
        self.flag_file = self.model_dir / "initialized.flag"
        self.model_file = self.model_dir / "xgboost_model.json"
        
        # 訓練參數（中性化，零偏見）
        self.training_params = {
            # XGBoost 中性參數
            'n_estimators': int(os.getenv("XGBOOST_N_ESTIMATORS", "50")),
            'max_depth': int(os.getenv("XGBOOST_MAX_DEPTH", "4")),
            'learning_rate': float(os.getenv("XGBOOST_LEARNING_RATE", "0.1")),
            'subsample': float(os.getenv("XGBOOST_SUBSAMPLE", "0.8")),
            'colsample_bytree': float(os.getenv("XGBOOST_COLSAMPLE", "0.8")),
            'min_child_weight': int(os.getenv("XGBOOST_MIN_CHILD_WEIGHT", "1")),
            'gamma': float(os.getenv("XGBOOST_GAMMA", "0")),
            
            # 訓練配置
            'min_samples': int(os.getenv("INITIAL_TRAINING_SAMPLES", "200")),
            'lookback_days': int(os.getenv("INITIAL_TRAINING_LOOKBACK_DAYS", "30")),
        }
        
        logger.info("=" * 60)
        logger.info("✅ 模型自動初始化器已創建（v3.17+）")
        logger.info(f"   📁 模型目錄: {self.model_dir}")
        logger.info(f"   🎯 訓練參數: n_estimators={self.training_params['n_estimators']}, "
                   f"max_depth={self.training_params['max_depth']}")
        logger.info("=" * 60)
    
    async def check_and_initialize(self) -> bool:
        """
        檢查模型是否已初始化，若無則自動訓練
        
        Returns:
            是否已初始化（True=已存在或訓練成功，False=訓練失敗）
        """
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
        收集訓練數據
        
        策略：
        1. 優先使用歷史交易記錄（若有 TradeRecorder）
        2. 否則使用市場數據生成合成樣本
        
        Returns:
            訓練數據列表
        """
        training_data = []
        
        # 策略 1: 從交易記錄收集
        if self.trade_recorder:
            try:
                cutoff_date = datetime.now() - timedelta(days=self.training_params['lookback_days'])
                
                # 獲取所有交易記錄
                all_trades = await self._get_historical_trades()
                
                # 過濾高品質交易（已平倉，有明確結果）
                quality_trades = [
                    t for t in all_trades
                    if t.get('status') == 'closed' and
                       t.get('pnl') is not None and
                       datetime.fromisoformat(str(t.get('timestamp', cutoff_date))) >= cutoff_date
                ]
                
                if quality_trades:
                    logger.info(f"📊 從交易記錄收集到 {len(quality_trades)} 筆高品質樣本")
                    training_data.extend(quality_trades)
                
            except Exception as e:
                logger.warning(f"⚠️ 無法從交易記錄收集數據: {e}")
        
        # 策略 2: 生成合成樣本（若數據不足）
        if len(training_data) < self.training_params['min_samples']:
            logger.info("📊 從市場數據生成合成樣本...")
            synthetic_samples = await self._generate_synthetic_samples(
                target_count=self.training_params['min_samples'] - len(training_data)
            )
            training_data.extend(synthetic_samples)
        
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
    
    async def _train_xgboost_model(self, training_data: List[Dict]) -> bool:
        """
        訓練 XGBoost 模型
        
        Args:
            training_data: 訓練數據
            
        Returns:
            訓練是否成功
        """
        try:
            import xgboost as xgb
            import numpy as np
            
            # 提取特徵和標籤
            X = []
            y = []
            
            for sample in training_data:
                if 'features' in sample and 'label' in sample:
                    features = sample['features']
                    # 轉換為數值列表
                    feature_vector = [
                        float(features.get('ema_20', 0)),
                        float(features.get('ema_50', 0)),
                        float(features.get('rsi', 50)),
                        float(features.get('atr', 0)),
                        float(features.get('volume', 0)),
                    ]
                    X.append(feature_vector)
                    y.append(int(sample['label']))
            
            if len(X) < 10:
                logger.error(f"❌ 特徵數據不足: {len(X)} < 10")
                return False
            
            X = np.array(X)
            y = np.array(y)
            
            logger.info(f"📊 訓練數據: X.shape={X.shape}, y.shape={y.shape}")
            
            # 創建 DMatrix
            dtrain = xgb.DMatrix(X, label=y)
            
            # 訓練參數（中性化）
            params = {
                'objective': 'binary:logistic',
                'eval_metric': 'logloss',
                'max_depth': self.training_params['max_depth'],
                'learning_rate': self.training_params['learning_rate'],
                'subsample': self.training_params['subsample'],
                'colsample_bytree': self.training_params['colsample_bytree'],
                'min_child_weight': self.training_params['min_child_weight'],
                'gamma': self.training_params['gamma'],
                'seed': 42,
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
            
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            
            if std_return == 0:
                return 0.0
            
            sharpe = mean_return / std_return
            
            return sharpe
            
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
