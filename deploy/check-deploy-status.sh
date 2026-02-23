#!/bin/bash
# ============================================
# TrendRadar 部署状态检查工具
#
# 显示：
# 1. 当前代码版本
# 2. 已部署版本
# 3. 版本一致性状态
# 4. 待提交的修改
# ============================================

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_ROOT="/home/zxy/Documents/code/TrendRadar"
PROD_BASE="/home/zxy/Documents/install/trendradar"

cd "$PROJECT_ROOT"

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  TrendRadar 部署状态${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# ============================================
# 1. 代码版本
# ============================================
echo -e "${CYAN}📦 代码版本:${NC}"

if [ -f "$PROJECT_ROOT/version" ]; then
    CODE_VERSION=$(cat "$PROJECT_ROOT/version" | tr -d '[:space:]')
    echo -e "  版本号: ${YELLOW}$CODE_VERSION${NC}"
else
    echo -e "  ${RED}❌ 版本文件不存在${NC}"
fi

# 最后一次提交时间
LAST_COMMIT=$(git log -1 --format="%ci" 2>/dev/null || echo "unknown")
echo -e "  最后提交: $LAST_COMMIT"

echo ""

# ============================================
# 2. 部署版本
# ============================================
echo -e "${CYAN}🚀 部署版本:${NC}"

DEPLOYMENT_MARKER="$PROJECT_ROOT/.deployed_version"
if [ -f "$DEPLOYMENT_MARKER" ]; then
    DEPLOYED_VERSION=$(grep "^version:" "$DEPLOYMENT_MARKER" | awk '{print $2}' | tr -d '"' | tr -d "'")
    DEPLOYED_AT=$(grep "^deployed_at:" "$DEPLOYMENT_MARKER" | awk '{print $2}' | tr -d '"')

    echo -e "  版本号: ${YELLOW}$DEPLOYED_VERSION${NC}"
    echo -e "  部署时间: $DEPLOYED_AT"
else
    echo -e "  ${YELLOW}⚠️  未找到部署标记（可能从未部署）${NC}"
fi

# 生产环境当前版本
if [ -f "$PROD_BASE/versions/manifest.yaml" ]; then
    PROD_VERSION=$(grep "^current_version:" "$PROD_BASE/versions/manifest.yaml" | awk '{print $2}' | tr -d '"' | tr -d "'")
    echo -e "  生产环境: ${YELLOW}$PROD_VERSION${NC}"
fi

echo ""

# ============================================
# 3. 版本一致性检查
# ============================================
echo -e "${CYAN}🔍 版本一致性:${NC}"

if [ -n "$CODE_VERSION" ] && [ -n "$DEPLOYED_VERSION" ]; then
    CODE_VER_NUM=$(echo "$CODE_VERSION" | sed 's/^v//')
    DEPLOYED_VER_NUM=$(echo "$DEPLOYED_VERSION" | sed 's/^v//')

    if [ "$CODE_VER_NUM" = "$DEPLOYED_VER_NUM" ]; then
        echo -e "  ${GREEN}✓ 代码版本与部署版本一致${NC}"
    else
        echo -e "  ${RED}✗ 版本不一致！${NC}"
        echo -e "    代码版本: $CODE_VER_NUM"
        echo -e "    部署版本: $DEPLOYED_VER_NUM"
        echo -e "    ${YELLOW}建议: 执行 'cd deploy && ./quick-deploy.sh'${NC}"
    fi
fi

echo ""

# ============================================
# 4. Git状态
# ============================================
echo -e "${CYAN}📝 Git状态:${NC}"

if git diff --quiet && git diff --cached --quiet; then
    echo -e "  ${GREEN}✓ 工作区干净${NC}"
else
    echo -e "  ${YELLOW}⚠️  有未提交的修改${NC}"

    MODIFIED_COUNT=$(git diff --name-only | wc -l)
    STAGED_COUNT=$(git diff --name-only --cached | wc -l)

    echo -e "    未暂存: $MODIFIED_COUNT 个文件"
    echo -e "    已暂存: $STAGED_COUNT 个文件"

    # 检查是否影响运行时
    AFFECTS_RUNTIME=$(git diff --name-only | grep -v ".deployed_version\|CHANGELOG.md\|CLAUDE.md" | grep -E "^(trendradar|docker|config|wechat)/" || true)

    if [ -n "$AFFECTS_RUNTIME" ]; then
        echo -e "    ${RED}✗ 包含影响运行时的代码修改${NC}"
        echo -e "    ${YELLOW}需要重新部署后才能提交${NC}"
    fi
fi

echo ""

# ============================================
# 5. 容器状态
# ============================================
echo -e "${CYAN}🐳 容器状态:${NC}"

if docker ps --format "{{.Names}}" | grep -q "^trendradar-prod$"; then
    CONTAINER_VERSION=$(docker exec trendradar-prod printenv APP_VERSION 2>/dev/null || echo "unknown")
    echo -e "  容器运行: ${GREEN}✓${NC}"
    echo -e "  容器版本: ${YELLOW}$CONTAINER_VERSION${NC}"
else
    echo -e "  ${RED}✗ 容器未运行${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""
