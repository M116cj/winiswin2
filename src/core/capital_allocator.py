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
    
    參數處理：
        - 勝率：使用原始值，限制在[0, 1]（不強制拉升到MIN_WIN_PROBABILITY）
        - 信心值：使用原始值，限制在[0, 1]（不強制拉升到MIN_CONFIDENCE）
        - 報酬率：限制在[0, config.MAX_RR_RATIO]
    
    **重要**：此函數不進行質量過濾，僅計算分數。
              低品質信號應該產生低分數並被allocate_capital過濾掉。
    
    Args:
        signal: 交易信號（dict格式，包含win_probability, confidence, rr_ratio）
        config: 配置對象
    
    Returns:
        質量分數（0-1之間的浮點數）
    """
    # 提取原始參數（不拉升）
    win_rate = signal.get('win_probability', 0.55)
    confidence = signal.get('confidence', 0.5)
    rr_ratio = signal.get('rr_ratio', 1.0)
    
    # 僅進行邊界保護，不強制拉升
    # 勝率和信心值限制在[0, 1]
    win_rate = max(0.0, min(1.0, win_rate))
    confidence = max(0.0, min(1.0, confidence))
    
    # 報酬率限制在[0, MAX_RR_RATIO]
    rr_ratio = max(0.0, min(config.MAX_RR_RATIO, rr_ratio))
    
    # 計算質量分數（加權幾何平均）
    score = (win_rate ** 0.4) * (confidence ** 0.4) * (rr_ratio ** 0.2)
    
    # 最終分數限制在[0, 1]（防止rr_ratio較大時分數超過1）
    score = min(1.0, score)
    
    return score


class CapitalAllocator:
    """
    資金分配器（v3.18.7+ 動態預算池版本 + 豁免期質量門檻）
    
    核心理念：
    - 競價排名：質量分數越高，越優先分配資金
    - 動態預算池：高分信號優先扣減預算，預算耗盡拒絕低分信號
    - 單倉上限：單個倉位不超過帳戶權益的50%
    - 總預算控制：使用可用保證金的80%
    - 🔥 v3.18.7+ 豁免期質量門檻：前100筆使用0.4，第101筆起使用0.6
    """
    
    def __init__(
        self,
        config: Config,
        total_account_equity: float,
        total_balance: float = 0.0,
        total_margin: float = 0.0,
        total_trades: int = 0
    ):
        """
        初始化資金分配器
        
        Args:
            config: 配置對象
            total_account_equity: 帳戶總權益（用於單倉上限檢查）
            total_balance: 帳戶總金額（不含浮盈浮虧，用於90%上限檢查）
            total_margin: 已佔用保證金（用於90%上限檢查）
            total_trades: 已完成交易數（用於豁免期判斷，v3.18.7+）
        """
        self.config = config
        self.total_account_equity = total_account_equity
        self.total_balance = total_balance
        self.total_margin = total_margin
        self.total_trades = total_trades
        
        # 🔥 v3.18.7+ 動態質量門檻（豁免期0.25，正常期0.40）
        if total_trades < config.BOOTSTRAP_TRADE_LIMIT:
            self.quality_threshold = config.BOOTSTRAP_SIGNAL_QUALITY_THRESHOLD
            threshold_mode = f"豁免期模式（交易數:{total_trades}/{config.BOOTSTRAP_TRADE_LIMIT}）"
            progress_pct = (total_trades / config.BOOTSTRAP_TRADE_LIMIT) * 100
        else:
            self.quality_threshold = config.SIGNAL_QUALITY_THRESHOLD
            threshold_mode = f"正常模式（交易數:{total_trades}≥{config.BOOTSTRAP_TRADE_LIMIT}）"
            progress_pct = 100.0
        
        logger.info(
            f"💰 CapitalAllocator初始化 | "
            f"帳戶權益: ${total_account_equity:.2f} | "
            f"總金額: ${total_balance:.2f} | "
            f"已佔用保證金: ${total_margin:.2f}"
        )
        logger.info(
            f"🎯 質量門檻: {self.quality_threshold:.2%} | "
            f"模式: {threshold_mode} | "
            f"進度: {progress_pct:.1f}%"
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
            
            # 🔥 v3.18.7+ 使用動態質量門檻（豁免期0.4，正常期0.6）
            if score >= self.quality_threshold:
                scored_signals.append((signal, score))
            else:
                logger.debug(
                    f"💰 質量不足，拒絕信號 {signal.get('symbol', 'UNKNOWN')} | "
                    f"分數: {score:.3f} < 門檻: {self.quality_threshold:.3f}"
                )
        
        if not scored_signals:
            logger.info(
                f"💰 所有信號質量不足（門檻: {self.quality_threshold:.3f}），"
                f"無信號獲批"
            )
            return []
        
        # ===== 步驟2：按分數降序排序（競價排名）=====
        scored_signals.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(
            f"💰 質量排名完成：{len(scored_signals)}/{len(signals)} 信號通過質量門檻 | "
            f"最高分: {scored_signals[0][1]:.3f} | 最低分: {scored_signals[-1][1]:.3f}"
        )
        
        # ===== 步驟3：初始化預算（含90%總倉位保證金上限檢查）=====
        total_budget = available_margin * self.config.MAX_TOTAL_BUDGET_RATIO
        max_single_budget = self.total_account_equity * self.config.MAX_SINGLE_POSITION_RATIO
        
        # 🔥 v3.18+ 優化：90%總倉位保證金上限檢查（渐进式削減）
        # 計算還能使用的保證金空間（帳戶總金額×90% - 已佔用保證金）
        max_allowed_total_margin = self.total_balance * self.config.MAX_TOTAL_MARGIN_RATIO
        remaining_margin_space = max(0, max_allowed_total_margin - self.total_margin)
        margin_usage_ratio = self.total_margin / self.total_balance if self.total_balance > 0 else 0
        
        # 🔥 v3.23+ 修復：渐进式削減預算（避免直接清零）
        if remaining_margin_space < total_budget:
            # 計算超出部分
            excess_margin = self.total_margin - max_allowed_total_margin
            
            if excess_margin > 0:
                # 已經超出上限：根據超出程度削減預算
                # 超出越多，削減越多（1.5倍懲罰）
                budget_reduction = min(total_budget, excess_margin * 1.5)
                adjusted_budget = max(0, total_budget - budget_reduction)
                
                logger.warning(
                    f"⚠️ 保證金超出90%上限 | "
                    f"使用率: {margin_usage_ratio:.1%} > {self.config.MAX_TOTAL_MARGIN_RATIO:.0%} | "
                    f"原預算: ${total_budget:.2f} → 削減: ${adjusted_budget:.2f} | "
                    f"超出: ${excess_margin:.2f} | "
                    f"已佔用: ${self.total_margin:.2f} / 上限: ${max_allowed_total_margin:.2f}"
                )
            else:
                # 接近但未超出上限：使用剩餘空間
                adjusted_budget = remaining_margin_space
                
                logger.warning(
                    f"⚠️ 接近90%保證金上限 | "
                    f"使用率: {margin_usage_ratio:.1%} | "
                    f"原預算: ${total_budget:.2f} → 調整為: ${adjusted_budget:.2f} | "
                    f"剩餘空間: ${remaining_margin_space:.2f}"
                )
            
            total_budget = adjusted_budget
        
        remaining_budget = total_budget
        
        logger.info(
            f"💰 預算池初始化 | "
            f"總預算: ${total_budget:.2f} ({self.config.MAX_TOTAL_BUDGET_RATIO:.0%} × ${available_margin:.2f}) | "
            f"單倉上限: ${max_single_budget:.2f} ({self.config.MAX_SINGLE_POSITION_RATIO:.0%} × ${self.total_account_equity:.2f}) | "
            f"總倉位保證金: ${self.total_margin:.2f} / ${max_allowed_total_margin:.2f} ({self.config.MAX_TOTAL_MARGIN_RATIO:.0%})"
        )
        
        # ===== 步驟4：動態分配（修正版：預算池扣減）=====
        allocated_signals = []
        total_score = sum(score for _, score in scored_signals)
        
        for rank, (signal, score) in enumerate(scored_signals, 1):
            symbol = signal.get('symbol', 'UNKNOWN')
            leverage = signal.get('leverage', 1.0)
            
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
            
            # 計算單倉上限（名義價值 = 保證金 × 槓桿）
            # 保證金上限 = 名義價值上限 / 槓桿
            max_budget_for_leverage = max_single_budget / leverage if leverage > 0 else max_single_budget
            
            # 應用單倉上限和剩餘預算限制
            actual_budget = min(theoretical_budget, max_budget_for_leverage, remaining_budget)
            
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
        
        # 🔥 v3.18+防禦性編程：避免除以零（當available_margin=0時）
        if total_budget > 0:
            logger.info(f"   總分配: ${total_allocated:.2f} / ${total_budget:.2f} ({total_allocated/total_budget:.1%})")
            logger.info(f"   剩餘預算: ${remaining_budget:.2f}")
            logger.info(f"   預算利用率: {(total_budget - remaining_budget) / total_budget:.1%}")
        else:
            logger.warning(f"   ⚠️ 無可用預算（available_margin=0，可能是帳戶餘額為0或API失敗）")
            logger.info(f"   總分配: $0.00 / $0.00")
            logger.info(f"   獲批信號將無法執行")
        
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
