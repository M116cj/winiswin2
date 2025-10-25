"""
XGBoost 訓練數據格式示例
展示從 DataArchiver 生成的 CSV 文件如何用於 XGBoost 訓練
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_sample_signals_data():
    """
    生成示例的 signals.csv 數據
    包含所有被接受和被拒絕的交易信號
    """
    np.random.seed(42)
    
    signals = []
    base_time = datetime.now() - timedelta(days=7)
    
    for i in range(100):
        timestamp = base_time + timedelta(hours=i)
        
        # 隨機生成信號特徵
        trend_alignment = np.random.uniform(0.3, 1.0)
        market_structure = np.random.uniform(0.5, 1.0)
        price_position = np.random.uniform(0.2, 1.0)
        momentum = np.random.uniform(0.0, 1.0)
        volatility = np.random.uniform(0.4, 1.0)
        
        # 計算總信心度
        confidence = (
            trend_alignment * 0.40 +
            market_structure * 0.20 +
            price_position * 0.20 +
            momentum * 0.10 +
            volatility * 0.10
        )
        
        # 決定是否接受（信心度 >= 55%）
        accepted = confidence >= 0.55
        rejection_reason = "" if accepted else "信心度不足"
        
        signal = {
            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': np.random.choice(['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']),
            'direction': np.random.choice(['LONG', 'SHORT']),
            'confidence': round(confidence, 4),
            'accepted': accepted,
            'rejection_reason': rejection_reason,
            
            # 五維評分
            'trend_alignment_score': round(trend_alignment, 4),
            'market_structure_score': round(market_structure, 4),
            'price_position_score': round(price_position, 4),
            'momentum_score': round(momentum, 4),
            'volatility_score': round(volatility, 4),
            
            # 時間框架趨勢
            'h1_trend': np.random.choice(['BULLISH', 'BEARISH', 'NEUTRAL']),
            'm15_trend': np.random.choice(['BULLISH', 'BEARISH', 'NEUTRAL']),
            'm5_trend': np.random.choice(['BULLISH', 'BEARISH', 'NEUTRAL']),
            
            # 價格信息
            'current_price': round(np.random.uniform(40000, 50000), 2),
            'entry_price': round(np.random.uniform(40000, 50000), 2),
            'stop_loss': round(np.random.uniform(39000, 49000), 2),
            'take_profit': round(np.random.uniform(41000, 51000), 2),
            
            # 技術指標
            'rsi': round(np.random.uniform(30, 70), 2),
            'macd': round(np.random.uniform(-100, 100), 2),
            'macd_signal': round(np.random.uniform(-100, 100), 2),
            'atr': round(np.random.uniform(500, 1500), 2),
            'bb_width_pct': round(np.random.uniform(20, 80), 2),
            
            # Order Block 和流動性
            'order_blocks_count': np.random.randint(1, 5),
            'liquidity_zones_count': np.random.randint(0, 3)
        }
        
        signals.append(signal)
    
    return pd.DataFrame(signals)


def generate_sample_positions_data():
    """
    生成示例的 positions.csv 數據
    包含所有倉位的開倉和平倉記錄
    """
    np.random.seed(42)
    
    positions = []
    base_time = datetime.now() - timedelta(days=7)
    
    for i in range(50):  # 50 個倉位
        position_id = f"POS_{i:04d}"
        is_virtual = np.random.choice([True, False], p=[0.7, 0.3])  # 70% 虛擬倉位
        
        entry_time = base_time + timedelta(hours=i*2)
        exit_time = entry_time + timedelta(hours=np.random.randint(1, 24))
        
        entry_price = round(np.random.uniform(40000, 50000), 2)
        
        # 隨機決定盈虧
        won = np.random.choice([True, False], p=[0.6, 0.4])  # 60% 勝率
        if won:
            pnl_pct = round(np.random.uniform(0.5, 5.0), 2)
            exit_price = round(entry_price * (1 + pnl_pct/100), 2)
        else:
            pnl_pct = round(np.random.uniform(-2.0, -0.5), 2)
            exit_price = round(entry_price * (1 + pnl_pct/100), 2)
        
        quantity = round(np.random.uniform(0.001, 0.1), 4)
        pnl = round((exit_price - entry_price) * quantity, 2)
        
        # 開倉記錄
        open_event = {
            'event': 'OPEN',
            'timestamp': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'position_id': position_id,
            'is_virtual': is_virtual,
            'symbol': np.random.choice(['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']),
            'direction': np.random.choice(['LONG', 'SHORT']),
            'entry_price': entry_price,
            'exit_price': None,
            'stop_loss': round(entry_price * 0.99, 2),
            'take_profit': round(entry_price * 1.02, 2),
            'quantity': quantity,
            'leverage': np.random.randint(5, 20),
            'confidence': round(np.random.uniform(0.55, 0.95), 4),
            'pnl': None,
            'pnl_pct': None,
            'close_reason': None,
            'won': None,
            
            # 五維評分
            'trend_alignment_score': round(np.random.uniform(0.5, 1.0), 4),
            'market_structure_score': round(np.random.uniform(0.5, 1.0), 4),
            'price_position_score': round(np.random.uniform(0.4, 1.0), 4),
            'momentum_score': round(np.random.uniform(0.3, 1.0), 4),
            'volatility_score': round(np.random.uniform(0.5, 1.0), 4),
            
            # 技術指標（開倉時）
            'rsi': round(np.random.uniform(30, 70), 2),
            'macd': round(np.random.uniform(-100, 100), 2),
            'atr': round(np.random.uniform(500, 1500), 2),
            'bb_width_pct': round(np.random.uniform(20, 80), 2),
            
            # Order Block 和流動性
            'order_blocks_count': np.random.randint(1, 5),
            'liquidity_zones_count': np.random.randint(0, 3),
            
            'holding_duration_minutes': None
        }
        
        # 平倉記錄
        close_event = {
            'event': 'CLOSE',
            'timestamp': exit_time.strftime('%Y-%m-%d %H:%M:%S'),
            'position_id': position_id,
            'is_virtual': is_virtual,
            'symbol': open_event['symbol'],
            'direction': open_event['direction'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'stop_loss': open_event['stop_loss'],
            'take_profit': open_event['take_profit'],
            'quantity': quantity,
            'leverage': open_event['leverage'],
            'confidence': open_event['confidence'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'close_reason': 'TAKE_PROFIT' if won else 'STOP_LOSS',
            'won': won,
            
            # 五維評分（與開倉時相同）
            'trend_alignment_score': open_event['trend_alignment_score'],
            'market_structure_score': open_event['market_structure_score'],
            'price_position_score': open_event['price_position_score'],
            'momentum_score': open_event['momentum_score'],
            'volatility_score': open_event['volatility_score'],
            
            # 技術指標（與開倉時相同）
            'rsi': open_event['rsi'],
            'macd': open_event['macd'],
            'atr': open_event['atr'],
            'bb_width_pct': open_event['bb_width_pct'],
            
            # Order Block 和流動性（與開倉時相同）
            'order_blocks_count': open_event['order_blocks_count'],
            'liquidity_zones_count': open_event['liquidity_zones_count'],
            
            'holding_duration_minutes': int((exit_time - entry_time).total_seconds() / 60)
        }
        
        positions.append(open_event)
        positions.append(close_event)
    
    return pd.DataFrame(positions)


def prepare_xgboost_training_data(signals_df, positions_df):
    """
    從信號和倉位數據準備 XGBoost 訓練數據集
    
    目標：預測信號是否會產生盈利
    """
    # 只使用被接受的信號
    accepted_signals = signals_df[signals_df['accepted'] == True].copy()
    
    # 獲取平倉記錄
    closed_positions = positions_df[positions_df['event'] == 'CLOSE'].copy()
    
    # 準備特徵
    feature_columns = [
        # 五維評分
        'trend_alignment_score',
        'market_structure_score',
        'price_position_score',
        'momentum_score',
        'volatility_score',
        
        # 總信心度
        'confidence',
        
        # 技術指標
        'rsi',
        'macd',
        'atr',
        'bb_width_pct',
        
        # Order Block
        'order_blocks_count',
        'liquidity_zones_count'
    ]
    
    # 創建訓練數據（使用平倉記錄）
    X = closed_positions[feature_columns].copy()
    y = closed_positions['won'].astype(int)  # 目標：是否盈利
    
    # 添加額外特徵
    X['risk_reward_ratio'] = (
        (closed_positions['take_profit'] - closed_positions['entry_price']) / 
        (closed_positions['entry_price'] - closed_positions['stop_loss'])
    ).abs()
    
    X['leverage'] = closed_positions['leverage']
    
    # 編碼分類特徵（如果需要）
    # 這裡可以添加 symbol, direction 等的編碼
    
    return X, y, closed_positions


def print_data_summary(signals_df, positions_df, X, y):
    """
    打印數據摘要
    """
    print("=" * 80)
    print("📊 XGBoost 訓練數據格式示例")
    print("=" * 80)
    print()
    
    # Signals 數據
    print("🎯 SIGNALS.CSV 數據格式")
    print("-" * 80)
    print(f"總信號數: {len(signals_df)}")
    print(f"被接受: {signals_df['accepted'].sum()} ({signals_df['accepted'].sum()/len(signals_df)*100:.1f}%)")
    print(f"被拒絕: {(~signals_df['accepted']).sum()} ({(~signals_df['accepted']).sum()/len(signals_df)*100:.1f}%)")
    print()
    print("數據示例（前 5 行）：")
    print(signals_df.head())
    print()
    print("列名稱：")
    print(signals_df.columns.tolist())
    print()
    
    # Positions 數據
    print("📈 POSITIONS.CSV 數據格式")
    print("-" * 80)
    print(f"總記錄數: {len(positions_df)}")
    print(f"開倉記錄: {(positions_df['event'] == 'OPEN').sum()}")
    print(f"平倉記錄: {(positions_df['event'] == 'CLOSE').sum()}")
    closed = positions_df[positions_df['event'] == 'CLOSE']
    if len(closed) > 0:
        print(f"盈利倉位: {closed['won'].sum()} ({closed['won'].sum()/len(closed)*100:.1f}%)")
        print(f"虧損倉位: {(~closed['won']).sum()} ({(~closed['won']).sum()/len(closed)*100:.1f}%)")
    print()
    print("數據示例（平倉記錄前 3 行）：")
    print(closed.head(3))
    print()
    
    # XGBoost 訓練數據
    print("🤖 XGBOOST 訓練數據集")
    print("-" * 80)
    print(f"樣本數: {len(X)}")
    print(f"特徵數: {len(X.columns)}")
    print(f"正樣本（盈利）: {y.sum()} ({y.sum()/len(y)*100:.1f}%)")
    print(f"負樣本（虧損）: {(~y).sum()} ({(~y).sum()/len(y)*100:.1f}%)")
    print()
    print("特徵列名：")
    print(X.columns.tolist())
    print()
    print("特徵矩陣 X（前 5 行）：")
    print(X.head())
    print()
    print("目標變量 y（前 20 個）：")
    print(y.head(20).values)
    print()
    
    # 統計信息
    print("📊 特徵統計信息")
    print("-" * 80)
    print(X.describe())
    print()


def demonstrate_xgboost_training(X, y):
    """
    演示如何使用這些數據訓練 XGBoost 模型
    """
    print("🚀 XGBOOST 訓練示例代碼")
    print("=" * 80)
    
    code = """
