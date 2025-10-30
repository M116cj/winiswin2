"""
CapitalAllocator v3.18+ - 動態預算池 + 質量加權分配
職責：
1. 計算信號質量分數（勝率^0.4 × 信心值^0.4 × 報酬率^0.2）
2. 競價排名（按分數降序排列）
3. 動態預算池分配（高分優先，預算耗盡拒絕）
4. 單倉上限強制執行（≤50%帳戶權益）
"""

import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass

from src.config import Config

logger = logging.getLogger(__name__)


@dataclass
class AllocatedSignal:
    """
    已分配資金的信號
    
    Attributes:
        signal: 原始交易信號（dict格式）
        allocated_budget: 分配的保證金（USDT）
        allocation_ratio: 分配比例（0-1）
        quality_score: 質量分數
    """
    signal: Dict
    allocated_budget: float
    allocation_ratio: float
    quality_score: float


def calculate_signal_score(signal: Dict, config: Config) -> float:
    """
    計算信號質量分數（v3.18+ 標準公式）
    
    公式：
        質量分數 = 勝率^0.4 × 信心值^0.4 × 報酬率^0.2
    
    參數規範化：
        - 勝率：min(config.MIN_WIN_PROBABILITY, signal['win_probability'])
        - 信心值：min(config.MIN_CONFIDENCE, signal['confidence'])
        - 報酬率：限制在[config.MIN_RR_RATIO, config.MAX_RR_RATIO]
    
    Args:
        signal: 交易信號（dict格式，包含win_probability, confidence, rr_ratio）
        config: 配置對象
    
    Returns:
        質量分數（0-1之間的浮點數）
    """
    # 提取並規範化參數
    win_rate = max(config.MIN_WIN_PROBABILITY, signal.get('win_probability', 0.55))
    confidence = max(config.MIN_CONFIDENCE, signal.get('confidence', 0.5))
    rr_ratio = signal.get('rr_ratio', 1.0)
    
    # 報酬率限制在合理範圍
    rr_ratio = max(
        config.MIN_RR_RATIO,
        min(config.MAX_RR_RATIO, rr_ratio)
    )
    
    # 計算質量分數（加權幾何平均）
    score = (win_rate ** 0.4) * (confidence ** 0.4) * (rr_ratio ** 0.2)
    
    return score


