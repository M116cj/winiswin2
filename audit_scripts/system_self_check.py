#!/usr/bin/env python3
"""
SelfLearningTrader v4.4.1 系统自我检查脚本
执行频率: 按需或每30分钟自动执行
"""

import os
import sys
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, Tuple, List

class SystemSelfChecker:
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
    
    def check_environment(self) -> Dict[str, Any]:
        """检查1: 环境配置"""
        print("\n" + "="*80)
        print("📋 检查1: 环境配置")
        print("="*80)
        
        checks = {
            "Python版本": self._check_python_version(),
            "Binance API密钥": self._check_binance_credentials(),
            "数据库URL": self._check_database_url(),
            "关键环境变量": self._check_critical_env_vars(),
            "WebSocket配置": self._check_websocket_config(),
            "风险控制配置": self._check_risk_config()
        }
        
        passed = sum(1 for v in checks.values() if v["status"] == "PASS")
        total = len(checks)
        
        return {
            "status": "PASS" if passed == total else "WARNING" if passed >= total * 0.7 else "FAIL",
            "passed": passed,
            "total": total,
            "checks": checks
        }
    
    def _check_python_version(self) -> Dict[str, Any]:
        """检查Python版本"""
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"
        
        if version >= (3, 11):
            status = "PASS"
            message = f"Python {version_str} ✅"
        else:
            status = "FAIL"
            message = f"Python {version_str} (需要 ≥3.11) ❌"
        
        print(f"  • Python版本: {message}")
        return {"status": status, "message": message, "value": version_str}
    
    def _check_binance_credentials(self) -> Dict[str, Any]:
        """检查Binance API密钥"""
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")
        
        if api_key and api_secret:
            status = "PASS"
            message = f"API密钥已配置 ✅ (长度: {len(api_key)}字符)"
        else:
            status = "FAIL"
            message = "API密钥未配置 ❌ (系统无法执行实际交易)"
        
        print(f"  • Binance API: {message}")
        return {"status": status, "message": message}
    
    def _check_database_url(self) -> Dict[str, Any]:
        """检查数据库URL"""
        db_url = os.getenv("DATABASE_URL", "")
        db_public_url = os.getenv("DATABASE_PUBLIC_URL", "")
        
        if db_url or db_public_url:
            status = "PASS"
            db_type = "内部" if db_url else "公开"
            message = f"数据库URL已配置 ({db_type}) ✅"
        else:
            status = "FAIL"
            message = "数据库URL未配置 ❌"
        
        print(f"  • 数据库URL: {message}")
        return {"status": status, "message": message}
    
    def _check_critical_env_vars(self) -> Dict[str, Any]:
        """检查关键环境变量"""
        critical_vars = {
            "TRADING_ENABLED": os.getenv("TRADING_ENABLED", "true"),
            "WEBSOCKET_ONLY_KLINES": os.getenv("WEBSOCKET_ONLY_KLINES", "true"),
            "TIME_BASED_STOP_LOSS_ENABLED": os.getenv("TIME_BASED_STOP_LOSS_ENABLED", "true"),
            "CROSS_MARGIN_PROTECTOR_ENABLED": os.getenv("CROSS_MARGIN_PROTECTOR_ENABLED", "true")
        }
        
        all_configured = all(critical_vars.values())
        status = "PASS" if all_configured else "WARNING"
        
        details = []
        for key, value in critical_vars.items():
            symbol = "✅" if value.lower() == "true" else "⚠️"
            details.append(f"{key}={value} {symbol}")
            print(f"  • {key}: {value} {symbol}")
        
        message = "所有关键变量已配置" if all_configured else "部分变量使用默认值"
        return {"status": status, "message": message, "details": details}
    
    def _check_websocket_config(self) -> Dict[str, Any]:
        """检查WebSocket配置"""
        ws_only = os.getenv("WEBSOCKET_ONLY_KLINES", "true").lower() == "true"
        disable_rest = os.getenv("DISABLE_REST_FALLBACK", "true").lower() == "true"
        
        if ws_only and disable_rest:
            status = "PASS"
            message = "WebSocket-only模式已启用 ✅ (符合Binance API规范)"
        else:
            status = "WARNING"
            message = "WebSocket配置未优化 ⚠️"
        
        print(f"  • WebSocket模式: {message}")
        return {"status": status, "message": message}
    
    def _check_risk_config(self) -> Dict[str, Any]:
        """检查风险控制配置"""
        time_stop = os.getenv("TIME_BASED_STOP_LOSS_ENABLED", "true").lower() == "true"
        cross_margin = os.getenv("CROSS_MARGIN_PROTECTOR_ENABLED", "true").lower() == "true"
        
        if time_stop and cross_margin:
            status = "PASS"
            message = "风险控制机制已启用 ✅"
        else:
            status = "WARNING"
            message = "部分风险控制未启用 ⚠️"
        
        print(f"  • 风险控制: {message}")
        return {"status": status, "message": message}
    
    def check_core_files(self) -> Dict[str, Any]:
        """检查2: 核心文件"""
        print("\n" + "="*80)
        print("📂 检查2: 核心文件")
        print("="*80)
        
        critical_files = [
            "src/main.py",
            "src/config.py",
            "src/core/unified_scheduler.py",
            "src/strategies/self_learning_trader.py",
            "src/core/position_controller.py",
            "src/clients/binance_client.py",
            "src/database/manager.py",
            "requirements.txt",
            "SYSTEM_ENVIRONMENT_REPORT.md"
        ]
        
        checks = {}
        for file_path in critical_files:
            exists = Path(file_path).exists()
            status = "PASS" if exists else "FAIL"
            symbol = "✅" if exists else "❌"
            
            if exists:
                size = Path(file_path).stat().st_size
                message = f"{size:,} 字节"
            else:
                message = "文件不存在"
            
            checks[file_path] = {"status": status, "message": message}
            print(f"  • {file_path}: {message} {symbol}")
        
        passed = sum(1 for v in checks.values() if v["status"] == "PASS")
        total = len(checks)
        
        return {
            "status": "PASS" if passed == total else "FAIL",
            "passed": passed,
            "total": total,
            "checks": checks
        }
    
    def check_dependencies(self) -> Dict[str, Any]:
        """检查3: 依赖包"""
        print("\n" + "="*80)
        print("📦 检查3: Python依赖包")
        print("="*80)
        
        required_packages = [
            "aiohttp",
            "websockets",
            "pandas",
            "numpy",
            "xgboost",
            "sklearn",
            "ccxt",
            "psycopg2",
            "asyncpg",
            "psutil"
        ]
        
        checks = {}
        for package in required_packages:
            try:
                # 特殊处理某些包名
                import_name = package
                if package == "sklearn":
                    import_name = "sklearn"
                elif package == "psycopg2":
                    import_name = "psycopg2"
                
                module = __import__(import_name)
                version = getattr(module, "__version__", "未知版本")
                
                status = "PASS"
                message = f"v{version}"
                symbol = "✅"
            except ImportError as e:
                status = "FAIL"
                message = "未安装"
                symbol = "❌"
            
            checks[package] = {"status": status, "message": message}
            print(f"  • {package}: {message} {symbol}")
        
        passed = sum(1 for v in checks.values() if v["status"] == "PASS")
        total = len(checks)
        
        return {
            "status": "PASS" if passed == total else "FAIL",
            "passed": passed,
            "total": total,
            "checks": checks
        }
    
    def check_directory_structure(self) -> Dict[str, Any]:
        """检查4: 目录结构"""
        print("\n" + "="*80)
        print("📁 检查4: 目录结构")
        print("="*80)
        
        required_dirs = [
            "src/core",
            "src/strategies",
            "src/database",
            "src/clients",
            "src/ml",
            "src/managers",
            "src/monitoring",
            "data",
            "models",
            "docs"
        ]
        
        checks = {}
        for dir_path in required_dirs:
            exists = Path(dir_path).exists()
            status = "PASS" if exists else "WARNING"
            symbol = "✅" if exists else "⚠️"
            
            if exists:
                file_count = len(list(Path(dir_path).glob("*.py"))) if dir_path.startswith("src") else len(list(Path(dir_path).iterdir()))
                message = f"{file_count} 个文件"
            else:
                message = "目录不存在"
            
            checks[dir_path] = {"status": status, "message": message}
            print(f"  • {dir_path}: {message} {symbol}")
        
        passed = sum(1 for v in checks.values() if v["status"] == "PASS")
        total = len(checks)
        
        return {
            "status": "PASS" if passed >= total * 0.8 else "WARNING",
            "passed": passed,
            "total": total,
            "checks": checks
        }
    
    def check_configuration_validity(self) -> Dict[str, Any]:
        """检查5: 配置验证"""
        print("\n" + "="*80)
        print("⚙️ 检查5: 配置有效性")
        print("="*80)
        
        checks = {}
        
        try:
            from src.config import Config
            
            # 检查配置类加载
            checks["Config类加载"] = {
                "status": "PASS",
                "message": "配置类成功加载 ✅"
            }
            print(f"  • Config类加载: 成功 ✅")
            
            # 检查数据库配置
            db_configured = Config.is_database_configured()
            checks["数据库配置"] = {
                "status": "PASS" if db_configured else "WARNING",
                "message": f"数据库{'已配置' if db_configured else '未配置'} {'✅' if db_configured else '⚠️'}"
            }
            print(f"  • 数据库配置: {'已配置' if db_configured else '未配置'} {'✅' if db_configured else '⚠️'}")
            
            # 检查交易参数
            trading_enabled = Config.TRADING_ENABLED
            checks["交易启用状态"] = {
                "status": "PASS",
                "message": f"TRADING_ENABLED={trading_enabled} ✅"
            }
            print(f"  • 交易启用: {trading_enabled} ✅")
            
            # 检查WebSocket配置
            ws_only = Config.WEBSOCKET_ONLY_KLINES
            checks["WebSocket模式"] = {
                "status": "PASS" if ws_only else "WARNING",
                "message": f"WEBSOCKET_ONLY_KLINES={ws_only} {'✅' if ws_only else '⚠️'}"
            }
            print(f"  • WebSocket模式: {ws_only} {'✅' if ws_only else '⚠️'}")
            
            # 检查风险控制
            time_stop = Config.TIME_BASED_STOP_LOSS_ENABLED
            checks["时间止损"] = {
                "status": "PASS" if time_stop else "WARNING",
                "message": f"TIME_BASED_STOP_LOSS_ENABLED={time_stop} {'✅' if time_stop else '⚠️'}"
            }
            print(f"  • 时间止损: {time_stop} {'✅' if time_stop else '⚠️'}")
            
        except Exception as e:
            checks["配置加载错误"] = {
                "status": "FAIL",
                "message": f"配置加载失败: {str(e)} ❌"
            }
            print(f"  • 配置加载: 失败 ❌ ({str(e)})")
        
        passed = sum(1 for v in checks.values() if v["status"] == "PASS")
        total = len(checks)
        
        return {
            "status": "PASS" if passed == total else "WARNING" if passed >= total * 0.7 else "FAIL",
            "passed": passed,
            "total": total,
            "checks": checks
        }
    
    def check_workflow_status(self) -> Dict[str, Any]:
        """检查6: Workflow状态"""
        print("\n" + "="*80)
        print("🔄 检查6: Workflow状态")
        print("="*80)
        
        # 这里我们只能检查基本状态，实际运行状态需要通过日志
        workflow_file = Path(".replit")
        
        if workflow_file.exists():
            status = "PASS"
            message = "Workflow配置文件存在 ✅"
            print(f"  • Workflow配置: {message}")
        else:
            status = "WARNING"
            message = "Workflow配置文件不存在 ⚠️"
            print(f"  • Workflow配置: {message}")
        
        print(f"  • Trading Bot状态: 需要手动启动 ⚠️")
        
        return {
            "status": status,
            "message": message,
            "note": "Workflow需要通过Replit界面或restart_workflow工具启动"
        }
    
    def generate_report(self, all_results: Dict[str, Any]) -> str:
        """生成最终报告"""
        elapsed = time.time() - self.start_time
        
        print("\n" + "="*80)
        print("📊 系统自我检查报告 (v4.4.1)")
        print("="*80)
        print(f"检查时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"执行耗时: {elapsed:.2f}秒")
        print("="*80)
        
        total_checks = 0
        total_passed = 0
        
        for check_name, result in all_results.items():
            if isinstance(result, dict) and "passed" in result and "total" in result:
                total_checks += result["total"]
                total_passed += result["passed"]
                
                status_icon = "✅" if result["status"] == "PASS" else "⚠️" if result["status"] == "WARNING" else "❌"
                pass_rate = (result["passed"] / result["total"] * 100) if result["total"] > 0 else 0
                
                print(f"{status_icon} {check_name}: {result['passed']}/{result['total']} ({pass_rate:.0f}%)")
        
        print("="*80)
        
        overall_pass_rate = (total_passed / total_checks * 100) if total_checks > 0 else 0
        
        if overall_pass_rate >= 95:
            overall_status = "✅ 优秀"
            recommendation = "系统运行正常，无需干预"
        elif overall_pass_rate >= 85:
            overall_status = "⚠️ 良好"
            recommendation = "关注警告项，监控运行"
        elif overall_pass_rate >= 75:
            overall_status = "🔶 需关注"
            recommendation = "检查失败项，考虑优化"
        else:
            overall_status = "❌ 异常"
            recommendation = "立即干预，排查问题"
        
        print(f"总体状态: {overall_status}")
        print(f"通过率: {total_passed}/{total_checks} ({overall_pass_rate:.1f}%)")
        print(f"处理建议: {recommendation}")
        print("="*80)
        
        # 关键问题汇总
        print("\n⚠️ 需要注意的问题:")
        
        issues = []
        
        # 检查Binance API
        if "环境配置" in all_results:
            env_checks = all_results["环境配置"].get("checks", {})
            if "Binance API密钥" in env_checks and env_checks["Binance API密钥"]["status"] == "FAIL":
                issues.append("❌ Binance API密钥未配置 - 系统无法执行实际交易")
        
        # 检查数据库
        if "环境配置" in all_results:
            env_checks = all_results["环境配置"].get("checks", {})
            if "数据库URL" in env_checks and env_checks["数据库URL"]["status"] == "FAIL":
                issues.append("❌ 数据库未配置 - 无法持久化交易数据和持仓时间")
        
        # 检查依赖包
        if "依赖包" in all_results and all_results["依赖包"]["status"] == "FAIL":
            issues.append("❌ 部分依赖包未安装 - 可能影响系统功能")
        
        if issues:
            for issue in issues:
                print(f"  {issue}")
        else:
            print("  ✅ 无严重问题")
        
        print("\n" + "="*80)
        
        return overall_status
    
    def run_full_check(self) -> None:
        """执行完整系统检查"""
        print("\n" + "🔍"*40)
        print("SelfLearningTrader v4.4.1 系统自我检查")
        print("🔍"*40)
        
        results = {
            "环境配置": self.check_environment(),
            "核心文件": self.check_core_files(),
            "依赖包": self.check_dependencies(),
            "目录结构": self.check_directory_structure(),
            "配置有效性": self.check_configuration_validity(),
            "Workflow状态": self.check_workflow_status()
        }
        
        self.generate_report(results)
        
        return results

if __name__ == "__main__":
    checker = SystemSelfChecker()
    checker.run_full_check()