# 1. 導入必要的庫
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

# 2. 分割訓練集和測試集
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"訓練集大小: {len(X_train)}")
print(f"測試集大小: {len(X_test)}")

# 3. 創建 DMatrix（XGBoost 的數據格式）
dtrain = xgb.DMatrix(X_train, label=y_train)
dtest = xgb.DMatrix(X_test, label=y_test)

# 4. 設置 XGBoost 參數
params = {
    'objective': 'binary:logistic',  # 二分類
    'max_depth': 6,
    'learning_rate': 0.1,
    'n_estimators': 100,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'eval_metric': 'logloss',
    'random_state': 42
}

# 5. 訓練模型
print("\\n開始訓練 XGBoost 模型...")
model = xgb.train(
    params,
    dtrain,
    num_boost_round=100,
    evals=[(dtrain, 'train'), (dtest, 'test')],
    early_stopping_rounds=10,
    verbose_eval=10
)

# 6. 預測
y_pred_proba = model.predict(dtest)
y_pred = (y_pred_proba > 0.5).astype(int)

# 7. 評估
accuracy = accuracy_score(y_test, y_pred)
print(f"\\n測試集準確率: {accuracy:.4f}")
print("\\n分類報告:")
print(classification_report(y_test, y_pred, target_names=['虧損', '盈利']))

