"""
CapitalAllocator單元測試（v3.18+）

測試目標：
1. 質量分數計算正確性
2. 低品質信號過濾行為
3. 競價排名正確性
4. 預算池分配正確性
5. 單倉上限強制執行
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.capital_allocator import calculate_signal_score, CapitalAllocator, AllocatedSignal
from src.config import Config


class TestSignalScoreCalculation:
    """測試質量分數計算"""
    
    def test_high_quality_signal(self):
        """高品質信號應該產生高分數"""
        config = Config()
        signal = {
            'win_probability': 0.75,
            'confidence': 0.80,
            'rr_ratio': 2.5
        }
        
        score = calculate_signal_score(signal, config)
        
        # 預期分數：0.75^0.4 * 0.80^0.4 * 2.5^0.2 ≈ 0.945
        assert score > 0.9, f"高品質信號分數應該>0.9，實際：{score}"
    
    def test_low_quality_signal_not_lifted(self):
        """低品質信號不應該被拉升（Critical Test）"""
        config = Config()
        signal = {
            'win_probability': 0.40,  # 低於MIN_WIN_PROBABILITY(0.55)
            'confidence': 0.30,       # 低於MIN_CONFIDENCE(0.5)
            'rr_ratio': 1.0
        }
        
        score = calculate_signal_score(signal, config)
        
        # 預期分數：0.40^0.4 * 0.30^0.4 * 1.0^0.2 ≈ 0.392
        # 關鍵：應該 < SIGNAL_QUALITY_THRESHOLD(0.6)
        assert score < config.SIGNAL_QUALITY_THRESHOLD, \
            f"低品質信號分數應該<{config.SIGNAL_QUALITY_THRESHOLD}，實際：{score}"
        assert 0.35 < score < 0.45, f"分數異常：{score}"
    
    def test_medium_quality_signal(self):
        """中等品質信號應該產生中等分數"""
        config = Config()
        signal = {
            'win_probability': 0.60,
            'confidence': 0.55,
            'rr_ratio': 1.5
        }
        
        score = calculate_signal_score(signal, config)
        
        # 預期分數：0.60^0.4 * 0.55^0.4 * 1.5^0.2 ≈ 0.649
        assert 0.6 < score < 0.7, f"中等品質信號分數應該在0.6-0.7，實際：{score}"
    
    def test_boundary_clamping(self):
        """邊界保護測試"""
        config = Config()
        
        # 測試超出上界
        signal_high = {
            'win_probability': 1.5,  # 超過1.0
            'confidence': 2.0,       # 超過1.0
            'rr_ratio': 10.0         # 超過MAX_RR_RATIO(5.0)
        }
        score_high = calculate_signal_score(signal_high, config)
        assert score_high <= 1.0, "分數應該被限制在合理範圍"
        
        # 測試超出下界
        signal_low = {
            'win_probability': -0.1,  # 負數
            'confidence': -0.2,       # 負數
            'rr_ratio': -1.0          # 負數
        }
        score_low = calculate_signal_score(signal_low, config)
        assert score_low == 0.0, "負數參數應該產生0分數"


class TestQualityFiltering:
    """測試質量過濾行為"""
    
    def test_filter_low_quality_signals(self):
        """低品質信號應該被過濾掉（Core Functionality）"""
        config = Config()
        allocator = CapitalAllocator(config, total_account_equity=10000.0)
        
        signals = [
            {
                'symbol': 'HIGH_QUALITY',
                'win_probability': 0.75,
                'confidence': 0.80,
                'rr_ratio': 2.5,
                'entry_price': 100.0,
                'leverage': 10.0,
                'stop_loss': 98.0
            },
            {
                'symbol': 'LOW_QUALITY',
                'win_probability': 0.40,  # 低品質
                'confidence': 0.30,       # 低品質
                'rr_ratio': 1.0,
                'entry_price': 100.0,
                'leverage': 10.0,
                'stop_loss': 98.0
            }
        ]
        
        allocated = allocator.allocate_capital(signals, available_margin=5000.0)
        
        # 驗證只有高品質信號獲得資金
        assert len(allocated) == 1, f"應該只有1個信號獲得資金，實際：{len(allocated)}"
        assert allocated[0].signal['symbol'] == 'HIGH_QUALITY', "應該是高品質信號"
    
    def test_all_signals_below_threshold(self):
        """所有信號都低於閾值時，不應分配任何資金"""
        config = Config()
        allocator = CapitalAllocator(config, total_account_equity=10000.0)
        
        signals = [
            {
                'symbol': 'BAD1',
                'win_probability': 0.45,
                'confidence': 0.35,
                'rr_ratio': 1.0,
                'entry_price': 100.0,
                'leverage': 10.0,
                'stop_loss': 98.0
            },
            {
                'symbol': 'BAD2',
                'win_probability': 0.50,
                'confidence': 0.40,
                'rr_ratio': 1.0,
                'entry_price': 100.0,
                'leverage': 10.0,
                'stop_loss': 98.0
            }
        ]
        
        allocated = allocator.allocate_capital(signals, available_margin=5000.0)
        
        assert len(allocated) == 0, "低品質信號不應獲得任何資金"


class TestCompetitiveBidding:
    """測試競價排名"""
    
    def test_ranking_by_quality_score(self):
        """信號應該按質量分數降序排名"""
        config = Config()
        allocator = CapitalAllocator(config, total_account_equity=10000.0)
        
        signals = [
            {
                'symbol': 'MEDIUM',
                'win_probability': 0.65,
                'confidence': 0.60,
                'rr_ratio': 1.5,
                'entry_price': 100.0,
                'leverage': 10.0,
                'stop_loss': 98.0
            },
            {
                'symbol': 'BEST',
                'win_probability': 0.80,
                'confidence': 0.85,
                'rr_ratio': 3.0,
                'entry_price': 100.0,
                'leverage': 10.0,
                'stop_loss': 98.0
            },
            {
                'symbol': 'GOOD',
                'win_probability': 0.70,
                'confidence': 0.70,
                'rr_ratio': 2.0,
                'entry_price': 100.0,
                'leverage': 10.0,
                'stop_loss': 98.0
            }
        ]
        
        allocated = allocator.allocate_capital(signals, available_margin=5000.0)
        
        # 驗證排名順序：BEST > GOOD > MEDIUM
        assert len(allocated) == 3, "所有信號都應通過閾值"
        assert allocated[0].signal['symbol'] == 'BEST', "最高分應排第一"
        assert allocated[1].signal['symbol'] == 'GOOD', "次高分應排第二"
        assert allocated[2].signal['symbol'] == 'MEDIUM', "最低分應排第三"


class TestBudgetAllocation:
    """測試預算池分配"""
    
    def test_max_total_budget_ratio(self):
        """總分配不應超過可用保證金的80%"""
        config = Config()
        allocator = CapitalAllocator(config, total_account_equity=10000.0)
        
        signals = [
            {
                'symbol': f'SIGNAL_{i}',
                'win_probability': 0.70,
                'confidence': 0.70,
                'rr_ratio': 2.0,
                'entry_price': 100.0,
                'leverage': 10.0,
                'stop_loss': 98.0
            }
            for i in range(10)
        ]
        
        available_margin = 5000.0
        allocated = allocator.allocate_capital(signals, available_margin)
        
        total_allocated = sum(alloc.allocated_budget for alloc in allocated)
        max_allowed = available_margin * config.MAX_TOTAL_BUDGET_RATIO
        
        assert total_allocated <= max_allowed, \
            f"總分配{total_allocated}超過上限{max_allowed}"
    
    def test_single_position_cap(self):
        """單倉不應超過帳戶權益的50%"""
        config = Config()
        total_equity = 10000.0
        allocator = CapitalAllocator(config, total_account_equity=total_equity)
        
        signals = [
            {
                'symbol': 'HIGH_LEVERAGE',
                'win_probability': 0.80,
                'confidence': 0.85,
                'rr_ratio': 3.0,
                'entry_price': 100.0,
                'leverage': 100.0,  # 超高槓桿
                'stop_loss': 98.0
            }
        ]
        
        allocated = allocator.allocate_capital(signals, available_margin=8000.0)
        
        if allocated:
            max_single_cap = total_equity * config.MAX_SINGLE_POSITION_RATIO
            allocated_budget = allocated[0].allocated_budget
            
            # 計算名義價值
            notional_value = allocated_budget * signals[0]['leverage']
            
            assert notional_value <= max_single_cap, \
                f"單倉名義價值{notional_value}超過上限{max_single_cap}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
