#!/bin/bash

# 构建 TrendRadar Docker 镜像脚本
# 使用本地构建，避免从 Docker Hub 拉取镜像

set -e

echo "=========================================="
echo "开始构建 TrendRadar Docker 镜像"
echo "=========================================="

# 切换到项目根目录
cd "$(dirname "$0")/.."

# 检查必要的文件
echo "检查必要的文件..."
if [ ! -f "requirements.txt" ]; then
    echo "错误: requirements.txt 文件不存在"
    exit 1
fi

if [ ! -f "docker/Dockerfile" ]; then
    echo "错误: docker/Dockerfile 文件不存在"
    exit 1
fi

if [ ! -d "config" ]; then
    echo "警告: config 目录不存在，将创建空目录"
    mkdir -p config
fi

if [ ! -d "output" ]; then
    echo "创建 output 目录..."
    mkdir -p output
fi

# 构建主镜像
echo ""
echo "构建 TrendRadar 主镜像..."
docker build -f docker/Dockerfile -t trendradar:local .

echo ""
echo "=========================================="
echo "镜像构建成功！"
echo "镜像标签: trendradar:local"
echo "=========================================="
echo ""
echo "下一步："
echo "1. 编辑 config/config.yaml 配置文件"
echo "2. 运行容器: cd docker && docker-compose -f docker-compose-build.yml up -d"
echo "   或者直接运行: docker run -d --name trendradar -v \$(pwd)/config:/app/config:ro -v \$(pwd)/output:/app/output trendradar:local"
echo ""
