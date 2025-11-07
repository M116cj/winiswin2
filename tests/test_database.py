"""
Database System Tests
数据库系统测试
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import DatabaseManager, TradingDataService, initialize_database
from datetime import datetime


def test_database_connection():
    """测试数据库连接"""
    print("=" * 70)
    print("测试 1: 数据库连接")
    print("=" * 70)
    
    try:
        db_manager = DatabaseManager(
            min_connections=1,
            max_connections=5
        )
        
        # 健康检查
        is_healthy = db_manager.check_health()
        
        if is_healthy:
            print("✅ 数据库连接测试通过")
        else:
            print("❌ 数据库连接测试失败")
        
        return is_healthy
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_table_initialization(db_manager: DatabaseManager):
    """测试表初始化"""
    print("\n" + "=" * 70)
    print("测试 2: 数据表初始化")
    print("=" * 70)
    
    try:
        success = initialize_database(db_manager)
        
        if success:
            print("✅ 数据表初始化测试通过")
        else:
            print("❌ 数据表初始化测试失败")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_trade_operations(db_service: TradingDataService):
    """测试交易操作"""
    print("\n" + "=" * 70)
    print("测试 3: 交易记录操作")
    print("=" * 70)
    
    try:
        # 创建测试交易记录
        trade_data = {
            'symbol': 'BTCUSDT',
            'direction': 'LONG',
            'entry_price': 43250.50,
            'quantity': 0.1,
            'entry_timestamp': datetime.utcnow().isoformat() + 'Z',
            'leverage': 5,
            'confidence': 0.75,
            'win_probability': 0.70,
            'strategy': 'ICT_SMC_TEST',
            'position_value': 2162.53,
            'status': 'OPEN'
        }
        
        # 保存交易
        trade_id = db_service.save_trade(trade_data)
        
        if not trade_id:
            print("❌ 保存交易失败")
            return False
        
        print(f"✅ 交易已保存，ID: {trade_id}")
        
        # 获取交易历史
        trades = db_service.get_trade_history(symbol='BTCUSDT', limit=10)
        print(f"✅ 获取到 {len(trades)} 条交易记录")
        
        # 更新交易状态
        success = db_service.update_trade_status(
            trade_id=trade_id,
            status='CLOSED',
            exit_price=43680.20,
            pnl=42.97,
            pnl_pct=1.99
        )
        
        if success:
            print(f"✅ 交易 {trade_id} 状态已更新")
        else:
            print(f"❌ 更新交易状态失败")
            return False
        
        # 获取统计数据
        stats = db_service.get_statistics()
        print(f"✅ 统计数据: {stats}")
        
        print("✅ 交易操作测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ml_model_operations(db_service: TradingDataService):
    """测试ML模型操作"""
    print("\n" + "=" * 70)
    print("测试 4: ML模型操作")
    print("=" * 70)
    
    try:
        # 创建一个简单的测试模型（字典）
        test_model = {
            'type': 'XGBoost',
            'parameters': {'max_depth': 5, 'learning_rate': 0.1},
            'trained_at': datetime.utcnow().isoformat()
        }
        
        features = [
            'confidence', 'leverage', 'rsi', 'macd',
            'trend_1h', 'trend_15m', 'order_blocks_count'
        ]
        
        # 保存模型
        model_id = db_service.save_ml_model(
            model_name='test_model',
            model=test_model,
            features=features,
            accuracy=0.85,
            parameters={'description': 'Test model for database integration'},
            is_active=True
        )
        
        if not model_id:
            print("❌ 保存ML模型失败")
            return False
        
        print(f"✅ ML模型已保存，ID: {model_id}")
        
        # 加载模型
        loaded_model = db_service.load_ml_model('test_model')
        
        if loaded_model:
            print(f"✅ ML模型已加载: {loaded_model['type']}")
        else:
            print("❌ 加载ML模型失败")
            return False
        
        print("✅ ML模型操作测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("🧪 开始数据库系统测试")
    print("=" * 70)
    
    # 检查环境变量
    if not os.environ.get('DATABASE_URL') and not os.environ.get('DATABASE_PUBLIC_URL'):
        print("❌ 未找到数据库环境变量")
        print("   请设置 DATABASE_URL 或 DATABASE_PUBLIC_URL")
        return False
    
    # 测试1: 连接
    db_manager = None
    try:
        db_manager = DatabaseManager(min_connections=1, max_connections=5)
        if not test_database_connection():
            return False
    except Exception as e:
        print(f"❌ 无法创建数据库管理器: {e}")
        return False
    
    # 测试2: 表初始化
    if not test_table_initialization(db_manager):
        return False
    
    # 创建服务实例
    db_service = TradingDataService(db_manager)
    
    # 测试3: 交易操作
    if not test_trade_operations(db_service):
        return False
    
    # 测试4: ML模型操作
    if not test_ml_model_operations(db_service):
        return False
    
    # 清理
    db_manager.close_all_connections()
    
    print("\n" + "=" * 70)
    print("✅ 所有测试通过！")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
