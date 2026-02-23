#!/bin/bash
# ═══════════════════════════════════════════════════════════
#   TrendRadar 生产环境验证脚本
#   用法: bash deploy/verify-production.sh [--all]
#   --all  同时验证公众号服务（wechat-service + wewe-rss）
# ═══════════════════════════════════════════════════════════
set -euo pipefail

# 颜色
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

VERIFY_ALL=false
[[ "${1:-}" == "--all" ]] && VERIFY_ALL=true

PASS=0; FAIL=0; WARN=0
CONTAINER="trendradar-prod"

pass() { echo -e "  ${GREEN}✅ $1${NC}"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}❌ $1${NC}"; FAIL=$((FAIL + 1)); }
warn() { echo -e "  ${YELLOW}⚠️  $1${NC}"; WARN=$((WARN + 1)); }
step() { echo -e "\n${CYAN}── $1 ──${NC}"; }

# 轮询容器日志，等待关键字出现
# 用法: wait_for_keyword <关键字> <超时秒数>
# 返回: 0=找到，1=超时
wait_for_keyword() {
    local keyword="$1"
    local timeout_sec="$2"
    local elapsed=0
    while [ $elapsed -lt $timeout_sec ]; do
        if docker logs "${CONTAINER}" --tail 300 2>&1 | grep -q "$keyword"; then
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    return 1
}

# ─── Phase 1: 容器状态 ─────────────────────────────────
step "Phase 1 / 容器状态检查"
if docker ps --format "{{.Names}}" | grep -q "^${CONTAINER}$"; then
    STATUS=$(docker ps --format "{{.Status}}" -f "name=^${CONTAINER}$")
    pass "trendradar-prod: ${STATUS}"
else
    fail "trendradar-prod 未运行"
    echo -e "  ${CYAN}请先执行: cd \$PROD_BASE/current && docker compose up -d${NC}"
    exit 1
fi

# ─── Phase 2: 配置摘要校验 ──────────────────────────────
step "Phase 2 / 启动配置摘要"
CONFIG_LOG=$(docker logs "${CONTAINER}" 2>&1 | grep -A 15 "=== 配置摘要 ===" | head -20)
if [ -z "$CONFIG_LOG" ]; then
    warn "未找到配置摘要日志（可能是旧版本容器，需重启生效新 entrypoint）"
else
    echo "$CONFIG_LOG"
    # 自动检查关键变量
    for VAR in EMAIL_FROM EMAIL_TO; do
        if echo "$CONFIG_LOG" | grep -q "${VAR}.*\[未设置\]"; then
            fail "${VAR} 未设置 — 邮件将无法发送"
        fi
    done
    pass "配置摘要输出正常"
fi

# ─── Phase 3: 健康检查 ──────────────────────────────────
step "Phase 3 / 系统健康检查"
if docker exec "${CONTAINER}" python -m trendradar.cli health; then
    pass "健康检查通过"
else
    warn "健康检查有告警，详见上方输出（不阻塞后续验证）"
fi

# ─── Phase 4A: 投资模块 ──────────────────────────────────
step "Phase 4A / 投资模块验证"
# IMMEDIATE_RUN 的输出走 entrypoint（PID 1），会出现在 docker logs 里
# 先快速检查是否有 IMMEDIATE_RUN 执行痕迹
if docker logs "${CONTAINER}" 2>&1 | grep -q "立即执行一次投资模块"; then
    echo -e "  ${BLUE}检测到 IMMEDIATE_RUN 已触发，轮询结果（最多 120s）…${NC}"
    if wait_for_keyword "投资报告推送成功" 120; then
        pass "投资模块完成 — IMMEDIATE_RUN 执行正常"
    else
        warn "投资模块未在 120s 内产生成功日志（可能首次无数据或仍在处理）"
    fi
