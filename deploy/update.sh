#!/bin/bash

# TrendRadar 版本更新脚本
# 将生产环境切换到指定版本

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

# 参数
TARGET_VERSION="$1"

if [ -z "$TARGET_VERSION" ]; then
    echo -e "${RED}❌ 错误：请指定目标版本${NC}"
    echo -e "${CYAN}用法: $0 <version>${NC}"
    echo -e "${CYAN}示例: $0 5.4.0${NC}"
    exit 1
fi

# 去掉版本号前的 v
TARGET_VERSION="${TARGET_VERSION#v}"

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  TrendRadar 版本更新${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# 检查生产环境
if ! check_production_initialized; then
    echo -e "${RED}❌ 错误：生产环境未初始化${NC}"
    exit 1
fi

# 检查目标版本是否存在
if ! version_exists "$TARGET_VERSION"; then
    echo -e "${RED}❌ 错误：版本 v${TARGET_VERSION} 不存在${NC}"
    echo -e "${CYAN}💡 查看可用版本: trend versions${NC}"
    exit 1
fi

# 获取当前版本
CURRENT_VERSION=$(get_current_version)

if [ "$CURRENT_VERSION" = "$TARGET_VERSION" ]; then
    echo -e "${YELLOW}⚠️  当前已是版本 v${TARGET_VERSION}${NC}"
    exit 0
fi

echo -e "${CYAN}🔄 更新版本${NC}"
echo -e "   当前版本: ${YELLOW}v${CURRENT_VERSION}${NC}"
echo -e "   目标版本: ${YELLOW}v${TARGET_VERSION}${NC}"
echo ""

# 确认操作
echo -e "${YELLOW}❓ 确认要切换到版本 v${TARGET_VERSION}吗？(y/N)${NC}"
read -r confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}✋ 已取消${NC}"
    exit 0
fi

# 1. 停止当前容器
echo -e "${CYAN}🛑 停止当前服务...${NC}"

if docker ps --format "{{.Names}}" | grep -q "trendradar-prod"; then
    cd "$PROD_BASE/current" 2>/dev/null && docker compose down 2>/dev/null || true
    echo -e "${GREEN}  ✓ 服务已停止${NC}"
else
    echo -e "${YELLOW}  ℹ️  服务未运行${NC}"
fi

# 2. 更新 current 软链接
echo -e "${CYAN}🔗 更新版本链接...${NC}"

cd "$PROD_BASE"
rm -f current
ln -sfn "releases/v${TARGET_VERSION}" current

echo -e "${GREEN}  ✓ 链接已更新${NC}"
echo ""

# 3. 更新版本清单
update_current_version "$TARGET_VERSION"

# 4. 启动新版本
echo -e "${CYAN}🚀 启动新版本服务...${NC}"

cd "$PROD_BASE/current"
docker compose up -d

echo -e "${GREEN}  ✓ 服务已启动${NC}"
echo ""

# 5. 添加部署历史
add_deployment_history "$TARGET_VERSION" "updated" "$CURRENT_VERSION" "true"

# 等待容器启动（留出 entrypoint 配置摘要输出的时间）
sleep 5

# 6. 检查服务状态
echo -e "${CYAN}🔍 检查服务状态...${NC}"

if docker ps --format "{{.Names}}" | grep -q "trendradar-prod"; then
    docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "NAMES|trendradar"
    echo ""
    echo -e "${GREEN}  ✓ 服务运行正常${NC}"
else
    echo -e "${RED}  ❌ 服务启动失败${NC}"
    echo -e "${CYAN}  💡 查看日志: docker logs trendradar-prod${NC}"
fi

# 完成
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ 版本更新完成！${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}📊 当前状态:${NC}"
echo -e "   运行版本: ${YELLOW}v${TARGET_VERSION}${NC}"
echo -e "   上一版本: ${YELLOW}v${CURRENT_VERSION}${NC}"
echo ""

# 7. 自动模块验证（触发各模块完整流程并确认结果）
echo -e "${CYAN}🔍 运行模块验证...${NC}"
if bash "$SCRIPT_DIR/verify-production.sh" "${2:-}"; then
    echo -e "${GREEN}  ✓ 模块验证通过${NC}"
else
    echo -e "${YELLOW}  ⚠️  模块验证有告警，详见上方输出（不阻塞更新）${NC}"
fi
echo ""

# 8. 发送更新通知邮件
echo -e "${CYAN}📧 发送更新通知邮件...${NC}"
if [ -f "$SCRIPT_DIR/send_deploy_notification.py" ]; then
    python3 "$SCRIPT_DIR/send_deploy_notification.py" "$TARGET_VERSION" 2>/dev/null && \
        echo -e "${GREEN}  ✓ 更新通知邮件已发送${NC}" || \
        echo -e "${YELLOW}  ⚠️ 邮件发送失败，但不影响更新${NC}"
else
    echo -e "${YELLOW}  ⚠️ 通知脚本不存在，跳过邮件发送${NC}"
fi
echo ""

echo -e "${CYAN}💡 有用的命令:${NC}"
echo -e "   查看日志: ${YELLOW}docker logs trendradar-prod -f${NC}"
echo -e "   查看状态: ${YELLOW}trend production${NC}"
echo -e "   回退版本: ${YELLOW}trend rollback${NC}"
echo ""
