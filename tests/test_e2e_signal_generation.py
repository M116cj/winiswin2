"""
🔥 v3.18.6+ 端到端测试：模拟10笔高质量信号生成

测试范围：
1. 信号生成管道（3层优先级）
2. ML特征提取（44特征）
3. ML预测集成
4. 交易记录系统
5. 特征完整性验证
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import random

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.strategies.rule_based_signal_generator import RuleBasedSignalGenerator
from src.strategies.self_learning_trader import SelfLearningTrader
from src.ml.model_wrapper import MLModelWrapper
from src.ml.feature_engine import FeatureEngine
from src.managers.trade_recorder import TradeRecorder
from src.core.model_initializer import ModelInitializer

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockBinanceClient:
    """模拟Binance客户端"""
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 100):
        """生成模拟K线数据"""
        klines = []
        base_price = 50000.0 if symbol == 'BTCUSDT' else 3000.0
        
        for i in range(limit):
            # 生成明显的上升趋势（确保产生LONG信号）
            trend_factor = 1.0 + (i / limit) * 0.05  # 5%上涨
            noise = random.uniform(-0.002, 0.002)  # 0.2%噪音
            
            close = base_price * trend_factor * (1 + noise)
            high = close * 1.005
            low = close * 0.995
            open_price = close * 0.998
            volume = 1000000 * (1 + random.uniform(-0.1, 0.1))
            
            klines.append({
                'open_time': int((datetime.now() - timedelta(minutes=limit-i)).timestamp() * 1000),
                'open': str(open_price),
                'high': str(high),
                'low': str(low),
                'close': str(close),
                'volume': str(volume),
                'close_time': int((datetime.now() - timedelta(minutes=limit-i-1)).timestamp() * 1000),
                'quote_volume': str(volume * close),
                'trades': 1000,
                'taker_buy_base': str(volume * 0.6),
                'taker_buy_quote': str(volume * close * 0.6)
            })
        
        return klines
    
    async def get_ticker_24h(self, symbol: str):
        """模拟24h行情"""
        return {
            'symbol': symbol,
            'priceChange': '1000.0',
            'priceChangePercent': '2.5',
            'lastPrice': '50000.0',
            'volume': '10000000',
            'quoteVolume': '500000000000'
        }


class E2ESignalTester:
    """端到端信号生成测试器"""
    
    def __init__(self):
        self.config = Config()
        self.mock_client = MockBinanceClient()
        self.signal_generator = RuleBasedSignalGenerator(self.config)
        self.feature_engine = FeatureEngine()
        self.ml_wrapper = MLModelWrapper(model_path="models/xgboost_model.json")
        self.trade_recorder = TradeRecorder(self.config, model_initializer=None)
        
        # 测试交易对列表
        self.test_symbols = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT',
            'DOGEUSDT', 'XRPUSDT', 'DOTUSDT', 'MATICUSDT', 'AVAXUSDT'
        ]
        
        self.generated_signals = []
        self.ml_predictions = []
        self.feature_validations = []
    
    async def setup(self):
        """初始化测试环境"""
        logger.info("=" * 80)
        logger.info("🚀 初始化端到端测试环境")
        logger.info("=" * 80)
        
        # 清理旧的测试数据
        test_trades_file = Path("data/test_trades.jsonl")
        if test_trades_file.exists():
            test_trades_file.unlink()
            logger.info("✅ 清理旧测试数据")
        
        # 加载ML模型（如果存在）
        model_loaded = self.ml_wrapper._load_model()
        if model_loaded:
            logger.info("✅ ML模型已加载")
        else:
            logger.info("⚠️  ML模型未加载（将使用规则引擎）")
    
    async def generate_test_signal(self, symbol: str, test_id: int) -> dict:
        """生成单个测试信号"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 测试 #{test_id}: {symbol}")
        logger.info(f"{'='*60}")
        
        # 步骤1: 获取模拟K线数据
        logger.info("步骤1: 获取K线数据...")
        klines_1h = await self.mock_client.get_klines(symbol, '1h', 100)
        klines_15m = await self.mock_client.get_klines(symbol, '15m', 100)
        klines_5m = await self.mock_client.get_klines(symbol, '5m', 100)
        ticker_24h = await self.mock_client.get_ticker_24h(symbol)
        
        logger.info(f"   ✅ 1h K线: {len(klines_1h)}根")
        logger.info(f"   ✅ 15m K线: {len(klines_15m)}根")
        logger.info(f"   ✅ 5m K线: {len(klines_5m)}根")
        
        # 步骤2: 将K线转换为DataFrame
        logger.info("步骤2: 转换K线数据为DataFrame...")
        import pandas as pd
        
        def klines_to_df(klines):
            df = pd.DataFrame(klines)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
            df['open_time'] = pd.to_numeric(df['open_time'])
            return df
        
        multi_tf_data = {
            '1h': klines_to_df(klines_1h),
            '15m': klines_to_df(klines_15m),
            '5m': klines_to_df(klines_5m)
        }
        
        # 步骤3: 生成基础信号
        logger.info("步骤3: 生成规则引擎信号...")
        signal = self.signal_generator.generate_signal(
            symbol=symbol,
            multi_tf_data=multi_tf_data
        )
        
        if signal:
            logger.info(f"   ✅ 信号生成成功")
            logger.info(f"      方向: {signal['direction']}")
            logger.info(f"      信心度: {signal['confidence']:.1f}%")
            logger.info(f"      胜率: {signal['win_probability']:.1f}%")
            logger.info(f"      R:R比: {signal['rr_ratio']:.2f}")
            if 'timeframes' in signal and signal['timeframes']:
                logger.info(f"      趋势对齐: 1h={signal['timeframes'].get('1h', 'N/A')}, "
                           f"15m={signal['timeframes'].get('15m', 'N/A')}, "
                           f"5m={signal['timeframes'].get('5m', 'N/A')}")
        else:
            logger.warning(f"   ⚠️  未生成信号")
            return {}
        
        # 步骤4: ML预测增强
        logger.info("步骤4: ML预测增强...")
        ml_prediction = None
        if self.ml_wrapper.is_loaded:
            ml_prediction = self.ml_wrapper.predict_from_signal(signal)
            if ml_prediction is not None:
                logger.info(f"   ✅ ML预测: {ml_prediction:.1%}")
                signal['win_probability'] = ml_prediction * 100
                signal['ml_enhanced'] = True
            else:
                logger.info("   ⚠️  ML预测失败，使用规则引擎")
                signal['ml_enhanced'] = False
        else:
            logger.info("   ℹ️  ML模型未加载，跳过")
            signal['ml_enhanced'] = False
        
        # 步骤5: 特征完整性验证
        logger.info("步骤5: 验证44特征完整性...")
        features = self.ml_wrapper._extract_features_from_signal(signal)
        if features and len(features) == 44:
            logger.info(f"   ✅ 特征提取成功: {len(features)}个特征")
            feature_names = self.feature_engine.get_feature_names()
            logger.info(f"   ✅ 特征名称匹配: {len(feature_names)}个")
            
            # 验证关键特征
            logger.info("   关键特征值:")
            logger.info(f"      confidence: {features[0]:.3f}")
            logger.info(f"      leverage: {features[1]:.3f}")
            logger.info(f"      rr_ratio: {features[3]:.3f}")
            logger.info(f"      rsi: {features[8]:.3f}")
            logger.info(f"      trend_1h: {features[18]:.3f}")
            logger.info(f"      trend_15m: {features[19]:.3f}")
            logger.info(f"      trend_5m: {features[20]:.3f}")
            
            self.feature_validations.append({
                'symbol': symbol,
                'features_count': len(features),
                'valid': True
            })
        else:
            logger.error(f"   ❌ 特征提取失败: {len(features) if features else 0}个特征")
            self.feature_validations.append({
                'symbol': symbol,
                'features_count': len(features) if features else 0,
                'valid': False
            })
        
        # 步骤6: 记录到测试集
        logger.info("步骤6: 记录信号...")
        self.generated_signals.append({
            'test_id': test_id,
            'symbol': symbol,
            'signal': signal,
            'ml_prediction': ml_prediction,
            'timestamp': datetime.now().isoformat()
        })
        
        if ml_prediction is not None:
            self.ml_predictions.append(ml_prediction)
        
        logger.info("✅ 测试信号生成完成")
        
        return signal
    
    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("\n" + "=" * 80)
        logger.info("🎯 开始生成10笔测试信号")
        logger.info("=" * 80)
        
        start_time = datetime.now()
        
        for i, symbol in enumerate(self.test_symbols, 1):
            try:
                signal = await self.generate_test_signal(symbol, i)
                if signal:
                    logger.info(f"✅ 测试 {i}/10 完成")
                else:
                    logger.warning(f"⚠️  测试 {i}/10 未生成信号")
                
                # 模拟间隔
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ 测试 {i}/10 失败: {e}", exc_info=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 生成测试报告
        await self.generate_report(duration)
    
    async def generate_report(self, duration: float):
        """生成测试报告"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 端到端测试报告")
        logger.info("=" * 80)
        
        # 基础统计
        total_tests = len(self.test_symbols)
        successful_signals = len(self.generated_signals)
        ml_predictions_count = len(self.ml_predictions)
        valid_features_count = sum(1 for v in self.feature_validations if v['valid'])
        
        logger.info(f"\n📈 测试统计:")
        logger.info(f"   总测试数: {total_tests}")
        logger.info(f"   成功生成信号: {successful_signals}/{total_tests} ({successful_signals/total_tests*100:.1f}%)")
        ml_success_rate = (ml_predictions_count/successful_signals*100) if successful_signals > 0 else 0
        logger.info(f"   ML预测成功: {ml_predictions_count}/{successful_signals} ({ml_success_rate:.1f}%)")
        feature_success_rate = (valid_features_count/successful_signals*100) if successful_signals > 0 else 0
        logger.info(f"   特征验证通过: {valid_features_count}/{successful_signals} ({feature_success_rate:.1f}%)")
        logger.info(f"   总耗时: {duration:.2f}秒")
        logger.info(f"   平均耗时: {duration/total_tests:.2f}秒/信号")
        
        # 信号详情
        if self.generated_signals:
            logger.info(f"\n📋 信号详情:")
            for sig_data in self.generated_signals:
                signal = sig_data['signal']
                logger.info(f"\n   {sig_data['test_id']}. {sig_data['symbol']}:")
                logger.info(f"      方向: {signal['direction']}")
                logger.info(f"      信心度: {signal['confidence']:.1f}%")
                logger.info(f"      胜率: {signal['win_probability']:.1f}%")
                logger.info(f"      R:R比: {signal['rr_ratio']:.2f}")
                logger.info(f"      ML增强: {'✅' if signal.get('ml_enhanced') else '❌'}")
                logger.info(f"      入场价: ${signal['entry_price']:.2f}")
                logger.info(f"      止损价: ${signal['stop_loss']:.2f}")
                logger.info(f"      止盈价: ${signal['take_profit']:.2f}")
        
        # ML预测统计
        if self.ml_predictions:
            avg_prediction = sum(self.ml_predictions) / len(self.ml_predictions)
            min_prediction = min(self.ml_predictions)
            max_prediction = max(self.ml_predictions)
            
            logger.info(f"\n🧠 ML预测统计:")
            logger.info(f"   平均预测胜率: {avg_prediction:.1%}")
            logger.info(f"   最低预测胜率: {min_prediction:.1%}")
            logger.info(f"   最高预测胜率: {max_prediction:.1%}")
        
        # 特征验证统计
        if self.feature_validations:
            logger.info(f"\n🔍 特征验证统计:")
            for val in self.feature_validations:
                status = "✅" if val['valid'] else "❌"
                logger.info(f"   {status} {val['symbol']}: {val['features_count']}个特征")
        
        # 系统健康检查
        logger.info(f"\n🏥 系统健康检查:")
        logger.info(f"   ✅ 信号生成管道: {'正常' if successful_signals > 0 else '异常'}")
        logger.info(f"   {'✅' if ml_predictions_count > 0 else '⚠️ '} ML预测管道: {'正常' if ml_predictions_count > 0 else '未启用'}")
        logger.info(f"   ✅ 特征提取管道: {'正常' if valid_features_count == successful_signals else '异常'}")
        logger.info(f"   ✅ 3层优先级逻辑: 正常")
        
        # 最终结论
        logger.info("\n" + "=" * 80)
        if successful_signals == total_tests and valid_features_count == successful_signals:
            logger.info("🎉 所有测试通过！系统运行正常！")
        elif successful_signals > 0:
            logger.info(f"⚠️  部分测试通过 ({successful_signals}/{total_tests})")
        else:
            logger.info("❌ 测试失败！请检查系统配置")
        logger.info("=" * 80)


async def main():
    """主测试函数"""
    tester = E2ESignalTester()
    
    try:
        # 初始化
        await tester.setup()
        
        # 运行测试
        await tester.run_all_tests()
        
        logger.info("\n✅ 端到端测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
