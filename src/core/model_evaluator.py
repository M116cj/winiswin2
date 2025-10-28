"""
ModelEvaluator v3.17+ - 100 分制模型評級系統
職責：評估交易模型性能、生成每日報告、輸出 Railway 日誌
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class ModelEvaluator:
    """
    ModelEvaluator v3.17+ - 100 分制評級系統
    
    評分公式：
    1. R:R 比率（20分）
    2. 勝率（20分）
    3. 期望值 EV（20分）
    4. 最大回撤 MDD（15分）
    5. Sharpe 比率（15分）
    6. 交易頻率（10分）
    7. 100% 虧損懲罰（每次 -15分）
    
    評級等級：
    - S 級（90-100）：加倉
    - A 級（80-89）：維持
    - B 級（70-79）：觀察
    - C 級（<70）：降級至純規則模式
    """
    
    def __init__(self, config=None, reports_dir: str = "reports/daily"):
        """
        初始化 ModelEvaluator
        
        Args:
            config: 配置對象
            reports_dir: 報告目錄
        """
        self.config = config
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # 評分權重
        self.weights = {
            'rr_ratio': 20.0,
            'win_rate': 20.0,
            'expected_value': 20.0,
            'max_drawdown': 15.0,
            'sharpe_ratio': 15.0,
            'trade_frequency': 10.0
        }
        
        # 100% 虧損懲罰
        self.loss_penalty_per_trade = 15.0
        
        logger.info("=" * 80)
        logger.info("✅ ModelEvaluator v3.17+ 初始化完成")
        logger.info("   📊 評分系統: 6 大維度 + 100% 虧損懲罰")
        logger.info(f"   📁 報告目錄: {self.reports_dir}")
        logger.info("=" * 80)
    
    def evaluate_model(
        self,
        trades: List[Dict],
        period_days: int = 1
    ) -> Dict:
        """
        評估模型性能（100 分制）
        
        Args:
            trades: 交易記錄列表
            period_days: 評估週期（天）
        
        Returns:
            評估報告字典
        """
        try:
            if not trades:
                logger.warning("⚠️ 無交易記錄，無法評估")
                return self._generate_empty_report()
            
            # 計算統計數據
            stats = self._calculate_statistics(trades)
            
            # 計算各維度分數
            scores = self._calculate_dimension_scores(stats)
            
            # 計算 100% 虧損懲罰
            total_100_loss = stats['total_100_loss']
            loss_penalty = total_100_loss * self.loss_penalty_per_trade
            
            # 計算總分
            raw_score = sum(scores.values())
            final_score = max(0, min(100, raw_score - loss_penalty))
            
            # 確定評級
            grade, action = self._determine_grade(final_score)
            
            # 構建報告
            report = {
                'timestamp': datetime.now().isoformat(),
                'period_days': period_days,
                'total_trades': len(trades),
                'statistics': stats,
                'dimension_scores': scores,
                'raw_score': raw_score,
                'loss_penalty': loss_penalty,
                'final_score': final_score,
                'grade': grade,
                'action': action,
                'evaluation_details': self._generate_evaluation_details(
                    stats, scores, final_score, grade, action
                )
            }
            
            # 輸出 Railway 日誌
            self._log_to_railway(report)
            
            return report
            
        except Exception as e:
            logger.error(f"❌ 模型評估失敗: {e}", exc_info=True)
            return self._generate_empty_report()
    
    def _calculate_statistics(self, trades: List[Dict]) -> Dict:
        """
        計算交易統計數據
        
        Args:
            trades: 交易記錄列表
        
        Returns:
            統計數據字典
        """
        total_trades = len(trades)
        
        # 過濾已完成交易
        closed_trades = [t for t in trades if t.get('status') == 'closed']
        
        if not closed_trades:
            return self._generate_empty_statistics()
        
        # 盈虧數據
        pnls = [t.get('pnl', 0) for t in closed_trades]
        total_pnl = sum(pnls)
        avg_pnl = total_pnl / len(closed_trades)
        
        # 勝率計算
        winning_trades = [t for t in closed_trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in closed_trades if t.get('pnl', 0) <= 0]
        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0.0
        
        # R:R 計算
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0.0
        avg_loss = abs(np.mean([t['pnl'] for t in losing_trades])) if losing_trades else 1.0
        rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
        
        # 期望值（EV）
        expected_value = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        # 最大回撤（MDD）
        cumulative_pnl = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative_pnl)
        drawdown = running_max - cumulative_pnl
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0
        max_drawdown_pct = (max_drawdown / abs(total_pnl)) if total_pnl != 0 else 0.0
        
        # Sharpe 比率（假設無風險利率 = 0）
        pnl_std = np.std(pnls) if len(pnls) > 1 else 1.0
        sharpe_ratio = (avg_pnl / pnl_std) if pnl_std > 0 else 0.0
        
        # 交易頻率（每天交易次數）
        if closed_trades:
            first_trade_time = closed_trades[0].get('entry_time', datetime.now())
            last_trade_time = closed_trades[-1].get('exit_time', datetime.now())
            
            if isinstance(first_trade_time, str):
                first_trade_time = datetime.fromisoformat(first_trade_time)
            if isinstance(last_trade_time, str):
                last_trade_time = datetime.fromisoformat(last_trade_time)
            
            days = max(1, (last_trade_time - first_trade_time).days + 1)
            trade_frequency = len(closed_trades) / days
        else:
            trade_frequency = 0.0
        
        # 🚨 100% 虧損統計（PnL ≤ -99% 初始風險）
        total_100_loss = sum(
            1 for t in closed_trades
            if t.get('pnl', 0) <= -t.get('risk_amount', 0) * 0.99
        )
        
        return {
            'total_trades': total_trades,
            'closed_trades': len(closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'rr_ratio': rr_ratio,
            'expected_value': expected_value,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio': sharpe_ratio,
            'trade_frequency': trade_frequency,
            'total_100_loss': total_100_loss
        }
    
    def _calculate_dimension_scores(self, stats: Dict) -> Dict:
        """
        計算各維度分數
        
        Args:
            stats: 統計數據
        
        Returns:
            各維度分數字典
        """
        scores = {}
        
        # 1️⃣ R:R 比率（20 分）
        rr_ratio = stats['rr_ratio']
        if rr_ratio >= 2.5:
            scores['rr_ratio'] = 20.0
        elif rr_ratio >= 2.0:
            scores['rr_ratio'] = 18.0
        elif rr_ratio >= 1.5:
            scores['rr_ratio'] = 15.0
        elif rr_ratio >= 1.0:
            scores['rr_ratio'] = 10.0
        else:
            scores['rr_ratio'] = 5.0
        
        # 2️⃣ 勝率（20 分）
        win_rate = stats['win_rate']
        if win_rate >= 0.70:
            scores['win_rate'] = 20.0
        elif win_rate >= 0.65:
            scores['win_rate'] = 18.0
        elif win_rate >= 0.60:
            scores['win_rate'] = 15.0
        elif win_rate >= 0.55:
            scores['win_rate'] = 12.0
        elif win_rate >= 0.50:
            scores['win_rate'] = 8.0
        else:
            scores['win_rate'] = 4.0
        
        # 3️⃣ 期望值（20 分）
        ev = stats['expected_value']
        if ev >= 10.0:
            scores['expected_value'] = 20.0
        elif ev >= 5.0:
            scores['expected_value'] = 16.0
        elif ev >= 2.0:
            scores['expected_value'] = 12.0
        elif ev >= 0.5:
            scores['expected_value'] = 8.0
        elif ev > 0:
            scores['expected_value'] = 4.0
        else:
            scores['expected_value'] = 0.0
        
        # 4️⃣ 最大回撤（15 分）
        mdd_pct = stats['max_drawdown_pct']
        if mdd_pct <= 0.10:  # ≤10%
            scores['max_drawdown'] = 15.0
        elif mdd_pct <= 0.20:  # ≤20%
            scores['max_drawdown'] = 12.0
        elif mdd_pct <= 0.30:  # ≤30%
            scores['max_drawdown'] = 8.0
        elif mdd_pct <= 0.50:  # ≤50%
            scores['max_drawdown'] = 4.0
        else:
            scores['max_drawdown'] = 0.0
        
        # 5️⃣ Sharpe 比率（15 分）
        sharpe = stats['sharpe_ratio']
        if sharpe >= 2.0:
            scores['sharpe_ratio'] = 15.0
        elif sharpe >= 1.5:
            scores['sharpe_ratio'] = 12.0
        elif sharpe >= 1.0:
            scores['sharpe_ratio'] = 9.0
        elif sharpe >= 0.5:
            scores['sharpe_ratio'] = 6.0
        else:
            scores['sharpe_ratio'] = 3.0
        
        # 6️⃣ 交易頻率（10 分）
        freq = stats['trade_frequency']
        if 2.0 <= freq <= 10.0:  # 每天 2-10 筆最佳
            scores['trade_frequency'] = 10.0
        elif 1.0 <= freq < 2.0 or 10.0 < freq <= 20.0:
            scores['trade_frequency'] = 7.0
        elif 0.5 <= freq < 1.0 or 20.0 < freq <= 30.0:
            scores['trade_frequency'] = 4.0
        else:
            scores['trade_frequency'] = 2.0
        
        return scores
    
    def _determine_grade(self, score: float) -> tuple:
        """
        確定評級等級和建議行動
        
        Args:
            score: 最終分數
        
        Returns:
            (grade, action)
        """
        if score >= 90:
            return 'S', '加倉（模型表現優異）'
        elif score >= 80:
            return 'A', '維持（模型表現良好）'
        elif score >= 70:
            return 'B', '觀察（模型表現一般）'
        else:
            return 'C', '降級至純規則模式（模型表現不佳）'
    
    def _generate_evaluation_details(
        self,
        stats: Dict,
        scores: Dict,
        final_score: float,
        grade: str,
        action: str
    ) -> str:
        """生成評估詳情文本"""
        details = []
        details.append(f"=== 模型評級報告 ===")
        details.append(f"最終分數: {final_score:.1f}/100 | 等級: {grade} | 建議: {action}")
        details.append("")
        details.append("📊 統計數據:")
        details.append(f"  總交易數: {stats['total_trades']}")
        details.append(f"  勝率: {stats['win_rate']:.2%}")
        details.append(f"  R:R 比率: {stats['rr_ratio']:.2f}")
        details.append(f"  總盈虧: ${stats['total_pnl']:.2f}")
        details.append(f"  期望值: ${stats['expected_value']:.2f}")
        details.append(f"  最大回撤: ${stats['max_drawdown']:.2f} ({stats['max_drawdown_pct']:.2%})")
        details.append(f"  Sharpe 比率: {stats['sharpe_ratio']:.2f}")
        details.append(f"  交易頻率: {stats['trade_frequency']:.2f} 筆/天")
        details.append(f"  🚨 100% 虧損次數: {stats['total_100_loss']}")
        details.append("")
        details.append("📈 各維度分數:")
        for dim, score in scores.items():
            details.append(f"  {dim}: {score:.1f}")
        
        return "\n".join(details)
    
    def _log_to_railway(self, report: Dict):
        """輸出到 Railway 日誌"""
        logger.info("=" * 80)
        logger.info("[MODEL_EVALUATOR] 📊 每日模型評估報告")
        logger.info(f"[MODEL_EVALUATOR] ✅ 評分: {report['final_score']:.1f}/100 | "
                   f"等級: {report['grade']} | "
                   f"P&L: ${report['statistics']['total_pnl']:.2f}")
        logger.info(f"[MODEL_EVALUATOR] 📈 勝率: {report['statistics']['win_rate']:.2%} | "
                   f"R:R: {report['statistics']['rr_ratio']:.2f} | "
                   f"EV: ${report['statistics']['expected_value']:.2f}")
        logger.info(f"[MODEL_EVALUATOR] 🚨 100% 虧損: {report['statistics']['total_100_loss']} 次 | "
                   f"懲罰: -{report['loss_penalty']:.1f} 分")
        logger.info(f"[MODEL_EVALUATOR] 💡 建議行動: {report['action']}")
        logger.info("=" * 80)
    
    def _generate_empty_report(self) -> Dict:
        """生成空報告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'period_days': 0,
            'total_trades': 0,
            'statistics': self._generate_empty_statistics(),
            'dimension_scores': {},
            'raw_score': 0.0,
            'loss_penalty': 0.0,
            'final_score': 0.0,
            'grade': 'N/A',
            'action': '無交易記錄',
            'evaluation_details': '無交易記錄，無法評估'
        }
    
    def _generate_empty_statistics(self) -> Dict:
        """生成空統計數據"""
        return {
            'total_trades': 0,
            'closed_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'avg_pnl': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'rr_ratio': 0.0,
            'expected_value': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_pct': 0.0,
            'sharpe_ratio': 0.0,
            'trade_frequency': 0.0,
            'total_100_loss': 0
        }
    
    def generate_daily_report(
        self,
        trades: List[Dict],
        save_json: bool = True,
        save_markdown: bool = True
    ) -> Optional[Dict]:
        """
        生成每日報告並保存
        
        Args:
            trades: 交易記錄列表
            save_json: 是否保存 JSON 格式
            save_markdown: 是否保存 Markdown 格式
        
        Returns:
            報告字典
        """
        try:
            # 評估模型
            report = self.evaluate_model(trades, period_days=1)
            
            # 保存 JSON
            if save_json:
                today = datetime.now().strftime("%Y-%m-%d")
                json_path = self.reports_dir / f"model_report_{today}.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                logger.info(f"✅ JSON 報告已保存: {json_path}")
                
                # 保存最新報告
                latest_path = self.reports_dir / "latest_report.json"
                with open(latest_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
            
            # 保存 Markdown
            if save_markdown:
                today = datetime.now().strftime("%Y-%m-%d")
                md_path = self.reports_dir / f"model_report_{today}.md"
                markdown_content = self._generate_markdown_report(report)
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                logger.info(f"✅ Markdown 報告已保存: {md_path}")
            
            return report
            
        except Exception as e:
            logger.error(f"❌ 生成每日報告失敗: {e}", exc_info=True)
            return None
    
    def _generate_markdown_report(self, report: Dict) -> str:
        """生成 Markdown 格式報告"""
        md = []
        md.append(f"# 模型評級報告 - {datetime.now().strftime('%Y-%m-%d')}\n")
        md.append(f"## 📊 總覽\n")
        md.append(f"- **最終分數**: {report['final_score']:.1f}/100")
        md.append(f"- **評級**: {report['grade']}")
        md.append(f"- **建議行動**: {report['action']}\n")
        
        stats = report['statistics']
        md.append(f"## 📈 統計數據\n")
        md.append(f"| 指標 | 數值 |")
        md.append(f"|------|------|")
        md.append(f"| 總交易數 | {stats['total_trades']} |")
        md.append(f"| 勝率 | {stats['win_rate']:.2%} |")
        md.append(f"| R:R 比率 | {stats['rr_ratio']:.2f} |")
        md.append(f"| 總盈虧 | ${stats['total_pnl']:.2f} |")
        md.append(f"| 期望值 | ${stats['expected_value']:.2f} |")
        md.append(f"| 最大回撤 | ${stats['max_drawdown']:.2f} ({stats['max_drawdown_pct']:.2%}) |")
        md.append(f"| Sharpe 比率 | {stats['sharpe_ratio']:.2f} |")
        md.append(f"| 交易頻率 | {stats['trade_frequency']:.2f} 筆/天 |")
        md.append(f"| 🚨 100% 虧損 | {stats['total_100_loss']} 次 |\n")
        
        md.append(f"## 🎯 各維度分數\n")
        md.append(f"| 維度 | 分數 | 權重 |")
        md.append(f"|------|------|------|")
        for dim, score in report['dimension_scores'].items():
            weight = self.weights.get(dim, 0)
            md.append(f"| {dim} | {score:.1f} | {weight:.0f}% |")
        md.append(f"| **原始總分** | {report['raw_score']:.1f} | 100% |")
        md.append(f"| **100% 虧損懲罰** | -{report['loss_penalty']:.1f} | - |")
        md.append(f"| **最終分數** | {report['final_score']:.1f} | - |\n")
        
        return "\n".join(md)
    
    def analyze_feature_importance(self, model, feature_engine=None):
        """
        分析特徵重要性並動態調整（v3.17.10+）
        
        解決「特徵漂移」問題：
        - 市場變化導致某些特徵失效（如 RSI 在 trending 市失效）
        - 模型自動聚焦於當前市場有效的特徵
        
        Args:
            model: XGBoost 模型實例（必須有 feature_importances_ 屬性）
            feature_engine: 特徵工程引擎（用於獲取特徵名稱）
        
        Returns:
            特徵重要性字典
        """
        try:
            # 檢查模型是否有特徵重要性屬性
            if not hasattr(model, 'feature_importances_'):
                logger.warning("⚠️ 模型沒有 feature_importances_ 屬性")
                return {}
            
            importance = model.feature_importances_
            
            # 獲取特徵名稱
            if feature_engine and hasattr(feature_engine, 'get_feature_names'):
                feature_names = feature_engine.get_feature_names()
            else:
                # 使用默認特徵名稱（41個）
                feature_names = [
                    # 基本特徵 (8)
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
                    
                    # 競價上下文特徵 (3) - v3.17.10+
                    'competition_rank', 'score_gap_to_best', 'num_competing_signals'
                ]
            
            # 確保特徵數量匹配
            if len(feature_names) != len(importance):
                logger.warning(
                    f"⚠️ 特徵數量不匹配: feature_names={len(feature_names)} "
                    f"vs importance={len(importance)}"
                )
                # 使用索引作為特徵名稱
                feature_names = [f"feature_{i}" for i in range(len(importance))]
            
            # 記錄重要性到日誌（輸出到 Railway Logs）
            logger.info("=" * 80)
            logger.info("[FEATURE_IMPORTANCE] 📊 特徵重要性分析（v3.17.10+）")
            logger.info("=" * 80)
            
            # 排序特徵（從高到低）
            sorted_features = sorted(
                zip(feature_names, importance),
                key=lambda x: x[1],
                reverse=True
            )
            
            # 記錄前 15 名重要特徵
            logger.info("🔝 TOP 15 重要特徵:")
            for i, (name, imp) in enumerate(sorted_features[:15], 1):
                logger.info(f"  {i:2d}. {name:25s}: {imp:.4f}")
                print(f"[FEATURE_IMPORTANCE] {name}: {imp:.4f}")
            
            # 動態調整特徵權重（用於下輪訓練）
            low_importance_features = [
                name for name, imp in zip(feature_names, importance)
                if imp < 0.01  # 低於 1% 重要性
            ]
            
            if low_importance_features:
                logger.warning("=" * 80)
                logger.warning(f"⚠️ 低重要性特徵（<1%）: {len(low_importance_features)} 個")
                logger.warning(f"⚠️ 建議考慮移除: {low_importance_features}")
                logger.warning("=" * 80)
            else:
                logger.info("✅ 所有特徵都有顯著貢獻（>=1%）")
            
            logger.info("=" * 80)
            
            # 返回特徵重要性字典
            feature_importance_dict = dict(zip(feature_names, importance.tolist()))
            
            return feature_importance_dict
            
        except Exception as e:
            logger.error(f"❌ 分析特徵重要性失敗: {e}", exc_info=True)
            return {}
