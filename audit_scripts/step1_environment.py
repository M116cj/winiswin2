#!/usr/bin/env python3
"""
STEP 1: 基礎環境與網絡連接檢測
檢測Python環境和關鍵依賴、DNS解析、端口連接、SSL證書
"""

import sys
import socket
import ssl
import asyncio
from datetime import datetime

def check_python_version():
    """檢查Python版本"""
    version = sys.version_info
    print(f"✅ Python 版本: {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """檢查關鍵依賴包"""
    dependencies = {
        'aiohttp': None,
        'websockets': None,
        'asyncpg': None,
        'xgboost': None,
        'pandas': None,
        'numpy': None
    }
    
    score = 0
    for package in dependencies.keys():
        try:
            __import__(package)
            print(f"✅ {package}: 已安裝")
            score += 1
        except ImportError:
            print(f"❌ {package}: 未安裝")
    
    return score / len(dependencies)

def check_dns_resolution(hostname):
    """檢查DNS解析"""
    try:
        ip_address = socket.gethostbyname(hostname)
        print(f"✅ {hostname}: DNS解析成功 → {ip_address}")
        return True
    except socket.gaierror as e:
        print(f"❌ {hostname}: DNS解析失敗 - {e}")
        return False

def check_port_connection(hostname, port, timeout=5):
    """檢查端口連接"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start_time = datetime.now()
        result = sock.connect_ex((hostname, port))
        latency = (datetime.now() - start_time).total_seconds() * 1000
        sock.close()
        
        if result == 0:
            print(f"✅ {hostname}:{port}: 端口連接成功 ({latency:.0f}ms)")
            return True
        else:
            print(f"❌ {hostname}:{port}: 端口連接失敗 (錯誤碼: {result})")
            return False
    except Exception as e:
        print(f"❌ {hostname}:{port}: 連接異常 - {e}")
        return False

def check_ssl_certificate(hostname, port=443):
    """檢查SSL證書有效性"""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                print(f"✅ SSL證書有效")
                print(f"   發行者: {dict(x[0] for x in cert['issuer']).get('organizationName', 'N/A')}")
                print(f"   有效期至: {cert['notAfter']}")
                return True
    except ssl.SSLError as e:
        print(f"❌ SSL證書錯誤: {e}")
        return False
    except Exception as e:
        print(f"❌ SSL檢查異常: {e}")
        return False

def check_environment_variables():
    """檢查系統環境變量配置"""
    import os
    
    required_vars = [
        'BINANCE_API_KEY',
        'BINANCE_API_SECRET',
        'DATABASE_URL'
    ]
    
    score = 0
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked = value[:4] + '...' + value[-4:] if len(value) > 8 else '***'
            print(f"✅ {var}: 已配置 ({masked})")
            score += 1
        else:
            print(f"❌ {var}: 未配置")
    
    return score / len(required_vars)

def main():
    print("=" * 60)
    print("🔍 STEP 1: 基礎環境與網絡連接檢測")
    print("=" * 60)
    print()
    
    scores = []
    
    # 1. Python版本檢查
    print("📌 1.1 Python版本檢查")
    check_python_version()
    print()
    
    # 2. 依賴包檢查
    print("📌 1.2 關鍵依賴包檢查")
    dep_score = check_dependencies()
    scores.append(dep_score)
    print()
    
    # 3. DNS解析檢查
    print("📌 1.3 DNS解析檢查")
    dns_results = []
    for hostname in ['api.binance.com', 'fapi.binance.com', 'fstream.binance.com']:
        result = check_dns_resolution(hostname)
        dns_results.append(result)
    dns_score = sum(dns_results) / len(dns_results)
    scores.append(dns_score)
    print()
    
    # 4. 端口連接檢查
    print("📌 1.4 端口連接檢查")
    port_results = []
    for hostname, port in [('api.binance.com', 443), ('fapi.binance.com', 443)]:
        result = check_port_connection(hostname, port)
        port_results.append(result)
    port_score = sum(port_results) / len(port_results)
    scores.append(port_score)
    print()
    
    # 5. SSL證書檢查
    print("📌 1.5 SSL證書有效性檢查")
    ssl_result = check_ssl_certificate('api.binance.com')
    scores.append(1.0 if ssl_result else 0.0)
    print()
    
    # 6. 環境變量檢查
    print("📌 1.6 環境變量配置檢查")
    env_score = check_environment_variables()
    scores.append(env_score)
    print()
    
    # 總評分
    total_score = sum(scores) / len(scores) * 100
    print("=" * 60)
    print(f"📊 STEP 1 總體評分: {total_score:.1f}%")
    print("=" * 60)
    
    return total_score

if __name__ == "__main__":
    score = main()
    sys.exit(0 if score >= 80 else 1)
