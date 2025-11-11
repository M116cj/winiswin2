#!/usr/bin/env python3
"""
🔍 优化验证脚本 v4.1
验证所有ML优化是否正确实施
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def validate_optimizations():
    """验证所有优化实施"""
    logger.info("=" * 70)
    logger.info("🔍 开始验证所有优化...")
    logger.info("=" * 70)
    
    all_passed = True
    
    # ========== STEP 1: 验证 XGBoost 参数 ==========
    logger.info("\n📊 STEP 1: 验证 XGBoost 参数优化")
    try:
        from src.core.model_initializer import ModelInitializer
        
        # 创建实例（不需要真实客户端）
        initializer = ModelInitializer()
        params = initializer.training_params
        
        # 验证关键参数
        checks = {
            'n_estimators': (params['n_estimators'], 30, "树数量应为30"),
            'max_depth': (params['max_depth'], 3, "树深度应为3"),
            'min_child_weight': (params['min_child_weight'], 50, "最小子节点权重应为50（兼容200样本）"),
            'gamma': (params['gamma'], 0.2, "Gamma应为0.2"),
            'subsample': (params['subsample'], 0.6, "Subsample应为0.6"),
            'colsample_bytree': (params['colsample_bytree'], 0.6, "Colsample应为0.6"),
            'learning_rate': (params['learning_rate'], 0.05, "学习率应为0.05"),
        }
        
        step1_passed = True
        for param_name, (actual, expected, msg) in checks.items():
            if actual == expected:
                logger.info(f"   ✅ {param_name}: {actual} (正确)")
            else:
                logger.error(f"   ❌ {param_name}: {actual} != {expected} ({msg})")
                step1_passed = False
        
        if step1_passed:
            logger.info("✅ STEP 1: XGBoost参数优化 - 通过")
        else:
            logger.error("❌ STEP 1: XGBoost参数优化 - 失败")
            all_passed = False
            
    except Exception as e:
        logger.error(f"❌ STEP 1验证失败: {e}")
        all_passed = False
    
    # ========== STEP 2: 验证 Bootstrap 渐进式阈值 ==========
    logger.info("\n📊 STEP 2: 验证 Bootstrap 渐进式阈值")
    try:
        from src.strategies.self_learning_trader import SelfLearningTrader
        from src.config import Config
        
        # 创建实例（模拟）
        trader = SelfLearningTrader(config=Config)
        
        # 测试渐进式阈值
        test_cases = [
            (1, 'phase_1', 0.35, 0.30, 2.0),
            (15, 'phase_1', 0.35, 0.30, 2.0),
            (16, 'phase_2', 0.40, 0.35, 3.0),
            (35, 'phase_2', 0.40, 0.35, 3.0),
            (36, 'phase_3', 0.43, 0.38, 4.0),
            (50, 'phase_3', 0.43, 0.38, 4.0),
            (100, 'normal', 0.45, 0.40, None),
        ]
        
        step2_passed = True
        logger.info("   测试用例:")
        for trade_count, expected_phase, expected_win, expected_conf, expected_lev in test_cases:
            thresholds = trader._get_progressive_bootstrap_thresholds(trade_count)
            
            if (thresholds['phase'] == expected_phase and
                thresholds['min_win_probability'] == expected_win and
                thresholds['min_confidence'] == expected_conf and
                thresholds['max_leverage'] == expected_lev):
                logger.info(
                    f"   ✅ 交易{trade_count}: {expected_phase} | "
                    f"胜率={expected_win:.0%}, 信心={expected_conf:.0%}, "
                    f"杠杆≤{expected_lev if expected_lev else '动态'}"
                )
            else:
                logger.error(
                    f"   ❌ 交易{trade_count}: 期望{expected_phase}, "
                    f"实际{thresholds['phase']}"
                )
                step2_passed = False
        
        if step2_passed:
            logger.info("✅ STEP 2: Bootstrap渐进式阈值 - 通过")
        else:
            logger.error("❌ STEP 2: Bootstrap渐进式阈值 - 失败")
            all_passed = False
            
    except Exception as e:
        logger.error(f"❌ STEP 2验证失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # ========== STEP 3: 验证信号质量公式 ==========
    logger.info("\n📊 STEP 3: 验证信号质量公式平衡")
    try:
        from src.strategies.self_learning_trader import SelfLearningTrader
        from src.config import Config
        
        trader = SelfLearningTrader(config=Config)
        
        # 测试用例：验证低预测能力+高RR不应该主导
        test_cases = [
            {
                'name': '高预测+高RR',
                'signal': {'confidence': 80, 'win_probability': 70, 'rr_ratio': 3.0},
                'expected_range': (65, 80),  # 应该很高
            },
            {
                'name': '低预测+极高RR',
                'signal': {'confidence': 40, 'win_probability': 40, 'rr_ratio': 5.0},
                'expected_range': (20, 45),  # 不应该过高（修复RR主导）
            },
            {
                'name': '优秀预测+低RR',
                'signal': {'confidence': 90, 'win_probability': 90, 'rr_ratio': 1.0},
                'expected_range': (65, 75),  # 预测能力应主导
            },
        ]
        
        step3_passed = True
        logger.info("   测试用例:")
        for case in test_cases:
            quality = trader._evaluate_signal_quality(case['signal'])
            min_expected, max_expected = case['expected_range']
            
            if min_expected <= quality <= max_expected:
                logger.info(
                    f"   ✅ {case['name']}: 质量={quality:.1f} "
                    f"(期望范围 {min_expected}-{max_expected})"
                )
            else:
                logger.error(
                    f"   ❌ {case['name']}: 质量={quality:.1f} "
                    f"(超出期望范围 {min_expected}-{max_expected})"
                )
                step3_passed = False
        
        # 关键测试：低预测+高RR应该 < 50
        low_pred_high_rr = trader._evaluate_signal_quality(
            {'confidence': 40, 'win_probability': 40, 'rr_ratio': 5.0}
        )
        if low_pred_high_rr < 50:
            logger.info(f"   ✅ 关键验证: 低预测+高RR={low_pred_high_rr:.1f} < 50 (不再RR主导)")
        else:
            logger.error(f"   ❌ 关键验证: 低预测+高RR={low_pred_high_rr:.1f} >= 50 (仍然RR主导)")
            step3_passed = False
        
        if step3_passed:
            logger.info("✅ STEP 3: 信号质量公式平衡 - 通过")
        else:
            logger.error("❌ STEP 3: 信号质量公式平衡 - 失败")
            all_passed = False
            
    except Exception as e:
        logger.error(f"❌ STEP 3验证失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # ========== 最终结果 ==========
    logger.info("\n" + "=" * 70)
    if all_passed:
        logger.info("🎉 所有优化验证通过！")
        logger.info("=" * 70)
        logger.info("\n📋 优化总结:")
        logger.info("   ✅ XGBoost复杂度降低 (30树/深度3/min_weight50)")
        logger.info("   ✅ Bootstrap渐进式阈值 (35%→40%→43%→45%)")
        logger.info("   ✅ Bootstrap渐进式杠杆 (2x→3x→4x→动态)")
        logger.info("   ✅ 信号质量公式平衡 (70%预测+30%RR)")
        logger.info("\n🚀 系统已优化完成，可以重启workflow测试")
        return 0
    else:
        logger.error("❌ 部分优化验证失败")
        logger.error("=" * 70)
        logger.error("\n请检查上述错误并修复")
        return 1


if __name__ == '__main__':
    exit_code = validate_optimizations()
    sys.exit(exit_code)
