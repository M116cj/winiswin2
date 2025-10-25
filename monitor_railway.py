#!/usr/bin/env python3
"""
Railway 部署监控脚本
实时监控 Railway 部署状态和验证版本
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone

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
        print(f"❌ API 请求失败: {response.status_code}")
        return None
    
    data = response.json()
    if "errors" in data:
        print(f"❌ GraphQL 错误: {data['errors']}")
        return None
    
    return data.get("data")

def get_latest_deployment():
    """获取最新部署信息"""
    query = """
    query {
      project(id: "%s") {
        name
        services {
          edges {
            node {
              id
              name
              deployments(first: 1) {
                edges {
                  node {
                    id
                    status
                    staticUrl
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
    if not data or "project" not in data:
        return None
    
    services = data["project"]["services"]["edges"]
    if not services:
        return None
    
    for service in services:
        if service["node"]["id"] == SERVICE_ID:
            deployments = service["node"]["deployments"]["edges"]
            if deployments:
                return deployments[0]["node"]
    
    return None

def format_time(iso_time):
    """格式化时间"""
    try:
        dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return iso_time

def check_deployment_status():
    """检查部署状态"""
    print("=" * 60)
    print("🚀 Railway 部署状态监控")
    print("=" * 60)
    print(f"项目 ID: {PROJECT_ID}")
    print(f"服务 ID: {SERVICE_ID}")
    print(f"环境 ID: {ENVIRONMENT_ID}")
    print("=" * 60)
    
    deployment = get_latest_deployment()
    
    if not deployment:
        print("❌ 无法获取部署信息")
        return False
    
    status = deployment["status"]
    created_at = format_time(deployment["createdAt"])
    updated_at = format_time(deployment["updatedAt"])
    deployment_id = deployment["id"]
    
    print(f"\n📦 最新部署:")
    print(f"  ID: {deployment_id}")
    print(f"  状态: {status}")
    print(f"  创建时间: {created_at}")
    print(f"  更新时间: {updated_at}")
    
    # 状态说明
    status_emoji = {
        "SUCCESS": "✅",
        "FAILED": "❌",
        "BUILDING": "🔨",
        "DEPLOYING": "🚀",
        "CRASHED": "💥",
        "REMOVED": "🗑️"
    }
    
    emoji = status_emoji.get(status, "❓")
    print(f"\n{emoji} 部署状态: {status}")
    
    if status == "SUCCESS":
        print("\n✅ 部署成功！")
        print("\n📌 验证要点:")
        print("请在 Railway 控制台日志中查找以下内容:")
        print("  ✓ 版本标识: 📌 代碼版本: 2025-10-25-v2.0")
        print("  ✓ 市场扫描: 🔍 開始掃描市場，目標選擇前 200 個高波動率交易對")
        print("  ✓ 波动率显示: 📈 波動率最高的前10個交易對")
        print("  ✓ 并行处理: 🔍 使用 32 核心並行分析 200 個")
        return True
    elif status == "FAILED":
        print("\n❌ 部署失败！")
        print("请检查 Railway 控制台的构建和部署日志")
        return False
    elif status in ["BUILDING", "DEPLOYING"]:
        print(f"\n⏳ 部署进行中... ({status})")
        print("请稍后再次运行此脚本检查状态")
        return None
    else:
        print(f"\n⚠️  未知状态: {status}")
        return None

def monitor_continuous(interval=10, max_attempts=30):
    """持续监控部署状态"""
    print("🔍 开始持续监控模式（每 {} 秒检查一次）\n".format(interval))
    
    for attempt in range(max_attempts):
        print(f"\n[检查 {attempt + 1}/{max_attempts}] {datetime.now().strftime('%H:%M:%S')}")
        
        result = check_deployment_status()
        
        if result is True:
            print("\n🎉 部署成功完成！")
            return True
        elif result is False:
            print("\n❌ 部署失败！")
            return False
        
        if attempt < max_attempts - 1:
            print(f"\n⏳ 等待 {interval} 秒后重新检查...")
            time.sleep(interval)
    
    print("\n⚠️  达到最大检查次数，请手动查看 Railway 控制台")
    return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Railway 部署监控")
    parser.add_argument("--monitor", action="store_true", help="持续监控模式")
    parser.add_argument("--interval", type=int, default=10, help="监控间隔（秒）")
    parser.add_argument("--max-attempts", type=int, default=30, help="最大检查次数")
    
    args = parser.parse_args()
    
    if args.monitor:
        success = monitor_continuous(args.interval, args.max_attempts)
        sys.exit(0 if success else 1)
    else:
        result = check_deployment_status()
        if result is True:
            sys.exit(0)
        elif result is False:
            sys.exit(1)
        else:
            sys.exit(2)
