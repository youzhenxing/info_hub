#!/bin/bash

# TrendRadar 版本发布脚本
# 从开发环境构建并发布新版本到生产环境

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# 配置
DEV_BASE="/home/zxy/Documents/code/TrendRadar"
PROD_BASE="/home/zxy/Documents/install/trendradar"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 加载版本管理工具
source "$SCRIPT_DIR/version-manager.sh"

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  TrendRadar 版本发布${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# ============================================
# 部署前检查（强制执行）
# ============================================
PRE_CHECK_SCRIPT="$SCRIPT_DIR/pre-deploy-check.sh"
if [ -f "$PRE_CHECK_SCRIPT" ]; then
    echo -e "${CYAN}🔍 执行部署前检查...${NC}"
    echo ""
    if ! bash "$PRE_CHECK_SCRIPT"; then
        echo ""
        echo -e "${RED}❌ 部署前检查失败，请修复问题后重试${NC}"
        exit 1
    fi
    echo ""
else
    echo -e "${YELLOW}⚠️  警告：部署前检查脚本不存在: $PRE_CHECK_SCRIPT${NC}"
fi

# 检查开发环境
if [ ! -d "$DEV_BASE" ]; then
    echo -e "${RED}❌ 错误：开发环境不存在: $DEV_BASE${NC}"
    exit 1
fi

# 检查生产环境
if ! check_production_initialized; then
    echo -e "${RED}❌ 错误：生产环境未初始化${NC}"
    echo -e "${CYAN}💡 请先运行: ./deploy/init-production.sh${NC}"
    exit 1
fi

# 读取版本号
cd "$DEV_BASE"

if [ ! -f "version" ]; then
    echo -e "${RED}❌ 错误：版本文件不存在: $DEV_BASE/version${NC}"
    exit 1
fi

OLD_VERSION=$(cat version | tr -d '[:space:]')
MCP_VERSION=$(cat version_mcp | tr -d '[:space:]' 2>/dev/null || echo "unknown")

# 自动递增版本号（patch 版本）
VERSION=$(bump_version "$OLD_VERSION")
echo -e "${CYAN}🔄 自动递增版本号: ${YELLOW}v${OLD_VERSION} → v${VERSION}${NC}"

# 更新版本文件
echo "$VERSION" > version
echo -e "${GREEN}  ✓ 版本文件已更新${NC}"
echo ""

echo -e "${CYAN}📦 准备发布版本: ${YELLOW}v${VERSION}${NC}"
echo -e "${CYAN}   MCP 版本: ${YELLOW}v${MCP_VERSION}${NC}"
echo ""

# 检查版本是否已存在（跳过确认，直接覆盖）
if version_exists "$VERSION"; then
    echo -e "${YELLOW}⚠️  版本 v${VERSION} 已存在，将覆盖${NC}"
fi

# 1. 构建 Docker 镜像
echo -e "${CYAN}🔨 构建 Docker 镜像...${NC}"

# 构建主镜像
echo -e "   构建主镜像: trendradar:v${VERSION}"
docker build -t "trendradar:v${VERSION}" -f docker/Dockerfile . --quiet

# 构建 MCP 镜像
echo -e "   构建 MCP 镜像: trendradar-mcp:v${MCP_VERSION}"
docker build -t "trendradar-mcp:v${MCP_VERSION}" -f docker/Dockerfile.mcp . --quiet

echo -e "${GREEN}  ✓ Docker 镜像构建完成${NC}"
echo ""

# 2. 创建版本目录
RELEASE_DIR="$PROD_BASE/releases/v${VERSION}"

echo -e "${CYAN}📁 创建版本目录...${NC}"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# 3. 复制必要文件
echo -e "${CYAN}📋 复制文件...${NC}"

# 复制核心代码
cp -r trendradar "$RELEASE_DIR/"
cp -r mcp_server "$RELEASE_DIR/"
cp -r docker "$RELEASE_DIR/"

# 复制配置文件到生产环境（确保最新配置生效）
echo -e "   复制配置文件到生产环境..."
mkdir -p "$PROD_BASE/shared/config"
cp -r config/*.yaml "$PROD_BASE/shared/config/"
echo -e "${GREEN}  ✓ 配置文件同步完成${NC}"

# 复制版本文件
cp version "$RELEASE_DIR/"
cp version_mcp "$RELEASE_DIR/"
cp version_configs "$RELEASE_DIR/"

# 复制依赖文件
cp requirements.txt "$RELEASE_DIR/"

# 复制共享脚本到生产环境
echo -e "   复制共享脚本到生产环境..."
cp docker/run_investment.py "$PROD_BASE/shared/run_investment.py"
cp docker/daily_report.py "$PROD_BASE/shared/daily_report.py"
cp docker/run_community.py "$PROD_BASE/shared/run_community.py"
cp docker/entrypoint.sh "$PROD_BASE/shared/entrypoint.sh"
chmod +x "$PROD_BASE/shared/entrypoint.sh"
cp docker/bootstrap.py "$PROD_BASE/shared/bootstrap.py"

# 复制 shared Python 包（email_renderer + 邮件模板）到生产环境
echo -e "   复制 shared 模块到生产环境..."
rm -rf "$PROD_BASE/shared/shared_pkg/email_templates"
cp -r shared/email_templates "$PROD_BASE/shared/shared_pkg/"

# 复制 prompts 提示词到生产环境
echo -e "   复制 prompts 到生产环境..."
cp -r prompts "$PROD_BASE/shared/prompts"

# 同步 .env 配置到生产环境
echo -e "   同步 .env 配置到生产环境..."
cp "$DEV_BASE/agents/.env" "$PROD_BASE/shared/.env"

# 校验生产 .env 中的必选配置
REQUIRED_VARS="EMAIL_FROM EMAIL_PASSWORD EMAIL_TO EMAIL_SMTP_SERVER EMAIL_SMTP_PORT"
MISSING=""
for VAR in $REQUIRED_VARS; do
    VAL=$(grep "^${VAR}=" "$PROD_BASE/shared/.env" | cut -d= -f2-)
    if [ -z "$VAL" ]; then
        MISSING="$MISSING $VAR"
    fi
done
if [ -n "$MISSING" ]; then
    echo -e "${RED}❌ 部署中断：生产 .env 中以下必选配置为空:$MISSING${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ .env 配置同步和校验通过${NC}"

# 追加 APP_VERSION 到 .env（供 wechat-service 等共享容器读取）
echo "APP_VERSION=${VERSION}" >> "$PROD_BASE/shared/.env"

# 读取 CRON_SCHEDULE（需要在 docker-compose.yml 中显式设置）
CRON_SCHEDULE=$(grep "^CRON_SCHEDULE=" "$PROD_BASE/shared/.env" | cut -d= -f2-)
if [ -z "$CRON_SCHEDULE" ]; then
    echo -e "${YELLOW}  ⚠️  警告：CRON_SCHEDULE 未设置，使用默认值 0 */6 * * *${NC}"
    CRON_SCHEDULE="0 */6 * * *"
fi
echo -e "   主程序定时: ${GREEN}${CRON_SCHEDULE}${NC}"

echo -e "${GREEN}  ✓ 文件复制完成${NC}"
echo ""

# 4. 生成生产环境 docker-compose.yml
echo -e "${CYAN}🐳 生成 Docker Compose 配置...${NC}"

cat > "$RELEASE_DIR/docker-compose.yml" << EOF
services:
  trendradar:
    image: trendradar:v${VERSION}
    container_name: trendradar-prod
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
    env_file:
      - $PROD_BASE/shared/.env

    ports:
      - "127.0.0.1:\${WEBSERVER_PORT:-8080}:\${WEBSERVER_PORT:-8080}"

    volumes:
      - $PROD_BASE/shared/config:/app/config:ro
      - $PROD_BASE/shared/prompts:/app/prompts:ro
      - $PROD_BASE/shared/output:/app/output
      - $PROD_BASE/shared/run_investment.py:/app/run_investment.py:ro
      - $PROD_BASE/shared/daily_report.py:/app/daily_report.py:ro
      - $PROD_BASE/shared/run_community.py:/app/run_community.py:ro
      - $PROD_BASE/shared/shared_init.py:/app/shared/__init__.py:ro
      - $PROD_BASE/shared/shared_pkg/lib:/app/shared/lib:ro
      - $PROD_BASE/shared/shared_pkg/email_templates:/app/shared/email_templates:ro
      - $PROD_BASE/shared/entrypoint.sh:/entrypoint.sh:ro
      - $PROD_BASE/shared/bootstrap.py:/app/bootstrap.py:ro
      # 版本标记文件（用于容器启动验证）
      - $DEV_BASE/.deployed_version:/app/.deployed_version:ro

    environment:
      - TZ=Asia/Shanghai
      - APP_VERSION=${VERSION}
      - CRON_SCHEDULE=${CRON_SCHEDULE}

  trendradar-mcp:
    image: trendradar-mcp:v${MCP_VERSION}
    container_name: trendradar-mcp-prod
    restart: unless-stopped
    env_file:
      - $PROD_BASE/shared/.env

    ports:
      - "127.0.0.1:3333:3333"

    volumes:
      - $PROD_BASE/shared/config:/app/config:ro
      - $PROD_BASE/shared/output:/app/output

    environment:
      - TZ=Asia/Shanghai
EOF

echo -e "${GREEN}  ✓ Docker Compose 配置已生成${NC}"
echo ""

# 5. 创建版本信息文件
echo -e "${CYAN}📝 创建版本记录...${NC}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")

