#!/bin/bash

echo "======================================"
echo "TrendRadar 直接运行脚本"
echo "======================================"

# 进入项目目录
cd "$(dirname "$0")/.."

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
export IMMEDIATE_RUN="true"

echo "安装必要的Python依赖..."
pip install --user pytz requests PyYAML

echo "======================================"
echo "配置信息："
echo "邮箱: $EMAIL_FROM"
echo "AI模型: $AI_MODEL"
echo "======================================"

echo "运行TrendRadar..."
python -m trendradar.run --mode once

echo ""
echo "======================================"
echo "执行完成！"
echo "查看输出: ls -la output/"
echo "======================================"