#!/bin/bash

# TrendRadar 服务状态检查脚本
# 用法: ./status.sh

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 自动检测容器名（支持 trendradar 或 trendradar-prod）
CONTAINER_NAME=$(docker ps --format "{{.Names}}" | grep -E "^trendradar(-prod)?$" | head -1)
if [ -z "$CONTAINER_NAME" ]; then
    CONTAINER_NAME="trendradar"  # 默认值，用于显示帮助命令
fi

# 打印分隔线
print_separator() {
    echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
}

# 打印标题
print_title() {
    echo -e "${BOLD}${BLUE}$1${NC}"
}

# 检查状态图标
check_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌${NC}"
    fi
}

echo ""
print_separator
echo -e "${BOLD}${CYAN}        TrendRadar 服务状态监控面板        ${NC}"
print_separator
echo ""

# ============================================================
# 1. 容器运行状态
# ============================================================
print_title "📦 容器运行状态"
echo ""

if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -q "trendradar"; then
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAMES|trendradar" | \
    awk 'NR==1 {printf "%-20s %-25s %s\n", $1, $2" "$3, $4" "$5" "$6" "$7}
         NR>1 {printf "%-20s %-25s %s\n", $1, $2" "$3, $4" "$5" "$6" "$7}'
    echo ""
    echo -e "  状态: $(check_status 0) ${GREEN}服务正常运行${NC}"
else
    echo -e "  状态: $(check_status 1) ${RED}服务未运行${NC}"
    echo ""
    echo "  💡 启动服务: cd docker && docker compose -f docker-compose-build.yml up -d"
    exit 1
fi

echo ""

# ============================================================
# 2. 重启策略与开机自启
# ============================================================
print_title "🔄 自动化配置"
echo ""

restart_policy=$(docker inspect $CONTAINER_NAME --format '{{.HostConfig.RestartPolicy.Name}}' 2>/dev/null)
if [ "$restart_policy" = "unless-stopped" ] || [ "$restart_policy" = "always" ]; then
    echo -e "  容器重启策略: $(check_status 0) ${restart_policy}"
else
    echo -e "  容器重启策略: $(check_status 1) ${restart_policy}"
fi

docker_enabled=$(systemctl is-enabled docker 2>/dev/null)
if [ "$docker_enabled" = "enabled" ]; then
    echo -e "  Docker 开机自启: $(check_status 0) enabled"
else
    echo -e "  Docker 开机自启: $(check_status 1) ${docker_enabled}"
fi

echo ""

# ============================================================
# 3. 定时任务状态
# ============================================================
print_title "⏰ 定时任务状态"
echo ""

if docker logs $CONTAINER_NAME 2>&1 | grep -q "启动supercronic"; then
    cron_schedule="*/30 * * * *"
    echo -e "  任务调度器: $(check_status 0) supercronic (PID 1)"
    echo -e "  执行频率: ${YELLOW}${cron_schedule}${NC} (每 30 分钟)"

    # 计算下次执行时间
    current_minute=$(date +%M)
    current_second=$(date +%S)
    if [ $current_minute -lt 30 ]; then
        next_minute=30
    else
        next_minute=0
    fi
    next_run_seconds=$((($next_minute - $current_minute) * 60 - $current_second))
    if [ $next_run_seconds -lt 0 ]; then
        next_run_seconds=$((next_run_seconds + 3600))
    fi
    next_run_time=$(date -d "+${next_run_seconds} seconds" "+%H:%M:%S")

    echo -e "  下次执行: ${CYAN}${next_run_time}${NC} ($(($next_run_seconds / 60)) 分钟后)"
else
    echo -e "  任务调度器: $(check_status 1) ${RED}未运行${NC}"
fi

echo ""

# ============================================================
# 4. 最近执行记录
# ============================================================
print_title "📝 最近执行记录"
echo ""

last_run=$(docker logs $CONTAINER_NAME 2>&1 | grep "HTML报告已生成:" | tail -1)
if [ -n "$last_run" ]; then
    echo -e "  ${last_run}"

    # 提取新闻条数
    news_count=$(docker logs $CONTAINER_NAME 2>&1 | grep "成功:" | tail -1 | grep -oP '\d+(?= 条)' | head -1)
    if [ -n "$news_count" ]; then
        echo -e "  抓取数据: ${GREEN}${news_count}${NC} 条新闻"
    fi
else
    echo -e "  ${YELLOW}暂无执行记录${NC}"