# 读取最近的 git commit 信息作为变更说明
SUMMARY="版本 v${VERSION}"
if [ -d "$DEV_BASE/.git" ]; then
    SUMMARY=$(git -C "$DEV_BASE" log -1 --pretty=format:"%s" 2>/dev/null || echo "版本 v${VERSION}")
fi

# 创建详细版本记录
create_version_record "$VERSION" "trendradar:v${VERSION}" "trendradar-mcp:v${MCP_VERSION}" "$SUMMARY"

# 更新 manifest.yaml
add_version_to_manifest "$VERSION" "trendradar:v${VERSION}" "$TIMESTAMP"

# 添加部署历史
add_deployment_history "$VERSION" "deployed" "" "true"

echo -e "${GREEN}  ✓ 版本记录已创建${NC}"
echo ""

# 完成
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ 版本发布完成！${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}📦 版本信息:${NC}"
echo -e "   版本号: ${YELLOW}v${VERSION}${NC}"
echo -e "   Docker 镜像: ${YELLOW}trendradar:v${VERSION}${NC}"
echo -e "   安装路径: ${YELLOW}$RELEASE_DIR${NC}"
echo ""

# 6. 发送部署通知邮件
echo -e "${CYAN}📧 发送部署通知邮件...${NC}"
if [ -f "$SCRIPT_DIR/send_deploy_notification.py" ]; then
    python3 "$SCRIPT_DIR/send_deploy_notification.py" "$VERSION" 2>/dev/null && \
        echo -e "${GREEN}  ✓ 部署通知邮件已发送${NC}" || \
        echo -e "${YELLOW}  ⚠️ 邮件发送失败，但不影响部署${NC}"
