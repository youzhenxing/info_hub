#!/bin/bash
# ============================================
# TrendRadar 一键部署脚本
#
# 自动执行完整的部署流程：
# 1. 检查代码状态
# 2. 执行部署（自动确认）
# 3. 切换到新版本
# 4. 验证部署
# ============================================

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_BASE="/home/zxy/Documents/code/TrendRadar"
cd "$DEV_BASE"

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  TrendRadar 一键部署${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# ============================================
# Step 1: 检查Git状态
# ============================================
echo -e "${BLUE}[Step 1/5] 检查代码状态...${NC}"

if git diff --quiet && git diff --cached --quiet; then
    echo -e "${YELLOW}⚠️  没有检测到代码修改${NC}"
    echo -e "${YELLOW}   如果是重新部署已有版本，继续执行${NC}"
    echo -e "${YELLOW}   如果要部署新代码，请先提交代码${NC}"
    echo ""
    read -p "是否继续部署? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${CYAN}✋ 已取消${NC}"
        exit 0
    fi
else
    echo -e "${GREEN}✓ 检测到代码修改${NC}"

    # 检查是否有未提交的修改
    UNCOMMITTED=$(git diff --name-only | wc -l)
    if [ $UNCOMMITTED -gt 0 ]; then
        echo -e "${YELLOW}⚠️  有 $UNCOMMITTED 个文件未提交${NC}"
        echo ""
        echo -e "${CYAN}未提交的文件:${NC}"
        git diff --name-only | sed 's/^/   - /'
        echo ""
        echo -e "${RED}❌ 请先提交代码再部署${NC}"
        echo -e "${CYAN}执行: git add <files> && git commit${NC}"
        exit 1
    fi
fi

echo ""

# ============================================
# Step 2: 读取当前版本
# ============================================
echo -e "${BLUE}[Step 2/5] 读取版本信息...${NC}"

if [ ! -f "version" ]; then
    echo -e "${RED}❌ 版本文件不存在: version${NC}"
    exit 1
fi

VERSION=$(cat version | tr -d '[:space:]')
echo -e "${GREEN}✓ 当前版本: ${YELLOW}v${VERSION}${NC}"
echo ""

# ============================================
# Step 3: 执行部署（自动确认）
# ============================================
echo -e "${BLUE}[Step 3/5] 执行部署...${NC}"
echo -e "${CYAN}提示: 将使用自动确认模式，覆盖已存在的版本${NC}"
echo ""

cd "$SCRIPT_DIR"
yes "y" | bash deploy.sh

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 部署失败${NC}"
    exit 1
fi

echo ""

# ============================================
# Step 4: 切换到新版本
# ============================================
echo -e "${BLUE}[Step 4/5] 切换到新版本...${NC}"

# 检查trend命令是否可用
if command -v trend &> /dev/null; then
    yes "y" | trend update "v${VERSION}"
    echo -e "${GREEN}✓ 已切换到 v${VERSION}${NC}"
else
    echo -e "${YELLOW}⚠️  trend 命令不可用，请手动切换版本${NC}"
    echo -e "${CYAN}执行: cd /home/zxy/Documents/install/trendradar/current && docker compose down${NC}"
    echo -e "${CYAN}     cd /home/zxy/Documents/install/trendradar/releases/v${VERSION} && docker compose up -d${NC}"
fi

echo ""

# ============================================
# Step 5: 验证部署
# ============================================
echo -e "${BLUE}[Step 5/5] 验证部署...${NC}"

VERIFY_SCRIPT="$SCRIPT_DIR/verify-production.sh"
if [ -f "$VERIFY_SCRIPT" ]; then
    bash "$VERIFY_SCRIPT"
else
    echo -e "${YELLOW}⚠️  验证脚本不存在: $VERIFY_SCRIPT${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ 一键部署完成！${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}💡 下一步:${NC}"
echo -e "   1. ${GREEN}git add .deployed_version${NC}  # 添加部署标记"
echo -e "   2. ${GREEN}git commit${NC}                 # 提交代码"
echo ""