class CapitalAllocator:
    """
    資金分配器（v3.18+ 動態預算池版本）
    
    核心理念：
    - 競價排名：質量分數越高，越優先分配資金
    - 動態預算池：高分信號優先扣減預算，預算耗盡拒絕低分信號
    - 單倉上限：單個倉位不超過帳戶權益的50%
    - 總預算控制：使用可用保證金的80%
    """
    
    def __init__(self, config: Config, total_account_equity: float):
        """
        初始化資金分配器
        
        Args:
            config: 配置對象
            total_account_equity: 帳戶總權益（用於單倉上限檢查）
        """
        self.config = config
        self.total_account_equity = total_account_equity
        
        logger.debug(
            f"💰 CapitalAllocator初始化 | 帳戶權益: ${total_account_equity:.2f} | "
            f"單倉上限: {self.config.MAX_SINGLE_POSITION_RATIO:.0%}"
        )
    
    def allocate_capital(
        self,
        signals: List[Dict],
        available_margin: float
    ) -> List[AllocatedSignal]:
        """
        動態預算池分配（v3.18+ 修正版）
        
        流程：
        1. 計算質量分數 + 過濾低質量（< SIGNAL_QUALITY_THRESHOLD）
        2. 按分數降序排序（競價排名）
        3. 初始化預算池（總預算 = 可用保證金 × MAX_TOTAL_BUDGET_RATIO）
        4. 動態分配：
           - 理論分配 = 總預算 × (分數 / 總分數)
           - 實際分配 = min(理論分配, 單倉上限, 剩餘預算)
           - 預算扣減：remaining_budget -= actual_budget
        5. 預算耗盡 → 拒絕剩餘信號
        
        Args:
            signals: 交易信號列表（dict格式）
            available_margin: 可用保證金（USDT）
        
        Returns:
            已分配資金的信號列表（AllocatedSignal）
        """
        if not signals:
            logger.debug("💰 無信號需要分配資金")
            return []
        
        # ===== 步驟1：計算質量分數並過濾 =====
        scored_signals: List[Tuple[Dict, float]] = []
        
        for signal in signals:
            score = calculate_signal_score(signal, self.config)
            
            # 過濾低質量信號
            if score >= self.config.SIGNAL_QUALITY_THRESHOLD:
                scored_signals.append((signal, score))
            else:
                logger.debug(
                    f"💰 質量不足，拒絕信號 {signal.get('symbol', 'UNKNOWN')} | "
                    f"分數: {score:.3f} < 門檻: {self.config.SIGNAL_QUALITY_THRESHOLD:.3f}"
                )
        
        if not scored_signals:
            logger.info(
                f"💰 所有信號質量不足（門檻: {self.config.SIGNAL_QUALITY_THRESHOLD:.3f}），"
                f"無信號獲批"
            )
            return []
        
        # ===== 步驟2：按分數降序排序（競價排名）=====
        scored_signals.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(
            f"💰 質量排名完成：{len(scored_signals)}/{len(signals)} 信號通過質量門檻 | "
            f"最高分: {scored_signals[0][1]:.3f} | 最低分: {scored_signals[-1][1]:.3f}"
        )
        
        # ===== 步驟3：初始化預算 =====
        total_budget = available_margin * self.config.MAX_TOTAL_BUDGET_RATIO
        remaining_budget = total_budget
        max_single_budget = self.total_account_equity * self.config.MAX_SINGLE_POSITION_RATIO
        
        logger.info(
            f"💰 預算池初始化 | "
            f"總預算: ${total_budget:.2f} ({self.config.MAX_TOTAL_BUDGET_RATIO:.0%} × ${available_margin:.2f}) | "
            f"單倉上限: ${max_single_budget:.2f} ({self.config.MAX_SINGLE_POSITION_RATIO:.0%} × ${self.total_account_equity:.2f})"
        )
        
        # ===== 步驟4：動態分配（修正版：預算池扣減）=====
        allocated_signals = []
        total_score = sum(score for _, score in scored_signals)
        
        for rank, (signal, score) in enumerate(scored_signals, 1):
            symbol = signal.get('symbol', 'UNKNOWN')
            
            # 檢查預算是否耗盡
            if remaining_budget <= 0:
                logger.info(
                    f"💰 預算耗盡，拒絕剩餘 {len(scored_signals) - rank + 1} 個信號 "
                    f"（排名 {rank}-{len(scored_signals)}）"
                )
                break
            
            # 計算理論分配（基於質量分數比例）
            allocation_ratio = score / total_score
            theoretical_budget = total_budget * allocation_ratio
            
            # 應用單倉上限和剩餘預算限制
            actual_budget = min(theoretical_budget, max_single_budget, remaining_budget)
            
            if actual_budget > 0:
                allocated_signals.append(AllocatedSignal(
                    signal=signal,
                    allocated_budget=actual_budget,
                    allocation_ratio=allocation_ratio,
                    quality_score=score
                ))
                remaining_budget -= actual_budget
                
                logger.debug(
                    f"💰 排名 #{rank} | {symbol} | 分數: {score:.3f} | "
                    f"理論分配: ${theoretical_budget:.2f} | "
                    f"實際分配: ${actual_budget:.2f} | "
                    f"剩餘預算: ${remaining_budget:.2f}"
                )
            else:
                logger.debug(
                    f"💰 預算不足或單倉超限，拒絕信號 {symbol} | "
                    f"排名 #{rank} | 分數: {score:.3f}"
                )
        
        # ===== 最終報告 =====
        total_allocated = sum(a.allocated_budget for a in allocated_signals)
        logger.info("=" * 80)
        logger.info(f"✅ 資金分配完成")
        logger.info(f"   獲批信號: {len(allocated_signals)}/{len(scored_signals)} (通過質量門檻)")
        logger.info(f"   總分配: ${total_allocated:.2f} / ${total_budget:.2f} ({total_allocated/total_budget:.1%})")
        logger.info(f"   剩餘預算: ${remaining_budget:.2f}")
        logger.info(f"   預算利用率: {(total_budget - remaining_budget) / total_budget:.1%}")
        logger.info("=" * 80)
        
        return allocated_signals
    
    def get_allocation_summary(self, allocated_signals: List[AllocatedSignal]) -> Dict:
        """
        生成分配摘要報告
        
        Args:
            allocated_signals: 已分配信號列表
        
        Returns:
            包含統計信息的字典
        """
        if not allocated_signals:
            return {
                'total_signals': 0,
                'total_allocated': 0.0,
                'avg_allocation': 0.0,
                'max_allocation': 0.0,
                'min_allocation': 0.0
            }
        
        allocations = [a.allocated_budget for a in allocated_signals]
        
        return {
            'total_signals': len(allocated_signals),
            'total_allocated': sum(allocations),
            'avg_allocation': sum(allocations) / len(allocations),
            'max_allocation': max(allocations),
            'min_allocation': min(allocations),
            'avg_score': sum(a.quality_score for a in allocated_signals) / len(allocated_signals)
        }
