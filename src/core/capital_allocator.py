"""
CapitalAllocator v3.23+ - 動態預算池 + 質量加權分配 + 安全驗證
職責：
1. 計算信號質量分數（勝率^0.4 × 信心值^0.4 × 報酬率^0.2）
2. 競價排名（按分數降序排列）
3. 動態預算池分配（高分優先，預算耗盡拒絕）
4. 單倉上限強制執行（≤50%帳戶權益）
5. 🔥 v3.23+: 多層次安全驗證（除零、NaN、邊界條件）
6. 🔥 v3.23+: 集成 ExceptionHandler 統一異常處理
"""

import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass

from src.config import Config
from src.core.safety_validator import SafetyValidator, ValidationError
from src.core.margin_safety_controller import MarginSafetyController
from src.core.exception_handler import ExceptionHandler

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
    資金分配器（v3.23+ 動態預算池 + 安全驗證）
    
    核心理念：
    - 競價排名：質量分數越高，越優先分配資金
    - 🔥 v3.23+: 多層次安全驗證，防止數學錯誤和邊界條件異常
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
        🔥 v3.23+ 初始化資金分配器（新增安全驗證）
        
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
        
        self.margin_controller = MarginSafetyController(
            warning_threshold=0.80,
            critical_threshold=0.90,
            lock_threshold=0.95
        )
        logger.info("🔒 保證金安全控制器已啟用（v3.23+）")
        
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
    
    @ExceptionHandler.critical_section(max_retries=2, backoff_base=1.0)
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
        
        # ===== 步驟0：安全驗證 =====
        try:
            available_margin = SafetyValidator.validate_budget(
                available_margin, 
                "available_margin in allocate_capital"
            )
        except ValidationError as e:
            logger.error(f"❌ 可用保證金驗證失敗: {e}")
            return []
        
        # ===== 步驟1：計算質量分數並過濾 + 槓桿驗證 =====
        scored_signals: List[Tuple[Dict, float]] = []
        
        for signal in signals:
            symbol = signal.get('symbol', 'UNKNOWN')
            
            try:
                leverage = SafetyValidator.validate_leverage(
                    signal.get('leverage', 1.0), 
                    symbol
                )
                signal['leverage'] = leverage
            except ValidationError as e:
                logger.error(f"❌ 信號驗證失敗，拒絕 {symbol}: {e}")
                continue
            
            score = calculate_signal_score(signal, self.config)
            
            if score >= self.quality_threshold:
                scored_signals.append((signal, score))
            else:
                logger.debug(
                    f"💰 質量不足，拒絕信號 {symbol} | "
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
        
        # ===== 步驟3：初始化預算 + 保證金安全控制 =====
        total_budget = available_margin * self.config.MAX_TOTAL_BUDGET_RATIO
        max_single_budget = self.total_account_equity * self.config.MAX_SINGLE_POSITION_RATIO
        
        max_allowed_total_margin = self.total_balance * self.config.MAX_TOTAL_MARGIN_RATIO
        
        margin_health = self.margin_controller.check_margin_health(
            self.total_margin, 
            max_allowed_total_margin
        )
        
        total_budget = self.margin_controller.apply_budget_protection(
            total_budget, 
            margin_health
        )
        
        if total_budget <= 0:
            logger.warning("⚠️ 預算為0，無法分配資金")
            return []
        
        remaining_budget = total_budget
        
        logger.info(
            f"💰 預算池初始化 | "
            f"總預算: ${total_budget:.2f} ({self.config.MAX_TOTAL_BUDGET_RATIO:.0%} × ${available_margin:.2f}) | "
            f"單倉上限: ${max_single_budget:.2f} ({self.config.MAX_SINGLE_POSITION_RATIO:.0%} × ${self.total_account_equity:.2f}) | "
            f"保證金狀態: {margin_health.status}"
        )
        
        # ===== 步驟4：動態分配 + total_score驗證 =====
        allocated_signals = []
        total_score = sum(score for _, score in scored_signals)
        
        try:
            total_score = SafetyValidator.validate_total_score(
                total_score, 
                len(scored_signals)
            )
        except ValidationError as e:
            logger.error(f"{e}")
            logger.error(f"   信號列表: {[s.get('symbol') for s, _ in scored_signals]}")
            logger.error(f"   分數列表: {[score for _, score in scored_signals]}")
            return []
        
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
            allocation_ratio = SafetyValidator.safe_division(
                score, 
                total_score, 
                context=f"allocation_ratio for {symbol}",
                default=0.0
            )
            theoretical_budget = total_budget * allocation_ratio
            
            # 計算單倉上限（使用SafetyValidator防止除零）
            max_budget_for_leverage = SafetyValidator.safe_division(
                max_single_budget, 
                leverage, 
                context=f"max_budget_for_leverage for {symbol}",
                default=max_single_budget
            )
            
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
