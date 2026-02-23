#!/bin/bash

# TrendRadar 生产环境初始化脚本
# 创建生产环境的目录结构和初始配置

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
DEV_BASE="/home/zxy/Documents/code/TrendRadar"

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  TrendRadar 生产环境初始化${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# 检查开发环境
if [ ! -d "$DEV_BASE" ]; then
    echo -e "${RED}❌ 错误：开发环境不存在: $DEV_BASE${NC}"
    exit 1
fi

# 检查生产环境是否已存在
if [ -d "$PROD_BASE" ]; then
    echo -e "${YELLOW}⚠️  生产环境目录已存在: $PROD_BASE${NC}"
    echo -e "${YELLOW}   是否继续？这将重新初始化目录结构 (y/N)${NC}"
    read -r confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${CYAN}✋ 已取消${NC}"
        exit 0
    fi
fi

# 创建目录结构
echo -e "${CYAN}📁 创建目录结构...${NC}"

mkdir -p "$PROD_BASE/releases"
mkdir -p "$PROD_BASE/shared/config"
mkdir -p "$PROD_BASE/shared/output/html"
mkdir -p "$PROD_BASE/shared/output/news"
mkdir -p "$PROD_BASE/shared/output/rss"
mkdir -p "$PROD_BASE/versions/history"

echo -e "${GREEN}  ✓ 目录创建完成${NC}"

# 复制配置文件到 shared/config
echo -e "${CYAN}📋 复制配置文件...${NC}"

if [ -d "$DEV_BASE/config" ]; then
    cp -r "$DEV_BASE/config/"* "$PROD_BASE/shared/config/" 2>/dev/null || true
fi

# 复制 .env 文件
if [ -f "$DEV_BASE/agents/.env" ]; then
    cp "$DEV_BASE/agents/.env" "$PROD_BASE/shared/.env"
    echo -e "${GREEN}  ✓ 配置文件和环境变量已复制${NC}"
elif [ ! -d "$DEV_BASE/config" ]; then
    echo -e "${YELLOW}  ⚠️  开发环境配置目录不存在，请稍后手动配置${NC}"
else
    echo -e "${YELLOW}  ⚠️  警告: agents/.env 文件不存在，请手动创建${NC}"
    echo -e "${GREEN}  ✓ 配置文件已复制${NC}"
fi

# 创建初始 manifest.yaml
echo -e "${CYAN}📝 创建版本清单...${NC}"

cat > "$PROD_BASE/versions/manifest.yaml" << 'EOF'
# TrendRadar 版本清单
# 此文件记录所有已部署的版本信息

current_version: null
previous_version: null
install_path: /home/zxy/Documents/install/trendradar
initialized_at: $(date -u +"%Y-%m-%dT%H:%M:%S+00:00")

versions: []
EOF

# 替换时间戳
sed -i "s/\$(date -u +\"%Y-%m-%dT%H:%M:%S+00:00\")/$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")/" "$PROD_BASE/versions/manifest.yaml"

echo -e "${GREEN}  ✓ 版本清单已创建${NC}"

# 创建 README
echo -e "${CYAN}📄 创建 README...${NC}"

cat > "$PROD_BASE/README.md" << 'EOF'
# TrendRadar 生产环境

此目录为 TrendRadar 的生产部署环境。

## 目录结构

- `current/` - 软链接，指向当前运行的版本
- `releases/` - 所有已发布的版本
- `shared/` - 跨版本共享的数据和配置
  - `config/` - 配置文件
  - `output/` - 输出数据（HTML 报告、数据库等）
- `versions/` - 版本管理信息
  - `manifest.yaml` - 版本清单
  - `history/` - 各版本详细记录

## 使用方法

查看可用命令：
```bash
trend help
```

版本管理命令：
- `trend deploy` - 发布新版本
- `trend update <version>` - 更新到指定版本
- `trend rollback` - 回退到上一版本
- `trend versions` - 查看所有版本
- `trend production` - 生产环境管理

## 注意事项

1. 不要手动修改 `current` 软链接
2. 配置文件在 `shared/config/` 目录
3. 输出数据在 `shared/output/` 目录
4. 版本回退不会删除数据，只是切换运行的代码版本
EOF

echo -e "${GREEN}  ✓ README 已创建${NC}"

# 设置权限
echo -e "${CYAN}🔒 设置权限...${NC}"
chmod -R 755 "$PROD_BASE"
echo -e "${GREEN}  ✓ 权限设置完成${NC}"

# 显示目录结构
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ 生产环境初始化完成！${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}📁 目录结构:${NC}"
tree -L 2 "$PROD_BASE" 2>/dev/null || ls -la "$PROD_BASE"
echo ""
echo -e "${CYAN}💡 下一步:${NC}"
echo -e "  1. 检查配置文件: $PROD_BASE/shared/config/config.yaml"
echo -e "  2. 发布第一个版本: ${YELLOW}trend deploy${NC}"
echo -e "  3. 启动生产环境: ${YELLOW}trend update <version>${NC}"
echo ""
