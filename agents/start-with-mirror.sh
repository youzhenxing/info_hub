#!/bin/bash

echo "======================================"
echo "Docker 镜像拉取解决方案"
echo "======================================"

# 设置镜像源环境变量
export DOCKER_REGISTRY_MIRROR=https://dockerhub.azk8s.cn

# 尝试从国内镜像源拉取
echo "尝试从国内镜像源拉取..."
docker pull $DOCKER_REGISTRY_MIRROR/wantcat/trendradar:latest

if [ $? -eq 0 ]; then
    echo "✅ 镜像拉取成功！"
    
    # 重新标记镜像
    docker tag $DOCKER_REGISTRY_MIRROR/wantcat/trendradar:latest wantcat/trendradar:latest
    
    # 启动服务
    echo "启动TrendRadar服务..."
    cd /home/zxy/Documents/code/TrendRadar/agents
    
    # 使用docker-compose-simple.yml启动
    docker compose -f docker-compose-simple.yml up -d
    
    # 等待服务启动
    sleep 10
    
    # 检查服务状态
    docker ps | grep trendradar
    
    # 手动执行一次爬虫
    echo "立即执行一次爬虫..."
    sleep 5
    docker exec trendradar python -m trendradar --mode once
    
    echo ""
    echo "======================================"
    echo "服务已启动！"
    echo "Web地址: http://localhost:8080"
    echo "查看日志: docker logs -f trendradar"
    echo "======================================"
else
    echo "❌ 镜像拉取失败，尝试直接运行Python..."
    
    # 直接使用Python运行
    cd /home/zxy/Documents/code/TrendRadar
    
    # 设置环境变量
    export EMAIL_FROM="{{EMAIL_ADDRESS}}"
    export EMAIL_PASSWORD="your_email_auth_code"
    export EMAIL_TO="{{EMAIL_ADDRESS}}"
    export EMAIL_SMTP_SERVER="smtp.163.com"
    export EMAIL_SMTP_PORT="465"
    
    export AI_ANALYSIS_ENABLED="true"
    export AI_API_KEY="your_zhipu_api_key"
    export AI_MODEL="zhipuai/glm-4.6"
    export AI_API_BASE="https://open.bigmodel.cn/api/paas/v4"
    
    export ENABLE_WEBSERVER="true"
    export WEBSERVER_PORT="8080"
    export RUN_MODE="once"
    
    # 安装必要依赖
    pip install --user requests pytz PyYAML litellm --no-deps -q
    
    # 运行
    python -m trendradar --mode once
fi