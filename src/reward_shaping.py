"""
🎯 Reward Shaping - 獎懲機制系統
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

根據虛擬交易 ROI% 計算加權分數，訓練模型專注於高勝率交易。
非對稱評分：虧損扣分重，盈利加分輕。
"""

import logging

logger = logging.getLogger(__name__)


class RewardTiers:
    """獎懲等級定義"""
    
    # 盈利等級（ROI%）→ 分數
    PROFIT_TIERS = [
        (0.30, 1.0),      # ≤30% → +1分
        (0.50, 3.0),      # ≤50% → +3分
        (0.80, 5.0),      # ≤80% → +5分
        (float('inf'), 8.0)  # >80% → +8分
    ]
    
    # 虧損等級（ROI%）→ 分數
    LOSS_TIERS = [
        (0.30, -1.0),     # ≥-30% → -1分
        (0.50, -3.0),     # ≥-50% → -3分
        (0.80, -7.0),     # ≥-80% → -7分
        (float('inf'), -10.0)  # <-80% → -10分
    ]


def calculate_reward_score(roi_pct: float) -> float:
    """
    根據 ROI% 計算獎懲分數
    
    Args:
        roi_pct: ROI 百分比 (例如 0.15 表示 15%, -0.25 表示 -25%)
    
    Returns:
        獎懲分數 (-10.0 到 +8.0)
    """
    abs_roi = abs(roi_pct)
    
    if roi_pct >= 0:
        # 盈利情況
        for threshold, score in RewardTiers.PROFIT_TIERS:
            if abs_roi <= threshold:
                return score
        return 8.0  # 預設最高分
    else:
        # 虧損情況
        for threshold, score in RewardTiers.LOSS_TIERS:
            if abs_roi <= threshold:
                return score
        return -10.0  # 預設最低分


def get_sample_weight(reward_score: float) -> float:
    """
    將獎懲分數轉換為樣本權重（用於 ML 訓練）
    
    Args:
        reward_score: 獎懲分數
    
    Returns:
        樣本權重（絕對值，供訓練使用）
    """
    # 使用絕對值：高分數 = 高權重
    weight = abs(reward_score)
    
    # 確保權重在合理範圍
    # -10 分 → 10 倍權重（嚴重虧損，模型應高度注意）
    # +8 分 → 8 倍權重（大幅盈利，模型應學習）
    return max(0.1, min(weight, 10.0))


def get_label_from_score(reward_score: float) -> int:
    """
    將獎懲分數轉換為二元標籤
    
    Args:
        reward_score: 獎懲分數
    
    Returns:
        1 (盈利) 或 0 (虧損)
    """
    return 1 if reward_score > 0 else 0


# 測試範例
if __name__ == "__main__":
    test_cases = [
        0.15,    # 15% 盈利 → 應為 +1
        0.40,    # 40% 盈利 → 應為 +3
        0.65,    # 65% 盈利 → 應為 +5
        0.95,    # 95% 盈利 → 應為 +8
        -0.15,   # -15% 虧損 → 應為 -1
        -0.40,   # -40% 虧損 → 應為 -3
        -0.65,   # -65% 虧損 → 應為 -7
        -0.95,   # -95% 虧損 → 應為 -10
    ]
    
    for roi in test_cases:
        score = calculate_reward_score(roi)
        weight = get_sample_weight(score)
        label = get_label_from_score(score)
        print(f"ROI: {roi:+.1%} → Score: {score:+.1f} → Weight: {weight:.2f} → Label: {label}")
