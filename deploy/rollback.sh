#!/bin/bash

# TrendRadar 版本回退脚本
# 回退到上一个版本

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# 配置
PROD_BASE="/home/zxy/Documents/install/trendradar"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 加载版本管理工具
source "$SCRIPT_DIR/version-manager.sh"

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  TrendRadar 版本回退${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# 检查生产环境
if ! check_production_initialized; then
    echo -e "${RED}❌ 错误：生产环境未初始化${NC}"
    exit 1
fi

# 获取当前版本和上一版本
CURRENT_VERSION=$(get_current_version)
PREVIOUS_VERSION=$(get_previous_version)

if [ -z "$CURRENT_VERSION" ] || [ "$CURRENT_VERSION" = "null" ]; then
    echo -e "${RED}❌ 错误：无法获取当前版本${NC}"
    exit 1
fi

if [ -z "$PREVIOUS_VERSION" ] || [ "$PREVIOUS_VERSION" = "null" ]; then
    echo -e "${RED}❌ 错误：没有可回退的版本${NC}"
    echo -e "${CYAN}💡 查看版本历史: trend versions${NC}"
    exit 1
fi

echo -e "${CYAN}⚠️  准备回退版本${NC}"
echo -e "   当前版本: ${YELLOW}v${CURRENT_VERSION}${NC}"
echo -e "   回退到: ${YELLOW}v${PREVIOUS_VERSION}${NC}"
echo ""

# 确认操作
echo -e "${YELLOW}❓ 确认要回退到版本 v${PREVIOUS_VERSION}吗？(y/N)${NC}"
read -r confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}✋ 已取消${NC}"
    exit 0
fi

# 调用 update.sh 执行实际的版本切换
echo -e "${CYAN}🔄 执行回退操作...${NC}"
echo ""

"$SCRIPT_DIR/update.sh" "$PREVIOUS_VERSION"

# 更新部署历史为回退操作
add_deployment_history "$PREVIOUS_VERSION" "rollback" "$CURRENT_VERSION" "true"

echo -e "${GREEN}✅ 已成功回退到版本 v${PREVIOUS_VERSION}${NC}"