else
    echo -e "${YELLOW}  ⚠️ 通知脚本不存在，跳过邮件发送${NC}"
fi
echo ""

# 7. 更新代码仓库的部署标记（强制部署流程机制）
echo -e "${CYAN}📋 更新部署标记...${NC}"
DEPLOYMENT_MARKER="$DEV_BASE/.deployed_version"
cat > "$DEPLOYMENT_MARKER" << EOF
version: "$VERSION"
deployed_at: "$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")"
deployed_by: "$(whoami)"
commit_hash: "$(cd "$DEV_BASE" && git rev-parse HEAD 2>/dev/null || echo 'unknown')"
deployment_path: "$RELEASE_DIR"
EOF
echo -e "${GREEN}  ✓ 部署标记已更新: $DEPLOYMENT_MARKER${NC}"
echo ""

# 8. 自动提交版本号更新
echo -e "${CYAN}📝 提交版本号更新...${NC}"
cd "$DEV_BASE"
if git diff --quiet version .deployed_version 2>/dev/null; then
    echo -e "${YELLOW}  ○ 版本文件无变化，跳过提交${NC}"
else
    git add version .deployed_version
    git commit -m "chore: bump version to v${VERSION}" --no-verify 2>/dev/null && \
        echo -e "${GREEN}  ✓ 版本号已提交: v${VERSION}${NC}" || \
        echo -e "${YELLOW}  ⚠️ 提交失败（可能没有变更）${NC}"
fi
echo ""

# 自动切换到新版本
echo -e "${CYAN}🚀 正在切换到版本 v${VERSION}...${NC}"
"$SCRIPT_DIR/update.sh" "v${VERSION}"

# 检查切换结果
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ 部署 + 切换完成！${NC}"
    echo -e "${CYAN}💡 查看日志: ${YELLOW}docker logs trendradar-prod -f${NC}"
else
    echo ""
    echo -e "${RED}❌ 切换失败${NC}"
    echo -e "${CYAN}💡 请手动执行: ${YELLOW}trend update v${VERSION}${NC}"
fi
