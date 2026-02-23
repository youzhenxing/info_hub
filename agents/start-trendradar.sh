#!/bin/bash

# TrendRadar Docker 启动脚本
# 使用 agents 目录下的配置文件

echo "======================================"
echo "TrendRadar Docker 服务启动脚本"
echo "======================================"

# 进入 docker 目录
cd "$(dirname "$0")/../docker"

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker 未运行，请先启动 Docker"
    exit 1
fi

# 停止并删除现有容器
echo "停止现有容器..."
docker-compose down 2>/dev/null || true

# 拉取最新镜像
echo "拉取最新镜像..."
docker-compose pull

# 启动服务
echo "启动 TrendRadar 服务..."
docker-compose -f ../agents/docker-compose.yml up -d

# 检查服务状态
echo ""
echo "服务状态:"
docker-compose -f ../agents/docker-compose.yml ps

echo ""
echo "======================================"
echo "服务已启动！"
echo ""
echo "Web 服务器地址: http://localhost:${WEBSERVER_PORT:-8080}"
echo "MCP 服务地址: http://localhost:3333"
echo ""
echo "查看日志: docker logs -f trendradar"
echo "查看 MCP 日志: docker logs -f trendradar-mcp"
echo ""
echo "停止服务: docker-compose -f ../agents/docker-compose.yml down"
echo "======================================"