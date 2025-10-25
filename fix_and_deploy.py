#!/usr/bin/env python3
"""
自动诊断和修复 Railway 部署问题
"""

import os
import sys
import json
import requests
from datetime import datetime

# Railway API 配置
RAILWAY_API = "https://backboard.railway.com/graphql/v2"
PROJECT_ID = "ef7a7a00-69c2-4ed7-aac6-58efb6a60587"
SERVICE_ID = "65a8c8d7-b734-4bcf-bd04-13b83f95ba87"
ENVIRONMENT_ID = "7cdf5c02-eb2a-42cb-b419-924aae71ff53"

def get_token():
    """获取 Railway token"""
    token = os.getenv("RAILWAY_TOKEN")
    if not token:
        print("❌ 错误: RAILWAY_TOKEN 环境变量未设置")
        sys.exit(1)
    return token

def query_railway(query, variables=None):
    """执行 Railway GraphQL 查询"""
    token = get_token()
    headers = {
        "Project-Access-Token": token,
        "Content-Type": "application/json"
    }
    
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    
    response = requests.post(RAILWAY_API, headers=headers, json=payload)
    
    if response.status_code != 200:
        return None
    
    data = response.json()
    if "errors" in data:
        return None
    
    return data.get("data")

def check_deployment_status():
    """检查最新部署状态"""
    print("=" * 60)
    print("🔍 检查 Railway 部署状态...")
    print("=" * 60)
    
    query = """
    query {
      project(id: "%s") {
        services {
          edges {
            node {
              id
              name
              deployments(first: 3) {
                edges {
                  node {
                    id
                    status
                    createdAt
                    updatedAt
                  }
                }
              }
            }
          }
        }
      }
    }
    """ % PROJECT_ID
    
    data = query_railway(query)
    if not data:
        print("❌ 无法获取部署信息")
        return None
    
    services = data["project"]["services"]["edges"]
    for service in services:
        if service["node"]["id"] == SERVICE_ID:
            deployments = service["node"]["deployments"]["edges"]
            if deployments:
                latest = deployments[0]["node"]
                print(f"\n📦 最新部署:")
                print(f"  ID: {latest['id']}")
                print(f"  状态: {latest['status']}")
                print(f"  创建时间: {latest['createdAt']}")
                print(f"  更新时间: {latest['updatedAt']}")
                return latest
    
    return None

def diagnose_issues():
    """诊断问题"""
    print("\n" + "=" * 60)
    print("🔍 诊断系统问题...")
    print("=" * 60)
    
    issues = []
    
    # 检查关键文件
    import subprocess
    
    # 1. 检查 get_24h_tickers
    try:
        result = subprocess.run(
            ["grep", "-q", "async def get_24h_tickers", "src/clients/binance_client.py"],
            capture_output=True
        )
        if result.returncode == 0:
            print("✅ get_24h_tickers 函数存在")
        else:
            print("❌ get_24h_tickers 函数缺失")
            issues.append("get_24h_tickers 函数缺失")
    except Exception as e:
        print(f"⚠️  检查失败: {e}")
    
    # 2. 检查依赖
    if not os.path.exists("requirements.txt"):
        print("❌ requirements.txt 缺失")
        issues.append("requirements.txt 缺失")
    else:
        print("✅ requirements.txt 存在")
    
    # 3. 检查配置文件
    if not os.path.exists("railway.json"):
        print("❌ railway.json 缺失")
        issues.append("railway.json 缺失")
    else:
        print("✅ railway.json 存在")
    
    if not os.path.exists("nixpacks.toml"):
        print("❌ nixpacks.toml 缺失")
        issues.append("nixpacks.toml 缺失")
    else:
        print("✅ nixpacks.toml 存在")
    
    return issues

def provide_solution():
    """提供解决方案"""
    print("\n" + "=" * 60)
    print("💡 解决方案")
    print("=" * 60)
    
    deployment = check_deployment_status()
    issues = diagnose_issues()
    
    if deployment and deployment["status"] == "FAILED":
        print("\n🚨 部署失败的可能原因:")
        print("1. 构建错误（依赖安装失败）")
        print("2. 启动命令错误")
        print("3. 端口配置问题")
        print("4. 环境变量缺失")
        
        print("\n📋 建议操作:")
        print("\n方法 1: 查看 Railway 构建日志（推荐）")
        print("  1. 登录 Railway: https://railway.app/")
        print("  2. 进入项目: skillful-perfection")
        print("  3. 点击失败的部署")
        print("  4. 查看 'Build Logs' 和 'Deploy Logs'")
        print("  5. 复制错误信息给我")
        
        print("\n方法 2: 手动重新部署")
        print("  1. 确保本地代码没有问题:")
        print("     python3 verify_system.py")
        print("  2. 提交到 Git:")
        print("     git add .")
        print("     git commit -m 'Fix deployment issues'")
        print("     git push origin main")
        print("  3. 在 Railway 控制台点击 'Redeploy'")
        
        print("\n方法 3: 检查环境变量")
        print("  确保 Railway 设置了以下环境变量:")
        print("  - BINANCE_API_KEY 或 BINANCE_KEY")
        print("  - BINANCE_API_SECRET 或 BINANCE_SECRET_KEY")
        print("  - DISCORD_TOKEN 或 DISCORD_BOT_TOKEN")
        print("  - SESSION_SECRET")
    
    elif deployment and deployment["status"] == "SUCCESS":
        print("\n✅ 部署成功！")
        print("现在检查日志以确认系统正常运行...")
        print("\n在 Railway 日志中查找:")
        print("  ✓ 📌 代碼版本: 2025-10-25-v2.0")
        print("  ✓ 🔍 開始掃描市場，目標選擇前 200 個高波動率交易對")
        print("  ✓ ✅ 市場掃描完成: 從 X 個交易對中選擇波動率最高的前 200 個")
        print("  ✓ 🔍 使用 32 核心並行分析 200 個高波動率交易對")
        print("  ✓ 開始批量分析 200 個交易對")
    
    print("\n" + "=" * 60)
    
    if issues:
        print(f"⚠️  发现 {len(issues)} 个问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        return False
    else:
        print("✅ 本地代码检查通过")
        return True

if __name__ == "__main__":
    try:
        result = provide_solution()
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
