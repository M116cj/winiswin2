"""
信號詳情專屬日誌系統 v3.17+
職責：將信號生成、槓桿計算、SL/TP調整等詳細信息記錄到專屬文件
與Railway主日誌分離，避免日誌污染
"""

import logging
import os
from datetime import datetime
from typing import Optional

class SignalDetailsLogger:
    """信號詳情專屬日誌器"""
    
    def __init__(self, log_dir: str = "data/logs"):
        """
        初始化信號詳情日誌器
        
        Args:
            log_dir: 日誌目錄
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # 創建專屬logger
        self.logger = logging.getLogger('signal_details')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  # 不傳播到root logger
        
        # 清除現有handlers（避免重複）
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # 創建文件handler
        log_file = os.path.join(log_dir, 'signal_details.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 設置格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
    
    def log_signal_generated(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        win_rate: float,
        rr_ratio: float
    ):
        """
        記錄信號生成詳情
        
        Args:
            symbol: 交易對
            direction: 方向（LONG/SHORT）
            confidence: 信心度
            win_rate: 勝率
            rr_ratio: 風險回報比
        """
        self.logger.info(
            f"✅ {symbol} 信號生成: {direction} | "
            f"信心度={confidence*100:.1f}% | "
            f"勝率={win_rate*100:.1f}% | "
            f"R:R={rr_ratio:.2f}"
        )
    
    def log_leverage_calculation(
        self,
        symbol: str,
        win_rate: float,
        confidence: float,
        win_leverage: float,
        conf_factor: float,
        final_leverage: float
    ):
        """
        記錄槓桿計算詳情
        
        Args:
            symbol: 交易對
            win_rate: 勝率
            confidence: 信心度
            win_leverage: 勝率槓桿
            conf_factor: 信心因子
            final_leverage: 最終槓桿
        """
        self.logger.info(
            f"📊 {symbol} 槓桿計算: "
            f"勝率={win_rate*100:.2f}% → win_leverage={win_leverage:.2f}x | "
            f"信心度={confidence*100:.2f}% → conf_factor={conf_factor:.2f}x | "
            f"最終槓桿={final_leverage:.2f}x"
        )
    
    def log_sltp_adjustment(
        self,
        symbol: str,
        leverage: float,
        scale: float,
        base_sl_pct: float,
        adjusted_sl_pct: float,
        sl_price: float,
        tp_price: float
    ):
        """
        記錄SL/TP調整詳情
        
        Args:
            symbol: 交易對
            leverage: 槓桿
            scale: 縮放因子
            base_sl_pct: 基礎止損百分比
            adjusted_sl_pct: 調整後止損百分比
            sl_price: 止損價格
            tp_price: 止盈價格
        """
        self.logger.info(
            f"🎯 {symbol} SL/TP調整: "
            f"槓桿={leverage:.1f}x → scale={scale:.2f}x | "
            f"基礎SL={base_sl_pct:.2f}% → 調整後={adjusted_sl_pct:.2f}% | "
            f"SL=${sl_price:.4f} | TP=${tp_price:.4f}"
        )
    
    def log_complete_signal(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        leverage: float,
        sl_price: float,
        tp_price: float,
        win_rate: float,
        confidence: float
    ):
        """
        記錄完整信號詳情
        
        Args:
            symbol: 交易對
            direction: 方向
            entry_price: 入場價格
            leverage: 槓桿
            sl_price: 止損價格
            tp_price: 止盈價格
            win_rate: 勝率
            confidence: 信心度
        """
        self.logger.info(
            f"🎯 {symbol} 完整信號: "
            f"{direction} @ {entry_price:.4f} | "
            f"槓桿={leverage:.1f}x | "
            f"SL={sl_price:.4f} | "
            f"TP={tp_price:.4f} | "
            f"勝率={win_rate*100:.1f}% | "
            f"信心度={confidence*100:.1f}%"
        )


# 全局單例
_signal_details_logger: Optional[SignalDetailsLogger] = None


def get_signal_details_logger() -> SignalDetailsLogger:
    """獲取信號詳情日誌器（單例模式）"""
    global _signal_details_logger
    if _signal_details_logger is None:
        _signal_details_logger = SignalDetailsLogger()
    return _signal_details_logger
