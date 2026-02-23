#!/bin/bash

echo "======================================"
echo "TrendRadar 立即执行脚本"
echo "======================================"

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker 未运行，请先安装并启动 Docker"
    echo "参考文档: agents/DOCKER_INSTALL.md"
    exit 1
fi

# 进入agents目录
cd "$(dirname "$0")"

# 启动服务（如果未启动）
echo "启动TrendRadar服务..."
docker compose -f docker-compose.yml up -d

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 立即执行一次爬虫
echo "立即执行爬虫和推送..."
docker exec trendradar python manage.py run

# 查看执行结果
echo ""
echo "======================================"
echo "执行完成！"
echo ""
echo "查看推送结果："
echo "1. 邮箱: {{EMAIL_ADDRESS}}"
echo "2. Web报告: http://localhost:8080"
echo ""
echo "查看日志: docker logs -f trendradar"
echo "======================================"