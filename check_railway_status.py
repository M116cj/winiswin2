"""
Railway服务状态检查工具
用于诊断Railway上的交易机器人为什么自动下线
"""

import os
import sys
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Optional

class RailwayStatusChecker:
    """Railway状态检查器"""
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化检查器
        
        Args:
            token: Railway API Token（可选，从环境变量读取）
        """
        self.token = token or os.getenv('RAILWAY_TOKEN')
        self.api_url = "https://backboard.railway.app/graphql/v2"
    
    async def check_service_status(self, project_id: str) -> Dict:
        """
        检查服务状态
        
        Args:
            project_id: Railway项目ID
        
        Returns:
            Dict: 服务状态信息
        """
        if not self.token:
            return {
                'error': '未设置RAILWAY_TOKEN环境变量',
                'solution': '请在环境变量中设置RAILWAY_TOKEN'
            }
        
        query = """
        query($projectId: String!) {
          project(id: $projectId) {
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
                        createdAt
                        staticUrl
                      }
                    }
                  }
                }
              }
            }
            estimatedUsage {
              current
              estimated
            }
          }
        }
        """
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json={
                        "query": query,
                        "variables": {"projectId": project_id}
                    },
                    headers=headers
                ) as response:
                    data = await response.json()
                    
                    if 'errors' in data:
                        return {
                            'error': 'API调用失败',
                            'details': data['errors']
                        }
                    
                    return self._parse_status(data)
        
        except Exception as e:
            return {
                'error': f'网络错误: {str(e)}',
                'solution': '检查网络连接或Railway API状态'
            }
    
    def _parse_status(self, data: Dict) -> Dict:
        """解析API响应"""
        try:
            project = data['data']['project']
            services = project['services']['edges']
            usage = project.get('estimatedUsage', {})
            
            result = {
                'project_name': project['name'],
                'timestamp': datetime.now().isoformat(),
                'services': [],
                'usage': {
                    'current': usage.get('current', 0) / 100,  # 转换为美元
                    'estimated': usage.get('estimated', 0) / 100
                },
                'status_summary': {}
            }
            
            for service in services:
                node = service['node']
                deployment = None
                
                if node['deployments']['edges']:
                    deployment = node['deployments']['edges'][0]['node']
                
                service_info = {
                    'name': node['name'],
                    'id': node['id'],
                    'status': deployment['status'] if deployment else 'NO_DEPLOYMENT',
                    'created_at': deployment['createdAt'] if deployment else None,
                    'url': deployment.get('staticUrl') if deployment else None
                }
                
                result['services'].append(service_info)
            
            # 生成状态摘要
            statuses = [s['status'] for s in result['services']]
            result['status_summary'] = {
                'total_services': len(statuses),
                'running': statuses.count('SUCCESS'),
                'failed': statuses.count('FAILED'),
                'crashed': statuses.count('CRASHED'),
                'building': statuses.count('BUILDING')
            }
            
            return result
        
        except Exception as e:
            return {
                'error': f'解析响应失败: {str(e)}',
                'raw_data': data
            }
    
    def print_status(self, status: Dict):
        """打印格式化的状态信息"""
        print("\n" + "=" * 60)
        print("🚂 Railway服务状态检查")
        print("=" * 60)
        
        if 'error' in status:
            print(f"\n❌ 错误: {status['error']}")
            if 'solution' in status:
                print(f"💡 解决方案: {status['solution']}")
            if 'details' in status:
                print(f"详细信息: {status['details']}")
            return
        
        print(f"\n📋 项目: {status['project_name']}")
        print(f"🕒 检查时间: {status['timestamp']}")
        
        print(f"\n💰 使用情况:")
        print(f"   当前消耗: ${status['usage']['current']:.2f}")
        print(f"   预估月费: ${status['usage']['estimated']:.2f}")
        
        # 检查额度是否即将用尽
        if status['usage']['current'] >= 4.50:
            print(f"   ⚠️  警告: 免费额度即将用尽！")
        
        print(f"\n📊 服务状态:")
        summary = status['status_summary']
        print(f"   总服务数: {summary['total_services']}")
        print(f"   ✅ 运行中: {summary['running']}")
        print(f"   ❌ 失败: {summary['failed']}")
        print(f"   💥 崩溃: {summary['crashed']}")
        print(f"   🔨 构建中: {summary['building']}")
        
        print(f"\n📦 服务详情:")
        for service in status['services']:
            status_emoji = {
                'SUCCESS': '✅',
                'FAILED': '❌',
                'CRASHED': '💥',
                'BUILDING': '🔨',
                'NO_DEPLOYMENT': '⚪'
            }.get(service['status'], '❓')
            
            print(f"\n   {status_emoji} {service['name']}")
            print(f"      状态: {service['status']}")
            if service['created_at']:
                print(f"      部署时间: {service['created_at']}")
            if service['url']:
                print(f"      URL: {service['url']}")
        
        # 诊断建议
        print(f"\n🔍 诊断建议:")
        
        if summary['failed'] > 0 or summary['crashed'] > 0:
            print("   ❌ 发现失败/崩溃的服务")
            print("   💡 建议:")
            print("      1. 查看Railway日志: railway logs")
            print("      2. 检查代码错误")
            print("      3. 尝试重新部署: railway up")
        
        if status['usage']['current'] >= 4.50:
            print("   ⚠️  免费额度即将用尽")
            print("   💡 建议:")
            print("      1. 升级到付费计划")
            print("      2. 优化资源使用")
            print("      3. 减少API调用频率")
        
        if summary['running'] == 0:
            print("   ⚪ 没有运行中的服务")
            print("   💡 建议:")
            print("      1. 检查是否有部署")
            print("      2. 尝试手动部署")
            print("      3. 检查Railway账户状态")
        
        print("\n" + "=" * 60)


async def main():
    """主函数"""
    print("🚀 Railway交易机器人状态检查工具")
    print("=" * 60)
    
    # 从命令行或环境变量获取配置
    token = os.getenv('RAILWAY_TOKEN')
    project_id = os.getenv('RAILWAY_PROJECT_ID')
    
    if not token:
        print("\n❌ 错误: 未找到RAILWAY_TOKEN环境变量")
        print("\n📝 设置方法:")
        print("   1. 登录 https://railway.app/")
        print("   2. Account Settings → Tokens → Create Token")
        print("   3. 复制token并设置:")
        print("      export RAILWAY_TOKEN='your-token-here'")
        sys.exit(1)
    
    if not project_id:
        print("\n❌ 错误: 未找到RAILWAY_PROJECT_ID环境变量")
        print("\n📝 获取方法:")
        print("   1. 打开Railway项目页面")
        print("   2. 从URL中复制项目ID:")
        print("      https://railway.app/project/{PROJECT_ID}")
        print("   3. 设置环境变量:")
        print("      export RAILWAY_PROJECT_ID='your-project-id'")
        sys.exit(1)
    
    checker = RailwayStatusChecker(token)
    
    print(f"\n🔍 正在检查项目: {project_id}")
    
    status = await checker.check_service_status(project_id)
    checker.print_status(status)
    
    # 持续监控模式（可选）
    if '--watch' in sys.argv:
        print("\n👁️  进入持续监控模式（每5分钟检查一次）")
        print("   按 Ctrl+C 退出\n")
        
        try:
            while True:
                await asyncio.sleep(300)  # 5分钟
                print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} - 重新检查状态...")
                status = await checker.check_service_status(project_id)
                checker.print_status(status)
        except KeyboardInterrupt:
            print("\n\n👋 监控已停止")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 程序已退出")