# 8. 特徵重要性
importance = model.get_score(importance_type='weight')
print("\\n特徵重要性:")
for feature, score in sorted(importance.items(), key=lambda x: x[1], reverse=True):
    print(f"  {feature}: {score}")

# 9. 保存模型
model.save_model('xgboost_trading_model.json')
print("\\n模型已保存到: xgboost_trading_model.json")

# 10. 使用模型預測新信號
def predict_signal_quality(signal_features):
    \"\"\"
    預測信號的獲勝概率
    
    Args:
        signal_features: dict，包含所有特徵的字典
    
    Returns:
        float: 獲勝概率 (0-1)
    \"\"\"
    # 轉換為 DataFrame
    import pandas as pd
    X_new = pd.DataFrame([signal_features])
    
    # 創建 DMatrix
    dnew = xgb.DMatrix(X_new)
    
    # 預測
    win_probability = model.predict(dnew)[0]
    
    return win_probability

# 示例：預測新信號
new_signal = {
    'trend_alignment_score': 0.85,
    'market_structure_score': 0.90,
    'price_position_score': 0.75,
    'momentum_score': 0.70,
    'volatility_score': 0.80,
    'confidence': 0.82,
    'rsi': 55,
    'macd': 50,
    'atr': 800,
    'bb_width_pct': 45,
    'order_blocks_count': 3,
    'liquidity_zones_count': 2,
    'risk_reward_ratio': 2.5,
    'leverage': 10
}

