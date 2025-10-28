"""
v3.17+ 核心配置類
使用 @dataclass(frozen=True) 確保不可變性和線程安全
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ConfigProfile:
    """v3.17+ 配置檔案（環境變量驅動，不可變）"""
    
    # ===== 槓桿與風險配置 (v3.17+) =====
    min_win_probability: float = float(os.getenv("MIN_WIN_PROBABILITY", "0.55"))
    min_confidence: float = float(os.getenv("MIN_CONFIDENCE", "0.50"))
    min_rr_ratio: float = float(os.getenv("MIN_RR_RATIO", "1.0"))
    max_rr_ratio: float = float(os.getenv("MAX_RR_RATIO", "2.0"))
    
    # 槓桿計算參數（無上限）
    leverage_base: float = 1.0
    leverage_win_threshold: float = 0.55
    leverage_win_scale: float = 0.15
    leverage_win_multiplier: float = 11.0
    leverage_conf_scale: float = 0.5
    min_leverage: float = 0.0  # 無限制：允許任意槓桿
    
    # 倉位計算參數
    equity_usage_ratio: float = 0.8
    min_notional_value: float = 10.0
    min_stop_distance_pct: float = 0.003
    
    # SL/TP 動態調整參數
    sltp_scale_factor: float = 0.05
    sltp_max_scale: float = 3.0
    
    # ===== 倉位監控配置 (v3.17+) =====
    position_monitor_enabled: bool = os.getenv("POSITION_MONITOR_ENABLED", "true").lower() == "true"
    position_monitor_interval: int = int(os.getenv("POSITION_MONITOR_INTERVAL", "2"))
    risk_kill_threshold: float = float(os.getenv("RISK_KILL_THRESHOLD", "0.99"))
    
    # ===== 模型評級配置 (v3.17+) =====
    model_rating_enabled: bool = os.getenv("MODEL_RATING_ENABLED", "true").lower() == "true"
    rating_rr_weight: float = 0.25
    rating_winrate_weight: float = 0.20
    rating_ev_weight: float = 0.20
    rating_mdd_weight: float = 0.15
    rating_sharpe_weight: float = 0.10
    rating_frequency_weight: float = 0.10
    rating_loss_penalty: float = 15.0
    
    # ===== 報告配置 (v3.17+) =====
    reports_dir: str = os.getenv("REPORTS_DIR", "reports/daily")
    enable_daily_report: bool = os.getenv("ENABLE_DAILY_REPORT", "true").lower() == "true"
    report_stdout_enabled: bool = True
    
    # ===== API 優先級配置 (v3.17+) =====
    priority_position_ops: int = 0
    priority_data_fetch: int = 3
    
    # ===== 策略模式配置 =====
    strategy_mode: str = os.getenv("STRATEGY_MODE", "self_learning")
    position_control_mode: str = os.getenv("POSITION_CONTROL_MODE", "self_learning")
    
    # ===== Binance API 配置 =====
    binance_api_key: str = os.getenv("BINANCE_API_KEY", "")
    binance_api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    binance_testnet: bool = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
    
    # ===== 系統配置 =====
    trading_enabled: bool = os.getenv("TRADING_ENABLED", "false").lower() == "true"
    max_positions: int = int(os.getenv("MAX_POSITIONS", "999"))
    cycle_interval: int = int(os.getenv("CYCLE_INTERVAL", "60"))
    
    # ===== ThreadPool 配置（避免 pickle 錯誤）=====
    use_thread_pool: bool = True
    max_workers: int = int(os.getenv("MAX_WORKERS", "4"))
    
    def validate(self) -> tuple[bool, list[str]]:
        """
        驗證配置有效性
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        # 驗證槓桿參數
        if self.min_win_probability < 0 or self.min_win_probability > 1:
            errors.append(f"MIN_WIN_PROBABILITY 必須在 0-1 之間，當前為 {self.min_win_probability}")
        
        if self.min_confidence < 0 or self.min_confidence > 1:
            errors.append(f"MIN_CONFIDENCE 必須在 0-1 之間，當前為 {self.min_confidence}")
        
        if self.min_rr_ratio < 0:
            errors.append(f"MIN_RR_RATIO 必須 >= 0，當前為 {self.min_rr_ratio}")
        
        # 驗證倉位監控參數
        if self.position_monitor_interval < 1:
            errors.append(f"POSITION_MONITOR_INTERVAL 必須 >= 1 秒，當前為 {self.position_monitor_interval}")
        
        if self.risk_kill_threshold < 0 or self.risk_kill_threshold > 1:
            errors.append(f"RISK_KILL_THRESHOLD 必須在 0-1 之間，當前為 {self.risk_kill_threshold}")
        
        # 驗證模型評級權重
        total_weight = (
            self.rating_rr_weight + 
            self.rating_winrate_weight + 
            self.rating_ev_weight + 
            self.rating_mdd_weight + 
            self.rating_sharpe_weight + 
            self.rating_frequency_weight
        )
        if abs(total_weight - 1.0) > 0.01:
            errors.append(f"模型評級權重總和必須為 1.0，當前為 {total_weight:.2f}")
        
        # 驗證 API 密鑰（如果交易啟用）
        if self.trading_enabled:
            if not self.binance_api_key or not self.binance_api_secret:
                errors.append("TRADING_ENABLED=true 但未設置 BINANCE_API_KEY/SECRET")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def to_dict(self) -> dict:
        """轉換為字典（用於日誌/報告）"""
        return {
            "strategy_mode": self.strategy_mode,
            "position_control_mode": self.position_control_mode,
            "min_win_probability": f"{self.min_win_probability:.1%}",
            "min_confidence": f"{self.min_confidence:.1%}",
            "min_rr_ratio": f"{self.min_rr_ratio:.1f}",
            "leverage_range": "無限制 (0x ~ ∞)",
            "position_monitor": "已啟用" if self.position_monitor_enabled else "已禁用",
            "model_rating": "已啟用" if self.model_rating_enabled else "已禁用",
            "trading_enabled": self.trading_enabled,
            "max_positions": self.max_positions,
            "use_thread_pool": self.use_thread_pool,
        }