fi

echo ""

# ============================================================
# 5. 邮件推送状态
# ============================================================
print_title "📧 邮件推送状态"
echo ""

email_config=$(docker exec $CONTAINER_NAME cat /app/config/config.yaml 2>/dev/null | grep -A 5 "email:" | grep "from:" | awk '{print $2}' | tr -d '"')
if [ -n "$email_config" ] && [ "$email_config" != '""' ]; then
    echo -e "  邮件配置: $(check_status 0) 已配置"
    echo -e "  发件邮箱: ${CYAN}${email_config}${NC}"

    # 检查最近一次邮件发送
    last_email=$(docker logs $CONTAINER_NAME 2>&1 | grep "邮件发送成功" | tail -1)
    if [ -n "$last_email" ]; then
        email_time=$(docker logs $CONTAINER_NAME 2>&1 | grep "邮件发送成功" -B 20 | grep "当前北京时间" | tail -1 | awk '{print $2}')
        echo -e "  最近推送: ${GREEN}成功${NC}"
        if [ -n "$email_time" ]; then
            echo -e "  推送时间: ${email_time}"
        fi
    else
        echo -e "  最近推送: ${YELLOW}暂无记录${NC}"
    fi

    # 推送窗口
    time_window=$(docker exec $CONTAINER_NAME cat /app/config/config.yaml 2>/dev/null | grep -A 3 "time_window:" | grep "start:" | awk '{print $2}' | tr -d '"')
    time_window_end=$(docker exec $CONTAINER_NAME cat /app/config/config.yaml 2>/dev/null | grep -A 3 "time_window:" | grep "end:" | awk '{print $2}' | tr -d '"')
    if [ -n "$time_window" ]; then
        echo -e "  推送窗口: ${YELLOW}${time_window} - ${time_window_end}${NC} (每天一次)"
    fi
else
    echo -e "  邮件配置: $(check_status 1) ${YELLOW}未配置${NC}"
fi

echo ""

# ============================================================
# 6. 数据存储信息
# ============================================================
print_title "💾 数据存储信息"
echo ""

# 获取今天的日期
today=$(date +%Y-%m-%d)

# 检查 HTML 报告
html_dir="../output/html/${today}"
if [ -d "$html_dir" ]; then
    html_count=$(ls -1 "$html_dir"/*.html 2>/dev/null | wc -l)
    latest_html=$(ls -t "$html_dir"/*.html 2>/dev/null | head -1)
    if [ -n "$latest_html" ]; then
        html_size=$(du -h "$latest_html" | awk '{print $1}')
        echo -e "  今日报告: ${GREEN}${html_count}${NC} 个"
        echo -e "  最新报告: ${CYAN}$(basename $latest_html)${NC} (${html_size})"
    fi
else
    echo -e "  今日报告: ${YELLOW}暂无${NC}"
fi

# 检查数据库
db_file="../output/news/${today}.db"
if [ -f "$db_file" ]; then
    db_size=$(du -h "$db_file" | awk '{print $1}')
    echo -e "  新闻数据库: ${GREEN}存在${NC} (${db_size})"
else
    echo -e "  新闻数据库: ${YELLOW}暂无${NC}"
fi

echo ""

# ============================================================
# 7. 监控平台
# ============================================================
print_title "🌐 监控平台"
echo ""

platforms=$(docker logs $CONTAINER_NAME 2>&1 | grep "配置的监控平台:" | tail -1 | sed 's/.*\[\(.*\)\]/\1/' | sed "s/', '/\n  • /g" | sed "s/'//g")
if [ -n "$platforms" ]; then
    echo -e "  • $platforms"
else
    echo -e "  ${YELLOW}暂无数据${NC}"
fi

echo ""

# ============================================================
# 8. 快速操作指南
# ============================================================
print_title "🛠️  快速操作"
echo ""
echo -e "  查看实时日志:    ${CYAN}docker logs $CONTAINER_NAME -f${NC}"
echo -e "  手动执行一次:    ${CYAN}docker exec -it $CONTAINER_NAME python manage.py run${NC}"
echo -e "  重启服务:        ${CYAN}docker restart $CONTAINER_NAME${NC}"
echo -e "  停止服务:        ${CYAN}docker compose -f docker-compose-build.yml down${NC}"
echo -e "  编辑配置:        ${CYAN}nano ../config/config.yaml${NC}"
echo ""

print_separator
echo ""
