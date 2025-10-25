"""
輔助函數
職責：時間處理、數值格式化、數據驗證
"""

from datetime import datetime, timezone
from typing import Any, Optional
import json
import os

def get_timestamp() -> int:
    """獲取當前 UTC 時間戳（毫秒）"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def format_timestamp(timestamp: int) -> str:
    """
    格式化時間戳為可讀字符串
    
    Args:
        timestamp: 毫秒時間戳
    
    Returns:
        格式化的時間字符串
    """
    dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

def round_to_precision(value: float, precision: int) -> float:
    """
    將數值四捨五入到指定精度
    
    Args:
        value: 數值
        precision: 小數位數
    
    Returns:
        四捨五入後的值
    """
    return round(value, precision)

def format_percentage(value: float) -> str:
    """
    格式化百分比
    
    Args:
        value: 0-1 之間的數值
    
    Returns:
        百分比字符串
    """
    return f"{value * 100:.2f}%"

def format_usd(value: float) -> str:
    """
    格式化美元金額
    
    Args:
        value: 金額
    
    Returns:
        格式化的金額字符串
    """
    return f"${value:,.2f}"

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    安全除法（避免除零錯誤）
    
    Args:
        numerator: 分子
        denominator: 分母
        default: 默認值
    
    Returns:
        除法結果或默認值
    """
    return numerator / denominator if denominator != 0 else default

def load_json_file(filepath: str, default: Any = None) -> Any:
    """
    加載 JSON 文件
    
    Args:
        filepath: 文件路徑
        default: 文件不存在時的默認值
    
    Returns:
        JSON 數據或默認值
    """
    if not os.path.exists(filepath):
        return default if default is not None else []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加載 JSON 文件失敗 {filepath}: {e}")
        return default if default is not None else []

def save_json_file(filepath: str, data: Any):
    """
    保存 JSON 文件
    
    Args:
        filepath: 文件路徑
        data: 要保存的數據
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def validate_required_fields(data: dict, required_fields: list[str]) -> tuple[bool, list[str]]:
    """
    驗證必填字段
    
    Args:
        data: 數據字典
        required_fields: 必填字段列表
    
    Returns:
        tuple[bool, list[str]]: (是否有效, 缺失字段列表)
    """
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    return len(missing_fields) == 0, missing_fields

def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    計算百分比變化
    
    Args:
        old_value: 舊值
        new_value: 新值
    
    Returns:
        百分比變化（0-1 之間）
    """
    if old_value == 0:
        return 0.0
    return (new_value - old_value) / old_value

def clamp(value: float, min_value: float, max_value: float) -> float:
    """
    將值限制在指定範圍內
    
    Args:
        value: 值
        min_value: 最小值
        max_value: 最大值
    
    Returns:
        限制後的值
    """
    return max(min_value, min(max_value, value))
