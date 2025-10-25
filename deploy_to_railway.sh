#!/bin/bash

# Railway 自动部署脚本
# 确保修复后的代码正确部署到 Railway

set -e

echo "============================================================"
echo "🚀 Railway 自动部署脚本"
echo "============================================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 步骤 1: 验证关键修复
echo -e "\n${YELLOW}📋 步骤 1: 验证关键修复${NC}"
echo "检查 get_24h_tickers 函数..."

if grep -q "async def get_24h_tickers" src/clients/binance_client.py; then
    echo -e "${GREEN}✅ get_24h_tickers 函数存在${NC}"
else
    echo -e "${RED}❌ 错误: get_24h_tickers 函数不存在！${NC}"
    echo "请确保已经添加了该函数到 src/clients/binance_client.py"
    exit 1
fi

# 步骤 2: 检查版本标识
echo -e "\n${YELLOW}📋 步骤 2: 检查版本标识${NC}"

if grep -q "2025-10-25-v2.0" src/main.py; then
    echo -e "${GREEN}✅ 版本标识正确${NC}"
else
    echo -e "${RED}❌ 警告: 版本标识不正确${NC}"
fi

# 步骤 3: 运行系统验证
echo -e "\n${YELLOW}📋 步骤 3: 运行系统验证${NC}"

if command -v python3 &> /dev/null; then
    python3 verify_system.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 系统验证通过${NC}"
    else
        echo -e "${RED}❌ 系统验证失败${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Python3 不可用，跳过系统验证${NC}"
fi

# 步骤 4: Git 状态检查
echo -e "\n${YELLOW}📋 步骤 4: Git 状态检查${NC}"

echo "当前 Git 状态:"
git status --short

# 步骤 5: 用户确认
echo -e "\n${YELLOW}📋 步骤 5: 确认部署${NC}"
echo "即将执行以下操作:"
echo "  1. 提交所有更改到 Git"
echo "  2. 推送到远程仓库"
echo "  3. 触发 Railway 重新部署"
echo ""
read -p "是否继续？(y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}已取消部署${NC}"
    exit 0
fi

# 步骤 6: 提交和推送
echo -e "\n${YELLOW}📋 步骤 6: 提交和推送代码${NC}"

git add .
git commit -m "🚨 Critical fix: Add get_24h_tickers API for volatility scanning

- Added missing get_24h_tickers() function to BinanceClient
- This fixes the fallback mode issue where system only fetched prices
- Now properly scans 200 high volatility pairs with full analysis
- Version: 2025-10-25-v2.0"

echo -e "${GREEN}✅ 代码已提交${NC}"

git push origin main

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 代码已推送到 GitHub${NC}"
else
    echo -e "${RED}❌ 推送失败${NC}"
    exit 1
fi

# 步骤 7: Railway 部署说明
echo -e "\n${YELLOW}📋 步骤 7: Railway 部署${NC}"
echo ""
echo "GitHub 推送成功！"
echo ""
echo "接下来："
echo "  1. Railway 会自动检测到新的推送（如果启用了自动部署）"
echo "  2. 或者手动登录 Railway 控制台点击 'Redeploy'"
echo ""
echo "Railway 控制台: https://railway.app/"
echo "项目: skillful-perfection"
echo "服务: winiswin2"
echo ""

# 步骤 8: 监控部署
echo -e "\n${YELLOW}📋 步骤 8: 监控部署（可选）${NC}"
echo ""
read -p "是否启动自动监控？(y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v python3 &> /dev/null && [ -n "$RAILWAY_TOKEN" ]; then
        echo "开始监控 Railway 部署状态..."
        python3 monitor_railway.py --monitor --interval 10 --max-attempts 30
    else
        echo -e "${YELLOW}⚠️  需要 Python3 和 RAILWAY_TOKEN 环境变量${NC}"
        echo "请手动运行: python3 monitor_railway.py --monitor"
    fi
fi

echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}✅ 部署流程完成！${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "验证清单（在 Railway 日志中查找）:"
echo "  ✓ 📌 代碼版本: 2025-10-25-v2.0"
echo "  ✓ 🔍 開始掃描市場，目標選擇前 200 個高波動率交易對"
echo "  ✓ ✅ 市場掃描完成: 從 X 個交易對中選擇波動率最高的前 200 個"
echo "  ✓ 📈 波動率最高的前10個交易對:"
echo "  ✓ 🔍 使用 32 核心並行分析 200 個高波動率交易對"
echo "  ✓ 開始批量分析 200 個交易對"
echo "  ✓ ✅ 批量分析完成: 分析 X 個交易對, 生成 Y 個信號"
echo ""
echo "如果看到这些日志 = 修复成功！ 🎉"
echo ""