else
    # IMMEDIATE_RUN 未启用（默认 false），手动触发一次
    echo -e "  ${BLUE}IMMEDIATE_RUN 未启用，手动触发 run_investment.py…${NC}"
    INVEST_OUT=$(timeout 120 docker exec "${CONTAINER}" python /app/run_investment.py 2>&1) || true
    echo "$INVEST_OUT"
    if echo "$INVEST_OUT" | grep -q "投资报告推送成功"; then
        pass "投资模块完成 — 推送正常"
    elif echo "$INVEST_OUT" | grep -q "❌"; then
        fail "投资模块执行失败"
    else
        warn "投资模块未产生成功信号（可能首次无数据）"
    fi
fi

# ─── Phase 4B: 社区模块（触发 + 验证启动） ────────────
# 社区模块完整流程耗时 10-15min（逐条 AI 分析），不等全部完成
# 验证策略：确认模块启动、数据收集阶段通过即可
step "Phase 4B / 社区模块验证"
echo -e "  ${BLUE}触发 run_community.py，等待初始数据收集信号（最多 30s）…${NC}"
COMMUNITY_OUT=$(timeout 30 docker exec "${CONTAINER}" python /app/run_community.py 2>&1) || true
echo "$COMMUNITY_OUT"
if echo "$COMMUNITY_OUT" | grep -q "社区热点推送成功"; then
    pass "社区模块完成 — 推送正常"
elif echo "$COMMUNITY_OUT" | grep -q "社区热点推送失败\|社区监控模块运行失败"; then
    fail "社区模块执行失败"
elif echo "$COMMUNITY_OUT" | grep -qE "\[Collector\].+[1-9][0-9]* 条"; then
    # 至少一个数据源成功收集（非零条），模块启动和数据采集通路正常
    pass "社区模块启动正常 — 数据源可达，AI 分析将在后台运行"
else
    warn "社区模块未在 30s 内收集到任何数据"
fi

# ─── Phase 4C: 日志报告模块（触发 + 捕获输出） ────────
step "Phase 4C / 日志报告模块验证"
echo -e "  ${BLUE}触发 daily_report.py…${NC}"
REPORT_OUT=$(timeout 60 docker exec "${CONTAINER}" python /app/daily_report.py 2>&1) || true
echo "$REPORT_OUT"
if echo "$REPORT_OUT" | grep -q "每日日志报告生成完成"; then
    pass "日志报告模块完成 — 报告生成+邮件发送正常"
elif echo "$REPORT_OUT" | grep -q "生成日志报告失败"; then
    fail "日志报告模块执行失败"
else
    warn "日志报告模块未在 60s 内完成"
fi

# ─── Phase 5: 公众号服务 (仅 --all) ────────────────────
if $VERIFY_ALL; then
    step "Phase 5 / 公众号服务验证"
    # 5a. 容器状态
    if docker ps --format "{{.Names}}" | grep -q "^wechat-service$"; then
        pass "wechat-service 运行中"
    else
        fail "wechat-service 未运行 — 请执行: cd wechat && docker compose up -d"
    fi
    # 5b. wewe-rss 状态
    if docker ps --format "{{.Names}}" | grep -q "^wewe-rss$"; then
        pass "wewe-rss 运行中"
    else
        fail "wewe-rss 未运行"
    fi
    # 5c. 网络连通性（用 python 代替 wget/curl，避免镜像内缺工具）
    if docker exec wechat-service python3 -c "
import urllib.request, sys
try:
    urllib.request.urlopen('http://wewe-rss:4000', timeout=5)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        pass "wechat-service → wewe-rss 网络连通"
    else
        fail "wechat-service 无法访问 wewe-rss:4000（网络隔离？）"
    fi
fi

# ─── 汇总报告 ───────────────────────────────────────────
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BOLD}  验证汇总${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "  通过: ${GREEN}${PASS}${NC}  警告: ${YELLOW}${WARN}${NC}  失败: ${RED}${FAIL}${NC}"
if [ $FAIL -gt 0 ]; then
    echo -e "${RED}  结论: 存在失败项，需人工处理${NC}"
    exit 1
elif [ $WARN -gt 0 ]; then
    echo -e "${YELLOW}  结论: 基本正常，有警告项建议关注${NC}"
    exit 0
else
    echo -e "${GREEN}  结论: 全部验证通过 ✓${NC}"
    exit 0
fi
