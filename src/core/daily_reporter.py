"""
v3.17+ 每日報告生成器
生成 JSON + Markdown 報告，並輸出到 Railway Logs
"""

from src.utils.logger_factory import get_logger
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

logger = get_logger(__name__)


class DailyReporter:
    """
    每日報告生成器（v3.17+）
    
    職責：
    1. 收集交易統計數據
    2. 調用 ModelRatingEngine 計算評分
    3. 生成 JSON + Markdown 報告
    4. 輸出到 stdout（供 Railway Logs）
    5. 保存到 /reports/daily/
    """
    
    def __init__(
        self,
        config_profile,
        model_rating_engine,
        trade_recorder=None
    ):
        """
        初始化報告生成器
        
        Args:
            config_profile: config manager instance
            model_rating_engine: ModelRatingEngine 實例
            trade_recorder: TradeRecorder 實例（可選）
        """
        self.config = config_profile
        self.rating_engine = model_rating_engine
        self.trade_recorder = trade_recorder
        
        # 確保報告目錄存在
        self.reports_dir = Path(self.config.reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("✅ 每日報告生成器初始化完成（v3.17+）")
        logger.info(f"   📁 報告目錄: {self.reports_dir}")
    
    async def generate_daily_report(
        self,
        period_days: int = 1,
        output_stdout: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        生成每日報告
        
        Args:
            period_days: 統計週期（天）
            output_stdout: 是否輸出到 stdout
            
        Returns:
            報告數據字典
        """
        try:
            # 1. 收集交易數據
            trades = await self._collect_trades(period_days)
            
            if not trades:
                logger.warning(f"⚠️ 過去 {period_days} 天無交易記錄")
                return None
            
            # 2. 計算統計數據
            stats = self._calculate_statistics(trades)
            
            # 3. 計算模型評分
            rating = self.rating_engine.calculate_rating(trades, period_days)
            
            # 4. 構建報告數據
            report_data = {
                'report_date': datetime.now().isoformat(),
                'period_days': period_days,
                'model_rating': rating,
                'statistics': stats,
                'trades': trades,
                'version': 'v3.17+',
            }
            
            # 5. 保存報告
            json_path = await self._save_json_report(report_data)
            md_path = await self._save_markdown_report(report_data)
            
            # 6. 輸出到 stdout（供 Railway Logs）
            if output_stdout:
                self._print_to_stdout(report_data, rating)
            
            logger.info(f"✅ 每日報告生成完成: {json_path}, {md_path}")
            
            return report_data
            
        except Exception as e:
            logger.error(f"❌ 生成報告失敗: {e}", exc_info=True)
            return None
    
    async def _collect_trades(self, period_days: int) -> List[Dict[str, Any]]:
        """收集交易記錄"""
        if not self.trade_recorder:
            logger.warning("⚠️ 無 TradeRecorder，使用模擬數據")
            return []
        
        try:
            trades = self.trade_recorder.get_recent_trades(days=period_days)
            return trades
        except Exception as e:
            logger.error(f"❌ 收集交易數據失敗: {e}")
            return []
    
    def _calculate_statistics(self, trades: List[Dict]) -> Dict[str, Any]:
        """計算統計數據"""
        if not trades:
            return {}
        
        total_trades = len(trades)
        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        losses = total_trades - wins
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        avg_win = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0) / wins if wins > 0 else 0
        avg_loss = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0) / losses if losses > 0 else 0
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': f"{win_rate:.2%}",
            'total_pnl': f"${total_pnl:.2f}",
            'avg_win': f"${avg_win:.2f}",
            'avg_loss': f"${avg_loss:.2f}",
        }
    
    async def _save_json_report(self, report_data: Dict[str, Any]) -> Path:
        """保存 JSON 報告"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"model_report_{date_str}.json"
        filepath = self.reports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        # 同時保存為 latest_report.json（方便訪問）
        latest_path = self.reports_dir / "latest_report.json"
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    async def _save_markdown_report(self, report_data: Dict[str, Any]) -> Path:
        """保存 Markdown 報告"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"model_report_{date_str}.md"
        filepath = self.reports_dir / filename
        
        md_content = self._generate_markdown(report_data)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        return filepath
    
    def _generate_markdown(self, report_data: Dict[str, Any]) -> str:
        """生成 Markdown 格式報告"""
        rating = report_data.get('model_rating', {})
        stats = report_data.get('statistics', {})
        
        score = rating.get('final_score', 0)
        grade = rating.get('grade', 'N/A')
        recommendation = self.rating_engine.get_recommendation(grade)
        
        md = f"""# 📊 SelfLearningTrader v3.17+ 每日報告

**生成時間**: {report_data['report_date']}  
**統計週期**: {report_data['period_days']} 天

---

## 🏆 模型評分

**最終評分**: {score:.2f} / 100  
**等級**: {grade}  
**建議**: {recommendation}

### 📈 評分細節

| 維度 | 分數 | 權重 |
|------|------|------|
| R:R 比率 | {rating['component_scores']['rr_ratio']:.2f} | 25% |
| 勝率 | {rating['component_scores']['win_rate']:.2f} | 20% |
| 期望值 | {rating['component_scores']['expected_value']:.2f} | 20% |
| 最大回撤 | {rating['component_scores']['max_drawdown']:.2f} | 15% |
| Sharpe 比率 | {rating['component_scores']['sharpe_ratio']:.2f} | 10% |
| 交易頻率 | {rating['component_scores']['trade_frequency']:.2f} | 10% |

**原始分數**: {rating['raw_score']:.2f}  
**100% 虧損懲罰**: -{rating['loss_penalty']:.2f} 分 ({rating['total_100_losses']} 筆)

---

## 📊 交易統計

- **總交易數**: {stats.get('total_trades', 0)}
- **勝場**: {stats.get('wins', 0)}
- **敗場**: {stats.get('losses', 0)}
- **勝率**: {stats.get('win_rate', 'N/A')}
- **總 P&L**: {stats.get('total_pnl', 'N/A')}
- **平均盈利**: {stats.get('avg_win', 'N/A')}
- **平均虧損**: {stats.get('avg_loss', 'N/A')}

---

## 🎯 行動建議

"""
        
        if grade == "S":
            md += "✅ **加倉**: 模型表現優異，建議增加倉位規模\n"
        elif grade == "A":
            md += "✅ **維持**: 模型表現良好，繼續當前策略\n"
        elif grade == "B":
            md += "⚠️ **觀察**: 模型表現一般，密切監控後續表現\n"
        elif grade == "C":
            md += "🚨 **降級**: 模型表現不佳，建議切換到純規則模式\n"
        else:
            md += "📊 **數據不足**: 無法提供建議\n"
        
        md += "\n---\n\n*報告由 SelfLearningTrader v3.17+ 自動生成*\n"
        
        return md
    
    def _print_to_stdout(self, report_data: Dict[str, Any], rating: Dict[str, Any]):
        """輸出到 stdout（供 Railway Logs 捕獲）"""
        score = rating.get('final_score', 0)
        grade = rating.get('grade', 'N/A')
        stats = report_data.get('statistics', {})
        
        print("\n" + "=" * 60)
        print("[MODEL_EVALUATOR] 📊 每日報告")
        print("=" * 60)
        print(f"✅ 評分: {score:.2f}/100 (等級: {grade})")
        print(f"📊 交易: {stats.get('total_trades', 0)} 筆 | 勝率: {stats.get('win_rate', 'N/A')}")
        print(f"💰 P&L: {stats.get('total_pnl', 'N/A')}")
        print(f"🚨 100% 虧損: {rating['total_100_losses']} 筆 (懲罰: -{rating['loss_penalty']:.2f} 分)")
        print(f"🎯 建議: {self.rating_engine.get_recommendation(grade)}")
        print("=" * 60 + "\n")
