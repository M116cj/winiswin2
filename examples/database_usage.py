"""
Railway PostgreSQL Database Usage Examples
数据库使用示例
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import DatabaseManager, TradingDataService, initialize_database
from datetime import datetime
import json


def example_1_basic_setup():
    """示例1: 基本设置和初始化"""
    print("=" * 70)
    print("示例 1: 数据库基本设置")
    print("=" * 70)
    
    # 创建数据库管理器
    db_manager = DatabaseManager(
        min_connections=1,
        max_connections=10,
        auto_retry=True
    )
    
    # 健康检查
    if db_manager.check_health():
        print("✅ 数据库连接正常")
    else:
        print("❌ 数据库连接失败")
        return None
    
    # 初始化表结构
    initialize_database(db_manager)
    
    # 创建服务实例
    db_service = TradingDataService(db_manager)
    
    return db_manager, db_service


def example_2_save_trade(db_service: TradingDataService):
    """示例2: 保存完整交易记录"""
    print("\n" + "=" * 70)
    print("示例 2: 保存完整交易记录")
    print("=" * 70)
    
    # 完整的交易数据（44个特征）
    trade_data = {
        # 基本信息
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry_price': 43250.50,
        'exit_price': 43680.20,
        'quantity': 0.1,
        'leverage': 5,
        'entry_timestamp': '2025-01-15T08:30:00Z',
        'exit_timestamp': '2025-01-15T14:45:00Z',
        
        # 盈亏信息
        'pnl': 42.97,
        'pnl_pct': 1.99,
        'won': True,
        'status': 'CLOSED',
        
        # 策略信息
        'strategy': 'ICT_SMC_Elite',
        'confidence': 0.75,
        'win_probability': 0.72,
        'position_value': 2162.53,
        'risk_reward_ratio': 2.5,
        
        # 技术指标
        'rsi': 58.3,
        'macd': 125.6,
        'macd_signal': 120.1,
        'macd_histogram': 5.5,
        'atr': 450.2,
        'bb_width': 0.015,
        'volume_sma_ratio': 1.2,
        'ema50': 43100.0,
        'ema200': 42800.0,
        'volatility_24h': 0.025,
        
        # 趋势特征
        'trend_1h': 1,
        'trend_15m': 1,
        'trend_5m': 1,
        'market_structure': 1,
        'trend_alignment': 0.85,
        
        # ICT/SMC特征
        'order_blocks_count': 3,
        'liquidity_zones_count': 2,
        'fvg_count': 2,
        'swing_high_distance': 0.005,
        'swing_low_distance': 0.003,
        'order_flow': 0.55,
        'liquidity_grab': 1,
        'institutional_candle': 1,
        
        # EMA斜率
        'ema50_slope': 0.002,
        'ema200_slope': 0.001,
        
        # 支撑/阻力
        'support_strength': 0.7,
        'resistance_strength': 0.6,
        'higher_highs': 3,
        'lower_lows': 0,
        
        # 市场微观结构
        'volume_profile': 0.65,
        'price_momentum': 0.015,
        
        # 竞价特征
        'competition_rank': 1,
        'score_gap_to_best': 0.0,
        'num_competing_signals': 3,
        
        # WebSocket特征
        'latency_zscore': 0.5,
        'shard_load': 0.3,
        'timestamp_consistency': 1,
        
        # 其他信息
        'reason': 'Take Profit Hit',
        'hold_duration_seconds': 22500,
        'entry_id': f"BTCUSDT_{datetime.utcnow().timestamp()}",
        'metadata': {'notes': 'Perfect ICT setup with order block confirmation'}
    }
    
    # 保存到数据库
    trade_id = db_service.save_trade(trade_data)
    
    if trade_id:
        print(f"✅ 交易记录已保存")
        print(f"   交易ID: {trade_id}")
        print(f"   交易对: {trade_data['symbol']}")
        print(f"   方向: {trade_data['direction']}")
        print(f"   盈亏: ${trade_data['pnl']:.2f} ({trade_data['pnl_pct']:.2%})")
        return trade_id
    else:
        print("❌ 保存失败")
        return None


def example_3_query_trades(db_service: TradingDataService):
    """示例3: 查询交易记录"""
    print("\n" + "=" * 70)
    print("示例 3: 查询交易记录")
    print("=" * 70)
    
    # 查询特定交易对的历史
    trades = db_service.get_trade_history(
        symbol='BTCUSDT',
        status='CLOSED',
        limit=10
    )
    
    print(f"✅ 查询到 {len(trades)} 条BTCUSDT已平仓交易")
    
    # 获取统计数据
    stats = db_service.get_statistics()
    
    print("\n📊 交易统计:")
    print(f"   总交易数: {stats.get('total_trades', 0)}")
    print(f"   已平仓: {stats.get('closed_trades', 0)}")
    print(f"   盈利交易: {stats.get('winning_trades', 0)}")
    print(f"   胜率: {stats.get('win_rate', 0):.2%}")
    print(f"   平均盈亏: {stats.get('avg_pnl_pct', 0):.2%}")
    print(f"   总盈亏: ${stats.get('total_pnl', 0):.2f}")


def example_4_ml_model(db_service: TradingDataService):
    """示例4: ML模型管理"""
    print("\n" + "=" * 70)
    print("示例 4: ML模型管理")
    print("=" * 70)
    
    # 创建一个简单的模型对象（实际应该是训练好的模型）
    model_data = {
        'model_type': 'XGBoost',
        'hyperparameters': {
            'max_depth': 5,
            'learning_rate': 0.1,
            'n_estimators': 100
        },
        'training_date': datetime.utcnow().isoformat(),
        'training_samples': 1000
    }
    
    # 特征列表（44个）
    features = [
        # 基本特征 (8)
        'confidence', 'leverage', 'position_value', 'risk_reward_ratio',
        'order_blocks_count', 'liquidity_zones_count', 'entry_price', 'win_probability',
        # 技術指標 (10)
        'rsi', 'macd', 'macd_signal', 'macd_histogram', 'atr', 'bb_width',
        'volume_sma_ratio', 'ema50', 'ema200', 'volatility_24h',
        # 趨勢特徵 (6)
        'trend_1h', 'trend_15m', 'trend_5m', 'market_structure', 'direction', 'trend_alignment',
        # 其他特徵 (14)
        'ema50_slope', 'ema200_slope', 'higher_highs', 'lower_lows',
        'support_strength', 'resistance_strength', 'fvg_count',
        'swing_high_distance', 'swing_low_distance', 'volume_profile',
        'price_momentum', 'order_flow', 'liquidity_grab', 'institutional_candle',
        # 競價上下文特徵 (3)
        'competition_rank', 'score_gap_to_best', 'num_competing_signals',
        # WebSocket專屬特徵 (3)
        'latency_zscore', 'shard_load', 'timestamp_consistency'
    ]
    
    # 保存模型
    model_id = db_service.save_ml_model(
        model_name='xgboost_production',
        model=model_data,
        features=features,
        accuracy=0.85,
        parameters={
            'description': 'Production XGBoost model with 44 features',
            'training_samples': 1000,
            'validation_accuracy': 0.82
        },
        is_active=True
    )
    
    if model_id:
        print(f"✅ ML模型已保存")
        print(f"   模型ID: {model_id}")
        print(f"   模型名称: xgboost_production")
        print(f"   特征数量: {len(features)}")
        print(f"   准确率: 85.00%")
        
        # 加载模型
        loaded_model = db_service.load_ml_model('xgboost_production')
        
        if loaded_model:
            print(f"\n✅ 模型已加载")
            print(f"   模型类型: {loaded_model.get('model_type')}")
            print(f"   训练样本: {loaded_model.get('training_samples')}")
        else:
            print("\n❌ 模型加载失败")
    else:
        print("❌ 模型保存失败")


def example_5_integration():
    """示例5: 与交易机器人集成"""
    print("\n" + "=" * 70)
    print("示例 5: 与交易机器人集成")
    print("=" * 70)
    
    print("""
    # 在您的交易机器人中集成数据库
    
    ## 1. 在main.py中初始化
    
    from src.database import DatabaseManager, TradingDataService, initialize_database
    
    # 启动时初始化
    db_manager = DatabaseManager()
    initialize_database(db_manager)
    db_service = TradingDataService(db_manager)
    
    ## 2. 在EnhancedTradeRecorder中使用
    
    class EnhancedTradeRecorder:
        def __init__(self, db_service):
            self.db_service = db_service
        
        def record_exit(self, symbol, exit_price, pnl, pnl_pct, reason):
            # 保存到JSONL（现有逻辑）
            self._write_to_jsonl(...)
            
            # 同时保存到PostgreSQL
            trade_data = {
                'symbol': symbol,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                # ... 其他字段
            }
            self.db_service.save_trade(trade_data)
    
    ## 3. 在ModelInitializer中使用
    
    async def _train_xgboost_model(self, training_data):
        # 训练模型
        model.fit(X_train, y_train)
        
        # 保存到数据库
        self.db_service.save_ml_model(
            model_name='xgboost_production',
            model=model,
            features=feature_names,
            accuracy=accuracy,
            is_active=True
        )
    """)


def main():
    """主函数：运行所有示例"""
    print("🚀 Railway PostgreSQL 使用示例")
    print("=" * 70)
    
    # 检查环境变量
    if not os.environ.get('DATABASE_URL') and not os.environ.get('DATABASE_PUBLIC_URL'):
        print("⚠️ 未检测到数据库环境变量")
        print("   请在Railway中配置PostgreSQL服务")
        print("   或设置 DATABASE_URL 环境变量进行本地测试")
        return
    
    try:
        # 示例1: 基本设置
        result = example_1_basic_setup()
        if not result:
            return
        
        db_manager, db_service = result
        
        # 示例2: 保存交易
        trade_id = example_2_save_trade(db_service)
        
        # 示例3: 查询交易
        if trade_id:
            example_3_query_trades(db_service)
        
        # 示例4: ML模型
        example_4_ml_model(db_service)
        
        # 示例5: 集成说明
        example_5_integration()
        
        print("\n" + "=" * 70)
        print("✅ 所有示例运行完成！")
        print("=" * 70)
        print("\n📖 更多信息请参考: docs/DATABASE_SETUP.md")
        
        # 清理
        db_manager.close_all_connections()
        
    except Exception as e:
        print(f"\n❌ 示例运行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
