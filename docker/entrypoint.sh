#!/bin/bash
set -e

# 检查配置文件
if [ ! -f "/app/config/config.yaml" ] || [ ! -f "/app/config/frequency_words.txt" ]; then
    echo "❌ 配置文件缺失"
    exit 1
fi

# 保存环境变量
env >> /etc/environment

case "${RUN_MODE:-cron}" in
"once")
    echo "🔄 单次执行"
    exec /usr/local/bin/python -m trendradar
    ;;
"cron")
    # 生成 crontab
    > /tmp/crontab
    
    # 1. 主程序（热点+播客）：每 2 小时扫描一次
    if [ "${PODCAST_ENABLED:-true}" = "true" ]; then
        echo "# 主程序定时任务（每2小时）" >> /tmp/crontab
        echo "${CRON_SCHEDULE:-0 */2 * * *} cd /app && /usr/local/bin/python -m trendradar" >> /tmp/crontab
    fi
    
    # 2. 投资模块：每天 6:00, 11:30, 23:30
    if [ "${INVESTMENT_ENABLED:-true}" = "true" ]; then
        echo "# 投资模块定时任务（每天3次）" >> /tmp/crontab
        echo "0 6 * * * cd /app && /usr/local/bin/python /app/run_investment.py" >> /tmp/crontab
        echo "30 11 * * * cd /app && /usr/local/bin/python /app/run_investment.py" >> /tmp/crontab
        echo "30 23 * * * cd /app && /usr/local/bin/python /app/run_investment.py" >> /tmp/crontab
    fi
    
    # 3. 社区监控模块：每天 03:00
    if [ "${COMMUNITY_ENABLED:-true}" = "true" ]; then
        echo "# 社区监控定时任务（每天03:00）" >> /tmp/crontab
        echo "0 3 * * * cd /app && /usr/local/bin/python /app/run_community.py" >> /tmp/crontab
    fi
    
    # 4. 每日任务日志：每天 23:00
    echo "# 每日任务日志（23:00）" >> /tmp/crontab
    echo "0 23 * * * cd /app && /usr/local/bin/python /app/daily_report.py" >> /tmp/crontab

    # 5. 播客数据库备份：每天凌晨 2:00
    if [ "${PODCAST_ENABLED:-true}" = "true" ]; then
        echo "# 播客数据库备份（每天02:00）" >> /tmp/crontab
        echo "0 2 * * * cd /app && /app/scripts/backup_podcast.sh >> /var/log/backup.log 2>&1" >> /tmp/crontab
    fi

    # 配置摘要输出（启动时显式列出关键配置状态）
    echo "=== 配置摘要 ==="
    for VAR in EMAIL_FROM EMAIL_TO EMAIL_SMTP_SERVER EMAIL_SMTP_PORT NOTIFYAPI_KEY; do
        VAL=$(printenv $VAR || true)
        if [ -z "$VAL" ]; then
            echo "  ⚠️  $VAR = [未设置]"
        else
            echo "  ✅  $VAR = [已设置]"
        fi
    done
    echo "================"

    echo "📅 生成的crontab内容:"
    cat /tmp/crontab

    if ! /usr/local/bin/supercronic -test /tmp/crontab; then
        echo "❌ crontab格式验证失败"
        exit 1
    fi

    # 首次部署引导（后台运行，不阻塞 supercronic）
    /usr/local/bin/python /app/bootstrap.py &

    # 启动 Web 服务器（如果配置了）
    if [ "${ENABLE_WEBSERVER:-false}" = "true" ]; then
        echo "🌐 启动 Web 服务器..."
        /usr/local/bin/python manage.py start_webserver
    fi

    echo "⏰ 启动supercronic"
    if [ "${PODCAST_ENABLED:-true}" = "true" ]; then
        echo "   主程序: ${CRON_SCHEDULE:-0 */2 * * *}"
    fi
    if [ "${INVESTMENT_ENABLED:-true}" = "true" ]; then
        echo "   投资: 6:00, 11:30, 23:30"
    fi
    if [ "${COMMUNITY_ENABLED:-true}" = "true" ]; then
        echo "   社区监控: 03:00"
    fi
    echo "   日志报告: 23:00"
    if [ "${PODCAST_ENABLED:-true}" = "true" ]; then
        echo "   播客备份: 02:00"
    fi
    echo "🎯 supercronic 将作为 PID 1 运行"

    exec /usr/local/bin/supercronic -passthrough-logs /tmp/crontab
    ;;
*)
    exec "$@"
    ;;
esac