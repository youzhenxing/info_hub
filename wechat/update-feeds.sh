#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#        微信公众号手动更新脚本
# ═══════════════════════════════════════════════════════════════
#
# 用途：手动触发 wewe-rss 更新所有公众号订阅源
# 使用：bash ./update-feeds.sh
#
# ⚠️ 注意：
# - 建议在每天早上 8:00-10:00 执行（避开高峰期）
# - 执行前先访问 http://localhost:4000 检查服务状态
# - 如果账号失效，需要先扫码登录微信读书
#
# ═══════════════════════════════════════════════════════════════

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  微信公众号手动更新${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# 检查容器是否运行
echo -e "${CYAN}🔍 检查容器状态...${NC}"
if ! docker ps | grep -q "wewe-rss"; then
    echo -e "${RED}❌ wewe-rss 容器未运行${NC}"
    echo -e "${YELLOW}💡 请先启动容器: cd /home/zxy/Documents/code/TrendRadar/wechat && docker-compose up -d${NC}"
    exit 1
fi

echo -e "${GREEN}  ✓ wewe-rss 容器运行中${NC}"
echo ""

# 显示当前时间
echo -e "${CYAN}🕐 当前时间: ${YELLOW}$(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo ""

# 确认执行
echo -e "${YELLOW}⚠️  即将触发所有公众号订阅源更新${NC}"
echo -e "${YELLOW}   更新过程可能需要 5-15 分钟（取决于公众号数量）${NC}"
echo ""
read -p "是否继续？(y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}✋ 已取消${NC}"
    exit 0
fi

# 触发更新
echo -e "${CYAN}🚀 触发更新...${NC}"

# 获取所有订阅源 ID
FEED_IDS=$(curl -s http://localhost:4000/feeds | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for feed in data:
        print(feed.get('id', ''))
except:
    pass
" 2>/dev/null)

if [ -z "$FEED_IDS" ]; then
    echo -e "${RED}❌ 无法获取订阅源列表${NC}"
    echo -e "${YELLOW}💡 请检查服务是否正常运行: curl http://localhost:4000/feeds${NC}"
    exit 1
fi

TOTAL=$(echo "$FEED_IDS" | wc -l)
echo -e "${GREEN}  ✓ 找到 ${TOTAL} 个订阅源${NC}"
echo ""

# 逐个触发更新
SUCCESS=0
FAILED=0

for feed_id in $FEED_IDS; do
    if [ -n "$feed_id" ]; then
        echo -ne "${CYAN}  更新订阅源: ${YELLOW}${feed_id}${NC} ... "

        RESULT=$(curl -s -X POST "http://localhost:4000/feeds/${feed_id}/refresh" \
            -H "Content-Type: application/json" \
            -u ":${WEWE_AUTH_CODE:-123456}" 2>&1)

        if echo "$RESULT" | grep -q "success\|ok\|true"; then
            echo -e "${GREEN}✓${NC}"
            ((SUCCESS++))
        else
            echo -e "${RED}✗${NC}"
            ((FAILED++))
        fi

        # 延迟避免请求过快
        sleep 2
    fi
done

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ 更新完成！${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}📊 统计信息:${NC}"
echo -e "   成功: ${GREEN}${SUCCESS}${NC}"
echo -e "   失败: ${RED}${FAILED}${NC}"
echo -e "   总数: ${YELLOW}${TOTAL}${NC}"
echo ""

# 提示下一步操作
echo -e "${CYAN}💡 下一步操作:${NC}"
echo -e "   1. 查看订阅源状态: ${YELLOW}curl http://localhost:4000/feeds | python3 -m json.tool${NC}"
echo -e "   2. 触发微信模块分析: ${YELLOW}trend run wechat${NC}"
echo -e "   3. 查看容器日志: ${YELLOW}docker logs wewe-rss --tail 50${NC}"
echo ""
