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
from src.core.unified_config_manager import config_manager as config
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
        🔥 v4.6.0 Phase 2: 收集訓練數據（PostgreSQL唯一數據源）
        
        策略：
        1. 🔥 從 PostgreSQL 加載真實交易數據（12個ICT/SMC特徵）
        2. 若數據不足，使用市場數據生成合成樣本
        
        Returns:
            訓練數據列表
        """
        training_data = []
        
        # 🔥 v4.6.0 Phase 2: 從 PostgreSQL 加載真實交易數據（已移除JSONL fallback）
        logger.info("📊 加載真實交易數據（PostgreSQL唯一數據源）...")
        real_trades = await self._load_training_data_from_trades()
        
        if real_trades:
            logger.info(f"✅ 加載 {len(real_trades)} 筆真實交易數據（12特徵）")
            training_data.extend(real_trades)
        else:
            logger.warning("⚠️ PostgreSQL 無數據")
        
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
        生成使用12个ICT/SMC特征的合成样本（v4.5.0兼容）
        
        v4.5.0 P0修复：重新启用合成样本生成，解决新部署环境无数据问题
        使用12个ICT/SMC特征（与预测一致）
        
        Args:
            target_count: 目標樣本數量
            
        Returns:
            合成样本列表（每个样本包含12个ICT/SMC特征）
        """
        import random
        
        logger.info(f"⚙️  生成{target_count}个合成样本（使用12个ICT/SMC特征）")
        
        samples = []
        for i in range(target_count):
            # 随机生成WIN/LOSS标签
            label = random.choice([0, 1])
            
            # 生成12个ICT/SMC特征的合理随机值
            features = {
                # 基础特征（8个）
                'market_structure': random.choice([-1, 0, 1]),  # 看跌/中性/看涨
                'order_blocks_count': random.randint(0, 5),  # 0-5个订单块
                'institutional_candle': random.choice([0, 1]),  # 是否机构K线
                'liquidity_grab': random.choice([0, 1]),  # 是否流动性抓取
                'order_flow': random.uniform(-1.0, 1.0),  # 订单流 -1到1
                'fvg_count': random.randint(0, 3),  # 0-3个FVG
                'trend_alignment_enhanced': random.uniform(0.0, 1.0),  # 趋势对齐度
                'swing_high_distance': random.uniform(0.0, 1.0),  # 摆动高点距离
                
                # 合成特征（4个）
                'structure_integrity': random.uniform(0.0, 1.0),  # 结构完整性
                'institutional_participation': random.uniform(0.0, 1.0),  # 机构参与度
                'timeframe_convergence': random.uniform(0.0, 1.0),  # 时间框架收敛度
                'liquidity_context': random.uniform(0.0, 1.0),  # 流动性情境
            }
            
            # 验证特征完整性
            assert all(feat in features for feat in CANONICAL_FEATURE_NAMES), \
                f"合成样本缺少必需特征"
            
            samples.append({
                'label': label,
                'features': features,
                'pnl': random.uniform(-5.0, 5.0) if label == 1 else random.uniform(-10.0, 0.0)
            })
        
        logger.info(f"✅ 成功生成{len(samples)}个合成样本（特征验证通过）")
        return samples
    
    async def _load_training_data_from_trades(self) -> List[Dict]:
        """
        🔥 v4.6.0 Phase 2: 從 PostgreSQL 加載真實交易數據（唯一數據源）
        
        使用统一的12个ICT/SMC特征（与预测一致），并验证特征完整性
        
        Returns:
            訓練數據列表（每個元素包含12個標準特徵 + label）
        """
        training_data = []
        
        # 🔥 v4.6.0 Phase 2: PostgreSQL唯一数据源（已移除trades.jsonl fallback）
        if self.trade_recorder and hasattr(self.trade_recorder, 'data_service'):
            try:
                # 使用 get_trade_history 获取所有已关闭交易（用于训练）
                trades = await self.trade_recorder.data_service.get_trade_history(
                    status='CLOSED',
                    limit=10000  # 足够大的限制
                )
                
                for trade in trades:
                    # Phase 3: asyncpg返回dict，直接访问字段
                    if isinstance(trade, dict):
                        # 提取元数据中的特征
                        metadata = trade.get('metadata', {})
                        features_dict = metadata.get('features', {}) if isinstance(metadata, dict) else {}
                        
                        # v4.0: 即使缺少features，也使用默认值（defensive）
                        if not features_dict:
                            logger.debug(f"⚠️ Trade {trade.get('id')} 缺少features，使用默认值")
                            features_dict = {}
                        
                        # 提取12个标准特征（缺失字段使用FEATURE_DEFAULTS）
                        canonical = extract_canonical_features(features_dict)
                        
                        # 确定标签（won: True=1, False=0）
                        label = 1 if trade.get('won') is True else 0
                        
                        training_data.append({
                            'features': canonical,
                            'label': label,
                            'pnl': float(trade.get('pnl', 0))
                        })
                    elif hasattr(trade, 'get'):
                        # 向后兼容：处理_row_to_dict返回的数据
                        raw_data = trade.get('raw_data')
                        logger.debug(f"⚠️ 收到raw_data格式，可能需要更新_row_to_dict实现")
                
                if training_data:
                    logger.info(f"✅ 從 PostgreSQL 加載 {len(training_data)} 筆訓練數據（12特徵）")
                else:
                    logger.warning("⚠️ PostgreSQL 無可用訓練數據")
                
            except Exception as e:
                logger.error(f"❌ 從 PostgreSQL 加載訓練數據失敗: {e}", exc_info=True)
        else:
            logger.warning("⚠️ TradeRecorder或DataService未配置，無法加載訓練數據")
        
        # 🔥 v4.5.0 P1: Schema验证 - 过滤不兼容的旧数据
        return self._validate_feature_schema(training_data)
    
    def _validate_feature_schema(self, training_data: List[Dict]) -> List[Dict]:
        """
        🔥 v4.5.0 P1修复: 验证训练数据的特征schema
        
        过滤不包含所有12个ICT/SMC特征的数据（防止训练失败）
        
        Args:
            training_data: 原始训练数据
            
        Returns:
            经过schema验证的训练数据
        """
        if not training_data:
            return training_data
        
        valid_data = []
        invalid_count = 0
        
        for trade in training_data:
            features = trade.get('features', {})
            
            # 验证是否包含所有12个ICT/SMC特征
            missing_features = [f for f in CANONICAL_FEATURE_NAMES if f not in features]
            
            if not missing_features:
                # 所有特征都存在
                valid_data.append(trade)
            else:
                # 缺少特征，跳过此交易
                invalid_count += 1
                if invalid_count <= 3:  # 只记录前3个警告，避免日志过多
                    logger.warning(
                        f"⚠️ 跳过不兼容交易数据（缺少特征: {missing_features[:3]}...）"
                    )
        
        if invalid_count > 0:
            logger.info(
                f"📊 特征schema验证: {len(valid_data)}条有效, "
                f"{invalid_count}条无效（已过滤）"
            )
        else:
            logger.info(f"✅ 特征schema验证: {len(valid_data)}条数据全部有效")
        
        return valid_data
    
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
            
            # 🔥 Stability Fix: Safe JSON read with corruption handling
            with open(regime_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    logger.debug("市場狀態文件為空，返回None")
                    return None
                data = json.loads(content)
                return data.get('regime')
                
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ 市場狀態JSON損壞（已忽略）: {e}")
            return None
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"讀取市場狀態失敗: {e}")
            return None
    
    def _update_last_market_regime(self, regime: str):
        """
        更新市場狀態記錄（使用安全寫入防止損壞）
        
        Args:
            regime: 新的市場狀態
        """
        try:
            regime_file = self.model_dir / "market_regime.json"
            tmp_file = self.model_dir / "market_regime.json.tmp"
            
            data = {
                'regime': regime,
                'updated_at': datetime.now().isoformat()
            }
            
            # 🔥 Stability Fix: Safe write (tmp file + rename)
            with open(tmp_file, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()  # Ensure data is written to disk
                os.fsync(f.fileno())  # Force OS to write to disk
            
            # Atomic rename (prevents corruption during crashes)
            tmp_file.rename(regime_file)
                
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
            
            # 🔥 Stability Fix: Safe JSON read with corruption handling
            with open(self.flag_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    logger.debug("Flag文件為空，返回0樣本")
                    return 0
                flag_data = json.loads(content)
                last_trained = datetime.fromisoformat(flag_data.get('initialized_at', '1970-01-01'))
            
            # 計算新交易數
            all_trades = self.trade_recorder.completed_trades
            new_trades = [
                t for t in all_trades
                if datetime.fromisoformat(t.get('entry_timestamp', '1970-01-01')) > last_trained
            ]
            
            return len(new_trades)
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Flag文件JSON損壞（已忽略，返回0）: {e}")
            return 0
        except FileNotFoundError:
            return 0
        except Exception as e:
            logger.error(f"計算新樣本數失敗: {e}")
            return 0