win_prob = predict_signal_quality(new_signal)
print(f"\\n新信號獲勝概率: {win_prob:.2%}")

if win_prob > 0.65:
    print("✅ 建議接受此信號")
elif win_prob > 0.50:
    print("⚠️  信號質量中等，謹慎考慮")
else:
    print("❌ 建議拒絕此信號")
"""
    
    print(code)
    print()


if __name__ == "__main__":
    # 生成示例數據
    print("正在生成示例數據...")
    signals_df = generate_sample_signals_data()
    positions_df = generate_sample_positions_data()
    
    # 準備 XGBoost 訓練數據
    X, y, closed_positions = prepare_xgboost_training_data(signals_df, positions_df)
    
    # 打印數據摘要
    print_data_summary(signals_df, positions_df, X, y)
    
    # 演示訓練代碼
    demonstrate_xgboost_training(X, y)
    
    # 保存示例數據
    print("💾 保存示例數據到文件...")
    signals_df.to_csv('example_signals.csv', index=False)
    positions_df.to_csv('example_positions.csv', index=False)
    
    # 保存訓練數據
    training_df = X.copy()
    training_df['won'] = y
    training_df.to_csv('example_xgboost_training.csv', index=False)
    
    print("✅ 數據已保存:")
    print("   - example_signals.csv (信號數據)")
    print("   - example_positions.csv (倉位數據)")
    print("   - example_xgboost_training.csv (XGBoost 訓練數據)")
    print()
    print("=" * 80)
    print("🎉 示例完成！")
    print("=" * 80)
